"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from app.db.models import PhaseEnum, SessionStatusEnum, OutcomeEnum


# =============================================================================
# Request Schemas
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new coaching session."""
    topic: Optional[str] = Field(
        default=None,
        description="Optional topic or goal for the coaching session"
    )
    max_turns: int = Field(
        default=12,
        ge=4,
        le=20,
        description="Maximum number of turns for this session (4-20)"
    )


class SendMessageRequest(BaseModel):
    """Request to send a message in a session."""
    content: str = Field(
        ...,
        min_length=1,
        description="The user's message content"
    )


# =============================================================================
# Response Schemas
# =============================================================================

class SessionResponse(BaseModel):
    """Response when creating or getting a session."""
    session_id: str
    phase: PhaseEnum
    max_turns: int
    turn_count: int
    turns_remaining: int
    status: SessionStatusEnum
    content: str = Field(description="Coach's message (unified key)")

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """Response after sending a message."""
    content: str = Field(description="Coach's response message")
    phase: PhaseEnum
    turn_count: int
    turns_remaining: int

    model_config = ConfigDict(from_attributes=True)


class ReflectionResponse(BaseModel):
    """Post-session reflection output."""
    key_observations: str = Field(
        description="Free-form narrative of observations"
    )
    outcome_classification: OutcomeEnum
    insights_summary: str
    commitment: Optional[str] = None
    suggested_followup: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SessionEndResponse(BaseModel):
    """Response when ending a session."""
    session_id: str
    status: SessionStatusEnum
    reflection: ReflectionResponse

    model_config = ConfigDict(from_attributes=True)


class MessageHistoryItem(BaseModel):
    """Single message in conversation history."""
    role: str
    content: str
    phase: PhaseEnum
    turn_number: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionDetailResponse(BaseModel):
    """Detailed session information with message history."""
    session_id: str
    topic: Optional[str]
    phase: PhaseEnum
    turn_count: int
    max_turns: int
    turns_remaining: int
    status: SessionStatusEnum
    created_at: datetime
    ended_at: Optional[datetime]
    messages: List[MessageHistoryItem]
    reflection: Optional[ReflectionResponse] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Error Schemas
# =============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None
