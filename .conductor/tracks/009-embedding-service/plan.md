# Plan: Embedding Service

**Track:** 009-embedding-service
**Spec:** [spec.md](./spec.md)
**Status:** Not Started

---

## Phase 1: Embedding Service

### Step 1.1: Create EmbeddingService class with constructor

Create the file `gwen/memory/embeddings.py` (path: `C:\Users\Administrator\Desktop\projects\Gwen\gwen\memory\embeddings.py`).

- [x]Write EmbeddingService class with __init__ and constants

```python
"""Embedding generation and storage for the Living Memory system.

Generates two types of embeddings for every message:
1. Semantic embeddings (1024-dim) via qwen3-embedding:0.6b through Ollama /api/embed
2. Emotional embeddings (5-dim) via direct encoding of EmotionalStateVector dimensions

Both are stored in ChromaDB for retrieval by the memory system.
References: SRS.md FR-MEM-006, OQ-001, OQ-008.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
from datetime import datetime
from typing import TYPE_CHECKING

import chromadb

if TYPE_CHECKING:
    from gwen.models.emotional import EmotionalStateVector
    from gwen.models.message import MessageRecord

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates and stores embeddings for memory retrieval.

    Semantic: qwen3-embedding:0.6b via Ollama (1024-dim)
    Emotional: Direct 5D vector from EmotionalStateVector (no model needed)

    Usage:
        service = EmbeddingService(chromadb_client=client)
        await service.store_embeddings(message)
        results = await service.search_similar("some query", n_results=5)
    """

    EMBEDDING_MODEL = "qwen3-embedding:0.6b"
    EMBEDDING_DIM = 1024
    EMOTIONAL_DIM = 5
    OLLAMA_HOST = "http://localhost:11434"

    def __init__(self, chromadb_client: chromadb.ClientAPI, ollama_host: str | None = None):
        """Initialize the EmbeddingService.

        Args:
            chromadb_client: A ChromaDB client instance (PersistentClient or Client).
                             This is the same client initialized in Track 003 (database layer).
                             It should already be configured with the correct persist directory.
            ollama_host: Optional override for the Ollama server URL.
                         Defaults to "http://localhost:11434".
                         Only change this if Ollama is running on a non-default port.
        """
        if ollama_host is not None:
            self.OLLAMA_HOST = ollama_host

        # Get or create the two ChromaDB collections.
        # "get_or_create" is idempotent -- safe to call on every startup.
        # The "semantic_embeddings" collection stores 1024-dim vectors from qwen3-embedding:0.6b.
        # The "emotional_embeddings" collection stores 5-dim vectors from direct ESV encoding.
        self.semantic_collection = chromadb_client.get_or_create_collection(
            name="semantic_embeddings",
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity for semantic search
        )
        self.emotional_collection = chromadb_client.get_or_create_collection(
            name="emotional_embeddings",
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity for emotional search
        )

        logger.info(
            "EmbeddingService initialized. Semantic collection: %d items, Emotional collection: %d items",
            self.semantic_collection.count(),
            self.emotional_collection.count(),
        )
```

**What this does:** Creates the `EmbeddingService` class with its constructor. The constructor takes a ChromaDB client (created in Track 003) and an optional Ollama host override. It creates or retrieves two ChromaDB collections: one for 1024-dim semantic embeddings and one for 5-dim emotional embeddings. Both collections use cosine similarity, which is the standard metric for embedding comparison. The `get_or_create_collection` call is idempotent, meaning it is safe to call every time the application starts.

**Why `TYPE_CHECKING`:** We import `EmotionalStateVector` and `MessageRecord` inside an `if TYPE_CHECKING` block to avoid circular imports at runtime. These types are only needed for type hints, not at runtime. The actual objects will be passed in as arguments.

---

### Step 1.2: Implement generate_semantic_embedding

Add this method to the `EmbeddingService` class in `gwen/memory/embeddings.py`, directly after the `__init__` method.

- [x]Add generate_semantic_embedding method

```python
    async def generate_semantic_embedding(self, text: str) -> list[float]:
        """Generate a 1024-dim semantic embedding via Ollama /api/embed.

        This calls the Ollama embedding endpoint with the qwen3-embedding:0.6b model.
        The call is made using urllib (stdlib) to avoid adding an HTTP client dependency.
        It is wrapped in asyncio.to_thread() so that the blocking HTTP call does not
        block the event loop.

        Args:
            text: The text to generate an embedding for. Can be any length, but
                  shorter texts (single messages) produce the most meaningful embeddings.

        Returns:
            A list of 1024 floats representing the semantic embedding vector.

        Raises:
            urllib.error.URLError: If the Ollama server is not reachable.
            KeyError: If the Ollama response format is unexpected.
            IndexError: If the Ollama response contains no embeddings.
        """
        # _call_ollama_embed is a blocking function (uses urllib).
        # We run it in a thread so it does not block the async event loop.
        return await asyncio.to_thread(self._call_ollama_embed, text)

    def _call_ollama_embed(self, text: str) -> list[float]:
        """Synchronous helper that calls Ollama /api/embed.

        This is separated from the async method so it can be run in a thread via
        asyncio.to_thread(). Do NOT call this directly from async code — use
        generate_semantic_embedding() instead.

        Args:
            text: The text to embed.

        Returns:
            A list of 1024 floats.
        """
        payload = json.dumps({
            "model": self.EMBEDDING_MODEL,
            "input": text
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.OLLAMA_HOST}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            embedding = result["embeddings"][0]

        # Sanity check: verify we got the expected dimensionality.
        if len(embedding) != self.EMBEDDING_DIM:
            logger.warning(
                "Expected %d-dim embedding, got %d-dim. Model may have changed.",
                self.EMBEDDING_DIM,
                len(embedding),
            )

        return embedding
```

**What this does:** Implements semantic embedding generation by calling the Ollama `/api/embed` endpoint. The actual HTTP call is synchronous (using `urllib.request` from the stdlib, so we do not add any new dependencies). We wrap it in `asyncio.to_thread()` so the blocking I/O does not stall the event loop. The method returns a list of 1024 floats.

**Why `asyncio.to_thread` instead of aiohttp:** The SRS reference implementation uses `urllib.request`, and the project dependencies (from Track 001's `pyproject.toml`) do not include `aiohttp` or `httpx`. Using `asyncio.to_thread` is the simplest way to make a blocking stdlib call non-blocking without adding a new dependency.

**Why a 30-second timeout:** The Ollama server may need to load the embedding model into memory on the first call. After warmup, typical latency is 100-150ms per embedding (SRS OQ-008). The 30-second timeout gives plenty of room for cold starts.

---

### Step 1.3: Implement generate_emotional_embedding

Add this method to the `EmbeddingService` class in `gwen/memory/embeddings.py`, directly after the `_call_ollama_embed` method.

- [x]Add generate_emotional_embedding method

```python
    def generate_emotional_embedding(self, state: EmotionalStateVector) -> list[float]:
        """Encode an EmotionalStateVector into a 5D embedding.

        Direct dimensional encoding -- interpretable and requires no training data.
        The 5D space is sufficient for mood-congruent retrieval (resolved OQ-001).

        The dimensions are, in order:
          [0] valence              (0.0 = extremely negative, 1.0 = extremely positive)
          [1] arousal              (0.0 = calm/lethargic, 1.0 = highly activated)
          [2] dominance            (0.0 = helpless, 1.0 = in-control)
          [3] relational_significance  (0.0 = routine, 1.0 = deeply significant)
          [4] vulnerability_level  (0.0 = guarded, 1.0 = fully open)

        This is pure computation. No model call is needed.

        Args:
            state: An EmotionalStateVector instance (from Track 002 data models).

        Returns:
            A list of 5 floats, each in the range [0.0, 1.0].
        """
        return [
            state.valence,
            state.arousal,
            state.dominance,
            state.relational_significance,
            state.vulnerability_level,
        ]
```

**What this does:** Converts an `EmotionalStateVector` dataclass into a 5-element list of floats. This is the "emotional embedding" that gets stored in the `emotional_embeddings` ChromaDB collection. It is a direct encoding -- no model inference required -- which means it is instant and deterministic. The 5D emotional space gives 32 possible "quadrants" (2^5), which provides sufficient granularity for mood-congruent retrieval as decided in SRS OQ-001.

---

### Step 1.4: Implement store_embeddings

Add this method to the `EmbeddingService` class in `gwen/memory/embeddings.py`, directly after the `generate_emotional_embedding` method.

- [x]Add store_embeddings method

```python
    async def store_embeddings(self, message: MessageRecord) -> None:
        """Generate both embeddings and store them in ChromaDB.

        This is the main entry point for embedding a message. It:
        1. Generates the 1024-dim semantic embedding via Ollama (async)
        2. Generates the 5-dim emotional embedding (sync, instant)
        3. Stores both in their respective ChromaDB collections with full metadata
        4. Updates the message's embedding ID fields so downstream code knows
           the embeddings exist

        Args:
            message: A fully populated MessageRecord. Must have at minimum:
                     - id (str): UUID for the message
                     - session_id (str): UUID for the session
                     - timestamp (datetime): when the message was created
                     - sender (str): "user" or "companion"
                     - content (str): the message text
                     - emotional_state (EmotionalStateVector): from Tier 0 classification
                     - storage_strength (float): from EmotionalStateVector.storage_strength
                     - compass_direction (CompassDirection): from classification

        Side effects:
            - message.semantic_embedding_id is set to message.id
            - message.emotional_embedding_id is set to "{message.id}_emo"
        """
        # --- 1. Generate semantic embedding (async, calls Ollama) ---
        semantic = await self.generate_semantic_embedding(message.content)

        # --- 2. Generate emotional embedding (sync, instant) ---
        emotional = self.generate_emotional_embedding(message.emotional_state)

        # --- 3. Store semantic embedding in ChromaDB ---
        # The ID is the message UUID. This means one semantic embedding per message.
        # The metadata dict allows filtering during retrieval (e.g., by session, by sender).
        self.semantic_collection.add(
            ids=[message.id],
            embeddings=[semantic],
            metadatas=[{
                "session_id": message.session_id,
                "timestamp": message.timestamp.isoformat(),
                "sender": message.sender,
                "valence": message.emotional_state.valence,
                "arousal": message.emotional_state.arousal,
                "storage_strength": message.storage_strength,
                "embedding_model": self.EMBEDDING_MODEL,
                "embedding_dim": self.EMBEDDING_DIM,
            }],
            documents=[message.content],
        )

        # --- 4. Store emotional embedding in ChromaDB ---
        # The ID is "{message_id}_emo" to distinguish it from the semantic embedding.
        # This collection is used for mood-congruent retrieval (Section 4.5.1).
        self.emotional_collection.add(
            ids=[f"{message.id}_emo"],
            embeddings=[emotional],
            metadatas=[{
                "session_id": message.session_id,
                "timestamp": message.timestamp.isoformat(),
                "compass_direction": message.compass_direction.value,
            }],
        )

        # --- 5. Update the message's embedding references ---
        # These fields are Optional[str] on the MessageRecord dataclass (Track 002).
        # Setting them here signals to downstream code that embeddings have been generated.
        message.semantic_embedding_id = message.id
        message.emotional_embedding_id = f"{message.id}_emo"

        logger.debug(
            "Stored embeddings for message %s (semantic: %d-dim, emotional: %d-dim)",
            message.id,
            len(semantic),
            len(emotional),
        )
```

**What this does:** This is the main workhorse method. For a given `MessageRecord`, it generates both embedding types and stores them in ChromaDB. The semantic embedding is stored with rich metadata (session ID, timestamp, sender, emotional dimensions, model info) that enables filtered queries later. The emotional embedding is stored with lighter metadata. After storage, it updates the message's `semantic_embedding_id` and `emotional_embedding_id` fields so the Chronicle (SQLite) record can reference them.

**Why `documents=[message.content]`:** ChromaDB stores both the embedding vector and the original document text. This allows `query_texts` searches (where ChromaDB generates the embedding internally) and also lets us retrieve the original text alongside results without a separate database lookup.

**Why metadata includes `valence` and `arousal` but not all 5 dimensions:** The semantic collection metadata is for filtering, not for emotional search. If a downstream query wants to find "all messages with valence > 0.7", it can filter on metadata. The full 5D emotional comparison is done through the `emotional_embeddings` collection instead.

---

## Phase 2: Similarity Search Helpers

### Step 2.1: Implement search_similar

Add this method to the `EmbeddingService` class in `gwen/memory/embeddings.py`, directly after the `store_embeddings` method.

- [x]Add search_similar method

```python
    async def search_similar(
        self,
        query_text: str,
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[dict]:
        """Search for semantically similar messages.

        Generates an embedding for the query text using the same qwen3-embedding:0.6b
        model, then queries the semantic_embeddings collection for the nearest neighbors.

        Args:
            query_text: The text to search for. This is typically the user's current
                        message, but can be any text string.
            n_results: Maximum number of results to return. Defaults to 10.
                       ChromaDB returns results sorted by distance (closest first).
            where: Optional ChromaDB metadata filter dict. Examples:
                   {"sender": "user"} -- only user messages
                   {"session_id": "abc-123"} -- only messages from a specific session
                   See ChromaDB docs for filter syntax.

        Returns:
            A list of dicts, each containing:
                - "id" (str): The message UUID
                - "document" (str): The original message text
                - "distance" (float): Cosine distance (0.0 = identical, 2.0 = opposite)
                - "metadata" (dict): The metadata stored with the embedding
            Results are sorted by distance (closest first).
            Returns an empty list if no results are found or if an error occurs.
        """
        try:
            # Generate embedding for the query text
            query_embedding = await self.generate_semantic_embedding(query_text)

            # Build query kwargs
            query_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["documents", "distances", "metadatas"],
            }
            if where is not None:
                query_kwargs["where"] = where

            # Query ChromaDB
            raw_results = self.semantic_collection.query(**query_kwargs)

            # ChromaDB returns results in a nested structure:
            # {"ids": [[...]], "documents": [[...]], "distances": [[...]], "metadatas": [[...]]}
            # We flatten this into a list of dicts for easier consumption.
            results = []
            if raw_results["ids"] and raw_results["ids"][0]:
                for i, msg_id in enumerate(raw_results["ids"][0]):
                    results.append({
                        "id": msg_id,
                        "document": raw_results["documents"][0][i] if raw_results["documents"] else None,
                        "distance": raw_results["distances"][0][i] if raw_results["distances"] else None,
                        "metadata": raw_results["metadatas"][0][i] if raw_results["metadatas"] else None,
                    })

            return results

        except Exception:
            logger.exception("Error during semantic search for query: %s", query_text[:100])
            return []
```

**What this does:** Takes a text query, generates its semantic embedding, and queries ChromaDB for the closest matches. The results are flattened from ChromaDB's nested list format into a simple list of dicts. The optional `where` parameter allows metadata filtering (e.g., restrict results to a specific session or sender).

**Why we catch all exceptions:** If the Ollama server is down or ChromaDB has an issue, we do not want search failures to crash the conversation. The caller (Context Assembler, Track 010) will handle an empty result list gracefully.

---

### Step 2.2: Implement search_by_emotion

Add this method to the `EmbeddingService` class in `gwen/memory/embeddings.py`, directly after the `search_similar` method.

- [x]Add search_by_emotion method

```python
    async def search_by_emotion(
        self,
        state: EmotionalStateVector,
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[dict]:
        """Search for messages with similar emotional states.

        Uses the 5D emotional embedding to find messages where the user (or companion)
        was in a similar emotional state. This is used by the mood-congruent retrieval
        system (SRS Section 4.5.1).

        Args:
            state: The EmotionalStateVector to search for. Typically the user's current
                   emotional state from Tier 0 classification.
            n_results: Maximum number of results to return. Defaults to 10.
            where: Optional ChromaDB metadata filter dict. Example:
                   {"compass_direction": "anchoring"} -- only WEST/anchoring messages

        Returns:
            A list of dicts, each containing:
                - "id" (str): The emotional embedding ID ("{message_id}_emo")
                - "distance" (float): Cosine distance in the 5D emotional space
                - "metadata" (dict): The metadata stored with the embedding
            Results are sorted by distance (closest first).
            Returns an empty list if no results are found or if an error occurs.
        """
        try:
            # Generate the 5D emotional embedding (instant, no model call)
            query_embedding = self.generate_emotional_embedding(state)

            # Build query kwargs
            query_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["distances", "metadatas"],
            }
            if where is not None:
                query_kwargs["where"] = where

            # Query the emotional_embeddings collection
            raw_results = self.emotional_collection.query(**query_kwargs)

            # Flatten results
            results = []
            if raw_results["ids"] and raw_results["ids"][0]:
                for i, emo_id in enumerate(raw_results["ids"][0]):
                    results.append({
                        "id": emo_id,
                        "distance": raw_results["distances"][0][i] if raw_results["distances"] else None,
                        "metadata": raw_results["metadatas"][0][i] if raw_results["metadatas"] else None,
                    })

            return results

        except Exception:
            logger.exception("Error during emotional search")
            return []
```

**What this does:** Takes an `EmotionalStateVector`, converts it to a 5D embedding, and queries the `emotional_embeddings` collection for nearest neighbors. This powers the mood-congruent retrieval described in SRS Section 4.5.1 -- when the user is sad, the system retrieves memories from times they were also sad (or, during safety events, memories from when they felt better). Note that this returns emotional embedding IDs (format: `{message_id}_emo`), not message IDs directly. The caller can strip the `_emo` suffix to get the original message ID.

---

## Phase 3: Tests

### Step 3.1: Create tests/test_embeddings.py

Create the file `tests/test_embeddings.py` (path: `C:\Users\Administrator\Desktop\projects\Gwen\tests\test_embeddings.py`).

- [x]Write test file for EmbeddingService

```python
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
from unittest.mock import AsyncMock, MagicMock, patch

import chromadb
import pytest

from gwen.memory.embeddings import EmbeddingService


# ---------------------------------------------------------------------------
# Minimal stub types for testing.
# These mirror the real data models from Track 002 but are self-contained
# so this test file does not depend on the full model package being complete.
# Once Track 002 is implemented, these stubs can be replaced with real imports.
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
    """Factory function to create a FakeMessageRecord with sensible defaults."""
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
    """Create an in-memory ChromaDB client for testing.

    This client does NOT persist to disk. It is created fresh for every test
    function and discarded after. This ensures test isolation.
    """
    return chromadb.Client()


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
        """Emotional embedding must always return exactly 5 floats."""
        state = FakeEmotionalStateVector(
            valence=0.7, arousal=0.3, dominance=0.5,
            relational_significance=0.8, vulnerability_level=0.2,
        )
        result = embedding_service.generate_emotional_embedding(state)

        assert isinstance(result, list)
        assert len(result) == 5

    def test_dimensions_match_state_values(self, embedding_service):
        """Each dimension of the emotional embedding must exactly match
        the corresponding EmotionalStateVector field."""
        state = FakeEmotionalStateVector(
            valence=0.1, arousal=0.9, dominance=0.4,
            relational_significance=0.6, vulnerability_level=0.8,
        )
        result = embedding_service.generate_emotional_embedding(state)

        assert result[0] == 0.1   # valence
        assert result[1] == 0.9   # arousal
        assert result[2] == 0.4   # dominance
        assert result[3] == 0.6   # relational_significance
        assert result[4] == 0.8   # vulnerability_level

    def test_extreme_low_values(self, embedding_service):
        """All dimensions at 0.0 should produce a zero vector."""
        state = FakeEmotionalStateVector(
            valence=0.0, arousal=0.0, dominance=0.0,
            relational_significance=0.0, vulnerability_level=0.0,
        )
        result = embedding_service.generate_emotional_embedding(state)
        assert result == [0.0, 0.0, 0.0, 0.0, 0.0]

    def test_extreme_high_values(self, embedding_service):
        """All dimensions at 1.0 should produce a ones vector."""
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
        """A fake 1024-dim embedding vector for mocking Ollama responses."""
        return [0.01 * i for i in range(1024)]

    async def test_stores_both_embeddings_in_chromadb(
        self, embedding_service, fake_semantic_embedding
    ):
        """After store_embeddings, both ChromaDB collections should contain one entry."""
        message = make_message("I had a really great day today!")

        # Mock the Ollama call so we do not need a running server.
        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_semantic_embedding
        ):
            await embedding_service.store_embeddings(message)

        # Verify semantic collection has the entry
        assert embedding_service.semantic_collection.count() == 1

        # Verify emotional collection has the entry
        assert embedding_service.emotional_collection.count() == 1

    async def test_semantic_metadata_fields(
        self, embedding_service, fake_semantic_embedding
    ):
        """The semantic embedding metadata must contain all required fields."""
        message = make_message("Testing metadata fields")

        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_semantic_embedding
        ):
            await embedding_service.store_embeddings(message)

        # Retrieve the stored entry
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

    async def test_emotional_metadata_fields(
        self, embedding_service, fake_semantic_embedding
    ):
        """The emotional embedding metadata must contain session_id, timestamp,
        and compass_direction."""
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

    async def test_updates_message_embedding_ids(
        self, embedding_service, fake_semantic_embedding
    ):
        """After store_embeddings, message.semantic_embedding_id and
        message.emotional_embedding_id should be set."""
        message = make_message("ID update test")

        # Verify they start as None
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

    async def test_search_returns_stored_messages(self, embedding_service):
        """Storing a message and then searching for similar text should return it."""
        fake_embedding = [0.01 * i for i in range(1024)]
        message = make_message("The weather is beautiful today")

        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_embedding
        ):
            await embedding_service.store_embeddings(message)

            # Search for the same text (should get distance ~0)
            results = await embedding_service.search_similar(
                "The weather is beautiful today", n_results=5
            )

        assert len(results) >= 1
        assert results[0]["id"] == message.id
        assert results[0]["document"] == "The weather is beautiful today"
        assert results[0]["distance"] is not None

    async def test_search_empty_collection_returns_empty(self, embedding_service):
        """Searching an empty collection should return an empty list, not an error."""
        fake_embedding = [0.0] * 1024

        with patch.object(
            embedding_service, "_call_ollama_embed", return_value=fake_embedding
        ):
            results = await embedding_service.search_similar("anything", n_results=5)

        assert results == []


class TestSearchByEmotion:
    """Tests for search_by_emotion using mocked embeddings."""

    async def test_emotional_search_returns_similar_states(self, embedding_service):
        """Storing a message and searching for a similar emotional state should find it."""
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

        # Search for a similar emotional state
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
    """Integration tests that call the real Ollama /api/embed endpoint.

    These tests require:
    1. A running Ollama server at http://localhost:11434
    2. The qwen3-embedding:0.6b model pulled (run: ollama pull qwen3-embedding:0.6b)

    Skip these tests in environments without Ollama:
        pytest tests/test_embeddings.py -m "not ollama"
    """

    async def test_real_embedding_is_1024_dim(self, embedding_service):
        """A real Ollama embedding should return exactly 1024 dimensions."""
        result = await embedding_service.generate_semantic_embedding("Hello, world!")

        assert isinstance(result, list)
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)

    async def test_similar_texts_have_high_similarity(self, embedding_service):
        """Semantically similar texts should have cosine similarity > 0.7."""
        emb1 = await embedding_service.generate_semantic_embedding("I feel really happy today")
        emb2 = await embedding_service.generate_semantic_embedding("Today I am feeling joyful")

        # Compute cosine similarity manually
        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        norm1 = sum(a * a for a in emb1) ** 0.5
        norm2 = sum(b * b for b in emb2) ** 0.5
        cosine_sim = dot_product / (norm1 * norm2) if (norm1 * norm2) > 0 else 0.0

        assert cosine_sim > 0.7, f"Expected similarity > 0.7, got {cosine_sim:.4f}"

    async def test_dissimilar_texts_have_lower_similarity(self, embedding_service):
        """Semantically dissimilar texts should have cosine similarity < 0.7."""
        emb1 = await embedding_service.generate_semantic_embedding("I need to fix the kitchen sink")
        emb2 = await embedding_service.generate_semantic_embedding(
            "The philosophical implications of quantum mechanics"
        )

        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        norm1 = sum(a * a for a in emb1) ** 0.5
        norm2 = sum(b * b for b in emb2) ** 0.5
        cosine_sim = dot_product / (norm1 * norm2) if (norm1 * norm2) > 0 else 0.0

        assert cosine_sim < 0.7, f"Expected similarity < 0.7, got {cosine_sim:.4f}"
```

**What this file does:** Provides comprehensive tests for the EmbeddingService. Unit tests use fake stub types and mock the Ollama HTTP call, so they run without any external dependencies. Integration tests (marked `@pytest.mark.ollama`) call the real Ollama server and verify real embedding properties. The test stubs (`FakeEmotionalStateVector`, `FakeMessageRecord`) mirror the data model interfaces without importing the real models, avoiding circular dependency issues during early development.

---

### Step 3.2: Run pytest

Run this command from the project root (`C:\Users\Administrator\Desktop\projects\Gwen\`):

- [x]Run `pytest tests/test_embeddings.py -m "not ollama" -v` and confirm all unit tests pass

```bash
pytest tests/test_embeddings.py -m "not ollama" -v
```

**Expected output:** All tests in `TestEmotionalEmbedding`, `TestStoreEmbeddings`, `TestSearchSimilar`, and `TestSearchByEmotion` pass. The `TestSemanticEmbeddingIntegration` tests are skipped (deselected) because they require the `ollama` marker.

**If it fails:**
- If `ModuleNotFoundError: No module named 'gwen.memory.embeddings'`: The file was not created at the correct path. Verify that `gwen/memory/embeddings.py` exists and that `gwen/memory/__init__.py` exists (created in Track 001).
- If `ModuleNotFoundError: No module named 'chromadb'`: Run `pip install -e ".[dev]"` to install dependencies.
- If tests fail on ChromaDB operations: Ensure chromadb version >= 0.4.0 is installed.

---

## Summary of Files Created

| Step | File Path | Purpose |
|------|-----------|---------|
| 1.1-2.2 | `gwen/memory/embeddings.py` | EmbeddingService class with all methods |
| 3.1 | `tests/test_embeddings.py` | Unit and integration tests |

**Total new files:** 2
**Modified files:** 0
**Dependencies added:** 0 (all deps already in pyproject.toml from Track 001)
