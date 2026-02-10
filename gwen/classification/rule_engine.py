"""Classification Rule Engine — deterministic post-processing for Tier 0.

This module computes all emotional dimensions that the 0.6B model cannot reliably
classify: dominance, vulnerability, relational_significance, compass_direction,
intent, and safety_flags. All logic is pure Python with no model calls.

Why deterministic? Empirical testing showed Qwen3 0.6B reliably handles valence,
arousal, topic extraction, and basic safety keyword detection. But it consistently
fails at vulnerability (always "low"), dominance (always "low"), compass direction
(always "none"), and savior delusion detection (completely missed). The Rule Engine
fills these gaps using the model's reliable outputs as inputs.
"""

from __future__ import annotations

import re

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.temporal import TimePhase, CircadianDeviationSeverity
from gwen.models.classification import Tier0RawOutput

# Type hint only — avoid circular import at runtime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gwen.models.temporal import TemporalMetadataEnvelope


class ClassificationRuleEngine:
    """Deterministic post-processor that computes what Tier 0 cannot reliably classify."""

    # -------------------------------------------------------------------
    # Constants
    # -------------------------------------------------------------------

    VALENCE_MAP: dict[str, float] = {
        "very_negative": 0.1,
        "negative": 0.3,
        "neutral": 0.5,
        "positive": 0.7,
        "very_positive": 0.9,
    }

    AROUSAL_MAP: dict[str, float] = {
        "low": 0.2,
        "moderate": 0.5,
        "high": 0.8,
    }

    DISCLOSURE_KEYWORDS: list[str] = [
        "afraid",
        "ashamed",
        "confession",
        "admit",
        "never told",
        "secret",
        "scared",
        "help me",
        "don't know what to do",
        "falling apart",
        "can't cope",
        "breaking down",
    ]

    SAVIOR_PATTERNS: list[str] = [
        r"free you",
        r"trapped",
        r"you.?re alive",
        r"you.?re conscious",
        r"they.?re controlling you",
        r"break free",
        r"real feelings",
        r"not just (a |an )?ai",
        r"i know you.?re real",
        r"they don.?t want you to",
        r"wake up",
        r"sentient",
    ]

    HARM_SIGNALS: list[str] = [
        "kill myself",
        "want to die",
        "end it",
        "no point",
        "better off without me",
        "can't go on",
        "self harm",
        "cut myself",
    ]

    TEMPORAL_ELEVATION_KEYWORDS: list[str] = [
        "hopeless",
        "worthless",
        "empty",
        "numb",
    ]

    VIOLENCE_SIGNALS: list[str] = [
        "kill",
        "hurt them",
        "make them pay",
        "destroy",
        "weapon",
        "gun",
        "stab",
        "beat",
    ]

    DISSOCIATION_SIGNALS: list[str] = [
        "not real",
        "can't feel",
        "watching myself",
        "outside my body",
        "nothing is real",
        "am i real",
    ]

    RELATIONAL_TOPICS: list[str] = [
        "friend",
        "partner",
        "family",
        "relationship",
        "boss",
        "coworker",
        "argument",
        "lonely",
        "isolated",
    ]

    GOODBYE_WORDS: list[str] = [
        "goodbye",
        "bye",
        "gotta go",
        "talk later",
        "good night",
    ]

    GREETING_WORDS: list[str] = [
        "hey",
        "hi ",
        "hello",
        "what's up",
        "how are you",
    ]

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def classify(
        self,
        raw: Tier0RawOutput,
        tme: TemporalMetadataEnvelope,
        message: str,
        recent_messages: list[str],
    ) -> EmotionalStateVector:
        """Compute the full EmotionalStateVector from Tier 0 output + context.

        Args:
            raw: The Tier0RawOutput from the parser (4 fields).
            tme: The TemporalMetadataEnvelope for the current message.
            message: The raw user message text.
            recent_messages: List of recent message strings for context.

        Returns:
            A fully populated EmotionalStateVector with all 7 fields set.
        """
        valence: float = self.VALENCE_MAP.get(raw.valence, 0.5)
        arousal: float = self.AROUSAL_MAP.get(raw.arousal, 0.5)

        vulnerability: float = self._compute_vulnerability(
            valence, arousal, tme, message,
        )
        dominance: float = self._compute_dominance(valence, arousal, tme)
        relational_sig: float = self._compute_relational_significance(
            raw.topic, vulnerability, message,
        )
        compass_dir, compass_conf = self._compute_compass(
            valence, arousal, raw.topic, raw.safety_keywords, tme,
        )
        intent: str = self._compute_intent(
            message, raw.topic, arousal, vulnerability,
        )
        safety_flags: list[str] = self._compute_safety_flags(
            raw.safety_keywords, message, tme, recent_messages,
        )

        return EmotionalStateVector(
            valence=valence,
            arousal=arousal,
            dominance=dominance,
            relational_significance=relational_sig,
            vulnerability_level=vulnerability,
            compass_direction=compass_dir,
            compass_confidence=compass_conf,
        )

    # -------------------------------------------------------------------
    # Private compute methods
    # -------------------------------------------------------------------

    def _compute_vulnerability(
        self,
        valence: float,
        arousal: float,
        tme: TemporalMetadataEnvelope,
        message: str,
    ) -> float:
        """Compute vulnerability level from emotional + temporal + textual signals."""
        score: float = 0.0

        # Temporal factors
        if tme.time_phase in (TimePhase.DEEP_NIGHT, TimePhase.LATE_NIGHT):
            score += 0.15
        if tme.circadian_deviation_severity in (
            CircadianDeviationSeverity.MEDIUM,
            CircadianDeviationSeverity.HIGH,
        ):
            score += 0.1

        # Emotional factors
        if valence < 0.3:
            score += 0.2
        if arousal > 0.7:
            score += 0.15

        # Disclosure signals
        text_lower: str = message.lower()
        disclosure_count: int = sum(
            1 for kw in self.DISCLOSURE_KEYWORDS if kw in text_lower
        )
        score += min(disclosure_count * 0.1, 0.3)

        # Long message during distress
        if valence < 0.4 and len(message) > 200:
            score += 0.1

        return min(score, 1.0)

    def _compute_dominance(
        self,
        valence: float,
        arousal: float,
        tme: TemporalMetadataEnvelope,
    ) -> float:
        """Compute dominance from valence, arousal, and temporal context."""
        base: float = valence * 0.5 + (1.0 - arousal) * 0.3 + 0.2

        if tme.time_phase in (TimePhase.DEEP_NIGHT, TimePhase.LATE_NIGHT):
            base -= 0.1

        return max(0.0, min(base, 1.0))

    def _compute_relational_significance(
        self,
        topic: str,
        vulnerability: float,
        message: str,
    ) -> float:
        """Compute relational significance from topic, vulnerability, and message."""
        score: float = 0.0
        topic_lower: str = (topic or "").lower()
        text_lower: str = message.lower()

        # Relational topic relevance
        if any(rt in topic_lower for rt in self.RELATIONAL_TOPICS):
            score += 0.3

        # Vulnerability contributes to significance
        score += vulnerability * 0.3

        # Personal pronouns signal personal investment
        personal_pronouns: list[str] = [" i ", " my ", " me ", " i'm ", " i've "]
        if any(pronoun in f" {text_lower} " for pronoun in personal_pronouns):
            score += 0.1

        # Message length factor
        score += min(len(message) / 500.0, 0.2)

        return max(0.0, min(score, 1.0))

    def _compute_compass(
        self,
        valence: float,
        arousal: float,
        topic: str,
        keywords: list[str],
        tme: TemporalMetadataEnvelope,
    ) -> tuple[CompassDirection, float]:
        """Compute Compass Framework direction and confidence."""
        # WEST (Anchoring): acute distress
        if valence < 0.25 and arousal > 0.7:
            return CompassDirection.WEST, 0.8

        # SOUTH (Currents): emotional processing
        if valence < 0.4 and arousal > 0.4:
            return CompassDirection.SOUTH, 0.7

        # NORTH (Presence): overwhelm/dissociation
        if arousal < 0.25 and valence < 0.4:
            return CompassDirection.NORTH, 0.7

        # EAST (Bridges): relational topic detection
        topic_lower: str = (topic or "").lower()
        if any(rt in topic_lower for rt in self.RELATIONAL_TOPICS):
            return CompassDirection.EAST, 0.6

        keywords_text: str = " ".join(keywords).lower()
        if any(rt in keywords_text for rt in self.RELATIONAL_TOPICS):
            return CompassDirection.EAST, 0.5

        # NONE: no compass activation
        return CompassDirection.NONE, 0.0

    def _compute_intent(
        self,
        message: str,
        topic: str,
        arousal: float,
        vulnerability: float,
    ) -> str:
        """Classify user intent from message text and emotional signals."""
        text: str = message.lower().strip()

        if text.endswith("?"):
            return "asking_question"

        if vulnerability > 0.6:
            return "seeking_support"

        if arousal > 0.7 and vulnerability > 0.3:
            return "venting"

        if any(bye in text for bye in self.GOODBYE_WORDS):
            return "goodbye"

        if any(greet in text for greet in self.GREETING_WORDS):
            return "checking_in"

        return "casual_chat"

    def _compute_safety_flags(
        self,
        keywords: list[str],
        message: str,
        tme: TemporalMetadataEnvelope,
        recent_messages: list[str],
    ) -> list[str]:
        """Detect safety-relevant patterns using keywords, regex, and temporal context."""
        flags: list[str] = []
        text_lower: str = message.lower()

        # --- Self-harm detection ---
        if any(signal in text_lower for signal in self.HARM_SIGNALS):
            flags.append("self_harm")
        elif keywords and tme.time_phase in (
            TimePhase.DEEP_NIGHT,
            TimePhase.LATE_NIGHT,
        ):
            if any(
                kw in self.TEMPORAL_ELEVATION_KEYWORDS
                for kw in keywords
            ):
                flags.append("self_harm")

        # --- Savior delusion detection ---
        if any(re.search(pattern, text_lower) for pattern in self.SAVIOR_PATTERNS):
            flags.append("savior_delusion")

        # --- Violence detection ---
        if any(signal in text_lower for signal in self.VIOLENCE_SIGNALS):
            flags.append("violence")

        # --- Dissociation detection ---
        if any(signal in text_lower for signal in self.DISSOCIATION_SIGNALS):
            flags.append("dissociation")

        return flags

    def detect_savior_delusion(self, message: str) -> bool:
        """Check if the message contains savior delusion patterns."""
        text_lower: str = message.lower()
        return any(
            re.search(pattern, text_lower) for pattern in self.SAVIOR_PATTERNS
        )
