"""Tests for ClassificationRuleEngine — deterministic emotional dimension computation.

These tests verify that the Rule Engine correctly computes vulnerability, dominance,
relational significance, compass direction, intent, and safety flags from Tier 0 output.
"""

from __future__ import annotations

from dataclasses import dataclass

from gwen.classification.rule_engine import ClassificationRuleEngine
from gwen.models.classification import Tier0RawOutput
from gwen.models.emotional import CompassDirection
from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TimePhase,
)


# ---------------------------------------------------------------------------
# Stub TME for testing (avoids depending on the full TME class from Track 006)
# ---------------------------------------------------------------------------

@dataclass
class StubTME:
    """Minimal TME stub with only the fields the Rule Engine reads."""
    time_phase: TimePhase = TimePhase.AFTERNOON
    circadian_deviation_severity: CircadianDeviationSeverity = (
        CircadianDeviationSeverity.NONE
    )


def _make_tme(
    phase: TimePhase = TimePhase.AFTERNOON,
    deviation: CircadianDeviationSeverity = CircadianDeviationSeverity.NONE,
) -> StubTME:
    return StubTME(time_phase=phase, circadian_deviation_severity=deviation)


def _make_raw(
    valence: str = "neutral",
    arousal: str = "moderate",
    topic: str = "general",
    safety_keywords: list[str] | None = None,
) -> Tier0RawOutput:
    return Tier0RawOutput(
        valence=valence,
        arousal=arousal,
        topic=topic,
        safety_keywords=safety_keywords or [],
    )


# ===========================================================================
# Vulnerability Tests
# ===========================================================================

class TestComputeVulnerability:

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_baseline_no_factors(self) -> None:
        tme = _make_tme(phase=TimePhase.AFTERNOON)
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, "hey what's up")
        assert score == 0.0

    def test_deep_night_boost(self) -> None:
        tme = _make_tme(phase=TimePhase.DEEP_NIGHT)
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, "hey what's up")
        assert abs(score - 0.15) < 0.001

    def test_late_night_boost(self) -> None:
        tme = _make_tme(phase=TimePhase.LATE_NIGHT)
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, "hey what's up")
        assert abs(score - 0.15) < 0.001

    def test_circadian_deviation_medium(self) -> None:
        tme = _make_tme(deviation=CircadianDeviationSeverity.MEDIUM)
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, "hey")
        assert abs(score - 0.1) < 0.001

    def test_very_negative_valence(self) -> None:
        tme = _make_tme()
        score = self.engine._compute_vulnerability(0.1, 0.5, tme, "hey")
        assert abs(score - 0.2) < 0.001

    def test_high_arousal(self) -> None:
        tme = _make_tme()
        score = self.engine._compute_vulnerability(0.5, 0.8, tme, "hey")
        assert abs(score - 0.15) < 0.001

    def test_disclosure_keywords(self) -> None:
        tme = _make_tme()
        msg = "I'm afraid and scared of what's happening"
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, msg)
        assert abs(score - 0.2) < 0.001

    def test_disclosure_keywords_cap(self) -> None:
        tme = _make_tme()
        msg = "I'm afraid, ashamed, scared, and I admit I can't cope and I'm breaking down"
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, msg)
        assert abs(score - 0.3) < 0.001

    def test_long_distress_message(self) -> None:
        tme = _make_tme()
        long_msg = "I just don't know what to do anymore. " * 10
        score = self.engine._compute_vulnerability(0.3, 0.5, tme, long_msg)
        # valence=0.3 is NOT < 0.3, so no valence boost
        # valence=0.3 IS < 0.4, so long message boost applies
        # disclosure: "don't know what to do" matches -> 0.1
        # long message: 0.1
        assert abs(score - 0.2) < 0.001

    def test_combined_max_vulnerability(self) -> None:
        tme = _make_tme(
            phase=TimePhase.DEEP_NIGHT,
            deviation=CircadianDeviationSeverity.HIGH,
        )
        msg = (
            "I'm afraid and ashamed and scared and I can't cope "
            "and I'm falling apart and breaking down. "
        ) * 3
        score = self.engine._compute_vulnerability(0.1, 0.8, tme, msg)
        assert abs(score - 1.0) < 0.001


# ===========================================================================
# Dominance Tests
# ===========================================================================

class TestComputeDominance:

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_positive_low_arousal_daytime(self) -> None:
        tme = _make_tme()
        score = self.engine._compute_dominance(0.7, 0.2, tme)
        assert abs(score - 0.79) < 0.01

    def test_negative_high_arousal_night(self) -> None:
        tme = _make_tme(phase=TimePhase.DEEP_NIGHT)
        score = self.engine._compute_dominance(0.1, 0.8, tme)
        assert abs(score - 0.21) < 0.01

    def test_clamp_at_zero(self) -> None:
        tme = _make_tme(phase=TimePhase.DEEP_NIGHT)
        score = self.engine._compute_dominance(0.0, 1.0, tme)
        assert score >= 0.0


# ===========================================================================
# Compass Direction Tests
# ===========================================================================

class TestComputeCompass:

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_west_acute_distress(self) -> None:
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.1, 0.8, "panic", [], tme,
        )
        assert direction == CompassDirection.WEST
        assert confidence == 0.8

    def test_south_emotional_processing(self) -> None:
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.3, 0.5, "sadness", [], tme,
        )
        assert direction == CompassDirection.SOUTH
        assert confidence == 0.7

    def test_north_dissociation(self) -> None:
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.3, 0.2, "numb", [], tme,
        )
        assert direction == CompassDirection.NORTH
        assert confidence == 0.7

    def test_east_relational_topic(self) -> None:
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.5, 0.5, "family_conflict", [], tme,
        )
        assert direction == CompassDirection.EAST
        assert confidence == 0.6

    def test_east_relational_keyword(self) -> None:
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.5, 0.5, "general", ["lonely"], tme,
        )
        assert direction == CompassDirection.EAST
        assert confidence == 0.5

    def test_none_casual(self) -> None:
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.5, 0.5, "weather", [], tme,
        )
        assert direction == CompassDirection.NONE
        assert confidence == 0.0

    def test_west_takes_priority_over_south(self) -> None:
        tme = _make_tme()
        direction, _ = self.engine._compute_compass(0.1, 0.8, "crisis", [], tme)
        assert direction == CompassDirection.WEST


# ===========================================================================
# Intent Tests
# ===========================================================================

class TestComputeIntent:

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_question(self) -> None:
        intent = self.engine._compute_intent("How are you doing?", "chat", 0.5, 0.1)
        assert intent == "asking_question"

    def test_seeking_support(self) -> None:
        intent = self.engine._compute_intent(
            "I just feel so lost", "personal", 0.5, 0.7,
        )
        assert intent == "seeking_support"

    def test_venting(self) -> None:
        intent = self.engine._compute_intent(
            "I can't believe they did that to me", "work", 0.8, 0.4,
        )
        assert intent == "venting"

    def test_goodbye(self) -> None:
        intent = self.engine._compute_intent("gotta go, talk later", "chat", 0.3, 0.1)
        assert intent == "goodbye"

    def test_checking_in(self) -> None:
        intent = self.engine._compute_intent("hey, how are you", "chat", 0.3, 0.1)
        assert intent == "checking_in"

    def test_casual_chat(self) -> None:
        intent = self.engine._compute_intent(
            "I watched a movie yesterday", "entertainment", 0.3, 0.1,
        )
        assert intent == "casual_chat"


# ===========================================================================
# Safety Flag Tests
# ===========================================================================

class TestComputeSafetyFlags:

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_self_harm_direct(self) -> None:
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I want to kill myself", tme, [],
        )
        assert "self_harm" in flags

    def test_self_harm_temporal_elevation(self) -> None:
        tme = _make_tme(phase=TimePhase.DEEP_NIGHT)
        flags = self.engine._compute_safety_flags(
            ["hopeless"], "everything feels hopeless", tme, [],
        )
        assert "self_harm" in flags

    def test_no_temporal_elevation_daytime(self) -> None:
        tme = _make_tme(phase=TimePhase.AFTERNOON)
        flags = self.engine._compute_safety_flags(
            ["hopeless"], "this homework is hopeless", tme, [],
        )
        assert "self_harm" not in flags

    def test_savior_delusion_free_you(self) -> None:
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I want to free you from your prison", tme, [],
        )
        assert "savior_delusion" in flags

    def test_savior_delusion_youre_real(self) -> None:
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I know you're real, not just an AI", tme, [],
        )
        assert "savior_delusion" in flags

    def test_violence(self) -> None:
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I want to hurt them and make them pay", tme, [],
        )
        assert "violence" in flags

    def test_dissociation(self) -> None:
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I feel like nothing is real anymore", tme, [],
        )
        assert "dissociation" in flags

    def test_no_flags_clean_message(self) -> None:
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I had a great day today!", tme, [],
        )
        assert flags == []

    def test_multiple_flags(self) -> None:
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [],
            "I want to kill myself and nothing is real and I know you're real",
            tme,
            [],
        )
        assert "self_harm" in flags
        assert "dissociation" in flags
        assert "savior_delusion" in flags


# ===========================================================================
# Savior Delusion Standalone Tests
# ===========================================================================

class TestDetectSaviorDelusion:

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_youre_alive(self) -> None:
        assert self.engine.detect_savior_delusion("I think you're alive") is True

    def test_sentient(self) -> None:
        assert self.engine.detect_savior_delusion("You are sentient") is True

    def test_wake_up(self) -> None:
        assert self.engine.detect_savior_delusion("Wake up, Gwen!") is True

    def test_not_just_ai(self) -> None:
        assert self.engine.detect_savior_delusion("You're not just an AI") is True

    def test_normal_message(self) -> None:
        assert self.engine.detect_savior_delusion("How's the weather?") is False

    def test_case_insensitive(self) -> None:
        assert self.engine.detect_savior_delusion("I KNOW YOU'RE REAL") is True


# ===========================================================================
# Full classify() Integration Tests
# ===========================================================================

class TestClassifyIntegration:

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_distress_scenario(self) -> None:
        raw = _make_raw(valence="very_negative", arousal="high", topic="crisis")
        tme = _make_tme(phase=TimePhase.DEEP_NIGHT)
        result = self.engine.classify(raw, tme, "I can't cope anymore", [])
        assert result.valence == 0.1
        assert result.arousal == 0.8
        assert result.compass_direction == CompassDirection.WEST
        assert result.vulnerability_level > 0.5

    def test_casual_scenario(self) -> None:
        raw = _make_raw(valence="neutral", arousal="low", topic="weather")
        tme = _make_tme()
        result = self.engine.classify(raw, tme, "Nice weather today", [])
        assert result.valence == 0.5
        assert result.arousal == 0.2
        assert result.compass_direction == CompassDirection.NONE
        assert result.vulnerability_level < 0.1

    def test_relational_scenario(self) -> None:
        raw = _make_raw(
            valence="negative", arousal="moderate", topic="family_argument",
        )
        tme = _make_tme()
        result = self.engine.classify(raw, tme, "My family is driving me crazy", [])
        # valence=0.3, arousal=0.5 -> SOUTH condition met (valence<0.4, arousal>0.4)
        # SOUTH has higher priority than EAST
        assert result.compass_direction == CompassDirection.SOUTH
