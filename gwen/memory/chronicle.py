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

    def get_last_n_sessions(self, n: int = 30) -> list[SessionRecord]:
        """Return the N most recent completed sessions, newest first.

        Parameters
        ----------
        n : int
            Maximum number of sessions to return.  Defaults to 30.

        Returns
        -------
        list[SessionRecord]
            Sessions ordered by start_time descending (newest first).
            Returns an empty list if no sessions exist.
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM sessions
            ORDER BY start_time DESC
            LIMIT ?
            """,
            (n,),
        )
        return [self._row_to_session(row) for row in cursor.fetchall()]

    # -- private helpers ------------------------------------------------------

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
