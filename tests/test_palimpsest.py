"""Tests for gwen.memory.palimpsest — the Memory Reconsolidation system.

Run with:
    pytest tests/test_palimpsest.py -v
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from gwen.memory.palimpsest import PalimpsestManager
from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.messages import MessageRecord
from gwen.models.reconsolidation import ReconsolidationLayer


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
        # First layer: no existing layers, so cooldown does not apply
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
