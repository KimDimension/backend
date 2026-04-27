import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.question import AIQuestion, AIQuestionStatus, AIQuestionType, CommonQuestion
from app.models.record import DailyRecord
from app.models.survey import RejectedQPattern
from app.models.user import User, UserRole
from app.schemas.question import (
    CommonQuestionCreate, CommonQuestionUpdate, CommonQuestionResponse
)

router = APIRouter(prefix="/questions", tags=["질문"])


def _require_doctor(current_user: User):
    if current_user.role != UserRole.doctor:
        raise HTTPException(status_code=403, detail="의사만 접근할 수 있습니다.")


@router.get(
    "/common",
    response_model=List[CommonQuestionResponse],
    summary="공통 질문 목록 (active 필터 지원)",
)
def list_common_questions(
    active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(CommonQuestion)
    if active is not None:
        q = q.filter(CommonQuestion.is_active == active)
    return q.order_by(CommonQuestion.created_at.asc()).all()


@router.post(
    "/common",
    response_model=CommonQuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="공통 질문 생성 (의사 전용)",
)
def create_common_question(
    body: CommonQuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_doctor(current_user)
    try:
        q_type = AIQuestionType(body.question_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 질문 유형: {body.question_type}")
    options_json = None
    if q_type in (AIQuestionType.single_select, AIQuestionType.multi_select):
        if body.options:
            options_json = json.dumps(body.options, ensure_ascii=False)
    q = CommonQuestion(
        doctor_id=current_user.id,
        question_text=body.question_text,
        question_type=q_type,
        options=options_json,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.patch(
    "/common/{question_id}",
    response_model=CommonQuestionResponse,
    summary="공통 질문 수정 (의사 전용)",
)
def update_common_question(
    question_id: int,
    body: CommonQuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_doctor(current_user)
    q = db.query(CommonQuestion).filter(CommonQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다.")
    if body.question_text is not None:
        q.question_text = body.question_text
    if body.question_type is not None:
        try:
            q.question_type = AIQuestionType(body.question_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"유효하지 않은 질문 유형: {body.question_type}")
    if body.options is not None:
        q_type = q.question_type
        if q_type in (AIQuestionType.single_select, AIQuestionType.multi_select):
            q.options = json.dumps(body.options, ensure_ascii=False)
        else:
            q.options = None
    elif body.question_type is not None:
        new_type = AIQuestionType(body.question_type)
        if new_type not in (AIQuestionType.single_select, AIQuestionType.multi_select):
            q.options = None
    if body.is_active is not None:
        q.is_active = body.is_active
    q.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(q)
    return q


@router.delete(
    "/common/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="공통 질문 삭제 (의사 전용)",
)
def delete_common_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_doctor(current_user)
    q = db.query(CommonQuestion).filter(CommonQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다.")
    db.delete(q)
    db.commit()


@router.patch(
    "/common/{question_id}/toggle",
    response_model=CommonQuestionResponse,
    summary="공통 질문 활성/비활성 전환 (의사 전용)",
)
def toggle_common_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_doctor(current_user)
    q = db.query(CommonQuestion).filter(CommonQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다.")
    q.is_active = not q.is_active
    q.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(q)
    return q


class AIQuestionRejectRequest(BaseModel):
    scope: str  # "patient" | "global"


@router.get(
    "/ai",
    summary="담당 환자 AI 질문 목록 조회 (의사 전용)",
)
def list_ai_questions(
    patient_id: Optional[int] = Query(None, description="특정 환자 필터링"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_doctor(current_user)

    my_patients = (
        db.query(User)
        .filter(User.doctor_id == current_user.id, User.is_active == True)
        .all()
    )
    patient_ids = [p.id for p in my_patients]

    if not patient_ids:
        return []

    query = (
        db.query(AIQuestion, DailyRecord, User)
        .join(DailyRecord, AIQuestion.daily_record_id == DailyRecord.id)
        .join(User, AIQuestion.patient_id == User.id)
        .filter(
            AIQuestion.patient_id.in_(patient_ids),
            AIQuestion.status != AIQuestionStatus.rejected_global,
        )
    )
    if patient_id:
        query = query.filter(AIQuestion.patient_id == patient_id)

    rows = query.order_by(AIQuestion.created_at.desc()).limit(200).all()

    return [
        {
            "id":            q.id,
            "patient_id":    q.patient_id,
            "patient_name":  patient.name,
            "record_id":     record.id,
            "record_date":   record.record_date.isoformat(),
            "question_text": q.question_text,
            "question_type": q.question_type.value,
            "reason":        q.reason,
            "status":        q.status.value,
            "created_at":    q.created_at.isoformat(),
        }
        for q, record, patient in rows
    ]


@router.post(
    "/ai/{question_id}/reject",
    summary="AI 질문 거절 (의사 전용)",
)
def reject_ai_question(
    question_id: int,
    body: AIQuestionRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_doctor(current_user)

    if body.scope not in ("patient", "global"):
        raise HTTPException(status_code=400, detail="scope는 'patient' 또는 'global'이어야 합니다.")

    q = db.query(AIQuestion).filter(AIQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다.")

    if body.scope == "global":
        q.status = AIQuestionStatus.rejected_global
        existing = db.query(RejectedQPattern).filter(
            RejectedQPattern.pattern == q.question_text,
            RejectedQPattern.patient_id.is_(None),
        ).first()
        if not existing:
            db.add(RejectedQPattern(pattern=q.question_text, patient_id=None))
    else:
        q.status = AIQuestionStatus.rejected_for_patient
        existing = db.query(RejectedQPattern).filter(
            RejectedQPattern.pattern == q.question_text,
            RejectedQPattern.patient_id == q.patient_id,
        ).first()
        if not existing:
            db.add(RejectedQPattern(pattern=q.question_text, patient_id=q.patient_id))

    db.commit()
    return {"success": True, "scope": body.scope, "question_id": question_id}
