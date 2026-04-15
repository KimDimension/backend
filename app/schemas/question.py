from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── 공통 질문 ──────────────────────────────────────────────
class CommonQuestionCreate(BaseModel):
    question_text: str


class CommonQuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    is_active: Optional[bool] = None


class CommonQuestionResponse(BaseModel):
    id: int
    question_text: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── AI 맞춤 질문 ───────────────────────────────────────────
class AIQuestionResponse(BaseModel):
    id: int
    question_text: str
    reason: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}
