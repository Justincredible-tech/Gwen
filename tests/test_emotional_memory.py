"""Tests for gwen.memory.pulse and gwen.memory.bond.

Run with:
    pytest tests/test_emotional_memory.py -v
"""

from datetime import datetime
from pathlib import Path

import pytest

from gwen.memory.bond import (
    BondManager,
)
from gwen.memory.pulse import (
    DEFAULT_BASELINE_VALUES,
    PulseManager,
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

@pytest.fixture
def pulse_path(tmp_path: Path) -> Path:
    """Return a path to a temporary Pulse JSON file."""
    return tmp_path / "test_pulse.json"


@pytest.fixture
def bond_path(tmp_path: Path) -> Path:
    """Return a path to a temporary Bond JSON file."""
    return tmp_path / "test_bond.json"


@pytest.fixture
def pulse(pulse_path: Path) -> PulseManager:
    """Return a PulseManager backed by a temporary file."""
    return PulseManager(pulse_path)


@pytest.fixture
def bond(bond_path: Path) -> BondManager:
    """Return a BondManager backed by a temporary file."""
    return BondManager(bond_path)


def _make_esv(**overrides) -> EmotionalStateVector:
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
    content: str = "Hello",
    sender: str = "user",
    valence: float = 0.6,
    arousal: float = 0.4,
    vulnerability: float = 0.2,
    rel_sig: float = 0.3,
    **overrides,
) -> MessageRecord:
    """Create a MessageRecord with sensible defaults."""
    import uuid
    defaults = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "timestamp": datetime(2026, 2, 9, 14, 30, 0),
        "sender": sender,
        "content": content,
        "tme": None,
        "emotional_state": _make_esv(
            valence=valence,
            arousal=arousal,
            vulnerability_level=vulnerability,
            relational_significance=rel_sig,
        ),
        "storage_strength": 0.34,
        "is_flashbulb": False,
        "compass_direction": CompassDirection.NONE,
        "compass_skill_used": None,
        "semantic_embedding_id": None,
        "emotional_embedding_id": None,
    }
    defaults.update(overrides)
    return MessageRecord(**defaults)


def _make_session(
    session_id: str = "sess-001",
    start_hour: int = 14,
    gwen_initiated: bool = False,
    compass_activations: dict | None = None,
    **overrides,
) -> SessionRecord:
    """Create a SessionRecord with sensible defaults."""
    defaults = {
        "id": session_id,
        "start_time": datetime(2026, 2, 9, start_hour, 0, 0),
        "end_time": datetime(2026, 2, 9, start_hour, 45, 0),
        "duration_sec": 2700,
        "session_type": SessionType.CHAT,
        "end_mode": SessionEndMode.NATURAL,
        "opening_emotional_state": None,
        "peak_emotional_state": None,
        "closing_emotional_state": None,
        "emotional_arc_embedding_id": None,
        "avg_emotional_intensity": 0.5,
        "avg_relational_significance": 0.3,
        "subjective_duration_weight": 1.0,
        "message_count": 10,
        "user_message_count": 5,
        "companion_message_count": 5,
        "avg_response_latency_sec": 1.0,
        "compass_activations": compass_activations or {},
        "topics": ["general"],
        "relational_field_delta": {},
        "gwen_initiated": gwen_initiated,
    }
    defaults.update(overrides)
    return SessionRecord(**defaults)


# ---------------------------------------------------------------------------
# Tests: PulseManager — Initialization
# ---------------------------------------------------------------------------

class TestPulseInit:
    """Tests for PulseManager initialization."""

    def test_default_baseline_values(self, pulse: PulseManager) -> None:
        """Default baseline should have neutral values."""
        b = pulse.overall_baseline
        assert b.valence == pytest.approx(0.5)
        assert b.arousal == pytest.approx(0.3)
        assert b.dominance == pytest.approx(0.5)

    def test_initial_data_points_count_zero(
        self, pulse: PulseManager
    ) -> None:
        """Data points count should start at zero."""
        assert pulse.data_points_count == 0

    def test_initial_day_baselines_empty(
        self, pulse: PulseManager
    ) -> None:
        """Day-of-week baselines should start empty."""
        assert pulse.day_baselines == {}

    def test_initial_time_baselines_empty(
        self, pulse: PulseManager
    ) -> None:
        """Time-phase baselines should start empty."""
        assert pulse.time_baselines == {}


# ---------------------------------------------------------------------------
# Tests: PulseManager — Rolling Average
# ---------------------------------------------------------------------------

class TestRollingAverage:
    """Tests for the rolling average computation."""

    def test_first_update_sets_to_new_value(self) -> None:
        """With count=0, rolling average should equal the new value."""
        current = _make_esv(valence=0.5, arousal=0.3)
        new = _make_esv(valence=0.8, arousal=0.6)
        result = PulseManager._rolling_average(current, new, count=0)
        assert result.valence == pytest.approx(0.8)
        assert result.arousal == pytest.approx(0.6)

    def test_second_update_averages(self) -> None:
        """With count=1, rolling average should be midpoint."""
        current = _make_esv(valence=0.8, arousal=0.6)
        new = _make_esv(valence=0.4, arousal=0.2)
        result = PulseManager._rolling_average(current, new, count=1)
        assert result.valence == pytest.approx(0.6)
        assert result.arousal == pytest.approx(0.4)

    def test_many_updates_converge(self) -> None:
        """After many updates with the same value, baseline converges."""
        baseline = _make_esv(valence=0.5)
        target = _make_esv(valence=0.9)
        for i in range(100):
            baseline = PulseManager._rolling_average(baseline, target, count=i)
        # After 100 updates of 0.9, should be very close to 0.9
        assert baseline.valence == pytest.approx(0.9, abs=0.01)


# ---------------------------------------------------------------------------
# Tests: PulseManager — Update from Session
# ---------------------------------------------------------------------------

class TestPulseUpdate:
    """Tests for update_from_session."""

    def test_update_changes_overall_baseline(
        self, pulse: PulseManager
    ) -> None:
        """Updating with a session should change the overall baseline."""
        session = _make_session(start_hour=14)
        messages = [
            _make_message(valence=0.8, arousal=0.5),
            _make_message(valence=0.7, arousal=0.4),
        ]
        pulse.update_from_session(session, messages)

        assert pulse.data_points_count == 1
        # Baseline should have moved toward the session average (0.75, 0.45)
        assert pulse.overall_baseline.valence == pytest.approx(0.75)
        assert pulse.overall_baseline.arousal == pytest.approx(0.45)

    def test_update_creates_day_baseline(
        self, pulse: PulseManager
    ) -> None:
        """Updating should create a day-of-week baseline entry."""
        # February 9, 2026 is a Monday
        session = _make_session(start_hour=14)
        messages = [_make_message(valence=0.8)]
        pulse.update_from_session(session, messages)

        assert "monday" in pulse.day_baselines
        assert pulse.day_baselines["monday"].valence == pytest.approx(0.8)

    def test_update_creates_time_phase_baseline(
        self, pulse: PulseManager
    ) -> None:
        """Updating should create a time-phase baseline entry."""
        session = _make_session(start_hour=2)  # 2 AM = deep_night
        messages = [_make_message(valence=0.3, arousal=0.7)]
        pulse.update_from_session(session, messages)

        assert "deep_night" in pulse.time_baselines

    def test_empty_messages_is_noop(self, pulse: PulseManager) -> None:
        """Updating with no messages should not change baselines."""
        session = _make_session()
        pulse.update_from_session(session, [])
        assert pulse.data_points_count == 0

    def test_multiple_updates_accumulate(
        self, pulse: PulseManager
    ) -> None:
        """Multiple session updates should accumulate data points."""
        for i in range(5):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message(valence=0.6)]
            pulse.update_from_session(session, messages)

        assert pulse.data_points_count == 5


# ---------------------------------------------------------------------------
# Tests: PulseManager — Baseline Retrieval
# ---------------------------------------------------------------------------

class TestBaselineRetrieval:
    """Tests for get_baseline and get_deviation."""

    def test_get_baseline_no_specifics_returns_overall(
        self, pulse: PulseManager
    ) -> None:
        """get_baseline() with no args should return overall baseline."""
        baseline = pulse.get_baseline()
        assert baseline.valence == pytest.approx(
            DEFAULT_BASELINE_VALUES["valence"]
        )

    def test_get_baseline_with_day(self, pulse: PulseManager) -> None:
        """get_baseline(day='monday') should return Monday baseline if it exists."""
        session = _make_session(start_hour=14)
        messages = [_make_message(valence=0.8)]
        pulse.update_from_session(session, messages)

        baseline = pulse.get_baseline(day="monday")
        assert baseline.valence == pytest.approx(0.8)

    def test_get_baseline_falls_back_to_overall(
        self, pulse: PulseManager
    ) -> None:
        """get_baseline with unknown day should fall back to overall."""
        baseline = pulse.get_baseline(day="wednesday")
        assert baseline.valence == pytest.approx(
            DEFAULT_BASELINE_VALUES["valence"]
        )

    def test_get_deviation_positive(self, pulse: PulseManager) -> None:
        """Deviation should be positive when current > baseline."""
        current = _make_esv(valence=0.8)
        deviation = pulse.get_deviation(current)
        assert deviation["valence"] > 0

    def test_get_deviation_negative(self, pulse: PulseManager) -> None:
        """Deviation should be negative when current < baseline."""
        current = _make_esv(valence=0.1)
        deviation = pulse.get_deviation(current)
        assert deviation["valence"] < 0

    def test_get_deviation_zero_at_baseline(
        self, pulse: PulseManager
    ) -> None:
        """Deviation should be zero when current equals baseline."""
        current = _make_esv(**DEFAULT_BASELINE_VALUES)
        deviation = pulse.get_deviation(current)
        assert deviation["valence"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: PulseManager — Persistence
# ---------------------------------------------------------------------------

class TestPulsePersistence:
    """Tests for Pulse save/load round-trip."""

    def test_save_and_load(self, pulse_path: Path) -> None:
        """Saving and loading should preserve baseline data."""
        pm1 = PulseManager(pulse_path)
        session = _make_session()
        messages = [_make_message(valence=0.8, arousal=0.6)]
        pm1.update_from_session(session, messages)

        pm2 = PulseManager(pulse_path)
        assert pm2.data_points_count == 1
        assert pm2.overall_baseline.valence == pytest.approx(0.8)
        assert pm2.overall_baseline.arousal == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Tests: BondManager — Initialization
# ---------------------------------------------------------------------------

class TestBondInit:
    """Tests for BondManager initialization."""

    def test_default_field_values(self, bond: BondManager) -> None:
        """Default field should have new-relationship values."""
        f = bond.current_field
        assert f.warmth == pytest.approx(0.3)
        assert f.trust == pytest.approx(0.2)
        assert f.depth == pytest.approx(0.1)
        assert f.stability == pytest.approx(0.5)
        assert f.reciprocity == pytest.approx(0.3)
        assert f.growth == pytest.approx(0.3)

    def test_initial_session_count_zero(self, bond: BondManager) -> None:
        """Session count should start at zero."""
        assert bond.session_count == 0

    def test_initial_history_empty(self, bond: BondManager) -> None:
        """Field history should start empty."""
        assert bond.field_history == []


# ---------------------------------------------------------------------------
# Tests: BondManager — Field Updates
# ---------------------------------------------------------------------------

class TestBondUpdates:
    """Tests for relational field updates from sessions."""

    def test_positive_session_increases_warmth(
        self, bond: BondManager
    ) -> None:
        """A session with high valence should increase warmth."""
        initial_warmth = bond.current_field.warmth
        session = _make_session()
        messages = [
            _make_message(valence=0.9),
            _make_message(valence=0.8),
        ]
        bond.update_from_session(session, messages)
        assert bond.current_field.warmth > initial_warmth

    def test_negative_session_decreases_warmth(
        self, bond: BondManager
    ) -> None:
        """A session with low valence should decrease warmth."""
        initial_warmth = bond.current_field.warmth
        session = _make_session()
        messages = [
            _make_message(valence=0.1),
            _make_message(valence=0.2),
        ]
        bond.update_from_session(session, messages)
        assert bond.current_field.warmth < initial_warmth

    def test_trust_increases_every_session(
        self, bond: BondManager
    ) -> None:
        """Trust should increase at least slightly with every session."""
        initial_trust = bond.current_field.trust
        session = _make_session()
        messages = [_make_message()]
        bond.update_from_session(session, messages)
        assert bond.current_field.trust > initial_trust

    def test_vulnerability_increases_trust_more(
        self, bond: BondManager
    ) -> None:
        """High vulnerability sessions should increase trust more."""
        bond1 = BondManager(bond.data_path.parent / "bond1.json")
        bond2 = BondManager(bond.data_path.parent / "bond2.json")

        session = _make_session()

        # Low vulnerability session
        low_vuln_msgs = [_make_message(vulnerability=0.1)]
        bond1.update_from_session(session, low_vuln_msgs)

        # High vulnerability session
        high_vuln_msgs = [_make_message(vulnerability=0.9)]
        bond2.update_from_session(session, high_vuln_msgs)

        assert bond2.current_field.trust > bond1.current_field.trust

    def test_gwen_initiated_increases_reciprocity(
        self, bond: BondManager
    ) -> None:
        """Gwen-initiated sessions should increase reciprocity."""
        initial_recip = bond.current_field.reciprocity
        session = _make_session(gwen_initiated=True)
        messages = [_make_message()]
        bond.update_from_session(session, messages)
        assert bond.current_field.reciprocity > initial_recip

    def test_user_initiated_slightly_decreases_reciprocity(
        self, bond: BondManager
    ) -> None:
        """User-initiated sessions should slightly decrease reciprocity."""
        initial_recip = bond.current_field.reciprocity
        session = _make_session(gwen_initiated=False)
        messages = [_make_message()]
        bond.update_from_session(session, messages)
        assert bond.current_field.reciprocity < initial_recip

    def test_field_clamped_to_0_1(self, bond: BondManager) -> None:
        """All field dimensions should stay within [0.0, 1.0]."""
        # Run many very positive sessions to push warmth toward max
        for i in range(100):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message(valence=1.0)]
            bond.update_from_session(session, messages)

        f = bond.current_field
        assert 0.0 <= f.warmth <= 1.0
        assert 0.0 <= f.trust <= 1.0
        assert 0.0 <= f.depth <= 1.0
        assert 0.0 <= f.stability <= 1.0
        assert 0.0 <= f.reciprocity <= 1.0
        assert 0.0 <= f.growth <= 1.0

    def test_session_count_increments(self, bond: BondManager) -> None:
        """Session count should increment after each update."""
        session = _make_session()
        messages = [_make_message()]
        bond.update_from_session(session, messages)
        assert bond.session_count == 1

        bond.update_from_session(session, messages)
        assert bond.session_count == 2

    def test_field_history_appended(self, bond: BondManager) -> None:
        """Field history should grow after each update."""
        session = _make_session()
        messages = [_make_message()]
        bond.update_from_session(session, messages)
        assert len(bond.field_history) == 1

    def test_empty_messages_is_noop(self, bond: BondManager) -> None:
        """Updating with no messages should not change the field."""
        initial = bond.current_field.warmth
        session = _make_session()
        bond.update_from_session(session, [])
        assert bond.current_field.warmth == initial
        assert bond.session_count == 0


# ---------------------------------------------------------------------------
# Tests: BondManager — Attachment Style
# ---------------------------------------------------------------------------

class TestAttachmentStyle:
    """Tests for attachment style estimation."""

    def test_returns_none_before_20_sessions(
        self, bond: BondManager
    ) -> None:
        """Attachment style should be None before 20 sessions."""
        style, confidence = bond.estimate_attachment_style()
        assert style is None
        assert confidence == 0.0

    def test_returns_none_at_19_sessions(
        self, bond: BondManager
    ) -> None:
        """Attachment style should still be None at 19 sessions."""
        for i in range(19):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message()]
            bond.update_from_session(session, messages)

        style, confidence = bond.estimate_attachment_style()
        assert style is None
        assert confidence == 0.0

    def test_returns_style_after_20_sessions(
        self, bond: BondManager
    ) -> None:
        """Attachment style should return a style after 20 sessions."""
        for i in range(20):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message(valence=0.7)]
            bond.update_from_session(session, messages)

        style, confidence = bond.estimate_attachment_style()
        assert style is not None
        assert style in ("secure", "anxious", "avoidant", "fearful")
        assert 0.0 <= confidence <= 1.0

    def test_positive_stable_sessions_trend_secure(
        self, bond: BondManager
    ) -> None:
        """Consistently positive, stable sessions should trend toward secure."""
        for i in range(50):
            session = _make_session(session_id=f"sess-{i}")
            # Strongly positive, moderate arousal, open vulnerability
            # Needs enough sessions for warmth/trust to cross thresholds
            messages = [
                _make_message(valence=0.9, arousal=0.4, vulnerability=0.5),
                _make_message(valence=0.9, arousal=0.4, vulnerability=0.5),
            ]
            bond.update_from_session(session, messages)

        style, confidence = bond.estimate_attachment_style()
        # With consistently warm, stable, trusting sessions,
        # the most likely style is secure
        assert style == "secure"


# ---------------------------------------------------------------------------
# Tests: BondManager — Persistence
# ---------------------------------------------------------------------------

class TestBondPersistence:
    """Tests for Bond save/load round-trip."""

    def test_save_and_load_preserves_field(
        self, bond_path: Path
    ) -> None:
        """Saving and loading should preserve the current field."""
        bm1 = BondManager(bond_path)
        session = _make_session()
        messages = [_make_message(valence=0.9)]
        bm1.update_from_session(session, messages)
        initial_warmth = bm1.current_field.warmth

        bm2 = BondManager(bond_path)
        assert bm2.current_field.warmth == pytest.approx(initial_warmth)

    def test_save_and_load_preserves_history(
        self, bond_path: Path
    ) -> None:
        """Saving and loading should preserve field history."""
        bm1 = BondManager(bond_path)
        for i in range(3):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message()]
            bm1.update_from_session(session, messages)

        bm2 = BondManager(bond_path)
        assert len(bm2.field_history) == 3
        assert bm2.session_count == 3

    def test_save_and_load_preserves_session_count(
        self, bond_path: Path
    ) -> None:
        """Saving and loading should preserve the session count."""
        bm1 = BondManager(bond_path)
        for i in range(5):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message()]
            bm1.update_from_session(session, messages)

        bm2 = BondManager(bond_path)
        assert bm2.session_count == 5


# ---------------------------------------------------------------------------
# Tests: PulseManager — Hour to Time Phase
# ---------------------------------------------------------------------------

class TestHourToTimePhase:
    """Tests for the _hour_to_time_phase helper."""

    @pytest.mark.parametrize(
        "hour, expected",
        [
            (0, "deep_night"),
            (2, "deep_night"),
            (4, "deep_night"),
            (5, "early_morning"),
            (7, "early_morning"),
            (8, "morning"),
            (11, "morning"),
            (12, "afternoon"),
            (16, "afternoon"),
            (17, "evening"),
            (20, "evening"),
            (21, "night"),
            (23, "night"),
        ],
    )
    def test_hour_mapping(self, hour: int, expected: str) -> None:
        """Each hour should map to the correct time phase."""
        assert PulseManager._hour_to_time_phase(hour) == expected
