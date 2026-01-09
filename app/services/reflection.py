"""Reflection generation service for post-session analysis."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OutcomeEnum
from app.db.repositories import SessionRepository, MessageRepository, ReflectionRepository
from app.api.schemas import ReflectionResponse
from app.core.prompts import REFLECTION_GENERATION_PROMPT, format_conversation_history
from app.core.llm import generate_reflection


class ReflectionService:
    """Service for generating post-session reflections."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.message_repo = MessageRepository(db)
        self.reflection_repo = ReflectionRepository(db)

    async def generate_reflection(self, session_id: str) -> ReflectionResponse:
        """
        Generate a reflection for a completed session.

        Args:
            session_id: Session ID

        Returns:
            ReflectionResponse with analysis
        """
        # Get session
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Check if reflection already exists
        existing = await self.reflection_repo.get_by_session_id(session_id)
        if existing:
            return ReflectionResponse(
                key_observations=existing.observations,
                outcome_classification=existing.outcome,
                insights_summary=existing.insights,
                commitment=existing.commitment,
                suggested_followup=existing.suggested_followup
            )

        # Get full conversation history
        messages = await self.message_repo.get_session_messages(session_id)

        # Format conversation for reflection prompt
        message_dicts = [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]
        conversation_text = format_conversation_history(message_dicts)

        # Build reflection prompt
        reflection_prompt = REFLECTION_GENERATION_PROMPT.format(
            full_conversation=conversation_text
        )

        # Generate reflection via LLM
        reflection_data = await generate_reflection(reflection_prompt)

        # Parse outcome classification
        outcome_str = reflection_data.get("outcome_classification", "partial_progress")
        try:
            outcome = OutcomeEnum(outcome_str)
        except ValueError:
            outcome = OutcomeEnum.PARTIAL_PROGRESS

        # Extract fields with defaults
        key_observations = reflection_data.get(
            "key_observations",
            "Unable to generate observations. Please review the conversation manually."
        )
        insights_summary = reflection_data.get(
            "insights_summary",
            "Session completed."
        )
        commitment = reflection_data.get("commitment")
        suggested_followup = reflection_data.get("suggested_followup")

        # Handle null strings
        if commitment and commitment.lower() in ["null", "none", ""]:
            commitment = None
        if suggested_followup and suggested_followup.lower() in ["null", "none", ""]:
            suggested_followup = None

        # Save reflection to database
        reflection = await self.reflection_repo.create(
            session_id=session_id,
            observations=key_observations,
            outcome=outcome,
            insights=insights_summary,
            commitment=commitment,
            suggested_followup=suggested_followup
        )

        return ReflectionResponse(
            key_observations=reflection.observations,
            outcome_classification=reflection.outcome,
            insights_summary=reflection.insights,
            commitment=reflection.commitment,
            suggested_followup=reflection.suggested_followup
        )
