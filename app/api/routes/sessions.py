"""API routes for coaching sessions."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories import SessionRepository, MessageRepository, ReflectionRepository
from app.db.models import SessionStatusEnum, RoleEnum
from app.api.schemas import (
    CreateSessionRequest,
    SendMessageRequest,
    SessionResponse,
    MessageResponse,
    SessionEndResponse,
    SessionDetailResponse,
    ReflectionResponse,
    MessageHistoryItem,
    ErrorResponse
)
from app.services.coaching import CoachingService

router = APIRouter()


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Session created successfully"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    }
)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new coaching session.

    - **topic**: Optional topic or goal for the session
    - **max_turns**: Maximum turns for the session (4-20, default 12)
    """
    coaching_service = CoachingService(db)
    return await coaching_service.start_session(
        topic=request.topic,
        max_turns=request.max_turns
    )


@router.post(
    "/{session_id}/messages",
    response_model=MessageResponse,
    responses={
        200: {"description": "Message processed successfully"},
        400: {"model": ErrorResponse, "description": "Session already ended or invalid state"},
        404: {"model": ErrorResponse, "description": "Session not found"}
    }
)
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message in an active coaching session.

    The coach will respond based on the current phase and conversation history.
    """
    coaching_service = CoachingService(db)

    # Check session exists
    session_repo = SessionRepository(db)
    session = await session_repo.get_by_id(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    if session.status != SessionStatusEnum.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is {session.status.value}, cannot send messages"
        )

    return await coaching_service.process_message(
        session_id=session_id,
        user_message=request.content
    )


@router.post(
    "/{session_id}/end",
    response_model=SessionEndResponse,
    responses={
        200: {"description": "Session ended and reflection generated"},
        400: {"model": ErrorResponse, "description": "Session already ended"},
        404: {"model": ErrorResponse, "description": "Session not found"}
    }
)
async def end_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    End a coaching session and generate a reflection.

    This will analyze the full conversation and produce:
    - Key observations (free-form narrative)
    - Outcome classification
    - Insights summary
    - Commitment (if any was made)
    - Suggested follow-up
    """
    coaching_service = CoachingService(db)

    # Check session exists
    session_repo = SessionRepository(db)
    session = await session_repo.get_by_id(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    if session.status != SessionStatusEnum.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is already {session.status.value}"
        )

    return await coaching_service.end_session(session_id)


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    responses={
        200: {"description": "Session details retrieved"},
        404: {"model": ErrorResponse, "description": "Session not found"}
    }
)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a coaching session.

    Includes full message history and reflection (if session is completed).
    """
    session_repo = SessionRepository(db)
    session = await session_repo.get_by_id(
        session_id,
        include_messages=True,
        include_reflection=True
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    # Build response
    messages = [
        MessageHistoryItem(
            role=msg.role.value,
            content=msg.content,
            phase=msg.phase,
            turn_number=msg.turn_number,
            created_at=msg.created_at
        )
        for msg in session.messages
    ]

    reflection = None
    if session.reflection:
        reflection = ReflectionResponse(
            key_observations=session.reflection.observations,
            outcome_classification=session.reflection.outcome,
            insights_summary=session.reflection.insights,
            commitment=session.reflection.commitment,
            suggested_followup=session.reflection.suggested_followup
        )

    return SessionDetailResponse(
        session_id=session.id,
        topic=session.topic,
        phase=session.current_phase,
        turn_count=session.turn_count,
        max_turns=session.max_turns,
        turns_remaining=session.max_turns - session.turn_count,
        status=session.status,
        created_at=session.created_at,
        ended_at=session.ended_at,
        messages=messages,
        reflection=reflection
    )


@router.get(
    "/{session_id}/reflection",
    response_model=ReflectionResponse,
    responses={
        200: {"description": "Reflection retrieved"},
        400: {"model": ErrorResponse, "description": "Session not completed"},
        404: {"model": ErrorResponse, "description": "Session or reflection not found"}
    }
)
async def get_reflection(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the reflection for a completed coaching session.
    """
    session_repo = SessionRepository(db)
    session = await session_repo.get_by_id(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    if session.status != SessionStatusEnum.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not completed. End the session first to generate a reflection."
        )

    reflection_repo = ReflectionRepository(db)
    reflection = await reflection_repo.get_by_session_id(session_id)

    if not reflection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reflection not found for this session"
        )

    return ReflectionResponse(
        key_observations=reflection.observations,
        outcome_classification=reflection.outcome,
        insights_summary=reflection.insights,
        commitment=reflection.commitment,
        suggested_followup=reflection.suggested_followup
    )
