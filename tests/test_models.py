"""Tests for gwen.models data structures.

Covers:
- EmotionalStateVector computed properties (storage_strength, is_flashbulb)
- Tier0RawOutput fuzzy field coercion
- MemoryPalimpsest drift bounds and evolution summary

Reference: 002-data-models spec.md Verification Plan
"""

from datetime import datetime, timezone

import pytest

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.classification import Tier0RawOutput
from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TemporalMetadataEnvelope,
    TimePhase,
)
from gwen.models.messages import MessageRecord
from gwen.models.reconsolidation import (
    MemoryPalimpsest,
    ReconsolidationConstraints,
    ReconsolidationLayer,
)


# ---------------------------------------------------------------------------
# Helpers: factory functions for creating test objects
# ---------------------------------------------------------------------------

def make_esv(
    valence: float = 0.5,
    arousal: float = 0.5,
    dominance: float = 0.5,
    relational_significance: float = 0.5,
    vulnerability_level: float = 0.5,
    compass_direction: CompassDirection = CompassDirection.NONE,
    compass_confidence: float = 0.0,
) -> EmotionalStateVector:
    """Create an EmotionalStateVector with sensible defaults."""
    return EmotionalStateVector(
        valence=valence,
        arousal=arousal,
        dominance=dominance,
        relational_significance=relational_significance,
        vulnerability_level=vulnerability_level,
        compass_direction=compass_direction,
        compass_confidence=compass_confidence,
    )


def make_tme() -> TemporalMetadataEnvelope:
    """Create a minimal valid TME for use in MessageRecord tests."""
    now = datetime.now(timezone.utc)
    return TemporalMetadataEnvelope(
        timestamp_utc=now,
        local_time=now,
        hour_of_day=14,
        day_of_week="Wednesday",
        day_of_month=9,
        month=2,
        year=2026,
        is_weekend=False,
        time_phase=TimePhase.AFTERNOON,
        session_id="test-session-001",
        session_start=now,
        session_duration_sec=300,
        msg_index_in_session=0,
        time_since_last_msg_sec=None,
        time_since_last_user_msg_sec=None,
        time_since_last_gwen_msg_sec=None,
        user_msgs_last_5min=1,
        user_msgs_last_hour=1,
        user_msgs_last_24hr=1,
        last_session_end=None,
        hours_since_last_session=None,
        sessions_last_7_days=0,
        sessions_last_30_days=0,
        avg_session_gap_30d_hours=None,
        circadian_deviation_severity=CircadianDeviationSeverity.NONE,
        circadian_deviation_type=None,
    )


def make_message_record(
    valence: float = 0.5,
    arousal: float = 0.5,
    relational_significance: float = 0.5,
) -> MessageRecord:
    """Create a minimal valid MessageRecord for palimpsest tests."""
    esv = make_esv(
        valence=valence,
        arousal=arousal,
        relational_significance=relational_significance,
    )
    return MessageRecord(
        id="msg-001",
        session_id="session-001",
        timestamp=datetime.now(timezone.utc),
        sender="user",
        content="Test message",
        tme=make_tme(),
        emotional_state=esv,
        storage_strength=esv.storage_strength,
        is_flashbulb=esv.is_flashbulb,
        compass_direction=CompassDirection.NONE,
        compass_skill_used=None,
    )


def make_layer(
    valence_delta: float = 0.0,
    arousal_delta: float = 0.0,
    significance_delta: float = 0.0,
    timestamp: datetime | None = None,
) -> ReconsolidationLayer:
    """Create a ReconsolidationLayer with sensible defaults."""
    return ReconsolidationLayer(
        id="layer-001",
        timestamp=timestamp or datetime.now(timezone.utc),
        recall_session_id="recall-session-001",
        user_emotional_state_at_recall=make_esv(),
        conversation_topic_at_recall="test topic",
        reaction_type="warmth",
        reaction_detail="User smiled when recalling this.",
        valence_delta=valence_delta,
        arousal_delta=arousal_delta,
        significance_delta=significance_delta,
        narrative="Test narrative",
    )


# ---------------------------------------------------------------------------
# Test: EmotionalStateVector computed properties
# ---------------------------------------------------------------------------

class TestEmotionalStateVector:
    """Tests for EmotionalStateVector.storage_strength and .is_flashbulb."""

    def test_storage_strength_formula(self) -> None:
        """storage_strength = arousal*0.4 + relational_significance*0.4 + vulnerability*0.2"""
        esv = make_esv(arousal=0.9, relational_significance=0.9, vulnerability_level=0.3)
        expected = 0.9 * 0.4 + 0.9 * 0.4 + 0.3 * 0.2  # = 0.78
        assert abs(esv.storage_strength - expected) < 1e-9

    def test_storage_strength_zeros(self) -> None:
        """All zeros should produce storage_strength of 0.0."""
        esv = make_esv(arousal=0.0, relational_significance=0.0, vulnerability_level=0.0)
        assert esv.storage_strength == 0.0

    def test_storage_strength_ones(self) -> None:
        """All ones should produce storage_strength of 1.0."""
        esv = make_esv(arousal=1.0, relational_significance=1.0, vulnerability_level=1.0)
        expected = 1.0 * 0.4 + 1.0 * 0.4 + 1.0 * 0.2  # = 1.0
        assert abs(esv.storage_strength - expected) < 1e-9

    def test_storage_strength_mixed(self) -> None:
        """A typical mixed-value case."""
        esv = make_esv(arousal=0.5, relational_significance=0.3, vulnerability_level=0.7)
        expected = 0.5 * 0.4 + 0.3 * 0.4 + 0.7 * 0.2  # = 0.20 + 0.12 + 0.14 = 0.46
        assert abs(esv.storage_strength - expected) < 1e-9

    def test_is_flashbulb_both_above_threshold(self) -> None:
        """Flashbulb requires BOTH arousal > 0.8 AND relational_significance > 0.8."""
        esv = make_esv(arousal=0.85, relational_significance=0.90)
        assert esv.is_flashbulb is True

    def test_is_flashbulb_arousal_below(self) -> None:
        """Arousal at 0.8 exactly should NOT trigger flashbulb (must be > 0.8)."""
        esv = make_esv(arousal=0.8, relational_significance=0.9)
        assert esv.is_flashbulb is False

    def test_is_flashbulb_significance_below(self) -> None:
        """Significance at 0.8 exactly should NOT trigger flashbulb (must be > 0.8)."""
        esv = make_esv(arousal=0.9, relational_significance=0.8)
        assert esv.is_flashbulb is False

    def test_is_flashbulb_both_at_boundary(self) -> None:
        """Both at exactly 0.8 should NOT trigger flashbulb."""
        esv = make_esv(arousal=0.8, relational_significance=0.8)
        assert esv.is_flashbulb is False

    def test_is_flashbulb_low_values(self) -> None:
        """Low values should not be flashbulb."""
        esv = make_esv(arousal=0.3, relational_significance=0.2)
        assert esv.is_flashbulb is False


# ---------------------------------------------------------------------------
# Test: Tier0RawOutput fuzzy coercion
# ---------------------------------------------------------------------------

class TestTier0RawOutput:
    """Tests for Tier0RawOutput field validators (fuzzy coercion)."""

    # --- Valence coercion ---

    def test_valence_exact_match(self) -> None:
        """Exact canonical values pass through unchanged."""
        result = Tier0RawOutput(valence="very_negative", arousal="low")
        assert result.valence == "very_negative"

    def test_valence_space_to_underscore(self) -> None:
        """'very negative' (with space) coerces to 'very_negative'."""
        result = Tier0RawOutput(valence="very negative", arousal="low")
        assert result.valence == "very_negative"

    def test_valence_abbreviation_neg(self) -> None:
        """'neg' coerces to 'negative'."""
        result = Tier0RawOutput(valence="neg", arousal="low")
        assert result.valence == "negative"

    def test_valence_abbreviation_neu(self) -> None:
        """'neu' coerces to 'neutral'."""
        result = Tier0RawOutput(valence="neu", arousal="low")
        assert result.valence == "neutral"

    def test_valence_abbreviation_neut(self) -> None:
        """'neut' coerces to 'neutral'."""
        result = Tier0RawOutput(valence="neut", arousal="low")
        assert result.valence == "neutral"

    def test_valence_abbreviation_pos(self) -> None:
        """'pos' coerces to 'positive'."""
        result = Tier0RawOutput(valence="pos", arousal="low")
        assert result.valence == "positive"

    def test_valence_abbreviation_very_pos(self) -> None:
        """'very_pos' coerces to 'very_positive'."""
        result = Tier0RawOutput(valence="very_pos", arousal="low")
        assert result.valence == "very_positive"

    def test_valence_very_positive_with_space(self) -> None:
        """'very positive' (with space) coerces to 'very_positive'."""
        result = Tier0RawOutput(valence="very positive", arousal="low")
        assert result.valence == "very_positive"

    def test_valence_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped."""
        result = Tier0RawOutput(valence="  neutral  ", arousal="low")
        assert result.valence == "neutral"

    def test_valence_case_insensitive(self) -> None:
        """Coercion is case-insensitive."""
        result = Tier0RawOutput(valence="NEGATIVE", arousal="low")
        assert result.valence == "negative"

    # --- Arousal coercion ---

    def test_arousal_exact_match(self) -> None:
        """Exact canonical values pass through unchanged."""
        result = Tier0RawOutput(valence="neutral", arousal="moderate")
        assert result.arousal == "moderate"

    def test_arousal_med_to_moderate(self) -> None:
        """'med' coerces to 'moderate'."""
        result = Tier0RawOutput(valence="neutral", arousal="med")
        assert result.arousal == "moderate"

    def test_arousal_medium_to_moderate(self) -> None:
        """'medium' coerces to 'moderate'."""
        result = Tier0RawOutput(valence="neutral", arousal="medium")
        assert result.arousal == "moderate"

    def test_arousal_hi_to_high(self) -> None:
        """'hi' coerces to 'high'."""
        result = Tier0RawOutput(valence="neutral", arousal="hi")
        assert result.arousal == "high"

    def test_arousal_lo_to_low(self) -> None:
        """'lo' coerces to 'low'."""
        result = Tier0RawOutput(valence="neutral", arousal="lo")
        assert result.arousal == "low"

    def test_arousal_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped."""
        result = Tier0RawOutput(valence="neutral", arousal="  high  ")
        assert result.arousal == "high"

    def test_arousal_case_insensitive(self) -> None:
        """Coercion is case-insensitive."""
        result = Tier0RawOutput(valence="neutral", arousal="HIGH")
        assert result.arousal == "high"

    # --- Default fields ---

    def test_default_topic(self) -> None:
        """topic defaults to 'unknown'."""
        result = Tier0RawOutput(valence="neutral", arousal="low")
        assert result.topic == "unknown"

    def test_default_safety_keywords(self) -> None:
        """safety_keywords defaults to empty list."""
        result = Tier0RawOutput(valence="neutral", arousal="low")
        assert result.safety_keywords == []

    def test_custom_topic_and_keywords(self) -> None:
        """Custom topic and safety_keywords are preserved."""
        result = Tier0RawOutput(
            valence="negative",
            arousal="high",
            topic="work_stress",
            safety_keywords=["overwhelmed", "can't cope"],
        )
        assert result.topic == "work_stress"
        assert result.safety_keywords == ["overwhelmed", "can't cope"]


# ---------------------------------------------------------------------------
# Test: MemoryPalimpsest drift bounds
# ---------------------------------------------------------------------------

class TestMemoryPalimpsest:
    """Tests for MemoryPalimpsest computed properties and drift enforcement."""

    def test_no_layers_returns_archive_values(self) -> None:
        """With no reconsolidation layers, current values match the archive."""
        record = make_message_record(valence=0.6, arousal=0.4, relational_significance=0.5)
        palimpsest = MemoryPalimpsest(archive=record)
        assert palimpsest.current_valence == 0.6
        assert palimpsest.current_arousal == 0.4
        assert palimpsest.current_significance == 0.5

    def test_single_layer_applies_delta(self) -> None:
        """A single layer shifts the values by its deltas."""
        record = make_message_record(valence=0.5, arousal=0.5, relational_significance=0.5)
        layer = make_layer(valence_delta=0.05, arousal_delta=-0.03, significance_delta=0.02)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer])
        assert abs(palimpsest.current_valence - 0.55) < 1e-9
        assert abs(palimpsest.current_arousal - 0.47) < 1e-9
        assert abs(palimpsest.current_significance - 0.52) < 1e-9

    def test_multiple_layers_accumulate(self) -> None:
        """Multiple layers accumulate their deltas."""
        record = make_message_record(valence=0.5, arousal=0.5, relational_significance=0.5)
        layer1 = make_layer(valence_delta=0.05, arousal_delta=0.05, significance_delta=0.02)
        layer2 = make_layer(valence_delta=0.05, arousal_delta=0.05, significance_delta=0.02)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer1, layer2])
        assert abs(palimpsest.current_valence - 0.6) < 1e-9
        assert abs(palimpsest.current_arousal - 0.6) < 1e-9
        assert abs(palimpsest.current_significance - 0.54) < 1e-9

    def test_drift_clamped_to_max_total(self) -> None:
        """Total drift cannot exceed MAX_TOTAL_DRIFT (0.50 by default)."""
        record = make_message_record(valence=0.5, arousal=0.5, relational_significance=0.5)
        # Create 10 layers each pushing valence up by 0.10 = total 1.0, but clamped to 0.50
        layers = [make_layer(valence_delta=0.10) for _ in range(10)]
        palimpsest = MemoryPalimpsest(archive=record, layers=layers)
        # 0.5 + 0.50 (clamped) = 1.0
        assert abs(palimpsest.current_valence - 1.0) < 1e-9

    def test_drift_clamped_negative_direction(self) -> None:
        """Negative drift is also clamped to MAX_TOTAL_DRIFT."""
        record = make_message_record(valence=0.5, arousal=0.5, relational_significance=0.5)
        layers = [make_layer(valence_delta=-0.10) for _ in range(10)]
        palimpsest = MemoryPalimpsest(archive=record, layers=layers)
        # 0.5 + (-0.50 clamped) = 0.0
        assert abs(palimpsest.current_valence - 0.0) < 1e-9

    def test_valence_never_below_zero(self) -> None:
        """Even with drift, valence is clamped to [0.0, 1.0]."""
        record = make_message_record(valence=0.1, arousal=0.5, relational_significance=0.5)
        layers = [make_layer(valence_delta=-0.10) for _ in range(5)]
        palimpsest = MemoryPalimpsest(archive=record, layers=layers)
        # 0.1 + (-0.50 clamped) = -0.4, clamped to 0.0
        assert palimpsest.current_valence == 0.0

    def test_valence_never_above_one(self) -> None:
        """Even with drift, valence is clamped to [0.0, 1.0]."""
        record = make_message_record(valence=0.9, arousal=0.5, relational_significance=0.5)
        layers = [make_layer(valence_delta=0.10) for _ in range(5)]
        palimpsest = MemoryPalimpsest(archive=record, layers=layers)
        # 0.9 + 0.50 (clamped) = 1.4, clamped to 1.0
        assert palimpsest.current_valence == 1.0

    def test_current_reading_preserves_other_dimensions(self) -> None:
        """current_reading() preserves dominance, vulnerability, compass from archive."""
        esv = make_esv(
            valence=0.5,
            arousal=0.5,
            dominance=0.7,
            relational_significance=0.5,
            vulnerability_level=0.3,
            compass_direction=CompassDirection.SOUTH,
            compass_confidence=0.85,
        )
        record = MessageRecord(
            id="msg-002",
            session_id="session-002",
            timestamp=datetime.now(timezone.utc),
            sender="user",
            content="Test",
            tme=make_tme(),
            emotional_state=esv,
            storage_strength=esv.storage_strength,
            is_flashbulb=esv.is_flashbulb,
            compass_direction=CompassDirection.SOUTH,
            compass_skill_used=None,
        )
        layer = make_layer(valence_delta=0.05)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer])
        reading = palimpsest.current_reading()
        assert reading.dominance == 0.7
        assert reading.vulnerability_level == 0.3
        assert reading.compass_direction == CompassDirection.SOUTH
        assert reading.compass_confidence == 0.85

    def test_reading_at_filters_by_time(self) -> None:
        """reading_at() only applies layers before the given timestamp."""
        record = make_message_record(valence=0.5, arousal=0.5, relational_significance=0.5)
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 2, 1, tzinfo=timezone.utc)
        t3 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        layer1 = make_layer(valence_delta=0.05, timestamp=t1)
        layer2 = make_layer(valence_delta=0.05, timestamp=t2)
        layer3 = make_layer(valence_delta=0.05, timestamp=t3)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer1, layer2, layer3])

        # At t1: only layer1 applied
        reading_t1 = palimpsest.reading_at(t1)
        assert abs(reading_t1.valence - 0.55) < 1e-9

        # At t2: layers 1 and 2 applied
        reading_t2 = palimpsest.reading_at(t2)
        assert abs(reading_t2.valence - 0.60) < 1e-9

        # At t3: all three layers applied
        reading_t3 = palimpsest.reading_at(t3)
        assert abs(reading_t3.valence - 0.65) < 1e-9

    def test_evolution_summary_no_layers(self) -> None:
        """evolution_summary() with no layers returns the 'no reconsolidation' message."""
        record = make_message_record(valence=0.5)
        palimpsest = MemoryPalimpsest(archive=record)
        summary = palimpsest.evolution_summary()
        assert "No reconsolidation" in summary

    def test_evolution_summary_with_layers(self) -> None:
        """evolution_summary() describes the drift direction and layer count."""
        record = make_message_record(valence=0.5)
        layer = make_layer(valence_delta=0.05)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer])
        summary = palimpsest.evolution_summary()
        assert "1 time(s)" in summary
        assert "more positive" in summary
        assert "warmth" in summary  # reaction_type from make_layer

    def test_evolution_summary_negative_drift(self) -> None:
        """evolution_summary() reports 'more negative' when valence decreases."""
        record = make_message_record(valence=0.5)
        layer = make_layer(valence_delta=-0.05)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer])
        summary = palimpsest.evolution_summary()
        assert "more negative" in summary

    def test_custom_constraints(self) -> None:
        """Custom ReconsolidationConstraints override defaults."""
        constraints = ReconsolidationConstraints(
            MAX_DELTA_PER_LAYER=0.05,
            MAX_TOTAL_DRIFT=0.20,
            MIN_LAYERS_FOR_TREND=5,
            COOLDOWN_HOURS=48.0,
        )
        record = make_message_record(valence=0.5)
        layers = [make_layer(valence_delta=0.10) for _ in range(5)]
        palimpsest = MemoryPalimpsest(
            archive=record, layers=layers, constraints=constraints
        )
        # Total delta = 5 * 0.10 = 0.50, but clamped to 0.20 by custom constraints
        assert abs(palimpsest.current_valence - 0.7) < 1e-9
