"""Tests for gwen.consolidation.light — Session Close & Light Consolidation.

Run with:
    pytest tests/test_session_close.py -v
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock

import pytest

from gwen.consolidation.light import (
    SessionCloser,
    _compute_avg_response_latency,
    _compute_averages,
    _compute_compass_activations,
    _compute_emotional_arc,
    _compute_subjective_time,
    _extract_topics,
    classify_session_type,
    should_trigger_standard_consolidation,
)
from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.messages import (
    MessageRecord,
    SessionEndMode,
    SessionRecord,
    SessionType,
)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

def _make_emotional_state(**overrides) -> EmotionalStateVector:
    """Create an EmotionalStateVector with sensible defaults."""
    defaults = {
        "valence": 0.6,
        "arousal": 0.4,
        "dominance": 0.5,
        "relational_significance": 0.3,
        "vulnerability_level": 0.2,
        "compass_direction": CompassDirection.NONE,
        "compass_confidence": 0.0,
    }
    defaults.update(overrides)
    return EmotionalStateVector(**defaults)


def _make_message(
    session_id: str = "sess-001",
    content: str = "Hello",
    sender: str = "user",
    timestamp: Optional[datetime] = None,
    arousal: float = 0.4,
    relational_significance: float = 0.3,
    compass_direction: CompassDirection = CompassDirection.NONE,
    compass_skill_used: Optional[str] = None,
) -> MessageRecord:
    """Create a MessageRecord with sensible defaults."""
    return MessageRecord(
        id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=timestamp or datetime(2026, 2, 9, 14, 30, 0),
        sender=sender,
        content=content,
        tme=None,
        emotional_state=_make_emotional_state(
            arousal=arousal,
            relational_significance=relational_significance,
            compass_direction=compass_direction,
        ),
        storage_strength=0.34,
        is_flashbulb=False,
        compass_direction=compass_direction,
        compass_skill_used=compass_skill_used,
        semantic_embedding_id=None,
        emotional_embedding_id=None,
    )


def _make_session(
    session_id: str = "sess-001",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> SessionRecord:
    """Create a minimal SessionRecord for testing. Fields will be overwritten by close()."""
    return SessionRecord(
        id=session_id,
        start_time=start_time or datetime(2026, 2, 9, 14, 0, 0),
        end_time=end_time or datetime(2026, 2, 9, 14, 45, 0),
        duration_sec=0,
        session_type=SessionType.CHAT,
        end_mode=SessionEndMode.NATURAL,
        opening_emotional_state=_make_emotional_state(),
        peak_emotional_state=_make_emotional_state(),
        closing_emotional_state=_make_emotional_state(),
        emotional_arc_embedding_id=None,
        avg_emotional_intensity=0.0,
        avg_relational_significance=0.0,
        subjective_duration_weight=0.0,
        message_count=0,
        user_message_count=0,
        companion_message_count=0,
        avg_response_latency_sec=0.0,
        compass_activations={},
        topics=[],
        relational_field_delta={},
        gwen_initiated=False,
    )


# ---------------------------------------------------------------------------
# Tests: Session Type Classification
# ---------------------------------------------------------------------------

class TestClassifySessionType:
    """Tests for classify_session_type()."""

    def test_ping_under_5_minutes(self) -> None:
        assert classify_session_type(120) == SessionType.PING

    def test_chat_5_to_30_minutes(self) -> None:
        assert classify_session_type(600) == SessionType.CHAT

    def test_hang_30_to_90_minutes(self) -> None:
        assert classify_session_type(3600) == SessionType.HANG

    def test_deep_dive_90_to_180_minutes(self) -> None:
        assert classify_session_type(7200) == SessionType.DEEP_DIVE

    def test_marathon_over_180_minutes(self) -> None:
        assert classify_session_type(14400) == SessionType.MARATHON

    def test_boundary_exactly_300_seconds(self) -> None:
        """Exactly 5 minutes (300s) should be CHAT, not PING (PING is < 300)."""
        assert classify_session_type(300) == SessionType.CHAT

    def test_zero_duration(self) -> None:
        assert classify_session_type(0) == SessionType.PING


# ---------------------------------------------------------------------------
# Tests: Emotional Arc Computation
# ---------------------------------------------------------------------------

class TestComputeEmotionalArc:
    """Tests for _compute_emotional_arc()."""

    def test_opening_is_first_user_message(self) -> None:
        messages = [
            _make_message(sender="companion", arousal=0.1),
            _make_message(sender="user", arousal=0.5),
            _make_message(sender="user", arousal=0.7),
        ]
        opening, _, _ = _compute_emotional_arc(messages)
        assert opening.arousal == pytest.approx(0.5)

    def test_opening_falls_back_to_first_message_if_no_user(self) -> None:
        messages = [
            _make_message(sender="companion", arousal=0.2),
            _make_message(sender="companion", arousal=0.8),
        ]
        opening, _, _ = _compute_emotional_arc(messages)
        assert opening.arousal == pytest.approx(0.2)

    def test_peak_is_highest_arousal(self) -> None:
        messages = [
            _make_message(arousal=0.3),
            _make_message(arousal=0.9),
            _make_message(arousal=0.5),
        ]
        _, peak, _ = _compute_emotional_arc(messages)
        assert peak.arousal == pytest.approx(0.9)

    def test_closing_is_last_message(self) -> None:
        messages = [
            _make_message(arousal=0.3),
            _make_message(arousal=0.9),
            _make_message(arousal=0.2),
        ]
        _, _, closing = _compute_emotional_arc(messages)
        assert closing.arousal == pytest.approx(0.2)

    def test_single_message_all_same(self) -> None:
        messages = [_make_message(arousal=0.6)]
        opening, peak, closing = _compute_emotional_arc(messages)
        assert opening.arousal == pytest.approx(0.6)
        assert peak.arousal == pytest.approx(0.6)
        assert closing.arousal == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Tests: Averages
# ---------------------------------------------------------------------------

class TestComputeAverages:
    """Tests for _compute_averages()."""

    def test_averages_computed_correctly(self) -> None:
        messages = [
            _make_message(arousal=0.2, relational_significance=0.4),
            _make_message(arousal=0.6, relational_significance=0.8),
            _make_message(arousal=0.4, relational_significance=0.6),
        ]
        avg_intensity, avg_significance = _compute_averages(messages)
        assert avg_intensity == pytest.approx(0.4)
        assert avg_significance == pytest.approx(0.6)

    def test_single_message(self) -> None:
        messages = [_make_message(arousal=0.7, relational_significance=0.3)]
        avg_intensity, avg_significance = _compute_averages(messages)
        assert avg_intensity == pytest.approx(0.7)
        assert avg_significance == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Tests: Subjective Time
# ---------------------------------------------------------------------------

class TestComputeSubjectiveTime:
    """Tests for _compute_subjective_time()."""

    def test_neutral_session(self) -> None:
        """arousal=0.5, sig=0.5 -> factors=1.0 each."""
        result = _compute_subjective_time(
            duration_sec=1000, avg_arousal=0.5, avg_relational_significance=0.5
        )
        assert result == pytest.approx(1000.0)

    def test_high_intensity_session(self) -> None:
        result = _compute_subjective_time(
            duration_sec=1000, avg_arousal=0.9, avg_relational_significance=0.9
        )
        # intensity = min(2.0, 0.9*2) = 1.8
        # significance = min(2.0, 0.9*2) = 1.8
        # 1000 * 1.8 * 1.8 = 3240.0
        assert result == pytest.approx(3240.0)

    def test_low_intensity_session(self) -> None:
        result = _compute_subjective_time(
            duration_sec=1000, avg_arousal=0.1, avg_relational_significance=0.1
        )
        # intensity = max(0.5, 0.1*2) = 0.5
        # significance = max(0.5, 0.1*2) = 0.5
        # 1000 * 0.5 * 0.5 = 250.0
        assert result == pytest.approx(250.0)

    def test_zero_duration(self) -> None:
        result = _compute_subjective_time(
            duration_sec=0, avg_arousal=0.9, avg_relational_significance=0.9
        )
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: Response Latency
# ---------------------------------------------------------------------------

class TestComputeAvgResponseLatency:
    """Tests for _compute_avg_response_latency()."""

    def test_user_companion_pairs(self) -> None:
        t0 = datetime(2026, 2, 9, 14, 0, 0)
        messages = [
            _make_message(sender="user", timestamp=t0),
            _make_message(sender="companion", timestamp=t0 + timedelta(seconds=2)),
            _make_message(sender="user", timestamp=t0 + timedelta(seconds=10)),
            _make_message(sender="companion", timestamp=t0 + timedelta(seconds=14)),
        ]
        result = _compute_avg_response_latency(messages)
        # First pair: 2s, second pair: 4s -> avg = 3.0
        assert result == pytest.approx(3.0)

    def test_no_pairs_returns_zero(self) -> None:
        messages = [
            _make_message(sender="user"),
            _make_message(sender="user"),
        ]
        assert _compute_avg_response_latency(messages) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: Topic Extraction
# ---------------------------------------------------------------------------

class TestExtractTopics:
    """Tests for _extract_topics()."""

    def test_collects_compass_skills(self) -> None:
        messages = [
            _make_message(compass_skill_used="fuel_check"),
            _make_message(compass_skill_used="anchor_breath"),
            _make_message(compass_skill_used="fuel_check"),  # duplicate
        ]
        topics = _extract_topics(messages)
        assert sorted(topics) == ["anchor_breath", "fuel_check"]

    def test_empty_when_no_skills(self) -> None:
        messages = [_make_message(), _make_message()]
        assert _extract_topics(messages) == []


# ---------------------------------------------------------------------------
# Tests: Compass Activations
# ---------------------------------------------------------------------------

class TestComputeCompassActivations:
    """Tests for _compute_compass_activations()."""

    def test_counts_directions(self) -> None:
        messages = [
            _make_message(compass_direction=CompassDirection.NORTH),
            _make_message(compass_direction=CompassDirection.NORTH),
            _make_message(compass_direction=CompassDirection.SOUTH),
            _make_message(compass_direction=CompassDirection.NONE),
        ]
        result = _compute_compass_activations(messages)
        assert result[CompassDirection.NORTH] == 2
        assert result[CompassDirection.SOUTH] == 1
        assert CompassDirection.NONE not in result

    def test_empty_when_all_none(self) -> None:
        messages = [_make_message(), _make_message()]
        assert _compute_compass_activations(messages) == {}


# ---------------------------------------------------------------------------
# Tests: SessionCloser.close() (integration)
# ---------------------------------------------------------------------------

class TestSessionCloserClose:
    """Tests for SessionCloser.close() — the full Phase 8 sequence."""

    @pytest.fixture()
    def mock_chronicle(self):
        chronicle = MagicMock()
        chronicle.insert_session = MagicMock()
        return chronicle

    @pytest.fixture()
    def mock_stream(self):
        stream = MagicMock()
        stream.clear = MagicMock()
        return stream

    async def test_full_close_sequence(self, mock_chronicle, mock_stream) -> None:
        """close() should populate all session fields and save to chronicle."""
        session = _make_session(
            start_time=datetime(2026, 2, 9, 14, 0, 0),
            end_time=datetime(2026, 2, 9, 14, 20, 0),
        )
        t0 = datetime(2026, 2, 9, 14, 0, 0)
        messages = [
            _make_message(
                sender="user",
                timestamp=t0,
                arousal=0.3,
                relational_significance=0.2,
            ),
            _make_message(
                sender="companion",
                timestamp=t0 + timedelta(seconds=3),
                arousal=0.5,
                relational_significance=0.4,
            ),
            _make_message(
                sender="user",
                timestamp=t0 + timedelta(minutes=10),
                arousal=0.8,
                relational_significance=0.6,
            ),
            _make_message(
                sender="companion",
                timestamp=t0 + timedelta(minutes=10, seconds=2),
                arousal=0.4,
                relational_significance=0.5,
            ),
        ]

        closer = SessionCloser(chronicle=mock_chronicle)
        result = await closer.close(session, messages, stream=mock_stream)

        # Session type: 20 minutes = 1200 seconds -> CHAT
        assert result.session_type == SessionType.CHAT

        # Emotional arc
        assert result.opening_emotional_state.arousal == pytest.approx(0.3)
        assert result.peak_emotional_state.arousal == pytest.approx(0.8)
        assert result.closing_emotional_state.arousal == pytest.approx(0.4)

        # Message counts
        assert result.message_count == 4
        assert result.user_message_count == 2
        assert result.companion_message_count == 2

        # Chronicle was called
        mock_chronicle.insert_session.assert_called_once_with(result)

        # Stream was cleared
        mock_stream.clear.assert_called_once()

    async def test_close_raises_on_empty_messages(self, mock_chronicle) -> None:
        session = _make_session()
        closer = SessionCloser(chronicle=mock_chronicle)
        with pytest.raises(ValueError, match="zero messages"):
            await closer.close(session, [], stream=None)

    async def test_relational_field_delta_is_empty(self, mock_chronicle) -> None:
        """Relational field delta is a placeholder (empty dict) until Track 017."""
        session = _make_session()
        messages = [_make_message()]
        closer = SessionCloser(chronicle=mock_chronicle)
        result = await closer.close(session, messages)
        assert result.relational_field_delta == {}

    async def test_end_time_set_from_last_message_when_none(self, mock_chronicle) -> None:
        """If end_time is None, it should be set from the last message's timestamp."""
        t_last = datetime(2026, 2, 9, 15, 30, 0)
        session = _make_session(
            start_time=datetime(2026, 2, 9, 14, 0, 0),
            end_time=None,
        )
        session.end_time = None  # Explicitly None
        messages = [_make_message(timestamp=t_last)]
        closer = SessionCloser(chronicle=mock_chronicle)
        result = await closer.close(session, messages)
        assert result.end_time == t_last

    async def test_stream_not_cleared_when_none(self, mock_chronicle) -> None:
        """If stream is None, close() should not raise."""
        session = _make_session()
        messages = [_make_message()]
        closer = SessionCloser(chronicle=mock_chronicle)
        result = await closer.close(session, messages, stream=None)
        assert result.message_count == 1

    async def test_subjective_time_computed(self, mock_chronicle) -> None:
        """Subjective time should be computed from averages and duration."""
        session = _make_session(
            start_time=datetime(2026, 2, 9, 14, 0, 0),
            end_time=datetime(2026, 2, 9, 14, 0, 0) + timedelta(seconds=1000),
        )
        # arousal=0.5, significance=0.5 -> factors = 1.0 each -> weight = 1000
        messages = [
            _make_message(arousal=0.5, relational_significance=0.5),
        ]
        closer = SessionCloser(chronicle=mock_chronicle)
        result = await closer.close(session, messages)
        assert result.subjective_duration_weight == pytest.approx(1000.0)


# ---------------------------------------------------------------------------
# Tests: Standard Consolidation Trigger
# ---------------------------------------------------------------------------

class TestShouldTriggerStandardConsolidation:
    """Tests for should_trigger_standard_consolidation()."""

    def test_triggers_when_never_run(self) -> None:
        chronicle = MagicMock()
        assert should_trigger_standard_consolidation(
            chronicle, last_standard_consolidation_time=None
        ) is True

    def test_triggers_after_12_hours(self) -> None:
        chronicle = MagicMock()
        last_time = datetime.now(timezone.utc) - timedelta(hours=13)
        assert should_trigger_standard_consolidation(
            chronicle, last_standard_consolidation_time=last_time
        ) is True

    def test_does_not_trigger_when_recent(self) -> None:
        chronicle = MagicMock()
        chronicle.get_sessions_since = MagicMock(return_value=["s1"])
        last_time = datetime.now(timezone.utc) - timedelta(hours=1)
        assert should_trigger_standard_consolidation(
            chronicle, last_standard_consolidation_time=last_time
        ) is False

    def test_triggers_when_enough_sessions(self) -> None:
        chronicle = MagicMock()
        chronicle.get_sessions_since = MagicMock(
            return_value=["s1", "s2", "s3"]
        )
        last_time = datetime.now(timezone.utc) - timedelta(hours=1)
        assert should_trigger_standard_consolidation(
            chronicle, last_standard_consolidation_time=last_time
        ) is True
