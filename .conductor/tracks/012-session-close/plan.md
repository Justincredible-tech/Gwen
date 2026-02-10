# Plan: Session Close & Light Consolidation

**Track:** 012-session-close
**Depends on:** 007-session-manager (SessionRecord, SessionManager must exist), 011-post-processing (post-processing pipeline must be complete so messages have emotional states)
**Produces:** gwen/consolidation/__init__.py, gwen/consolidation/light.py, tests/test_session_close.py

---

## Phase 1: Package Initialization

### Step 1.1: Create gwen/consolidation/__init__.py

Create the file `gwen/consolidation/__init__.py` with the following exact content:

```python
"""Background memory consolidation - light, standard, and deep passes."""
```

**Why:** This makes `gwen.consolidation` a Python package so that `from gwen.consolidation.light import SessionCloser` works. If this file already exists from Track 001 scaffold, verify the content matches and skip this step.

**Verification gate (manual):** Run `python -c "import gwen.consolidation; print('OK')"` and confirm it prints `OK`.

---

## Phase 2: SessionCloser Class

### Step 2.1: Create gwen/consolidation/light.py with imports and class skeleton

Create the file `gwen/consolidation/light.py` with the following exact content:

```python
"""
Light Consolidation — Session close and post-session cleanup.

Handles Phase 8 of the message lifecycle (SRS.md Section 4.8):
1. Classify session end mode
2. Compute emotional arc (opening, peak, closing)
3. Classify session type from duration
4. Compute subjective time weight
5. Compute statistics (message counts, avg latency, topics, compass activations)
6. Save complete SessionRecord to Chronicle
7. Clear Stream (working memory)
8. Evaluate if standard consolidation should trigger
"""

from datetime import datetime, timedelta
from typing import Optional

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.messages import (
    MessageRecord,
    SessionEndMode,
    SessionRecord,
    SessionType,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Session type thresholds (in seconds), from SRS.md Section 3.4
SESSION_TYPE_THRESHOLDS: list[tuple[int, SessionType]] = [
    (300, SessionType.PING),         # < 5 minutes
    (1800, SessionType.CHAT),        # 5-30 minutes
    (5400, SessionType.HANG),        # 30-90 minutes
    (10800, SessionType.DEEP_DIVE),  # 90-180 minutes
    # Anything above 10800 is MARATHON
]

# Standard consolidation trigger thresholds
STANDARD_CONSOLIDATION_SESSION_THRESHOLD = 3
STANDARD_CONSOLIDATION_HOURS_THRESHOLD = 12.0


def classify_session_type(duration_sec: int) -> SessionType:
    """Classify a session by duration using the thresholds from SRS.md Section 3.4.

    Parameters
    ----------
    duration_sec : int
        Total session duration in seconds.

    Returns
    -------
    SessionType
        One of PING, CHAT, HANG, DEEP_DIVE, or MARATHON.

    Examples
    --------
    >>> classify_session_type(120)
    <SessionType.PING: 'ping'>
    >>> classify_session_type(600)
    <SessionType.CHAT: 'chat'>
    >>> classify_session_type(3600)
    <SessionType.HANG: 'hang'>
    >>> classify_session_type(7200)
    <SessionType.DEEP_DIVE: 'deep_dive'>
    >>> classify_session_type(20000)
    <SessionType.MARATHON: 'marathon'>
    """
    for threshold, session_type in SESSION_TYPE_THRESHOLDS:
        if duration_sec < threshold:
            return session_type
    return SessionType.MARATHON


class SessionCloser:
    """Handles Phase 8 of the message lifecycle: session close and light consolidation.

    Computes the emotional arc, subjective time, session statistics,
    saves the finalized SessionRecord to the Chronicle, and clears
    the Stream (working memory).
    """

    def __init__(self, chronicle, session_manager=None) -> None:
        """Initialize the SessionCloser.

        Parameters
        ----------
        chronicle : Chronicle
            The Tier 2 episodic memory store. Used to save the finalized
            SessionRecord via ``chronicle.insert_session()``.
        session_manager : SessionManager, optional
            The session manager. Used to check last standard consolidation
            time. Can be None if consolidation trigger check is not needed.
        """
        self.chronicle = chronicle
        self.session_manager = session_manager

    async def close(
        self,
        session: SessionRecord,
        messages: list[MessageRecord],
        stream=None,
    ) -> SessionRecord:
        """Execute the full Phase 8 session close sequence.

        This method performs ALL of the following steps in order:
        1. Classify session end mode (if not already set by caller)
        2. Compute emotional arc (opening, peak, closing states)
        3. Classify session type from duration
        4. Compute subjective time weight
        5. Compute average emotional intensity and relational significance
        6. Compute message count statistics
        7. Extract topics from messages
        8. Compute compass activation counts
        9. Set relational_field_delta to empty dict (placeholder for Track 017)
        10. Update the session record with all computed fields
        11. Save the finalized SessionRecord to Chronicle
        12. Clear the Stream (working memory)
        13. Return the finalized SessionRecord

        Parameters
        ----------
        session : SessionRecord
            The session record to finalize. Must have ``id``, ``start_time``,
            and ``end_time`` already set. Other fields will be overwritten
            by this method.
        messages : list[MessageRecord]
            All messages from this session, in chronological order.
            Must not be empty — a session with zero messages should not
            reach this code path.
        stream : Stream, optional
            The Tier 1 working memory. If provided, it will be cleared
            after the session is saved. If None, the clear step is skipped.

        Returns
        -------
        SessionRecord
            The fully populated session record, with all computed fields
            set. This is the same object that was saved to Chronicle.

        Raises
        ------
        ValueError
            If ``messages`` is empty.
        """
        if not messages:
            raise ValueError(
                "Cannot close a session with zero messages. "
                "A session must have at least one message to compute "
                "emotional arc, subjective time, etc."
            )

        # -- Step 1: Compute end_time and duration if not already set --------
        if session.end_time is None:
            session.end_time = messages[-1].timestamp

        duration_sec = int(
            (session.end_time - session.start_time).total_seconds()
        )
        session.duration_sec = max(0, duration_sec)

        # -- Step 2: Classify session type from duration ---------------------
        session.session_type = classify_session_type(session.duration_sec)

        # -- Step 3: Compute emotional arc -----------------------------------
        opening_state, peak_state, closing_state = _compute_emotional_arc(
            messages
        )
        session.opening_emotional_state = opening_state
        session.peak_emotional_state = peak_state
        session.closing_emotional_state = closing_state

        # -- Step 4: Compute average emotional intensity and significance ----
        avg_intensity, avg_significance = _compute_averages(messages)
        session.avg_emotional_intensity = avg_intensity
        session.avg_relational_significance = avg_significance

        # -- Step 5: Compute subjective time weight --------------------------
        session.subjective_duration_weight = _compute_subjective_time(
            duration_sec=session.duration_sec,
            avg_arousal=avg_intensity,
            avg_relational_significance=avg_significance,
        )

        # -- Step 6: Compute message count statistics ------------------------
        session.message_count = len(messages)
        session.user_message_count = sum(
            1 for m in messages if m.sender == "user"
        )
        session.companion_message_count = sum(
            1 for m in messages if m.sender == "companion"
        )
        session.avg_response_latency_sec = _compute_avg_response_latency(
            messages
        )

        # -- Step 7: Extract topics ------------------------------------------
        session.topics = _extract_topics(messages)

        # -- Step 8: Compute compass activation counts -----------------------
        session.compass_activations = _compute_compass_activations(messages)

        # -- Step 9: Relational field delta (placeholder for Track 017) ------
        session.relational_field_delta = {}

        # -- Step 10: Save to Chronicle --------------------------------------
        self.chronicle.insert_session(session)

        # -- Step 11: Clear Stream -------------------------------------------
        if stream is not None:
            stream.clear()

        # -- Step 12: Return finalized session -------------------------------
        return session


# ---------------------------------------------------------------------------
# Pure helper functions (no side effects, easy to test independently)
# ---------------------------------------------------------------------------

def _compute_emotional_arc(
    messages: list[MessageRecord],
) -> tuple[EmotionalStateVector, EmotionalStateVector, EmotionalStateVector]:
    """Compute the emotional arc of a session.

    The arc consists of three snapshots:
    - **Opening state:** The emotional state of the first user message.
      If there are no user messages, fall back to the first message of
      any sender.
    - **Peak state:** The emotional state of the message with the highest
      arousal value across ALL messages (user and companion). In case of
      a tie, the earliest message wins.
    - **Closing state:** The emotional state of the last message of any
      sender.

    Parameters
    ----------
    messages : list[MessageRecord]
        All messages in the session, in chronological order.
        Must contain at least one message.

    Returns
    -------
    tuple[EmotionalStateVector, EmotionalStateVector, EmotionalStateVector]
        A 3-tuple of ``(opening_state, peak_state, closing_state)``.
    """
    # Opening: first user message, or first message if no user messages exist
    user_messages = [m for m in messages if m.sender == "user"]
    if user_messages:
        opening_state = user_messages[0].emotional_state
    else:
        opening_state = messages[0].emotional_state

    # Peak: message with highest arousal (earliest wins ties)
    peak_message = max(messages, key=lambda m: m.emotional_state.arousal)
    peak_state = peak_message.emotional_state

    # Closing: last message
    closing_state = messages[-1].emotional_state

    return opening_state, peak_state, closing_state


def _compute_averages(
    messages: list[MessageRecord],
) -> tuple[float, float]:
    """Compute average emotional intensity and relational significance.

    Emotional intensity is approximated by the arousal dimension of the
    EmotionalStateVector, as arousal captures how emotionally activated
    the interaction was.

    Parameters
    ----------
    messages : list[MessageRecord]
        All messages in the session.

    Returns
    -------
    tuple[float, float]
        A 2-tuple of ``(avg_emotional_intensity, avg_relational_significance)``.
        Both values are in [0.0, 1.0].
    """
    total_arousal = sum(m.emotional_state.arousal for m in messages)
    total_significance = sum(
        m.emotional_state.relational_significance for m in messages
    )
    count = len(messages)
    return total_arousal / count, total_significance / count


def _compute_subjective_time(
    duration_sec: int,
    avg_arousal: float,
    avg_relational_significance: float,
) -> float:
    """Compute subjective duration weight for a session.

    Formula from SRS.md FR-TCS-008:
        subjective_duration = clock_duration * intensity_factor * significance_factor

    Where:
        intensity_factor = clamp(avg_arousal * 2, 0.5, 2.0)
        significance_factor = clamp(avg_relational_significance * 2, 0.5, 2.0)

    The multiplication by 2 maps the [0, 1] range of arousal and significance
    to the [0, 2] range, which is then clamped to [0.5, 2.0]. This means:
    - A perfectly calm, routine session (arousal=0.25, significance=0.25)
      has weight = duration * 0.5 * 0.5 = duration * 0.25 (feels shorter)
    - A highly emotional, deeply significant session (arousal=0.9, sig=0.9)
      has weight = duration * 1.8 * 1.8 = duration * 3.24 (feels much longer)

    Parameters
    ----------
    duration_sec : int
        Clock duration of the session in seconds.
    avg_arousal : float
        Average arousal across all messages. Range [0.0, 1.0].
    avg_relational_significance : float
        Average relational significance across all messages. Range [0.0, 1.0].

    Returns
    -------
    float
        The subjective duration weight. Always >= 0.
    """
    intensity_factor = max(0.5, min(2.0, avg_arousal * 2))
    significance_factor = max(0.5, min(2.0, avg_relational_significance * 2))
    return float(duration_sec) * intensity_factor * significance_factor


def _compute_avg_response_latency(messages: list[MessageRecord]) -> float:
    """Compute average response latency in seconds.

    Response latency is the time between a user message and the next
    companion message. Only consecutive user -> companion pairs are
    counted.

    Parameters
    ----------
    messages : list[MessageRecord]
        All messages in the session, in chronological order.

    Returns
    -------
    float
        Average latency in seconds. Returns 0.0 if there are no
        user -> companion pairs.
    """
    latencies: list[float] = []
    for i in range(len(messages) - 1):
        if messages[i].sender == "user" and messages[i + 1].sender == "companion":
            delta = (messages[i + 1].timestamp - messages[i].timestamp).total_seconds()
            latencies.append(delta)
    if not latencies:
        return 0.0
    return sum(latencies) / len(latencies)


def _extract_topics(messages: list[MessageRecord]) -> list[str]:
    """Extract unique topics from all messages in the session.

    Topics are sourced from the emotional state's compass_direction
    and, when available, from message content keywords. For now,
    this implementation collects unique compass_skill_used values
    as topic proxies. A richer topic extraction (using Tier 0 topic
    field) will be available after Track 005.

    Parameters
    ----------
    messages : list[MessageRecord]
        All messages in the session.

    Returns
    -------
    list[str]
        Deduplicated list of topic strings. May be empty.
    """
    topics: set[str] = set()
    for msg in messages:
        if msg.compass_skill_used:
            topics.add(msg.compass_skill_used)
    return sorted(topics)


def _compute_compass_activations(
    messages: list[MessageRecord],
) -> dict[CompassDirection, int]:
    """Count compass activations per direction across all messages.

    A compass activation is counted whenever a message has a
    ``compass_direction`` other than ``CompassDirection.NONE``.

    Parameters
    ----------
    messages : list[MessageRecord]
        All messages in the session.

    Returns
    -------
    dict[CompassDirection, int]
        Map from CompassDirection to the number of times it was activated.
        Directions with zero activations are omitted.
    """
    counts: dict[CompassDirection, int] = {}
    for msg in messages:
        direction = msg.compass_direction
        if direction != CompassDirection.NONE:
            counts[direction] = counts.get(direction, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Consolidation trigger check
# ---------------------------------------------------------------------------

def should_trigger_standard_consolidation(
    chronicle,
    last_standard_consolidation_time: Optional[datetime] = None,
) -> bool:
    """Determine whether standard consolidation should run.

    Standard consolidation should trigger when EITHER of:
    1. More than 3 sessions have been completed since the last standard
       consolidation was run.
    2. The last standard consolidation was more than 12 hours ago
       (and at least 1 session has occurred since).

    This function does NOT run consolidation. It only returns True/False.
    The caller is responsible for scheduling the actual consolidation job
    if this returns True.

    Parameters
    ----------
    chronicle : Chronicle
        The Chronicle instance. Used to query recent session count.
        The chronicle must have a ``get_sessions_since(datetime)`` method
        or equivalent. If not yet available, this function falls back to
        a simple time-based check.
    last_standard_consolidation_time : datetime, optional
        When the last standard consolidation ran. If None, consolidation
        is assumed to have never run, and the function returns True
        (as long as there is at least one session).

    Returns
    -------
    bool
        True if standard consolidation should be triggered, False otherwise.
    """
    now = datetime.utcnow()

    # If consolidation has never run, trigger it
    if last_standard_consolidation_time is None:
        return True

    hours_since_last = (
        now - last_standard_consolidation_time
    ).total_seconds() / 3600.0

    # Time-based trigger: more than 12 hours since last consolidation
    if hours_since_last > STANDARD_CONSOLIDATION_HOURS_THRESHOLD:
        return True

    # Session-count trigger: check if chronicle has enough sessions
    # since the last consolidation. We use a try/except because the
    # chronicle may not yet have the get_sessions_since method
    # (depends on Track 003 implementation completeness).
    try:
        recent_sessions = chronicle.get_sessions_since(
            last_standard_consolidation_time
        )
        if len(recent_sessions) >= STANDARD_CONSOLIDATION_SESSION_THRESHOLD:
            return True
    except AttributeError:
        # chronicle.get_sessions_since() not yet implemented.
        # Fall back to time-only check (already handled above).
        pass

    return False
```

**What this does:**
1. `classify_session_type()` maps duration to one of the 5 session types from SRS.md Section 3.4.
2. `SessionCloser.close()` orchestrates the full Phase 8 sequence from SRS.md Section 4.8.
3. Pure helper functions (`_compute_emotional_arc`, `_compute_averages`, `_compute_subjective_time`, etc.) contain all computation logic with no side effects, making them easy to unit test.
4. `should_trigger_standard_consolidation()` checks whether the background consolidation process should be scheduled.

---

## Phase 3: Integration

### Step 3.1: Update orchestrator shutdown flow to use SessionCloser

This step modifies `gwen/core/orchestrator.py` to use SessionCloser during session teardown. **If the orchestrator does not yet exist (Track 008 not complete), skip this step and leave a TODO comment in this plan.**

Add the following to the orchestrator's session end handler. The exact insertion point depends on Track 008's implementation, but the pattern is:

```python
# In gwen/core/orchestrator.py, inside the session end handler:

from gwen.consolidation.light import SessionCloser, should_trigger_standard_consolidation

# ... inside the method that handles session end ...

async def _handle_session_end(self, end_mode: SessionEndMode) -> None:
    """Handle session close — Phase 8 of the message lifecycle."""
    session = self.session_manager.current_session
    messages = self.chronicle.get_messages_by_session(session.id)

    # Set end mode
    session.end_mode = end_mode

    # Run Phase 8 via SessionCloser
    closer = SessionCloser(
        chronicle=self.chronicle,
        session_manager=self.session_manager,
    )
    finalized = await closer.close(
        session=session,
        messages=messages,
        stream=self.stream,
    )

    # Check if standard consolidation should trigger
    if should_trigger_standard_consolidation(
        chronicle=self.chronicle,
        last_standard_consolidation_time=self._last_standard_consolidation,
    ):
        # Schedule standard consolidation (implemented in Track 020)
        # For now, just log that it should trigger
        pass  # TODO(track-020): schedule standard consolidation
```

**Why this pattern:** The orchestrator delegates ALL Phase 8 computation to SessionCloser. It does not compute emotional arcs or subjective time itself. This keeps the orchestrator thin and the consolidation logic testable in isolation.

**If Track 008 is not complete:** Do NOT create orchestrator.py. Instead, add a note: "Integration deferred — orchestrator not yet available."

---

## Phase 4: Tests

### Step 4.1: Write tests/test_session_close.py

Create the file `tests/test_session_close.py` with the following exact content:

```python
"""Tests for gwen.consolidation.light — Session Close & Light Consolidation.

Run with:
    pytest tests/test_session_close.py -v
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import MagicMock

import pytest

from gwen.consolidation.light import (
    SessionCloser,
    _compute_avg_response_latency,
    _compute_averages,
    _compute_compass_activations,
    _compute_emotional_arc,
    _compute_subjective_time,
    _extract_topics,
    classify_session_type,
    should_trigger_standard_consolidation,
)
from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.messages import (
    MessageRecord,
    SessionEndMode,
    SessionRecord,
    SessionType,
)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

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
    content: str = "Hello",
    sender: str = "user",
    timestamp: Optional[datetime] = None,
    arousal: float = 0.4,
    relational_significance: float = 0.3,
    compass_direction: CompassDirection = CompassDirection.NONE,
    compass_skill_used: Optional[str] = None,
) -> MessageRecord:
    """Create a MessageRecord with sensible defaults."""
    return MessageRecord(
        id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=timestamp or datetime(2026, 2, 9, 14, 30, 0),
        sender=sender,
        content=content,
        tme=None,
        emotional_state=_make_emotional_state(
            arousal=arousal,
            relational_significance=relational_significance,
        ),
        storage_strength=0.34,
        is_flashbulb=False,
        compass_direction=compass_direction,
        compass_skill_used=compass_skill_used,
        semantic_embedding_id=None,
        emotional_embedding_id=None,
    )


def _make_session(
    session_id: str = "sess-001",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> SessionRecord:
    """Create a minimal SessionRecord for testing. Fields will be overwritten by close()."""
    return SessionRecord(
        id=session_id,
        start_time=start_time or datetime(2026, 2, 9, 14, 0, 0),
        end_time=end_time or datetime(2026, 2, 9, 14, 45, 0),
        duration_sec=0,
        session_type=SessionType.CHAT,
        end_mode=SessionEndMode.NATURAL,
        opening_emotional_state=_make_emotional_state(),
        peak_emotional_state=_make_emotional_state(),
        closing_emotional_state=_make_emotional_state(),
        emotional_arc_embedding_id=None,
        avg_emotional_intensity=0.0,
        avg_relational_significance=0.0,
        subjective_duration_weight=0.0,
        message_count=0,
        user_message_count=0,
        companion_message_count=0,
        avg_response_latency_sec=0.0,
        compass_activations={},
        topics=[],
        relational_field_delta={},
        gwen_initiated=False,
    )


# ---------------------------------------------------------------------------
# Tests: Session Type Classification
# ---------------------------------------------------------------------------

class TestClassifySessionType:
    """Tests for classify_session_type()."""

    def test_ping_under_5_minutes(self) -> None:
        """A 2-minute session should be classified as PING."""
        assert classify_session_type(120) == SessionType.PING

    def test_chat_5_to_30_minutes(self) -> None:
        """A 10-minute session should be classified as CHAT."""
        assert classify_session_type(600) == SessionType.CHAT

    def test_hang_30_to_90_minutes(self) -> None:
        """A 60-minute session should be classified as HANG."""
        assert classify_session_type(3600) == SessionType.HANG

    def test_deep_dive_90_to_180_minutes(self) -> None:
        """A 120-minute session should be classified as DEEP_DIVE."""
        assert classify_session_type(7200) == SessionType.DEEP_DIVE

    def test_marathon_over_180_minutes(self) -> None:
        """A 240-minute session should be classified as MARATHON."""
        assert classify_session_type(14400) == SessionType.MARATHON

    def test_boundary_exactly_300_seconds(self) -> None:
        """Exactly 5 minutes (300s) should be CHAT, not PING (PING is < 300)."""
        assert classify_session_type(300) == SessionType.CHAT

    def test_zero_duration(self) -> None:
        """A 0-second session should be classified as PING."""
        assert classify_session_type(0) == SessionType.PING


# ---------------------------------------------------------------------------
# Tests: Emotional Arc Computation
# ---------------------------------------------------------------------------

class TestComputeEmotionalArc:
    """Tests for _compute_emotional_arc()."""

    def test_opening_is_first_user_message(self) -> None:
        """Opening state should come from the first user message."""
        messages = [
            _make_message(sender="companion", arousal=0.1),
            _make_message(sender="user", arousal=0.5),
            _make_message(sender="user", arousal=0.7),
        ]
        opening, _, _ = _compute_emotional_arc(messages)
        assert opening.arousal == pytest.approx(0.5)

    def test_opening_falls_back_to_first_message_if_no_user(self) -> None:
        """If all messages are companion, opening uses the first message."""
        messages = [
            _make_message(sender="companion", arousal=0.2),
            _make_message(sender="companion", arousal=0.8),
        ]
        opening, _, _ = _compute_emotional_arc(messages)
        assert opening.arousal == pytest.approx(0.2)

    def test_peak_is_highest_arousal(self) -> None:
        """Peak state should be the message with the highest arousal."""
        messages = [
            _make_message(arousal=0.3),
            _make_message(arousal=0.9),
            _make_message(arousal=0.5),
        ]
        _, peak, _ = _compute_emotional_arc(messages)
        assert peak.arousal == pytest.approx(0.9)

    def test_closing_is_last_message(self) -> None:
        """Closing state should be the emotional state of the last message."""
        messages = [
            _make_message(arousal=0.3),
            _make_message(arousal=0.9),
            _make_message(arousal=0.2),
        ]
        _, _, closing = _compute_emotional_arc(messages)
        assert closing.arousal == pytest.approx(0.2)

    def test_single_message_all_same(self) -> None:
        """With one message, opening = peak = closing."""
        messages = [_make_message(arousal=0.6)]
        opening, peak, closing = _compute_emotional_arc(messages)
        assert opening.arousal == pytest.approx(0.6)
        assert peak.arousal == pytest.approx(0.6)
        assert closing.arousal == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Tests: Averages
# ---------------------------------------------------------------------------

class TestComputeAverages:
    """Tests for _compute_averages()."""

    def test_averages_computed_correctly(self) -> None:
        """Average arousal and significance should be arithmetic means."""
        messages = [
            _make_message(arousal=0.2, relational_significance=0.4),
            _make_message(arousal=0.6, relational_significance=0.8),
            _make_message(arousal=0.4, relational_significance=0.6),
        ]
        avg_intensity, avg_significance = _compute_averages(messages)
        assert avg_intensity == pytest.approx(0.4)
        assert avg_significance == pytest.approx(0.6)

    def test_single_message(self) -> None:
        """With one message, averages equal that message's values."""
        messages = [_make_message(arousal=0.7, relational_significance=0.3)]
        avg_intensity, avg_significance = _compute_averages(messages)
        assert avg_intensity == pytest.approx(0.7)
        assert avg_significance == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Tests: Subjective Time
# ---------------------------------------------------------------------------

class TestComputeSubjectiveTime:
    """Tests for _compute_subjective_time()."""

    def test_neutral_session(self) -> None:
        """A perfectly average session: arousal=0.5, sig=0.5 -> factors=1.0."""
        result = _compute_subjective_time(
            duration_sec=1000, avg_arousal=0.5, avg_relational_significance=0.5
        )
        # factor = max(0.5, min(2.0, 0.5*2)) = 1.0 for both
        assert result == pytest.approx(1000.0)

    def test_high_intensity_session(self) -> None:
        """High arousal + high significance -> subjective time much longer."""
        result = _compute_subjective_time(
            duration_sec=1000, avg_arousal=0.9, avg_relational_significance=0.9
        )
        # intensity = min(2.0, 0.9*2) = 1.8
        # significance = min(2.0, 0.9*2) = 1.8
        # 1000 * 1.8 * 1.8 = 3240.0
        assert result == pytest.approx(3240.0)

    def test_low_intensity_session(self) -> None:
        """Very low arousal/significance -> clamped to 0.5 minimum."""
        result = _compute_subjective_time(
            duration_sec=1000, avg_arousal=0.1, avg_relational_significance=0.1
        )
        # intensity = max(0.5, 0.1*2) = max(0.5, 0.2) = 0.5
        # significance = max(0.5, 0.1*2) = max(0.5, 0.2) = 0.5
        # 1000 * 0.5 * 0.5 = 250.0
        assert result == pytest.approx(250.0)

    def test_zero_duration(self) -> None:
        """Zero-length session -> zero subjective time."""
        result = _compute_subjective_time(
            duration_sec=0, avg_arousal=0.9, avg_relational_significance=0.9
        )
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: Response Latency
# ---------------------------------------------------------------------------

class TestComputeAvgResponseLatency:
    """Tests for _compute_avg_response_latency()."""

    def test_user_companion_pairs(self) -> None:
        """Latency should be computed from user->companion pairs."""
        t0 = datetime(2026, 2, 9, 14, 0, 0)
        messages = [
            _make_message(sender="user", timestamp=t0),
            _make_message(sender="companion", timestamp=t0 + timedelta(seconds=2)),
            _make_message(sender="user", timestamp=t0 + timedelta(seconds=10)),
            _make_message(sender="companion", timestamp=t0 + timedelta(seconds=14)),
        ]
        result = _compute_avg_response_latency(messages)
        # First pair: 2s, second pair: 4s -> avg = 3.0
        assert result == pytest.approx(3.0)

    def test_no_pairs_returns_zero(self) -> None:
        """If there are no user->companion pairs, return 0."""
        messages = [
            _make_message(sender="user"),
            _make_message(sender="user"),
        ]
        assert _compute_avg_response_latency(messages) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: Topic Extraction
# ---------------------------------------------------------------------------

class TestExtractTopics:
    """Tests for _extract_topics()."""

    def test_collects_compass_skills(self) -> None:
        """Topics should include unique compass_skill_used values."""
        messages = [
            _make_message(compass_skill_used="fuel_check"),
            _make_message(compass_skill_used="anchor_breath"),
            _make_message(compass_skill_used="fuel_check"),  # duplicate
        ]
        topics = _extract_topics(messages)
        assert sorted(topics) == ["anchor_breath", "fuel_check"]

    def test_empty_when_no_skills(self) -> None:
        """If no messages have compass_skill_used, topics is empty."""
        messages = [_make_message(), _make_message()]
        assert _extract_topics(messages) == []


# ---------------------------------------------------------------------------
# Tests: Compass Activations
# ---------------------------------------------------------------------------

class TestComputeCompassActivations:
    """Tests for _compute_compass_activations()."""

    def test_counts_directions(self) -> None:
        """Activations should count each non-NONE direction."""
        messages = [
            _make_message(compass_direction=CompassDirection.NORTH),
            _make_message(compass_direction=CompassDirection.NORTH),
            _make_message(compass_direction=CompassDirection.SOUTH),
            _make_message(compass_direction=CompassDirection.NONE),
        ]
        result = _compute_compass_activations(messages)
        assert result[CompassDirection.NORTH] == 2
        assert result[CompassDirection.SOUTH] == 1
        assert CompassDirection.NONE not in result

    def test_empty_when_all_none(self) -> None:
        """If all messages are NONE, activations is empty."""
        messages = [_make_message(), _make_message()]
        assert _compute_compass_activations(messages) == {}


# ---------------------------------------------------------------------------
# Tests: SessionCloser.close() (integration)
# ---------------------------------------------------------------------------

class TestSessionCloserClose:
    """Tests for SessionCloser.close() — the full Phase 8 sequence."""

    @pytest.fixture()
    def mock_chronicle(self):
        """A mock Chronicle that records insert_session calls."""
        chronicle = MagicMock()
        chronicle.insert_session = MagicMock()
        return chronicle

    @pytest.fixture()
    def mock_stream(self):
        """A mock Stream that records clear() calls."""
        stream = MagicMock()
        stream.clear = MagicMock()
        return stream

    async def test_full_close_sequence(self, mock_chronicle, mock_stream) -> None:
        """close() should populate all session fields and save to chronicle."""
        session = _make_session(
            start_time=datetime(2026, 2, 9, 14, 0, 0),
            end_time=datetime(2026, 2, 9, 14, 20, 0),
        )
        t0 = datetime(2026, 2, 9, 14, 0, 0)
        messages = [
            _make_message(
                sender="user",
                timestamp=t0,
                arousal=0.3,
                relational_significance=0.2,
            ),
            _make_message(
                sender="companion",
                timestamp=t0 + timedelta(seconds=3),
                arousal=0.5,
                relational_significance=0.4,
            ),
            _make_message(
                sender="user",
                timestamp=t0 + timedelta(minutes=10),
                arousal=0.8,
                relational_significance=0.6,
            ),
            _make_message(
                sender="companion",
                timestamp=t0 + timedelta(minutes=10, seconds=2),
                arousal=0.4,
                relational_significance=0.5,
            ),
        ]

        closer = SessionCloser(chronicle=mock_chronicle)
        result = await closer.close(session, messages, stream=mock_stream)

        # Session type: 20 minutes = 1200 seconds -> CHAT
        assert result.session_type == SessionType.CHAT

        # Emotional arc
        assert result.opening_emotional_state.arousal == pytest.approx(0.3)
        assert result.peak_emotional_state.arousal == pytest.approx(0.8)
        assert result.closing_emotional_state.arousal == pytest.approx(0.4)

        # Message counts
        assert result.message_count == 4
        assert result.user_message_count == 2
        assert result.companion_message_count == 2

        # Chronicle was called
        mock_chronicle.insert_session.assert_called_once_with(result)

        # Stream was cleared
        mock_stream.clear.assert_called_once()

    async def test_close_raises_on_empty_messages(self, mock_chronicle) -> None:
        """close() should raise ValueError if messages list is empty."""
        session = _make_session()
        closer = SessionCloser(chronicle=mock_chronicle)
        with pytest.raises(ValueError, match="zero messages"):
            await closer.close(session, [], stream=None)

    async def test_relational_field_delta_is_empty(self, mock_chronicle) -> None:
        """Relational field delta is a placeholder (empty dict) until Track 017."""
        session = _make_session()
        messages = [_make_message()]
        closer = SessionCloser(chronicle=mock_chronicle)
        result = await closer.close(session, messages)
        assert result.relational_field_delta == {}


# ---------------------------------------------------------------------------
# Tests: Standard Consolidation Trigger
# ---------------------------------------------------------------------------

class TestShouldTriggerStandardConsolidation:
    """Tests for should_trigger_standard_consolidation()."""

    def test_triggers_when_never_run(self) -> None:
        """If consolidation has never run, it should trigger."""
        chronicle = MagicMock()
        assert should_trigger_standard_consolidation(
            chronicle, last_standard_consolidation_time=None
        ) is True

    def test_triggers_after_12_hours(self) -> None:
        """If 13 hours have passed since last consolidation, trigger."""
        chronicle = MagicMock()
        last_time = datetime.utcnow() - timedelta(hours=13)
        assert should_trigger_standard_consolidation(
            chronicle, last_standard_consolidation_time=last_time
        ) is True

    def test_does_not_trigger_when_recent(self) -> None:
        """If consolidation ran 1 hour ago and few sessions, do not trigger."""
        chronicle = MagicMock()
        # Simulate get_sessions_since returning 1 session
        chronicle.get_sessions_since = MagicMock(return_value=["s1"])
        last_time = datetime.utcnow() - timedelta(hours=1)
        assert should_trigger_standard_consolidation(
            chronicle, last_standard_consolidation_time=last_time
        ) is False

    def test_triggers_when_enough_sessions(self) -> None:
        """If 3+ sessions since last consolidation, trigger even if recent."""
        chronicle = MagicMock()
        chronicle.get_sessions_since = MagicMock(
            return_value=["s1", "s2", "s3"]
        )
        last_time = datetime.utcnow() - timedelta(hours=1)
        assert should_trigger_standard_consolidation(
            chronicle, last_standard_consolidation_time=last_time
        ) is True
```

**What these tests cover:**
- `classify_session_type`: all 5 types + boundary at 300s + zero duration
- `_compute_emotional_arc`: opening (user vs fallback), peak (highest arousal), closing (last), single message
- `_compute_averages`: arithmetic mean correctness
- `_compute_subjective_time`: neutral/high/low intensity + zero duration
- `_compute_avg_response_latency`: normal pairs + no pairs
- `_extract_topics`: deduplication + empty case
- `_compute_compass_activations`: counts + empty case
- `SessionCloser.close()`: full integration with mocks, error on empty messages, placeholder delta
- `should_trigger_standard_consolidation`: never-run, time-based, recent, session-count

---

### Step 4.2: Run the tests

Execute the following command from the project root:

```bash
pytest tests/test_session_close.py -v
```

**Expected result:** All tests pass. If any test fails, read the error message carefully. The most likely causes are:

1. **ImportError for gwen.models**: Track 002 (data-models) has not been completed yet.
2. **ImportError for gwen.consolidation.light**: Step 2.1 was not completed. Check that `gwen/consolidation/__init__.py` and `gwen/consolidation/light.py` both exist.
3. **Assertion failures**: Compare the test's expected values against the computation logic in light.py.

---

## Checklist (update after each step)

- [ ] Phase 1 complete: gwen/consolidation/__init__.py exists
- [ ] Phase 2 complete: gwen/consolidation/light.py with SessionCloser, classify_session_type, all helper functions, and should_trigger_standard_consolidation
- [ ] Phase 3 complete: Orchestrator updated to use SessionCloser (or deferred if Track 008 not done)
- [ ] Phase 4 complete: tests/test_session_close.py passes with all tests green
