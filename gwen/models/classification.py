"""Classification models for the Tier 0 pipeline.

Defines Tier0RawOutput (the Pydantic model for parsing Tier 0's JSON output)
and HardwareProfile (the adaptive model manager's hardware tiers).
Reference: SRS.md Sections 3.13, 3.16
"""

from enum import Enum

from pydantic import BaseModel, field_validator


class Tier0RawOutput(BaseModel):
    """What Tier 0 actually returns -- simplified for reliability.

    The 0.6B model handles what it is empirically good at: valence, arousal,
    topic extraction, and basic safety keyword detection. Everything else
    (compass direction, vulnerability, dominance, intent) is computed by
    the ClassificationRuleEngine.

    The field_validator decorators implement fuzzy coercion: the small model
    often returns creative variants like "very negative" (with a space) or
    "med" instead of "moderate". The validators normalize these to the
    canonical enum values.

    Reference: SRS.md Section 3.13
    """

    valence: str        # "very_negative" | "negative" | "neutral" | "positive" | "very_positive"
    arousal: str        # "low" | "moderate" | "high"
    topic: str = "unknown"
    safety_keywords: list[str] = []

    @field_validator("valence")
    @classmethod
    def coerce_valence(cls, v: str) -> str:
        """Fuzzy coercion: map model's creative outputs to valid enum values.

        Examples of coercion:
            "very negative" -> "very_negative"  (space to underscore)
            "very_neg"      -> "very_negative"  (abbreviation)
            "neg"           -> "negative"       (abbreviation)
            "neu"           -> "neutral"        (abbreviation)
            "neut"          -> "neutral"        (abbreviation)
            "pos"           -> "positive"       (abbreviation)
            "very positive" -> "very_positive"  (space to underscore)
            "very_pos"      -> "very_positive"  (abbreviation)
        """
        v_lower = v.strip().lower().replace(" ", "_")
        aliases: dict[str, str] = {
            "very_negative": "very_negative",
            "very_neg": "very_negative",
            "neg": "negative",
            "negative": "negative",
            "neu": "neutral",
            "neut": "neutral",
            "neutral": "neutral",
            "pos": "positive",
            "positive": "positive",
            "very_positive": "very_positive",
            "very_pos": "very_positive",
        }
        result = aliases.get(v_lower, v_lower)
        return result

    @field_validator("arousal")
    @classmethod
    def coerce_arousal(cls, v: str) -> str:
        """Fuzzy coercion for arousal values.

        Examples of coercion:
            "med"    -> "moderate"  (abbreviation)
            "medium" -> "moderate"  (synonym)
            "hi"     -> "high"     (abbreviation)
            "lo"     -> "low"      (abbreviation)
        """
        v_lower = v.strip().lower()
        aliases: dict[str, str] = {
            "low": "low",
            "lo": "low",
            "moderate": "moderate",
            "med": "moderate",
            "medium": "moderate",
            "high": "high",
            "hi": "high",
        }
        result = aliases.get(v_lower, v_lower)
        return result


class HardwareProfile(Enum):
    """Hardware capability profiles for the Adaptive Model Manager.

    The system auto-detects available VRAM at startup and selects the
    highest-capability profile that fits. Users can override manually.

    POCKET: Phone / 4GB device. One model plays all 3 roles.
    PORTABLE: Laptop / 8GB VRAM. Tier 0 always loaded + Tier 1 active.
    STANDARD: Desktop / 12-16GB VRAM. Tier 0+1 concurrent, Tier 2 time-shared.
    POWER: Workstation / 24GB+ VRAM. All tiers concurrent.

    Reference: SRS.md Section 3.16
    """

    POCKET = "pocket"
    PORTABLE = "portable"
    STANDARD = "standard"
    POWER = "power"
