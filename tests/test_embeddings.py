"""Tests for the EmbeddingService.

Tests are split into two groups:
1. Unit tests that do NOT require Ollama (emotional embeddings, ChromaDB storage with fake data)
2. Integration tests that DO require Ollama (semantic embeddings) -- marked with @pytest.mark.ollama

Run all tests:           pytest tests/test_embeddings.py
Run without Ollama:      pytest tests/test_embeddings.py -m "not ollama"
Run only Ollama tests:   pytest tests/test_embeddings.py -m ollama
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from unittest.mock import patch

import chromadb
import pytest

from gwen.memory.embeddings import EmbeddingService


# ---------------------------------------------------------------------------
# Minimal stub types for testing.
# ---------------------------------------------------------------------------

class CompassDirection(Enum):
    NONE = "none"
    NORTH = "presence"
    SOUTH = "currents"
    WEST = "anchoring"
    EAST = "bridges"


@dataclass
class FakeEmotionalStateVector:
    valence: float = 0.5
    arousal: float = 0.5
    dominance: float = 0.5
    relational_significance: float = 0.5
    vulnerability_level: float = 0.5
    compass_direction: CompassDirection = CompassDirection.NONE

    @property
    def storage_strength(self) -> float:
        return self.arousal * 0.4 + self.relational_significance * 0.4 + self.vulnerability_level * 0.2

    @property
    def is_flashbulb(self) -> bool:
        return self.arousal > 0.8 and self.relational_significance > 0.8


@dataclass
class FakeMessageRecord:
    id: str = ""
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    sender: str = "user"
    content: str = ""
    emotional_state: FakeEmotionalStateVector = field(default_factory=FakeEmotionalStateVector)
    storage_strength: float = 0.5
    is_flashbulb: bool = False
    compass_direction: CompassDirection = CompassDirection.NONE
    semantic_embedding_id: Optional[str] = None
    emotional_embedding_id: Optional[str] = None


def make_message(content: str = "Hello, how are you?", **overrides) -> FakeMessageRecord:
    defaults = {
        "id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "timestamp": datetime.now(),
        "sender": "user",
        "content": content,
        "emotional_state": FakeEmotionalStateVector(
            valence=0.65, arousal=0.45, dominance=0.50,
            relational_significance=0.70, vulnerability_level=0.30,
        ),
        "storage_strength": 0.5,
        "is_flashbulb": False,
        "compass_direction": CompassDirection.NONE,
    }
    defaults.update(overrides)
    return FakeMessageRecord(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def chromadb_client():
    """Create an in-memory ChromaDB client for testing."""
    client = chromadb.Client()
    # Delete any pre-existing collections for test isolation
    for col in client.list_collections():
        client.delete_collection(col.name)
    return client


@pytest.fixture
def embedding_service(chromadb_client):
    """Create an EmbeddingService backed by the in-memory ChromaDB client."""
    return EmbeddingService(chromadb_client=chromadb_client)


# ---------------------------------------------------------------------------
# Unit tests (no Ollama required)
# ---------------------------------------------------------------------------

class TestEmotionalEmbedding:
    """Tests for generate_emotional_embedding (pure computation, no model)."""

    def test_returns_5_dimensions(self, embedding_service):
        state = FakeEmotionalStateVector(
            valence=0.7, arousal=0.3, dominance=0.5,
            relational_significance=0.8, vulnerability_level=0.2,
        )
        result = embedding_service.generate_emotional_embedding(state)
        assert isinstance(result, list)
        assert len(result) == 5

    def test_dimensions_match_state_values(self, embedding_service):
        state = FakeEmotionalStateVector(
            valence=0.1, arousal=0.9, dominance=0.4,
            relational_significance=0.6, vulnerability_level=0.8,
        )
        result = embedding_service.generate_emotional_embedding(state)
        assert result[0] == 0.1
        assert result[1] == 0.9
        assert result[2] == 0.4
        assert result[3] == 0.6
        assert result[4] == 0.8

    def test_extreme_low_values(self, embedding_service):
        state = FakeEmotionalStateVector(
            valence=0.0, arousal=0.0, dominance=0.0,
            relational_significance=0.0, vulnerability_level=0.0,
        )
        result = embedding_service.generate_emotional_embedding(state)
        assert result == [0.0, 0.0, 0.0, 0.0, 0.0]

    def test_extreme_high_values(self, embedding_service):
        state = FakeEmotionalStateVector(
            valence=1.0, arousal=1.0, dominance=1.0,
            relational_significance=1.0, vulnerability_level=1.0,
        )
        result = embedding_service.generate_emotional_embedding(state)
        assert result == [1.0, 1.0, 1.0, 1.0, 1.0]


class TestStoreEmbeddings:
    """Tests for store_embeddings using a mocked Ollama call."""

    @pytest.fixture
    def fake_semantic_embedding(self):
        return [0.01 * i for i in range(1024)]

    @pytest.mark.asyncio
    async def test_stores_both_embeddings_in_chromadb(
        self, embedding_service, fake_semantic_embedding
    ):
        message = make_message("I had a really great day today!")
        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_semantic_embedding
        ):
            await embedding_service.store_embeddings(message)
        assert embedding_service.semantic_collection.count() == 1
        assert embedding_service.emotional_collection.count() == 1

    @pytest.mark.asyncio
    async def test_semantic_metadata_fields(
        self, embedding_service, fake_semantic_embedding
    ):
        message = make_message("Testing metadata fields")
        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_semantic_embedding
        ):
            await embedding_service.store_embeddings(message)
        result = embedding_service.semantic_collection.get(
            ids=[message.id], include=["metadatas"]
        )
        metadata = result["metadatas"][0]
        assert metadata["session_id"] == message.session_id
        assert metadata["sender"] == "user"
        assert metadata["embedding_model"] == "qwen3-embedding:0.6b"
        assert metadata["embedding_dim"] == 1024
        assert "timestamp" in metadata
        assert "valence" in metadata
        assert "arousal" in metadata
        assert "storage_strength" in metadata

    @pytest.mark.asyncio
    async def test_emotional_metadata_fields(
        self, embedding_service, fake_semantic_embedding
    ):
        message = make_message("Testing emotional metadata")
        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_semantic_embedding
        ):
            await embedding_service.store_embeddings(message)
        emo_id = f"{message.id}_emo"
        result = embedding_service.emotional_collection.get(
            ids=[emo_id], include=["metadatas"]
        )
        metadata = result["metadatas"][0]
        assert metadata["session_id"] == message.session_id
        assert "timestamp" in metadata
        assert metadata["compass_direction"] == "none"

    @pytest.mark.asyncio
    async def test_updates_message_embedding_ids(
        self, embedding_service, fake_semantic_embedding
    ):
        message = make_message("ID update test")
        assert message.semantic_embedding_id is None
        assert message.emotional_embedding_id is None
        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_semantic_embedding
        ):
            await embedding_service.store_embeddings(message)
        assert message.semantic_embedding_id == message.id
        assert message.emotional_embedding_id == f"{message.id}_emo"


class TestSearchSimilar:
    """Tests for search_similar using mocked embeddings."""

    @pytest.mark.asyncio
    async def test_search_returns_stored_messages(self, embedding_service):
        fake_embedding = [0.01 * i for i in range(1024)]
        message = make_message("The weather is beautiful today")
        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_embedding
        ):
            await embedding_service.store_embeddings(message)
            results = await embedding_service.search_similar(
                "The weather is beautiful today", n_results=5
            )
        assert len(results) >= 1
        assert results[0]["id"] == message.id
        assert results[0]["document"] == "The weather is beautiful today"
        assert results[0]["distance"] is not None

    @pytest.mark.asyncio
    async def test_search_empty_collection_returns_empty(self, embedding_service):
        fake_embedding = [0.0] * 1024
        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_embedding
        ):
            results = await embedding_service.search_similar("anything", n_results=5)
        assert results == []


class TestSearchByEmotion:
    """Tests for search_by_emotion using mocked embeddings."""

    @pytest.mark.asyncio
    async def test_emotional_search_returns_similar_states(self, embedding_service):
        fake_embedding = [0.5] * 1024
        state = FakeEmotionalStateVector(
            valence=0.7, arousal=0.3, dominance=0.5,
            relational_significance=0.8, vulnerability_level=0.2,
        )
        message = make_message(
            "Feeling calm and connected",
            emotional_state=state,
            compass_direction=CompassDirection.NONE,
        )
        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_embedding
        ):
            await embedding_service.store_embeddings(message)
        similar_state = FakeEmotionalStateVector(
            valence=0.65, arousal=0.35, dominance=0.5,
            relational_significance=0.75, vulnerability_level=0.25,
        )
        results = await embedding_service.search_by_emotion(similar_state, n_results=5)
        assert len(results) >= 1
        assert results[0]["id"] == f"{message.id}_emo"


# ---------------------------------------------------------------------------
# Integration tests (require Ollama with qwen3-embedding:0.6b loaded)
# ---------------------------------------------------------------------------

@pytest.mark.ollama
class TestSemanticEmbeddingIntegration:

    @pytest.mark.asyncio
    async def test_real_embedding_is_1024_dim(self, embedding_service):
        result = await embedding_service.generate_semantic_embedding("Hello, world!")
        assert isinstance(result, list)
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_similar_texts_have_high_similarity(self, embedding_service):
        emb1 = await embedding_service.generate_semantic_embedding("I feel really happy today")
        emb2 = await embedding_service.generate_semantic_embedding("Today I am feeling joyful")
        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        norm1 = sum(a * a for a in emb1) ** 0.5
        norm2 = sum(b * b for b in emb2) ** 0.5
        cosine_sim = dot_product / (norm1 * norm2) if (norm1 * norm2) > 0 else 0.0
        assert cosine_sim > 0.7, f"Expected similarity > 0.7, got {cosine_sim:.4f}"

    @pytest.mark.asyncio
    async def test_dissimilar_texts_have_lower_similarity(self, embedding_service):
        emb1 = await embedding_service.generate_semantic_embedding("I need to fix the kitchen sink")
        emb2 = await embedding_service.generate_semantic_embedding(
            "The philosophical implications of quantum mechanics"
        )
        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        norm1 = sum(a * a for a in emb1) ** 0.5
        norm2 = sum(b * b for b in emb2) ** 0.5
        cosine_sim = dot_product / (norm1 * norm2) if (norm1 * norm2) > 0 else 0.0
        assert cosine_sim < 0.7, f"Expected similarity < 0.7, got {cosine_sim:.4f}"
