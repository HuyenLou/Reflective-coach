"""Phase transition logic and budget calculations for coaching sessions."""

from typing import Dict, Optional
from dataclasses import dataclass

from app.db.models import PhaseEnum


@dataclass
class PhaseBudget:
    """Budget allocation for each phase."""
    framing_budget: int
    exploration_budget: int
    challenge_budget: int
    synthesis_budget: int


def calculate_phase_budgets(max_turns: int) -> Dict[str, int]:
    """
    Calculate turn budgets for each phase based on max_turns.

    Phase distribution:
    - Framing: 1-2 turns (fixed)
    - Exploration: ~30-40% of remaining
    - Challenge: ~30-40% of remaining
    - Synthesis: 1-3 turns (fixed)

    IMPORTANT: Total budget must never exceed max_turns.

    Args:
        max_turns: Total turns budget for the session

    Returns:
        Dictionary with budget for each phase
    """
    # Handle extremely short sessions (< 4 turns)
    if max_turns < 4:
        # Distribute available turns across phases as evenly as possible
        # Priority: framing=1, exploration=1, challenge=1, synthesis gets remainder
        if max_turns <= 1:
            return {"framing_budget": 1, "exploration_budget": 0, "challenge_budget": 0, "synthesis_budget": 0}
        elif max_turns == 2:
            return {"framing_budget": 1, "exploration_budget": 1, "challenge_budget": 0, "synthesis_budget": 0}
        elif max_turns == 3:
            return {"framing_budget": 1, "exploration_budget": 1, "challenge_budget": 1, "synthesis_budget": 0}

    # Reserve fixed turns for framing and synthesis
    framing_budget = min(2, max_turns // 4)
    synthesis_budget = min(3, max_turns // 4)

    # Remaining turns for exploration + challenge
    variable_turns = max_turns - framing_budget - synthesis_budget

    # Split roughly equally between exploration and challenge
    # No artificial minimum that could exceed max_turns
    exploration_budget = max(1, variable_turns // 2)
    challenge_budget = max(1, variable_turns - exploration_budget)

    # Final validation: ensure total doesn't exceed max_turns
    total = framing_budget + exploration_budget + challenge_budget + synthesis_budget
    if total > max_turns:
        # Scale down variable phases proportionally
        excess = total - max_turns
        if exploration_budget > 1:
            reduce_exploration = min(excess, exploration_budget - 1)
            exploration_budget -= reduce_exploration
            excess -= reduce_exploration
        if excess > 0 and challenge_budget > 1:
            challenge_budget -= min(excess, challenge_budget - 1)

    return {
        "framing_budget": max(1, framing_budget),
        "exploration_budget": exploration_budget,
        "challenge_budget": challenge_budget,
        "synthesis_budget": max(1, synthesis_budget)
    }


@dataclass
class TransitionDecision:
    """Result of a phase transition check."""
    should_transition: bool
    next_phase: Optional[PhaseEnum]
    reasoning: str


def check_phase_transition(
    current_phase: PhaseEnum,
    turn_count: int,
    max_turns: int,
    phase_turns: int,
    has_concrete_example: bool = False,
    has_resistance_surfaced: bool = False,
    has_commitment: bool = False,
    user_requested_end: bool = False
) -> TransitionDecision:
    """
    Determine if we should transition to the next phase.

    This function provides heuristic guidance, but the LLM makes
    the final decision based on conversation quality signals.

    Args:
        current_phase: Current coaching phase
        turn_count: Total turns so far
        max_turns: Maximum turns for session
        phase_turns: Turns spent in current phase
        has_concrete_example: Whether user gave a concrete example
        has_resistance_surfaced: Whether resistance/fear has been identified
        has_commitment: Whether a commitment has been made
        user_requested_end: Whether user wants to end early

    Returns:
        TransitionDecision with recommendation
    """
    budgets = calculate_phase_budgets(max_turns)
    turns_remaining = max_turns - turn_count

    # Early exit requested
    if user_requested_end:
        return TransitionDecision(
            should_transition=True,
            next_phase=PhaseEnum.SYNTHESIS,
            reasoning="User requested to end session early"
        )

    # Phase-specific logic
    if current_phase == PhaseEnum.FRAMING:
        # Framing complete after establishing context
        if phase_turns >= budgets["framing_budget"] or has_concrete_example:
            return TransitionDecision(
                should_transition=True,
                next_phase=PhaseEnum.EXPLORATION,
                reasoning="Framing complete - context established"
            )

    elif current_phase == PhaseEnum.EXPLORATION:
        # Check if we should move to challenge
        budget_used = phase_turns >= budgets["exploration_budget"]
        qualitative_ready = has_resistance_surfaced

        if budget_used or (qualitative_ready and phase_turns >= 2):
            return TransitionDecision(
                should_transition=True,
                next_phase=PhaseEnum.CHALLENGE,
                reasoning="Exploration complete - resistance identified" if qualitative_ready
                         else "Exploration budget exhausted"
            )

    elif current_phase == PhaseEnum.CHALLENGE:
        # Check if we should move to synthesis
        budget_used = phase_turns >= budgets["challenge_budget"]
        qualitative_ready = has_commitment

        if budget_used or qualitative_ready:
            return TransitionDecision(
                should_transition=True,
                next_phase=PhaseEnum.SYNTHESIS,
                reasoning="Challenge complete - commitment secured" if qualitative_ready
                         else "Challenge budget exhausted"
            )

    elif current_phase == PhaseEnum.SYNTHESIS:
        # Synthesis should wrap up quickly
        if phase_turns >= budgets["synthesis_budget"] or turns_remaining <= 0:
            return TransitionDecision(
                should_transition=True,
                next_phase=None,  # Session complete
                reasoning="Session complete"
            )

    # No transition needed
    return TransitionDecision(
        should_transition=False,
        next_phase=None,
        reasoning=f"Continuing in {current_phase.value} phase"
    )


def should_force_synthesis(turn_count: int, max_turns: int) -> bool:
    """
    Check if we should force transition to synthesis.

    This prevents sessions from running over budget.
    """
    # Reserve last 2 turns for synthesis
    return turn_count >= max_turns - 2
