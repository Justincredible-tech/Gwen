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
from typing import TYPE_CHECKING

import chromadb

if TYPE_CHECKING:
    from gwen.models.emotional import EmotionalStateVector
    from gwen.models.messages import MessageRecord

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
            ollama_host: Optional override for the Ollama server URL.
        """
        if ollama_host is not None:
            self.OLLAMA_HOST = ollama_host

        self.semantic_collection = chromadb_client.get_or_create_collection(
            name="semantic_embeddings",
            metadata={"hnsw:space": "cosine"},
        )
        self.emotional_collection = chromadb_client.get_or_create_collection(
            name="emotional_embeddings",
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            "EmbeddingService initialized. Semantic: %d items, Emotional: %d items",
            self.semantic_collection.count(),
            self.emotional_collection.count(),
        )

    async def generate_semantic_embedding(self, text: str) -> list[float]:
        """Generate a 1024-dim semantic embedding via Ollama /api/embed.

        Args:
            text: The text to generate an embedding for.

        Returns:
            A list of 1024 floats representing the semantic embedding vector.
        """
        return await asyncio.to_thread(self._call_ollama_embed, text)

    def _call_ollama_embed(self, text: str) -> list[float]:
        """Synchronous helper that calls Ollama /api/embed."""
        payload = json.dumps({
            "model": self.EMBEDDING_MODEL,
            "input": text,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.OLLAMA_HOST}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            embedding = result["embeddings"][0]

        if len(embedding) != self.EMBEDDING_DIM:
            logger.warning(
                "Expected %d-dim embedding, got %d-dim. Model may have changed.",
                self.EMBEDDING_DIM,
                len(embedding),
            )

        return embedding

    def generate_emotional_embedding(self, state: EmotionalStateVector) -> list[float]:
        """Encode an EmotionalStateVector into a 5D embedding.

        The dimensions are, in order:
          [0] valence, [1] arousal, [2] dominance,
          [3] relational_significance, [4] vulnerability_level

        Args:
            state: An EmotionalStateVector instance.

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

    async def store_embeddings(self, message: MessageRecord) -> None:
        """Generate both embeddings and store them in ChromaDB.

        Args:
            message: A fully populated MessageRecord.

        Side effects:
            - message.semantic_embedding_id is set to message.id
            - message.emotional_embedding_id is set to "{message.id}_emo"
        """
        # 1. Generate semantic embedding (async, calls Ollama)
        semantic = await self.generate_semantic_embedding(message.content)

        # 2. Generate emotional embedding (sync, instant)
        emotional = self.generate_emotional_embedding(message.emotional_state)

        # 3. Store semantic embedding in ChromaDB
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

        # 4. Store emotional embedding in ChromaDB
        self.emotional_collection.add(
            ids=[f"{message.id}_emo"],
            embeddings=[emotional],
            metadatas=[{
                "session_id": message.session_id,
                "timestamp": message.timestamp.isoformat(),
                "compass_direction": message.compass_direction.value,
            }],
        )

        # 5. Update the message's embedding references
        message.semantic_embedding_id = message.id
        message.emotional_embedding_id = f"{message.id}_emo"

        logger.debug(
            "Stored embeddings for message %s (semantic: %d-dim, emotional: %d-dim)",
            message.id,
            len(semantic),
            len(emotional),
        )

    async def search_similar(
        self,
        query_text: str,
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[dict]:
        """Search for semantically similar messages.

        Args:
            query_text: The text to search for.
            n_results: Maximum number of results to return.
            where: Optional ChromaDB metadata filter dict.

        Returns:
            A list of dicts with keys: id, document, distance, metadata.
        """
        try:
            query_embedding = await self.generate_semantic_embedding(query_text)

            query_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["documents", "distances", "metadatas"],
            }
            if where is not None:
                query_kwargs["where"] = where

            raw_results = self.semantic_collection.query(**query_kwargs)

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

    async def search_by_emotion(
        self,
        state: EmotionalStateVector,
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[dict]:
        """Search for messages with similar emotional states.

        Args:
            state: The EmotionalStateVector to search for.
            n_results: Maximum number of results to return.
            where: Optional ChromaDB metadata filter dict.

        Returns:
            A list of dicts with keys: id, distance, metadata.
        """
        try:
            query_embedding = self.generate_emotional_embedding(state)

            query_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["distances", "metadatas"],
            }
            if where is not None:
                query_kwargs["where"] = where

            raw_results = self.emotional_collection.query(**query_kwargs)

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
