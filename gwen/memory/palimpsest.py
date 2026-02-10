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
