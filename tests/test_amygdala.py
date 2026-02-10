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
        state = _make_state(
            arousal=0.8,
            relational_significance=0.6,
            vulnerability_level=0.4,
        )
        strength, _ = amygdala.compute_storage_modulation(state)
        expected = 0.8 * 0.4 + 0.6 * 0.4 + 0.4 * 0.2
        assert strength == pytest.approx(expected)

    def test_all_zeros(self, amygdala: AmygdalaLayer) -> None:
        state = _make_state(arousal=0.0, relational_significance=0.0, vulnerability_level=0.0)
        strength, flashbulb = amygdala.compute_storage_modulation(state)
        assert strength == pytest.approx(0.0)
        assert flashbulb is False

    def test_all_ones(self, amygdala: AmygdalaLayer) -> None:
        state = _make_state(arousal=1.0, relational_significance=1.0, vulnerability_level=1.0)
        strength, flashbulb = amygdala.compute_storage_modulation(state)
        expected = 1.0 * 0.4 + 1.0 * 0.4 + 1.0 * 0.2
        assert strength == pytest.approx(expected)
        assert flashbulb is True

    def test_flashbulb_threshold_both_above(self, amygdala: AmygdalaLayer) -> None:
        state = _make_state(arousal=0.85, relational_significance=0.85)
        _, flashbulb = amygdala.compute_storage_modulation(state)
        assert flashbulb is True

    def test_flashbulb_threshold_arousal_below(self, amygdala: AmygdalaLayer) -> None:
        state = _make_state(arousal=0.8, relational_significance=0.9)
        _, flashbulb = amygdala.compute_storage_modulation(state)
        assert flashbulb is False  # 0.8 is NOT > 0.8

    def test_flashbulb_threshold_significance_below(self, amygdala: AmygdalaLayer) -> None:
        state = _make_state(arousal=0.9, relational_significance=0.8)
        _, flashbulb = amygdala.compute_storage_modulation(state)
        assert flashbulb is False  # 0.8 is NOT > 0.8

    def test_high_vulnerability_low_others(self, amygdala: AmygdalaLayer) -> None:
        state = _make_state(arousal=0.2, relational_significance=0.1, vulnerability_level=0.9)
        strength, flashbulb = amygdala.compute_storage_modulation(state)
        expected = 0.2 * 0.4 + 0.1 * 0.4 + 0.9 * 0.2
        assert strength == pytest.approx(expected)
        assert flashbulb is False


# ---------------------------------------------------------------------------
# Tests: Decay Modulation
# ---------------------------------------------------------------------------

class TestDecayModulation:
    """Tests for AmygdalaLayer.compute_decay_factor()."""

    def test_flashbulb_barely_decays(self, amygdala: AmygdalaLayer) -> None:
        state = _make_state(arousal=0.9, relational_significance=0.9)
        factor = amygdala.compute_decay_factor(state, days_elapsed=100)
        assert factor > 0.85

    def test_negative_memory_decays_slower(self, amygdala: AmygdalaLayer) -> None:
        negative_state = _make_state(valence=0.1, arousal=0.4, relational_significance=0.3)
        neutral_state = _make_state(valence=0.5, arousal=0.4, relational_significance=0.3)

        neg_factor = amygdala.compute_decay_factor(negative_state, days_elapsed=10)
        neu_factor = amygdala.compute_decay_factor(neutral_state, days_elapsed=10)

        assert neg_factor > neu_factor

    def test_neutral_memory_decays_fastest(self, amygdala: AmygdalaLayer) -> None:
        positive_state = _make_state(valence=0.8, arousal=0.4, relational_significance=0.3)
        neutral_state = _make_state(valence=0.5, arousal=0.4, relational_significance=0.3)

        pos_factor = amygdala.compute_decay_factor(positive_state, days_elapsed=10)
        neu_factor = amygdala.compute_decay_factor(neutral_state, days_elapsed=10)

        assert neu_factor < pos_factor

    def test_no_decay_at_zero_days(self, amygdala: AmygdalaLayer) -> None:
        state = _make_state(valence=0.5, arousal=0.3)
        factor = amygdala.compute_decay_factor(state, days_elapsed=0)
        assert factor == pytest.approx(1.0)

    def test_high_storage_strength_reduces_decay(self, amygdala: AmygdalaLayer) -> None:
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

        assert strong_factor > weak_factor

    def test_decay_factor_clamped_to_zero(self, amygdala: AmygdalaLayer) -> None:
        state = _make_state(valence=0.5, arousal=0.1, relational_significance=0.1)
        factor = amygdala.compute_decay_factor(state, days_elapsed=1000)
        assert factor >= 0.0

    def test_decay_factor_clamped_to_one(self, amygdala: AmygdalaLayer) -> None:
        state = _make_state(valence=0.5)
        factor = amygdala.compute_decay_factor(state, days_elapsed=0)
        assert factor <= 1.0


# ---------------------------------------------------------------------------
# Tests: Cosine Similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    """Tests for the cosine_similarity helper function."""

    def test_identical_vectors(self) -> None:
        v = [0.5, 0.3, 0.7, 0.2, 0.8]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0, 0.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self) -> None:
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            cosine_similarity([1, 2], [1, 2, 3])

    def test_known_value(self) -> None:
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        expected = 32.0 / math.sqrt(1078)
        assert cosine_similarity(a, b) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Tests: Emotional State to Vector
# ---------------------------------------------------------------------------

class TestEmotionalStateToVector:
    """Tests for emotional_state_to_vector()."""

    def test_correct_order(self) -> None:
        state = _make_state(
            valence=0.1, arousal=0.2, dominance=0.3,
            relational_significance=0.4, vulnerability_level=0.5,
        )
        vec = emotional_state_to_vector(state)
        assert vec == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_length_is_five(self) -> None:
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
        embedding_service = AsyncMock()
        embedding_service.embed = AsyncMock(return_value=[0.1] * 1024)

        semantic_collection = MagicMock()
        semantic_collection.query = MagicMock(return_value={
            "ids": [semantic_ids],
            "documents": [semantic_documents],
            "distances": [semantic_distances],
            "metadatas": [semantic_metadatas],
        })

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
        retriever = self._make_retriever(
            semantic_ids=["m1", "m2"],
            semantic_distances=[0.1, 0.1],
            semantic_documents=["happy memory", "sad memory"],
            semantic_metadatas=[{}, {}],
            emotional_ids=["m1", "m2"],
            emotional_embeddings=[
                [0.8, 0.5, 0.5, 0.5, 0.5],
                [0.1, 0.5, 0.5, 0.5, 0.5],
            ],
        )
        current = _make_state(valence=0.8)
        results = await retriever.retrieve(
            query="test",
            current_state=current,
            max_results=2,
            alpha=0.5,
        )
        assert results[0]["id"] == "m1"
        assert results[0]["final_score"] > results[1]["final_score"]

    async def test_safety_inversion_surfaces_positive(self) -> None:
        retriever = self._make_retriever(
            semantic_ids=["m1", "m2"],
            semantic_distances=[0.1, 0.1],
            semantic_documents=["sad memory", "happy memory"],
            semantic_metadatas=[{}, {}],
            emotional_ids=["m1", "m2"],
            emotional_embeddings=[
                [0.1, 0.5, 0.5, 0.5, 0.5],
                [0.9, 0.5, 0.5, 0.5, 0.5],
            ],
        )
        current = _make_state(valence=0.1)
        results = await retriever.retrieve(
            query="test",
            current_state=current,
            safety_level="critical",
            max_results=2,
            alpha=0.5,
        )
        assert results[0]["id"] == "m2"

    async def test_distress_penalty(self) -> None:
        retriever = self._make_retriever(
            semantic_ids=["m1", "m2"],
            semantic_distances=[0.1, 0.1],
            semantic_documents=["sensitive topic", "safe topic"],
            semantic_metadatas=[
                {"sensitivity_level": "0.9"},
                {"sensitivity_level": "0.1"},
            ],
            emotional_ids=["m1", "m2"],
            emotional_embeddings=[
                [0.5, 0.5, 0.5, 0.5, 0.5],
                [0.5, 0.5, 0.5, 0.5, 0.5],
            ],
        )
        current = _make_state(valence=0.1)
        results = await retriever.retrieve(
            query="test",
            current_state=current,
            max_results=2,
        )
        m1_result = next(r for r in results if r["id"] == "m1")
        m2_result = next(r for r in results if r["id"] == "m2")
        assert m2_result["final_score"] > m1_result["final_score"]

    async def test_empty_results(self) -> None:
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
