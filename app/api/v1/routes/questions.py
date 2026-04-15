from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.question import CommonQuestion
from app.models.user import User, UserRole
from app.schemas.question import (
    CommonQuestionCreate, CommonQuestionUpdate, CommonQuestionResponse
)

router = APIRouter(prefix="/questions", tags=["질문"])


def _require_doctor(current_user: User):
    if current_user.role != UserRole.doctor:
        raise HTTPException(status_code=403, detail="의사만 접근할 수 있습니다.")


# ── GET 공통 질문 목록 ─────────────────────────────────────
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


# ── POST 공통 질문 생성 ────────────────────────────────────
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
    q = CommonQuestion(doctor_id=current_user.id, question_text=body.question_text)
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


# ── PATCH 공통 질문 수정 ───────────────────────────────────
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
    if body.is_active is not None:
        q.is_active = body.is_active
    q.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(q)
    return q


# ── DELETE 공통 질문 삭제 ──────────────────────────────────
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


# ── PATCH 활성/비활성 토글 ─────────────────────────────────
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
