"""Tests for gwen.temporal.circadian — circadian deviation detection.

Run with:
    pytest tests/test_circadian.py -v
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gwen.temporal.circadian import CircadianDeviationDetector
from gwen.temporal.rhythm import RhythmTracker
from gwen.models.temporal import CircadianDeviationSeverity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

import pytest


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Create a temporary database with a messages table."""
    db_path = tmp_path / "test_circadian.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            timestamp TEXT NOT NULL,
            sender TEXT,
            content TEXT,
            valence REAL, arousal REAL, dominance REAL,
            relational_significance REAL, vulnerability_level REAL,
            storage_strength REAL, is_flashbulb INTEGER,
            compass_direction TEXT, compass_skill_used TEXT,
            semantic_embedding_id TEXT, emotional_embedding_id TEXT,
            tme_json TEXT
        )
    """)
    conn.commit()
    conn.close()
    return db_path


def _insert_messages_at_hour(
    db_path: Path,
    hour: int,
    count: int,
    days_back: int = 30,
) -> None:
    """Insert ``count`` messages at the given hour spread over recent days.

    Each message gets a unique timestamp at the given hour on consecutive
    days going backwards from today.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database.
    hour : int
        The hour (0-23) to set for each message's timestamp.
    count : int
        Number of messages to insert.
    days_back : int
        Maximum days back to spread the messages.
    """
    conn = sqlite3.connect(str(db_path))
    now = datetime.now(timezone.utc)
    for i in range(count):
        day_offset = i % days_back
        ts = now - timedelta(days=day_offset)
        ts = ts.replace(hour=hour, minute=0, second=0, microsecond=0)
        msg_id = f"msg-h{hour}-{i:04d}"
        conn.execute(
            "INSERT OR IGNORE INTO messages (id, session_id, timestamp, sender, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (msg_id, "session-001", ts.isoformat(), "user", f"Message at {hour}:00"),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tests: CircadianDeviationDetector
# ---------------------------------------------------------------------------

class TestCircadianDeviationDetector:
    """Tests for CircadianDeviationDetector."""

    def test_insufficient_data_returns_none(self, tmp_db: Path) -> None:
        """With fewer than 100 total messages, deviation should be NONE."""
        _insert_messages_at_hour(tmp_db, hour=10, count=50)
        detector = CircadianDeviationDetector(tmp_db)
        severity = detector.compute_deviation(current_hour=3)
        assert severity == CircadianDeviationSeverity.NONE

    def test_high_deviation_at_unused_hour(self, tmp_db: Path) -> None:
        """An hour with 0-2 messages should produce HIGH deviation."""
        # Fill hours 8-17 with messages (total > 100)
        for h in range(8, 18):
            _insert_messages_at_hour(tmp_db, hour=h, count=15)
        # Hour 3 has 0 messages
        detector = CircadianDeviationDetector(tmp_db)
        severity = detector.compute_deviation(current_hour=3)
        assert severity == CircadianDeviationSeverity.HIGH

    def test_medium_deviation_at_rare_hour(self, tmp_db: Path) -> None:
        """An hour with 3-9 messages should produce MEDIUM deviation."""
        # Fill normal hours
        for h in range(8, 18):
            _insert_messages_at_hour(tmp_db, hour=h, count=15)
        # Add 5 messages at hour 3 (rare but not unprecedented)
        _insert_messages_at_hour(tmp_db, hour=3, count=5)

        detector = CircadianDeviationDetector(tmp_db)
        severity = detector.compute_deviation(current_hour=3)
        assert severity == CircadianDeviationSeverity.MEDIUM

    def test_low_deviation_at_occasional_hour(self, tmp_db: Path) -> None:
        """An hour with 10-19 messages should produce LOW deviation."""
        for h in range(8, 18):
            _insert_messages_at_hour(tmp_db, hour=h, count=15)
        _insert_messages_at_hour(tmp_db, hour=3, count=12)

        detector = CircadianDeviationDetector(tmp_db)
        severity = detector.compute_deviation(current_hour=3)
        assert severity == CircadianDeviationSeverity.LOW

    def test_no_deviation_at_normal_hour(self, tmp_db: Path) -> None:
        """An hour with 20+ messages should produce NONE deviation."""
        for h in range(8, 18):
            _insert_messages_at_hour(tmp_db, hour=h, count=25)

        detector = CircadianDeviationDetector(tmp_db)
        severity = detector.compute_deviation(current_hour=10)
        assert severity == CircadianDeviationSeverity.NONE

    def test_compute_baseline_returns_correct_hours(
        self, tmp_db: Path
    ) -> None:
        """compute_baseline should return counts for the correct hours."""
        _insert_messages_at_hour(tmp_db, hour=9, count=30)
        _insert_messages_at_hour(tmp_db, hour=14, count=20)

        detector = CircadianDeviationDetector(tmp_db)
        baseline = detector.compute_baseline(days=30)
        assert 9 in baseline
        assert 14 in baseline
        assert baseline[9] == 30
        assert baseline[14] == 20

    def test_get_peak_hours(self, tmp_db: Path) -> None:
        """get_peak_hours should return the most active hours."""
        _insert_messages_at_hour(tmp_db, hour=9, count=50)
        _insert_messages_at_hour(tmp_db, hour=14, count=30)
        _insert_messages_at_hour(tmp_db, hour=20, count=40)

        detector = CircadianDeviationDetector(tmp_db)
        peaks = detector.get_peak_hours(days=30, top_n=2)
        assert peaks[0] == 9   # Most active
        assert peaks[1] == 20  # Second most active


# ---------------------------------------------------------------------------
# Tests: RhythmTracker
# ---------------------------------------------------------------------------

class TestRhythmTracker:
    """Tests for RhythmTracker."""

    def test_empty_tracker(self) -> None:
        """An empty tracker should return zero for all metrics."""
        tracker = RhythmTracker()
        assert tracker.message_count == 0
        assert tracker.get_density() == 0.0
        assert tracker.get_avg_latency() == 0.0
        assert tracker.get_last_latency() == 0.0
        assert tracker.detect_anomaly() is None

    def test_single_message(self) -> None:
        """A single message should have density 1 and no latency."""
        tracker = RhythmTracker()
        tracker.add_message(datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc))
        assert tracker.message_count == 1
        assert tracker.get_density() == 1.0
        assert tracker.get_avg_latency() == 0.0

    def test_density_within_window(self) -> None:
        """Messages within the window should all be counted."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            tracker.add_message(base + timedelta(seconds=30 * i))
        # All 5 messages are within 300 seconds
        density = tracker.get_density(window_seconds=300)
        assert density == 5.0

    def test_density_outside_window(self) -> None:
        """Messages outside the window should not be counted."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        tracker.add_message(base)  # 10 minutes before the last
        tracker.add_message(base + timedelta(minutes=10))
        # Window is 300 seconds (5 min). Only the last message is in window.
        density = tracker.get_density(window_seconds=300)
        assert density == 1.0

    def test_avg_latency_computation(self) -> None:
        """Average latency should be the mean of all consecutive gaps."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        tracker.add_message(base)
        tracker.add_message(base + timedelta(seconds=10))
        tracker.add_message(base + timedelta(seconds=30))
        # Gaps: 10s, 20s → average = 15s
        assert abs(tracker.get_avg_latency() - 15.0) < 1e-9

    def test_sudden_pause_detection(self) -> None:
        """A long gap after rapid messages should trigger 'sudden_pause'."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        # 5 rapid messages (5 seconds apart)
        for i in range(5):
            tracker.add_message(base + timedelta(seconds=5 * i))
        # Then a 60-second pause (12x the 5-second average)
        tracker.add_message(base + timedelta(seconds=80))
        anomaly = tracker.detect_anomaly()
        assert anomaly == "sudden_pause"

    def test_no_anomaly_with_steady_rhythm(self) -> None:
        """Steady rhythm should produce no anomaly."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        for i in range(10):
            tracker.add_message(base + timedelta(seconds=30 * i))
        anomaly = tracker.detect_anomaly()
        assert anomaly is None

    def test_reset_clears_state(self) -> None:
        """reset() should clear all tracked timestamps."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        tracker.add_message(base)
        tracker.add_message(base + timedelta(seconds=10))
        tracker.reset()
        assert tracker.message_count == 0


# ---------------------------------------------------------------------------
# Tests: Autonomy Engine
# ---------------------------------------------------------------------------

class TestTriggerEvaluator:
    """Tests for TriggerEvaluator."""

    def test_morning_greeting_trigger(self) -> None:
        """Should fire when in morning window and user has not messaged."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 8, 0, 0, tzinfo=timezone.utc),
            user_messaged_today=False,
        )
        time_triggers = [t for t in triggers if t["type"] == "time_based"]
        assert len(time_triggers) >= 1
        assert any("Morning" in t["description"] for t in time_triggers)

    def test_no_morning_trigger_if_already_messaged(self) -> None:
        """Should NOT fire morning trigger if user already messaged today."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 8, 0, 0, tzinfo=timezone.utc),
            user_messaged_today=True,
        )
        time_triggers = [t for t in triggers if t["type"] == "time_based"]
        assert len(time_triggers) == 0

    def test_emotional_trigger_low_valence(self) -> None:
        """Should fire emotional trigger when last session had low valence."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
            last_session_closing_valence=0.15,
        )
        emotional = [t for t in triggers if t["type"] == "emotional"]
        assert len(emotional) == 1
        assert emotional[0]["urgency"] == "high"

    def test_no_emotional_trigger_normal_valence(self) -> None:
        """Should NOT fire emotional trigger for normal valence."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
            last_session_closing_valence=0.6,
        )
        emotional = [t for t in triggers if t["type"] == "emotional"]
        assert len(emotional) == 0

    def test_safety_trigger_wellness_checkpoint(self) -> None:
        """Should fire safety trigger when wellness checkpoint is due."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
            wellness_checkpoint_due=True,
        )
        safety = [t for t in triggers if t["type"] == "safety"]
        assert len(safety) >= 1
        assert safety[0]["urgency"] == "high"

    def test_long_absence_trigger(self) -> None:
        """Should fire pattern trigger after 48+ hours of absence."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
            hours_since_last_session=72.0,
        )
        pattern = [t for t in triggers if t["type"] == "pattern_based"]
        assert len(pattern) >= 1


class TestShouldISpeakDecision:
    """Tests for ShouldISpeakDecision."""

    def test_no_triggers_returns_false(self) -> None:
        """No triggers should result in 'do not speak'."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[],
            bond_warmth=0.8,
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
        )
        assert result is False

    def test_safety_trigger_overrides_everything(self) -> None:
        """Safety trigger should result in 'speak' even during quiet hours."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "safety",
                "urgency": "high",
                "description": "Wellness checkpoint due",
            }],
            bond_warmth=0.1,  # Very low warmth
            current_time=datetime(2026, 2, 9, 2, 0, 0, tzinfo=timezone.utc),  # 2am
            quiet_hours_start=23,
            quiet_hours_end=7,
        )
        assert result is True

    def test_quiet_hours_blocks_non_safety(self) -> None:
        """Non-safety triggers during quiet hours should result in 'do not speak'."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "emotional",
                "urgency": "high",
                "description": "Low valence",
            }],
            bond_warmth=0.8,
            current_time=datetime(2026, 2, 9, 2, 0, 0, tzinfo=timezone.utc),  # 2am
            quiet_hours_start=23,
            quiet_hours_end=7,
        )
        assert result is False

    def test_low_warmth_blocks_outreach(self) -> None:
        """Bond warmth < 0.3 should block outreach (too early in relationship)."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "time_based",
                "urgency": "low",
                "description": "Morning greeting",
            }],
            bond_warmth=0.2,
            current_time=datetime(2026, 2, 9, 9, 0, 0, tzinfo=timezone.utc),
        )
        assert result is False

    def test_high_urgency_with_warm_bond(self) -> None:
        """High-urgency trigger + warm bond should result in 'speak'."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "emotional",
                "urgency": "high",
                "description": "Low valence",
            }],
            bond_warmth=0.4,
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
        )
        assert result is True

    def test_warm_bond_with_low_urgency(self) -> None:
        """Low-urgency trigger + warm bond (> 0.5) should result in 'speak'."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "time_based",
                "urgency": "low",
                "description": "Morning greeting",
            }],
            bond_warmth=0.6,
            current_time=datetime(2026, 2, 9, 9, 0, 0, tzinfo=timezone.utc),
        )
        assert result is True

    def test_medium_warmth_low_urgency_does_not_speak(self) -> None:
        """Low-urgency trigger + medium bond (0.3-0.5) should result in 'do not speak'."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "time_based",
                "urgency": "low",
                "description": "Morning greeting",
            }],
            bond_warmth=0.4,
            current_time=datetime(2026, 2, 9, 9, 0, 0, tzinfo=timezone.utc),
        )
        assert result is False

    def test_quiet_hours_spanning_midnight(self) -> None:
        """Quiet hours 23:00-07:00 should correctly handle midnight crossing."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()

        # 23:30 should be in quiet hours
        result_late = decision.decide(
            triggers=[{
                "type": "time_based",
                "urgency": "low",
                "description": "test",
            }],
            bond_warmth=0.8,
            current_time=datetime(2026, 2, 9, 23, 30, 0, tzinfo=timezone.utc),
            quiet_hours_start=23,
            quiet_hours_end=7,
        )
        assert result_late is False

        # 14:00 should NOT be in quiet hours
        result_afternoon = decision.decide(
            triggers=[{
                "type": "time_based",
                "urgency": "low",
                "description": "test",
            }],
            bond_warmth=0.8,
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
            quiet_hours_start=23,
            quiet_hours_end=7,
        )
        assert result_afternoon is True
