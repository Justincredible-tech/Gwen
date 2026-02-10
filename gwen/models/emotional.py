"""Emotional state models and Compass direction enum.

Defines the core emotional representation used throughout the Gwen system.
All float values are normalized to 0.0-1.0 unless otherwise noted.
Reference: SRS.md Section 3.1
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CompassDirection(Enum):
    """The four Compass Framework directions plus a neutral state.

    Each direction maps to a domain of life-coaching support:
    - NORTH (presence): Mindfulness and grounding techniques
    - SOUTH (currents): Emotion regulation and processing
    - WEST (anchoring): Distress tolerance and stability
    - EAST (bridges): Interpersonal effectiveness and connection
    """

    NONE = "none"
    NORTH = "presence"
    SOUTH = "currents"
    WEST = "anchoring"
    EAST = "bridges"


@dataclass
class EmotionalStateVector:
    """The core emotional representation used throughout the system.

    All values are floats from 0.0 to 1.0 unless otherwise noted.
    This model extends the standard Valence-Arousal-Dominance (VAD)
    dimensional model with two companion-specific dimensions:
    relational_significance and vulnerability_level.

    Reference: SRS.md Section 3.1
    """

    # Primary dimensions (Valence-Arousal-Dominance model)
    valence: float              # 0.0 = extremely negative, 0.5 = neutral, 1.0 = extremely positive
    arousal: float              # 0.0 = calm/lethargic, 1.0 = highly activated/agitated
    dominance: float            # 0.0 = helpless/submissive, 1.0 = in-control/dominant

    # Companion-specific dimensions
    relational_significance: float  # 0.0 = routine, 1.0 = deeply significant to the relationship
    vulnerability_level: float      # 0.0 = guarded, 1.0 = fully open/exposed

    # Classification outputs
    compass_direction: CompassDirection = CompassDirection.NONE
    compass_confidence: float = 0.0  # 0.0-1.0, classifier confidence in the direction tag

    @property
    def storage_strength(self) -> float:
        """Compute the storage strength multiplier for the Amygdala Layer.

        Formula: arousal * 0.4 + relational_significance * 0.4 + vulnerability_level * 0.2

        This determines how strongly a memory is encoded. High-arousal,
        high-significance, high-vulnerability moments are stored more strongly
        and resist decay longer.
        """
        return (
            self.arousal * 0.4
            + self.relational_significance * 0.4
            + self.vulnerability_level * 0.2
        )

    @property
    def is_flashbulb(self) -> bool:
        """Determine if this emotional state qualifies as a flashbulb memory candidate.

        A flashbulb memory is created when BOTH arousal AND relational_significance
        exceed 0.8. These memories receive special treatment: they are never decayed,
        always retrievable, and stored with maximum detail.

        Returns True when arousal > 0.8 AND relational_significance > 0.8.
        """
        return self.arousal > 0.8 and self.relational_significance > 0.8
