import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AIQuestionStatus(str, enum.Enum):
    pending              = "pending"
    approved             = "approved"
    rejected_for_patient = "rejected_for_patient"   # 이 환자만 거절
    rejected_global      = "rejected_global"         # 전체 환자 거절


class AIQuestionType(str, enum.Enum):
    yes_no        = "yes_no"         # 예/아니오 (기존 방식)
    single_select = "single_select"  # 단일 선택 (라디오)
    multi_select  = "multi_select"   # 다중 선택 (체크박스)
    short_text    = "short_text"     # 단답 텍스트 입력


class CommonQuestion(Base):
    """의사가 등록한 공통 질문"""
    __tablename__ = "common_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AIQuestion(Base):
    """AI가 특정 기록에 대해 생성한 맞춤 질문"""
    __tablename__ = "ai_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("daily_records.id"), nullable=False, index=True
    )
    patient_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)          # 생성 이유
    question_type: Mapped[AIQuestionType] = mapped_column(
        Enum(AIQuestionType, name="ai_question_type_enum"),
        default=AIQuestionType.yes_no,
        nullable=False,
    )
    options: Mapped[Optional[str]] = mapped_column(Text, nullable=True)         # JSON 배열 문자열 (선택지)
    status: Mapped[AIQuestionStatus] = mapped_column(
        Enum(AIQuestionStatus, name="ai_question_status_enum"),
        default=AIQuestionStatus.pending,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    daily_record = relationship("DailyRecord")
