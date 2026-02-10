"""Tests for TME generator — temporal metadata envelope computation.

These tests verify TimePhase mapping, session tracking, intra-message timing,
and weekend detection. Inter-session timing is tested with a mock Chronicle.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TimePhase,
)
from gwen.temporal.tme import TMEGenerator, compute_time_phase


# ===========================================================================
# TimePhase Mapping Tests
# ===========================================================================

class TestComputeTimePhase:
    """Test compute_time_phase() maps all 24 hours correctly."""

    def test_deep_night_hours(self) -> None:
        """Hours 0-4 -> DEEP_NIGHT."""
        for hour in range(0, 5):
            assert compute_time_phase(hour) == TimePhase.DEEP_NIGHT, (
                f"Hour {hour} should be DEEP_NIGHT"
            )

    def test_early_morning_hours(self) -> None:
        """Hours 5-7 -> EARLY_MORNING."""
        for hour in range(5, 8):
            assert compute_time_phase(hour) == TimePhase.EARLY_MORNING, (
                f"Hour {hour} should be EARLY_MORNING"
            )

    def test_morning_hours(self) -> None:
        """Hours 8-11 -> MORNING."""
        for hour in range(8, 12):
            assert compute_time_phase(hour) == TimePhase.MORNING, (
                f"Hour {hour} should be MORNING"
            )

    def test_midday_hours(self) -> None:
        """Hours 12-13 -> MIDDAY."""
        for hour in range(12, 14):
            assert compute_time_phase(hour) == TimePhase.MIDDAY, (
                f"Hour {hour} should be MIDDAY"
            )

    def test_afternoon_hours(self) -> None:
        """Hours 14-16 -> AFTERNOON."""
        for hour in range(14, 17):
            assert compute_time_phase(hour) == TimePhase.AFTERNOON, (
                f"Hour {hour} should be AFTERNOON"
            )

    def test_evening_hours(self) -> None:
        """Hours 17-20 -> EVENING."""
        for hour in range(17, 21):
            assert compute_time_phase(hour) == TimePhase.EVENING, (
                f"Hour {hour} should be EVENING"
            )

    def test_late_night_hours(self) -> None:
        """Hours 21-23 -> LATE_NIGHT."""
        for hour in range(21, 24):
            assert compute_time_phase(hour) == TimePhase.LATE_NIGHT, (
                f"Hour {hour} should be LATE_NIGHT"
            )

    def test_all_24_hours_covered(self) -> None:
        """Every hour from 0 to 23 maps to a valid TimePhase (no gaps)."""
        for hour in range(24):
            result = compute_time_phase(hour)
            assert isinstance(result, TimePhase), (
                f"Hour {hour} returned {result!r}, expected a TimePhase enum"
            )

    def test_invalid_hour_negative(self) -> None:
        """Negative hour raises ValueError."""
        try:
            compute_time_phase(-1)
            assert False, "Expected ValueError for hour=-1"
        except ValueError:
            pass

    def test_invalid_hour_24(self) -> None:
        """Hour 24 raises ValueError."""
        try:
            compute_time_phase(24)
            assert False, "Expected ValueError for hour=24"
        except ValueError:
            pass

    def test_boundary_hour_4_to_5(self) -> None:
        """Hour 4 is DEEP_NIGHT, hour 5 is EARLY_MORNING."""
        assert compute_time_phase(4) == TimePhase.DEEP_NIGHT
        assert compute_time_phase(5) == TimePhase.EARLY_MORNING

    def test_boundary_hour_20_to_21(self) -> None:
        """Hour 20 is EVENING, hour 21 is LATE_NIGHT."""
        assert compute_time_phase(20) == TimePhase.EVENING
        assert compute_time_phase(21) == TimePhase.LATE_NIGHT


# ===========================================================================
# TMEGenerator Session Tests
# ===========================================================================

class TestTMEGeneratorSession:
    """Test session lifecycle: start_session, generate, message counting."""

    def test_start_session_returns_id(self) -> None:
        gen = TMEGenerator(chronicle=None)
        sid = gen.start_session("test-session-123")
        assert sid == "test-session-123"

    def test_start_session_auto_generates_id(self) -> None:
        gen = TMEGenerator(chronicle=None)
        sid = gen.start_session()
        assert sid is not None
        assert len(sid) > 0
        assert sid.count("-") == 4

    def test_generate_requires_session(self) -> None:
        gen = TMEGenerator(chronicle=None)
        try:
            gen.generate("user")
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "start_session" in str(e)

    def test_first_message_index_is_zero(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")
        assert tme.msg_index_in_session == 0

    def test_message_index_increments(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme0 = gen.generate("user")
        tme1 = gen.generate("companion")
        tme2 = gen.generate("user")
        assert tme0.msg_index_in_session == 0
        assert tme1.msg_index_in_session == 1
        assert tme2.msg_index_in_session == 2

    def test_session_id_in_tme(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("my-session")
        tme = gen.generate("user")
        assert tme.session_id == "my-session"

    def test_session_duration_increases(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme0 = gen.generate("user")
        time.sleep(0.05)
        tme1 = gen.generate("user")
        assert tme1.session_duration_sec >= tme0.session_duration_sec


# ===========================================================================
# Intra-Message Timing Tests
# ===========================================================================

class TestTMEIntraMessageTiming:
    """Test timing between messages within a session."""

    def test_first_message_has_none_timing(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")
        assert tme.time_since_last_msg_sec is None
        assert tme.time_since_last_user_msg_sec is None
        assert tme.time_since_last_gwen_msg_sec is None

    def test_second_message_has_timing(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        gen.generate("user")
        time.sleep(0.05)
        tme = gen.generate("user")
        assert tme.time_since_last_msg_sec is not None
        assert tme.time_since_last_msg_sec > 0.0
        assert tme.time_since_last_user_msg_sec is not None
        assert tme.time_since_last_user_msg_sec > 0.0

    def test_companion_message_after_user(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        gen.generate("user")
        time.sleep(0.05)
        tme = gen.generate("companion")
        assert tme.time_since_last_msg_sec is not None
        assert tme.time_since_last_user_msg_sec is not None
        assert tme.time_since_last_gwen_msg_sec is None

    def test_user_message_after_companion(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        gen.generate("user")
        time.sleep(0.05)
        gen.generate("companion")
        time.sleep(0.05)
        tme = gen.generate("user")
        assert tme.time_since_last_msg_sec is not None
        assert tme.time_since_last_user_msg_sec is not None
        assert tme.time_since_last_gwen_msg_sec is not None

    def test_user_message_density_count(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        gen.generate("user")
        gen.generate("user")
        tme = gen.generate("user")
        assert tme.user_msgs_last_5min == 2
        assert tme.user_msgs_last_hour == 2
        assert tme.user_msgs_last_24hr == 2


# ===========================================================================
# Weekend Detection Tests
# ===========================================================================

class TestTMEWeekendDetection:

    def test_tme_has_is_weekend_field(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")
        assert isinstance(tme.is_weekend, bool)

    def test_weekend_day_names(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")
        if tme.day_of_week in ("Saturday", "Sunday"):
            assert tme.is_weekend is True
        else:
            assert tme.is_weekend is False


# ===========================================================================
# Inter-Session Timing Tests (with mock Chronicle)
# ===========================================================================

class TestTMEInterSessionTiming:

    def test_no_chronicle_defaults(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")
        assert tme.last_session_end is None
        assert tme.hours_since_last_session is None
        assert tme.sessions_last_7_days == 0
        assert tme.sessions_last_30_days == 0
        assert tme.avg_session_gap_30d_hours is None

    def test_with_mock_chronicle(self) -> None:
        mock_chronicle = MagicMock()
        two_hours_ago = datetime.now() - timedelta(hours=2)
        mock_chronicle.get_last_session_end.return_value = two_hours_ago
        mock_chronicle.count_sessions_since.return_value = 5
        t1 = datetime.now() - timedelta(days=3)
        t2 = datetime.now() - timedelta(days=2)
        t3 = datetime.now() - timedelta(days=1)
        mock_chronicle.get_session_start_times_since.return_value = [t1, t2, t3]

        gen = TMEGenerator(chronicle=mock_chronicle)
        gen.start_session("s1")
        tme = gen.generate("user")

        assert tme.last_session_end is not None
        assert tme.hours_since_last_session is not None
        assert tme.hours_since_last_session > 1.0
        assert tme.sessions_last_7_days == 5
        assert tme.sessions_last_30_days == 5
        assert tme.avg_session_gap_30d_hours is not None
        assert tme.avg_session_gap_30d_hours > 0.0


# ===========================================================================
# Circadian Deviation Tests
# ===========================================================================

class TestTMECircadianDeviation:

    def test_default_circadian_deviation_is_none(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")
        assert tme.circadian_deviation_severity == CircadianDeviationSeverity.NONE
        assert tme.circadian_deviation_type is None


# ===========================================================================
# TME Field Completeness Tests
# ===========================================================================

class TestTMEFieldCompleteness:

    def test_all_fields_present(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")

        # Absolute time
        assert isinstance(tme.timestamp_utc, datetime)
        assert isinstance(tme.local_time, datetime)

        # Clock position
        assert isinstance(tme.hour_of_day, int)
        assert 0 <= tme.hour_of_day <= 23
        assert isinstance(tme.day_of_week, str)
        assert tme.day_of_week in (
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        )
        assert isinstance(tme.day_of_month, int)
        assert 1 <= tme.day_of_month <= 31
        assert isinstance(tme.month, int)
        assert 1 <= tme.month <= 12
        assert isinstance(tme.year, int)
        assert isinstance(tme.is_weekend, bool)
        assert isinstance(tme.time_phase, TimePhase)

        # Session context
        assert isinstance(tme.session_id, str)
        assert isinstance(tme.session_start, datetime)
        assert isinstance(tme.session_duration_sec, int)
        assert tme.session_duration_sec >= 0
        assert isinstance(tme.msg_index_in_session, int)
        assert tme.msg_index_in_session >= 0

        # Intra-message timing (first message: all None/0)
        assert tme.time_since_last_msg_sec is None
        assert tme.time_since_last_user_msg_sec is None
        assert tme.time_since_last_gwen_msg_sec is None
        assert isinstance(tme.user_msgs_last_5min, int)
        assert isinstance(tme.user_msgs_last_hour, int)
        assert isinstance(tme.user_msgs_last_24hr, int)

        # Circadian deviation
        assert isinstance(tme.circadian_deviation_severity, CircadianDeviationSeverity)


# ===========================================================================
# Session Reset Tests
# ===========================================================================

class TestTMESessionReset:

    def test_new_session_resets_message_index(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        gen.generate("user")
        gen.generate("user")
        gen.start_session("s2")
        tme = gen.generate("user")
        assert tme.msg_index_in_session == 0

    def test_new_session_resets_timing(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        gen.generate("user")
        gen.generate("user")
        gen.start_session("s2")
        tme = gen.generate("user")
        assert tme.time_since_last_msg_sec is None

    def test_new_session_resets_density_counters(self) -> None:
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        gen.generate("user")
        gen.generate("user")
        gen.generate("user")
        gen.start_session("s2")
        tme = gen.generate("user")
        assert tme.user_msgs_last_5min == 0
