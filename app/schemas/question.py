from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


# ── 공통 질문 ──────────────────────────────────────────────
class CommonQuestionCreate(BaseModel):
    question_text: str
    question_type: str = "yes_no"          # yes_no | single_select | multi_select | short_text
    options: Optional[List[str]] = None    # single/multi_select 선택지 목록


class CommonQuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[List[str]] = None
    is_active: Optional[bool] = None


class CommonQuestionResponse(BaseModel):
    id: int
    question_text: str
    question_type: str
    options: Optional[str] = None          # JSON 문자열 그대로 반환 (프론트에서 파싱)
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
