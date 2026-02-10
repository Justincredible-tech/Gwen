# Plan: Database Layer

**Track:** 003-database-layer
**Depends on:** 002-data-models (MessageRecord, SessionRecord, EmotionalStateVector, TME, CompassDirection, SessionType, SessionEndMode must exist in gwen/models/)
**Produces:** gwen/memory/__init__.py, gwen/memory/chronicle.py, tests/test_chronicle.py

---

## Phase 1: Database Initialization

### Step 1.1: Create gwen/memory/__init__.py

Create the file `gwen/memory/__init__.py` with the following exact content:

```python
"""Living Memory — Gwen's 5-tier persistence system."""
```

**Why:** This makes `gwen.memory` a Python package so that `from gwen.memory.chronicle import Chronicle` works.

---

### Step 1.2: Create gwen/memory/chronicle.py with schema constants

Create the file `gwen/memory/chronicle.py` with the following exact content. This step defines ONLY the schema constants and the `init_database()` function. The Chronicle class is added in Phase 2.

```python
"""
Chronicle — Tier 2 episodic memory backed by SQLite.

Stores every message and session with full emotional metadata.
References: SRS.md Section 3.3 (MessageRecord), 3.4 (SessionRecord), 6 (FR-MEM-002).
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from gwen.models.messages import MessageRecord, SessionRecord, SessionType, SessionEndMode
from gwen.models.emotional import EmotionalStateVector, CompassDirection


# ---------------------------------------------------------------------------
# SQL Schema
# ---------------------------------------------------------------------------

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id                      TEXT PRIMARY KEY,
    session_id              TEXT NOT NULL,
    timestamp               TEXT NOT NULL,
    sender                  TEXT NOT NULL CHECK(sender IN ('user', 'companion')),
    content                 TEXT NOT NULL,

    -- Emotional state (flattened from EmotionalStateVector)
    valence                 REAL,
    arousal                 REAL,
    dominance               REAL,
    relational_significance REAL,
    vulnerability_level     REAL,

    -- Storage modulation (computed by Amygdala Layer)
    storage_strength        REAL,
    is_flashbulb            INTEGER DEFAULT 0,

    -- Compass activation
    compass_direction       TEXT,
    compass_skill_used      TEXT,

    -- Embedding references (populated after encoding)
    semantic_embedding_id   TEXT,
    emotional_embedding_id  TEXT,

    -- Full TME snapshot serialised as JSON
    tme_json                TEXT,

    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""

CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id                          TEXT PRIMARY KEY,
    start_time                  TEXT NOT NULL,
    end_time                    TEXT,
    duration_sec                INTEGER NOT NULL DEFAULT 0,
    session_type                TEXT NOT NULL,
    end_mode                    TEXT NOT NULL,

    -- Emotional arc (serialised as JSON blobs)
    opening_emotional_state     TEXT,
    peak_emotional_state        TEXT,
    closing_emotional_state     TEXT,
    emotional_arc_embedding_id  TEXT,

    -- Subjective time weight
    avg_emotional_intensity     REAL,
    avg_relational_significance REAL,
    subjective_duration_weight  REAL,

    -- Statistics
    message_count               INTEGER DEFAULT 0,
    user_message_count          INTEGER DEFAULT 0,
    companion_message_count     INTEGER DEFAULT 0,
    avg_response_latency_sec    REAL,

    -- Compass activity (JSON dict: {direction: count})
    compass_activations         TEXT,

    -- Topics (JSON list of strings)
    topics                      TEXT,

    -- Relational delta (JSON dict: {dimension: change_amount})
    relational_field_delta      TEXT,

    -- Autonomy flag
    gwen_initiated              INTEGER DEFAULT 0
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_messages_timestamp  ON messages(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_messages_sender     ON messages(sender);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);",
]


def init_database(db_path: str | Path) -> sqlite3.Connection:
    """Create all tables and indexes, return the open connection.

    Parameters
    ----------
    db_path : str | Path
        Filesystem path to the SQLite database file.
        The parent directory must already exist (see ``ensure_data_dir``).

    Returns
    -------
    sqlite3.Connection
        An open connection with ``row_factory`` set to ``sqlite3.Row``
        so that rows behave like dicts.

    Example
    -------
    >>> conn = init_database("~/.gwen/data/chronicle.db")
    """
    db_path = Path(db_path).expanduser()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.execute(CREATE_MESSAGES_TABLE)
    conn.execute(CREATE_SESSIONS_TABLE)
    for idx_sql in CREATE_INDEXES:
        conn.execute(idx_sql)

    conn.commit()
    return conn
```

**Verification gate (manual):** After creating this file, confirm that `python -c "from gwen.memory.chronicle import init_database; print('OK')"` prints `OK`. If it fails because `gwen.models` does not exist yet, that is expected — track 002 must be completed first.

---

## Phase 2: Chronicle CRUD

Append the `Chronicle` class to `gwen/memory/chronicle.py` directly below the `init_database` function. Every method is documented individually below.

### Step 2.1: Chronicle class skeleton with __init__

Add the following to the **bottom** of `gwen/memory/chronicle.py`:

```python
# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_emotional_state(state: Optional[EmotionalStateVector]) -> Optional[str]:
    """Convert an EmotionalStateVector to a JSON string for SQLite storage."""
    if state is None:
        return None
    return json.dumps({
        "valence": state.valence,
        "arousal": state.arousal,
        "dominance": state.dominance,
        "relational_significance": state.relational_significance,
        "vulnerability_level": state.vulnerability_level,
        "compass_direction": state.compass_direction.value,
        "compass_confidence": state.compass_confidence,
    })


def _deserialize_emotional_state(raw: Optional[str]) -> Optional[EmotionalStateVector]:
    """Reconstruct an EmotionalStateVector from its JSON representation."""
    if raw is None:
        return None
    d = json.loads(raw)
    return EmotionalStateVector(
        valence=d["valence"],
        arousal=d["arousal"],
        dominance=d["dominance"],
        relational_significance=d["relational_significance"],
        vulnerability_level=d["vulnerability_level"],
        compass_direction=CompassDirection(d["compass_direction"]),
        compass_confidence=d["compass_confidence"],
    )


def _serialize_tme(tme) -> Optional[str]:
    """Serialize a TemporalMetadataEnvelope to JSON.

    Uses a simple dict with all fields converted to strings/primitives
    so the TME can round-trip through SQLite.
    """
    if tme is None:
        return None
    from dataclasses import asdict
    d = asdict(tme)
    # datetime objects need explicit conversion
    for key, val in d.items():
        if isinstance(val, datetime):
            d[key] = val.isoformat()
    # Enum values need explicit conversion
    if hasattr(tme, "time_phase") and tme.time_phase is not None:
        d["time_phase"] = tme.time_phase.value
    if hasattr(tme, "circadian_deviation_severity") and tme.circadian_deviation_severity is not None:
        d["circadian_deviation_severity"] = tme.circadian_deviation_severity.value
    return json.dumps(d)


class Chronicle:
    """Tier 2: The Chronicle — episodic memory backed by SQLite.

    Every conversation message and session is stored here with full
    emotional metadata.  The Chronicle is append-only; messages are
    never deleted by the system.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Open (or create) the Chronicle database.

        Parameters
        ----------
        db_path : str | Path
            Path to the SQLite file.  Tables are created automatically
            if they do not already exist.
        """
        self.db_path = Path(db_path).expanduser()
        self.conn = init_database(self.db_path)
```

**What this does:** Creates the Chronicle class that holds a connection. The `init_database` call inside `__init__` guarantees that the tables exist before any read/write.

---

### Step 2.2: insert_message()

Add the following method to the `Chronicle` class (indented inside the class body, directly after `__init__`):

```python
    def insert_message(self, message: MessageRecord) -> None:
        """Persist a single MessageRecord to the messages table.

        Parameters
        ----------
        message : MessageRecord
            The message to store.  Its ``tme`` and ``emotional_state``
            fields are serialised to JSON.

        Raises
        ------
        sqlite3.IntegrityError
            If a message with the same ``id`` already exists.
        """
        es = message.emotional_state
        self.conn.execute(
            """
            INSERT INTO messages (
                id, session_id, timestamp, sender, content,
                valence, arousal, dominance,
                relational_significance, vulnerability_level,
                storage_strength, is_flashbulb,
                compass_direction, compass_skill_used,
                semantic_embedding_id, emotional_embedding_id,
                tme_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                message.session_id,
                message.timestamp.isoformat(),
                message.sender,
                message.content,
                es.valence,
                es.arousal,
                es.dominance,
                es.relational_significance,
                es.vulnerability_level,
                message.storage_strength,
                int(message.is_flashbulb),
                message.compass_direction.value,
                message.compass_skill_used,
                message.semantic_embedding_id,
                message.emotional_embedding_id,
                _serialize_tme(message.tme),
            ),
        )
        self.conn.commit()
```

**What this does:** Flattens the EmotionalStateVector fields into individual columns (for indexed queries) and stores the full TME as a JSON blob.

---

### Step 2.3: insert_session()

Add the following method to the `Chronicle` class:

```python
    def insert_session(self, session: SessionRecord) -> None:
        """Persist a SessionRecord to the sessions table.

        Parameters
        ----------
        session : SessionRecord
            The session to store.  Emotional state snapshots, compass
            activations, topics, and relational delta are serialised
            to JSON.
        """
        self.conn.execute(
            """
            INSERT INTO sessions (
                id, start_time, end_time, duration_sec,
                session_type, end_mode,
                opening_emotional_state, peak_emotional_state,
                closing_emotional_state, emotional_arc_embedding_id,
                avg_emotional_intensity, avg_relational_significance,
                subjective_duration_weight,
                message_count, user_message_count,
                companion_message_count, avg_response_latency_sec,
                compass_activations, topics,
                relational_field_delta, gwen_initiated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.start_time.isoformat(),
                session.end_time.isoformat() if session.end_time else None,
                session.duration_sec,
                session.session_type.value,
                session.end_mode.value,
                _serialize_emotional_state(session.opening_emotional_state),
                _serialize_emotional_state(session.peak_emotional_state),
                _serialize_emotional_state(session.closing_emotional_state),
                session.emotional_arc_embedding_id,
                session.avg_emotional_intensity,
                session.avg_relational_significance,
                session.subjective_duration_weight,
                session.message_count,
                session.user_message_count,
                session.companion_message_count,
                session.avg_response_latency_sec,
                json.dumps(
                    {k.value if hasattr(k, "value") else k: v
                     for k, v in session.compass_activations.items()}
                ),
                json.dumps(session.topics),
                json.dumps(session.relational_field_delta),
                int(session.gwen_initiated),
            ),
        )
        self.conn.commit()
```

---

### Step 2.4: get_messages_by_session()

Add the following method to the `Chronicle` class:

```python
    def get_messages_by_session(self, session_id: str) -> list[MessageRecord]:
        """Return all messages for a session, ordered by timestamp ascending.

        Parameters
        ----------
        session_id : str
            The UUID of the session to look up.

        Returns
        -------
        list[MessageRecord]
            Empty list if no messages are found for this session.
        """
        cursor = self.conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        )
        return [self._row_to_message(row) for row in cursor.fetchall()]

    # -- private helper -------------------------------------------------------

    def _row_to_message(self, row: sqlite3.Row) -> MessageRecord:
        """Convert a sqlite3.Row from the messages table to a MessageRecord."""
        tme_raw = row["tme_json"]
        # TME deserialization is deferred to track 006 (tme-generator).
        # For now we store the raw JSON and set tme=None on the record
        # so that Chronicle can be used before the temporal module exists.
        tme = None  # TODO(track-006): deserialize TME from JSON

        emotional_state = EmotionalStateVector(
            valence=row["valence"] or 0.0,
            arousal=row["arousal"] or 0.0,
            dominance=row["dominance"] or 0.0,
            relational_significance=row["relational_significance"] or 0.0,
            vulnerability_level=row["vulnerability_level"] or 0.0,
            compass_direction=CompassDirection(row["compass_direction"])
                if row["compass_direction"] else CompassDirection.NONE,
        )

        return MessageRecord(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            sender=row["sender"],
            content=row["content"],
            tme=tme,
            emotional_state=emotional_state,
            storage_strength=row["storage_strength"] or 0.0,
            is_flashbulb=bool(row["is_flashbulb"]),
            compass_direction=CompassDirection(row["compass_direction"])
                if row["compass_direction"] else CompassDirection.NONE,
            compass_skill_used=row["compass_skill_used"],
            semantic_embedding_id=row["semantic_embedding_id"],
            emotional_embedding_id=row["emotional_embedding_id"],
        )
```

**What this does:** Queries by `session_id` (uses the index), reconstitutes every column back into the dataclass. The TME is left as `None` for now because the TME dataclass deserializer belongs to track 006.

---

### Step 2.5: get_session()

Add the following method to the `Chronicle` class:

```python
    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """Return a single SessionRecord by ID, or None if not found.

        Parameters
        ----------
        session_id : str
            The UUID of the session.
        """
        cursor = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def _row_to_session(self, row: sqlite3.Row) -> SessionRecord:
        """Convert a sqlite3.Row from the sessions table to a SessionRecord."""
        compass_raw = json.loads(row["compass_activations"]) if row["compass_activations"] else {}
        # Convert string keys back to CompassDirection enums
        compass_activations: dict = {}
        for k, v in compass_raw.items():
            try:
                compass_activations[CompassDirection(k)] = v
            except ValueError:
                compass_activations[k] = v

        return SessionRecord(
            id=row["id"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            duration_sec=row["duration_sec"],
            session_type=SessionType(row["session_type"]),
            end_mode=SessionEndMode(row["end_mode"]),
            opening_emotional_state=_deserialize_emotional_state(
                row["opening_emotional_state"]
            ),
            peak_emotional_state=_deserialize_emotional_state(
                row["peak_emotional_state"]
            ),
            closing_emotional_state=_deserialize_emotional_state(
                row["closing_emotional_state"]
            ),
            emotional_arc_embedding_id=row["emotional_arc_embedding_id"],
            avg_emotional_intensity=row["avg_emotional_intensity"] or 0.0,
            avg_relational_significance=row["avg_relational_significance"] or 0.0,
            subjective_duration_weight=row["subjective_duration_weight"] or 0.0,
            message_count=row["message_count"] or 0,
            user_message_count=row["user_message_count"] or 0,
            companion_message_count=row["companion_message_count"] or 0,
            avg_response_latency_sec=row["avg_response_latency_sec"] or 0.0,
            compass_activations=compass_activations,
            topics=json.loads(row["topics"]) if row["topics"] else [],
            relational_field_delta=json.loads(row["relational_field_delta"])
                if row["relational_field_delta"] else {},
            gwen_initiated=bool(row["gwen_initiated"]),
        )
```

---

### Step 2.6: search_messages()

Add the following method to the `Chronicle` class:

```python
    def search_messages(self, query: str, limit: int = 20) -> list[MessageRecord]:
        """Full-text search over message content using SQL LIKE.

        This is a simple substring match.  For semantic search, use the
        EmbeddingService (track 009) with ChromaDB instead.

        Parameters
        ----------
        query : str
            The search term.  Wrapped in ``%`` wildcards automatically.
        limit : int
            Maximum number of results to return.  Defaults to 20.

        Returns
        -------
        list[MessageRecord]
            Matching messages ordered by timestamp descending (newest first).
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM messages
            WHERE content LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        )
        return [self._row_to_message(row) for row in cursor.fetchall()]
```

---

### Step 2.7: get_messages_in_range()

Add the following method to the `Chronicle` class:

```python
    def get_messages_in_range(
        self, start: datetime, end: datetime
    ) -> list[MessageRecord]:
        """Return all messages whose timestamp falls in [start, end].

        Parameters
        ----------
        start : datetime
            Inclusive lower bound.
        end : datetime
            Inclusive upper bound.

        Returns
        -------
        list[MessageRecord]
            Matching messages ordered by timestamp ascending.
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM messages
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (start.isoformat(), end.isoformat()),
        )
        return [self._row_to_message(row) for row in cursor.fetchall()]
```

---

## Phase 3: ChromaDB Setup

### Step 3.1: Add ChromaDB initialization to chronicle.py

Add the following **module-level function** to `gwen/memory/chronicle.py`, **below** the `Chronicle` class definition:

```python
# ---------------------------------------------------------------------------
# ChromaDB vector store initialization
# ---------------------------------------------------------------------------

def init_chromadb(data_dir: str | Path) -> tuple:
    """Create a ChromaDB PersistentClient and two collections.

    Parameters
    ----------
    data_dir : str | Path
        Base data directory (e.g. ``~/.gwen/data``).  ChromaDB files
        will be stored under ``<data_dir>/embeddings/``.

    Returns
    -------
    tuple[chromadb.PersistentClient, chromadb.Collection, chromadb.Collection]
        A 3-tuple of ``(client, semantic_collection, emotional_collection)``.

    Notes
    -----
    - ``semantic_embeddings`` — stores 1024-dimensional vectors produced by
      ``qwen3-embedding:0.6b`` via Ollama.  Used for semantic similarity
      search in retrieval (track 009).
    - ``emotional_embeddings`` — stores 5-dimensional vectors built from
      the EmotionalStateVector ``(valence, arousal, dominance,
      relational_significance, vulnerability_level)``.  Used for mood-
      congruent retrieval (track 013).
    """
    import chromadb

    embeddings_path = Path(data_dir).expanduser() / "embeddings"
    embeddings_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(embeddings_path))

    semantic_collection = client.get_or_create_collection(
        name="semantic_embeddings",
        metadata={"description": "1024-dim semantic vectors from qwen3-embedding:0.6b"},
    )

    emotional_collection = client.get_or_create_collection(
        name="emotional_embeddings",
        metadata={"description": "5-dim emotional state vectors (VAD + RS + VL)"},
    )

    return client, semantic_collection, emotional_collection
```

**What this does:**
1. Creates the `embeddings/` subdirectory if it does not exist.
2. Opens a ChromaDB PersistentClient pointed at that directory.
3. Creates (or opens) two collections: one for semantic embeddings (1024-dim from qwen3-embedding:0.6b) and one for emotional embeddings (5-dim from the EmotionalStateVector).
4. Returns all three objects so the caller can pass them to the EmbeddingService (track 009).

---

## Phase 4: Data Directory

### Step 4.1: Add ensure_data_dir() to chronicle.py

Add the following **module-level function** to `gwen/memory/chronicle.py`, **above** the `init_database` function (near the top, after the schema constants):

```python
def ensure_data_dir(base_path: str | Path = "~/.gwen/data") -> Path:
    """Create the Gwen data directory structure if it does not exist.

    Parameters
    ----------
    base_path : str | Path
        Root of the data directory.  Defaults to ``~/.gwen/data``.
        The ``~`` is expanded automatically.

    Returns
    -------
    Path
        The resolved, absolute base_path.

    Creates
    -------
    ``<base_path>/``
        Main data directory.
    ``<base_path>/embeddings/``
        ChromaDB persistent storage.

    Example
    -------
    >>> data_dir = ensure_data_dir()
    >>> print(data_dir)  # e.g. /home/user/.gwen/data
    """
    base = Path(base_path).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    (base / "embeddings").mkdir(parents=True, exist_ok=True)
    return base
```

**What this does:** Ensures that `~/.gwen/data/` and `~/.gwen/data/embeddings/` both exist. Safe to call multiple times (idempotent via `exist_ok=True`).

---

## Phase 5: Verification

### Step 5.1: Write tests/test_chronicle.py

Create the file `tests/test_chronicle.py` with the following exact content:

```python
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
    """Return a Chronicle instance backed by a temporary database."""
    return Chronicle(tmp_db)


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
        session = _make_session()
        chronicle.insert_session(session)

        got = chronicle.get_session("sess-001")
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
        session = _make_session()
        chronicle.insert_session(session)

        got = chronicle.get_session("sess-001")
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
```

---

### Step 5.2: Run the tests

Execute the following command from the project root:

```bash
pytest tests/test_chronicle.py -v
```

**Expected result:** All tests pass. If any test fails, read the error message carefully. The most likely causes are:

1. **ImportError for gwen.models**: Track 002 (data-models) has not been completed yet. The models (MessageRecord, SessionRecord, EmotionalStateVector, CompassDirection, SessionType, SessionEndMode) must exist in `gwen/models/` before these tests can run.
2. **ModuleNotFoundError for chromadb**: Run `pip install chromadb` (see tech-stack.md).
3. **Assertion failures**: Compare the test's expected values against the serialization/deserialization logic in chronicle.py.

---

## Checklist (update after each step)

- [x] Phase 1 complete: gwen/memory/__init__.py and chronicle.py with schema + init_database (Done)
- [x] Phase 2 complete: Chronicle class with all 7 methods (Done: insert_message, insert_session, get_messages_by_session, get_session, search_messages, get_messages_in_range, _row_to_message, _row_to_session)
- [x] Phase 3 complete: init_chromadb() function with two collections (Done)
- [x] Phase 4 complete: ensure_data_dir() function (Done)
- [x] Phase 5 complete: tests/test_chronicle.py passes with all tests green (Done: 17 passed in 1.40s)

**Note:** Test fixture was modified from the plan to pre-insert a default session (`sess-001`) to satisfy the FK constraint on the messages table. Session CRUD tests use `sess-100`/`sess-101` to avoid UNIQUE conflicts.
