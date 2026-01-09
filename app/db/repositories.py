"""Repository layer for database operations."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Session, Message, Reflection,
    PhaseEnum, SessionStatusEnum, OutcomeEnum, RoleEnum
)


class SessionRepository:
    """Repository for Session CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        topic: Optional[str] = None,
        max_turns: int = 12
    ) -> Session:
        """Create a new coaching session."""
        session = Session(
            topic=topic,
            max_turns=max_turns,
            current_phase=PhaseEnum.FRAMING,
            turn_count=0,
            status=SessionStatusEnum.ACTIVE
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_by_id(
        self,
        session_id: str,
        include_messages: bool = False,
        include_reflection: bool = False
    ) -> Optional[Session]:
        """Get session by ID with optional relationships."""
        query = select(Session).where(Session.id == session_id)

        if include_messages:
            query = query.options(selectinload(Session.messages))
        if include_reflection:
            query = query.options(selectinload(Session.reflection))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_phase(
        self,
        session_id: str,
        phase: PhaseEnum
    ) -> Optional[Session]:
        """Update session phase."""
        session = await self.get_by_id(session_id)
        if session:
            session.current_phase = phase
            await self.db.flush()
        return session

    async def increment_turn_count(
        self,
        session_id: str
    ) -> Optional[Session]:
        """Increment turn count by 1."""
        session = await self.get_by_id(session_id)
        if session:
            session.turn_count += 1
            await self.db.flush()
        return session

    async def end_session(
        self,
        session_id: str,
        status: SessionStatusEnum = SessionStatusEnum.COMPLETED
    ) -> Optional[Session]:
        """Mark session as ended."""
        session = await self.get_by_id(session_id)
        if session:
            session.status = status
            session.ended_at = datetime.utcnow()
            await self.db.flush()
        return session

    async def update_session_state(
        self,
        session_id: str,
        phase: Optional[PhaseEnum] = None,
        observations: Optional[str] = None,
        commitment: Optional[str] = None,
        key_insight: Optional[str] = None
    ) -> Optional[Session]:
        """
        Update accumulated state for a session.

        Only non-None values will be updated. This allows partial updates.

        Args:
            session_id: Session ID
            phase: New phase (if transitioning)
            observations: Accumulated observations text
            commitment: Identified commitment
            key_insight: Key insight from the session

        Returns:
            Updated session or None if not found
        """
        session = await self.get_by_id(session_id)
        if session:
            if phase is not None:
                session.current_phase = phase
            if observations is not None:
                session.observations = observations
            if commitment is not None:
                session.commitment = commitment
            if key_insight is not None:
                session.key_insight = key_insight
            await self.db.flush()
        return session


class MessageRepository:
    """Repository for Message operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_message(
        self,
        session_id: str,
        role: RoleEnum,
        content: str,
        phase: PhaseEnum,
        turn_number: int
    ) -> Message:
        """Add a new message to a session."""
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            phase=phase,
            turn_number=turn_number
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get_session_messages(
        self,
        session_id: str
    ) -> List[Message]:
        """Get all messages for a session, ordered by turn number."""
        query = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.turn_number, Message.created_at)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_recent_messages(
        self,
        session_id: str,
        limit: int = 6
    ) -> List[Message]:
        """Get most recent messages for a session."""
        query = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.turn_number.desc(), Message.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        messages = list(result.scalars().all())
        # Reverse to get chronological order
        return messages[::-1]


class ReflectionRepository:
    """Repository for Reflection operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        session_id: str,
        observations: str,
        outcome: OutcomeEnum,
        insights: str,
        commitment: Optional[str] = None,
        suggested_followup: Optional[str] = None
    ) -> Reflection:
        """Create a reflection for a session."""
        reflection = Reflection(
            session_id=session_id,
            observations=observations,
            outcome=outcome,
            insights=insights,
            commitment=commitment,
            suggested_followup=suggested_followup
        )
        self.db.add(reflection)
        await self.db.flush()
        await self.db.refresh(reflection)
        return reflection

    async def get_by_session_id(
        self,
        session_id: str
    ) -> Optional[Reflection]:
        """Get reflection for a session."""
        query = select(Reflection).where(Reflection.session_id == session_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
