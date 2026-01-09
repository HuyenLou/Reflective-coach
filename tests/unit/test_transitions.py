"""Unit tests for phase transition logic."""

import pytest
from app.core.transitions import (
    calculate_phase_budgets,
    check_phase_transition,
    should_force_synthesis
)
from app.db.models import PhaseEnum


class TestCalculatePhaseBudgets:
    """Tests for budget calculation."""

    def test_default_12_turns(self):
        """Test budget calculation for 12 turns."""
        budgets = calculate_phase_budgets(12)

        assert budgets["framing_budget"] == 2
        assert budgets["synthesis_budget"] == 3
        # Remaining 7 turns split between exploration and challenge
        assert budgets["exploration_budget"] + budgets["challenge_budget"] == 7
        # Total must not exceed max_turns
        total = sum(budgets.values())
        assert total <= 12

    def test_minimum_4_turns(self):
        """Test budget calculation for minimum 4 turns."""
        budgets = calculate_phase_budgets(4)

        # Each phase gets at least 1 turn
        assert budgets["framing_budget"] >= 1
        assert budgets["synthesis_budget"] >= 1
        assert budgets["exploration_budget"] >= 1
        assert budgets["challenge_budget"] >= 1
        # Critical: total must not exceed max_turns
        total = sum(budgets.values())
        assert total <= 4

    def test_very_short_3_turns(self):
        """Test budget for very short session (3 turns)."""
        budgets = calculate_phase_budgets(3)

        # Priority phases get 1 each, synthesis gets 0
        assert budgets["framing_budget"] == 1
        assert budgets["exploration_budget"] == 1
        assert budgets["challenge_budget"] == 1
        assert budgets["synthesis_budget"] == 0
        # Total must not exceed max_turns
        total = sum(budgets.values())
        assert total <= 3

    def test_very_short_2_turns(self):
        """Test budget for very short session (2 turns)."""
        budgets = calculate_phase_budgets(2)

        assert budgets["framing_budget"] == 1
        assert budgets["exploration_budget"] == 1
        assert budgets["challenge_budget"] == 0
        assert budgets["synthesis_budget"] == 0
        total = sum(budgets.values())
        assert total <= 2

    def test_very_short_1_turn(self):
        """Test budget for minimum session (1 turn)."""
        budgets = calculate_phase_budgets(1)

        assert budgets["framing_budget"] == 1
        assert budgets["exploration_budget"] == 0
        assert budgets["challenge_budget"] == 0
        assert budgets["synthesis_budget"] == 0
        total = sum(budgets.values())
        assert total <= 1

    def test_6_turns(self):
        """Test budget for 6-turn session."""
        budgets = calculate_phase_budgets(6)

        # All phases get budget
        assert budgets["framing_budget"] >= 1
        assert budgets["exploration_budget"] >= 1
        assert budgets["challenge_budget"] >= 1
        assert budgets["synthesis_budget"] >= 1
        # Total must not exceed max_turns
        total = sum(budgets.values())
        assert total <= 6

    def test_large_20_turns(self):
        """Test budget calculation for 20 turns."""
        budgets = calculate_phase_budgets(20)

        assert budgets["framing_budget"] == 2
        assert budgets["synthesis_budget"] == 3
        # More budget for variable phases
        assert budgets["exploration_budget"] >= 4
        assert budgets["challenge_budget"] >= 4
        # Total must not exceed max_turns
        total = sum(budgets.values())
        assert total <= 20

    def test_budget_never_exceeds_max_turns(self):
        """Test that budget allocation never exceeds max_turns for any value."""
        for max_turns in range(1, 25):
            budgets = calculate_phase_budgets(max_turns)
            total = sum(budgets.values())
            assert total <= max_turns, f"Budget {total} exceeds max_turns {max_turns}"


class TestCheckPhaseTransition:
    """Tests for phase transition checks."""

    def test_framing_to_exploration(self):
        """Test transition from framing to exploration."""
        decision = check_phase_transition(
            current_phase=PhaseEnum.FRAMING,
            turn_count=2,
            max_turns=12,
            phase_turns=2,
            has_concrete_example=True
        )

        assert decision.should_transition
        assert decision.next_phase == PhaseEnum.EXPLORATION

    def test_exploration_to_challenge_with_resistance(self):
        """Test transition from exploration to challenge when resistance surfaced."""
        decision = check_phase_transition(
            current_phase=PhaseEnum.EXPLORATION,
            turn_count=6,
            max_turns=12,
            phase_turns=4,
            has_resistance_surfaced=True
        )

        assert decision.should_transition
        assert decision.next_phase == PhaseEnum.CHALLENGE

    def test_challenge_to_synthesis_with_commitment(self):
        """Test transition from challenge to synthesis when commitment made."""
        decision = check_phase_transition(
            current_phase=PhaseEnum.CHALLENGE,
            turn_count=9,
            max_turns=12,
            phase_turns=3,
            has_commitment=True
        )

        assert decision.should_transition
        assert decision.next_phase == PhaseEnum.SYNTHESIS

    def test_user_requested_end(self):
        """Test that user can request early end."""
        decision = check_phase_transition(
            current_phase=PhaseEnum.EXPLORATION,
            turn_count=3,
            max_turns=12,
            phase_turns=1,
            user_requested_end=True
        )

        assert decision.should_transition
        assert decision.next_phase == PhaseEnum.SYNTHESIS

    def test_no_transition_when_not_ready(self):
        """Test that no transition happens when criteria not met."""
        decision = check_phase_transition(
            current_phase=PhaseEnum.EXPLORATION,
            turn_count=3,
            max_turns=12,
            phase_turns=1,
            has_resistance_surfaced=False
        )

        assert not decision.should_transition


class TestShouldForceSynthesis:
    """Tests for force synthesis logic."""

    def test_force_at_turn_10_of_12(self):
        """Test that synthesis is forced near end of session."""
        assert should_force_synthesis(10, 12)

    def test_no_force_at_turn_5_of_12(self):
        """Test that synthesis is not forced early in session."""
        assert not should_force_synthesis(5, 12)

    def test_force_at_turn_8_of_10(self):
        """Test force synthesis for shorter sessions."""
        assert should_force_synthesis(8, 10)
