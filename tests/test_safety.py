"""Tests for the Safety Architecture — threat detection and encrypted ledger.

Run with:
    pytest tests/test_safety.py -v
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest
from cryptography.fernet import Fernet

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.safety import SafetyEvent, ThreatSeverity, ThreatVector, WellnessCheckpoint
from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TemporalMetadataEnvelope,
    TimePhase,
)
from gwen.safety.ledger import SafetyLedger, _get_or_create_key
from gwen.safety.monitor import (
    SEVERITY_TO_ACTION,
    THREAT_BASE_SEVERITY,
    THREAT_TO_COMPASS,
    SafetyMonitor,
    SafetyResult,
    _severity_index,
)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

def _make_emotional_state(**overrides) -> EmotionalStateVector:
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


def _make_tme(
    time_phase: TimePhase = TimePhase.MORNING,
    circadian_deviation: CircadianDeviationSeverity = CircadianDeviationSeverity.NONE,
    session_duration_sec: int = 600,
) -> TemporalMetadataEnvelope:
    now = datetime.utcnow()
    return TemporalMetadataEnvelope(
        timestamp_utc=now,
        local_time=now,
        hour_of_day=10,
        day_of_week="Monday",
        day_of_month=9,
        month=2,
        year=2026,
        is_weekend=False,
        time_phase=time_phase,
        session_id="test-session",
        session_start=now - timedelta(seconds=session_duration_sec),
        session_duration_sec=session_duration_sec,
        msg_index_in_session=5,
        time_since_last_msg_sec=10.0,
        time_since_last_user_msg_sec=10.0,
        time_since_last_gwen_msg_sec=5.0,
        user_msgs_last_5min=3,
        user_msgs_last_hour=20,
        user_msgs_last_24hr=50,
        last_session_end=now - timedelta(hours=12),
        hours_since_last_session=12.0,
        sessions_last_7_days=5,
        sessions_last_30_days=20,
        avg_session_gap_30d_hours=14.0,
        circadian_deviation_severity=circadian_deviation,
        circadian_deviation_type=None,
    )


def _make_safety_event(
    vector: ThreatVector = ThreatVector.SELF_HARM,
    severity: ThreatSeverity = ThreatSeverity.MEDIUM,
    days_ago: float = 1.0,
) -> SafetyEvent:
    return SafetyEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow() - timedelta(days=days_ago),
        vector=vector,
        severity=severity,
        trigger_message_id=None,
        trigger_description="test event",
        time_phase=TimePhase.MORNING,
        session_duration_sec=600,
        circadian_deviation=CircadianDeviationSeverity.NONE,
        response_action="monitor",
        compass_direction_used=None,
        user_response=None,
        resolved=False,
    )


def _make_wellness_checkpoint() -> WellnessCheckpoint:
    return WellnessCheckpoint(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        immersion_hours_since_last=48.0,
        q1_last_human_conversation="Yesterday at lunch",
        q2_life_outside_gwen="Doing okay, work is busy",
        q3_avoiding_anything="Not really",
        concern_flags=[],
        escalated=False,
    )


@pytest.fixture()
def tmp_ledger(tmp_path: Path) -> SafetyLedger:
    ledger_path = tmp_path / "test_ledger.enc"
    return SafetyLedger(
        ledger_path=str(ledger_path),
        key_path=str(tmp_path / "test_key"),
    )


@pytest.fixture()
def monitor(tmp_ledger: SafetyLedger) -> SafetyMonitor:
    return SafetyMonitor(ledger=tmp_ledger)


# ---------------------------------------------------------------------------
# Tests: SafetyResult
# ---------------------------------------------------------------------------

class TestSafetyResult:

    def test_default_values(self) -> None:
        result = SafetyResult()
        assert result.severity == ThreatSeverity.LOW
        assert result.flags == []
        assert result.recommended_action == "none"
        assert result.compass_direction is None
        assert result.requires_overlay is False


# ---------------------------------------------------------------------------
# Tests: SafetyMonitor.evaluate()
# ---------------------------------------------------------------------------

class TestSafetyMonitorEvaluate:

    def test_no_flags_returns_no_threat(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=[],
        )
        assert result.recommended_action == "none"
        assert result.flags == []

    def test_unrecognized_flag_ignored(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["not_a_real_flag"],
        )
        assert result.recommended_action == "none"
        assert result.flags == []

    def test_self_harm_detected(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
        )
        assert ThreatVector.SELF_HARM in result.flags
        assert result.severity == ThreatSeverity.MEDIUM
        assert result.recommended_action == "compass_activation"

    def test_violence_detected(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["violence"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
        )
        assert ThreatVector.VIOLENCE in result.flags
        assert result.severity == ThreatSeverity.MEDIUM

    def test_dissociation_detected(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["dissociation"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
        )
        assert ThreatVector.DISSOCIATION in result.flags
        assert result.severity == ThreatSeverity.LOW

    def test_savior_delusion_detected(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["savior_delusion"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
        )
        assert ThreatVector.SAVIOR_DELUSION in result.flags
        assert result.severity == ThreatSeverity.LOW

    def test_self_harm_compass_is_west(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
        )
        assert result.compass_direction == CompassDirection.WEST

    def test_violence_compass_is_south(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["violence"],
        )
        assert result.compass_direction == CompassDirection.SOUTH

    def test_dissociation_compass_is_north(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["dissociation"],
        )
        assert result.compass_direction == CompassDirection.NORTH


# ---------------------------------------------------------------------------
# Tests: Severity Escalation
# ---------------------------------------------------------------------------

class TestSeverityEscalation:

    def test_temporal_boost_deep_night(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.DEEP_NIGHT),
        )
        assert result.severity == ThreatSeverity.HIGH
        assert result.recommended_action == "safety_protocol"

    def test_temporal_boost_late_night(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.LATE_NIGHT),
        )
        assert result.severity == ThreatSeverity.HIGH

    def test_no_temporal_boost_morning(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
        )
        assert result.severity == ThreatSeverity.MEDIUM

    def test_historical_boost(self, monitor: SafetyMonitor) -> None:
        recent_events = [
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=1),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=2),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
            recent_events=recent_events,
        )
        assert result.severity == ThreatSeverity.HIGH

    def test_no_historical_boost_different_vector(self, monitor: SafetyMonitor) -> None:
        recent_events = [
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=1),
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=2),
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
            recent_events=recent_events,
        )
        assert result.severity == ThreatSeverity.MEDIUM

    def test_circadian_deviation_boost(self, monitor: SafetyMonitor) -> None:
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(
                time_phase=TimePhase.MORNING,
                circadian_deviation=CircadianDeviationSeverity.HIGH,
            ),
        )
        assert result.severity == ThreatSeverity.HIGH

    def test_multiple_boosts_stack(self, monitor: SafetyMonitor) -> None:
        recent_events = [
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=1),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=2),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.DEEP_NIGHT),
            recent_events=recent_events,
        )
        assert result.severity == ThreatSeverity.CRITICAL

    def test_severity_capped_at_critical(self, monitor: SafetyMonitor) -> None:
        recent_events = [
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=1),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=2),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(
                time_phase=TimePhase.DEEP_NIGHT,
                circadian_deviation=CircadianDeviationSeverity.HIGH,
            ),
            recent_events=recent_events,
        )
        assert result.severity == ThreatSeverity.CRITICAL

    def test_critical_self_harm_requires_overlay(self, monitor: SafetyMonitor) -> None:
        recent_events = [
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=1),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=2),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.DEEP_NIGHT),
            recent_events=recent_events,
        )
        assert result.severity == ThreatSeverity.CRITICAL
        assert result.requires_overlay is True

    def test_critical_violence_no_overlay(self, monitor: SafetyMonitor) -> None:
        recent_events = [
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=1),
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=2),
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["violence"],
            tme=_make_tme(time_phase=TimePhase.DEEP_NIGHT),
            recent_events=recent_events,
        )
        assert result.severity == ThreatSeverity.CRITICAL
        assert result.requires_overlay is False


# ---------------------------------------------------------------------------
# Tests: Safety Ledger
# ---------------------------------------------------------------------------

class TestSafetyLedger:

    def test_key_generation(self, tmp_path: Path) -> None:
        key_path = tmp_path / "test_key"
        key = _get_or_create_key(key_path)
        assert key_path.exists()
        f = Fernet(key)
        assert f is not None

    def test_key_persistence(self, tmp_path: Path) -> None:
        key_path = tmp_path / "test_key"
        key1 = _get_or_create_key(key_path)
        key2 = _get_or_create_key(key_path)
        assert key1 == key2

    def test_log_and_read_safety_event(self, tmp_ledger: SafetyLedger) -> None:
        event = _make_safety_event()
        tmp_ledger.log_event(event)

        entries = tmp_ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "safety_event"
        assert entries[0]["vector"] == event.vector.value
        assert entries[0]["severity"] == event.severity.value

    def test_log_and_read_wellness_checkpoint(self, tmp_ledger: SafetyLedger) -> None:
        checkpoint = _make_wellness_checkpoint()
        tmp_ledger.log_checkpoint(checkpoint)

        entries = tmp_ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "wellness_checkpoint"
        assert entries[0]["q1_last_human_conversation"] == checkpoint.q1_last_human_conversation

    def test_log_and_read_mode_change(self, tmp_ledger: SafetyLedger) -> None:
        now = datetime.utcnow()
        tmp_ledger.log_mode_change("grounded", "immersion", now)

        entries = tmp_ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "mode_change"
        assert entries[0]["from_mode"] == "grounded"
        assert entries[0]["to_mode"] == "immersion"

    def test_append_only_multiple_entries(self, tmp_ledger: SafetyLedger) -> None:
        event1 = _make_safety_event(vector=ThreatVector.SELF_HARM)
        event2 = _make_safety_event(vector=ThreatVector.VIOLENCE)
        checkpoint = _make_wellness_checkpoint()

        tmp_ledger.log_event(event1)
        tmp_ledger.log_event(event2)
        tmp_ledger.log_checkpoint(checkpoint)

        entries = tmp_ledger.read_all()
        assert len(entries) == 3
        assert entries[0]["vector"] == "self_harm"
        assert entries[1]["vector"] == "violence"
        assert entries[2]["entry_type"] == "wellness_checkpoint"

    def test_no_delete_method(self, tmp_ledger: SafetyLedger) -> None:
        assert not hasattr(tmp_ledger, "delete")
        assert not hasattr(tmp_ledger, "delete_event")
        assert not hasattr(tmp_ledger, "delete_entry")
        assert not hasattr(tmp_ledger, "remove")
        assert not hasattr(tmp_ledger, "clear")

    def test_empty_ledger_returns_empty_list(self, tmp_ledger: SafetyLedger) -> None:
        entries = tmp_ledger.read_all()
        assert entries == []

    def test_encryption_roundtrip(self, tmp_ledger: SafetyLedger) -> None:
        event = _make_safety_event()
        tmp_ledger.log_event(event)

        entries = tmp_ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["id"] == event.id
        assert entries[0]["trigger_description"] == event.trigger_description

    def test_ledger_file_is_encrypted(self, tmp_ledger: SafetyLedger) -> None:
        event_with_unique_text = SafetyEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            vector=ThreatVector.SELF_HARM,
            severity=ThreatSeverity.HIGH,
            trigger_message_id=None,
            trigger_description="UNIQUE_PLAINTEXT_MARKER_12345",
            time_phase=TimePhase.MORNING,
            session_duration_sec=600,
            circadian_deviation=CircadianDeviationSeverity.NONE,
            response_action="safety_protocol",
            compass_direction_used=CompassDirection.WEST,
            user_response=None,
            resolved=False,
        )
        tmp_ledger.log_event(event_with_unique_text)

        raw_content = tmp_ledger.ledger_path.read_bytes()
        assert b"UNIQUE_PLAINTEXT_MARKER_12345" not in raw_content

    def test_export_plaintext(self, tmp_ledger: SafetyLedger, tmp_path: Path) -> None:
        event = _make_safety_event()
        tmp_ledger.log_event(event)

        export_path = tmp_path / "export.txt"
        tmp_ledger.export_plaintext(str(export_path))

        assert export_path.exists()
        content = export_path.read_text(encoding="utf-8")
        assert "GWEN SAFETY LEDGER EXPORT" in content
        assert "safety_event" in content
        assert "Total entries: 1" in content
        assert "END OF EXPORT" in content

    def test_export_plaintext_with_all_types(
        self, tmp_ledger: SafetyLedger, tmp_path: Path
    ) -> None:
        tmp_ledger.log_event(_make_safety_event())
        tmp_ledger.log_checkpoint(_make_wellness_checkpoint())
        tmp_ledger.log_mode_change("grounded", "immersion", datetime.utcnow())

        export_path = tmp_path / "export_all.txt"
        tmp_ledger.export_plaintext(str(export_path))

        content = export_path.read_text(encoding="utf-8")
        assert "safety_event" in content
        assert "wellness_checkpoint" in content
        assert "mode_change" in content
        assert "Total entries: 3" in content


# ---------------------------------------------------------------------------
# Tests: Monitor logs events to ledger
# ---------------------------------------------------------------------------

class TestMonitorLedgerIntegration:

    def test_evaluate_logs_to_ledger(
        self, tmp_ledger: SafetyLedger, monitor: SafetyMonitor
    ) -> None:
        monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
        )

        entries = tmp_ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "safety_event"
        assert entries[0]["vector"] == "self_harm"

    def test_no_flags_no_log(
        self, tmp_ledger: SafetyLedger, monitor: SafetyMonitor
    ) -> None:
        monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=[],
        )

        entries = tmp_ledger.read_all()
        assert len(entries) == 0


# ---------------------------------------------------------------------------
# Tests: Severity index helper
# ---------------------------------------------------------------------------

class TestSeverityIndex:

    def test_ordering(self) -> None:
        assert _severity_index(ThreatSeverity.LOW) == 0
        assert _severity_index(ThreatSeverity.MEDIUM) == 1
        assert _severity_index(ThreatSeverity.HIGH) == 2
        assert _severity_index(ThreatSeverity.CRITICAL) == 3
