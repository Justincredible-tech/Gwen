"""Reconsolidation models for the Memory Palimpsest system.

The Palimpsest model ensures memories evolve naturally while maintaining
absolute historical integrity. The original memory is immutable forever.
New understanding is layered on top, like a palimpsest manuscript where
new text overlays old -- but the old text is always recoverable.

Reference: SRS.md Section 3.15
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from gwen.models.emotional import EmotionalStateVector
from gwen.models.messages import MessageRecord


@dataclass
class ReconsolidationLayer:
    """A single layer of re-interpretation applied to a memory during reconsolidation.

    Each layer records how the memory was perceived when it was recalled.
    Emotional adjustments are bounded per layer to prevent runaway drift.

    Reference: SRS.md Section 3.15
    """

    id: str                                         # UUID string
    timestamp: datetime
    recall_session_id: str                          # Which session triggered the recall

    # Context at time of recall
    user_emotional_state_at_recall: EmotionalStateVector
    conversation_topic_at_recall: str

    # How the user reacted to the resurfaced memory
    reaction_type: str      # "warmth", "pain", "correction", "elaboration", "dismissal", "humor"
    reaction_detail: str

    # Bounded emotional adjustments (capped per layer)
    valence_delta: float            # Range: -0.10 to +0.10
    arousal_delta: float            # Range: -0.10 to +0.10
    significance_delta: float       # Range: 0.0 to +0.10 (can only increase)

    # New narrative context added by this reconsolidation
    narrative: str                  # e.g., "User laughed about this -- healing is happening"


@dataclass
class ReconsolidationConstraints:
    """Hard limits on how far a memory can drift from its original emotional signature.

    These defaults are intentionally conservative. A memory can shift at most
    0.10 per reconsolidation event, and at most 0.50 total from its original
    values. This prevents a single emotionally-charged recall from rewriting
    history.

    Reference: SRS.md Section 3.15
    """

    MAX_DELTA_PER_LAYER: float = 0.10       # Max change in any dimension per event
    MAX_TOTAL_DRIFT: float = 0.50           # Max cumulative drift from archive values
    MIN_LAYERS_FOR_TREND: int = 3           # Need 3+ layers before computing trend direction
    COOLDOWN_HOURS: float = 24.0            # Minimum time between reconsolidation of same memory


@dataclass
class MemoryPalimpsest:
    """A memory with its complete reconsolidation history.

    The archive is IMMUTABLE FOREVER. Layers are APPEND-ONLY.
    This dataclass provides properties and methods to compute the memory's
    current emotional reading (archive + all layers applied), the reading
    at any historical point, and a human-readable evolution summary.

    Reference: SRS.md Section 3.15
    """

    archive: MessageRecord                      # The original memory -- never modified
    layers: list[ReconsolidationLayer] = field(default_factory=list)
    constraints: ReconsolidationConstraints = field(
        default_factory=ReconsolidationConstraints
    )

    @property
    def current_valence(self) -> float:
        """The memory's current emotional valence, accounting for all reconsolidation layers.

        Sums all valence_delta values from layers, clamps the total delta to
        MAX_TOTAL_DRIFT, then clamps the final result to [0.0, 1.0].
        """
        base = self.archive.emotional_state.valence
        total_delta = sum(layer.valence_delta for layer in self.layers)
        total_delta = max(
            -self.constraints.MAX_TOTAL_DRIFT,
            min(self.constraints.MAX_TOTAL_DRIFT, total_delta),
        )
        return max(0.0, min(1.0, base + total_delta))

    @property
    def current_arousal(self) -> float:
        """The memory's current arousal, accounting for all reconsolidation layers."""
        base = self.archive.emotional_state.arousal
        total_delta = sum(layer.arousal_delta for layer in self.layers)
        total_delta = max(
            -self.constraints.MAX_TOTAL_DRIFT,
            min(self.constraints.MAX_TOTAL_DRIFT, total_delta),
        )
        return max(0.0, min(1.0, base + total_delta))

    @property
    def current_significance(self) -> float:
        """The memory's current relational significance.

        Note: significance can only increase (significance_delta >= 0),
        so we only clamp against MAX_TOTAL_DRIFT on the positive side.
        """
        base = self.archive.emotional_state.relational_significance
        total_delta = sum(layer.significance_delta for layer in self.layers)
        total_delta = min(self.constraints.MAX_TOTAL_DRIFT, total_delta)
        return min(1.0, base + total_delta)

    def current_reading(self) -> EmotionalStateVector:
        """The memory as it feels NOW -- archive + all layers applied.

        Returns a new EmotionalStateVector with valence, arousal, and
        relational_significance adjusted by reconsolidation layers.
        All other dimensions (dominance, vulnerability_level, compass_direction,
        compass_confidence) are preserved from the original archive.
        """
        original = self.archive.emotional_state
        return EmotionalStateVector(
            valence=self.current_valence,
            arousal=self.current_arousal,
            dominance=original.dominance,
            relational_significance=self.current_significance,
            vulnerability_level=original.vulnerability_level,
            compass_direction=original.compass_direction,
            compass_confidence=original.compass_confidence,
        )

    def reading_at(self, point_in_time: datetime) -> EmotionalStateVector:
        """The memory as it felt at a specific point -- only layers up to that time.

        Filters layers by timestamp and applies only those that existed at
        the given point_in_time. Useful for understanding how the memory
        has evolved over the relationship history.

        Args:
            point_in_time: Only layers with timestamp <= this value are applied.

        Returns:
            EmotionalStateVector reflecting the memory at that point in time.
        """
        applicable = [layer for layer in self.layers if layer.timestamp <= point_in_time]
        original = self.archive.emotional_state
        v_delta = sum(layer.valence_delta for layer in applicable)
        a_delta = sum(layer.arousal_delta for layer in applicable)
        s_delta = sum(layer.significance_delta for layer in applicable)
        return EmotionalStateVector(
            valence=max(0.0, min(1.0, original.valence + v_delta)),
            arousal=max(0.0, min(1.0, original.arousal + a_delta)),
            dominance=original.dominance,
            relational_significance=min(1.0, original.relational_significance + s_delta),
            vulnerability_level=original.vulnerability_level,
            compass_direction=original.compass_direction,
            compass_confidence=original.compass_confidence,
        )

    def evolution_summary(self) -> str:
        """Human-readable summary of how this memory has evolved.

        Returns a string describing the number of reconsolidation events,
        the direction of emotional drift, and the most recent reaction type.
        If no reconsolidation has occurred, states that explicitly.
        """
        if not self.layers:
            return "No reconsolidation -- memory is as originally recorded."
        orig_v = self.archive.emotional_state.valence
        curr_v = self.current_valence
        if curr_v > orig_v:
            direction = "more positive"
        elif curr_v < orig_v:
            direction = "more negative"
        else:
            direction = "unchanged"
        return (
            f"Reconsolidated {len(self.layers)} time(s). "
            f"Emotional tone has shifted {direction} "
            f"(original valence: {orig_v:.2f}, current: {curr_v:.2f}). "
            f"Most recent reaction: {self.layers[-1].reaction_type}."
        )
