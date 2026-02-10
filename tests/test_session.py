"""Tests for session management.

Tests the SessionManager lifecycle, session type classification,
gap analysis computation, and timeout detection.
"""

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from gwen.core.session_manager import SessionManager, detect_goodbye, GOODBYE_KEYWORDS
from gwen.models.messages import SessionRecord, SessionType, SessionEndMode
from gwen.models.emotional import EmotionalStateVector, CompassDirection
from gwen.models.memory import GapAnalysis, GapClassification, ReturnContext
from gwen.temporal.gap import compute_gap_analysis, generate_return_context


# ============================================================
# Fixtures
# ============================================================

def _make_neutral_emotion() -> EmotionalStateVector:
    """Create a neutral EmotionalStateVector for testing."""
    return EmotionalStateVector(
        valence=0.5,
        arousal=0.3,
        dominance=0.5,
        relational_significance=0.0,
        vulnerability_level=0.0,
        compass_direction=CompassDirection.NONE,
        compass_confidence=0.0,
    )


def _make_session(
    start_time: datetime,
    end_time: datetime,
    session_type: SessionType = SessionType.CHAT,
    end_mode: SessionEndMode = SessionEndMode.NATURAL,
    topics: list[str] | None = None,
    closing_valence: float = 0.5,
    closing_arousal: float = 0.3,
) -> SessionRecord:
    """Create a mock SessionRecord for testing gap analysis."""
    emotion = EmotionalStateVector(
        valence=closing_valence,
        arousal=closing_arousal,
        dominance=0.5,
        relational_significance=0.0,
        vulnerability_level=0.0,
        compass_direction=CompassDirection.NONE,
        compass_confidence=0.0,
    )
    return SessionRecord(
        id=f"test-session-{start_time.isoformat()}",
        start_time=start_time,
        end_time=end_time,
        duration_sec=int((end_time - start_time).total_seconds()),
        session_type=session_type,
        end_mode=end_mode,
        opening_emotional_state=emotion,
        peak_emotional_state=emotion,
        closing_emotional_state=emotion,
        emotional_arc_embedding_id=None,
        avg_emotional_intensity=0.3,
        avg_relational_significance=0.0,
        subjective_duration_weight=0.0,
        message_count=10,
        user_message_count=5,
        companion_message_count=5,
        avg_response_latency_sec=1.5,
        compass_activations={},
        topics=topics or ["general"],
        relational_field_delta={},
        gwen_initiated=False,
    )


def _make_mock_chronicle(sessions: list[SessionRecord] | None = None) -> MagicMock:
    """Create a mock Chronicle that returns sessions newest-first."""
    mock = MagicMock()
    if sessions is None:
        sessions = []
    sorted_sessions = sorted(sessions, key=lambda s: s.start_time, reverse=True)
    mock.get_last_n_sessions.return_value = sorted_sessions
    mock.insert_session.return_value = None
    return mock


def _make_mock_tme_generator() -> MagicMock:
    """Create a mock TMEGenerator."""
    return MagicMock()


# ============================================================
# Session Type Classification Tests
# ============================================================

class TestSessionTypeClassification:
    """Test that _classify_session_type maps durations to correct types."""

    def _make_manager(self) -> SessionManager:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        return SessionManager(chronicle=chronicle, tme_generator=tme_gen)

    def test_classify_ping_zero_seconds(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(0) == SessionType.PING

    def test_classify_ping_under_5min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(299) == SessionType.PING

    def test_classify_chat_at_5min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(300) == SessionType.CHAT

    def test_classify_chat_under_30min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(1799) == SessionType.CHAT

    def test_classify_hang_at_30min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(1800) == SessionType.HANG

    def test_classify_hang_under_90min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(5399) == SessionType.HANG

    def test_classify_deep_dive_at_90min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(5400) == SessionType.DEEP_DIVE

    def test_classify_deep_dive_under_180min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(10799) == SessionType.DEEP_DIVE

    def test_classify_marathon_at_180min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(10800) == SessionType.MARATHON

    def test_classify_marathon_very_long(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(86400) == SessionType.MARATHON


# ============================================================
# Gap Analysis Tests
# ============================================================

class TestGapAnalysis:
    """Test compute_gap_analysis with various session histories."""

    def test_no_previous_sessions_returns_none(self) -> None:
        chronicle = _make_mock_chronicle(sessions=[])
        result = compute_gap_analysis(chronicle)
        assert result is None

    def test_one_previous_session_returns_normal(self) -> None:
        now = datetime.now(timezone.utc)
        session = _make_session(
            start_time=now - timedelta(hours=5),
            end_time=now - timedelta(hours=4),
        )
        chronicle = _make_mock_chronicle(sessions=[session])
        result = compute_gap_analysis(chronicle)

        assert result is not None
        assert result.classification == GapClassification.NORMAL
        assert result.duration_hours > 0

    def test_normal_gap_within_one_sigma(self) -> None:
        now = datetime.now(timezone.utc)
        sessions = []
        for i in range(10):
            start = now - timedelta(hours=(10 - i) * 9, minutes=30)
            end = start + timedelta(hours=1)
            sessions.append(_make_session(start_time=start, end_time=end))

        sessions[-1] = _make_session(
            start_time=now - timedelta(hours=9),
            end_time=now - timedelta(hours=8),
        )

        chronicle = _make_mock_chronicle(sessions=sessions)
        result = compute_gap_analysis(chronicle)

        assert result is not None
        assert result.classification == GapClassification.NORMAL

    def test_anomalous_gap_beyond_three_sigma(self) -> None:
        now = datetime.now(timezone.utc)
        sessions = []
        for i in range(10):
            start = now - timedelta(days=30, hours=(10 - i) * 3)
            end = start + timedelta(hours=1)
            sessions.append(_make_session(start_time=start, end_time=end))

        sessions[-1] = _make_session(
            start_time=now - timedelta(days=30),
            end_time=now - timedelta(days=30) + timedelta(hours=1),
        )

        chronicle = _make_mock_chronicle(sessions=sessions)
        result = compute_gap_analysis(chronicle)

        assert result is not None
        assert result.classification in (
            GapClassification.SIGNIFICANT,
            GapClassification.ANOMALOUS,
        )
        assert result.deviation_sigma > 2.0

    def test_gap_includes_last_session_context(self) -> None:
        now = datetime.now(timezone.utc)
        sessions = []
        for i in range(5):
            start = now - timedelta(hours=(5 - i) * 10)
            end = start + timedelta(hours=1)
            sessions.append(_make_session(
                start_time=start,
                end_time=end,
                topics=["work", "stress"],
                end_mode=SessionEndMode.ABRUPT,
            ))

        chronicle = _make_mock_chronicle(sessions=sessions)
        result = compute_gap_analysis(chronicle)

        assert result is not None
        # gap.py converts enum to string value
        assert result.last_session_end_mode == "abrupt"
        assert result.last_topic == "stress"


# ============================================================
# Return Context Tests
# ============================================================

class TestReturnContext:
    """Test generate_return_context output."""

    def _make_gap(
        self,
        hours: float = 72.0,
        classification: GapClassification = GapClassification.SIGNIFICANT,
        end_mode: str = "natural",
        valence: float = 0.5,
    ) -> GapAnalysis:
        emotion = EmotionalStateVector(
            valence=valence,
            arousal=0.3,
            dominance=0.5,
            relational_significance=0.0,
            vulnerability_level=0.0,
            compass_direction=CompassDirection.NONE,
            compass_confidence=0.0,
        )
        return GapAnalysis(
            duration_hours=hours,
            deviation_sigma=2.5,
            classification=classification,
            last_session_type="chat",
            last_session_end_mode=end_mode,
            last_emotional_state=emotion,
            last_topic="work",
            open_threads=[],
            known_explanations=[],
        )

    def test_gap_duration_display_days_and_hours(self) -> None:
        gap = self._make_gap(hours=75.0)
        ctx = generate_return_context(gap)
        assert "3 days" in ctx.gap_duration_display
        assert "3 hours" in ctx.gap_duration_display

    def test_gap_duration_display_hours_only(self) -> None:
        gap = self._make_gap(hours=5.0)
        ctx = generate_return_context(gap)
        assert "day" not in ctx.gap_duration_display
        assert "5 hours" in ctx.gap_duration_display

    def test_preceding_summary_includes_end_mode(self) -> None:
        gap = self._make_gap(end_mode="abrupt")
        ctx = generate_return_context(gap)
        assert "abruptly" in ctx.preceding_summary.lower() or "abrupt" in ctx.preceding_summary.lower()

    def test_anomalous_abrupt_approach_is_gentle(self) -> None:
        gap = self._make_gap(
            classification=GapClassification.ANOMALOUS,
            end_mode="abrupt",
        )
        ctx = generate_return_context(gap)
        assert "gentle" in ctx.suggested_approach.lower() or "warm" in ctx.suggested_approach.lower()

    def test_notable_approach_is_light(self) -> None:
        gap = self._make_gap(classification=GapClassification.NOTABLE)
        ctx = generate_return_context(gap)
        assert "natural" in ctx.suggested_approach.lower() or "warm" in ctx.suggested_approach.lower()


# ============================================================
# Session Lifecycle Tests
# ============================================================

class TestSessionLifecycle:
    """Test the full start -> add_message -> end flow."""

    def test_start_session_returns_partial_record(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        session = mgr.start_session()

        assert session.id is not None
        assert len(session.id) == 36
        assert session.start_time is not None
        assert session.end_time is None
        assert session.duration_sec == 0
        assert session.gwen_initiated is False

    def test_start_session_companion_initiated(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        session = mgr.start_session(initiated_by="companion")
        assert session.gwen_initiated is True

    def test_cannot_start_two_sessions(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        with pytest.raises(RuntimeError, match="Cannot start a new session"):
            mgr.start_session()

    def test_add_message_increments_counts(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")
        mgr.add_message("companion")
        mgr.add_message("user")

        assert mgr._user_message_count == 2
        assert mgr._companion_message_count == 1

    def test_add_message_invalid_sender_raises(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        with pytest.raises(ValueError, match="sender must be"):
            mgr.add_message("system")

    def test_add_message_no_session_raises(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        with pytest.raises(RuntimeError, match="no session is active"):
            mgr.add_message("user")

    def test_end_session_finalizes_record(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")
        mgr.add_message("companion")

        result = mgr.end_session(SessionEndMode.EXPLICIT_GOODBYE)

        assert result.end_time is not None
        assert result.end_mode == SessionEndMode.EXPLICIT_GOODBYE
        assert result.message_count == 2
        assert result.user_message_count == 1
        assert result.companion_message_count == 1
        assert result.session_type == SessionType.PING

    def test_end_session_saves_to_chronicle(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.end_session(SessionEndMode.NATURAL)

        chronicle.insert_session.assert_called_once()

    def test_end_session_clears_state(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.end_session(SessionEndMode.NATURAL)

        assert mgr.current_session is None
        assert mgr._user_message_count == 0
        assert mgr._companion_message_count == 0

    def test_end_session_no_session_raises(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        with pytest.raises(RuntimeError, match="no session is active"):
            mgr.end_session(SessionEndMode.NATURAL)


# ============================================================
# Timeout Detection Tests
# ============================================================

class TestTimeoutDetection:
    """Test detect_timeout behavior."""

    def test_no_session_returns_none(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        assert mgr.detect_timeout() is None

    def test_within_threshold_returns_none(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")

        assert mgr.detect_timeout(idle_threshold_sec=1800) is None

    def test_timeout_after_user_message_returns_abrupt(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")

        mgr._last_message_time = time.monotonic() - 2000

        result = mgr.detect_timeout(idle_threshold_sec=1800)
        assert result == SessionEndMode.ABRUPT

    def test_timeout_after_companion_message_returns_fade_out(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")
        mgr.add_message("companion")

        mgr._last_message_time = time.monotonic() - 2000

        result = mgr.detect_timeout(idle_threshold_sec=1800)
        assert result == SessionEndMode.FADE_OUT

    def test_timeout_empty_session_returns_fade_out(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()

        mgr._session_start_monotonic = time.monotonic() - 2000

        result = mgr.detect_timeout(idle_threshold_sec=1800)
        assert result == SessionEndMode.FADE_OUT

    def test_custom_threshold(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")

        mgr._last_message_time = time.monotonic() - 10

        assert mgr.detect_timeout(idle_threshold_sec=1800) is None
        assert mgr.detect_timeout(idle_threshold_sec=5) == SessionEndMode.ABRUPT


# ============================================================
# Goodbye Detection Tests
# ============================================================

class TestGoodbyeDetection:
    """Test the detect_goodbye helper."""

    def test_explicit_goodbye(self) -> None:
        assert detect_goodbye("Goodbye!") is True

    def test_bye(self) -> None:
        assert detect_goodbye("bye") is True

    def test_goodnight(self) -> None:
        assert detect_goodbye("Goodnight, Gwen") is True

    def test_ttyl(self) -> None:
        assert detect_goodbye("ttyl") is True

    def test_talk_later(self) -> None:
        assert detect_goodbye("Talk to you later!") is True

    def test_no_goodbye(self) -> None:
        assert detect_goodbye("How are you doing today?") is False

    def test_empty_string(self) -> None:
        assert detect_goodbye("") is False

    def test_case_insensitive(self) -> None:
        assert detect_goodbye("GOODBYE") is True
        assert detect_goodbye("See Ya") is True
