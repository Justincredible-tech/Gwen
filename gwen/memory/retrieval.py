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
        has zero magnitude.
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

    References: SRS.md Section 4.5.1, FR-AMY-003.
    """

    def __init__(
        self,
        embedding_service,
        semantic_collection,
        emotional_collection,
    ) -> None:
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
            The search query text.
        current_state : EmotionalStateVector
            The user's current emotional state.
        safety_level : str
            Current safety level: "none", "low", "medium", "high", "critical".
        max_results : int
            Number of results to return.
        alpha : float
            Mood-congruent bias strength. Default 0.3.

        Returns
        -------
        list[dict]
            Result dicts with id, content, semantic_score, emotional_score,
            final_score, and metadata.
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
            # ChromaDB distances are L2; convert to similarity
            distance = distances[i]
            semantic_score = 1.0 / (1.0 + distance)

            # Get emotional embedding for this memory
            memory_emotional_vec = emotional_embeddings_map.get(memory_id)
            if memory_emotional_vec is None:
                emotional_sim = 0.0
            else:
                emotional_sim = cosine_similarity(
                    current_emotional_vec, memory_emotional_vec
                )

            # Step 4a: Safety inversion
            if safety_level in ("high", "critical"):
                emotional_factor = 1.0 - emotional_sim
            else:
                emotional_factor = emotional_sim

            # Step 4b: Compute final score
            final_score = semantic_score * (1.0 + alpha * emotional_factor)

            # Step 4c: Distress penalty
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
