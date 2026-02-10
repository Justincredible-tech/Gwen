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
    return tmp_path / "test_semantic_map.json"


@pytest.fixture
def semantic_map(map_path: Path) -> SemanticMap:
    return SemanticMap(map_path)


def _make_emotional_state(**overrides) -> EmotionalStateVector:
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
    defaults = {
        "id": entity_id,
        "entity_type": entity_type,
        "name": name,
        "valid_from": datetime(2026, 1, 15, 10, 0, 0),
        "valid_until": None,
        "ingested_at": datetime(2026, 1, 15, 10, 0, 0),
        "last_updated": datetime(2026, 1, 15, 10, 0, 0),
        "emotional_weight": _make_emotional_state(),
        "sensitivity_level": 0.3,
        "source_session_ids": ["sess-001"],
        "consolidation_count": 0,
        "detail_level": 0.5,
        "semantic_embedding_id": None,
    }
    defaults.update(overrides)
    return MapEntity(**defaults)


def _make_edge(
    source_id: str = "entity-001",
    target_id: str = "entity-002",
    relationship_type: str = "friend_of",
    **overrides,
) -> MapEdge:
    defaults = {
        "id": f"edge-{source_id}-{target_id}",
        "source_entity_id": source_id,
        "target_entity_id": target_id,
        "relationship_type": relationship_type,
        "label": f"{source_id} is {relationship_type} {target_id}",
        "emotional_weight": 0.5,
        "valid_from": datetime(2026, 1, 15, 10, 0, 0),
        "valid_until": None,
        "confidence": 0.8,
    }
    defaults.update(overrides)
    return MapEdge(**defaults)


# ---------------------------------------------------------------------------
# Tests: Entity CRUD
# ---------------------------------------------------------------------------

class TestEntityCRUD:

    def test_add_and_get_entity(self, semantic_map: SemanticMap) -> None:
        entity = _make_entity()
        semantic_map.add_entity(entity)

        got = semantic_map.get_entity("entity-001")
        assert got is not None
        assert got.id == "entity-001"
        assert got.name == "Sarah"
        assert got.entity_type == "person"
        assert got.source_session_ids == ["sess-001"]
        assert got.sensitivity_level == pytest.approx(0.3)
        assert got.consolidation_count == 0

    def test_get_entity_preserves_emotional_weight(
        self, semantic_map: SemanticMap
    ) -> None:
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
        assert semantic_map.get_entity("nonexistent") is None

    def test_add_entity_overwrites_existing(
        self, semantic_map: SemanticMap
    ) -> None:
        semantic_map.add_entity(_make_entity(name="Sarah V1"))
        semantic_map.add_entity(_make_entity(name="Sarah V2"))

        got = semantic_map.get_entity("entity-001")
        assert got is not None
        assert got.name == "Sarah V2"

    def test_search_entities_by_name(
        self, semantic_map: SemanticMap
    ) -> None:
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
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        results = semantic_map.search_entities("SARAH")
        assert len(results) == 1
        assert results[0].name == "Sarah"

    def test_search_entities_excludes_expired(
        self, semantic_map: SemanticMap
    ) -> None:
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
        semantic_map.add_entity(_make_entity())
        result = semantic_map.invalidate_entity(
            "entity-001", "User corrected: not a friend"
        )
        assert result is True

        got = semantic_map.get_entity("entity-001")
        assert got is not None
        assert got.valid_until is not None
        # Reason is stored in graph node data
        reason = semantic_map.graph.nodes["entity-001"].get("invalidation_reason")
        assert reason == "User corrected: not a friend"

    def test_invalidate_nonexistent_entity_returns_false(
        self, semantic_map: SemanticMap
    ) -> None:
        result = semantic_map.invalidate_entity("nonexistent", "reason")
        assert result is False


# ---------------------------------------------------------------------------
# Tests: Edge CRUD
# ---------------------------------------------------------------------------

class TestEdgeCRUD:

    def test_add_and_get_edge(self, semantic_map: SemanticMap) -> None:
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
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        semantic_map.add_entity(_make_entity("e2", "John"))
        edge = _make_edge("e1", "e2", "friend_of")
        semantic_map.add_edge(edge)

        edges = semantic_map.get_edges_for_entity("e2")
        assert len(edges) == 1
        assert edges[0].source_entity_id == "e1"

    def test_get_edges_empty_for_no_edges(
        self, semantic_map: SemanticMap
    ) -> None:
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        edges = semantic_map.get_edges_for_entity("e1")
        assert edges == []

    def test_get_edges_nonexistent_entity(
        self, semantic_map: SemanticMap
    ) -> None:
        edges = semantic_map.get_edges_for_entity("nonexistent")
        assert edges == []


# ---------------------------------------------------------------------------
# Tests: BFS Traversal
# ---------------------------------------------------------------------------

class TestBFSTraversal:

    def _build_chain(self, semantic_map: SemanticMap) -> None:
        """Build a chain: A -> B -> C -> D."""
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
        self._build_chain(semantic_map)
        related = semantic_map.query_related("A", max_depth=1)
        ids = {e.id for e in related}
        assert ids == {"B"}

    def test_depth_2_finds_two_hops(
        self, semantic_map: SemanticMap
    ) -> None:
        self._build_chain(semantic_map)
        related = semantic_map.query_related("A", max_depth=2)
        ids = {e.id for e in related}
        assert ids == {"B", "C"}

    def test_depth_3_finds_entire_chain(
        self, semantic_map: SemanticMap
    ) -> None:
        self._build_chain(semantic_map)
        related = semantic_map.query_related("A", max_depth=3)
        ids = {e.id for e in related}
        assert ids == {"B", "C", "D"}

    def test_does_not_include_starting_entity(
        self, semantic_map: SemanticMap
    ) -> None:
        self._build_chain(semantic_map)
        related = semantic_map.query_related("A", max_depth=10)
        ids = {e.id for e in related}
        assert "A" not in ids

    def test_excludes_expired_entities_from_results(
        self, semantic_map: SemanticMap
    ) -> None:
        self._build_chain(semantic_map)
        semantic_map.invalidate_entity("B", "No longer relevant")

        related = semantic_map.query_related("A", max_depth=3)
        ids = {e.id for e in related}
        assert "B" not in ids
        assert "C" in ids
        assert "D" in ids

    def test_query_related_nonexistent_entity(
        self, semantic_map: SemanticMap
    ) -> None:
        related = semantic_map.query_related("nonexistent")
        assert related == []

    def test_query_related_follows_reverse_edges(
        self, semantic_map: SemanticMap
    ) -> None:
        semantic_map.add_entity(_make_entity("A", "Alice"))
        semantic_map.add_entity(_make_entity("B", "Bob"))
        semantic_map.add_entity(_make_entity("C", "Charlie"))

        semantic_map.add_edge(_make_edge("B", "A", "knows"))
        semantic_map.add_edge(_make_edge("B", "C", "knows"))

        related = semantic_map.query_related("A", max_depth=2)
        ids = {e.id for e in related}
        assert "B" in ids
        assert "C" in ids


# ---------------------------------------------------------------------------
# Tests: Sensitive Topics
# ---------------------------------------------------------------------------

class TestSensitiveTopics:

    def test_returns_entities_above_threshold(
        self, semantic_map: SemanticMap
    ) -> None:
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
        semantic_map.add_entity(
            _make_entity("e1", "Therapy", sensitivity_level=0.9)
        )
        semantic_map.invalidate_entity("e1", "No longer relevant")

        results = semantic_map.get_sensitive_topics(threshold=0.7)
        assert len(results) == 0

    def test_default_threshold_is_0_7(
        self, semantic_map: SemanticMap
    ) -> None:
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

    def test_empty_graph_counts(self, semantic_map: SemanticMap) -> None:
        assert semantic_map.entity_count() == 0
        assert semantic_map.edge_count() == 0

    def test_entity_count_excludes_expired_by_default(
        self, semantic_map: SemanticMap
    ) -> None:
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        semantic_map.add_entity(_make_entity("e2", "John"))
        semantic_map.invalidate_entity("e2", "Test")

        assert semantic_map.entity_count() == 1
        assert semantic_map.entity_count(include_expired=True) == 2

    def test_edge_count(self, semantic_map: SemanticMap) -> None:
        semantic_map.add_entity(_make_entity("e1", "Sarah"))
        semantic_map.add_entity(_make_entity("e2", "John"))
        semantic_map.add_edge(_make_edge("e1", "e2", "knows"))

        assert semantic_map.edge_count() == 1


# ---------------------------------------------------------------------------
# Tests: Persistence (save/load round-trip)
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_save_and_load_preserves_entities(
        self, map_path: Path
    ) -> None:
        sm1 = SemanticMap(map_path)
        sm1.add_entity(
            _make_entity(
                "e1", "Sarah",
                sensitivity_level=0.8,
                source_session_ids=["sess-001", "sess-002"],
            )
        )
        sm1.save_to_disk()

        sm2 = SemanticMap(map_path)
        got = sm2.get_entity("e1")
        assert got is not None
        assert got.name == "Sarah"
        assert got.sensitivity_level == pytest.approx(0.8)
        assert got.source_session_ids == ["sess-001", "sess-002"]

    def test_save_and_load_preserves_edges(
        self, map_path: Path
    ) -> None:
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
        sm1 = SemanticMap(map_path)
        vf = datetime(2026, 1, 15, 10, 0, 0)
        sm1.add_entity(_make_entity("e1", "Sarah", valid_from=vf))
        sm1.save_to_disk()

        sm2 = SemanticMap(map_path)
        got = sm2.get_entity("e1")
        assert got is not None
        assert got.valid_from == vf

    def test_save_creates_parent_directory(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "c" / "map.json"
        sm = SemanticMap(deep_path)
        sm.add_entity(_make_entity("e1", "Sarah"))
        sm.save_to_disk()
        assert deep_path.exists()

    def test_load_nonexistent_file_creates_empty_graph(
        self, tmp_path: Path
    ) -> None:
        sm = SemanticMap(tmp_path / "nonexistent.json")
        assert sm.entity_count() == 0
        assert sm.edge_count() == 0

    def test_save_and_load_preserves_invalidated_entities(
        self, map_path: Path
    ) -> None:
        sm1 = SemanticMap(map_path)
        sm1.add_entity(_make_entity("e1", "Sarah"))
        sm1.invalidate_entity("e1", "Moved away")
        sm1.save_to_disk()

        sm2 = SemanticMap(map_path)
        got = sm2.get_entity("e1")
        assert got is not None
        assert got.valid_until is not None
        # Reason persists in graph node data
        reason = sm2.graph.nodes["e1"].get("invalidation_reason")
        assert reason == "Moved away"
