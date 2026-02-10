# Plan: Memory Reconsolidation (Palimpsest Model)

**Track:** 018-reconsolidation
**Spec:** [spec.md](./spec.md)
**Depends on:** 003-database-layer (Chronicle, init_database), 013-amygdala-layer (emotional tagging must exist), 002-data-models (ReconsolidationLayer, ReconsolidationConstraints, MemoryPalimpsest, MessageRecord, EmotionalStateVector)
**Produces:** gwen/memory/palimpsest.py, tests/test_palimpsest.py
**Status:** Not Started

---

## Phase 1: SQLite Schema for Palimpsests

### Step 1.1: Create gwen/memory/palimpsest.py with schema constants

Create the file `gwen/memory/palimpsest.py`. This step defines the SQL schema for the palimpsests table and the reconsolidation_layers table, plus the `init_palimpsest_tables()` function that creates them.

- [ ] Write schema constants and init function to gwen/memory/palimpsest.py

**File: `gwen/memory/palimpsest.py`** (initial content -- Phase 2 appends the PalimpsestManager class)

```python
"""
PalimpsestManager — Memory reconsolidation with bounded drift.

The Palimpsest model stores memories with an immutable archive and
append-only reconsolidation layers.  The original memory is never modified;
new understanding is layered on top.  Emotional drift is bounded by
ReconsolidationConstraints to prevent runaway rewriting.

References: SRS.md Section 3.15
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.messages import MessageRecord
from gwen.models.reconsolidation import (
    MemoryPalimpsest,
    ReconsolidationConstraints,
    ReconsolidationLayer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQL Schema
# ---------------------------------------------------------------------------

CREATE_PALIMPSESTS_TABLE = """
CREATE TABLE IF NOT EXISTS palimpsests (
    message_id  TEXT PRIMARY KEY REFERENCES messages(id),
    created_at  TEXT NOT NULL
);
"""

CREATE_RECONSOLIDATION_LAYERS_TABLE = """
CREATE TABLE IF NOT EXISTS reconsolidation_layers (
    id                          TEXT PRIMARY KEY,
    message_id                  TEXT NOT NULL REFERENCES palimpsests(message_id),
    timestamp                   TEXT NOT NULL,
    recall_session_id           TEXT,
    user_emotional_state_json   TEXT,
    conversation_topic_at_recall TEXT,
    reaction_type               TEXT,
    reaction_detail             TEXT,
    valence_delta               REAL,
    arousal_delta               REAL,
    significance_delta          REAL,
    narrative                   TEXT
);
"""

CREATE_LAYERS_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_layers_message "
    "ON reconsolidation_layers(message_id);"
)


def init_palimpsest_tables(conn: sqlite3.Connection) -> None:
    """Create palimpsests and reconsolidation_layers tables if they do not exist.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open database connection (typically the same Chronicle connection).

    This function is idempotent -- safe to call multiple times.  It uses
    CREATE TABLE IF NOT EXISTS so it will not error on an already-initialised
    database.
    """
    conn.execute(CREATE_PALIMPSESTS_TABLE)
    conn.execute(CREATE_RECONSOLIDATION_LAYERS_TABLE)
    conn.execute(CREATE_LAYERS_INDEX)
    conn.commit()
    logger.info("Palimpsest tables initialised.")
```

**What this does:**
- Defines the SQL for two tables: `palimpsests` (which links a message_id to the palimpsest system) and `reconsolidation_layers` (which stores each layer of reinterpretation).
- The `message_id` in `palimpsests` is a foreign key to the `messages` table (created by Chronicle in track 003).
- The index `idx_layers_message` on `reconsolidation_layers(message_id)` makes layer lookups fast when loading a palimpsest.
- `init_palimpsest_tables()` creates both tables and the index.  It is safe to call multiple times.

**Verification gate (mental check):**
- The `palimpsests` table has exactly one column beyond the primary key: `created_at`.
- The `reconsolidation_layers` table stores all fields from `ReconsolidationLayer` plus the `message_id` foreign key.
- The `user_emotional_state_json` column stores the `user_emotional_state_at_recall` field as a JSON blob (serialized EmotionalStateVector).

---

## Phase 2: Palimpsest Manager

### Step 2.1: Add serialization helpers

Append the following serialization helpers to `gwen/memory/palimpsest.py`, directly below the `init_palimpsest_tables()` function.

- [ ] Append serialization helpers to gwen/memory/palimpsest.py

**Append to `gwen/memory/palimpsest.py`:**

```python


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_emotional_state(state: EmotionalStateVector) -> str:
    """Convert an EmotionalStateVector to a JSON string for SQLite storage.

    Parameters
    ----------
    state : EmotionalStateVector
        The emotional state to serialize.

    Returns
    -------
    str
        A JSON string with all 7 fields of the EmotionalStateVector.
    """
    return json.dumps({
        "valence": state.valence,
        "arousal": state.arousal,
        "dominance": state.dominance,
        "relational_significance": state.relational_significance,
        "vulnerability_level": state.vulnerability_level,
        "compass_direction": state.compass_direction.value,
        "compass_confidence": state.compass_confidence,
    })


def _deserialize_emotional_state(raw: str) -> EmotionalStateVector:
    """Reconstruct an EmotionalStateVector from its JSON representation.

    Parameters
    ----------
    raw : str
        A JSON string previously produced by ``_serialize_emotional_state``.

    Returns
    -------
    EmotionalStateVector
        The reconstituted emotional state.
    """
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
```

---

### Step 2.2: Add PalimpsestManager class with __init__

Append the PalimpsestManager class skeleton to `gwen/memory/palimpsest.py`, directly below the serialization helpers.

- [ ] Append PalimpsestManager class with __init__ to gwen/memory/palimpsest.py

**Append to `gwen/memory/palimpsest.py`:**

```python


# ---------------------------------------------------------------------------
# PalimpsestManager
# ---------------------------------------------------------------------------

class PalimpsestManager:
    """Manages creation, layer addition, and querying of Memory Palimpsests.

    The PalimpsestManager is the only gateway for reconsolidation operations.
    It enforces all constraints (per-layer delta limits, total drift limits,
    cooldown periods, significance-only-increases) and persists everything
    to SQLite.

    Usage
    -----
    >>> from gwen.memory.palimpsest import PalimpsestManager
    >>> mgr = PalimpsestManager(db_path="~/.gwen/data/chronicle.db")
    >>> palimpsest = mgr.create_palimpsest(some_message_record)
    >>> success = mgr.add_layer("msg-001", some_layer)
    >>> reading = mgr.get_current_reading("msg-001")
    """

    def __init__(self, db_path: str | Path) -> None:
        """Open (or create) the database and ensure palimpsest tables exist.

        Parameters
        ----------
        db_path : str | Path
            Path to the SQLite database file.  This should be the same
            database used by the Chronicle (track 003).  The palimpsest
            tables are created alongside the messages and sessions tables.
        """
        self.db_path = Path(db_path).expanduser()
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        init_palimpsest_tables(self.conn)
        self.constraints = ReconsolidationConstraints()
```

**What this does:** Opens the SQLite connection, enables WAL mode and foreign keys, and calls `init_palimpsest_tables()` to ensure the tables exist.  The `self.constraints` field holds the default reconsolidation limits.

---

### Step 2.3: Add create_palimpsest() method

Add the following method to the `PalimpsestManager` class, directly after `__init__`.

- [ ] Add create_palimpsest() to PalimpsestManager

**Append inside the PalimpsestManager class:**

```python
    def create_palimpsest(self, message: MessageRecord) -> MemoryPalimpsest:
        """Create a new palimpsest from a MessageRecord.

        The MessageRecord becomes the immutable archive.  It is never
        modified after this point.  The palimpsest starts with zero
        reconsolidation layers.

        Parameters
        ----------
        message : MessageRecord
            The original message to wrap in a palimpsest.  This message
            must already exist in the ``messages`` table (inserted by
            the Chronicle).

        Returns
        -------
        MemoryPalimpsest
            A new palimpsest with the given message as its archive and
            an empty list of layers.

        Raises
        ------
        sqlite3.IntegrityError
            If a palimpsest already exists for this message_id.
        """
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO palimpsests (message_id, created_at) VALUES (?, ?)",
            (message.id, now),
        )
        self.conn.commit()
        logger.info("Created palimpsest for message %s", message.id)
        return MemoryPalimpsest(
            archive=message,
            layers=[],
            constraints=self.constraints,
        )
```

**What this does:** Inserts a row into the `palimpsests` table with the message_id and the current UTC timestamp.  Returns a `MemoryPalimpsest` with no layers.

---

### Step 2.4: Add add_layer() method

Add the following method to the `PalimpsestManager` class, directly after `create_palimpsest`.

- [ ] Add add_layer() to PalimpsestManager

**Append inside the PalimpsestManager class:**

```python
    def add_layer(
        self, message_id: str, layer: ReconsolidationLayer
    ) -> bool:
        """Add a reconsolidation layer to an existing palimpsest.

        This method enforces ALL reconsolidation constraints before
        inserting the layer.  If any constraint is violated, the layer
        is rejected and this method returns False.

        Constraints enforced
        --------------------
        1. **Per-layer valence delta:** ``abs(layer.valence_delta)``
           must be <= ``MAX_DELTA_PER_LAYER`` (default 0.10).
        2. **Per-layer arousal delta:** ``abs(layer.arousal_delta)``
           must be <= ``MAX_DELTA_PER_LAYER`` (default 0.10).
        3. **Significance can only increase:**
           ``layer.significance_delta`` must be >= 0.0.
        4. **Per-layer significance delta:**
           ``layer.significance_delta`` must be <= ``MAX_DELTA_PER_LAYER``.
        5. **Total valence drift:** The sum of all existing valence_delta
           values plus this layer's valence_delta must not exceed
           ``MAX_TOTAL_DRIFT`` (default 0.50) in absolute value.
        6. **Total arousal drift:** Same as above for arousal.
        7. **Cooldown:** The most recent existing layer's timestamp must
           be at least ``COOLDOWN_HOURS`` (default 24.0) before now.

        Parameters
        ----------
        message_id : str
            The message_id of the palimpsest to add the layer to.
        layer : ReconsolidationLayer
            The layer to add.

        Returns
        -------
        bool
            True if the layer was accepted and inserted.
            False if any constraint was violated (the layer is NOT inserted).
        """
        c = self.constraints

        # --- Constraint 1: Per-layer valence delta ---
        if abs(layer.valence_delta) > c.MAX_DELTA_PER_LAYER:
            logger.warning(
                "Rejected layer for %s: valence_delta %.3f exceeds "
                "MAX_DELTA_PER_LAYER %.2f",
                message_id, layer.valence_delta, c.MAX_DELTA_PER_LAYER,
            )
            return False

        # --- Constraint 2: Per-layer arousal delta ---
        if abs(layer.arousal_delta) > c.MAX_DELTA_PER_LAYER:
            logger.warning(
                "Rejected layer for %s: arousal_delta %.3f exceeds "
                "MAX_DELTA_PER_LAYER %.2f",
                message_id, layer.arousal_delta, c.MAX_DELTA_PER_LAYER,
            )
            return False

        # --- Constraint 3: Significance can only increase ---
        if layer.significance_delta < 0.0:
            logger.warning(
                "Rejected layer for %s: significance_delta %.3f is negative "
                "(significance can only increase)",
                message_id, layer.significance_delta,
            )
            return False

        # --- Constraint 4: Per-layer significance delta ---
        if layer.significance_delta > c.MAX_DELTA_PER_LAYER:
            logger.warning(
                "Rejected layer for %s: significance_delta %.3f exceeds "
                "MAX_DELTA_PER_LAYER %.2f",
                message_id, layer.significance_delta, c.MAX_DELTA_PER_LAYER,
            )
            return False

        # --- Load existing layers for total drift and cooldown checks ---
        cursor = self.conn.execute(
            "SELECT valence_delta, arousal_delta, significance_delta, timestamp "
            "FROM reconsolidation_layers "
            "WHERE message_id = ? ORDER BY timestamp ASC",
            (message_id,),
        )
        existing_rows = cursor.fetchall()

        # --- Constraint 5: Total valence drift ---
        total_valence_drift = sum(r["valence_delta"] for r in existing_rows)
        proposed_total_valence = total_valence_drift + layer.valence_delta
        if abs(proposed_total_valence) > c.MAX_TOTAL_DRIFT:
            logger.warning(
                "Rejected layer for %s: total valence drift %.3f would "
                "exceed MAX_TOTAL_DRIFT %.2f",
                message_id, proposed_total_valence, c.MAX_TOTAL_DRIFT,
            )
            return False

        # --- Constraint 6: Total arousal drift ---
        total_arousal_drift = sum(r["arousal_delta"] for r in existing_rows)
        proposed_total_arousal = total_arousal_drift + layer.arousal_delta
        if abs(proposed_total_arousal) > c.MAX_TOTAL_DRIFT:
            logger.warning(
                "Rejected layer for %s: total arousal drift %.3f would "
                "exceed MAX_TOTAL_DRIFT %.2f",
                message_id, proposed_total_arousal, c.MAX_TOTAL_DRIFT,
            )
            return False

        # --- Constraint 7: Cooldown ---
        if existing_rows:
            last_timestamp_str = existing_rows[-1]["timestamp"]
            last_timestamp = datetime.fromisoformat(last_timestamp_str)
            # Ensure timezone-aware comparison
            if last_timestamp.tzinfo is None:
                last_timestamp = last_timestamp.replace(tzinfo=timezone.utc)
            cooldown_deadline = last_timestamp + timedelta(
                hours=c.COOLDOWN_HOURS
            )
            now = datetime.now(timezone.utc)
            if now < cooldown_deadline:
                remaining_hours = (
                    cooldown_deadline - now
                ).total_seconds() / 3600
                logger.warning(
                    "Rejected layer for %s: cooldown active. "
                    "%.1f hours remaining (minimum %.1f hours between layers)",
                    message_id, remaining_hours, c.COOLDOWN_HOURS,
                )
                return False

        # --- All constraints passed: insert the layer ---
        esv_json = _serialize_emotional_state(
            layer.user_emotional_state_at_recall
        )
        self.conn.execute(
            """
            INSERT INTO reconsolidation_layers (
                id, message_id, timestamp, recall_session_id,
                user_emotional_state_json, conversation_topic_at_recall,
                reaction_type, reaction_detail,
                valence_delta, arousal_delta, significance_delta,
                narrative
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                layer.id,
                message_id,
                layer.timestamp.isoformat(),
                layer.recall_session_id,
                esv_json,
                layer.conversation_topic_at_recall,
                layer.reaction_type,
                layer.reaction_detail,
                layer.valence_delta,
                layer.arousal_delta,
                layer.significance_delta,
                layer.narrative,
            ),
        )
        self.conn.commit()
        logger.info(
            "Added reconsolidation layer %s to palimpsest %s "
            "(valence_delta=%.3f, arousal_delta=%.3f, sig_delta=%.3f)",
            layer.id, message_id,
            layer.valence_delta, layer.arousal_delta,
            layer.significance_delta,
        )
        return True
```

**What this does:**
1. Checks all 7 constraints in order.  If any fails, logs a warning and returns False immediately.
2. To check total drift and cooldown, it loads all existing layers for this message_id from the database.
3. If all constraints pass, it serializes the layer's emotional state to JSON and inserts the row.
4. Returns True to indicate the layer was accepted.

---

### Step 2.5: Add get_palimpsest() method

Add the following method to the `PalimpsestManager` class.

- [ ] Add get_palimpsest() to PalimpsestManager

**Append inside the PalimpsestManager class:**

```python
    def get_palimpsest(
        self, message_id: str, archive: MessageRecord
    ) -> Optional[MemoryPalimpsest]:
        """Load a palimpsest from the database.

        This method requires the caller to provide the archive MessageRecord
        because the palimpsest table only stores the message_id reference,
        not the full message content.  The caller should retrieve the
        MessageRecord from the Chronicle first.

        Parameters
        ----------
        message_id : str
            The message_id of the palimpsest to load.
        archive : MessageRecord
            The original MessageRecord (the immutable archive).
            Must have ``archive.id == message_id``.

        Returns
        -------
        MemoryPalimpsest | None
            The reconstituted palimpsest with all its layers, or None if
            no palimpsest exists for this message_id.
        """
        # Check that the palimpsest exists
        cursor = self.conn.execute(
            "SELECT message_id FROM palimpsests WHERE message_id = ?",
            (message_id,),
        )
        if cursor.fetchone() is None:
            return None

        # Load all layers ordered by timestamp ascending
        cursor = self.conn.execute(
            "SELECT * FROM reconsolidation_layers "
            "WHERE message_id = ? ORDER BY timestamp ASC",
            (message_id,),
        )
        rows = cursor.fetchall()

        layers: list[ReconsolidationLayer] = []
        for row in rows:
            esv = _deserialize_emotional_state(
                row["user_emotional_state_json"]
            )
            layer = ReconsolidationLayer(
                id=row["id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                recall_session_id=row["recall_session_id"],
                user_emotional_state_at_recall=esv,
                conversation_topic_at_recall=row[
                    "conversation_topic_at_recall"
                ],
                reaction_type=row["reaction_type"],
                reaction_detail=row["reaction_detail"],
                valence_delta=row["valence_delta"],
                arousal_delta=row["arousal_delta"],
                significance_delta=row["significance_delta"],
                narrative=row["narrative"],
            )
            layers.append(layer)

        return MemoryPalimpsest(
            archive=archive,
            layers=layers,
            constraints=self.constraints,
        )
```

**What this does:** Queries the `palimpsests` table to check existence, then queries `reconsolidation_layers` for all layers in timestamp order.  Deserializes each layer's emotional state from JSON and reconstructs the full `MemoryPalimpsest`.

---

### Step 2.6: Add get_current_reading() method

Add the following method to the `PalimpsestManager` class.

- [ ] Add get_current_reading() to PalimpsestManager

**Append inside the PalimpsestManager class:**

```python
    def get_current_reading(
        self, message_id: str, archive: MessageRecord
    ) -> Optional[EmotionalStateVector]:
        """Get the current emotional reading of a palimpsest.

        Returns the archive's emotional state with all reconsolidation
        layers applied.  This is how the memory "feels" right now.

        Parameters
        ----------
        message_id : str
            The message_id of the palimpsest.
        archive : MessageRecord
            The original MessageRecord.

        Returns
        -------
        EmotionalStateVector | None
            The current emotional reading, or None if no palimpsest
            exists for this message_id.
        """
        palimpsest = self.get_palimpsest(message_id, archive)
        if palimpsest is None:
            return None
        return palimpsest.current_reading()
```

---

### Step 2.7: Add get_reading_at() method

Add the following method to the `PalimpsestManager` class.

- [ ] Add get_reading_at() to PalimpsestManager

**Append inside the PalimpsestManager class:**

```python
    def get_reading_at(
        self,
        message_id: str,
        archive: MessageRecord,
        point_in_time: datetime,
    ) -> Optional[EmotionalStateVector]:
        """Get the emotional reading of a palimpsest at a specific point in time.

        Only layers with timestamps <= ``point_in_time`` are applied.
        This lets you see how the memory felt at any historical moment.

        Parameters
        ----------
        message_id : str
            The message_id of the palimpsest.
        archive : MessageRecord
            The original MessageRecord.
        point_in_time : datetime
            Only layers with ``timestamp <= point_in_time`` are applied.

        Returns
        -------
        EmotionalStateVector | None
            The emotional reading at the specified time, or None if
            no palimpsest exists for this message_id.
        """
        palimpsest = self.get_palimpsest(message_id, archive)
        if palimpsest is None:
            return None
        return palimpsest.reading_at(point_in_time)
```

---

### Step 2.8: Add get_evolution_summary() method

Add the following method to the `PalimpsestManager` class.

- [ ] Add get_evolution_summary() to PalimpsestManager

**Append inside the PalimpsestManager class:**

```python
    def get_evolution_summary(
        self, message_id: str, archive: MessageRecord
    ) -> Optional[str]:
        """Get a human-readable summary of how a memory has evolved.

        Returns a string describing the number of reconsolidation events,
        the direction of emotional drift, and the most recent reaction type.

        Parameters
        ----------
        message_id : str
            The message_id of the palimpsest.
        archive : MessageRecord
            The original MessageRecord.

        Returns
        -------
        str | None
            The evolution summary, or None if no palimpsest exists
            for this message_id.
        """
        palimpsest = self.get_palimpsest(message_id, archive)
        if palimpsest is None:
            return None
        return palimpsest.evolution_summary()
```

**Complete file after all Phase 2 steps:** The file `gwen/memory/palimpsest.py` should contain the module docstring, imports, schema constants, `init_palimpsest_tables()`, two serialization helpers, and the `PalimpsestManager` class with 7 methods (`__init__`, `create_palimpsest`, `add_layer`, `get_palimpsest`, `get_current_reading`, `get_reading_at`, `get_evolution_summary`) -- approximately 350 lines total.

---

## Phase 3: Tests

### Step 3.1: Write tests/test_palimpsest.py

Create the file `tests/test_palimpsest.py` with the following exact content:

- [ ] Write tests/test_palimpsest.py

**File: `tests/test_palimpsest.py`** (complete content)

```python
"""Tests for gwen.memory.palimpsest — the Memory Reconsolidation system.

Run with:
    pytest tests/test_palimpsest.py -v
"""

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from gwen.memory.palimpsest import PalimpsestManager, init_palimpsest_tables
from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.messages import MessageRecord
from gwen.models.reconsolidation import (
    MemoryPalimpsest,
    ReconsolidationConstraints,
    ReconsolidationLayer,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to a temporary SQLite database file."""
    db_path = tmp_path / "test_palimpsest.db"
    # Pre-create the messages table so foreign keys work
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=OFF;")  # Disable FK for test setup
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            timestamp TEXT,
            sender TEXT,
            content TEXT,
            valence REAL, arousal REAL, dominance REAL,
            relational_significance REAL, vulnerability_level REAL,
            storage_strength REAL, is_flashbulb INTEGER,
            compass_direction TEXT, compass_skill_used TEXT,
            semantic_embedding_id TEXT, emotional_embedding_id TEXT,
            tme_json TEXT
        )
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def manager(tmp_db: Path) -> PalimpsestManager:
    """Return a PalimpsestManager backed by a temporary database."""
    return PalimpsestManager(tmp_db)


def _make_esv(
    valence: float = 0.5,
    arousal: float = 0.5,
    dominance: float = 0.5,
    relational_significance: float = 0.5,
    vulnerability_level: float = 0.5,
) -> EmotionalStateVector:
    """Create an EmotionalStateVector with sensible defaults."""
    return EmotionalStateVector(
        valence=valence,
        arousal=arousal,
        dominance=dominance,
        relational_significance=relational_significance,
        vulnerability_level=vulnerability_level,
        compass_direction=CompassDirection.NONE,
        compass_confidence=0.0,
    )


def _make_message(
    msg_id: str = "msg-001",
    valence: float = 0.5,
    arousal: float = 0.5,
    relational_significance: float = 0.5,
) -> MessageRecord:
    """Create a minimal valid MessageRecord for palimpsest tests.

    Note: tme is set to None because these tests do not exercise
    the temporal metadata system.
    """
    esv = _make_esv(
        valence=valence,
        arousal=arousal,
        relational_significance=relational_significance,
    )
    return MessageRecord(
        id=msg_id,
        session_id="session-001",
        timestamp=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        sender="user",
        content="I remember that day vividly.",
        tme=None,
        emotional_state=esv,
        storage_strength=esv.storage_strength,
        is_flashbulb=esv.is_flashbulb,
        compass_direction=CompassDirection.NONE,
        compass_skill_used=None,
    )


def _make_layer(
    layer_id: str = "layer-001",
    valence_delta: float = 0.0,
    arousal_delta: float = 0.0,
    significance_delta: float = 0.0,
    timestamp: datetime | None = None,
) -> ReconsolidationLayer:
    """Create a ReconsolidationLayer with sensible defaults."""
    return ReconsolidationLayer(
        id=layer_id,
        timestamp=timestamp or datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc),
        recall_session_id="recall-session-001",
        user_emotional_state_at_recall=_make_esv(),
        conversation_topic_at_recall="reminiscing about childhood",
        reaction_type="warmth",
        reaction_detail="User smiled when recalling this memory.",
        valence_delta=valence_delta,
        arousal_delta=arousal_delta,
        significance_delta=significance_delta,
        narrative="The user seems to have a warmer feeling about this now.",
    )


def _insert_dummy_message(db_path: Path, msg_id: str = "msg-001") -> None:
    """Insert a dummy row into the messages table so FK constraints pass.

    This is needed because palimpsests.message_id references messages.id.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO messages (id, session_id, timestamp, sender, content) "
        "VALUES (?, ?, ?, ?, ?)",
        (msg_id, "session-001", "2026-01-15T10:00:00+00:00", "user", "Test"),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tests: Create palimpsest
# ---------------------------------------------------------------------------

class TestCreatePalimpsest:
    """Tests for PalimpsestManager.create_palimpsest."""

    def test_create_palimpsest_stores_archive(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """Creating a palimpsest should insert a row into the palimpsests table."""
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message()
        palimpsest = manager.create_palimpsest(message)

        # Verify the returned object
        assert palimpsest.archive.id == "msg-001"
        assert palimpsest.layers == []
        assert palimpsest.archive.content == "I remember that day vividly."

        # Verify the database row
        cursor = manager.conn.execute(
            "SELECT * FROM palimpsests WHERE message_id = ?", ("msg-001",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["message_id"] == "msg-001"

    def test_create_palimpsest_archive_values_preserved(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """The archive's emotional state should be exactly as provided."""
        _insert_dummy_message(tmp_db, "msg-002")
        message = _make_message(
            msg_id="msg-002", valence=0.7, arousal=0.3,
            relational_significance=0.8
        )
        palimpsest = manager.create_palimpsest(message)

        assert palimpsest.archive.emotional_state.valence == 0.7
        assert palimpsest.archive.emotional_state.arousal == 0.3
        assert palimpsest.archive.emotional_state.relational_significance == 0.8


# ---------------------------------------------------------------------------
# Tests: Add layer (valid)
# ---------------------------------------------------------------------------

class TestAddLayerValid:
    """Tests for PalimpsestManager.add_layer with valid inputs."""

    def test_add_valid_layer(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """Adding a valid layer should return True and persist the layer."""
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message()
        manager.create_palimpsest(message)

        layer = _make_layer(
            valence_delta=0.05,
            arousal_delta=-0.03,
            significance_delta=0.02,
        )
        result = manager.add_layer("msg-001", layer)
        assert result is True

        # Verify the layer was persisted
        cursor = manager.conn.execute(
            "SELECT * FROM reconsolidation_layers WHERE message_id = ?",
            ("msg-001",),
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0]["valence_delta"] == pytest.approx(0.05)
        assert rows[0]["arousal_delta"] == pytest.approx(-0.03)
        assert rows[0]["significance_delta"] == pytest.approx(0.02)

    def test_add_layer_changes_current_reading(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """After adding a layer, current_reading should reflect the deltas."""
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message(valence=0.5, arousal=0.5, relational_significance=0.5)
        manager.create_palimpsest(message)

        layer = _make_layer(
            valence_delta=0.05,
            arousal_delta=-0.03,
            significance_delta=0.02,
        )
        manager.add_layer("msg-001", layer)

        reading = manager.get_current_reading("msg-001", message)
        assert reading is not None
        assert abs(reading.valence - 0.55) < 1e-9
        assert abs(reading.arousal - 0.47) < 1e-9
        assert abs(reading.relational_significance - 0.52) < 1e-9


# ---------------------------------------------------------------------------
# Tests: Add layer (rejected — constraint violations)
# ---------------------------------------------------------------------------

class TestAddLayerRejected:
    """Tests for PalimpsestManager.add_layer with constraint violations."""

    def test_exceed_per_layer_valence_delta(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """A layer with valence_delta > MAX_DELTA_PER_LAYER should be rejected."""
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message()
        manager.create_palimpsest(message)

        layer = _make_layer(valence_delta=0.15)  # Exceeds 0.10
        result = manager.add_layer("msg-001", layer)
        assert result is False

    def test_exceed_per_layer_arousal_delta(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """A layer with arousal_delta > MAX_DELTA_PER_LAYER should be rejected."""
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message()
        manager.create_palimpsest(message)

        layer = _make_layer(arousal_delta=-0.15)  # Exceeds 0.10 in abs
        result = manager.add_layer("msg-001", layer)
        assert result is False

    def test_significance_decrease_rejected(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """A layer with negative significance_delta should be rejected."""
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message()
        manager.create_palimpsest(message)

        layer = _make_layer(significance_delta=-0.05)
        result = manager.add_layer("msg-001", layer)
        assert result is False

    def test_exceed_total_drift(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """Adding layers that would push total drift past MAX_TOTAL_DRIFT should be rejected.

        Strategy: Add 5 layers of +0.10 each (total +0.50 = at the limit).
        Then try a 6th layer of +0.10 (total would be +0.60) -- should be rejected.
        Each layer needs a unique timestamp spaced > 24 hours apart to pass cooldown.
        """
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message()
        manager.create_palimpsest(message)

        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Add 5 layers, each spaced 48 hours apart to pass cooldown
        for i in range(5):
            layer_time = base_time + timedelta(hours=48 * i)
            layer = _make_layer(
                layer_id=f"layer-{i:03d}",
                valence_delta=0.10,
                timestamp=layer_time,
            )
            # Patch datetime.now to return a time after the cooldown
            fake_now = layer_time + timedelta(hours=25)
            with patch(
                "gwen.memory.palimpsest.datetime"
            ) as mock_dt:
                mock_dt.now.return_value = fake_now
                mock_dt.fromisoformat = datetime.fromisoformat
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                result = manager.add_layer("msg-001", layer)
            assert result is True, f"Layer {i} should have been accepted"

        # 6th layer should be rejected (total drift would be 0.60)
        layer_time_6 = base_time + timedelta(hours=48 * 5)
        layer_6 = _make_layer(
            layer_id="layer-005",
            valence_delta=0.10,
            timestamp=layer_time_6,
        )
        fake_now_6 = layer_time_6 + timedelta(hours=25)
        with patch("gwen.memory.palimpsest.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now_6
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = manager.add_layer("msg-001", layer_6)
        assert result is False, "6th layer should be rejected (total drift 0.60 > 0.50)"

    def test_cooldown_enforcement(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """Adding a second layer within COOLDOWN_HOURS should be rejected.

        Strategy: Add a layer, then immediately try to add another.
        The second should be rejected because < 24 hours have passed.
        """
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message()
        manager.create_palimpsest(message)

        t1 = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
        layer_1 = _make_layer(
            layer_id="layer-001",
            valence_delta=0.05,
            timestamp=t1,
        )
        # First layer: patch "now" to be 25 hours after some reference
        # (no existing layers, so cooldown does not apply)
        result_1 = manager.add_layer("msg-001", layer_1)
        assert result_1 is True

        # Second layer: "now" is only 1 hour after layer_1
        t2 = t1 + timedelta(hours=1)
        layer_2 = _make_layer(
            layer_id="layer-002",
            valence_delta=0.03,
            timestamp=t2,
        )
        fake_now = t1 + timedelta(hours=1)
        with patch("gwen.memory.palimpsest.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result_2 = manager.add_layer("msg-001", layer_2)
        assert result_2 is False, "Second layer should be rejected (cooldown active)"


# ---------------------------------------------------------------------------
# Tests: Reading at point in time
# ---------------------------------------------------------------------------

class TestReadingAt:
    """Tests for PalimpsestManager.get_reading_at."""

    def test_reading_at_returns_correct_state(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """reading_at should only apply layers up to the given timestamp.

        Strategy: Create 3 layers at t1, t2, t3.
        Query at (t1 + 12h) -- should only include layer 1.
        Query at (t2 + 12h) -- should include layers 1 and 2.
        Query at (t3 + 12h) -- should include all 3 layers.
        """
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message(valence=0.5)
        manager.create_palimpsest(message)

        t1 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2025, 8, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Insert layers directly into the database (bypassing cooldown
        # enforcement for this test, since we want to test reading_at logic
        # specifically).
        for i, (t, delta) in enumerate([
            (t1, 0.05), (t2, 0.05), (t3, 0.05)
        ]):
            manager.conn.execute(
                """
                INSERT INTO reconsolidation_layers (
                    id, message_id, timestamp, recall_session_id,
                    user_emotional_state_json, conversation_topic_at_recall,
                    reaction_type, reaction_detail,
                    valence_delta, arousal_delta, significance_delta,
                    narrative
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"layer-{i:03d}", "msg-001", t.isoformat(),
                    "recall-sess", '{"valence":0.5,"arousal":0.5,"dominance":0.5,'
                    '"relational_significance":0.5,"vulnerability_level":0.5,'
                    '"compass_direction":"none","compass_confidence":0.0}',
                    "test topic", "warmth", "test", delta, 0.0, 0.0,
                    "test narrative",
                ),
            )
        manager.conn.commit()

        # At t1 + 12h: only layer 0
        reading_1 = manager.get_reading_at(
            "msg-001", message,
            t1 + timedelta(hours=12),
        )
        assert reading_1 is not None
        assert abs(reading_1.valence - 0.55) < 1e-9

        # At t2 + 12h: layers 0 and 1
        reading_2 = manager.get_reading_at(
            "msg-001", message,
            t2 + timedelta(hours=12),
        )
        assert reading_2 is not None
        assert abs(reading_2.valence - 0.60) < 1e-9

        # At t3 + 12h: all 3 layers
        reading_3 = manager.get_reading_at(
            "msg-001", message,
            t3 + timedelta(hours=12),
        )
        assert reading_3 is not None
        assert abs(reading_3.valence - 0.65) < 1e-9


# ---------------------------------------------------------------------------
# Tests: Evolution summary
# ---------------------------------------------------------------------------

class TestEvolutionSummary:
    """Tests for PalimpsestManager.get_evolution_summary."""

    def test_no_layers_summary(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """With no layers, summary should say 'No reconsolidation'."""
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message()
        manager.create_palimpsest(message)

        summary = manager.get_evolution_summary("msg-001", message)
        assert summary is not None
        assert "No reconsolidation" in summary

    def test_summary_with_positive_drift(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """After adding a positive-valence layer, summary should say 'more positive'."""
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message(valence=0.5)
        manager.create_palimpsest(message)

        layer = _make_layer(valence_delta=0.05)
        manager.add_layer("msg-001", layer)

        summary = manager.get_evolution_summary("msg-001", message)
        assert summary is not None
        assert "1 time(s)" in summary
        assert "more positive" in summary

    def test_summary_with_negative_drift(
        self, manager: PalimpsestManager, tmp_db: Path
    ) -> None:
        """After adding a negative-valence layer, summary should say 'more negative'."""
        _insert_dummy_message(tmp_db, "msg-001")
        message = _make_message(valence=0.5)
        manager.create_palimpsest(message)

        layer = _make_layer(valence_delta=-0.05)
        manager.add_layer("msg-001", layer)

        summary = manager.get_evolution_summary("msg-001", message)
        assert summary is not None
        assert "more negative" in summary

    def test_nonexistent_palimpsest_returns_none(
        self, manager: PalimpsestManager
    ) -> None:
        """Querying a non-existent palimpsest should return None."""
        message = _make_message(msg_id="nonexistent")
        summary = manager.get_evolution_summary("nonexistent", message)
        assert summary is None
```

---

### Step 3.2: Run the tests

Execute the following command from the project root:

- [ ] Run `pytest tests/test_palimpsest.py -v` and confirm all tests pass

```bash
pytest tests/test_palimpsest.py -v
```

**Expected output:** All tests pass. You should see:

```
tests/test_palimpsest.py::TestCreatePalimpsest::test_create_palimpsest_stores_archive PASSED
tests/test_palimpsest.py::TestCreatePalimpsest::test_create_palimpsest_archive_values_preserved PASSED
tests/test_palimpsest.py::TestAddLayerValid::test_add_valid_layer PASSED
tests/test_palimpsest.py::TestAddLayerValid::test_add_layer_changes_current_reading PASSED
tests/test_palimpsest.py::TestAddLayerRejected::test_exceed_per_layer_valence_delta PASSED
tests/test_palimpsest.py::TestAddLayerRejected::test_exceed_per_layer_arousal_delta PASSED
tests/test_palimpsest.py::TestAddLayerRejected::test_significance_decrease_rejected PASSED
tests/test_palimpsest.py::TestAddLayerRejected::test_exceed_total_drift PASSED
tests/test_palimpsest.py::TestAddLayerRejected::test_cooldown_enforcement PASSED
tests/test_palimpsest.py::TestReadingAt::test_reading_at_returns_correct_state PASSED
tests/test_palimpsest.py::TestEvolutionSummary::test_no_layers_summary PASSED
tests/test_palimpsest.py::TestEvolutionSummary::test_summary_with_positive_drift PASSED
tests/test_palimpsest.py::TestEvolutionSummary::test_summary_with_negative_drift PASSED
tests/test_palimpsest.py::TestEvolutionSummary::test_nonexistent_palimpsest_returns_none PASSED

14 passed in X.XXs
```

**If any test fails:**
1. **ImportError for gwen.models**: Tracks 002 (data-models) must be complete.  The models `ReconsolidationLayer`, `ReconsolidationConstraints`, `MemoryPalimpsest`, `MessageRecord`, and `EmotionalStateVector` must exist in `gwen/models/`.
2. **sqlite3.OperationalError about foreign keys**: Make sure the test fixture creates the `messages` table before the palimpsest tables.  The `_insert_dummy_message()` helper must be called before `create_palimpsest()`.
3. **Cooldown test failures**: The cooldown test patches `datetime.now()`.  If you see `TypeError: cannot pickle 'datetime' object`, check that the mock is set up correctly.
4. **Total drift test failures**: Each layer adds +0.10 valence.  After 5 layers the total is +0.50 (exactly at limit).  The 6th layer would make +0.60, which exceeds MAX_TOTAL_DRIFT=0.50.

---

## Checklist (update after each step)

- [ ] Phase 1 complete: gwen/memory/palimpsest.py with schema constants and init_palimpsest_tables
- [ ] Phase 2 complete: PalimpsestManager with all 7 methods
- [ ] Phase 3 complete: tests/test_palimpsest.py passes with all 14 tests green
