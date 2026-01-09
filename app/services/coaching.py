"""Main coaching service orchestrating the agent and database."""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PhaseEnum, SessionStatusEnum, RoleEnum
from app.db.repositories import SessionRepository, MessageRepository, ReflectionRepository
from app.api.schemas import SessionResponse, MessageResponse, SessionEndResponse, ReflectionResponse
from app.core.agent import CoachingState, create_initial_state, process_turn
from app.core.prompts import SYSTEM_PROMPT, build_phase_prompt
from app.core.llm import generate_coach_response
from app.services.reflection import ReflectionService


class CoachingService:
    """Service for managing coaching sessions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.message_repo = MessageRepository(db)
        self.reflection_repo = ReflectionRepository(db)
        self.reflection_service = ReflectionService(db)

    async def start_session(
        self,
        topic: Optional[str] = None,
        max_turns: int = 12
    ) -> SessionResponse:
        """
        Start a new coaching session.

        Args:
            topic: Optional topic for the session
            max_turns: Maximum turns for the session

        Returns:
            SessionResponse with initial coach message
        """
        # Create session in database
        session = await self.session_repo.create(
            topic=topic,
            max_turns=max_turns
        )

        # If topic provided, save it as the initial user message
        # This preserves context in conversation history for later turns
        initial_messages = []
        if topic:
            await self.message_repo.add_message(
                session_id=session.id,
                role=RoleEnum.USER,
                content=topic,
                phase=PhaseEnum.FRAMING,
                turn_number=0
            )
            initial_messages = [{"role": "user", "content": topic}]

        # Generate initial coach message (with topic in prompt context)
        initial_prompt = build_phase_prompt(
            phase=PhaseEnum.FRAMING,
            max_turns=max_turns,
            turn_count=0,
            messages=initial_messages,
            user_input=topic or ""
        )

        initial_response = await generate_coach_response(
            SYSTEM_PROMPT,
            initial_prompt
        )

        # Save coach response
        await self.message_repo.add_message(
            session_id=session.id,
            role=RoleEnum.COACH,
            content=initial_response,
            phase=PhaseEnum.FRAMING,
            turn_number=0
        )

        return SessionResponse(
            session_id=session.id,
            phase=session.current_phase,
            max_turns=session.max_turns,
            turn_count=0,
            turns_remaining=session.max_turns,
            status=session.status,
            content=initial_response
        )

    async def process_message(
        self,
        session_id: str,
        user_message: str
    ) -> MessageResponse:
        """
        Process a user message and generate coach response.

        Args:
            session_id: Session ID
            user_message: User's message

        Returns:
            MessageResponse with coach's response
        """
        # Get session
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Get message history
        messages = await self.message_repo.get_session_messages(session_id)

        # Convert to dict format for agent
        message_history = [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]

        # Get phase-specific turn counts
        phase_turns = {
            PhaseEnum.FRAMING: 0,
            PhaseEnum.EXPLORATION: 0,
            PhaseEnum.CHALLENGE: 0,
            PhaseEnum.SYNTHESIS: 0
        }
        for msg in messages:
            if msg.role == RoleEnum.COACH:
                phase_turns[msg.phase] = phase_turns.get(msg.phase, 0) + 1

        # Create state for agent - load persisted observations from session
        state = CoachingState(
            session_id=session_id,
            phase=session.current_phase,
            turn_count=session.turn_count,
            max_turns=session.max_turns,
            framing_turns=phase_turns[PhaseEnum.FRAMING],
            exploration_turns=phase_turns[PhaseEnum.EXPLORATION],
            challenge_turns=phase_turns[PhaseEnum.CHALLENGE],
            synthesis_turns=phase_turns[PhaseEnum.SYNTHESIS],
            messages=message_history,
            current_input=user_message,
            coach_response="",
            observations=session.observations or "",
            commitment=session.commitment or "",
            key_insight=session.key_insight or "",
            should_end=False
        )

        # Process turn through agent
        result_state = await process_turn(state)

        # Save user message
        new_turn = session.turn_count + 1
        await self.message_repo.add_message(
            session_id=session_id,
            role=RoleEnum.USER,
            content=user_message,
            phase=session.current_phase,
            turn_number=new_turn
        )

        # Save coach response
        await self.message_repo.add_message(
            session_id=session_id,
            role=RoleEnum.COACH,
            content=result_state["coach_response"],
            phase=result_state["phase"],
            turn_number=new_turn
        )

        # Update session turn count and accumulated state
        await self.session_repo.increment_turn_count(session_id)

        # Persist accumulated state (observations, commitment, key_insight, and phase)
        await self.session_repo.update_session_state(
            session_id=session_id,
            phase=result_state["phase"] if result_state["phase"] != session.current_phase else None,
            observations=result_state.get("observations") or None,
            commitment=result_state.get("commitment") or None,
            key_insight=result_state.get("key_insight") or None
        )

        return MessageResponse(
            content=result_state["coach_response"],
            phase=result_state["phase"],
            turn_count=new_turn,
            turns_remaining=session.max_turns - new_turn
        )

    async def end_session(self, session_id: str) -> SessionEndResponse:
        """
        End a session and generate reflection.

        Args:
            session_id: Session ID

        Returns:
            SessionEndResponse with reflection
        """
        # Get session
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Generate reflection
        reflection = await self.reflection_service.generate_reflection(session_id)

        # Mark session as completed
        await self.session_repo.end_session(session_id, SessionStatusEnum.COMPLETED)

        return SessionEndResponse(
            session_id=session_id,
            status=SessionStatusEnum.COMPLETED,
            reflection=reflection
        )
