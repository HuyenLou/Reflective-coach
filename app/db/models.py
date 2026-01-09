"""SQLAlchemy ORM models for coaching sessions."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class PhaseEnum(str, PyEnum):
    """Coaching session phases."""
    FRAMING = "framing"
    EXPLORATION = "exploration"
    CHALLENGE = "challenge"
    SYNTHESIS = "synthesis"


class SessionStatusEnum(str, PyEnum):
    """Session status options."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class OutcomeEnum(str, PyEnum):
    """Reflection outcome classifications."""
    BREAKTHROUGH_ACHIEVED = "breakthrough_achieved"
    PARTIAL_PROGRESS = "partial_progress"
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"


class RoleEnum(str, PyEnum):
    """Message role options."""
    USER = "user"
    COACH = "coach"


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class Session(Base):
    """Coaching session model."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid
    )
    topic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_phase: Mapped[PhaseEnum] = mapped_column(
        Enum(PhaseEnum),
        default=PhaseEnum.FRAMING
    )
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    max_turns: Mapped[int] = mapped_column(Integer, default=12)
    status: Mapped[SessionStatusEnum] = mapped_column(
        Enum(SessionStatusEnum),
        default=SessionStatusEnum.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    # Accumulated state for coaching continuity across turns
    observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    commitment: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    key_insight: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")

    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.turn_number"
    )
    reflection: Mapped[Optional["Reflection"]] = relationship(
        "Reflection",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan"
    )


class Message(Base):
    """Individual message in a coaching session."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE")
    )
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum))
    content: Mapped[str] = mapped_column(Text)
    phase: Mapped[PhaseEnum] = mapped_column(Enum(PhaseEnum))
    turn_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="messages"
    )


class Reflection(Base):
    """Post-session reflection analysis."""

    __tablename__ = "reflections"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        unique=True
    )
    observations: Mapped[str] = mapped_column(Text)  # Free-form text
    outcome: Mapped[OutcomeEnum] = mapped_column(Enum(OutcomeEnum))
    insights: Mapped[str] = mapped_column(Text)
    commitment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_followup: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="reflection"
    )
