from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


# ── 공통 질문 ──────────────────────────────────────────────
class CommonQuestionCreate(BaseModel):
    question_text: str
    question_type: str = "yes_no"          # yes_no | single_select | multi_select | short_text
    options: Optional[List[str]] = None    # single/multi_select 선택지 목록
    target_all_patients: bool = True       # False 이면 patient_ids 에 명시된 환자만
    patient_ids: Optional[List[int]] = None  # target_all_patients=False 일 때 대상 환자 ID


class CommonQuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[List[str]] = None
    is_active: Optional[bool] = None
    target_all_patients: Optional[bool] = None
    patient_ids: Optional[List[int]] = None  # 전달 시 assignments 덮어쓰기


class CommonQuestionResponse(BaseModel):
    id: int
    question_text: str
    question_type: str
    options: Optional[str] = None          # JSON 문자열 그대로 반환 (프론트에서 파싱)
    is_active: bool
    target_all_patients: bool = True
    assigned_patient_ids: List[int] = []   # target_all_patients=False 일 때 대상 환자 ID 목록
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
