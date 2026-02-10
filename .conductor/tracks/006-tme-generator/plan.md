# Plan: TME Generator

**Track:** 006-tme-generator
**Spec:** [spec.md](./spec.md)
**Depends on:** 002-data-models (TemporalMetadataEnvelope, TimePhase, CircadianDeviationSeverity), 003-database-layer (Chronicle)
**Status:** Not Started

---

## Phase 1: Time Phase Logic

### Step 1.1: Create gwen/temporal/__init__.py

This file should already exist from Track 001. If it does not exist, create it at `C:\Users\Administrator\Desktop\projects\Gwen\gwen\temporal\__init__.py`.

- [x]Verify or create gwen/temporal/__init__.py

```python
"""Temporal Cognition System - TME generation, circadian analysis, gap detection."""
```

**Why:** Makes `gwen.temporal` a valid Python package so that `from gwen.temporal import tme` works.

---

### Step 1.2: Create tme.py with compute_time_phase()

Create the file `C:\Users\Administrator\Desktop\projects\Gwen\gwen\temporal\tme.py`.

- [x]Write compute_time_phase() function
- [x]Write imports

```python
"""Temporal Metadata Envelope (TME) generator.

This module produces a TemporalMetadataEnvelope for every message in the system.
All computation uses system clocks and SQLite queries — zero model inference.
The TME is the foundation of Gwen's temporal awareness.

References: SRS.md Section 3.2 and Section 7 (FR-TCS-001).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TemporalMetadataEnvelope,
    TimePhase,
)

# Type hint only — avoid circular import at runtime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gwen.memory.chronicle import Chronicle


def compute_time_phase(hour: int) -> TimePhase:
    """Map a 24-hour clock hour to a TimePhase.

    The boundaries are defined in SRS.md Section 3.2:
        - DEEP_NIGHT:    00:00 - 04:59  (hours 0, 1, 2, 3, 4)
        - EARLY_MORNING: 05:00 - 07:59  (hours 5, 6, 7)
        - MORNING:       08:00 - 11:59  (hours 8, 9, 10, 11)
        - MIDDAY:        12:00 - 13:59  (hours 12, 13)
        - AFTERNOON:     14:00 - 16:59  (hours 14, 15, 16)
        - EVENING:       17:00 - 20:59  (hours 17, 18, 19, 20)
        - LATE_NIGHT:    21:00 - 23:59  (hours 21, 22, 23)

    Args:
        hour: Integer from 0 to 23 representing the hour of the day in local time.

    Returns:
        The TimePhase enum value corresponding to the given hour.

    Raises:
        ValueError: If hour is not in range 0-23.
    """
    if not (0 <= hour <= 23):
        raise ValueError(f"hour must be 0-23, got {hour}")

    if hour <= 4:
        return TimePhase.DEEP_NIGHT
    elif hour <= 7:
        return TimePhase.EARLY_MORNING
    elif hour <= 11:
        return TimePhase.MORNING
    elif hour <= 13:
        return TimePhase.MIDDAY
    elif hour <= 16:
        return TimePhase.AFTERNOON
    elif hour <= 20:
        return TimePhase.EVENING
    else:
        return TimePhase.LATE_NIGHT
```

**How the mapping works:**
- The function uses simple range checks on the integer hour (0-23).
- `hour <= 4` catches 0, 1, 2, 3, 4 → DEEP_NIGHT
- `hour <= 7` catches 5, 6, 7 → EARLY_MORNING (since we already excluded 0-4)
- And so on through the chain of `elif` statements.
- The `else` clause at the end catches 21, 22, 23 → LATE_NIGHT.
- A `ValueError` is raised if the hour is outside 0-23 to catch programming errors early.

---

## Phase 2: TME Generator Class

### Step 2.1: TMEGenerator class with __init__

Continue editing `C:\Users\Administrator\Desktop\projects\Gwen\gwen\temporal\tme.py`. Append the class below after the `compute_time_phase()` function.

- [x]Write TMEGenerator class with __init__ and session state

```python
class TMEGenerator:
    """Generates a TemporalMetadataEnvelope for every message.

    The TME wraps each message with rich temporal context: absolute time,
    clock position, session state, intra-message timing, and inter-session
    statistics. All computed from system clocks and Chronicle queries.

    Usage:
        generator = TMEGenerator(chronicle)
        generator.start_session("session-uuid-here")
        tme = generator.generate("user")   # for a user message
        tme = generator.generate("companion")  # for a companion message
    """

    def __init__(self, chronicle: Optional[Chronicle] = None) -> None:
        """Initialize the TME generator.

        Args:
            chronicle: The Chronicle (SQLite) instance for querying inter-session
                       statistics. If None, inter-session fields will use defaults
                       (useful for testing or first-run scenarios).
        """
        self._chronicle = chronicle

        # Session state — set by start_session(), updated by generate()
        self._session_id: Optional[str] = None
        self._session_start: Optional[datetime] = None
        self._msg_index: int = 0

        # Message timestamp tracking — for intra-message timing
        # Key: sender ("user" or "companion"), Value: datetime of last message
        self._last_msg_time: Optional[datetime] = None
        self._last_user_msg_time: Optional[datetime] = None
        self._last_companion_msg_time: Optional[datetime] = None

        # Rolling counters for message density
        # Stores timestamps of all user messages in the current session
        self._user_msg_timestamps: list[datetime] = []
```

**What each field tracks:**
- `_chronicle`: Reference to the SQLite Chronicle for inter-session queries. Can be None during testing.
- `_session_id`, `_session_start`, `_msg_index`: Current session state. Reset by `start_session()`.
- `_last_msg_time`: Timestamp of the last message (any sender) for computing `time_since_last_msg_sec`.
- `_last_user_msg_time`, `_last_companion_msg_time`: Per-sender timestamps for `time_since_last_user_msg_sec` and `time_since_last_gwen_msg_sec`.
- `_user_msg_timestamps`: List of all user message timestamps in the current session, used to compute `user_msgs_last_5min`, `user_msgs_last_hour`, `user_msgs_last_24hr`.

---

### Step 2.2: start_session() method

Continue in the same class.

- [x]Write start_session() method

```python
    def start_session(self, session_id: Optional[str] = None) -> str:
        """Start a new session and reset all session-scoped state.

        This MUST be called before the first generate() call in a session.
        It resets the message counter, clears timing state, and records
        the session start time.

        Args:
            session_id: Optional UUID string for the session. If not provided,
                        a new UUID is generated automatically.

        Returns:
            The session_id (either the provided one or the auto-generated one).
        """
        self._session_id = session_id or str(uuid.uuid4())
        self._session_start = datetime.now()
        self._msg_index = 0

        # Reset intra-message timing
        self._last_msg_time = None
        self._last_user_msg_time = None
        self._last_companion_msg_time = None
        self._user_msg_timestamps = []

        return self._session_id
```

**Why reset everything:** Each session is an independent conversational unit. Timing from a previous session should not leak into the new one. The `_user_msg_timestamps` list is cleared because density counters (messages in last 5min) are session-scoped.

---

### Step 2.3: generate() method — the main entry point

Continue in the same class.

- [x]Write generate() method that computes ALL TME fields

```python
    def generate(self, message_sender: str) -> TemporalMetadataEnvelope:
        """Generate a complete TME for the current message.

        This is the main entry point. It computes all temporal fields from
        system clocks and Chronicle queries.

        Args:
            message_sender: Either "user" or "companion" — identifies who
                            sent the message being wrapped.

        Returns:
            A fully populated TemporalMetadataEnvelope.

        Raises:
            RuntimeError: If start_session() was not called first.
        """
        if self._session_id is None or self._session_start is None:
            raise RuntimeError(
                "TMEGenerator.start_session() must be called before generate(). "
                "No active session found."
            )

        now: datetime = datetime.now()
        now_utc: datetime = datetime.now(timezone.utc)

        # --- Clock position fields ---
        hour_of_day: int = now.hour
        day_of_week: str = now.strftime("%A")  # "Monday", "Tuesday", etc.
        day_of_month: int = now.day
        month: int = now.month
        year: int = now.year
        is_weekend: bool = day_of_week in ("Saturday", "Sunday")
        time_phase: TimePhase = compute_time_phase(hour_of_day)

        # --- Session context ---
        session_duration_sec: int = int((now - self._session_start).total_seconds())
        msg_index: int = self._msg_index

        # --- Intra-message timing ---
        intra = self._compute_intra_message_timing(now, message_sender)

        # --- Inter-session timing ---
        inter = self._compute_inter_session_timing()

        # --- Circadian deviation ---
        # Default to NONE. The circadian module (Track 006 future or separate track)
        # will compute real deviation once 30+ days of data exist.
        circadian_deviation_severity: CircadianDeviationSeverity = (
            CircadianDeviationSeverity.NONE
        )
        circadian_deviation_type: Optional[str] = None

        # --- Update internal state AFTER computing the TME ---
        # (so the current message's timing is relative to the previous one)
        self._msg_index += 1
        self._last_msg_time = now
        if message_sender == "user":
            self._last_user_msg_time = now
            self._user_msg_timestamps.append(now)
        elif message_sender == "companion":
            self._last_companion_msg_time = now

        # --- Build and return the envelope ---
        return TemporalMetadataEnvelope(
            # Absolute time
            timestamp_utc=now_utc,
            local_time=now,
            # Clock position
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month=month,
            year=year,
            is_weekend=is_weekend,
            time_phase=time_phase,
            # Session context
            session_id=self._session_id,
            session_start=self._session_start,
            session_duration_sec=session_duration_sec,
            msg_index_in_session=msg_index,
            # Intra-message timing
            time_since_last_msg_sec=intra["time_since_last_msg_sec"],
            time_since_last_user_msg_sec=intra["time_since_last_user_msg_sec"],
            time_since_last_gwen_msg_sec=intra["time_since_last_gwen_msg_sec"],
            user_msgs_last_5min=intra["user_msgs_last_5min"],
            user_msgs_last_hour=intra["user_msgs_last_hour"],
            user_msgs_last_24hr=intra["user_msgs_last_24hr"],
            # Inter-session timing
            last_session_end=inter["last_session_end"],
            hours_since_last_session=inter["hours_since_last_session"],
            sessions_last_7_days=inter["sessions_last_7_days"],
            sessions_last_30_days=inter["sessions_last_30_days"],
            avg_session_gap_30d_hours=inter["avg_session_gap_30d_hours"],
            # Circadian deviation
            circadian_deviation_severity=circadian_deviation_severity,
            circadian_deviation_type=circadian_deviation_type,
        )
```

**Critical ordering detail:** The internal state (`_msg_index`, `_last_msg_time`, etc.) is updated AFTER computing the TME. This ensures that the timing for message N is relative to message N-1. If we updated before computing, the first message would incorrectly show `time_since_last_msg_sec = 0.0` instead of `None`.

---

### Step 2.4: _compute_intra_message_timing() helper

Continue in the same class.

- [x]Write _compute_intra_message_timing() method

```python
    def _compute_intra_message_timing(
        self,
        now: datetime,
        message_sender: str,
    ) -> dict:
        """Compute timing between messages within the current session.

        Calculates:
        - time_since_last_msg_sec: Seconds since the last message (any sender).
          None if this is the first message.
        - time_since_last_user_msg_sec: Seconds since the last user message.
          None if no user message has been sent yet.
        - time_since_last_gwen_msg_sec: Seconds since the last companion message.
          None if no companion message has been sent yet.
        - user_msgs_last_5min: Count of user messages in the last 5 minutes.
        - user_msgs_last_hour: Count of user messages in the last 60 minutes.
        - user_msgs_last_24hr: Count of user messages in the last 24 hours.

        Args:
            now: The current timestamp (datetime.now()).
            message_sender: "user" or "companion".

        Returns:
            Dict with all 6 intra-message timing fields.
        """
        # Time since last message (any sender)
        time_since_last_msg_sec: Optional[float] = None
        if self._last_msg_time is not None:
            delta = (now - self._last_msg_time).total_seconds()
            time_since_last_msg_sec = delta

        # Time since last user message
        time_since_last_user_msg_sec: Optional[float] = None
        if self._last_user_msg_time is not None:
            delta = (now - self._last_user_msg_time).total_seconds()
            time_since_last_user_msg_sec = delta

        # Time since last companion message
        time_since_last_gwen_msg_sec: Optional[float] = None
        if self._last_companion_msg_time is not None:
            delta = (now - self._last_companion_msg_time).total_seconds()
            time_since_last_gwen_msg_sec = delta

        # Message density: count user messages in time windows
        # Uses _user_msg_timestamps which tracks all user messages in this session
        cutoff_5min: datetime = now - timedelta(minutes=5)
        cutoff_1hr: datetime = now - timedelta(hours=1)
        cutoff_24hr: datetime = now - timedelta(hours=24)

        user_msgs_last_5min: int = sum(
            1 for ts in self._user_msg_timestamps if ts >= cutoff_5min
        )
        user_msgs_last_hour: int = sum(
            1 for ts in self._user_msg_timestamps if ts >= cutoff_1hr
        )
        user_msgs_last_24hr: int = sum(
            1 for ts in self._user_msg_timestamps if ts >= cutoff_24hr
        )

        return {
            "time_since_last_msg_sec": time_since_last_msg_sec,
            "time_since_last_user_msg_sec": time_since_last_user_msg_sec,
            "time_since_last_gwen_msg_sec": time_since_last_gwen_msg_sec,
            "user_msgs_last_5min": user_msgs_last_5min,
            "user_msgs_last_hour": user_msgs_last_hour,
            "user_msgs_last_24hr": user_msgs_last_24hr,
        }
```

**Why return a dict?** This helper computes 6 related values. Returning them as a dict with string keys makes the caller code in `generate()` clear and self-documenting. A dataclass or NamedTuple would also work, but a dict is simpler here since this is an internal helper.

**Note on density counts:** The `_user_msg_timestamps` list is session-scoped (cleared in `start_session()`). For `user_msgs_last_24hr`, this means it only counts messages within the current session, not across sessions. For cross-session density, you would query the Chronicle. However, since sessions rarely last 24 hours, the in-memory count is sufficient and avoids a database hit on every message.

---

### Step 2.5: _compute_inter_session_timing() helper

Continue in the same class.

- [x]Write _compute_inter_session_timing() method

```python
    def _compute_inter_session_timing(self) -> dict:
        """Compute timing between sessions by querying the Chronicle.

        Calculates:
        - last_session_end: When the previous session ended (datetime or None).
        - hours_since_last_session: Hours between last session end and now (float or None).
        - sessions_last_7_days: Count of sessions in the last 7 days.
        - sessions_last_30_days: Count of sessions in the last 30 days.
        - avg_session_gap_30d_hours: Average hours between sessions in last 30 days
          (float or None if <2 sessions).

        If self._chronicle is None (no database available), returns safe defaults:
        all counts are 0 and all optionals are None.

        Returns:
            Dict with all 5 inter-session timing fields.
        """
        # Default values — used when no Chronicle is available
        defaults: dict = {
            "last_session_end": None,
            "hours_since_last_session": None,
            "sessions_last_7_days": 0,
            "sessions_last_30_days": 0,
            "avg_session_gap_30d_hours": None,
        }

        if self._chronicle is None:
            return defaults

        now: datetime = datetime.now()

        # Query Chronicle for the most recent session (excluding current)
        # Chronicle.get_last_session_end() returns Optional[datetime]
        try:
            last_session_end: Optional[datetime] = (
                self._chronicle.get_last_session_end(
                    exclude_session_id=self._session_id
                )
            )
        except (AttributeError, Exception):
            # Chronicle may not have this method yet (Track 003 in progress)
            # or database may be empty. Fail gracefully.
            return defaults

        hours_since_last_session: Optional[float] = None
        if last_session_end is not None:
            delta = (now - last_session_end).total_seconds() / 3600.0
            hours_since_last_session = delta

        # Query session counts in time windows
        try:
            cutoff_7d: datetime = now - timedelta(days=7)
            cutoff_30d: datetime = now - timedelta(days=30)

            sessions_last_7_days: int = (
                self._chronicle.count_sessions_since(cutoff_7d)
            )
            sessions_last_30_days: int = (
                self._chronicle.count_sessions_since(cutoff_30d)
            )
        except (AttributeError, Exception):
            sessions_last_7_days = 0
            sessions_last_30_days = 0

        # Compute average gap between sessions in last 30 days
        avg_session_gap_30d_hours: Optional[float] = None
        try:
            session_times: list[datetime] = (
                self._chronicle.get_session_start_times_since(cutoff_30d)
            )
            if len(session_times) >= 2:
                # Sort chronologically and compute gaps between consecutive sessions
                session_times.sort()
                gaps: list[float] = [
                    (session_times[i + 1] - session_times[i]).total_seconds() / 3600.0
                    for i in range(len(session_times) - 1)
                ]
                avg_session_gap_30d_hours = sum(gaps) / len(gaps)
        except (AttributeError, Exception):
            avg_session_gap_30d_hours = None

        return {
            "last_session_end": last_session_end,
            "hours_since_last_session": hours_since_last_session,
            "sessions_last_7_days": sessions_last_7_days,
            "sessions_last_30_days": sessions_last_30_days,
            "avg_session_gap_30d_hours": avg_session_gap_30d_hours,
        }
```

**Chronicle methods expected (from Track 003):**
This helper calls three Chronicle methods that should be defined in Track 003:
1. `chronicle.get_last_session_end(exclude_session_id: str) -> Optional[datetime]` — Returns the end timestamp of the most recent session, excluding the given session_id.
2. `chronicle.count_sessions_since(since: datetime) -> int` — Counts how many sessions started after the given timestamp.
3. `chronicle.get_session_start_times_since(since: datetime) -> list[datetime]` — Returns the start timestamps of all sessions after the given timestamp.

If Track 003 is not yet complete or the Chronicle does not have these methods, the `try/except` blocks catch `AttributeError` and return safe defaults. This allows the TME generator to work in isolation during development and testing.

**Average gap calculation explained:**
1. Get all session start times in the last 30 days.
2. Sort them chronologically.
3. Compute the time gap (in hours) between each consecutive pair.
4. Return the arithmetic mean of those gaps.
5. If fewer than 2 sessions exist, return None (cannot compute a gap from a single session).

---

## Phase 3: Tests

### Step 3.1: tests/test_tme.py

Create the file `C:\Users\Administrator\Desktop\projects\Gwen\tests\test_tme.py`.

- [x]Write all TME tests

```python
"""Tests for TME generator — temporal metadata envelope computation.

These tests verify TimePhase mapping, session tracking, intra-message timing,
and weekend detection. Inter-session timing is tested with a mock Chronicle.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TimePhase,
)
from gwen.temporal.tme import TMEGenerator, compute_time_phase


# ===========================================================================
# TimePhase Mapping Tests
# ===========================================================================

class TestComputeTimePhase:
    """Test compute_time_phase() maps all 24 hours correctly."""

    def test_deep_night_hours(self) -> None:
        """Hours 0-4 → DEEP_NIGHT."""
        for hour in range(0, 5):
            assert compute_time_phase(hour) == TimePhase.DEEP_NIGHT, (
                f"Hour {hour} should be DEEP_NIGHT"
            )

    def test_early_morning_hours(self) -> None:
        """Hours 5-7 → EARLY_MORNING."""
        for hour in range(5, 8):
            assert compute_time_phase(hour) == TimePhase.EARLY_MORNING, (
                f"Hour {hour} should be EARLY_MORNING"
            )

    def test_morning_hours(self) -> None:
        """Hours 8-11 → MORNING."""
        for hour in range(8, 12):
            assert compute_time_phase(hour) == TimePhase.MORNING, (
                f"Hour {hour} should be MORNING"
            )

    def test_midday_hours(self) -> None:
        """Hours 12-13 → MIDDAY."""
        for hour in range(12, 14):
            assert compute_time_phase(hour) == TimePhase.MIDDAY, (
                f"Hour {hour} should be MIDDAY"
            )

    def test_afternoon_hours(self) -> None:
        """Hours 14-16 → AFTERNOON."""
        for hour in range(14, 17):
            assert compute_time_phase(hour) == TimePhase.AFTERNOON, (
                f"Hour {hour} should be AFTERNOON"
            )

    def test_evening_hours(self) -> None:
        """Hours 17-20 → EVENING."""
        for hour in range(17, 21):
            assert compute_time_phase(hour) == TimePhase.EVENING, (
                f"Hour {hour} should be EVENING"
            )

    def test_late_night_hours(self) -> None:
        """Hours 21-23 → LATE_NIGHT."""
        for hour in range(21, 24):
            assert compute_time_phase(hour) == TimePhase.LATE_NIGHT, (
                f"Hour {hour} should be LATE_NIGHT"
            )

    def test_all_24_hours_covered(self) -> None:
        """Every hour from 0 to 23 maps to a valid TimePhase (no gaps)."""
        for hour in range(24):
            result = compute_time_phase(hour)
            assert isinstance(result, TimePhase), (
                f"Hour {hour} returned {result!r}, expected a TimePhase enum"
            )

    def test_invalid_hour_negative(self) -> None:
        """Negative hour raises ValueError."""
        try:
            compute_time_phase(-1)
            assert False, "Expected ValueError for hour=-1"
        except ValueError:
            pass

    def test_invalid_hour_24(self) -> None:
        """Hour 24 raises ValueError."""
        try:
            compute_time_phase(24)
            assert False, "Expected ValueError for hour=24"
        except ValueError:
            pass

    def test_boundary_hour_4_to_5(self) -> None:
        """Hour 4 is DEEP_NIGHT, hour 5 is EARLY_MORNING — boundary check."""
        assert compute_time_phase(4) == TimePhase.DEEP_NIGHT
        assert compute_time_phase(5) == TimePhase.EARLY_MORNING

    def test_boundary_hour_20_to_21(self) -> None:
        """Hour 20 is EVENING, hour 21 is LATE_NIGHT — boundary check."""
        assert compute_time_phase(20) == TimePhase.EVENING
        assert compute_time_phase(21) == TimePhase.LATE_NIGHT


# ===========================================================================
# TMEGenerator Session Tests
# ===========================================================================

class TestTMEGeneratorSession:
    """Test session lifecycle: start_session, generate, message counting."""

    def test_start_session_returns_id(self) -> None:
        """start_session() returns the provided session_id."""
        gen = TMEGenerator(chronicle=None)
        sid = gen.start_session("test-session-123")

        assert sid == "test-session-123"

    def test_start_session_auto_generates_id(self) -> None:
        """start_session() without id auto-generates a UUID."""
        gen = TMEGenerator(chronicle=None)
        sid = gen.start_session()

        assert sid is not None
        assert len(sid) > 0
        # UUID format: 8-4-4-4-12 hex digits
        assert sid.count("-") == 4

    def test_generate_requires_session(self) -> None:
        """generate() raises RuntimeError if no session is active."""
        gen = TMEGenerator(chronicle=None)
        try:
            gen.generate("user")
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "start_session" in str(e)

    def test_first_message_index_is_zero(self) -> None:
        """First message in session has msg_index_in_session = 0."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")

        assert tme.msg_index_in_session == 0

    def test_message_index_increments(self) -> None:
        """Message index increments with each generate() call."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")

        tme0 = gen.generate("user")
        tme1 = gen.generate("companion")
        tme2 = gen.generate("user")

        assert tme0.msg_index_in_session == 0
        assert tme1.msg_index_in_session == 1
        assert tme2.msg_index_in_session == 2

    def test_session_id_in_tme(self) -> None:
        """TME contains the correct session_id."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("my-session")
        tme = gen.generate("user")

        assert tme.session_id == "my-session"

    def test_session_duration_increases(self) -> None:
        """Session duration increases between messages."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme0 = gen.generate("user")

        # Wait a tiny bit to ensure clock progresses
        time.sleep(0.05)

        tme1 = gen.generate("user")

        assert tme1.session_duration_sec >= tme0.session_duration_sec


# ===========================================================================
# Intra-Message Timing Tests
# ===========================================================================

class TestTMEIntraMessageTiming:
    """Test timing between messages within a session."""

    def test_first_message_has_none_timing(self) -> None:
        """First message: time_since_last_msg_sec is None."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")

        assert tme.time_since_last_msg_sec is None
        assert tme.time_since_last_user_msg_sec is None
        assert tme.time_since_last_gwen_msg_sec is None

    def test_second_message_has_timing(self) -> None:
        """Second message: time_since_last_msg_sec is a positive float."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        gen.generate("user")

        time.sleep(0.05)  # 50ms gap

        tme = gen.generate("user")

        assert tme.time_since_last_msg_sec is not None
        assert tme.time_since_last_msg_sec > 0.0
        assert tme.time_since_last_user_msg_sec is not None
        assert tme.time_since_last_user_msg_sec > 0.0

    def test_companion_message_after_user(self) -> None:
        """Companion message after user: time_since_last_user is set, since_last_gwen is None."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        gen.generate("user")

        time.sleep(0.05)

        tme = gen.generate("companion")

        assert tme.time_since_last_msg_sec is not None
        assert tme.time_since_last_user_msg_sec is not None
        # No companion message has been sent before this one
        assert tme.time_since_last_gwen_msg_sec is None

    def test_user_message_after_companion(self) -> None:
        """User message after companion: both user and companion timings set."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        gen.generate("user")        # msg 0: user

        time.sleep(0.05)

        gen.generate("companion")    # msg 1: companion

        time.sleep(0.05)

        tme = gen.generate("user")   # msg 2: user

        assert tme.time_since_last_msg_sec is not None
        assert tme.time_since_last_user_msg_sec is not None
        assert tme.time_since_last_gwen_msg_sec is not None

    def test_user_message_density_count(self) -> None:
        """User message density counts reflect messages sent."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")

        # Send 3 user messages rapidly
        gen.generate("user")
        gen.generate("user")
        tme = gen.generate("user")

        # The third message should see 2 previous user messages in the last 5min
        # (the count does NOT include the current message being generated,
        # because state is updated AFTER computing the TME)
        assert tme.user_msgs_last_5min == 2
        assert tme.user_msgs_last_hour == 2
        assert tme.user_msgs_last_24hr == 2


# ===========================================================================
# Weekend Detection Tests
# ===========================================================================

class TestTMEWeekendDetection:
    """Test is_weekend field in the TME."""

    def test_tme_has_is_weekend_field(self) -> None:
        """TME has an is_weekend boolean field."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")

        assert isinstance(tme.is_weekend, bool)

    def test_weekend_day_names(self) -> None:
        """Saturday and Sunday are the only weekend days."""
        # We can't control datetime.now(), but we can verify the logic
        # by checking that the TME's is_weekend matches the day_of_week
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")

        if tme.day_of_week in ("Saturday", "Sunday"):
            assert tme.is_weekend is True
        else:
            assert tme.is_weekend is False


# ===========================================================================
# Inter-Session Timing Tests (with mock Chronicle)
# ===========================================================================

class TestTMEInterSessionTiming:
    """Test inter-session fields when Chronicle is available vs. None."""

    def test_no_chronicle_defaults(self) -> None:
        """When chronicle is None, inter-session fields use safe defaults."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")

        assert tme.last_session_end is None
        assert tme.hours_since_last_session is None
        assert tme.sessions_last_7_days == 0
        assert tme.sessions_last_30_days == 0
        assert tme.avg_session_gap_30d_hours is None

    def test_with_mock_chronicle(self) -> None:
        """When chronicle provides data, inter-session fields are computed."""
        mock_chronicle = MagicMock()

        # Last session ended 2 hours ago
        two_hours_ago = datetime.now() - timedelta(hours=2)
        mock_chronicle.get_last_session_end.return_value = two_hours_ago
        mock_chronicle.count_sessions_since.return_value = 5

        # 3 sessions in last 30 days with known start times
        t1 = datetime.now() - timedelta(days=3)
        t2 = datetime.now() - timedelta(days=2)
        t3 = datetime.now() - timedelta(days=1)
        mock_chronicle.get_session_start_times_since.return_value = [t1, t2, t3]

        gen = TMEGenerator(chronicle=mock_chronicle)
        gen.start_session("s1")
        tme = gen.generate("user")

        assert tme.last_session_end is not None
        assert tme.hours_since_last_session is not None
        assert tme.hours_since_last_session > 1.0  # Should be ~2 hours
        assert tme.sessions_last_7_days == 5
        assert tme.sessions_last_30_days == 5
        assert tme.avg_session_gap_30d_hours is not None
        assert tme.avg_session_gap_30d_hours > 0.0


# ===========================================================================
# Circadian Deviation Tests
# ===========================================================================

class TestTMECircadianDeviation:
    """Test circadian deviation defaults."""

    def test_default_circadian_deviation_is_none(self) -> None:
        """Circadian deviation defaults to NONE (no baseline data yet)."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")

        assert tme.circadian_deviation_severity == CircadianDeviationSeverity.NONE
        assert tme.circadian_deviation_type is None


# ===========================================================================
# TME Field Completeness Tests
# ===========================================================================

class TestTMEFieldCompleteness:
    """Verify that all TME fields are present and have correct types."""

    def test_all_fields_present(self) -> None:
        """A generated TME has all required fields with correct types."""
        gen = TMEGenerator(chronicle=None)
        gen.start_session("s1")
        tme = gen.generate("user")

        # Absolute time
        assert isinstance(tme.timestamp_utc, datetime)
        assert isinstance(tme.local_time, datetime)

        # Clock position
        assert isinstance(tme.hour_of_day, int)
        assert 0 <= tme.hour_of_day <= 23
        assert isinstance(tme.day_of_week, str)
        assert tme.day_of_week in (
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        )
        assert isinstance(tme.day_of_month, int)
        assert 1 <= tme.day_of_month <= 31
        assert isinstance(tme.month, int)
        assert 1 <= tme.month <= 12
        assert isinstance(tme.year, int)
        assert isinstance(tme.is_weekend, bool)
        assert isinstance(tme.time_phase, TimePhase)

        # Session context
        assert isinstance(tme.session_id, str)
        assert isinstance(tme.session_start, datetime)
        assert isinstance(tme.session_duration_sec, int)
        assert tme.session_duration_sec >= 0
        assert isinstance(tme.msg_index_in_session, int)
        assert tme.msg_index_in_session >= 0

        # Intra-message timing (first message: all None/0)
        assert tme.time_since_last_msg_sec is None
        assert tme.time_since_last_user_msg_sec is None
        assert tme.time_since_last_gwen_msg_sec is None
        assert isinstance(tme.user_msgs_last_5min, int)
        assert isinstance(tme.user_msgs_last_hour, int)
        assert isinstance(tme.user_msgs_last_24hr, int)

        # Inter-session timing (no chronicle: all None/0)
        # (already tested in TestTMEInterSessionTiming)

        # Circadian deviation
        assert isinstance(tme.circadian_deviation_severity, CircadianDeviationSeverity)


# ===========================================================================
# Session Reset Tests
# ===========================================================================

class TestTMESessionReset:
    """Test that start_session() correctly resets all state."""

    def test_new_session_resets_message_index(self) -> None:
        """Starting a new session resets msg_index to 0."""
        gen = TMEGenerator(chronicle=None)

        gen.start_session("s1")
        gen.generate("user")
        gen.generate("user")  # msg_index should be 1

        gen.start_session("s2")
        tme = gen.generate("user")

        assert tme.msg_index_in_session == 0

    def test_new_session_resets_timing(self) -> None:
        """Starting a new session resets time_since_last_msg to None."""
        gen = TMEGenerator(chronicle=None)

        gen.start_session("s1")
        gen.generate("user")
        gen.generate("user")  # time_since_last_msg should be set

        gen.start_session("s2")
        tme = gen.generate("user")

        assert tme.time_since_last_msg_sec is None

    def test_new_session_resets_density_counters(self) -> None:
        """Starting a new session resets user message density counters."""
        gen = TMEGenerator(chronicle=None)

        gen.start_session("s1")
        gen.generate("user")
        gen.generate("user")
        gen.generate("user")  # 2 previous user messages

        gen.start_session("s2")
        tme = gen.generate("user")

        assert tme.user_msgs_last_5min == 0
```

---

### Step 3.2: Run pytest

Run this command from the project root (`C:\Users\Administrator\Desktop\projects\Gwen\`):

- [x]Run `pytest tests/test_tme.py -v` and confirm all tests pass

```bash
pytest tests/test_tme.py -v
```

**Expected output:** All tests pass (green). If any test fails:
- **Import errors:** Make sure Track 002 (data models) is complete and `gwen.models.temporal` exports `TemporalMetadataEnvelope`, `TimePhase`, and `CircadianDeviationSeverity`.
- **Timing flakiness:** Tests that use `time.sleep(0.05)` may be flaky on very slow systems. If a timing assertion fails, increase the sleep to `0.1` seconds.
- **Weekend tests:** The `test_weekend_day_names` test depends on the current day. It is written to pass any day of the week by checking the TME's own `day_of_week` field.

---

## Summary of Files Created

| Step | File Path | Purpose |
|------|-----------|---------|
| 1.1 | `gwen/temporal/__init__.py` | Package init (may already exist from Track 001) |
| 1.2, 2.1-2.5 | `gwen/temporal/tme.py` | compute_time_phase() + TMEGenerator class |
| 3.1 | `tests/test_tme.py` | TME tests (phase mapping, session, timing, weekend) |

**Total files:** 3 (1 package init, 1 implementation, 1 test)
**Dependencies:** Track 002 (data models), Track 003 (Chronicle — optional, gracefully degraded)
