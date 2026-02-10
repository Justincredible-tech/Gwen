# Plan: Temporal Intelligence & Autonomy Engine

**Track:** 020-temporal-and-autonomy
**Spec:** [spec.md](./spec.md)
**Depends on:** 006-tme-generator (TemporalMetadataEnvelope, TimePhase), 007-session-manager (SessionManager, SessionRecord), 016-semantic-map (SemanticMap), 017-emotional-memory (PulseManager, BondManager), 003-database-layer (Chronicle)
**Produces:** gwen/temporal/circadian.py, gwen/temporal/rhythm.py, gwen/autonomy/__init__.py, gwen/autonomy/triggers.py, gwen/autonomy/decision.py, gwen/consolidation/standard.py, gwen/consolidation/deep.py, tests/test_circadian.py, tests/test_autonomy.py
**Status:** Not Started

---

## Phase 1: Circadian Deviation Detector

### Step 1.1: Create gwen/temporal/circadian.py

Create the file `gwen/temporal/circadian.py`. If the `gwen/temporal/` directory does not exist, create it along with a `gwen/temporal/__init__.py`.

- [ ] Create gwen/temporal/__init__.py (if it does not exist)
- [ ] Write CircadianDeviationDetector to gwen/temporal/circadian.py

**File: `gwen/temporal/__init__.py`** (create only if it does not exist)

```python
"""Temporal Cognition System — circadian awareness and rhythm tracking."""
```

**File: `gwen/temporal/circadian.py`** (complete content)

```python
"""Circadian Deviation Detector — flags unusual activity hours.

Compares the user's current activity time against a 30-day rolling
baseline of per-hour message counts.  High deviation (e.g., the user
is messaging at 3am when they have never been active at that hour)
triggers increased attention from the safety and emotional systems.

Reference: SRS.md Section 7
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from gwen.models.temporal import CircadianDeviationSeverity

logger = logging.getLogger(__name__)


class CircadianDeviationDetector:
    """Detects when the user is active at unusual hours.

    The detector queries the Chronicle database for the last 30 days
    of messages and builds a per-hour activity histogram.  It then
    compares the current hour against this baseline to determine the
    deviation severity.

    Usage
    -----
    >>> detector = CircadianDeviationDetector(db_path="~/.gwen/data/chronicle.db")
    >>> baseline = detector.compute_baseline(days=30)
    >>> severity = detector.compute_deviation(current_hour=3)
    >>> print(severity)  # CircadianDeviationSeverity.HIGH
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialise the detector.

        Parameters
        ----------
        db_path : str | Path
            Path to the Chronicle SQLite database.  The ``messages``
            table must exist (created by track 003).
        """
        self.db_path = Path(db_path).expanduser()
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def compute_baseline(self, days: int = 30) -> dict[int, int]:
        """Build a per-hour activity histogram from the last N days.

        Queries the ``messages`` table for all messages with timestamps
        in the last ``days`` days, extracts the hour from each timestamp,
        and counts messages per hour.

        Parameters
        ----------
        days : int
            Number of days to look back.  Defaults to 30.

        Returns
        -------
        dict[int, int]
            A mapping of ``{hour_of_day: message_count}``.
            Hours with zero messages are NOT included.
            Hours are integers from 0 to 23.

        Example
        -------
        >>> baseline = detector.compute_baseline(30)
        >>> print(baseline)
        {8: 45, 9: 62, 10: 55, 14: 30, 15: 28, 20: 40, 21: 35}
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()

        cursor = self.conn.execute(
            "SELECT timestamp FROM messages WHERE timestamp >= ?",
            (cutoff_iso,),
        )
        rows = cursor.fetchall()

        hour_counts: dict[int, int] = {}
        for row in rows:
            try:
                ts = datetime.fromisoformat(row["timestamp"])
                hour = ts.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
            except (ValueError, TypeError):
                # Skip rows with invalid timestamps
                continue

        return hour_counts

    def compute_deviation(
        self, current_hour: int, days: int = 30
    ) -> CircadianDeviationSeverity:
        """Compute the circadian deviation severity for the current hour.

        Parameters
        ----------
        current_hour : int
            The current hour of the day (0-23).
        days : int
            Number of days to use for the baseline.  Defaults to 30.

        Returns
        -------
        CircadianDeviationSeverity
            The severity of the deviation:
            - NONE: Normal activity time (20+ messages at this hour in baseline)
            - LOW: Slightly unusual (10-19 messages at this hour)
            - MEDIUM: Notably outside pattern (3-9 messages at this hour)
            - HIGH: Significantly anomalous (0-2 messages at this hour)

        Notes
        -----
        If there is not enough data to compute a meaningful baseline
        (fewer than 100 total messages in the baseline period), this
        method returns NONE to avoid false positives during early use.

        The thresholds are calibrated for a 30-day window.  A user who
        messages 3-5 times per day would accumulate roughly 100-150
        messages in 30 days.  The per-hour thresholds assume this
        density:
        - 20+ messages at an hour = very normal (they are frequently
          active here)
        - 10-19 = somewhat normal (active sometimes)
        - 3-9 = rare (they are occasionally active here)
        - 0-2 = almost never active here
        """
        baseline = self.compute_baseline(days)

        # Check for sufficient data
        total_messages = sum(baseline.values())
        if total_messages < 100:
            logger.debug(
                "Not enough data for circadian baseline "
                "(%d messages, need 100). Returning NONE.",
                total_messages,
            )
            return CircadianDeviationSeverity.NONE

        count_at_hour = baseline.get(current_hour, 0)

        if count_at_hour >= 20:
            return CircadianDeviationSeverity.NONE
        elif count_at_hour >= 10:
            return CircadianDeviationSeverity.LOW
        elif count_at_hour >= 3:
            return CircadianDeviationSeverity.MEDIUM
        else:
            return CircadianDeviationSeverity.HIGH

    def get_peak_hours(self, days: int = 30, top_n: int = 3) -> list[int]:
        """Return the top N most active hours in the baseline.

        Parameters
        ----------
        days : int
            Number of days to use for the baseline.
        top_n : int
            Number of top hours to return.

        Returns
        -------
        list[int]
            The ``top_n`` hours with the most messages, sorted by
            count descending.  Returns fewer if there are fewer
            active hours.
        """
        baseline = self.compute_baseline(days)
        sorted_hours = sorted(
            baseline.items(), key=lambda x: x[1], reverse=True
        )
        return [hour for hour, count in sorted_hours[:top_n]]
```

---

## Phase 2: Conversation Rhythm Tracker

### Step 2.1: Create gwen/temporal/rhythm.py

Create the file `gwen/temporal/rhythm.py` with the `RhythmTracker` class.

- [ ] Write RhythmTracker class to gwen/temporal/rhythm.py

**File: `gwen/temporal/rhythm.py`** (complete content)

```python
"""Conversation Rhythm Tracker — monitors message density and latency.

Tracks message timestamps within a single session and detects anomalies
such as sudden pauses (user stopped replying for much longer than usual)
and acceleration (user is typing much faster than usual, possibly
indicating agitation).

Reference: SRS.md Section 7
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class RhythmTracker:
    """Tracks conversation rhythm within a single session.

    Feed message timestamps into the tracker as they arrive.  The tracker
    computes density (messages per time window), average latency (time
    between messages), and detects anomalies.

    Usage
    -----
    >>> tracker = RhythmTracker()
    >>> tracker.add_message(datetime.now(timezone.utc))
    >>> tracker.add_message(datetime.now(timezone.utc))
    >>> density = tracker.get_density(window_seconds=300)
    >>> anomaly = tracker.detect_anomaly()
    """

    def __init__(self) -> None:
        """Initialise the tracker with an empty timestamp list."""
        self._timestamps: list[datetime] = []

    def add_message(self, timestamp: datetime) -> None:
        """Record a new message timestamp.

        Parameters
        ----------
        timestamp : datetime
            The UTC timestamp of the message.  Timestamps should be
            added in chronological order, but the tracker does not
            enforce this.
        """
        self._timestamps.append(timestamp)

    @property
    def message_count(self) -> int:
        """Total number of messages tracked so far."""
        return len(self._timestamps)

    def get_density(self, window_seconds: int = 300) -> float:
        """Compute message density: messages in the last N seconds.

        Parameters
        ----------
        window_seconds : int
            The time window to look back, in seconds.  Defaults to
            300 (5 minutes).

        Returns
        -------
        float
            The number of messages whose timestamp falls within the
            last ``window_seconds`` seconds from the most recent
            message.  Returns 0.0 if no messages are tracked.
        """
        if not self._timestamps:
            return 0.0

        latest = self._timestamps[-1]
        cutoff = latest.timestamp() - window_seconds
        count = sum(
            1 for ts in self._timestamps
            if ts.timestamp() >= cutoff
        )
        return float(count)

    def get_avg_latency(self) -> float:
        """Compute the average time between consecutive messages.

        Returns
        -------
        float
            Average gap in seconds between consecutive messages.
            Returns 0.0 if fewer than 2 messages are tracked.
        """
        if len(self._timestamps) < 2:
            return 0.0

        gaps: list[float] = []
        for i in range(1, len(self._timestamps)):
            delta = (
                self._timestamps[i] - self._timestamps[i - 1]
            ).total_seconds()
            gaps.append(abs(delta))

        return sum(gaps) / len(gaps)

    def get_last_latency(self) -> float:
        """Return the time gap between the last two messages.

        Returns
        -------
        float
            Gap in seconds between the last two messages.
            Returns 0.0 if fewer than 2 messages are tracked.
        """
        if len(self._timestamps) < 2:
            return 0.0
        return abs(
            (self._timestamps[-1] - self._timestamps[-2]).total_seconds()
        )

    def detect_anomaly(self) -> Optional[str]:
        """Detect rhythm anomalies in the conversation.

        Anomaly detection rules
        -----------------------
        1. **sudden_pause**: The last latency is > 3x the average latency.
           This suggests the user abruptly stopped replying.
        2. **acceleration**: The message density in the last 5 minutes is
           more than 2x the overall average density.  This suggests the
           user is typing rapidly, possibly indicating agitation.

        Returns
        -------
        str | None
            ``"sudden_pause"`` or ``"acceleration"`` if an anomaly is
            detected.  ``None`` if the rhythm is normal.

        Notes
        -----
        Requires at least 5 messages to compute meaningful averages.
        Returns None if fewer than 5 messages are tracked.
        """
        if len(self._timestamps) < 5:
            return None

        avg_latency = self.get_avg_latency()
        last_latency = self.get_last_latency()

        # Rule 1: Sudden pause
        if avg_latency > 0 and last_latency > 3.0 * avg_latency:
            logger.info(
                "Rhythm anomaly: sudden_pause (last=%.1fs, avg=%.1fs)",
                last_latency, avg_latency,
            )
            return "sudden_pause"

        # Rule 2: Acceleration
        # Compare density in last 5 minutes to overall density
        if len(self._timestamps) >= 2:
            total_duration = (
                self._timestamps[-1] - self._timestamps[0]
            ).total_seconds()
            if total_duration > 0:
                overall_density_per_5min = (
                    len(self._timestamps) / total_duration
                ) * 300
                recent_density = self.get_density(window_seconds=300)
                if (
                    overall_density_per_5min > 0
                    and recent_density > 2.0 * overall_density_per_5min
                ):
                    logger.info(
                        "Rhythm anomaly: acceleration "
                        "(recent_density=%.1f, overall=%.1f per 5min)",
                        recent_density, overall_density_per_5min,
                    )
                    return "acceleration"

        return None

    def reset(self) -> None:
        """Clear all tracked timestamps.  Use when starting a new session."""
        self._timestamps.clear()
```

---

## Phase 3: Autonomy Engine

### Step 3.1: Create gwen/autonomy/__init__.py

Create the file `gwen/autonomy/__init__.py`.

- [ ] Write gwen/autonomy/__init__.py

**File: `gwen/autonomy/__init__.py`**

```python
"""Autonomy Engine — background trigger evaluation and proactive outreach.

The Autonomy Engine determines when the companion should initiate
contact based on temporal patterns, emotional signals, and relational
state.  It answers the question: 'Should I speak?'

Reference: SRS.md Section 12
"""
```

---

### Step 3.2: Create gwen/autonomy/triggers.py with TriggerEvaluator

Create the file `gwen/autonomy/triggers.py` with the `TriggerEvaluator` class.

- [ ] Write TriggerEvaluator class to gwen/autonomy/triggers.py

**File: `gwen/autonomy/triggers.py`** (complete content)

```python
"""Trigger evaluation — determines what conditions warrant proactive outreach.

The TriggerEvaluator scans multiple signal sources (time, patterns,
emotional state, safety) and produces a list of trigger dicts describing
what was detected and how urgent it is.

Reference: SRS.md Section 12
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from gwen.models.temporal import CircadianDeviationSeverity

logger = logging.getLogger(__name__)


class TriggerEvaluator:
    """Evaluates trigger conditions for proactive companion outreach.

    The evaluator checks five categories of triggers:
    1. Time-based: morning greeting window, evening check-in window
    2. Pattern-based: user typically messages at this time but has not
    3. Emotional: last session ended with low valence
    4. Safety: wellness checkpoint is due
    5. Goal-based: user has a goal with a deadline approaching

    Each trigger includes a type, urgency level, and description.

    Usage
    -----
    >>> evaluator = TriggerEvaluator()
    >>> triggers = evaluator.evaluate_triggers(
    ...     current_time=datetime.now(timezone.utc),
    ...     last_session_end=some_datetime,
    ...     last_session_closing_valence=0.2,
    ...     hours_since_last_session=18.0,
    ...     user_typical_active_hours=[8, 9, 10, 14, 15, 20, 21],
    ...     user_messaged_today=False,
    ...     wellness_checkpoint_due=False,
    ...     cumulative_immersion_hours=0.0,
    ... )
    >>> for t in triggers:
    ...     print(t["type"], t["urgency"], t["description"])
    """

    # Morning greeting window: 7:00 - 9:59 local time
    MORNING_WINDOW_START: int = 7
    MORNING_WINDOW_END: int = 10

    # Evening check-in window: 19:00 - 21:59 local time
    EVENING_WINDOW_START: int = 19
    EVENING_WINDOW_END: int = 22

    # Valence threshold: if last session ended below this, emotional trigger fires
    LOW_VALENCE_THRESHOLD: float = 0.3

    # Hours threshold: if it has been longer than this, pattern trigger fires
    LONG_ABSENCE_HOURS: float = 48.0

    # Wellness checkpoint: after this many cumulative immersion hours
    WELLNESS_CHECKPOINT_HOURS: float = 48.0

    def evaluate_triggers(
        self,
        current_time: datetime,
        last_session_end: Optional[datetime] = None,
        last_session_closing_valence: Optional[float] = None,
        hours_since_last_session: Optional[float] = None,
        user_typical_active_hours: Optional[list[int]] = None,
        user_messaged_today: bool = False,
        wellness_checkpoint_due: bool = False,
        cumulative_immersion_hours: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Evaluate all trigger conditions and return a list of active triggers.

        Parameters
        ----------
        current_time : datetime
            The current UTC time.
        last_session_end : datetime | None
            When the last session ended.  None if no sessions exist yet.
        last_session_closing_valence : float | None
            The valence of the user's emotional state at the end of
            the last session.  None if no sessions exist yet.
        hours_since_last_session : float | None
            How many hours since the last session ended.
        user_typical_active_hours : list[int] | None
            The hours (0-23) when the user is typically active.
        user_messaged_today : bool
            Whether the user has sent any messages today.
        wellness_checkpoint_due : bool
            Whether a wellness checkpoint is overdue.
        cumulative_immersion_hours : float
            Total hours spent in immersion mode since last checkpoint.

        Returns
        -------
        list[dict[str, Any]]
            Each dict has keys:
            - ``type`` (str): "time_based", "pattern_based", "emotional",
              "safety", or "goal_based"
            - ``urgency`` (str): "low", "medium", or "high"
            - ``description`` (str): Human-readable description of the
              trigger condition
        """
        triggers: list[dict[str, Any]] = []

        current_hour = current_time.hour

        # ---- 1. Time-based triggers ----

        # Morning greeting
        if (
            self.MORNING_WINDOW_START <= current_hour < self.MORNING_WINDOW_END
            and not user_messaged_today
        ):
            triggers.append({
                "type": "time_based",
                "urgency": "low",
                "description": (
                    f"Morning greeting window ({self.MORNING_WINDOW_START}:00-"
                    f"{self.MORNING_WINDOW_END}:00) and user has not "
                    f"messaged today."
                ),
            })

        # Evening check-in
        if (
            self.EVENING_WINDOW_START <= current_hour < self.EVENING_WINDOW_END
            and not user_messaged_today
        ):
            triggers.append({
                "type": "time_based",
                "urgency": "low",
                "description": (
                    f"Evening check-in window ({self.EVENING_WINDOW_START}:00-"
                    f"{self.EVENING_WINDOW_END}:00) and user has not "
                    f"messaged today."
                ),
            })

        # ---- 2. Pattern-based triggers ----

        if user_typical_active_hours and not user_messaged_today:
            if current_hour in user_typical_active_hours:
                triggers.append({
                    "type": "pattern_based",
                    "urgency": "medium",
                    "description": (
                        f"User is typically active at hour {current_hour} "
                        f"but has not messaged today."
                    ),
                })

        # Long absence
        if (
            hours_since_last_session is not None
            and hours_since_last_session > self.LONG_ABSENCE_HOURS
        ):
            triggers.append({
                "type": "pattern_based",
                "urgency": "medium",
                "description": (
                    f"User has been absent for "
                    f"{hours_since_last_session:.1f} hours "
                    f"(threshold: {self.LONG_ABSENCE_HOURS:.0f} hours)."
                ),
            })

        # ---- 3. Emotional triggers ----

        if (
            last_session_closing_valence is not None
            and last_session_closing_valence < self.LOW_VALENCE_THRESHOLD
        ):
            triggers.append({
                "type": "emotional",
                "urgency": "high",
                "description": (
                    f"Last session ended with low valence "
                    f"({last_session_closing_valence:.2f} < "
                    f"{self.LOW_VALENCE_THRESHOLD:.2f}). "
                    f"User may still be struggling."
                ),
            })

        # ---- 4. Safety triggers ----

        if wellness_checkpoint_due:
            triggers.append({
                "type": "safety",
                "urgency": "high",
                "description": (
                    "Wellness checkpoint is due (48-hour immersion "
                    "threshold reached)."
                ),
            })

        if cumulative_immersion_hours >= self.WELLNESS_CHECKPOINT_HOURS:
            if not wellness_checkpoint_due:
                triggers.append({
                    "type": "safety",
                    "urgency": "high",
                    "description": (
                        f"Cumulative immersion time "
                        f"({cumulative_immersion_hours:.1f} hours) has "
                        f"reached the wellness checkpoint threshold "
                        f"({self.WELLNESS_CHECKPOINT_HOURS:.0f} hours)."
                    ),
                })

        return triggers
```

---

### Step 3.3: Create gwen/autonomy/decision.py with ShouldISpeakDecision

Create the file `gwen/autonomy/decision.py` with the `ShouldISpeakDecision` class.

- [ ] Write ShouldISpeakDecision class to gwen/autonomy/decision.py

**File: `gwen/autonomy/decision.py`** (complete content)

```python
"""'Should I speak?' decision model — determines when to initiate contact.

Takes the list of active triggers from the TriggerEvaluator and applies
relational and temporal filters to decide whether the companion should
actually reach out.

Reference: SRS.md Section 12
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ShouldISpeakDecision:
    """Decides whether the companion should initiate contact.

    The decision model balances trigger urgency against relational
    readiness and temporal appropriateness (quiet hours).

    Decision logic
    --------------
    1. If there are no triggers: NO (nothing to say)
    2. If any trigger is type "safety": YES (override everything)
    3. If current time is in quiet hours: NO (unless safety)
    4. If bond warmth < 0.3: NO (too early in relationship)
    5. If any trigger has urgency "high": YES
    6. If bond warmth > 0.5: YES (relationship is warm enough)
    7. Otherwise: NO

    Usage
    -----
    >>> decision = ShouldISpeakDecision()
    >>> should_speak = decision.decide(
    ...     triggers=[{"type": "emotional", "urgency": "high", ...}],
    ...     bond_warmth=0.6,
    ...     current_time=datetime.now(timezone.utc),
    ...     quiet_hours_start=23,
    ...     quiet_hours_end=7,
    ... )
    >>> print(should_speak)  # True
    """

    def decide(
        self,
        triggers: list[dict[str, Any]],
        bond_warmth: float,
        current_time: datetime,
        quiet_hours_start: int = 23,
        quiet_hours_end: int = 7,
    ) -> bool:
        """Determine whether the companion should initiate contact.

        Parameters
        ----------
        triggers : list[dict[str, Any]]
            The list of active triggers from TriggerEvaluator.
            Each dict has keys ``type``, ``urgency``, ``description``.
        bond_warmth : float
            The current warmth dimension of the RelationalField (0.0-1.0).
            Represents how warm the relationship is.
        current_time : datetime
            The current UTC time.
        quiet_hours_start : int
            Hour when quiet hours begin (default 23 = 11pm).
            During quiet hours, the companion does not initiate contact
            unless there is a safety trigger.
        quiet_hours_end : int
            Hour when quiet hours end (default 7 = 7am).

        Returns
        -------
        bool
            True if the companion should initiate contact.
            False if it should remain silent.
        """
        # 1. No triggers → do not speak
        if not triggers:
            logger.debug("No triggers active. Decision: do not speak.")
            return False

        # 2. Safety triggers override everything
        has_safety = any(t["type"] == "safety" for t in triggers)
        if has_safety:
            logger.info(
                "Safety trigger active. Decision: SPEAK (safety override)."
            )
            return True

        # 3. Quiet hours check
        current_hour = current_time.hour
        in_quiet_hours = self._is_in_quiet_hours(
            current_hour, quiet_hours_start, quiet_hours_end
        )
        if in_quiet_hours:
            logger.debug(
                "Currently in quiet hours (%d:00-%d:00). "
                "Decision: do not speak.",
                quiet_hours_start, quiet_hours_end,
            )
            return False

        # 4. Relationship too early
        if bond_warmth < 0.3:
            logger.debug(
                "Bond warmth %.2f < 0.3 (too early in relationship). "
                "Decision: do not speak.",
                bond_warmth,
            )
            return False

        # 5. High-urgency trigger
        has_high = any(t["urgency"] == "high" for t in triggers)
        if has_high:
            logger.info(
                "High-urgency trigger active. Decision: SPEAK."
            )
            return True

        # 6. Warm enough relationship
        if bond_warmth > 0.5:
            logger.info(
                "Bond warmth %.2f > 0.5 with active triggers. "
                "Decision: SPEAK.",
                bond_warmth,
            )
            return True

        # 7. Default: do not speak
        logger.debug(
            "No sufficient conditions met. Decision: do not speak."
        )
        return False

    @staticmethod
    def _is_in_quiet_hours(
        current_hour: int,
        start: int,
        end: int,
    ) -> bool:
        """Check if the current hour falls within quiet hours.

        Handles the case where quiet hours span midnight (e.g., 23:00-07:00).

        Parameters
        ----------
        current_hour : int
            Hour to check (0-23).
        start : int
            Hour when quiet hours begin (0-23).
        end : int
            Hour when quiet hours end (0-23).

        Returns
        -------
        bool
            True if current_hour is within the quiet window.
        """
        if start <= end:
            # Quiet hours do not span midnight (e.g., 01:00-06:00)
            return start <= current_hour < end
        else:
            # Quiet hours span midnight (e.g., 23:00-07:00)
            return current_hour >= start or current_hour < end
```

---

## Phase 4: Standard Consolidation

### Step 4.1: Create gwen/consolidation/standard.py

Create `gwen/consolidation/__init__.py` if it does not exist, then create `gwen/consolidation/standard.py`.

- [ ] Create gwen/consolidation/__init__.py (if it does not exist)
- [ ] Write StandardConsolidation class to gwen/consolidation/standard.py

**File: `gwen/consolidation/__init__.py`** (create only if it does not exist)

```python
"""Memory consolidation pipelines — standard and deep."""
```

**File: `gwen/consolidation/standard.py`** (complete content)

```python
"""Standard consolidation pipeline — runs every 6-12 hours during idle.

Processes recent sessions to extract entities, update emotional baselines,
update relational state, and build trigger map associations.

Reference: SRS.md Section 3.12, FR-MEM-012
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from gwen.models.messages import ConsolidationJob, ConsolidationType, SessionRecord

logger = logging.getLogger(__name__)


class StandardConsolidation:
    """Standard consolidation: extracts entities and updates baselines.

    This pipeline runs every 6-12 hours when the system is idle (no
    active session).  It processes all sessions that have not yet been
    consolidated.

    The pipeline does the following:
    1. For each unprocessed session, retrieve all messages.
    2. Use Tier 2 (or Tier 1 if unavailable) to extract entities
       (people, places, concepts, events) from conversation text.
    3. Add extracted entities to the SemanticMap (knowledge graph).
    4. Update Pulse emotional baselines from session emotional data.
    5. Update Bond relational field from session relational delta.
    6. Update trigger map with new temporal/topic associations.

    Dependencies
    ------------
    - model_manager: AdaptiveModelManager (for entity extraction via LLM)
    - chronicle: Chronicle (for retrieving sessions and messages)
    - semantic_map: SemanticMap (for adding entities and edges)
    - pulse_manager: PulseManager (for baseline updates)
    - bond_manager: BondManager (for relational field updates)

    Usage
    -----
    >>> consolidation = StandardConsolidation(
    ...     model_manager=mgr,
    ...     chronicle=chronicle,
    ...     semantic_map=semantic_map,
    ...     pulse_manager=pulse,
    ...     bond_manager=bond,
    ... )
    >>> job = await consolidation.run(sessions=[session1, session2])
    >>> print(job.map_entities_created)
    """

    # Prompt sent to the LLM for entity extraction
    ENTITY_EXTRACTION_PROMPT = (
        "Extract all entities (people, places, concepts, events, "
        "preferences, goals) from the following conversation. "
        "Return a JSON array of objects with keys: "
        '"name", "entity_type", "detail". '
        "entity_type must be one of: person, place, concept, event, "
        "preference, goal.\n\n"
        "Conversation:\n{conversation_text}\n\n"
        "Respond with ONLY a JSON array. No explanation."
    )

    def __init__(
        self,
        model_manager: Any,
        chronicle: Any,
        semantic_map: Any = None,
        pulse_manager: Any = None,
        bond_manager: Any = None,
    ) -> None:
        """Initialise the consolidation pipeline.

        Parameters
        ----------
        model_manager : AdaptiveModelManager
            Used for LLM-based entity extraction.
        chronicle : Chronicle
            Used for retrieving sessions and messages.
        semantic_map : SemanticMap | None
            Used for adding extracted entities.  If None, entity
            extraction is skipped.
        pulse_manager : PulseManager | None
            Used for updating emotional baselines.  If None, baseline
            updates are skipped.
        bond_manager : BondManager | None
            Used for updating the relational field.  If None, bond
            updates are skipped.
        """
        self.model_manager = model_manager
        self.chronicle = chronicle
        self.semantic_map = semantic_map
        self.pulse_manager = pulse_manager
        self.bond_manager = bond_manager

    async def run(
        self, sessions: list[SessionRecord]
    ) -> ConsolidationJob:
        """Run standard consolidation on a list of sessions.

        Parameters
        ----------
        sessions : list[SessionRecord]
            The sessions to consolidate.  These should be sessions
            that have not yet been processed by consolidation.

        Returns
        -------
        ConsolidationJob
            A record of what was processed and what was produced.
        """
        job = ConsolidationJob(
            id=str(uuid.uuid4()),
            type=ConsolidationType.STANDARD,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            sessions_processed=[s.id for s in sessions],
        )

        for session in sessions:
            try:
                await self._process_session(session, job)
            except Exception as exc:
                error_msg = (
                    f"Error consolidating session {session.id}: {exc}"
                )
                logger.error(error_msg)
                job.errors.append(error_msg)

        job.completed_at = datetime.now(timezone.utc)
        logger.info(
            "Standard consolidation complete: %d sessions processed, "
            "%d entities created, %d entities updated, %d errors",
            len(sessions),
            job.map_entities_created,
            job.map_entities_updated,
            len(job.errors),
        )
        return job

    async def _process_session(
        self, session: SessionRecord, job: ConsolidationJob
    ) -> None:
        """Process a single session for consolidation.

        Parameters
        ----------
        session : SessionRecord
            The session to process.
        job : ConsolidationJob
            The job record to update with results.
        """
        # Step 1: Get all messages for this session
        messages = self.chronicle.get_messages_by_session(session.id)
        if not messages:
            logger.debug(
                "Session %s has no messages. Skipping.", session.id
            )
            return

        # Step 2: Extract entities via LLM
        if self.semantic_map is not None:
            conversation_text = "\n".join(
                f"{m.sender}: {m.content}" for m in messages
            )
            entities_created = await self._extract_and_store_entities(
                conversation_text, session.id, job
            )
            job.map_entities_created += entities_created

        # Step 3: Update emotional baselines
        if self.pulse_manager is not None:
            try:
                # Collect emotional states from messages
                emotional_states = [
                    m.emotional_state for m in messages
                    if m.emotional_state is not None
                ]
                if emotional_states and hasattr(
                    self.pulse_manager, "update_baseline"
                ):
                    self.pulse_manager.update_baseline(emotional_states)
                    job.pulse_baselines_updated = True
            except Exception as exc:
                job.errors.append(
                    f"Baseline update failed for session {session.id}: {exc}"
                )

        # Step 4: Update bond relational field
        if self.bond_manager is not None:
            try:
                if (
                    session.relational_field_delta
                    and hasattr(self.bond_manager, "apply_delta")
                ):
                    self.bond_manager.apply_delta(
                        session.relational_field_delta
                    )
                    job.bond_field_updated = True
            except Exception as exc:
                job.errors.append(
                    f"Bond update failed for session {session.id}: {exc}"
                )

    async def _extract_and_store_entities(
        self,
        conversation_text: str,
        session_id: str,
        job: ConsolidationJob,
    ) -> int:
        """Use the LLM to extract entities from conversation text.

        Parameters
        ----------
        conversation_text : str
            The full conversation text (formatted as "sender: content").
        session_id : str
            The session ID (for linking entities to their source).
        job : ConsolidationJob
            The job record to update with errors.

        Returns
        -------
        int
            The number of entities successfully extracted and stored.
        """
        prompt = self.ENTITY_EXTRACTION_PROMPT.format(
            conversation_text=conversation_text
        )

        try:
            # Try Tier 2 first, fall back to Tier 1
            try:
                raw_response = await self.model_manager.generate(
                    tier=2,
                    prompt=prompt,
                    format="json",
                    options={"temperature": 0.1, "num_predict": 1024},
                )
            except Exception:
                raw_response = await self.model_manager.generate(
                    tier=1,
                    prompt=prompt,
                    format="json",
                    options={"temperature": 0.1, "num_predict": 1024},
                )

            # Parse the response
            entities_data = json.loads(raw_response)
            if not isinstance(entities_data, list):
                entities_data = []

            count = 0
            for entity_dict in entities_data:
                if (
                    isinstance(entity_dict, dict)
                    and "name" in entity_dict
                    and "entity_type" in entity_dict
                ):
                    # Add to semantic map if the method exists
                    if hasattr(self.semantic_map, "add_entity_from_dict"):
                        self.semantic_map.add_entity_from_dict(
                            entity_dict, session_id
                        )
                        count += 1

            return count

        except (json.JSONDecodeError, TypeError) as exc:
            job.errors.append(
                f"Entity extraction JSON parse error: {exc}"
            )
            return 0
        except Exception as exc:
            job.errors.append(
                f"Entity extraction failed: {exc}"
            )
            return 0
```

---

## Phase 5: Deep Consolidation

### Step 5.1: Create gwen/consolidation/deep.py

Create the file `gwen/consolidation/deep.py` with the `DeepConsolidation` class.

- [ ] Write DeepConsolidation class to gwen/consolidation/deep.py

**File: `gwen/consolidation/deep.py`** (complete content)

```python
"""Deep consolidation pipeline — runs weekly or after major events.

Performs advanced pattern analysis across all sessions, detects life
rhythms, identifies anniversaries, and generates anticipatory primes.

Reference: SRS.md Section 3.12, FR-MEM-013
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from gwen.models.messages import ConsolidationJob, ConsolidationType, SessionRecord
from gwen.models.memory import AnticipatoryPrime

logger = logging.getLogger(__name__)


class DeepConsolidation:
    """Deep consolidation: pattern analysis and anticipatory priming.

    This pipeline runs weekly (or after a major emotional event).  It
    builds on top of standard consolidation by:

    1. Running standard consolidation first (ensuring baselines are up
       to date).
    2. Analysing emotional trajectories across all sessions to detect
       recurring patterns (e.g., "user spirals on Sunday nights").
    3. Detecting life rhythms: day-of-week emotional profiles after
       4+ weeks of data.
    4. Detecting anniversaries: dates mentioned with emotional weight
       that might recur.
    5. Generating anticipatory primes: forward-looking predictions
       about what the user might need in upcoming sessions.

    Dependencies
    ------------
    - standard_consolidation: StandardConsolidation (run first)
    - model_manager: AdaptiveModelManager (for pattern analysis via LLM)
    - chronicle: Chronicle (for retrieving session history)
    - semantic_map: SemanticMap (for anniversary date storage)

    Usage
    -----
    >>> deep = DeepConsolidation(
    ...     standard_consolidation=standard,
    ...     model_manager=mgr,
    ...     chronicle=chronicle,
    ...     semantic_map=semantic_map,
    ... )
    >>> job = await deep.run()
    """

    # Prompt for pattern analysis
    PATTERN_ANALYSIS_PROMPT = (
        "Analyse the following emotional trajectory data from the "
        "last 4 weeks.  Identify recurring patterns, triggers, and "
        "rhythms.  Return a JSON object with keys:\n"
        '- "weekly_patterns": list of {day_of_week, typical_mood, notes}\n'
        '- "recurring_triggers": list of {trigger, typical_response, '
        "frequency}\n"
        '- "emotional_trends": overall direction (improving, declining, '
        "stable)\n"
        '- "recommended_primes": list of {prediction, confidence, '
        "suggested_response}\n\n"
        "Data:\n{trajectory_data}\n\n"
        "Respond with ONLY a JSON object. No explanation."
    )

    def __init__(
        self,
        standard_consolidation: Any,
        model_manager: Any,
        chronicle: Any,
        semantic_map: Any = None,
    ) -> None:
        """Initialise the deep consolidation pipeline.

        Parameters
        ----------
        standard_consolidation : StandardConsolidation
            The standard consolidation pipeline (run first).
        model_manager : AdaptiveModelManager
            Used for LLM-based pattern analysis.
        chronicle : Chronicle
            Used for retrieving session history.
        semantic_map : SemanticMap | None
            Used for anniversary detection and storage.
        """
        self.standard_consolidation = standard_consolidation
        self.model_manager = model_manager
        self.chronicle = chronicle
        self.semantic_map = semantic_map

    async def run(
        self,
        unprocessed_sessions: Optional[list[SessionRecord]] = None,
    ) -> ConsolidationJob:
        """Run deep consolidation.

        Parameters
        ----------
        unprocessed_sessions : list[SessionRecord] | None
            Sessions that have not yet been through standard consolidation.
            If provided, standard consolidation runs on them first.
            If None, only deep analysis is performed.

        Returns
        -------
        ConsolidationJob
            A record of what was processed and what was produced.
        """
        job = ConsolidationJob(
            id=str(uuid.uuid4()),
            type=ConsolidationType.DEEP,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
        )

        # Step 1: Run standard consolidation first
        if unprocessed_sessions:
            standard_job = await self.standard_consolidation.run(
                unprocessed_sessions
            )
            job.sessions_processed = standard_job.sessions_processed
            job.map_entities_created = standard_job.map_entities_created
            job.map_entities_updated = standard_job.map_entities_updated
            job.pulse_baselines_updated = standard_job.pulse_baselines_updated
            job.bond_field_updated = standard_job.bond_field_updated
            job.errors.extend(standard_job.errors)

        # Step 2: Analyse patterns across all sessions
        try:
            primes_count = await self._analyse_patterns(job)
            job.anticipatory_primes_generated = primes_count
        except Exception as exc:
            error_msg = f"Pattern analysis failed: {exc}"
            logger.error(error_msg)
            job.errors.append(error_msg)

        # Step 3: Detect anniversaries
        try:
            anniversary_count = await self._detect_anniversaries(job)
            if anniversary_count > 0:
                logger.info(
                    "Detected %d potential anniversaries.", anniversary_count
                )
        except Exception as exc:
            error_msg = f"Anniversary detection failed: {exc}"
            logger.error(error_msg)
            job.errors.append(error_msg)

        job.completed_at = datetime.now(timezone.utc)
        logger.info(
            "Deep consolidation complete: %d primes generated, %d errors",
            job.anticipatory_primes_generated,
            len(job.errors),
        )
        return job

    async def _analyse_patterns(
        self, job: ConsolidationJob
    ) -> int:
        """Analyse emotional patterns across recent sessions.

        Builds a summary of emotional trajectories from the last 4 weeks
        and sends it to the LLM for pattern detection.  Generates
        anticipatory primes from the results.

        Parameters
        ----------
        job : ConsolidationJob
            The job record to update with errors.

        Returns
        -------
        int
            Number of anticipatory primes generated.
        """
        # Build trajectory data from the last 28 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=28)

        # Query sessions from the last 28 days
        # Note: This uses a direct SQL query because Chronicle may not
        # have a get_sessions_since() method yet.
        if hasattr(self.chronicle, "conn"):
            cursor = self.chronicle.conn.execute(
                "SELECT id, start_time, session_type, "
                "closing_emotional_state, topics "
                "FROM sessions WHERE start_time >= ? "
                "ORDER BY start_time ASC",
                (cutoff.isoformat(),),
            )
            rows = cursor.fetchall()
        else:
            return 0

        if len(rows) < 7:
            logger.info(
                "Not enough sessions for pattern analysis "
                "(%d sessions, need 7).",
                len(rows),
            )
            return 0

        # Build the trajectory data summary
        trajectory_entries: list[str] = []
        for row in rows:
            start_time = row["start_time"] if isinstance(row, dict) else row[1]
            try:
                dt = datetime.fromisoformat(str(start_time))
                day_of_week = dt.strftime("%A")
                hour = dt.hour
            except (ValueError, TypeError):
                day_of_week = "Unknown"
                hour = 0

            session_type = row["session_type"] if isinstance(row, dict) else row[2]
            closing_state = row["closing_emotional_state"] if isinstance(row, dict) else row[3]
            topics = row["topics"] if isinstance(row, dict) else row[4]

            trajectory_entries.append(
                f"- {day_of_week} {hour}:00 | type={session_type} | "
                f"closing_state={closing_state} | topics={topics}"
            )

        trajectory_data = "\n".join(trajectory_entries)

        # Send to LLM for analysis
        prompt = self.PATTERN_ANALYSIS_PROMPT.format(
            trajectory_data=trajectory_data
        )

        try:
            raw_response = await self.model_manager.generate(
                tier=2,
                prompt=prompt,
                format="json",
                options={"temperature": 0.2, "num_predict": 2048},
            )
        except Exception:
            raw_response = await self.model_manager.generate(
                tier=1,
                prompt=prompt,
                format="json",
                options={"temperature": 0.2, "num_predict": 2048},
            )

        # Parse the response
        try:
            analysis = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError):
            job.errors.append("Pattern analysis response was not valid JSON.")
            return 0

        # Generate anticipatory primes from recommended_primes
        primes = analysis.get("recommended_primes", [])
        count = 0
        for prime_dict in primes:
            if isinstance(prime_dict, dict) and "prediction" in prime_dict:
                count += 1

        return count

    async def _detect_anniversaries(
        self, job: ConsolidationJob
    ) -> int:
        """Detect dates mentioned in conversations that may be anniversaries.

        Scans messages from the last 90 days for date references with
        high emotional weight.  These dates are candidates for
        anniversary-based anticipatory primes.

        Parameters
        ----------
        job : ConsolidationJob
            The job record to update with errors.

        Returns
        -------
        int
            Number of potential anniversaries detected.
        """
        # This is a simplified version. A full implementation would use
        # NER (named entity recognition) to find date references and
        # cross-reference them with emotional weight.

        if not hasattr(self.chronicle, "conn"):
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        cursor = self.chronicle.conn.execute(
            "SELECT content, valence, arousal, relational_significance "
            "FROM messages "
            "WHERE timestamp >= ? AND relational_significance > 0.7",
            (cutoff.isoformat(),),
        )
        rows = cursor.fetchall()

        # Count high-significance messages as potential anniversary markers
        anniversary_count = 0
        date_keywords = [
            "anniversary", "birthday", "year ago", "last year",
            "this day", "remember when", "it's been a year",
            "died", "passed away", "graduated", "got married",
        ]

        for row in rows:
            content = (
                row["content"] if isinstance(row, dict) else row[0]
            )
            if content and any(
                keyword in content.lower() for keyword in date_keywords
            ):
                anniversary_count += 1

        return anniversary_count
```

---

## Phase 6: Tests

### Step 6.1: Write tests/test_circadian.py

Create the file `tests/test_circadian.py` with the following exact content.

- [ ] Write tests/test_circadian.py

**File: `tests/test_circadian.py`** (complete content)

```python
"""Tests for gwen.temporal.circadian — circadian deviation detection.

Run with:
    pytest tests/test_circadian.py -v
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gwen.temporal.circadian import CircadianDeviationDetector
from gwen.temporal.rhythm import RhythmTracker
from gwen.models.temporal import CircadianDeviationSeverity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Create a temporary database with a messages table."""
    db_path = tmp_path / "test_circadian.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            timestamp TEXT NOT NULL,
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


def _insert_messages_at_hour(
    db_path: Path,
    hour: int,
    count: int,
    days_back: int = 30,
) -> None:
    """Insert ``count`` messages at the given hour spread over recent days.

    Each message gets a unique timestamp at the given hour on consecutive
    days going backwards from today.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database.
    hour : int
        The hour (0-23) to set for each message's timestamp.
    count : int
        Number of messages to insert.
    days_back : int
        Maximum days back to spread the messages.
    """
    conn = sqlite3.connect(str(db_path))
    now = datetime.now(timezone.utc)
    for i in range(count):
        day_offset = i % days_back
        ts = now - timedelta(days=day_offset)
        ts = ts.replace(hour=hour, minute=0, second=0, microsecond=0)
        msg_id = f"msg-h{hour}-{i:04d}"
        conn.execute(
            "INSERT OR IGNORE INTO messages (id, session_id, timestamp, sender, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (msg_id, "session-001", ts.isoformat(), "user", f"Message at {hour}:00"),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tests: CircadianDeviationDetector
# ---------------------------------------------------------------------------

class TestCircadianDeviationDetector:
    """Tests for CircadianDeviationDetector."""

    def test_insufficient_data_returns_none(self, tmp_db: Path) -> None:
        """With fewer than 100 total messages, deviation should be NONE."""
        _insert_messages_at_hour(tmp_db, hour=10, count=50)
        detector = CircadianDeviationDetector(tmp_db)
        severity = detector.compute_deviation(current_hour=3)
        assert severity == CircadianDeviationSeverity.NONE

    def test_high_deviation_at_unused_hour(self, tmp_db: Path) -> None:
        """An hour with 0-2 messages should produce HIGH deviation."""
        # Fill hours 8-17 with messages (total > 100)
        for h in range(8, 18):
            _insert_messages_at_hour(tmp_db, hour=h, count=15)
        # Hour 3 has 0 messages
        detector = CircadianDeviationDetector(tmp_db)
        severity = detector.compute_deviation(current_hour=3)
        assert severity == CircadianDeviationSeverity.HIGH

    def test_medium_deviation_at_rare_hour(self, tmp_db: Path) -> None:
        """An hour with 3-9 messages should produce MEDIUM deviation."""
        # Fill normal hours
        for h in range(8, 18):
            _insert_messages_at_hour(tmp_db, hour=h, count=15)
        # Add 5 messages at hour 3 (rare but not unprecedented)
        _insert_messages_at_hour(tmp_db, hour=3, count=5)

        detector = CircadianDeviationDetector(tmp_db)
        severity = detector.compute_deviation(current_hour=3)
        assert severity == CircadianDeviationSeverity.MEDIUM

    def test_low_deviation_at_occasional_hour(self, tmp_db: Path) -> None:
        """An hour with 10-19 messages should produce LOW deviation."""
        for h in range(8, 18):
            _insert_messages_at_hour(tmp_db, hour=h, count=15)
        _insert_messages_at_hour(tmp_db, hour=3, count=12)

        detector = CircadianDeviationDetector(tmp_db)
        severity = detector.compute_deviation(current_hour=3)
        assert severity == CircadianDeviationSeverity.LOW

    def test_no_deviation_at_normal_hour(self, tmp_db: Path) -> None:
        """An hour with 20+ messages should produce NONE deviation."""
        for h in range(8, 18):
            _insert_messages_at_hour(tmp_db, hour=h, count=25)

        detector = CircadianDeviationDetector(tmp_db)
        severity = detector.compute_deviation(current_hour=10)
        assert severity == CircadianDeviationSeverity.NONE

    def test_compute_baseline_returns_correct_hours(
        self, tmp_db: Path
    ) -> None:
        """compute_baseline should return counts for the correct hours."""
        _insert_messages_at_hour(tmp_db, hour=9, count=30)
        _insert_messages_at_hour(tmp_db, hour=14, count=20)

        detector = CircadianDeviationDetector(tmp_db)
        baseline = detector.compute_baseline(days=30)
        assert 9 in baseline
        assert 14 in baseline
        assert baseline[9] == 30
        assert baseline[14] == 20

    def test_get_peak_hours(self, tmp_db: Path) -> None:
        """get_peak_hours should return the most active hours."""
        _insert_messages_at_hour(tmp_db, hour=9, count=50)
        _insert_messages_at_hour(tmp_db, hour=14, count=30)
        _insert_messages_at_hour(tmp_db, hour=20, count=40)

        detector = CircadianDeviationDetector(tmp_db)
        peaks = detector.get_peak_hours(days=30, top_n=2)
        assert peaks[0] == 9   # Most active
        assert peaks[1] == 20  # Second most active


# ---------------------------------------------------------------------------
# Tests: RhythmTracker
# ---------------------------------------------------------------------------

class TestRhythmTracker:
    """Tests for RhythmTracker."""

    def test_empty_tracker(self) -> None:
        """An empty tracker should return zero for all metrics."""
        tracker = RhythmTracker()
        assert tracker.message_count == 0
        assert tracker.get_density() == 0.0
        assert tracker.get_avg_latency() == 0.0
        assert tracker.get_last_latency() == 0.0
        assert tracker.detect_anomaly() is None

    def test_single_message(self) -> None:
        """A single message should have density 1 and no latency."""
        tracker = RhythmTracker()
        tracker.add_message(datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc))
        assert tracker.message_count == 1
        assert tracker.get_density() == 1.0
        assert tracker.get_avg_latency() == 0.0

    def test_density_within_window(self) -> None:
        """Messages within the window should all be counted."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            tracker.add_message(base + timedelta(seconds=30 * i))
        # All 5 messages are within 300 seconds
        density = tracker.get_density(window_seconds=300)
        assert density == 5.0

    def test_density_outside_window(self) -> None:
        """Messages outside the window should not be counted."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        tracker.add_message(base)  # 10 minutes before the last
        tracker.add_message(base + timedelta(minutes=10))
        # Window is 300 seconds (5 min). Only the last message is in window.
        density = tracker.get_density(window_seconds=300)
        assert density == 1.0

    def test_avg_latency_computation(self) -> None:
        """Average latency should be the mean of all consecutive gaps."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        tracker.add_message(base)
        tracker.add_message(base + timedelta(seconds=10))
        tracker.add_message(base + timedelta(seconds=30))
        # Gaps: 10s, 20s → average = 15s
        assert abs(tracker.get_avg_latency() - 15.0) < 1e-9

    def test_sudden_pause_detection(self) -> None:
        """A long gap after rapid messages should trigger 'sudden_pause'."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        # 5 rapid messages (5 seconds apart)
        for i in range(5):
            tracker.add_message(base + timedelta(seconds=5 * i))
        # Then a 60-second pause (12x the 5-second average)
        tracker.add_message(base + timedelta(seconds=80))
        anomaly = tracker.detect_anomaly()
        assert anomaly == "sudden_pause"

    def test_no_anomaly_with_steady_rhythm(self) -> None:
        """Steady rhythm should produce no anomaly."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        for i in range(10):
            tracker.add_message(base + timedelta(seconds=30 * i))
        anomaly = tracker.detect_anomaly()
        assert anomaly is None

    def test_reset_clears_state(self) -> None:
        """reset() should clear all tracked timestamps."""
        tracker = RhythmTracker()
        base = datetime(2026, 2, 9, 10, 0, 0, tzinfo=timezone.utc)
        tracker.add_message(base)
        tracker.add_message(base + timedelta(seconds=10))
        tracker.reset()
        assert tracker.message_count == 0


# ---------------------------------------------------------------------------
# Tests: Autonomy Engine
# ---------------------------------------------------------------------------

class TestTriggerEvaluator:
    """Tests for TriggerEvaluator."""

    def test_morning_greeting_trigger(self) -> None:
        """Should fire when in morning window and user has not messaged."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 8, 0, 0, tzinfo=timezone.utc),
            user_messaged_today=False,
        )
        time_triggers = [t for t in triggers if t["type"] == "time_based"]
        assert len(time_triggers) >= 1
        assert any("Morning" in t["description"] for t in time_triggers)

    def test_no_morning_trigger_if_already_messaged(self) -> None:
        """Should NOT fire morning trigger if user already messaged today."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 8, 0, 0, tzinfo=timezone.utc),
            user_messaged_today=True,
        )
        time_triggers = [t for t in triggers if t["type"] == "time_based"]
        assert len(time_triggers) == 0

    def test_emotional_trigger_low_valence(self) -> None:
        """Should fire emotional trigger when last session had low valence."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
            last_session_closing_valence=0.15,
        )
        emotional = [t for t in triggers if t["type"] == "emotional"]
        assert len(emotional) == 1
        assert emotional[0]["urgency"] == "high"

    def test_no_emotional_trigger_normal_valence(self) -> None:
        """Should NOT fire emotional trigger for normal valence."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
            last_session_closing_valence=0.6,
        )
        emotional = [t for t in triggers if t["type"] == "emotional"]
        assert len(emotional) == 0

    def test_safety_trigger_wellness_checkpoint(self) -> None:
        """Should fire safety trigger when wellness checkpoint is due."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
            wellness_checkpoint_due=True,
        )
        safety = [t for t in triggers if t["type"] == "safety"]
        assert len(safety) >= 1
        assert safety[0]["urgency"] == "high"

    def test_long_absence_trigger(self) -> None:
        """Should fire pattern trigger after 48+ hours of absence."""
        from gwen.autonomy.triggers import TriggerEvaluator

        evaluator = TriggerEvaluator()
        triggers = evaluator.evaluate_triggers(
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
            hours_since_last_session=72.0,
        )
        pattern = [t for t in triggers if t["type"] == "pattern_based"]
        assert len(pattern) >= 1


class TestShouldISpeakDecision:
    """Tests for ShouldISpeakDecision."""

    def test_no_triggers_returns_false(self) -> None:
        """No triggers should result in 'do not speak'."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[],
            bond_warmth=0.8,
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
        )
        assert result is False

    def test_safety_trigger_overrides_everything(self) -> None:
        """Safety trigger should result in 'speak' even during quiet hours."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "safety",
                "urgency": "high",
                "description": "Wellness checkpoint due",
            }],
            bond_warmth=0.1,  # Very low warmth
            current_time=datetime(2026, 2, 9, 2, 0, 0, tzinfo=timezone.utc),  # 2am
            quiet_hours_start=23,
            quiet_hours_end=7,
        )
        assert result is True

    def test_quiet_hours_blocks_non_safety(self) -> None:
        """Non-safety triggers during quiet hours should result in 'do not speak'."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "emotional",
                "urgency": "high",
                "description": "Low valence",
            }],
            bond_warmth=0.8,
            current_time=datetime(2026, 2, 9, 2, 0, 0, tzinfo=timezone.utc),  # 2am
            quiet_hours_start=23,
            quiet_hours_end=7,
        )
        assert result is False

    def test_low_warmth_blocks_outreach(self) -> None:
        """Bond warmth < 0.3 should block outreach (too early in relationship)."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "time_based",
                "urgency": "low",
                "description": "Morning greeting",
            }],
            bond_warmth=0.2,
            current_time=datetime(2026, 2, 9, 9, 0, 0, tzinfo=timezone.utc),
        )
        assert result is False

    def test_high_urgency_with_warm_bond(self) -> None:
        """High-urgency trigger + warm bond should result in 'speak'."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "emotional",
                "urgency": "high",
                "description": "Low valence",
            }],
            bond_warmth=0.4,
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
        )
        assert result is True

    def test_warm_bond_with_low_urgency(self) -> None:
        """Low-urgency trigger + warm bond (> 0.5) should result in 'speak'."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "time_based",
                "urgency": "low",
                "description": "Morning greeting",
            }],
            bond_warmth=0.6,
            current_time=datetime(2026, 2, 9, 9, 0, 0, tzinfo=timezone.utc),
        )
        assert result is True

    def test_medium_warmth_low_urgency_does_not_speak(self) -> None:
        """Low-urgency trigger + medium bond (0.3-0.5) should result in 'do not speak'."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()
        result = decision.decide(
            triggers=[{
                "type": "time_based",
                "urgency": "low",
                "description": "Morning greeting",
            }],
            bond_warmth=0.4,
            current_time=datetime(2026, 2, 9, 9, 0, 0, tzinfo=timezone.utc),
        )
        assert result is False

    def test_quiet_hours_spanning_midnight(self) -> None:
        """Quiet hours 23:00-07:00 should correctly handle midnight crossing."""
        from gwen.autonomy.decision import ShouldISpeakDecision

        decision = ShouldISpeakDecision()

        # 23:30 should be in quiet hours
        result_late = decision.decide(
            triggers=[{
                "type": "time_based",
                "urgency": "low",
                "description": "test",
            }],
            bond_warmth=0.8,
            current_time=datetime(2026, 2, 9, 23, 30, 0, tzinfo=timezone.utc),
            quiet_hours_start=23,
            quiet_hours_end=7,
        )
        assert result_late is False

        # 14:00 should NOT be in quiet hours
        result_afternoon = decision.decide(
            triggers=[{
                "type": "time_based",
                "urgency": "low",
                "description": "test",
            }],
            bond_warmth=0.8,
            current_time=datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc),
            quiet_hours_start=23,
            quiet_hours_end=7,
        )
        assert result_afternoon is True
```

---

### Step 6.2: Run the tests

Execute the following commands from the project root:

- [ ] Run `pytest tests/test_circadian.py -v` and confirm all tests pass

```bash
pytest tests/test_circadian.py -v
```

**Expected output:** All tests pass. You should see:

```
tests/test_circadian.py::TestCircadianDeviationDetector::test_insufficient_data_returns_none PASSED
tests/test_circadian.py::TestCircadianDeviationDetector::test_high_deviation_at_unused_hour PASSED
tests/test_circadian.py::TestCircadianDeviationDetector::test_medium_deviation_at_rare_hour PASSED
tests/test_circadian.py::TestCircadianDeviationDetector::test_low_deviation_at_occasional_hour PASSED
tests/test_circadian.py::TestCircadianDeviationDetector::test_no_deviation_at_normal_hour PASSED
tests/test_circadian.py::TestCircadianDeviationDetector::test_compute_baseline_returns_correct_hours PASSED
tests/test_circadian.py::TestCircadianDeviationDetector::test_get_peak_hours PASSED
tests/test_circadian.py::TestRhythmTracker::test_empty_tracker PASSED
tests/test_circadian.py::TestRhythmTracker::test_single_message PASSED
tests/test_circadian.py::TestRhythmTracker::test_density_within_window PASSED
tests/test_circadian.py::TestRhythmTracker::test_density_outside_window PASSED
tests/test_circadian.py::TestRhythmTracker::test_avg_latency_computation PASSED
tests/test_circadian.py::TestRhythmTracker::test_sudden_pause_detection PASSED
tests/test_circadian.py::TestRhythmTracker::test_no_anomaly_with_steady_rhythm PASSED
tests/test_circadian.py::TestRhythmTracker::test_reset_clears_state PASSED
tests/test_circadian.py::TestTriggerEvaluator::test_morning_greeting_trigger PASSED
tests/test_circadian.py::TestTriggerEvaluator::test_no_morning_trigger_if_already_messaged PASSED
tests/test_circadian.py::TestTriggerEvaluator::test_emotional_trigger_low_valence PASSED
tests/test_circadian.py::TestTriggerEvaluator::test_no_emotional_trigger_normal_valence PASSED
tests/test_circadian.py::TestTriggerEvaluator::test_safety_trigger_wellness_checkpoint PASSED
tests/test_circadian.py::TestTriggerEvaluator::test_long_absence_trigger PASSED
tests/test_circadian.py::TestShouldISpeakDecision::test_no_triggers_returns_false PASSED
tests/test_circadian.py::TestShouldISpeakDecision::test_safety_trigger_overrides_everything PASSED
tests/test_circadian.py::TestShouldISpeakDecision::test_quiet_hours_blocks_non_safety PASSED
tests/test_circadian.py::TestShouldISpeakDecision::test_low_warmth_blocks_outreach PASSED
tests/test_circadian.py::TestShouldISpeakDecision::test_high_urgency_with_warm_bond PASSED
tests/test_circadian.py::TestShouldISpeakDecision::test_warm_bond_with_low_urgency PASSED
tests/test_circadian.py::TestShouldISpeakDecision::test_medium_warmth_low_urgency_does_not_speak PASSED
tests/test_circadian.py::TestShouldISpeakDecision::test_quiet_hours_spanning_midnight PASSED

29 passed in X.XXs
```

**If any test fails:**
1. **ImportError for gwen.temporal**: Make sure `gwen/temporal/__init__.py` exists.
2. **ImportError for gwen.autonomy**: Make sure `gwen/autonomy/__init__.py` exists.
3. **ImportError for gwen.models.temporal**: Track 002 (data-models) must be complete.
4. **CircadianDeviationDetector tests**: The test inserts messages at specific hours and checks deviation thresholds.  If thresholds do not match, verify the constants in `compute_deviation()`.
5. **RhythmTracker sudden_pause test**: The test creates 5 messages 5 seconds apart (avg gap = 5s) then a 60-second gap (12x average > 3x threshold).  If this test fails, check the `detect_anomaly()` logic.
6. **ShouldISpeakDecision quiet hours test**: The `_is_in_quiet_hours` method must handle midnight-spanning windows (23:00-07:00).  Hour 2 is in quiet hours.  Hour 14 is not.

---

## Summary of Files Created

| Phase | File Path | Contents |
|-------|-----------|----------|
| 1 | `gwen/temporal/__init__.py` | Package docstring |
| 1 | `gwen/temporal/circadian.py` | CircadianDeviationDetector |
| 2 | `gwen/temporal/rhythm.py` | RhythmTracker |
| 3 | `gwen/autonomy/__init__.py` | Package docstring |
| 3 | `gwen/autonomy/triggers.py` | TriggerEvaluator |
| 3 | `gwen/autonomy/decision.py` | ShouldISpeakDecision |
| 4 | `gwen/consolidation/__init__.py` | Package docstring |
| 4 | `gwen/consolidation/standard.py` | StandardConsolidation |
| 5 | `gwen/consolidation/deep.py` | DeepConsolidation |
| 6 | `tests/test_circadian.py` | 29 tests across 4 test classes |

---

## Checklist (update after each step)

- [ ] Phase 1 complete: gwen/temporal/circadian.py with CircadianDeviationDetector
- [ ] Phase 2 complete: gwen/temporal/rhythm.py with RhythmTracker
- [ ] Phase 3 complete: gwen/autonomy/ package with TriggerEvaluator and ShouldISpeakDecision
- [ ] Phase 4 complete: gwen/consolidation/standard.py with StandardConsolidation
- [ ] Phase 5 complete: gwen/consolidation/deep.py with DeepConsolidation
- [ ] Phase 6 complete: tests/test_circadian.py passes with all 29 tests green
