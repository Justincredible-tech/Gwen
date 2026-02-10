# Plan: Amygdala Layer

**Track:** 013-amygdala-layer
**Depends on:** 005-tier0-pipeline (EmotionalStateVector populated by classification), 009-embedding-service (EmbeddingService for semantic/emotional embeddings)
**Produces:** gwen/amygdala/__init__.py, gwen/amygdala/layer.py, gwen/memory/retrieval.py, tests/test_amygdala.py

---

## Phase 1: Package Initialization

### Step 1.1: Create gwen/amygdala/__init__.py

Create the file `gwen/amygdala/__init__.py` with the following exact content:

```python
"""Amygdala Layer - emotional modulation of storage, retrieval, and decay."""
```

**Why:** This makes `gwen.amygdala` a Python package so that `from gwen.amygdala.layer import AmygdalaLayer` works. If this file already exists from Track 001 scaffold, verify the content matches and skip this step.

**Verification gate (manual):** Run `python -c "import gwen.amygdala; print('OK')"` and confirm it prints `OK`.

---

## Phase 2: Storage Modulation

### Step 2.1: Create gwen/amygdala/layer.py

Create the file `gwen/amygdala/layer.py` with the following exact content:

```python
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
        """Initialize the AmygdalaLayer.

        No arguments needed — the AmygdalaLayer is stateless.
        It computes modulation values from EmotionalStateVectors
        passed to each method.
        """
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

        Flashbulb memories are moments of exceptional emotional intensity
        that are stored with maximum fidelity (like a camera flash preserving
        every detail). They occur when BOTH arousal AND relational_significance
        exceed 0.8.

        Parameters
        ----------
        state : EmotionalStateVector
            The emotional state of the memory being stored.

        Returns
        -------
        tuple[float, bool]
            A 2-tuple of ``(storage_strength, is_flashbulb)``.
            - ``storage_strength`` is in [0.0, 1.0].
            - ``is_flashbulb`` is True if this is a flashbulb memory.

        Examples
        --------
        >>> layer = AmygdalaLayer()
        >>> state = EmotionalStateVector(
        ...     valence=0.8, arousal=0.9, dominance=0.5,
        ...     relational_significance=0.9, vulnerability_level=0.3,
        ... )
        >>> strength, flashbulb = layer.compute_storage_modulation(state)
        >>> strength  # 0.9*0.4 + 0.9*0.4 + 0.3*0.2 = 0.36 + 0.36 + 0.06 = 0.78
        0.78
        >>> flashbulb  # arousal 0.9 > 0.8 AND significance 0.9 > 0.8
        True
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
        how much of the memory's retrieval priority remains. A factor of
        1.0 means no decay; 0.0 means fully decayed.

        Decay is emotionally modulated (SRS.md FR-AMY-004):
        - **Flashbulb memories** barely decay (rate = 0.001/day)
        - **Negative memories** decay slower than average (negativity bias)
        - **Positive memories** decay at normal rate
        - **Neutral memories** decay fastest
        - **High storage strength** further reduces decay rate

        IMPORTANT: Decay reduces retrieval priority, NOT deletes. The
        Chronicle remains complete. A fully-decayed memory still exists
        in the database; it just has very low retrieval priority.

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
            - 1.0 = no decay (memory is fresh or flashbulb)
            - 0.0 = fully decayed (memory has very low retrieval priority)

        Examples
        --------
        >>> layer = AmygdalaLayer()
        >>> # Flashbulb memory after 100 days: barely decayed
        >>> state = EmotionalStateVector(
        ...     valence=0.8, arousal=0.9, dominance=0.5,
        ...     relational_significance=0.9, vulnerability_level=0.3,
        ... )
        >>> layer.compute_decay_factor(state, days_elapsed=100)
        0.9  # Approximately, due to 0.001 * 100 = 0.1 decay

        >>> # Neutral memory after 10 days: significant decay
        >>> state = EmotionalStateVector(
        ...     valence=0.5, arousal=0.3, dominance=0.5,
        ...     relational_significance=0.2, vulnerability_level=0.1,
        ... )
        >>> layer.compute_decay_factor(state, days_elapsed=10)
        # decay_rate = 0.05 * 1.5 * (1 - storage_strength * 0.5)
        # storage_strength = 0.3*0.4 + 0.2*0.4 + 0.1*0.2 = 0.22
        # decay_rate = 0.075 * (1 - 0.11) = 0.075 * 0.89 = 0.06675
        # factor = max(0, 1.0 - 0.06675 * 10) = max(0, 0.3325) = 0.3325
        """
        # Step 1: Check if this is a flashbulb memory
        storage_strength, is_flashbulb = self.compute_storage_modulation(
            emotional_state
        )

        # Step 2: Determine base decay rate by emotional valence
        if is_flashbulb:
            decay_rate = FLASHBULB_DECAY_RATE
        elif emotional_state.valence < NEGATIVE_VALENCE_THRESHOLD:
            # Negative memories: negativity bias — they decay slower
            decay_rate = BASE_DECAY_RATE_PER_DAY * NEGATIVE_DECAY_MULTIPLIER
        elif emotional_state.valence > POSITIVE_VALENCE_THRESHOLD:
            # Positive memories: normal decay rate
            decay_rate = BASE_DECAY_RATE_PER_DAY * POSITIVE_DECAY_MULTIPLIER
        else:
            # Neutral memories: decay fastest
            decay_rate = BASE_DECAY_RATE_PER_DAY * NEUTRAL_DECAY_MULTIPLIER

        # Step 3: Factor in storage strength (stronger memories resist decay)
        # A storage_strength of 1.0 reduces decay by 50%;
        # a storage_strength of 0.0 does not reduce decay at all.
        decay_rate *= (1.0 - storage_strength * 0.5)

        # Step 4: Compute decay factor
        decay_factor = 1.0 - decay_rate * days_elapsed

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, decay_factor))
```

**What this does:**
1. `compute_storage_modulation()` implements FR-AMY-002 — the same formula used by `EmotionalStateVector.storage_strength` and `is_flashbulb`, but as an explicit method so callers do not need to know about the property.
2. `compute_decay_factor()` implements FR-AMY-004 — emotionally modulated decay with negativity bias and flashbulb resistance.

---

## Phase 3: Mood-Congruent Retrieval

### Step 3.1: Create gwen/memory/retrieval.py

Create the file `gwen/memory/retrieval.py` with the following exact content:

```python
"""
Mood-Congruent Memory Retrieval — emotionally biased memory search.

Implements SRS.md Section 4.5.1 and FR-AMY-003:
- Retrieval is biased toward memories that match the current emotional state
- During safety events, bias INVERTS to surface stabilizing (positive) memories
- During user distress, sensitive memories are penalized

References: SRS.md Section 4.5.1 (pseudocode), FR-AMY-003.
"""

import math
from typing import Optional

from gwen.models.emotional import EmotionalStateVector


# ---------------------------------------------------------------------------
# Pure math helpers
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Implemented from scratch for small vectors (5D emotional embeddings).
    No numpy dependency needed.

    Parameters
    ----------
    a : list[float]
        First vector. Must be the same length as ``b``.
    b : list[float]
        Second vector. Must be the same length as ``a``.

    Returns
    -------
    float
        Cosine similarity in [-1.0, 1.0]. Returns 0.0 if either vector
        has zero magnitude (to avoid division by zero).

    Examples
    --------
    >>> cosine_similarity([1, 0, 0], [1, 0, 0])
    1.0
    >>> cosine_similarity([1, 0, 0], [0, 1, 0])
    0.0
    >>> cosine_similarity([1, 0, 0], [-1, 0, 0])
    -1.0
    """
    if len(a) != len(b):
        raise ValueError(
            f"Vectors must be same length: len(a)={len(a)}, len(b)={len(b)}"
        )

    dot_product = sum(ai * bi for ai, bi in zip(a, b))
    magnitude_a = math.sqrt(sum(ai * ai for ai in a))
    magnitude_b = math.sqrt(sum(bi * bi for bi in b))

    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


def emotional_state_to_vector(state: EmotionalStateVector) -> list[float]:
    """Convert an EmotionalStateVector to a 5D list for similarity computation.

    The 5 dimensions are, in order:
    1. valence
    2. arousal
    3. dominance
    4. relational_significance
    5. vulnerability_level

    This matches the 5D emotional embedding format used in ChromaDB's
    emotional_embeddings collection (see SRS.md OQ-001 resolution).

    Parameters
    ----------
    state : EmotionalStateVector
        The emotional state to convert.

    Returns
    -------
    list[float]
        A 5-element list of floats.
    """
    return [
        state.valence,
        state.arousal,
        state.dominance,
        state.relational_significance,
        state.vulnerability_level,
    ]


class MoodCongruentRetriever:
    """Mood-congruent memory retrieval with safety inversion.

    Re-ranks semantic search results by incorporating emotional similarity
    between the current emotional state and stored memories. During safety
    events, the bias inverts to surface positive/stabilizing memories.

    This class requires:
    - An embedding service (for query embedding)
    - A ChromaDB semantic collection (for semantic search)
    - A ChromaDB emotional collection (for emotional embeddings)

    References: SRS.md Section 4.5.1, FR-AMY-003.
    """

    def __init__(
        self,
        embedding_service,
        semantic_collection,
        emotional_collection,
    ) -> None:
        """Initialize the MoodCongruentRetriever.

        Parameters
        ----------
        embedding_service : EmbeddingService
            Used to embed the query text into a 1024-dim semantic vector.
            Must have an ``embed(text: str) -> list[float]`` method.
        semantic_collection : chromadb.Collection
            The ChromaDB collection containing semantic embeddings (1024-dim).
            Used for the initial semantic search.
        emotional_collection : chromadb.Collection
            The ChromaDB collection containing emotional embeddings (5-dim).
            Used to look up the emotional vector for each candidate memory.
        """
        self.embedding_service = embedding_service
        self.semantic_collection = semantic_collection
        self.emotional_collection = emotional_collection

    async def retrieve(
        self,
        query: str,
        current_state: EmotionalStateVector,
        safety_level: str = "none",
        max_results: int = 5,
        alpha: float = 0.3,
    ) -> list[dict]:
        """Retrieve memories with mood-congruent bias.

        Algorithm (SRS.md Section 4.5.1):
        1. Embed the query and perform semantic search (over-fetch 3x)
        2. Encode current emotional state as a 5D vector
        3. For each candidate, compute emotional similarity
        4. Apply safety inversion if safety_level is "high" or "critical"
        5. Compute final_score = semantic_score * (1 + alpha * emotional_factor)
        6. Apply distress penalty for sensitive memories when user is distressed
        7. Sort by final_score descending, return top max_results

        Parameters
        ----------
        query : str
            The search query text. Will be embedded using the embedding
            service for semantic similarity search.
        current_state : EmotionalStateVector
            The user's current emotional state. Used for mood-congruent
            bias and distress detection.
        safety_level : str
            Current safety level. One of "none", "low", "medium", "high",
            "critical". When "high" or "critical", emotional bias inverts
            to surface positive/stabilizing memories (the computational
            equivalent of "remember when you got through that tough time").
        max_results : int
            Number of results to return. Default 5.
        alpha : float
            Mood-congruent bias strength. Default 0.3 (from SRS.md FR-AMY-003).
            Higher values increase the influence of emotional similarity
            on the final ranking. 0.0 disables mood-congruent bias entirely.

        Returns
        -------
        list[dict]
            A list of result dicts, each containing:
            - "id": str — the memory ID
            - "content": str — the memory text
            - "semantic_score": float — raw semantic similarity
            - "emotional_score": float — emotional similarity (or inverted)
            - "final_score": float — the combined score used for ranking
            - "metadata": dict — any metadata from ChromaDB

        Notes
        -----
        The over-fetch factor of 3x means we retrieve 3 * max_results
        candidates from ChromaDB, then re-rank them with emotional bias
        and return only the top max_results. This ensures we have enough
        candidates for the emotional re-ranking to be meaningful.
        """
        # Step 1: Semantic search (over-fetch 3x for re-ranking headroom)
        over_fetch = max_results * 3
        query_embedding = await self.embedding_service.embed(query)
        semantic_results = self.semantic_collection.query(
            query_embeddings=[query_embedding],
            n_results=over_fetch,
            include=["documents", "distances", "metadatas"],
        )

        # ChromaDB returns results in a nested list structure
        if not semantic_results["ids"] or not semantic_results["ids"][0]:
            return []

        ids = semantic_results["ids"][0]
        documents = semantic_results["documents"][0] if semantic_results["documents"] else [""] * len(ids)
        distances = semantic_results["distances"][0] if semantic_results["distances"] else [0.0] * len(ids)
        metadatas = semantic_results["metadatas"][0] if semantic_results["metadatas"] else [{}] * len(ids)

        # Step 2: Encode current emotional state as 5D vector
        current_emotional_vec = emotional_state_to_vector(current_state)

        # Step 3: Look up emotional embeddings for all candidates
        # Batch lookup from ChromaDB emotional collection
        emotional_lookup = self.emotional_collection.get(
            ids=ids,
            include=["embeddings"],
        )
        emotional_embeddings_map: dict[str, list[float]] = {}
        if emotional_lookup["ids"] and emotional_lookup["embeddings"]:
            for eid, emb in zip(
                emotional_lookup["ids"], emotional_lookup["embeddings"]
            ):
                emotional_embeddings_map[eid] = emb

        # Step 4: Re-rank with mood-congruent bias
        scored_results: list[dict] = []
        for i, memory_id in enumerate(ids):
            # ChromaDB distances are L2 distances; convert to similarity
            # similarity = 1 / (1 + distance) for L2
            distance = distances[i]
            semantic_score = 1.0 / (1.0 + distance)

            # Get emotional embedding for this memory
            memory_emotional_vec = emotional_embeddings_map.get(memory_id)
            if memory_emotional_vec is None:
                # No emotional embedding stored; use neutral default
                emotional_sim = 0.0
            else:
                emotional_sim = cosine_similarity(
                    current_emotional_vec, memory_emotional_vec
                )

            # Step 4a: Safety inversion
            if safety_level in ("high", "critical"):
                # INVERT: surface emotionally INCONGRUENT (positive) memories
                # during crisis. This is the computational equivalent of
                # "remember when you got through that tough time."
                emotional_factor = 1.0 - emotional_sim
            else:
                # Normal: bias toward emotionally similar memories
                emotional_factor = emotional_sim

            # Step 4b: Compute final score
            final_score = semantic_score * (1.0 + alpha * emotional_factor)

            # Step 4c: Distress penalty
            # If user is in distress (valence < 0.3) and the memory is
            # emotionally sensitive (sensitivity > 0.7), penalize it to
            # avoid reopening wounds.
            sensitivity = 0.0
            if metadatas[i] and "sensitivity_level" in metadatas[i]:
                sensitivity = float(metadatas[i]["sensitivity_level"])
            if current_state.valence < 0.3 and sensitivity > 0.7:
                final_score *= 0.5

            scored_results.append({
                "id": memory_id,
                "content": documents[i] if i < len(documents) else "",
                "semantic_score": semantic_score,
                "emotional_score": emotional_factor,
                "final_score": final_score,
                "metadata": metadatas[i] if i < len(metadatas) else {},
            })

        # Step 5: Sort by final_score descending, return top max_results
        scored_results.sort(key=lambda x: x["final_score"], reverse=True)
        return scored_results[:max_results]
```

**What this does:**
1. `cosine_similarity()` computes cosine similarity from scratch for 5D vectors (no numpy needed).
2. `emotional_state_to_vector()` converts an EmotionalStateVector to a 5D list.
3. `MoodCongruentRetriever.retrieve()` implements the full retrieval algorithm from SRS.md Section 4.5.1:
   - Over-fetches 3x from ChromaDB semantic collection
   - Computes emotional similarity using 5D emotional embeddings
   - Inverts bias during safety events (HIGH/CRITICAL)
   - Applies distress penalty for sensitive memories
   - Returns re-ranked results

---

## Phase 4: Tests

### Step 4.1: Write tests/test_amygdala.py

Create the file `tests/test_amygdala.py` with the following exact content:

```python
"""Tests for the Amygdala Layer — emotional modulation of storage, retrieval, and decay.

Run with:
    pytest tests/test_amygdala.py -v
"""

import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from gwen.amygdala.layer import (
    AROUSAL_WEIGHT,
    BASE_DECAY_RATE_PER_DAY,
    FLASHBULB_DECAY_RATE,
    NEGATIVE_DECAY_MULTIPLIER,
    NEUTRAL_DECAY_MULTIPLIER,
    POSITIVE_DECAY_MULTIPLIER,
    VULNERABILITY_WEIGHT,
    RELATIONAL_SIGNIFICANCE_WEIGHT,
    AmygdalaLayer,
)
from gwen.memory.retrieval import (
    MoodCongruentRetriever,
    cosine_similarity,
    emotional_state_to_vector,
)
from gwen.models.emotional import CompassDirection, EmotionalStateVector


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> EmotionalStateVector:
    """Create an EmotionalStateVector with sensible defaults."""
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


@pytest.fixture()
def amygdala() -> AmygdalaLayer:
    """Return a fresh AmygdalaLayer instance."""
    return AmygdalaLayer()


# ---------------------------------------------------------------------------
# Tests: Storage Modulation
# ---------------------------------------------------------------------------

class TestStorageModulation:
    """Tests for AmygdalaLayer.compute_storage_modulation()."""

    def test_formula_matches_spec(self, amygdala: AmygdalaLayer) -> None:
        """Storage strength = arousal*0.4 + relational_significance*0.4 + vulnerability*0.2."""
        state = _make_state(
            arousal=0.8,
            relational_significance=0.6,
            vulnerability_level=0.4,
        )
        strength, _ = amygdala.compute_storage_modulation(state)
        expected = 0.8 * 0.4 + 0.6 * 0.4 + 0.4 * 0.2  # 0.32 + 0.24 + 0.08 = 0.64
        assert strength == pytest.approx(expected)

    def test_all_zeros(self, amygdala: AmygdalaLayer) -> None:
        """All zero inputs produce zero storage strength."""
        state = _make_state(arousal=0.0, relational_significance=0.0, vulnerability_level=0.0)
        strength, flashbulb = amygdala.compute_storage_modulation(state)
        assert strength == pytest.approx(0.0)
        assert flashbulb is False

    def test_all_ones(self, amygdala: AmygdalaLayer) -> None:
        """All max inputs produce maximum storage strength and flashbulb."""
        state = _make_state(arousal=1.0, relational_significance=1.0, vulnerability_level=1.0)
        strength, flashbulb = amygdala.compute_storage_modulation(state)
        expected = 1.0 * 0.4 + 1.0 * 0.4 + 1.0 * 0.2  # 1.0
        assert strength == pytest.approx(expected)
        assert flashbulb is True

    def test_flashbulb_threshold_both_above(self, amygdala: AmygdalaLayer) -> None:
        """Flashbulb requires BOTH arousal > 0.8 AND significance > 0.8."""
        state = _make_state(arousal=0.85, relational_significance=0.85)
        _, flashbulb = amygdala.compute_storage_modulation(state)
        assert flashbulb is True

    def test_flashbulb_threshold_arousal_below(self, amygdala: AmygdalaLayer) -> None:
        """Flashbulb should NOT trigger if arousal <= 0.8."""
        state = _make_state(arousal=0.8, relational_significance=0.9)
        _, flashbulb = amygdala.compute_storage_modulation(state)
        assert flashbulb is False  # 0.8 is NOT > 0.8 (strict inequality)

    def test_flashbulb_threshold_significance_below(self, amygdala: AmygdalaLayer) -> None:
        """Flashbulb should NOT trigger if significance <= 0.8."""
        state = _make_state(arousal=0.9, relational_significance=0.8)
        _, flashbulb = amygdala.compute_storage_modulation(state)
        assert flashbulb is False  # 0.8 is NOT > 0.8 (strict inequality)

    def test_high_vulnerability_low_others(self, amygdala: AmygdalaLayer) -> None:
        """High vulnerability with low arousal/significance: moderate storage, no flashbulb."""
        state = _make_state(arousal=0.2, relational_significance=0.1, vulnerability_level=0.9)
        strength, flashbulb = amygdala.compute_storage_modulation(state)
        expected = 0.2 * 0.4 + 0.1 * 0.4 + 0.9 * 0.2  # 0.08 + 0.04 + 0.18 = 0.30
        assert strength == pytest.approx(expected)
        assert flashbulb is False


# ---------------------------------------------------------------------------
# Tests: Decay Modulation
# ---------------------------------------------------------------------------

class TestDecayModulation:
    """Tests for AmygdalaLayer.compute_decay_factor()."""

    def test_flashbulb_barely_decays(self, amygdala: AmygdalaLayer) -> None:
        """Flashbulb memories should barely decay even after many days."""
        state = _make_state(arousal=0.9, relational_significance=0.9)
        factor = amygdala.compute_decay_factor(state, days_elapsed=100)
        # Flashbulb rate = 0.001/day; after 100 days:
        # storage_strength affects it but factor should still be very high
        assert factor > 0.85

    def test_negative_memory_decays_slower(self, amygdala: AmygdalaLayer) -> None:
        """Negative memories (valence < 0.3) should decay slower than neutral."""
        negative_state = _make_state(valence=0.1, arousal=0.4, relational_significance=0.3)
        neutral_state = _make_state(valence=0.5, arousal=0.4, relational_significance=0.3)

        neg_factor = amygdala.compute_decay_factor(negative_state, days_elapsed=10)
        neu_factor = amygdala.compute_decay_factor(neutral_state, days_elapsed=10)

        # Negative decays slower (higher factor after same elapsed time)
        assert neg_factor > neu_factor

    def test_neutral_memory_decays_fastest(self, amygdala: AmygdalaLayer) -> None:
        """Neutral memories (0.3 <= valence <= 0.7) should decay fastest."""
        positive_state = _make_state(valence=0.8, arousal=0.4, relational_significance=0.3)
        neutral_state = _make_state(valence=0.5, arousal=0.4, relational_significance=0.3)

        pos_factor = amygdala.compute_decay_factor(positive_state, days_elapsed=10)
        neu_factor = amygdala.compute_decay_factor(neutral_state, days_elapsed=10)

        # Neutral decays faster (lower factor after same elapsed time)
        assert neu_factor < pos_factor

    def test_no_decay_at_zero_days(self, amygdala: AmygdalaLayer) -> None:
        """At zero days elapsed, decay factor should be 1.0 (no decay)."""
        state = _make_state(valence=0.5, arousal=0.3)
        factor = amygdala.compute_decay_factor(state, days_elapsed=0)
        assert factor == pytest.approx(1.0)

    def test_high_storage_strength_reduces_decay(self, amygdala: AmygdalaLayer) -> None:
        """Higher storage strength should result in slower decay."""
        weak_state = _make_state(
            valence=0.5, arousal=0.1,
            relational_significance=0.1, vulnerability_level=0.1,
        )
        strong_state = _make_state(
            valence=0.5, arousal=0.9,
            relational_significance=0.9, vulnerability_level=0.9,
        )

        weak_factor = amygdala.compute_decay_factor(weak_state, days_elapsed=10)
        strong_factor = amygdala.compute_decay_factor(strong_state, days_elapsed=10)

        # Stronger storage -> slower decay -> higher factor
        assert strong_factor > weak_factor

    def test_decay_factor_clamped_to_zero(self, amygdala: AmygdalaLayer) -> None:
        """Decay factor should never go below 0.0, even after many days."""
        state = _make_state(valence=0.5, arousal=0.1, relational_significance=0.1)
        factor = amygdala.compute_decay_factor(state, days_elapsed=1000)
        assert factor >= 0.0

    def test_decay_factor_clamped_to_one(self, amygdala: AmygdalaLayer) -> None:
        """Decay factor should never exceed 1.0."""
        state = _make_state(valence=0.5)
        factor = amygdala.compute_decay_factor(state, days_elapsed=0)
        assert factor <= 1.0


# ---------------------------------------------------------------------------
# Tests: Cosine Similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    """Tests for the cosine_similarity helper function."""

    def test_identical_vectors(self) -> None:
        """Identical vectors should have similarity 1.0."""
        v = [0.5, 0.3, 0.7, 0.2, 0.8]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        """Orthogonal vectors should have similarity 0.0."""
        a = [1.0, 0.0, 0.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        """Opposite vectors should have similarity -1.0."""
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self) -> None:
        """A zero vector should return 0.0 (avoid division by zero)."""
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_mismatched_lengths_raises(self) -> None:
        """Vectors of different lengths should raise ValueError."""
        with pytest.raises(ValueError, match="same length"):
            cosine_similarity([1, 2], [1, 2, 3])

    def test_known_value(self) -> None:
        """Test a known cosine similarity computation."""
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        # dot = 1*4 + 2*5 + 3*6 = 32
        # |a| = sqrt(14), |b| = sqrt(77)
        # cos = 32 / sqrt(14*77) = 32 / sqrt(1078)
        expected = 32.0 / math.sqrt(1078)
        assert cosine_similarity(a, b) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Tests: Emotional State to Vector
# ---------------------------------------------------------------------------

class TestEmotionalStateToVector:
    """Tests for emotional_state_to_vector()."""

    def test_correct_order(self) -> None:
        """Vector should be [valence, arousal, dominance, rel_sig, vuln]."""
        state = _make_state(
            valence=0.1, arousal=0.2, dominance=0.3,
            relational_significance=0.4, vulnerability_level=0.5,
        )
        vec = emotional_state_to_vector(state)
        assert vec == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_length_is_five(self) -> None:
        """Vector should always have exactly 5 elements."""
        vec = emotional_state_to_vector(_make_state())
        assert len(vec) == 5


# ---------------------------------------------------------------------------
# Tests: Mood-Congruent Retrieval
# ---------------------------------------------------------------------------

class TestMoodCongruentRetriever:
    """Tests for MoodCongruentRetriever.retrieve()."""

    def _make_retriever(
        self,
        semantic_ids: list[str],
        semantic_distances: list[float],
        semantic_documents: list[str],
        semantic_metadatas: list[dict],
        emotional_ids: list[str],
        emotional_embeddings: list[list[float]],
    ) -> MoodCongruentRetriever:
        """Create a MoodCongruentRetriever with mocked dependencies."""
        # Mock embedding service
        embedding_service = AsyncMock()
        embedding_service.embed = AsyncMock(return_value=[0.1] * 1024)

        # Mock semantic collection
        semantic_collection = MagicMock()
        semantic_collection.query = MagicMock(return_value={
            "ids": [semantic_ids],
            "documents": [semantic_documents],
            "distances": [semantic_distances],
            "metadatas": [semantic_metadatas],
        })

        # Mock emotional collection
        emotional_collection = MagicMock()
        emotional_collection.get = MagicMock(return_value={
            "ids": emotional_ids,
            "embeddings": emotional_embeddings,
        })

        return MoodCongruentRetriever(
            embedding_service=embedding_service,
            semantic_collection=semantic_collection,
            emotional_collection=emotional_collection,
        )

    async def test_returns_max_results(self) -> None:
        """Should return at most max_results items."""
        retriever = self._make_retriever(
            semantic_ids=["m1", "m2", "m3", "m4", "m5"],
            semantic_distances=[0.1, 0.2, 0.3, 0.4, 0.5],
            semantic_documents=["a", "b", "c", "d", "e"],
            semantic_metadatas=[{}, {}, {}, {}, {}],
            emotional_ids=["m1", "m2", "m3", "m4", "m5"],
            emotional_embeddings=[
                [0.5, 0.5, 0.5, 0.5, 0.5],
                [0.5, 0.5, 0.5, 0.5, 0.5],
                [0.5, 0.5, 0.5, 0.5, 0.5],
                [0.5, 0.5, 0.5, 0.5, 0.5],
                [0.5, 0.5, 0.5, 0.5, 0.5],
            ],
        )
        results = await retriever.retrieve(
            query="test",
            current_state=_make_state(),
            max_results=3,
        )
        assert len(results) <= 3

    async def test_mood_congruent_bias_boosts_similar(self) -> None:
        """Emotionally similar memories should rank higher than dissimilar."""
        # Memory m1 is emotionally similar to current state (high valence)
        # Memory m2 is emotionally dissimilar (low valence)
        # Both have same semantic distance
        retriever = self._make_retriever(
            semantic_ids=["m1", "m2"],
            semantic_distances=[0.1, 0.1],  # Same semantic distance
            semantic_documents=["happy memory", "sad memory"],
            semantic_metadatas=[{}, {}],
            emotional_ids=["m1", "m2"],
            emotional_embeddings=[
                [0.8, 0.5, 0.5, 0.5, 0.5],  # m1: high valence (similar)
                [0.1, 0.5, 0.5, 0.5, 0.5],  # m2: low valence (dissimilar)
            ],
        )
        current = _make_state(valence=0.8)  # Current: high valence
        results = await retriever.retrieve(
            query="test",
            current_state=current,
            max_results=2,
            alpha=0.5,  # Strong bias to make effect visible
        )
        # m1 (similar emotion) should rank higher than m2 (dissimilar)
        assert results[0]["id"] == "m1"
        assert results[0]["final_score"] > results[1]["final_score"]

    async def test_safety_inversion_surfaces_positive(self) -> None:
        """During crisis, emotionally OPPOSITE memories should rank higher."""
        # Current state: negative (low valence)
        # m1: similar to current (negative) -> should be DEMOTED during crisis
        # m2: opposite (positive) -> should be PROMOTED during crisis
        retriever = self._make_retriever(
            semantic_ids=["m1", "m2"],
            semantic_distances=[0.1, 0.1],
            semantic_documents=["sad memory", "happy memory"],
            semantic_metadatas=[{}, {}],
            emotional_ids=["m1", "m2"],
            emotional_embeddings=[
                [0.1, 0.5, 0.5, 0.5, 0.5],  # m1: negative (similar to current)
                [0.9, 0.5, 0.5, 0.5, 0.5],  # m2: positive (opposite to current)
            ],
        )
        current = _make_state(valence=0.1)  # Crisis: very negative
        results = await retriever.retrieve(
            query="test",
            current_state=current,
            safety_level="critical",  # Safety inversion active
            max_results=2,
            alpha=0.5,
        )
        # m2 (positive, opposite) should rank higher during crisis
        assert results[0]["id"] == "m2"

    async def test_distress_penalty(self) -> None:
        """Sensitive memories should be penalized when user is in distress."""
        retriever = self._make_retriever(
            semantic_ids=["m1", "m2"],
            semantic_distances=[0.1, 0.1],
            semantic_documents=["sensitive topic", "safe topic"],
            semantic_metadatas=[
                {"sensitivity_level": "0.9"},  # m1: highly sensitive
                {"sensitivity_level": "0.1"},  # m2: safe
            ],
            emotional_ids=["m1", "m2"],
            emotional_embeddings=[
                [0.5, 0.5, 0.5, 0.5, 0.5],
                [0.5, 0.5, 0.5, 0.5, 0.5],
            ],
        )
        current = _make_state(valence=0.1)  # Distressed (valence < 0.3)
        results = await retriever.retrieve(
            query="test",
            current_state=current,
            max_results=2,
        )
        # m2 (safe) should rank higher than m1 (sensitive) during distress
        m1_result = next(r for r in results if r["id"] == "m1")
        m2_result = next(r for r in results if r["id"] == "m2")
        assert m2_result["final_score"] > m1_result["final_score"]

    async def test_empty_results(self) -> None:
        """Empty ChromaDB results should return empty list."""
        embedding_service = AsyncMock()
        embedding_service.embed = AsyncMock(return_value=[0.1] * 1024)
        semantic_collection = MagicMock()
        semantic_collection.query = MagicMock(return_value={
            "ids": [[]],
            "documents": [[]],
            "distances": [[]],
            "metadatas": [[]],
        })
        emotional_collection = MagicMock()

        retriever = MoodCongruentRetriever(
            embedding_service=embedding_service,
            semantic_collection=semantic_collection,
            emotional_collection=emotional_collection,
        )
        results = await retriever.retrieve("test", current_state=_make_state())
        assert results == []
```

**What these tests cover:**
- `compute_storage_modulation()`: formula verification, all-zeros, all-ones, flashbulb threshold (both above, arousal boundary, significance boundary), high vulnerability
- `compute_decay_factor()`: flashbulb resilience, negativity bias, neutral fastest, zero days, storage strength effect, clamping to [0, 1]
- `cosine_similarity()`: identical, orthogonal, opposite, zero vector, mismatched lengths, known computation
- `emotional_state_to_vector()`: correct dimension order, length check
- `MoodCongruentRetriever.retrieve()`: max results limit, mood-congruent boost, safety inversion, distress penalty, empty results

---

### Step 4.2: Run the tests

Execute the following command from the project root:

```bash
pytest tests/test_amygdala.py -v
```

**Expected result:** All tests pass. If any test fails, read the error message carefully. The most likely causes are:

1. **ImportError for gwen.models**: Track 002 (data-models) has not been completed yet.
2. **ImportError for gwen.amygdala.layer**: Step 2.1 was not completed. Check that `gwen/amygdala/__init__.py` and `gwen/amygdala/layer.py` both exist.
3. **ImportError for gwen.memory.retrieval**: Step 3.1 was not completed. Check that `gwen/memory/retrieval.py` exists.
4. **Assertion failures**: Compare the test's expected values against the formulas in layer.py and retrieval.py.

---

## Checklist (update after each step)

- [x] Phase 1 complete: gwen/amygdala/__init__.py exists
- [x] Phase 2 complete: gwen/amygdala/layer.py with AmygdalaLayer.compute_storage_modulation() and compute_decay_factor()
- [x] Phase 3 complete: gwen/memory/retrieval.py with MoodCongruentRetriever, cosine_similarity, emotional_state_to_vector
- [x] Phase 4 complete: tests/test_amygdala.py passes with all tests green
