import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ConversationStatus(str, enum.Enum):
    in_progress = "in_progress"  # 문진 진행 중
    completed   = "completed"    # 문진 완료
    aborted     = "aborted"      # 긴급 신호로 중단


class MessageRole(str, enum.Enum):
    ai   = "ai"    # AI 발화
    user = "user"  # 환자 발화


class Conversation(Base):
    """대화형 문진 세션 — 기록 1건당 최대 1개"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("daily_records.id"), nullable=False, unique=True, index=True
    )
    patient_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status_enum"),
        default=ConversationStatus.in_progress,
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── 관계 ───────────────────────────────────────────────────
    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )


class ConversationMessage(Base):
    """대화 메시지 한 줄 — AI 발화 / 환자 발화"""
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role_enum"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # AI 발화일 때만 — 긴급 신호 여부
    is_urgent_flag: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── 관계 ───────────────────────────────────────────────────
    conversation = relationship("Conversation", back_populates="messages")
