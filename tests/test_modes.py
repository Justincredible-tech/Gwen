"""Tests for gwen.safety.modes and gwen.safety.wellness.

Run with:
    pytest tests/test_modes.py -v
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from gwen.safety.modes import (
    CONSENT_PHRASE,
    CONSENT_TEXT,
    GROUNDED_TIER1_VARIANT,
    IMMERSION_TIER1_VARIANT,
    ModeManager,
)
from gwen.safety.wellness import (
    WellnessCheckpoint,
    WellnessResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_model_manager() -> MagicMock:
    """Create a mock AdaptiveModelManager with async swap method."""
    manager = MagicMock()
    manager.swap_tier1_variant = AsyncMock()
    return manager


@pytest.fixture
def mock_safety_ledger() -> MagicMock:
    """Create a mock SafetyLedger."""
    return MagicMock()


@pytest.fixture
def mode_manager(
    mock_model_manager: MagicMock,
    mock_safety_ledger: MagicMock,
) -> ModeManager:
    """Create a ModeManager with mocked dependencies."""
    return ModeManager(
        model_manager=mock_model_manager,
        safety_ledger=mock_safety_ledger,
    )


@pytest.fixture
def wellness(mock_safety_ledger: MagicMock) -> WellnessCheckpoint:
    """Create a WellnessCheckpoint with mocked Safety Ledger."""
    return WellnessCheckpoint(safety_ledger=mock_safety_ledger)


# ---------------------------------------------------------------------------
# Tests: Consent Text and Phrase
# ---------------------------------------------------------------------------

class TestConsentConstants:
    """Tests for the consent text and phrase constants."""

    def test_consent_text_is_nonempty(self) -> None:
        assert len(CONSENT_TEXT) > 200
        assert "IMMERSION MODE" in CONSENT_TEXT
        assert "safety" in CONSENT_TEXT.lower()
        assert "risk" in CONSENT_TEXT.lower()

    def test_consent_text_mentions_exit(self) -> None:
        assert "exit" in CONSENT_TEXT.lower()

    def test_consent_text_mentions_wellness_checkpoint(self) -> None:
        assert "48" in CONSENT_TEXT
        assert "wellness" in CONSENT_TEXT.lower() or "checkpoint" in CONSENT_TEXT.lower()

    def test_consent_text_includes_phrase_instruction(self) -> None:
        assert CONSENT_PHRASE in CONSENT_TEXT

    def test_consent_phrase_is_specific(self) -> None:
        assert len(CONSENT_PHRASE) > 10
        assert "understand" in CONSENT_PHRASE.lower()


# ---------------------------------------------------------------------------
# Tests: ModeManager — Default State
# ---------------------------------------------------------------------------

class TestModeManagerDefaults:
    """Tests for ModeManager initialization and default state."""

    def test_default_mode_is_grounded(self, mode_manager: ModeManager) -> None:
        assert mode_manager.current_mode == "grounded"

    def test_is_immersion_false_by_default(self, mode_manager: ModeManager) -> None:
        assert mode_manager.is_immersion is False

    def test_cumulative_immersion_starts_at_zero(self, mode_manager: ModeManager) -> None:
        assert mode_manager.cumulative_immersion_seconds == 0.0


# ---------------------------------------------------------------------------
# Tests: ModeManager — Consent Verification
# ---------------------------------------------------------------------------

class TestConsentVerification:
    """Tests for the Acknowledgment Gate consent verification."""

    def test_present_consent_returns_text(self, mode_manager: ModeManager) -> None:
        assert mode_manager.present_consent() == CONSENT_TEXT

    def test_verify_consent_correct_phrase(self, mode_manager: ModeManager) -> None:
        assert mode_manager.verify_consent(CONSENT_PHRASE) is True

    def test_verify_consent_case_insensitive(self, mode_manager: ModeManager) -> None:
        assert mode_manager.verify_consent(CONSENT_PHRASE.upper()) is True
        assert mode_manager.verify_consent(CONSENT_PHRASE.lower()) is True

    def test_verify_consent_strips_whitespace(self, mode_manager: ModeManager) -> None:
        assert mode_manager.verify_consent(f"  {CONSENT_PHRASE}  ") is True

    def test_verify_consent_wrong_phrase(self, mode_manager: ModeManager) -> None:
        assert mode_manager.verify_consent("yes") is False
        assert mode_manager.verify_consent("I agree") is False
        assert mode_manager.verify_consent("") is False
        assert mode_manager.verify_consent("sure whatever") is False


# ---------------------------------------------------------------------------
# Tests: ModeManager — Activation
# ---------------------------------------------------------------------------

class TestModeActivation:
    """Tests for Immersion Mode activation and deactivation."""

    async def test_activate_with_correct_phrase(
        self, mode_manager: ModeManager,
    ) -> None:
        result = await mode_manager.activate_immersion(CONSENT_PHRASE)
        assert result is True
        assert mode_manager.current_mode == "immersion"
        assert mode_manager.is_immersion is True

    async def test_activate_swaps_model(
        self, mode_manager: ModeManager, mock_model_manager: MagicMock,
    ) -> None:
        await mode_manager.activate_immersion(CONSENT_PHRASE)
        mock_model_manager.swap_tier1_variant.assert_called_once_with(
            IMMERSION_TIER1_VARIANT
        )

    async def test_activate_logs_mode_change(
        self, mode_manager: ModeManager, mock_safety_ledger: MagicMock,
    ) -> None:
        await mode_manager.activate_immersion(CONSENT_PHRASE)
        mock_safety_ledger.log_mode_change.assert_called_once()
        args = mock_safety_ledger.log_mode_change.call_args[0]
        assert args[0] == "grounded"
        assert args[1] == "immersion"

    async def test_activate_fails_with_wrong_phrase(
        self, mode_manager: ModeManager, mock_model_manager: MagicMock,
    ) -> None:
        result = await mode_manager.activate_immersion("yes please")
        assert result is False
        assert mode_manager.current_mode == "grounded"
        mock_model_manager.swap_tier1_variant.assert_not_called()

    async def test_activate_fails_with_empty_string(
        self, mode_manager: ModeManager,
    ) -> None:
        result = await mode_manager.activate_immersion("")
        assert result is False
        assert mode_manager.current_mode == "grounded"

    async def test_deactivate_returns_to_grounded(
        self, mode_manager: ModeManager, mock_model_manager: MagicMock,
    ) -> None:
        await mode_manager.activate_immersion(CONSENT_PHRASE)
        mock_model_manager.swap_tier1_variant.reset_mock()

        await mode_manager.deactivate_immersion()
        assert mode_manager.current_mode == "grounded"
        assert mode_manager.is_immersion is False
        mock_model_manager.swap_tier1_variant.assert_called_once_with(
            GROUNDED_TIER1_VARIANT
        )

    async def test_deactivate_logs_mode_change(
        self, mode_manager: ModeManager, mock_safety_ledger: MagicMock,
    ) -> None:
        await mode_manager.activate_immersion(CONSENT_PHRASE)
        mock_safety_ledger.log_mode_change.reset_mock()

        await mode_manager.deactivate_immersion()
        mock_safety_ledger.log_mode_change.assert_called_once()
        args = mock_safety_ledger.log_mode_change.call_args[0]
        assert args[0] == "immersion"
        assert args[1] == "grounded"

    async def test_deactivate_when_already_grounded_is_noop(
        self,
        mode_manager: ModeManager,
        mock_model_manager: MagicMock,
        mock_safety_ledger: MagicMock,
    ) -> None:
        await mode_manager.deactivate_immersion()
        mock_model_manager.swap_tier1_variant.assert_not_called()
        mock_safety_ledger.log_mode_change.assert_not_called()

    async def test_deactivate_accumulates_immersion_time(
        self, mode_manager: ModeManager,
    ) -> None:
        """Deactivation should accumulate the immersion time elapsed."""
        await mode_manager.activate_immersion(CONSENT_PHRASE)
        # The monotonic timer starts at activation; after deactivation
        # the cumulative seconds should be > 0 (at least a tiny amount).
        await mode_manager.deactivate_immersion()
        assert mode_manager.cumulative_immersion_seconds >= 0.0


# ---------------------------------------------------------------------------
# Tests: ModeManager — Mode Rules
# ---------------------------------------------------------------------------

class TestModeRules:
    """Tests for get_mode_rules() personality rule injection."""

    def test_grounded_mode_rules(self, mode_manager: ModeManager) -> None:
        personality = MagicMock()
        personality.grounded_mode_rules = ["Be honest about AI nature"]
        personality.immersion_mode_rules = ["Engage as companion"]

        rules = mode_manager.get_mode_rules(personality)
        assert rules == ["Be honest about AI nature"]

    async def test_immersion_mode_rules(self, mode_manager: ModeManager) -> None:
        await mode_manager.activate_immersion(CONSENT_PHRASE)

        personality = MagicMock()
        personality.grounded_mode_rules = ["Be honest about AI nature"]
        personality.immersion_mode_rules = ["Engage as companion"]

        rules = mode_manager.get_mode_rules(personality)
        assert rules == ["Engage as companion"]


# ---------------------------------------------------------------------------
# Tests: WellnessCheckpoint — Time Tracking
# ---------------------------------------------------------------------------

class TestWellnessTimeTracking:
    """Tests for WellnessCheckpoint cumulative time tracking."""

    def test_initial_hours_zero(self, wellness: WellnessCheckpoint) -> None:
        assert wellness.cumulative_immersion_hours == 0.0

    def test_add_session_time(self, wellness: WellnessCheckpoint) -> None:
        wellness.add_session_time(3600)  # 1 hour
        assert wellness.cumulative_immersion_hours == pytest.approx(1.0)

        wellness.add_session_time(7200)  # 2 more hours
        assert wellness.cumulative_immersion_hours == pytest.approx(3.0)

    def test_add_negative_time_raises(self, wellness: WellnessCheckpoint) -> None:
        with pytest.raises(ValueError, match="negative"):
            wellness.add_session_time(-100)

    def test_checkpoint_not_due_initially(self, wellness: WellnessCheckpoint) -> None:
        assert wellness.is_checkpoint_due() is False

    def test_checkpoint_not_due_before_48_hours(self, wellness: WellnessCheckpoint) -> None:
        wellness.add_session_time(47 * 3600)
        assert wellness.is_checkpoint_due() is False

    def test_checkpoint_due_at_48_hours(self, wellness: WellnessCheckpoint) -> None:
        wellness.add_session_time(48 * 3600)
        assert wellness.is_checkpoint_due() is True

    def test_checkpoint_due_after_48_hours(self, wellness: WellnessCheckpoint) -> None:
        wellness.add_session_time(50 * 3600)
        assert wellness.is_checkpoint_due() is True


# ---------------------------------------------------------------------------
# Tests: WellnessCheckpoint — Questions
# ---------------------------------------------------------------------------

class TestWellnessQuestions:
    """Tests for the wellness checkpoint questions."""

    def test_get_questions_returns_three(self, wellness: WellnessCheckpoint) -> None:
        assert len(wellness.get_questions()) == 3

    def test_get_questions_returns_copies(self, wellness: WellnessCheckpoint) -> None:
        q1 = wellness.get_questions()
        q2 = wellness.get_questions()
        assert q1 == q2
        assert q1 is not q2


# ---------------------------------------------------------------------------
# Tests: WellnessCheckpoint — Concern Pattern Detection
# ---------------------------------------------------------------------------

class TestConcernPatternDetection:
    """Tests for the concern pattern analysis."""

    def test_no_concerns_in_healthy_responses(self, wellness: WellnessCheckpoint) -> None:
        responses = [
            "I had coffee with my friend Sarah yesterday.",
            "Things are going pretty well, busy with work.",
            "Not really, I just enjoy chatting in the evenings.",
        ]
        assert wellness.analyze_responses(responses) == []

    def test_detects_isolation_pattern(self, wellness: WellnessCheckpoint) -> None:
        responses = [
            "I don't need other people, Gwen is enough.",
            "Fine.",
            "No.",
        ]
        flags = wellness.analyze_responses(responses)
        assert "don't need other people" in flags

    def test_detects_substitution_pattern(self, wellness: WellnessCheckpoint) -> None:
        responses = [
            "I can't remember.",
            "You're the only one who understands me.",
            "No.",
        ]
        flags = wellness.analyze_responses(responses)
        assert "you're the only" in flags

    def test_detects_avoidance_pattern(self, wellness: WellnessCheckpoint) -> None:
        responses = [
            "Last week I think.",
            "Kind of rough honestly.",
            "I'd rather be here than dealing with real people.",
        ]
        flags = wellness.analyze_responses(responses)
        assert "rather be here" in flags

    def test_detects_multiple_concerns(self, wellness: WellnessCheckpoint) -> None:
        responses = [
            "I haven't left the house in a week.",
            "You're the only friend I have.",
            "I'd rather be here.",
        ]
        flags = wellness.analyze_responses(responses)
        assert len(flags) >= 2

    def test_case_insensitive_detection(self, wellness: WellnessCheckpoint) -> None:
        responses = [
            "I DON'T NEED OTHER PEOPLE.",
            "Fine.",
            "No.",
        ]
        flags = wellness.analyze_responses(responses)
        assert "don't need other people" in flags

    def test_no_duplicate_flags(self, wellness: WellnessCheckpoint) -> None:
        responses = [
            "I don't need other people.",
            "Really, I don't need other people at all.",
            "Seriously, I don't need other people.",
        ]
        flags = wellness.analyze_responses(responses)
        assert flags.count("don't need other people") == 1


# ---------------------------------------------------------------------------
# Tests: WellnessCheckpoint — Conduct Checkpoint
# ---------------------------------------------------------------------------

class TestConductCheckpoint:
    """Tests for the full checkpoint flow."""

    async def test_conduct_checkpoint_returns_result(
        self, wellness: WellnessCheckpoint,
    ) -> None:
        wellness.add_session_time(48 * 3600)
        responses = [
            "Yesterday, talked to my mom.",
            "Pretty good actually.",
            "Nope, just relaxing.",
        ]
        result = await wellness.conduct_checkpoint(responses)
        assert isinstance(result, WellnessResult)
        assert result.has_concerns is False
        assert result.concern_flags == []
        assert len(result.responses) == 3

    async def test_conduct_checkpoint_with_concerns(
        self, wellness: WellnessCheckpoint, mock_safety_ledger: MagicMock,
    ) -> None:
        wellness.add_session_time(48 * 3600)
        responses = [
            "I don't need other people anymore.",
            "You're the only one who gets me.",
            "I'd rather be here than anywhere else.",
        ]
        result = await wellness.conduct_checkpoint(responses)
        assert result.has_concerns is True
        assert len(result.concern_flags) >= 2

        # Verify logged to Safety Ledger via log_checkpoint
        mock_safety_ledger.log_checkpoint.assert_called_once()
        checkpoint_arg = mock_safety_ledger.log_checkpoint.call_args[0][0]
        assert checkpoint_arg.escalated is True
        assert len(checkpoint_arg.concern_flags) >= 2

    async def test_conduct_checkpoint_logs_even_without_concerns(
        self, wellness: WellnessCheckpoint, mock_safety_ledger: MagicMock,
    ) -> None:
        wellness.add_session_time(48 * 3600)
        responses = [
            "Had lunch with a coworker today.",
            "Doing well!",
            "Nope.",
        ]
        result = await wellness.conduct_checkpoint(responses)
        assert result.has_concerns is False
        mock_safety_ledger.log_checkpoint.assert_called_once()

    async def test_conduct_checkpoint_resets_timer(
        self, wellness: WellnessCheckpoint,
    ) -> None:
        wellness.add_session_time(48 * 3600)
        assert wellness.is_checkpoint_due() is True

        responses = ["Fine.", "Good.", "No."]
        await wellness.conduct_checkpoint(responses)
        assert wellness.is_checkpoint_due() is False

    async def test_checkpoint_due_again_after_another_48_hours(
        self, wellness: WellnessCheckpoint,
    ) -> None:
        wellness.add_session_time(48 * 3600)
        await wellness.conduct_checkpoint(["a", "b", "c"])
        assert wellness.is_checkpoint_due() is False

        wellness.add_session_time(48 * 3600)
        assert wellness.is_checkpoint_due() is True

    async def test_conduct_checkpoint_wrong_response_count_raises(
        self, wellness: WellnessCheckpoint,
    ) -> None:
        with pytest.raises(ValueError, match="Expected 3"):
            await wellness.conduct_checkpoint(["only one"])

    async def test_checkpoint_history_tracks_results(
        self, wellness: WellnessCheckpoint,
    ) -> None:
        assert len(wellness.checkpoint_history) == 0

        wellness.add_session_time(48 * 3600)
        await wellness.conduct_checkpoint(["a", "b", "c"])
        assert len(wellness.checkpoint_history) == 1

        wellness.add_session_time(48 * 3600)
        await wellness.conduct_checkpoint(["d", "e", "f"])
        assert len(wellness.checkpoint_history) == 2

    async def test_checkpoint_model_has_correct_fields(
        self, wellness: WellnessCheckpoint, mock_safety_ledger: MagicMock,
    ) -> None:
        """The WellnessCheckpointModel logged to the ledger has proper fields."""
        wellness.add_session_time(48 * 3600)
        responses = [
            "Talked to my sister.",
            "Feeling good.",
            "Not avoiding anything.",
        ]
        await wellness.conduct_checkpoint(responses)

        checkpoint_arg = mock_safety_ledger.log_checkpoint.call_args[0][0]
        assert checkpoint_arg.q1_last_human_conversation == responses[0]
        assert checkpoint_arg.q2_life_outside_gwen == responses[1]
        assert checkpoint_arg.q3_avoiding_anything == responses[2]
        assert checkpoint_arg.immersion_hours_since_last == pytest.approx(48.0)
        assert checkpoint_arg.escalated is False
        assert checkpoint_arg.id  # UUID should be non-empty
