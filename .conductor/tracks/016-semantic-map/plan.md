# Plan: Semantic Map (Knowledge Graph)

**Track:** 016-semantic-map
**Depends on:** 003-database-layer (Chronicle, data directory), 009-embedding-service (EmbeddingService for entity embeddings)
**Produces:** gwen/memory/semantic_map.py, tests/test_semantic_map.py

---

## Phase 1: SemanticMap Core

### Step 1.1: Create gwen/memory/semantic_map.py with imports and helpers

Create the file `gwen/memory/semantic_map.py` with the following exact content. This step defines imports, serialization helpers, and the SemanticMap class skeleton.

```python
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
from gwen.models.emotional import EmotionalStateVector


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
    )
```

**What this does:** Sets up the module with all necessary imports and serialization helpers for converting between Python objects and JSON-compatible dicts. The helpers handle `datetime` and `EmotionalStateVector` round-tripping.

---

### Step 1.2: Add the _entity_to_dict and _dict_to_entity helpers

Append the following to `gwen/memory/semantic_map.py`, below the serialization helpers:

```python
def _entity_to_dict(entity: MapEntity) -> dict:
    """Convert a MapEntity to a dict suitable for NetworkX node storage.

    All complex types (datetime, EmotionalStateVector) are converted to
    JSON-serializable primitives. The entity ID is NOT included in the
    dict because NetworkX stores it as the node key.
    """
    return {
        "name": entity.name,
        "entity_type": entity.entity_type,
        "description": entity.description,
        "source_session_id": entity.source_session_id,
        "source_message_id": entity.source_message_id,
        "valid_from": _datetime_to_iso(entity.valid_from),
        "valid_until": _datetime_to_iso(entity.valid_until),
        "invalidation_reason": entity.invalidation_reason,
        "emotional_weight": _emotional_state_to_dict(
            entity.emotional_weight
        ),
        "sensitivity_level": entity.sensitivity_level,
        "mention_count": entity.mention_count,
        "last_mentioned": _datetime_to_iso(entity.last_mentioned),
        "tags": list(entity.tags) if entity.tags else [],
    }


def _dict_to_entity(entity_id: str, d: dict) -> MapEntity:
    """Reconstruct a MapEntity from its NetworkX node dict.

    Parameters
    ----------
    entity_id : str
        The node key in the NetworkX graph (the entity's unique ID).
    d : dict
        The node data dict stored by NetworkX.

    Returns
    -------
    MapEntity
        The reconstituted entity with all fields.
    """
    return MapEntity(
        id=entity_id,
        name=d["name"],
        entity_type=d["entity_type"],
        description=d.get("description", ""),
        source_session_id=d.get("source_session_id"),
        source_message_id=d.get("source_message_id"),
        valid_from=_iso_to_datetime(d.get("valid_from")),
        valid_until=_iso_to_datetime(d.get("valid_until")),
        invalidation_reason=d.get("invalidation_reason"),
        emotional_weight=_dict_to_emotional_state(
            d.get("emotional_weight")
        ),
        sensitivity_level=d.get("sensitivity_level", 0.0),
        mention_count=d.get("mention_count", 1),
        last_mentioned=_iso_to_datetime(d.get("last_mentioned")),
        tags=d.get("tags", []),
    )
```

---

### Step 1.3: Add the _edge_to_dict and _dict_to_edge helpers

Append the following to `gwen/memory/semantic_map.py`:

```python
def _edge_to_dict(edge: MapEdge) -> dict:
    """Convert a MapEdge to a dict suitable for NetworkX edge storage.

    The source and target entity IDs are NOT included because NetworkX
    stores them as the edge endpoints.
    """
    return {
        "relationship_type": edge.relationship_type,
        "description": edge.description,
        "weight": edge.weight,
        "source_session_id": edge.source_session_id,
        "valid_from": _datetime_to_iso(edge.valid_from),
        "valid_until": _datetime_to_iso(edge.valid_until),
    }


def _dict_to_edge(
    source_id: str, target_id: str, d: dict
) -> MapEdge:
    """Reconstruct a MapEdge from its NetworkX edge dict.

    Parameters
    ----------
    source_id : str
        The source node key.
    target_id : str
        The target node key.
    d : dict
        The edge data dict stored by NetworkX.

    Returns
    -------
    MapEdge
        The reconstituted edge with all fields.
    """
    return MapEdge(
        source_entity_id=source_id,
        target_entity_id=target_id,
        relationship_type=d["relationship_type"],
        description=d.get("description", ""),
        weight=d.get("weight", 1.0),
        source_session_id=d.get("source_session_id"),
        valid_from=_iso_to_datetime(d.get("valid_from")),
        valid_until=_iso_to_datetime(d.get("valid_until")),
    )
```

---

### Step 1.4: Add the SemanticMap class

Append the following class to `gwen/memory/semantic_map.py`:

```python
class SemanticMap:
    """Tier 3: The Map -- a knowledge graph of entities and relationships.

    Wraps a NetworkX DiGraph with domain-specific methods for adding
    entities, edges, querying related entities via BFS, invalidating
    stale entities, and filtering by sensitivity level.

    The graph is persisted as JSON to a file on disk.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Open (or create) the semantic map.

        Parameters
        ----------
        db_path : str | Path
            Path to the JSON file for graph persistence. If the file
            exists, the graph is loaded from it. If not, a new empty
            graph is created.
        """
        self.db_path = Path(db_path).expanduser()
        self.graph: nx.DiGraph = nx.DiGraph()

        if self.db_path.exists():
            self._load_from_disk()

    # ------------------------------------------------------------------
    # Entity CRUD
    # ------------------------------------------------------------------

    def add_entity(self, entity: MapEntity) -> None:
        """Add an entity as a node in the knowledge graph.

        If an entity with the same ID already exists, its data is
        overwritten with the new entity's data.

        Parameters
        ----------
        entity : MapEntity
            The entity to add. The entity's ``id`` field is used as
            the node key.
        """
        self.graph.add_node(entity.id, **_entity_to_dict(entity))

    def get_entity(self, entity_id: str) -> Optional[MapEntity]:
        """Retrieve an entity by its unique ID.

        Parameters
        ----------
        entity_id : str
            The unique identifier of the entity.

        Returns
        -------
        MapEntity | None
            The entity if found, None otherwise.
        """
        if entity_id not in self.graph:
            return None
        data = dict(self.graph.nodes[entity_id])
        return _dict_to_entity(entity_id, data)

    def search_entities(self, name_query: str) -> list[MapEntity]:
        """Search entities by name using case-insensitive substring match.

        Only returns valid (non-expired) entities — entities whose
        ``valid_until`` is None.

        Parameters
        ----------
        name_query : str
            The search string. Matches if this string appears anywhere
            in the entity's name (case-insensitive).

        Returns
        -------
        list[MapEntity]
            All matching, non-expired entities.
        """
        query_lower = name_query.lower()
        results: list[MapEntity] = []
        for node_id, data in self.graph.nodes(data=True):
            # Skip expired entities
            if data.get("valid_until") is not None:
                continue
            name = data.get("name", "")
            if query_lower in name.lower():
                results.append(_dict_to_entity(node_id, data))
        return results

    def invalidate_entity(self, entity_id: str, reason: str) -> bool:
        """Mark an entity as invalid (expired).

        Sets the ``valid_until`` field to the current time and records
        the invalidation reason. The entity is NOT deleted from the
        graph — it remains for historical reference but is excluded
        from most queries.

        Parameters
        ----------
        entity_id : str
            The unique identifier of the entity to invalidate.
        reason : str
            Human-readable reason for the invalidation (e.g.,
            "User corrected: not a coworker, is a friend").

        Returns
        -------
        bool
            True if the entity was found and invalidated.
            False if no entity with that ID exists.
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
        """Add a relationship as a directed edge in the knowledge graph.

        Both the source and target entities must already exist in the
        graph as nodes. If they do not, NetworkX will create stub nodes
        with no data, which is undesirable. The caller should ensure
        entities are added before edges.

        Parameters
        ----------
        edge : MapEdge
            The relationship to add. The ``source_entity_id`` and
            ``target_entity_id`` fields determine the edge direction.
        """
        self.graph.add_edge(
            edge.source_entity_id,
            edge.target_entity_id,
            **_edge_to_dict(edge),
        )

    def get_edges_for_entity(self, entity_id: str) -> list[MapEdge]:
        """Return all edges (both outgoing and incoming) for an entity.

        Parameters
        ----------
        entity_id : str
            The entity to query edges for.

        Returns
        -------
        list[MapEdge]
            All edges where this entity is either source or target.
        """
        edges: list[MapEdge] = []
        if entity_id not in self.graph:
            return edges

        # Outgoing edges
        for _, target, data in self.graph.out_edges(entity_id, data=True):
            edges.append(_dict_to_edge(entity_id, target, data))

        # Incoming edges
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

        Traverses the graph outward from ``entity_id`` up to
        ``max_depth`` hops. Expired entities (with ``valid_until``
        set) are excluded from the results but can still be traversed
        through.

        Parameters
        ----------
        entity_id : str
            The starting entity for the BFS traversal.
        max_depth : int
            Maximum number of hops from the starting entity.
            Defaults to 2.

        Returns
        -------
        list[MapEntity]
            All valid (non-expired) entities within ``max_depth`` hops
            of the starting entity. Does NOT include the starting entity
            itself.
        """
        if entity_id not in self.graph:
            return []

        visited: set[str] = {entity_id}
        queue: deque[tuple[str, int]] = deque()

        # Seed with immediate neighbors (both directions for a DiGraph)
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

            # Only include non-expired entities in results
            if data.get("valid_until") is None:
                results.append(_dict_to_entity(current_id, data))

            # Continue BFS if within depth limit
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
        """Return all valid entities with sensitivity at or above threshold.

        Parameters
        ----------
        threshold : float
            Minimum sensitivity level (0.0 to 1.0). Defaults to 0.7.

        Returns
        -------
        list[MapEntity]
            Entities whose ``sensitivity_level`` >= threshold and
            whose ``valid_until`` is None (not expired).
        """
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
        """Return the number of entities in the graph.

        Parameters
        ----------
        include_expired : bool
            If True, count all entities. If False (default), only count
            valid (non-expired) entities.

        Returns
        -------
        int
            The entity count.
        """
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
        """Serialize the entire graph to JSON and write to self.db_path.

        Uses NetworkX's ``node_link_data`` format which captures all
        node and edge data in a JSON-serializable structure.
        """
        data = nx.node_link_data(self.graph)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_from_disk(self) -> None:
        """Load the graph from the JSON file at self.db_path.

        Called automatically by ``__init__`` if the file exists.
        """
        with open(self.db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.graph = nx.node_link_graph(data, directed=True)
```

**What this does:** The SemanticMap class provides the full knowledge graph interface:
- **Entity CRUD:** `add_entity`, `get_entity`, `search_entities`, `invalidate_entity`
- **Edge CRUD:** `add_edge`, `get_edges_for_entity`
- **Graph queries:** `query_related` (BFS), `get_sensitive_topics`
- **Persistence:** `save_to_disk`, `_load_from_disk` (JSON via node_link format)
- **Statistics:** `entity_count`, `edge_count`

BFS traversal follows both successor and predecessor edges (since this is a DiGraph), excludes expired entities from results, and respects the `max_depth` limit.

---

## Phase 2: Tests

### Step 2.1: Create tests/test_semantic_map.py

Create the file `tests/test_semantic_map.py` with the following exact content:

```python
"""Tests for gwen.memory.semantic_map -- the Semantic Map (Tier 3).

Run with:
    pytest tests/test_semantic_map.py -v
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from gwen.memory.semantic_map import SemanticMap
from gwen.models.emotional import EmotionalStateVector
from gwen.models.memory import MapEntity, MapEdge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def map_path(tmp_path: Path) -> Path:
    """Return a path to a temporary semantic map JSON file."""
    return tmp_path / "test_semantic_map.json"


@pytest.fixture
def semantic_map(map_path: Path) -> SemanticMap:
    """Return a SemanticMap instance backed by a temporary file."""
    return SemanticMap(map_path)


def _make_emotional_state(**overrides) -> EmotionalStateVector:
    """Create an EmotionalStateVector with sensible defaults."""
    defaults = {
        "valence": 0.6,
        "arousal": 0.4,
        "dominance": 0.5,
        "relational_significance": 0.3,
        "vulnerability_level": 0.2,
    }
    defaults.update(overrides)
    return EmotionalStateVector(**defaults)


def _make_entity(
    entity_id: str = "entity-001",
    name: str = "Sarah",
    entity_type: str = "person",
    **overrides,
) -> MapEntity:
    """Create a MapEntity with sensible defaults."""
    defaults = {
        "id": entity_id,
        "name": name,
        "entity_type": entity_type,
        "description": f"A {entity_type} named {name}",
        "source_session_id": "sess-001",
        "source_message_id": "msg-001",
        "valid_from": datetime(2026, 1, 15, 10, 0, 0),
        "valid_until": None,
        "invalidation_reason": None,
        "emotional_weight": _make_emotional_state(),
        "sensitivity_level": 0.3,
        "mention_count": 1,
        "last_mentioned": datetime(2026, 1, 15, 10, 0, 0),
        "tags": ["friend"],
    }
    defaults.update(overrides)
    return MapEntity(**defaults)


def _make_edge(
    source_id: str = "entity-001",
    target_id: str = "entity-002",
    relationship_type: str = "friend_of",
    **overrides,
) -> MapEdge:
    """Create a MapEdge with sensible defaults."""
    defaults = {
        "source_entity_id": source_id,
        "target_entity_id": target_id,
        "relationship_type": relationship_type,
        "description": f"{source_id} is {relationship_type} {target_id}",
        "weight": 1.0,
        "source_session_id": "sess-001",
        "valid_from": datetime(2026, 1, 15, 10, 0, 0),
        "valid_until": None,
    }
    defaults.update(overrides)
    return MapEdge(**defaults)


# ---------------------------------------------------------------------------
# Tests: Entity CRUD
# ---------------------------------------------------------------------------

class TestEntityCRUD:
    """Tests for adding, getting, searching, and invalidating entities."""

    def test_add_and_get_entity(self, semantic_map: SemanticMap) -> None:
        """Adding an entity and retrieving it should preserve all fields."""
        entity = _make_entity()
        semantic_map.add_entity(entity)

        got = semantic_map.get_entity("entity-001")
        assert got is not None
        assert got.id == "entity-001"
        assert got.name == "Sarah"
        assert got.entity_type == "person"
        assert got.description == "A person named Sarah"
        assert got.source_session_id == "sess-001"
        assert got.sensitivity_level == pytest.approx(0.3)
        assert got.mention_count == 1
        assert got.tags == ["friend"]

    def test_get_entity_preserves_emotional_weight(
        self, semantic_map: SemanticMap
    ) -> None:
        """Emotional weight should survive add/get round-trip."""
        ew = _make_emotional_state(valence=0.8, arousal=0.3)
        entity = _make_entity(emotional_weight=ew)
        semantic_map.add_entity(entity)

        got = semantic_map.get_entity("entity-001")
        assert got is not None
        assert got.emotional_weight is not None
        assert got.emotional_weight.valence == pytest.approx(0.8)
        assert got.emotional_weight.arousal == pytest.approx(0.3)

    def test_get_entity_preserves_datetimes(
        self, semantic_map: SemanticMap
    ) -> None:
        """Bi-temporal validity dates should survive add/get round-trip."""
        vf = datetime(2026, 1, 15, 10, 0, 0)
        entity = _make_entity(valid_from=vf)
        semantic_map.add_entity(entity)

        got = semantic_map.get_entity("entity-001")
        assert got is not None
        assert got.valid_from == vf
        assert got.valid_until is None

    def test_get_nonexistent_entity_returns_none(
        self, semantic_map: SemanticMap
    ) -> None:
        """get_entity with unknown ID should return None."""
        assert semantic_map.get_entity("nonexistent") is None

    def test_add_entity_overwrites_existing(
        self, semantic_map: SemanticMap
    ) -> None:
        """Adding an entity with an existing ID should overwrite."""
        semantic_map.add_entity(_make_entity(name="Sarah V1"))
        semantic_map.add_entity(_make_entity(name="Sarah V2"))

        got = semantic_map.get_entity("entity-001")
        assert got is not None
        assert got.name == "Sarah V2"

    def test_search_entities_by_name(
        self, semantic_map: SemanticMap
    ) -> None:
        """search_entities should find entities by name substring."""
        semantic_map.add_entity(_make_entity("e1", "Sarah Connor"))
        semantic_map.add_entity(_make_entity("e2", "John Connor"))
        semantic_map.add_entity(_make_entity("e3", "Miles Dyson"))

        results = semantic_map.search_entities("connor")
        assert len(results) == 2
        names = {e.name for e in results}
        assert "Sarah Connor" in names
        assert "John Connor" in names

    def test_search_entities_case_insensitive(
        self, semantic_map: SemanticMap
    ) -> None:
        """search_entities should be case-insensitive."""
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        results = semantic_map.search_entities("SARAH")
        assert len(results) == 1
        assert results[0].name == "Sarah"

    def test_search_entities_excludes_expired(
        self, semantic_map: SemanticMap
    ) -> None:
        """search_entities should not return expired entities."""
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        semantic_map.add_entity(
            _make_entity(
                "e2", "Sarah's Cat",
                valid_until=datetime(2026, 2, 1),
            )
        )
        results = semantic_map.search_entities("sarah")
        assert len(results) == 1
        assert results[0].id == "e1"

    def test_invalidate_entity(self, semantic_map: SemanticMap) -> None:
        """invalidate_entity should set valid_until and record reason."""
        semantic_map.add_entity(_make_entity())
        result = semantic_map.invalidate_entity(
            "entity-001", "User corrected: not a friend"
        )
        assert result is True

        got = semantic_map.get_entity("entity-001")
        assert got is not None
        assert got.valid_until is not None
        assert got.invalidation_reason == "User corrected: not a friend"

    def test_invalidate_nonexistent_entity_returns_false(
        self, semantic_map: SemanticMap
    ) -> None:
        """invalidate_entity with unknown ID should return False."""
        result = semantic_map.invalidate_entity("nonexistent", "reason")
        assert result is False


# ---------------------------------------------------------------------------
# Tests: Edge CRUD
# ---------------------------------------------------------------------------

class TestEdgeCRUD:
    """Tests for adding and retrieving edges."""

    def test_add_and_get_edge(self, semantic_map: SemanticMap) -> None:
        """Adding an edge and retrieving it should preserve attributes."""
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        semantic_map.add_entity(_make_entity("e2", "John"))
        edge = _make_edge("e1", "e2", "friend_of")
        semantic_map.add_edge(edge)

        edges = semantic_map.get_edges_for_entity("e1")
        assert len(edges) == 1
        assert edges[0].source_entity_id == "e1"
        assert edges[0].target_entity_id == "e2"
        assert edges[0].relationship_type == "friend_of"

    def test_get_edges_includes_incoming(
        self, semantic_map: SemanticMap
    ) -> None:
        """get_edges_for_entity should include incoming edges."""
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        semantic_map.add_entity(_make_entity("e2", "John"))
        edge = _make_edge("e1", "e2", "friend_of")
        semantic_map.add_edge(edge)

        # Query from John's perspective (incoming edge)
        edges = semantic_map.get_edges_for_entity("e2")
        assert len(edges) == 1
        assert edges[0].source_entity_id == "e1"

    def test_get_edges_empty_for_no_edges(
        self, semantic_map: SemanticMap
    ) -> None:
        """get_edges_for_entity should return empty list if no edges."""
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        edges = semantic_map.get_edges_for_entity("e1")
        assert edges == []

    def test_get_edges_nonexistent_entity(
        self, semantic_map: SemanticMap
    ) -> None:
        """get_edges_for_entity with unknown ID should return empty list."""
        edges = semantic_map.get_edges_for_entity("nonexistent")
        assert edges == []


# ---------------------------------------------------------------------------
# Tests: BFS Traversal
# ---------------------------------------------------------------------------

class TestBFSTraversal:
    """Tests for query_related BFS traversal."""

    def _build_chain(self, semantic_map: SemanticMap) -> None:
        """Build a chain: A -> B -> C -> D for traversal tests.

        A is connected to B, B to C, C to D. All are valid entities.
        """
        semantic_map.add_entity(_make_entity("A", "Alice"))
        semantic_map.add_entity(_make_entity("B", "Bob"))
        semantic_map.add_entity(_make_entity("C", "Charlie"))
        semantic_map.add_entity(_make_entity("D", "Diana"))

        semantic_map.add_edge(_make_edge("A", "B", "knows"))
        semantic_map.add_edge(_make_edge("B", "C", "knows"))
        semantic_map.add_edge(_make_edge("C", "D", "knows"))

    def test_depth_1_finds_immediate_neighbors(
        self, semantic_map: SemanticMap
    ) -> None:
        """query_related(A, max_depth=1) should find only B."""
        self._build_chain(semantic_map)
        related = semantic_map.query_related("A", max_depth=1)
        ids = {e.id for e in related}
        assert ids == {"B"}

    def test_depth_2_finds_two_hops(
        self, semantic_map: SemanticMap
    ) -> None:
        """query_related(A, max_depth=2) should find B and C."""
        self._build_chain(semantic_map)
        related = semantic_map.query_related("A", max_depth=2)
        ids = {e.id for e in related}
        assert ids == {"B", "C"}

    def test_depth_3_finds_entire_chain(
        self, semantic_map: SemanticMap
    ) -> None:
        """query_related(A, max_depth=3) should find B, C, and D."""
        self._build_chain(semantic_map)
        related = semantic_map.query_related("A", max_depth=3)
        ids = {e.id for e in related}
        assert ids == {"B", "C", "D"}

    def test_does_not_include_starting_entity(
        self, semantic_map: SemanticMap
    ) -> None:
        """query_related should NOT include the starting entity itself."""
        self._build_chain(semantic_map)
        related = semantic_map.query_related("A", max_depth=10)
        ids = {e.id for e in related}
        assert "A" not in ids

    def test_excludes_expired_entities_from_results(
        self, semantic_map: SemanticMap
    ) -> None:
        """Expired entities should not appear in query_related results."""
        self._build_chain(semantic_map)
        semantic_map.invalidate_entity("B", "No longer relevant")

        related = semantic_map.query_related("A", max_depth=3)
        ids = {e.id for e in related}
        # B is expired so excluded from results
        # But BFS should still traverse through B to reach C and D
        assert "B" not in ids
        assert "C" in ids
        assert "D" in ids

    def test_query_related_nonexistent_entity(
        self, semantic_map: SemanticMap
    ) -> None:
        """query_related with unknown ID should return empty list."""
        related = semantic_map.query_related("nonexistent")
        assert related == []

    def test_query_related_follows_reverse_edges(
        self, semantic_map: SemanticMap
    ) -> None:
        """BFS should follow edges in both directions."""
        semantic_map.add_entity(_make_entity("A", "Alice"))
        semantic_map.add_entity(_make_entity("B", "Bob"))
        semantic_map.add_entity(_make_entity("C", "Charlie"))

        # Only edge: B -> A and B -> C
        semantic_map.add_edge(_make_edge("B", "A", "knows"))
        semantic_map.add_edge(_make_edge("B", "C", "knows"))

        # From A's perspective, B is a predecessor. BFS should find B
        # and then C (a successor of B).
        related = semantic_map.query_related("A", max_depth=2)
        ids = {e.id for e in related}
        assert "B" in ids
        assert "C" in ids


# ---------------------------------------------------------------------------
# Tests: Sensitive Topics
# ---------------------------------------------------------------------------

class TestSensitiveTopics:
    """Tests for get_sensitive_topics filtering."""

    def test_returns_entities_above_threshold(
        self, semantic_map: SemanticMap
    ) -> None:
        """get_sensitive_topics should return entities at or above threshold."""
        semantic_map.add_entity(
            _make_entity("e1", "Therapy", sensitivity_level=0.9)
        )
        semantic_map.add_entity(
            _make_entity("e2", "Work", sensitivity_level=0.3)
        )
        semantic_map.add_entity(
            _make_entity("e3", "Family Issue", sensitivity_level=0.8)
        )

        results = semantic_map.get_sensitive_topics(threshold=0.7)
        ids = {e.id for e in results}
        assert "e1" in ids
        assert "e3" in ids
        assert "e2" not in ids

    def test_excludes_expired_sensitive_entities(
        self, semantic_map: SemanticMap
    ) -> None:
        """get_sensitive_topics should exclude expired entities."""
        semantic_map.add_entity(
            _make_entity("e1", "Therapy", sensitivity_level=0.9)
        )
        semantic_map.invalidate_entity("e1", "No longer relevant")

        results = semantic_map.get_sensitive_topics(threshold=0.7)
        assert len(results) == 0

    def test_default_threshold_is_0_7(
        self, semantic_map: SemanticMap
    ) -> None:
        """Default threshold should be 0.7."""
        semantic_map.add_entity(
            _make_entity("e1", "Therapy", sensitivity_level=0.7)
        )
        semantic_map.add_entity(
            _make_entity("e2", "Work", sensitivity_level=0.69)
        )

        results = semantic_map.get_sensitive_topics()
        assert len(results) == 1
        assert results[0].id == "e1"


# ---------------------------------------------------------------------------
# Tests: Statistics
# ---------------------------------------------------------------------------

class TestStatistics:
    """Tests for entity_count and edge_count."""

    def test_empty_graph_counts(self, semantic_map: SemanticMap) -> None:
        """Empty graph should have zero entities and edges."""
        assert semantic_map.entity_count() == 0
        assert semantic_map.edge_count() == 0

    def test_entity_count_excludes_expired_by_default(
        self, semantic_map: SemanticMap
    ) -> None:
        """entity_count() should exclude expired entities by default."""
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        semantic_map.add_entity(_make_entity("e2", "John"))
        semantic_map.invalidate_entity("e2", "Test")

        assert semantic_map.entity_count() == 1
        assert semantic_map.entity_count(include_expired=True) == 2

    def test_edge_count(self, semantic_map: SemanticMap) -> None:
        """edge_count() should return total number of edges."""
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        semantic_map.add_entity(_make_entity("e2", "John"))
        semantic_map.add_edge(_make_edge("e1", "e2", "knows"))

        assert semantic_map.edge_count() == 1


# ---------------------------------------------------------------------------
# Tests: Persistence (save/load round-trip)
# ---------------------------------------------------------------------------

class TestPersistence:
    """Tests for save_to_disk and _load_from_disk."""

    def test_save_and_load_preserves_entities(
        self, map_path: Path
    ) -> None:
        """Saving and loading should preserve all entity data."""
        sm1 = SemanticMap(map_path)
        sm1.add_entity(
            _make_entity(
                "e1", "Sarah",
                sensitivity_level=0.8,
                tags=["friend", "coworker"],
            )
        )
        sm1.save_to_disk()

        # Load into a new instance
        sm2 = SemanticMap(map_path)
        got = sm2.get_entity("e1")
        assert got is not None
        assert got.name == "Sarah"
        assert got.sensitivity_level == pytest.approx(0.8)
        assert got.tags == ["friend", "coworker"]

    def test_save_and_load_preserves_edges(
        self, map_path: Path
    ) -> None:
        """Saving and loading should preserve all edge data."""
        sm1 = SemanticMap(map_path)
        sm1.add_entity(_make_entity("e1", "Sarah"))
        sm1.add_entity(_make_entity("e2", "John"))
        sm1.add_edge(_make_edge("e1", "e2", "friend_of"))
        sm1.save_to_disk()

        sm2 = SemanticMap(map_path)
        assert sm2.entity_count() == 2
        assert sm2.edge_count() == 1

        edges = sm2.get_edges_for_entity("e1")
        assert len(edges) == 1
        assert edges[0].relationship_type == "friend_of"

    def test_save_and_load_preserves_emotional_weight(
        self, map_path: Path
    ) -> None:
        """Emotional weight should survive save/load round-trip."""
        sm1 = SemanticMap(map_path)
        ew = _make_emotional_state(valence=0.9, arousal=0.1)
        sm1.add_entity(_make_entity("e1", "Sarah", emotional_weight=ew))
        sm1.save_to_disk()

        sm2 = SemanticMap(map_path)
        got = sm2.get_entity("e1")
        assert got is not None
        assert got.emotional_weight is not None
        assert got.emotional_weight.valence == pytest.approx(0.9)
        assert got.emotional_weight.arousal == pytest.approx(0.1)

    def test_save_and_load_preserves_datetimes(
        self, map_path: Path
    ) -> None:
        """Bi-temporal validity dates should survive save/load."""
        sm1 = SemanticMap(map_path)
        vf = datetime(2026, 1, 15, 10, 0, 0)
        sm1.add_entity(_make_entity("e1", "Sarah", valid_from=vf))
        sm1.save_to_disk()

        sm2 = SemanticMap(map_path)
        got = sm2.get_entity("e1")
        assert got is not None
        assert got.valid_from == vf

    def test_save_creates_parent_directory(self, tmp_path: Path) -> None:
        """save_to_disk should create parent directories if needed."""
        deep_path = tmp_path / "a" / "b" / "c" / "map.json"
        sm = SemanticMap(deep_path)
        sm.add_entity(_make_entity("e1", "Sarah"))
        sm.save_to_disk()
        assert deep_path.exists()

    def test_load_nonexistent_file_creates_empty_graph(
        self, tmp_path: Path
    ) -> None:
        """Opening a SemanticMap with no existing file should be empty."""
        sm = SemanticMap(tmp_path / "nonexistent.json")
        assert sm.entity_count() == 0
        assert sm.edge_count() == 0

    def test_save_and_load_preserves_invalidated_entities(
        self, map_path: Path
    ) -> None:
        """Invalidated entities should persist through save/load."""
        sm1 = SemanticMap(map_path)
        sm1.add_entity(_make_entity("e1", "Sarah"))
        sm1.invalidate_entity("e1", "Moved away")
        sm1.save_to_disk()

        sm2 = SemanticMap(map_path)
        got = sm2.get_entity("e1")
        assert got is not None
        assert got.valid_until is not None
        assert got.invalidation_reason == "Moved away"
```

---

### Step 2.2: Run the tests

Execute the following command from the project root:

```bash
pytest tests/test_semantic_map.py -v
```

**Expected result:** All tests pass. If any test fails, read the error message carefully. The most likely causes are:

1. **ImportError for gwen.models.memory**: Track 002 (data-models) has not been completed yet. `MapEntity` and `MapEdge` must exist in `gwen/models/memory.py`.
2. **ImportError for gwen.models.emotional**: Track 002 must be completed. `EmotionalStateVector` must exist in `gwen/models/emotional.py`.
3. **ImportError for networkx**: Run `pip install networkx` (see tech-stack.md).
4. **Assertion failures on save/load**: If datetime round-tripping fails, check that `_datetime_to_iso` and `_iso_to_datetime` produce matching values. Python's `datetime.fromisoformat()` should handle the output of `datetime.isoformat()`.

---

## Checklist (update after each step)

- [ ] Phase 1 complete: gwen/memory/semantic_map.py with SemanticMap class, all CRUD methods, BFS, persistence
- [ ] Phase 2 complete: tests/test_semantic_map.py passes with all tests green
