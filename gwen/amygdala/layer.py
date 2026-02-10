"""
Amygdala Layer — cross-cutting emotional modulation system.

The Amygdala Layer is NOT a storage tier. It modulates operations across
all memory tiers: storage strength, flashbulb detection, retrieval bias,
and decay rates.

References: SRS.md Section 8 (FR-AMY-001 through FR-AMY-004).
"""

from gwen.models.emotional import EmotionalStateVector


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Storage strength weights (SRS.md Section 3.1, EmotionalStateVector.storage_strength)
AROUSAL_WEIGHT = 0.4
RELATIONAL_SIGNIFICANCE_WEIGHT = 0.4
VULNERABILITY_WEIGHT = 0.2

# Flashbulb thresholds (SRS.md Section 3.1, EmotionalStateVector.is_flashbulb)
FLASHBULB_AROUSAL_THRESHOLD = 0.8
FLASHBULB_SIGNIFICANCE_THRESHOLD = 0.8

# Decay constants (SRS.md FR-AMY-004)
BASE_DECAY_RATE_PER_DAY = 0.05  # 5% daily decay for neutral memories
FLASHBULB_DECAY_RATE = 0.001    # Almost no decay for flashbulb memories
NEGATIVE_DECAY_MULTIPLIER = 0.5  # Negative memories decay at half rate
POSITIVE_DECAY_MULTIPLIER = 1.0  # Positive memories decay at normal rate
NEUTRAL_DECAY_MULTIPLIER = 1.5   # Neutral memories decay fastest

# Valence thresholds for decay classification
NEGATIVE_VALENCE_THRESHOLD = 0.3  # Below this = negative memory
POSITIVE_VALENCE_THRESHOLD = 0.7  # Above this = positive memory


class AmygdalaLayer:
    """Cross-cutting emotional modulation system.

    This class provides three capabilities:
    1. **Storage modulation** — computes how strongly a memory should be
       stored based on its emotional state (FR-AMY-002).
    2. **Decay modulation** — computes how fast a memory should decay
       based on its emotional valence and flashbulb status (FR-AMY-004).
    3. **Retrieval bias** — mood-congruent retrieval is handled by
       MoodCongruentRetriever in gwen/memory/retrieval.py, which uses
       the AmygdalaLayer for emotional computations.

    The AmygdalaLayer is stateless. It does not store anything itself.
    All its methods are pure functions of their inputs.
    """

    def __init__(self) -> None:
        pass

    def compute_storage_modulation(
        self, state: EmotionalStateVector
    ) -> tuple[float, bool]:
        """Compute storage strength and flashbulb status for a memory.

        Storage strength determines how strongly a memory is consolidated.
        Higher values mean the memory will be stored with more detail and
        will resist decay more during consolidation.

        The formula matches EmotionalStateVector.storage_strength (SRS.md 3.1):
            storage_strength = arousal * 0.4 + relational_significance * 0.4
                             + vulnerability_level * 0.2

        Parameters
        ----------
        state : EmotionalStateVector
            The emotional state of the memory being stored.

        Returns
        -------
        tuple[float, bool]
            A 2-tuple of ``(storage_strength, is_flashbulb)``.
        """
        storage_strength = (
            state.arousal * AROUSAL_WEIGHT
            + state.relational_significance * RELATIONAL_SIGNIFICANCE_WEIGHT
            + state.vulnerability_level * VULNERABILITY_WEIGHT
        )

        is_flashbulb = (
            state.arousal > FLASHBULB_AROUSAL_THRESHOLD
            and state.relational_significance > FLASHBULB_SIGNIFICANCE_THRESHOLD
        )

        return storage_strength, is_flashbulb

    def compute_decay_factor(
        self,
        emotional_state: EmotionalStateVector,
        days_elapsed: float,
    ) -> float:
        """Compute the decay factor for a memory after a given time.

        The decay factor is a multiplier in [0.0, 1.0] that represents
        how much of the memory's retrieval priority remains.

        Decay is emotionally modulated (SRS.md FR-AMY-004):
        - **Flashbulb memories** barely decay (rate = 0.001/day)
        - **Negative memories** decay slower than average (negativity bias)
        - **Positive memories** decay at normal rate
        - **Neutral memories** decay fastest
        - **High storage strength** further reduces decay rate

        Parameters
        ----------
        emotional_state : EmotionalStateVector
            The emotional state of the memory at the time it was stored.
        days_elapsed : float
            Number of days since the memory was stored. Must be >= 0.

        Returns
        -------
        float
            The decay factor, clamped to [0.0, 1.0].
        """
        # Step 1: Check if this is a flashbulb memory
        storage_strength, is_flashbulb = self.compute_storage_modulation(
            emotional_state
        )

        # Step 2: Determine base decay rate by emotional valence
        if is_flashbulb:
            decay_rate = FLASHBULB_DECAY_RATE
        elif emotional_state.valence < NEGATIVE_VALENCE_THRESHOLD:
            decay_rate = BASE_DECAY_RATE_PER_DAY * NEGATIVE_DECAY_MULTIPLIER
        elif emotional_state.valence > POSITIVE_VALENCE_THRESHOLD:
            decay_rate = BASE_DECAY_RATE_PER_DAY * POSITIVE_DECAY_MULTIPLIER
        else:
            decay_rate = BASE_DECAY_RATE_PER_DAY * NEUTRAL_DECAY_MULTIPLIER

        # Step 3: Factor in storage strength (stronger memories resist decay)
        decay_rate *= (1.0 - storage_strength * 0.5)

        # Step 4: Compute decay factor
        decay_factor = 1.0 - decay_rate * days_elapsed

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, decay_factor))
