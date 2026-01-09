"""LangGraph-based coaching agent with state management."""

from typing import TypedDict, Literal, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from app.db.models import PhaseEnum
from app.core.prompts import (
    SYSTEM_PROMPT,
    PHASE_TRANSITION_PROMPT,
    build_phase_prompt,
    format_conversation_history
)
from app.core.transitions import (
    calculate_phase_budgets,
    check_phase_transition,
    should_force_synthesis
)
from app.core.llm import (
    generate_coach_response,
    check_transition,
    extract_observations
)


# =============================================================================
# State Definition
# =============================================================================

class CoachingState(TypedDict):
    """State for the coaching conversation."""
    # Session identifiers
    session_id: str

    # Phase tracking
    phase: PhaseEnum
    turn_count: int
    max_turns: int

    # Phase-specific turn counts
    framing_turns: int
    exploration_turns: int
    challenge_turns: int
    synthesis_turns: int

    # Conversation
    messages: List[Dict[str, Any]]
    current_input: str
    coach_response: str

    # Observations and tracking
    observations: str
    commitment: str
    key_insight: str

    # Control flags
    should_end: bool


def create_initial_state(
    session_id: str,
    max_turns: int = 12,
    topic: Optional[str] = None
) -> CoachingState:
    """Create initial state for a new coaching session."""
    return CoachingState(
        session_id=session_id,
        phase=PhaseEnum.FRAMING,
        turn_count=0,
        max_turns=max_turns,
        framing_turns=0,
        exploration_turns=0,
        challenge_turns=0,
        synthesis_turns=0,
        messages=[],
        current_input=topic or "",
        coach_response="",
        observations="",
        commitment="",
        key_insight="",
        should_end=False
    )


# =============================================================================
# Graph Nodes
# =============================================================================

async def coach_respond_node(state: CoachingState) -> CoachingState:
    """Generate coach response based on current phase."""
    # Build the phase-specific prompt
    phase_prompt = build_phase_prompt(
        phase=state["phase"],
        max_turns=state["max_turns"],
        turn_count=state["turn_count"],
        messages=state["messages"],
        user_input=state["current_input"],
        exploration_turns=state["exploration_turns"],
        challenge_turns=state["challenge_turns"],
        observations=state["observations"],
        commitment=state["commitment"],
        key_insight=state["key_insight"]
    )

    # Generate response
    response = await generate_coach_response(SYSTEM_PROMPT, phase_prompt)

    return {**state, "coach_response": response}


async def update_observations_node(state: CoachingState) -> CoachingState:
    """Extract observations, and commitment/key_insight during CHALLENGE phase."""
    # Only extract during exploration and challenge phases
    if state["phase"] not in [PhaseEnum.EXPLORATION, PhaseEnum.CHALLENGE]:
        return state

    # Get recent messages for analysis
    recent_messages = state["messages"][-4:] if len(state["messages"]) > 4 else state["messages"]

    # Add current exchange
    recent_text = format_conversation_history(recent_messages)
    recent_text += f"\n\nUSER: {state['current_input']}\n\nCOACH: {state['coach_response']}"

    # Only extract commitment/key_insight during CHALLENGE phase (cost optimization)
    extract_commitment = state["phase"] == PhaseEnum.CHALLENGE

    # Extract insights
    insights = await extract_observations(
        recent_text,
        state["observations"],
        extract_commitment=extract_commitment,
        existing_commitment=state["commitment"],
        existing_key_insight=state["key_insight"]
    )

    return {
        **state,
        "observations": insights["observations"],
        "commitment": insights["commitment"],
        "key_insight": insights["key_insight"]
    }


async def check_transition_node(state: CoachingState) -> CoachingState:
    """Check if we should transition to the next phase.

    Uses a hybrid approach:
    1. Heuristic check first (fast, no LLM cost)
    2. If heuristic suggests transition, confirm with LLM for quality
    3. Fallback to heuristic if LLM fails
    """
    # Get current phase turn count
    phase_turns_map = {
        PhaseEnum.FRAMING: state["framing_turns"],
        PhaseEnum.EXPLORATION: state["exploration_turns"],
        PhaseEnum.CHALLENGE: state["challenge_turns"],
        PhaseEnum.SYNTHESIS: state["synthesis_turns"]
    }
    phase_turns = phase_turns_map.get(state["phase"], 0)

    # Force synthesis if running out of turns (no LLM check needed)
    if should_force_synthesis(state["turn_count"], state["max_turns"]):
        if state["phase"] != PhaseEnum.SYNTHESIS:
            return {**state, "phase": PhaseEnum.SYNTHESIS}

    # Quick heuristic check first
    decision = check_phase_transition(
        current_phase=state["phase"],
        turn_count=state["turn_count"],
        max_turns=state["max_turns"],
        phase_turns=phase_turns,
        has_concrete_example=len(state["messages"]) >= 2,
        has_resistance_surfaced=len(state["observations"]) > 20,
        has_commitment=len(state["commitment"]) > 0
    )

    # If heuristic doesn't want to transition, don't call LLM
    if not decision.should_transition:
        return state

    # Heuristic wants to transition - confirm with LLM for better quality
    if decision.next_phase is not None:
        try:
            # Build transition check prompt
            budgets = calculate_phase_budgets(state["max_turns"])
            recent_messages = state["messages"][-6:] if len(state["messages"]) > 6 else state["messages"]

            transition_prompt = PHASE_TRANSITION_PROMPT.format(
                current_phase=state["phase"].value,
                max_turns=state["max_turns"],
                turn_count=state["turn_count"],
                turns_remaining=state["max_turns"] - state["turn_count"],
                phase_turns=phase_turns,
                exploration_budget=budgets["exploration_budget"],
                challenge_budget=budgets["challenge_budget"],
                recent_messages=format_conversation_history(recent_messages),
                observations=state["observations"] or "(None yet)"
            )

            # Get LLM decision
            llm_decision = await check_transition(transition_prompt)

            # Use LLM decision if valid
            if llm_decision.get("should_transition", False):
                next_phase_str = llm_decision.get("next_phase", "")
                try:
                    next_phase = PhaseEnum(next_phase_str)
                    return {**state, "phase": next_phase}
                except ValueError:
                    # Invalid phase from LLM, fall back to heuristic
                    pass
            else:
                # LLM says don't transition yet - trust it
                return state

        except Exception:
            # LLM failed - fall back to heuristic decision
            pass

        # Fallback: use heuristic decision
        return {**state, "phase": decision.next_phase}

    # Session complete (next_phase is None)
    return {**state, "should_end": True}


def update_state_node(state: CoachingState) -> CoachingState:
    """Update state after processing a turn."""
    # Add messages to history
    new_messages = state["messages"].copy()
    new_messages.append({
        "role": "user",
        "content": state["current_input"]
    })
    new_messages.append({
        "role": "coach",
        "content": state["coach_response"]
    })

    # Increment turn counts
    turn_count = state["turn_count"] + 1

    # Increment phase-specific turn count
    framing_turns = state["framing_turns"]
    exploration_turns = state["exploration_turns"]
    challenge_turns = state["challenge_turns"]
    synthesis_turns = state["synthesis_turns"]

    if state["phase"] == PhaseEnum.FRAMING:
        framing_turns += 1
    elif state["phase"] == PhaseEnum.EXPLORATION:
        exploration_turns += 1
    elif state["phase"] == PhaseEnum.CHALLENGE:
        challenge_turns += 1
    elif state["phase"] == PhaseEnum.SYNTHESIS:
        synthesis_turns += 1

    return {
        **state,
        "messages": new_messages,
        "turn_count": turn_count,
        "framing_turns": framing_turns,
        "exploration_turns": exploration_turns,
        "challenge_turns": challenge_turns,
        "synthesis_turns": synthesis_turns,
        "current_input": ""  # Clear current input
    }


# =============================================================================
# Conditional Edges
# =============================================================================

def should_continue(state: CoachingState) -> Literal["continue", "end"]:
    """Determine if the conversation should continue."""
    if state["should_end"]:
        return "end"
    if state["turn_count"] >= state["max_turns"]:
        return "end"
    return "continue"


# =============================================================================
# Graph Construction
# =============================================================================

def create_coaching_graph() -> StateGraph:
    """Create the LangGraph for coaching conversations."""
    # Create the graph
    graph = StateGraph(CoachingState)

    # Add nodes
    graph.add_node("coach_respond", coach_respond_node)
    graph.add_node("update_observations", update_observations_node)
    graph.add_node("check_transition", check_transition_node)
    graph.add_node("update_state", update_state_node)

    # Set entry point
    graph.set_entry_point("coach_respond")

    # Add edges
    graph.add_edge("coach_respond", "update_observations")
    graph.add_edge("update_observations", "check_transition")
    graph.add_edge("check_transition", "update_state")

    # Conditional edge from update_state
    graph.add_conditional_edges(
        "update_state",
        should_continue,
        {
            "continue": END,  # Wait for next user input
            "end": END
        }
    )

    return graph.compile()


# Global compiled graph instance
_coaching_graph = None


def get_coaching_graph():
    """Get or create the coaching graph."""
    global _coaching_graph
    if _coaching_graph is None:
        _coaching_graph = create_coaching_graph()
    return _coaching_graph


async def process_turn(state: CoachingState) -> CoachingState:
    """Process a single turn of the coaching conversation."""
    graph = get_coaching_graph()
    result = await graph.ainvoke(state)
    return result
