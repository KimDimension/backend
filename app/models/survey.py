import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QuestionType(str, enum.Enum):
    common = "common"
    ai     = "ai"


class SurveyChoice(str, enum.Enum):
    yes = "yes"
    no  = "no"


class SurveyResponse(Base):
    """환자의 설문 응답 (공통 질문 + AI 맞춤 질문)"""
    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("daily_records.id"), nullable=False, index=True
    )
    patient_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )  # common_questions.id 또는 ai_questions.id
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type_enum"), nullable=False
    )
    choice: Mapped[Optional[SurveyChoice]] = mapped_column(
        Enum(SurveyChoice, name="survey_choice_enum"), nullable=True
    )
    text_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RejectedQPattern(Base):
    """거절된 AI 질문 패턴 (중복 질문 방지)"""
    __tablename__ = "rejected_q_patterns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    patient_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )  # NULL = 전체 환자에게 거절
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    rejected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
