"""Tests for gwen.memory.chronicle — the Chronicle (Tier 2 episodic memory).

Run with:
    pytest tests/test_chronicle.py -v
"""

import json
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from gwen.memory.chronicle import (
    Chronicle,
    ensure_data_dir,
    init_chromadb,
    init_database,
)
from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.messages import (
    MessageRecord,
    SessionEndMode,
    SessionRecord,
    SessionType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to a temporary SQLite database file."""
    return tmp_path / "test_chronicle.db"


@pytest.fixture()
def chronicle(tmp_db: Path) -> Chronicle:
    """Return a Chronicle instance backed by a temporary database.

    Pre-inserts a default session ('sess-001') so that message inserts
    with session_id='sess-001' do not violate the foreign key constraint.
    """
    c = Chronicle(tmp_db)
    # Insert a default session to satisfy FK constraints in message tests
    c.conn.execute(
        """
        INSERT INTO sessions (id, start_time, duration_sec, session_type, end_mode)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("sess-001", "2026-02-09T14:00:00", 2700, "chat", "natural"),
    )
    c.conn.commit()
    return c


def _make_emotional_state(**overrides) -> EmotionalStateVector:
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


def _make_message(
    session_id: str = "sess-001",
    content: str = "Hello, Gwen!",
    sender: str = "user",
    **overrides,
) -> MessageRecord:
    """Create a MessageRecord with sensible defaults."""
    defaults = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "timestamp": datetime(2026, 2, 9, 14, 30, 0),
        "sender": sender,
        "content": content,
        "tme": None,
        "emotional_state": _make_emotional_state(),
        "storage_strength": 0.34,
        "is_flashbulb": False,
        "compass_direction": CompassDirection.NONE,
        "compass_skill_used": None,
        "semantic_embedding_id": None,
        "emotional_embedding_id": None,
    }
    defaults.update(overrides)
    return MessageRecord(**defaults)


def _make_session(session_id: str = "sess-001", **overrides) -> SessionRecord:
    """Create a SessionRecord with sensible defaults."""
    defaults = {
        "id": session_id,
        "start_time": datetime(2026, 2, 9, 14, 0, 0),
        "end_time": datetime(2026, 2, 9, 14, 45, 0),
        "duration_sec": 2700,
        "session_type": SessionType.CHAT,
        "end_mode": SessionEndMode.NATURAL,
        "opening_emotional_state": _make_emotional_state(valence=0.5),
        "peak_emotional_state": _make_emotional_state(arousal=0.9),
        "closing_emotional_state": _make_emotional_state(valence=0.7),
        "emotional_arc_embedding_id": None,
        "avg_emotional_intensity": 0.55,
        "avg_relational_significance": 0.4,
        "subjective_duration_weight": 1485.0,
        "message_count": 20,
        "user_message_count": 10,
        "companion_message_count": 10,
        "avg_response_latency_sec": 1.2,
        "compass_activations": {CompassDirection.NORTH: 3, CompassDirection.SOUTH: 1},
        "topics": ["work", "weekend plans"],
        "relational_field_delta": {"warmth": 0.05, "trust": 0.02},
        "gwen_initiated": False,
    }
    defaults.update(overrides)
    return SessionRecord(**defaults)


# ---------------------------------------------------------------------------
# Tests: Database initialization
# ---------------------------------------------------------------------------

class TestInitDatabase:
    """Tests for init_database()."""

    def test_creates_tables(self, tmp_db: Path) -> None:
        """init_database should create the messages and sessions tables."""
        conn = init_database(tmp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "messages" in table_names
        assert "sessions" in table_names
        conn.close()

    def test_creates_indexes(self, tmp_db: Path) -> None:
        """init_database should create all four indexes."""
        conn = init_database(tmp_db)
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchall()
        index_names = {i["name"] for i in indexes}
        assert "idx_messages_session_id" in index_names
        assert "idx_messages_timestamp" in index_names
        assert "idx_messages_sender" in index_names
        assert "idx_sessions_start_time" in index_names
        conn.close()

    def test_idempotent(self, tmp_db: Path) -> None:
        """Calling init_database twice on the same file should not error."""
        conn1 = init_database(tmp_db)
        conn1.close()
        conn2 = init_database(tmp_db)
        conn2.close()


# ---------------------------------------------------------------------------
# Tests: Message CRUD
# ---------------------------------------------------------------------------

class TestMessageCRUD:
    """Tests for insert_message, get_messages_by_session, search, range."""

    def test_insert_and_retrieve_message(self, chronicle: Chronicle) -> None:
        """Inserting a message and retrieving it should produce identical fields."""
        msg = _make_message(content="I had a great day today")
        chronicle.insert_message(msg)

        results = chronicle.get_messages_by_session("sess-001")
        assert len(results) == 1

        got = results[0]
        assert got.id == msg.id
        assert got.session_id == msg.session_id
        assert got.timestamp == msg.timestamp
        assert got.sender == msg.sender
        assert got.content == msg.content
        assert got.storage_strength == pytest.approx(msg.storage_strength)
        assert got.is_flashbulb == msg.is_flashbulb
        assert got.compass_direction == msg.compass_direction
        assert got.emotional_state.valence == pytest.approx(
            msg.emotional_state.valence
        )
        assert got.emotional_state.arousal == pytest.approx(
            msg.emotional_state.arousal
        )

    def test_multiple_messages_ordered_by_timestamp(
        self, chronicle: Chronicle
    ) -> None:
        """Messages should come back ordered by timestamp ascending."""
        t1 = datetime(2026, 2, 9, 10, 0, 0)
        t2 = datetime(2026, 2, 9, 10, 5, 0)
        t3 = datetime(2026, 2, 9, 10, 10, 0)

        # Insert in reverse order to verify ordering
        chronicle.insert_message(_make_message(content="Third", timestamp=t3))
        chronicle.insert_message(_make_message(content="First", timestamp=t1))
        chronicle.insert_message(_make_message(content="Second", timestamp=t2))

        results = chronicle.get_messages_by_session("sess-001")
        assert [m.content for m in results] == ["First", "Second", "Third"]

    def test_search_messages_finds_match(self, chronicle: Chronicle) -> None:
        """search_messages should return messages containing the query string."""
        chronicle.insert_message(_make_message(content="I love playing guitar"))
        chronicle.insert_message(_make_message(content="Work was stressful"))
        chronicle.insert_message(_make_message(content="Guitar practice tonight"))

        results = chronicle.search_messages("guitar")
        # LIKE is case-insensitive on ASCII in SQLite by default
        assert len(results) >= 1
        for r in results:
            assert "guitar" in r.content.lower()

    def test_search_messages_respects_limit(self, chronicle: Chronicle) -> None:
        """search_messages should not return more than ``limit`` results."""
        for i in range(10):
            chronicle.insert_message(
                _make_message(content=f"Repeated topic number {i}")
            )
        results = chronicle.search_messages("topic", limit=3)
        assert len(results) == 3

    def test_get_messages_in_range(self, chronicle: Chronicle) -> None:
        """get_messages_in_range should return only messages within the window."""
        t_before = datetime(2026, 2, 8, 23, 0, 0)
        t_inside = datetime(2026, 2, 9, 12, 0, 0)
        t_after = datetime(2026, 2, 10, 1, 0, 0)

        chronicle.insert_message(
            _make_message(content="Before", timestamp=t_before)
        )
        chronicle.insert_message(
            _make_message(content="Inside", timestamp=t_inside)
        )
        chronicle.insert_message(
            _make_message(content="After", timestamp=t_after)
        )

        start = datetime(2026, 2, 9, 0, 0, 0)
        end = datetime(2026, 2, 9, 23, 59, 59)
        results = chronicle.get_messages_in_range(start, end)
        assert len(results) == 1
        assert results[0].content == "Inside"

    def test_empty_session_returns_empty_list(self, chronicle: Chronicle) -> None:
        """Querying a session with no messages should return []."""
        results = chronicle.get_messages_by_session("nonexistent-session")
        assert results == []


# ---------------------------------------------------------------------------
# Tests: Session CRUD
# ---------------------------------------------------------------------------

class TestSessionCRUD:
    """Tests for insert_session and get_session."""

    def test_insert_and_retrieve_session(self, chronicle: Chronicle) -> None:
        """Round-trip a SessionRecord through insert and get."""
        session = _make_session(session_id="sess-100")
        chronicle.insert_session(session)

        got = chronicle.get_session("sess-100")
        assert got is not None
        assert got.id == session.id
        assert got.start_time == session.start_time
        assert got.end_time == session.end_time
        assert got.duration_sec == session.duration_sec
        assert got.session_type == session.session_type
        assert got.end_mode == session.end_mode
        assert got.message_count == session.message_count
        assert got.topics == session.topics
        assert got.gwen_initiated == session.gwen_initiated

    def test_session_emotional_states_round_trip(
        self, chronicle: Chronicle
    ) -> None:
        """Emotional state snapshots should survive serialization."""
        session = _make_session(session_id="sess-101")
        chronicle.insert_session(session)

        got = chronicle.get_session("sess-101")
        assert got is not None
        assert got.opening_emotional_state is not None
        assert got.opening_emotional_state.valence == pytest.approx(0.5)
        assert got.peak_emotional_state is not None
        assert got.peak_emotional_state.arousal == pytest.approx(0.9)

    def test_get_nonexistent_session_returns_none(
        self, chronicle: Chronicle
    ) -> None:
        """get_session with an unknown ID should return None."""
        assert chronicle.get_session("does-not-exist") is None


# ---------------------------------------------------------------------------
# Tests: Data directory
# ---------------------------------------------------------------------------

class TestEnsureDataDir:
    """Tests for ensure_data_dir()."""

    def test_creates_directory_structure(self, tmp_path: Path) -> None:
        """ensure_data_dir should create data/ and data/embeddings/."""
        data_dir = tmp_path / "gwen_data"
        result = ensure_data_dir(data_dir)
        assert result.exists()
        assert (result / "embeddings").exists()

    def test_idempotent(self, tmp_path: Path) -> None:
        """Calling ensure_data_dir twice should not raise."""
        data_dir = tmp_path / "gwen_data"
        ensure_data_dir(data_dir)
        ensure_data_dir(data_dir)


# ---------------------------------------------------------------------------
# Tests: ChromaDB initialization
# ---------------------------------------------------------------------------

class TestChromaDB:
    """Tests for init_chromadb()."""

    def test_creates_collections(self, tmp_path: Path) -> None:
        """init_chromadb should create semantic and emotional collections."""
        client, semantic, emotional = init_chromadb(tmp_path)
        assert semantic.name == "semantic_embeddings"
        assert emotional.name == "emotional_embeddings"

    def test_collections_accept_vectors(self, tmp_path: Path) -> None:
        """Collections should accept and return dummy vectors."""
        client, semantic, emotional = init_chromadb(tmp_path)

        # Semantic: 1024-dim vector
        semantic.add(
            ids=["test-sem-001"],
            embeddings=[[0.1] * 1024],
            documents=["Hello world"],
        )
        result = semantic.get(ids=["test-sem-001"], include=["embeddings"])
        assert len(result["ids"]) == 1

        # Emotional: 5-dim vector
        emotional.add(
            ids=["test-emo-001"],
            embeddings=[[0.6, 0.4, 0.5, 0.3, 0.2]],
            documents=["emotional snapshot"],
        )
        result = emotional.get(ids=["test-emo-001"], include=["embeddings"])
        assert len(result["ids"]) == 1

    def test_idempotent(self, tmp_path: Path) -> None:
        """Calling init_chromadb twice should not duplicate collections."""
        client1, _, _ = init_chromadb(tmp_path)
        client2, _, _ = init_chromadb(tmp_path)
        collections = client2.list_collections()
        names = [c.name for c in collections]
        assert names.count("semantic_embeddings") == 1
        assert names.count("emotional_embeddings") == 1
