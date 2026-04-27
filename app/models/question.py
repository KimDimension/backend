import enum
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AIQuestionStatus(str, enum.Enum):
    pending              = "pending"
    approved             = "approved"
    rejected_for_patient = "rejected_for_patient"
    rejected_global      = "rejected_global"


class AIQuestionType(str, enum.Enum):
    yes_no        = "yes_no"
    single_select = "single_select"
    multi_select  = "multi_select"
    short_text    = "short_text"


class CommonQuestion(Base):
    __tablename__ = "common_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[AIQuestionType] = mapped_column(
        Enum(AIQuestionType, name="ai_question_type_enum", create_type=False),
        default=AIQuestionType.yes_no,
        nullable=False,
    )
    options: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # TRUE: 담당 환자 전원에게 노출 / FALSE: assignments 테이블에 명시된 환자만
    target_all_patients: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true"
    )

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

    patient_assignments: Mapped[List["QuestionPatientAssignment"]] = relationship(
        "QuestionPatientAssignment",
        back_populates="question",
        cascade="all, delete-orphan",
        lazy="select",
    )


class QuestionPatientAssignment(Base):
    """공통 질문 ↔ 특정 환자 연결 (target_all_patients=False 일 때 사용)"""
    __tablename__ = "question_patient_assignments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("common_questions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    patient_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    question: Mapped["CommonQuestion"] = relationship(
        "CommonQuestion", back_populates="patient_assignments"
    )


class AIQuestion(Base):
    __tablename__ = "ai_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("daily_records.id"), nullable=False, index=True
    )
    patient_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    question_type: Mapped[AIQuestionType] = mapped_column(
        Enum(AIQuestionType, name="ai_question_type_enum", create_type=False),
        default=AIQuestionType.yes_no,
        nullable=False,
    )
    options: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
