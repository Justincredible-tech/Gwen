"""
Semantic Map -- Tier 3: Knowledge graph backed by NetworkX.

Stores entities (people, places, things, concepts, events) and their
relationships extracted from conversations. Each entity has:
- Bi-temporal validity (valid_from, valid_until)
- Emotional weight derived from source conversations
- Sensitivity level for privacy-aware retrieval

The graph is persisted as JSON via NetworkX's node_link_data format.

References: SRS.md Sections 3.5 and FR-MEM-003.
"""

import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

import networkx as nx

from gwen.models.memory import MapEntity, MapEdge
from gwen.models.emotional import CompassDirection, EmotionalStateVector


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _datetime_to_iso(dt: Optional[datetime]) -> Optional[str]:
    """Convert a datetime to ISO 8601 string, or None if None."""
    if dt is None:
        return None
    return dt.isoformat()


def _iso_to_datetime(s: Optional[str]) -> Optional[datetime]:
    """Convert an ISO 8601 string to datetime, or None if None."""
    if s is None:
        return None
    return datetime.fromisoformat(s)


def _emotional_state_to_dict(
    state: Optional[EmotionalStateVector],
) -> Optional[dict]:
    """Serialize an EmotionalStateVector to a plain dict."""
    if state is None:
        return None
    return {
        "valence": state.valence,
        "arousal": state.arousal,
        "dominance": state.dominance,
        "relational_significance": state.relational_significance,
        "vulnerability_level": state.vulnerability_level,
        "compass_direction": state.compass_direction.value,
        "compass_confidence": state.compass_confidence,
    }


def _dict_to_emotional_state(
    d: Optional[dict],
) -> Optional[EmotionalStateVector]:
    """Deserialize a dict back to an EmotionalStateVector."""
    if d is None:
        return None
    return EmotionalStateVector(
        valence=d["valence"],
        arousal=d["arousal"],
        dominance=d["dominance"],
        relational_significance=d["relational_significance"],
        vulnerability_level=d["vulnerability_level"],
        compass_direction=CompassDirection(d.get("compass_direction", "none")),
        compass_confidence=d.get("compass_confidence", 0.0),
    )


def _entity_to_dict(entity: MapEntity) -> dict:
    """Convert a MapEntity to a dict suitable for NetworkX node storage."""
    return {
        "entity_type": entity.entity_type,
        "name": entity.name,
        "valid_from": _datetime_to_iso(entity.valid_from),
        "valid_until": _datetime_to_iso(entity.valid_until),
        "ingested_at": _datetime_to_iso(entity.ingested_at),
        "last_updated": _datetime_to_iso(entity.last_updated),
        "emotional_weight": _emotional_state_to_dict(entity.emotional_weight),
        "sensitivity_level": entity.sensitivity_level,
        "source_session_ids": list(entity.source_session_ids),
        "consolidation_count": entity.consolidation_count,
        "detail_level": entity.detail_level,
        "semantic_embedding_id": entity.semantic_embedding_id,
    }


def _dict_to_entity(entity_id: str, d: dict) -> MapEntity:
    """Reconstruct a MapEntity from its NetworkX node dict."""
    return MapEntity(
        id=entity_id,
        entity_type=d["entity_type"],
        name=d["name"],
        valid_from=_iso_to_datetime(d["valid_from"]),
        valid_until=_iso_to_datetime(d.get("valid_until")),
        ingested_at=_iso_to_datetime(d["ingested_at"]),
        last_updated=_iso_to_datetime(d["last_updated"]),
        emotional_weight=_dict_to_emotional_state(d["emotional_weight"]),
        sensitivity_level=d.get("sensitivity_level", 0.0),
        source_session_ids=d.get("source_session_ids", []),
        consolidation_count=d.get("consolidation_count", 0),
        detail_level=d.get("detail_level", 0.5),
        semantic_embedding_id=d.get("semantic_embedding_id"),
    )


def _edge_to_dict(edge: MapEdge) -> dict:
    """Convert a MapEdge to a dict suitable for NetworkX edge storage."""
    return {
        "edge_id": edge.id,
        "relationship_type": edge.relationship_type,
        "label": edge.label,
        "emotional_weight": edge.emotional_weight,
        "valid_from": _datetime_to_iso(edge.valid_from),
        "valid_until": _datetime_to_iso(edge.valid_until),
        "confidence": edge.confidence,
    }


def _dict_to_edge(source_id: str, target_id: str, d: dict) -> MapEdge:
    """Reconstruct a MapEdge from its NetworkX edge dict."""
    return MapEdge(
        id=d.get("edge_id", ""),
        source_entity_id=source_id,
        target_entity_id=target_id,
        relationship_type=d["relationship_type"],
        label=d.get("label", ""),
        emotional_weight=d.get("emotional_weight", 0.0),
        valid_from=_iso_to_datetime(d.get("valid_from")),
        valid_until=_iso_to_datetime(d.get("valid_until")),
        confidence=d.get("confidence", 0.8),
    )


class SemanticMap:
    """Tier 3: The Map -- a knowledge graph of entities and relationships.

    Wraps a NetworkX DiGraph with domain-specific methods for adding
    entities, edges, querying related entities via BFS, invalidating
    stale entities, and filtering by sensitivity level.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser()
        self.graph: nx.DiGraph = nx.DiGraph()

        if self.db_path.exists():
            self._load_from_disk()

    # ------------------------------------------------------------------
    # Entity CRUD
    # ------------------------------------------------------------------

    def add_entity(self, entity: MapEntity) -> None:
        """Add an entity as a node in the knowledge graph."""
        self.graph.add_node(entity.id, **_entity_to_dict(entity))

    def get_entity(self, entity_id: str) -> Optional[MapEntity]:
        """Retrieve an entity by its unique ID."""
        if entity_id not in self.graph:
            return None
        data = dict(self.graph.nodes[entity_id])
        return _dict_to_entity(entity_id, data)

    def search_entities(self, name_query: str) -> list[MapEntity]:
        """Search entities by name using case-insensitive substring match.

        Only returns valid (non-expired) entities.
        """
        query_lower = name_query.lower()
        results: list[MapEntity] = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("valid_until") is not None:
                continue
            name = data.get("name", "")
            if query_lower in name.lower():
                results.append(_dict_to_entity(node_id, data))
        return results

    def invalidate_entity(self, entity_id: str, reason: str) -> bool:
        """Mark an entity as invalid (expired).

        The entity is NOT deleted — it remains for historical reference
        but is excluded from most queries.
        """
        if entity_id not in self.graph:
            return False
        self.graph.nodes[entity_id]["valid_until"] = _datetime_to_iso(
            datetime.now()
        )
        self.graph.nodes[entity_id]["invalidation_reason"] = reason
        return True

    # ------------------------------------------------------------------
    # Edge CRUD
    # ------------------------------------------------------------------

    def add_edge(self, edge: MapEdge) -> None:
        """Add a relationship as a directed edge in the knowledge graph."""
        self.graph.add_edge(
            edge.source_entity_id,
            edge.target_entity_id,
            **_edge_to_dict(edge),
        )

    def get_edges_for_entity(self, entity_id: str) -> list[MapEdge]:
        """Return all edges (both outgoing and incoming) for an entity."""
        edges: list[MapEdge] = []
        if entity_id not in self.graph:
            return edges

        for _, target, data in self.graph.out_edges(entity_id, data=True):
            edges.append(_dict_to_edge(entity_id, target, data))

        for source, _, data in self.graph.in_edges(entity_id, data=True):
            edges.append(_dict_to_edge(source, entity_id, data))

        return edges

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    def query_related(
        self, entity_id: str, max_depth: int = 2
    ) -> list[MapEntity]:
        """Find all entities related to the given entity via BFS.

        Traverses both successor and predecessor edges. Expired entities
        are excluded from results but can be traversed through.
        """
        if entity_id not in self.graph:
            return []

        visited: set[str] = {entity_id}
        queue: deque[tuple[str, int]] = deque()

        for neighbor in self.graph.successors(entity_id):
            if neighbor not in visited:
                queue.append((neighbor, 1))
                visited.add(neighbor)
        for neighbor in self.graph.predecessors(entity_id):
            if neighbor not in visited:
                queue.append((neighbor, 1))
                visited.add(neighbor)

        results: list[MapEntity] = []

        while queue:
            current_id, depth = queue.popleft()
            data = dict(self.graph.nodes[current_id])

            if data.get("valid_until") is None:
                results.append(_dict_to_entity(current_id, data))

            if depth < max_depth:
                for neighbor in self.graph.successors(current_id):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))
                        visited.add(neighbor)
                for neighbor in self.graph.predecessors(current_id):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))
                        visited.add(neighbor)

        return results

    def get_sensitive_topics(
        self, threshold: float = 0.7
    ) -> list[MapEntity]:
        """Return all valid entities with sensitivity at or above threshold."""
        results: list[MapEntity] = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("valid_until") is not None:
                continue
            sensitivity = data.get("sensitivity_level", 0.0)
            if sensitivity >= threshold:
                results.append(_dict_to_entity(node_id, data))
        return results

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def entity_count(self, include_expired: bool = False) -> int:
        """Return the number of entities in the graph."""
        if include_expired:
            return self.graph.number_of_nodes()
        return sum(
            1 for _, data in self.graph.nodes(data=True)
            if data.get("valid_until") is None
        )

    def edge_count(self) -> int:
        """Return the total number of edges in the graph."""
        return self.graph.number_of_edges()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_to_disk(self) -> None:
        """Serialize the entire graph to JSON and write to self.db_path."""
        data = nx.node_link_data(self.graph)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_from_disk(self) -> None:
        """Load the graph from the JSON file at self.db_path."""
        with open(self.db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.graph = nx.node_link_graph(data, directed=True)
