"""
대화형 문진 API
환자: 문진 시작 → 메시지 전송 → 종료
의사: 대화 내용 조회
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.conversation import Conversation, ConversationMessage, ConversationStatus, MessageRole
from app.models.record import DailyRecord, RiskLevel
from app.models.question import CommonQuestion, AIQuestion, AIQuestionStatus
from app.models.survey import SurveyResponse, QuestionType
from app.models.user import User, UserRole
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["대화형 문진"])

AI_SERVER_URL = "http://ai:8001"   # docker-compose 서비스명


# ── 스키마 ─────────────────────────────────────────────────────

class StartRequest(BaseModel):
    record_id: int


class MessageRequest(BaseModel):
    conversation_id: int
    patient_answer: str   # 환자가 입력한 답변


class ConversationMessageOut(BaseModel):
    id: int
    role: str
    content: str
    is_urgent_flag: bool
    created_at: str


class AIResponse(BaseModel):
    conversation_id: int
    type: str              # "question" | "urgent" | "done"
    content: str           # AI 메시지
    is_done: bool          # 문진 종료 여부


# ── 헬퍼 ───────────────────────────────────────────────────────

def _get_record_data(record: DailyRecord) -> dict:
    """DailyRecord → AI 서버에 넘길 dict"""
    return {
        "blood_pressure":        record.blood_pressure,
        "weight":                float(record.weight) if record.weight else None,
        "total_ultrafiltration": float(record.total_ultrafiltration) if record.total_ultrafiltration else None,
        "fasting_blood_glucose": float(record.fasting_blood_glucose) if record.fasting_blood_glucose else None,
        "turbid_peritoneal":     record.turbid_peritoneal,
        "urine_count":           record.urine_count,
        "memo":                  record.memo,
    }


def _get_common_qa(record_id: int, patient_id: int, db: Session) -> list[dict]:
    """공통 질문 + 환자 답변 목록 조립"""
    common_qs = db.query(CommonQuestion).filter(CommonQuestion.is_active == True).all()
    responses = (
        db.query(SurveyResponse)
        .filter(
            SurveyResponse.daily_record_id == record_id,
            SurveyResponse.question_type == QuestionType.common,
        )
        .all()
    )
    resp_map = {r.question_id: r for r in responses}

    result = []
    for q in common_qs:
        r = resp_map.get(q.id)
        result.append({
            "question_text": q.question_text,
            "choice":        r.choice.value if r and r.choice else None,
            "text_answer":   r.text_answer if r else None,
        })
    return result


def _get_history(conversation: Conversation) -> list[dict]:
    """대화 히스토리 → AI 서버 포맷"""
    return [
        {"role": msg.role.value, "content": msg.content}
        for msg in conversation.messages
    ]


async def _call_ai_server(endpoint: str, payload: dict) -> dict:
    """AI 서버 HTTP 호출"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{AI_SERVER_URL}{endpoint}", json=payload)
        resp.raise_for_status()
        return resp.json()


async def _generate_and_save_summary(record: DailyRecord, conversation: Conversation, db: Session):
    """문진 종료 후 AI 서버에 요약 요청 → DB 저장"""
    try:
        record_data = _get_record_data(record)
        common_qa = _get_common_qa(record.id, record.patient_id, db)
        history = _get_history(conversation)

        result = await _call_ai_server("/summary", {
            "record_data":            record_data,
            "common_qa":              common_qa,
            "conversation_messages":  history,
        })

        # daily_records 업데이트
        record.risk_level  = RiskLevel(result["risk_level"])
        record.ai_summary  = result["ai_summary"]
        record.emr_soap    = result["emr_soap"]
        db.commit()
        logger.info(f"[summary] record_id={record.id} risk={result['risk_level']}")

    except Exception as e:
        logger.error(f"요약 생성 실패 record_id={record.id}: {e}")


# ── 엔드포인트 ──────────────────────────────────────────────────

@router.post("/start", response_model=AIResponse, summary="문진 시작")
async def start_conversation(
    body: StartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    공통 질문 답변 완료 후 환자가 호출.
    대화 세션 생성 → AI 서버에 첫 질문 요청 → 반환.
    """
    if current_user.role != UserRole.patient:
        raise HTTPException(status_code=403, detail="환자만 접근할 수 있습니다.")

    record = db.query(DailyRecord).filter(DailyRecord.id == body.record_id).first()
    if not record or record.patient_id != current_user.id:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")

    # 이미 대화가 있으면 기존 대화 반환
    existing = db.query(Conversation).filter(
        Conversation.daily_record_id == body.record_id
    ).first()
    if existing and existing.status != ConversationStatus.in_progress:
        raise HTTPException(status_code=400, detail="이미 완료된 문진입니다.")
    if existing:
        # 진행 중인 대화가 있으면 마지막 AI 메시지 반환
        last_ai = next(
            (m for m in reversed(existing.messages) if m.role == MessageRole.ai), None
        )
        return AIResponse(
            conversation_id=existing.id,
            type="question",
            content=last_ai.content if last_ai else "문진을 계속 진행해 주세요.",
            is_done=False,
        )

    # 공통 질문 답변 조회
    common_qa = _get_common_qa(body.record_id, current_user.id, db)
    record_data = _get_record_data(record)

    # AI 서버에 첫 질문 요청
    try:
        ai_result = await _call_ai_server("/conversation/start", {
            "record_data": record_data,
            "common_qa":   common_qa,
        })
    except Exception as e:
        logger.error(f"AI 서버 호출 실패: {e}")
        raise HTTPException(status_code=503, detail="AI 서버에 연결할 수 없습니다.")

    # 대화 세션 생성
    conversation = Conversation(
        daily_record_id=body.record_id,
        patient_id=current_user.id,
        status=ConversationStatus.in_progress,
    )
    db.add(conversation)
    db.flush()

    # 첫 AI 메시지 저장
    is_urgent = ai_result["type"] == "urgent"
    db.add(ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.ai,
        content=ai_result["content"],
        is_urgent_flag=is_urgent,
    ))

    if ai_result["type"] in ("done", "urgent"):
        conversation.status = ConversationStatus.aborted if is_urgent else ConversationStatus.completed
        conversation.ended_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(conversation)

    # 즉시 종료 케이스면 요약 생성
    if conversation.status != ConversationStatus.in_progress:
        await _generate_and_save_summary(record, conversation, db)

    return AIResponse(
        conversation_id=conversation.id,
        type=ai_result["type"],
        content=ai_result["content"],
        is_done=conversation.status != ConversationStatus.in_progress,
    )


@router.post("/message", response_model=AIResponse, summary="환자 답변 전송 → 다음 질문")
async def send_message(
    body: MessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    환자가 답변 입력 → 저장 → AI 서버에 다음 질문 요청 → 반환.
    type이 "done" 또는 "urgent"이면 문진 종료.
    """
    if current_user.role != UserRole.patient:
        raise HTTPException(status_code=403, detail="환자만 접근할 수 있습니다.")

    conversation = db.query(Conversation).filter(
        Conversation.id == body.conversation_id,
        Conversation.patient_id == current_user.id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    if conversation.status != ConversationStatus.in_progress:
        raise HTTPException(status_code=400, detail="이미 완료된 문진입니다.")

    record = db.query(DailyRecord).filter(DailyRecord.id == conversation.daily_record_id).first()

    # 환자 답변 저장
    db.add(ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=body.patient_answer,
    ))
    db.flush()

    # 현재 턴 수 계산 (AI 메시지 수)
    turn_number = sum(1 for m in conversation.messages if m.role == MessageRole.ai)

    # 히스토리 구성 (환자 답변 포함)
    history = _get_history(conversation)
    record_data = _get_record_data(record)
    common_qa = _get_common_qa(record.id, current_user.id, db)

    # AI 서버에 다음 질문 요청
    try:
        ai_result = await _call_ai_server("/conversation/next", {
            "record_data":    record_data,
            "common_qa":      common_qa,
            "history":        history,
            "patient_answer": body.patient_answer,
            "turn_number":    turn_number,
        })
    except Exception as e:
        logger.error(f"AI 서버 호출 실패: {e}")
        raise HTTPException(status_code=503, detail="AI 서버에 연결할 수 없습니다.")

    # AI 응답 메시지 저장
    is_urgent = ai_result["type"] == "urgent"
    db.add(ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.ai,
        content=ai_result["content"],
        is_urgent_flag=is_urgent,
    ))

    # 종료 처리
    is_done = ai_result["type"] in ("done", "urgent")
    if is_done:
        conversation.status = ConversationStatus.aborted if is_urgent else ConversationStatus.completed
        conversation.ended_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(conversation)

    # 종료 시 요약 생성
    if is_done:
        await _generate_and_save_summary(record, conversation, db)

    return AIResponse(
        conversation_id=conversation.id,
        type=ai_result["type"],
        content=ai_result["content"],
        is_done=is_done,
    )


@router.get("/{conversation_id}/messages", summary="대화 내용 조회 (환자/의사 공용)")
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    대화 전체 메시지 반환.
    환자는 본인 대화만, 의사는 모든 대화 조회 가능.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")

    if current_user.role == UserRole.patient and conversation.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

    return {
        "conversation_id": conversation.id,
        "status":          conversation.status.value,
        "started_at":      conversation.started_at.isoformat(),
        "ended_at":        conversation.ended_at.isoformat() if conversation.ended_at else None,
        "messages": [
            {
                "id":             m.id,
                "role":           m.role.value,
                "content":        m.content,
                "is_urgent_flag": m.is_urgent_flag,
                "created_at":     m.created_at.isoformat(),
            }
            for m in conversation.messages
        ],
    }


@router.get("/by-record/{record_id}", summary="기록 ID로 대화 조회")
def get_conversation_by_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """record_id로 연결된 대화 세션 조회 (없으면 null)"""
    conversation = db.query(Conversation).filter(
        Conversation.daily_record_id == record_id
    ).first()

    if not conversation:
        return {"conversation": None}

    if current_user.role == UserRole.patient and conversation.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

    return {
        "conversation": {
            "id":         conversation.id,
            "status":     conversation.status.value,
            "started_at": conversation.started_at.isoformat(),
            "ended_at":   conversation.ended_at.isoformat() if conversation.ended_at else None,
            "message_count": len(conversation.messages),
        }
    }
