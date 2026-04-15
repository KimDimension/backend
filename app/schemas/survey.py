from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel


class SurveyResponseItem(BaseModel):
    question_id: int
    question_type: Literal["common", "ai"]
    choice: Optional[Literal["yes", "no"]] = None
    text_answer: Optional[str] = ""


class SurveySubmitRequest(BaseModel):
    record_id: int
    responses: List[SurveyResponseItem]


class SurveySubmitResponse(BaseModel):
    success: bool
    message: str
    saved_count: int
