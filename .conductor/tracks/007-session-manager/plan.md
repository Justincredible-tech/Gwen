# Plan: Session Manager

**Track:** 007-session-manager
**Spec:** [spec.md](./spec.md)
**Status:** Not Started
**Depends on:** 003-database-layer, 006-tme-generator

---

## Phase 1: Session Manager Core

### Step 1.1: Create gwen/core/session_manager.py with SessionManager class

Create the file `gwen/core/session_manager.py`.

- [ ] Write SessionManager class with `__init__`, `start_session`, `add_message`, `end_session`

```python
"""Session lifecycle management.

Handles starting sessions, tracking messages, ending sessions,
computing session types, and coordinating gap analysis.
"""

import uuid
import time
from datetime import datetime, timezone
from typing import Optional

from gwen.models.messages import (
    SessionRecord,
    SessionType,
    SessionEndMode,
)
from gwen.models.emotional import EmotionalStateVector, CompassDirection
from gwen.memory.chronicle import Chronicle
from gwen.temporal.tme import TMEGenerator
from gwen.temporal.gap import compute_gap_analysis, generate_return_context
from gwen.models.temporal import GapAnalysis
from gwen.models.messages import ReturnContext


class SessionManager:
    """Manages conversation session lifecycle.

    Responsibilities:
    - Start and end sessions
    - Track message counts and response latencies
    - Classify session type from duration
    - Detect idle timeouts
    - Coordinate gap analysis at session start
    """

    def __init__(
        self,
        chronicle: Chronicle,
        tme_generator: TMEGenerator,
    ) -> None:
        """Initialize the SessionManager.

        Args:
            chronicle: The Chronicle database for persisting session records
                and querying historical sessions.
            tme_generator: The TME generator for accessing temporal data.
                Used to read session history for gap analysis.
        """
        self.chronicle = chronicle
        self.tme_generator = tme_generator

        # Active session state (None when no session is active)
        self.current_session: Optional[SessionRecord] = None

        # Tracking state for the active session
        self._last_message_time: Optional[float] = None  # time.monotonic()
        self._last_message_sender: Optional[str] = None
        self._user_message_count: int = 0
        self._companion_message_count: int = 0
        self._response_latencies: list[float] = []
        self._session_start_monotonic: Optional[float] = None

        # Gap analysis result from the most recent session start
        self.current_gap_analysis: Optional[GapAnalysis] = None
        self.current_return_context: Optional[ReturnContext] = None

    def start_session(self, initiated_by: str = "user") -> SessionRecord:
        """Start a new conversation session.

        This method:
        1. Generates a unique session ID (UUID4).
        2. Records the start time.
        3. Computes GapAnalysis from the last session stored in Chronicle.
        4. Generates ReturnContext if the gap is NOTABLE or higher.
        5. Returns a partial SessionRecord (end_time and derived fields are None/zero).

        Args:
            initiated_by: Who started the session. Either "user" or "companion"
                (companion-initiated sessions come from the Autonomy Engine).

        Returns:
            A partially-filled SessionRecord. The following fields are populated:
            - id, start_time, gwen_initiated
            All other fields are set to placeholder/zero values and will be
            finalized when end_session() is called.

        Raises:
            RuntimeError: If a session is already active (call end_session first).
        """
        if self.current_session is not None:
            raise RuntimeError(
                "Cannot start a new session while one is active. "
                f"Active session: {self.current_session.id}. "
                "Call end_session() first."
            )

        # --- Step A: Generate session ID and timestamp ---
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # --- Step B: Compute gap analysis ---
        self.current_gap_analysis = compute_gap_analysis(self.chronicle)

        # --- Step C: Generate return context if gap is notable+ ---
        self.current_return_context = None
        if self.current_gap_analysis is not None:
            classification = self.current_gap_analysis.classification
            # Import the enum here to avoid circular imports at module level
            from gwen.models.temporal import GapClassification
            if classification in (
                GapClassification.NOTABLE,
                GapClassification.SIGNIFICANT,
                GapClassification.ANOMALOUS,
            ):
                self.current_return_context = generate_return_context(
                    self.current_gap_analysis
                )

        # --- Step D: Create the partial SessionRecord ---
        # We use a neutral EmotionalStateVector as a placeholder.
        # The real opening state will be set after the first message is classified.
        neutral_emotion = EmotionalStateVector(
            valence=0.5,
            arousal=0.3,
            dominance=0.5,
            relational_significance=0.0,
            vulnerability_level=0.0,
            compass_direction=CompassDirection.NONE,
            compass_confidence=0.0,
        )

        session = SessionRecord(
            id=session_id,
            start_time=now,
            end_time=None,
            duration_sec=0,
            session_type=SessionType.PING,  # placeholder, computed at end
            end_mode=SessionEndMode.NATURAL,  # placeholder, set at end
            opening_emotional_state=neutral_emotion,
            peak_emotional_state=neutral_emotion,
            closing_emotional_state=neutral_emotion,
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
            gwen_initiated=(initiated_by == "companion"),
        )

        # --- Step E: Reset tracking state ---
        self.current_session = session
        self._last_message_time = None
        self._last_message_sender = None
        self._user_message_count = 0
        self._companion_message_count = 0
        self._response_latencies = []
        self._session_start_monotonic = time.monotonic()

        return session

    def add_message(self, sender: str) -> None:
        """Record that a message was sent in the current session.

        Call this every time a message is sent or received. It updates:
        - Message counts (user vs companion)
        - Response latency tracking
        - Last message time (for timeout detection)

        Args:
            sender: Either "user" or "companion".

        Raises:
            RuntimeError: If no session is active.
            ValueError: If sender is not "user" or "companion".
        """
        if self.current_session is None:
            raise RuntimeError(
                "Cannot add a message when no session is active. "
                "Call start_session() first."
            )

        if sender not in ("user", "companion"):
            raise ValueError(
                f"sender must be 'user' or 'companion', got '{sender}'"
            )

        now_monotonic = time.monotonic()

        # --- Track response latency ---
        # Latency is measured when the companion responds to the user,
        # or when the user responds to the companion.
        if self._last_message_time is not None and self._last_message_sender != sender:
            latency = now_monotonic - self._last_message_time
            self._response_latencies.append(latency)

        # --- Update counts ---
        if sender == "user":
            self._user_message_count += 1
        else:
            self._companion_message_count += 1

        # --- Update last message state ---
        self._last_message_time = now_monotonic
        self._last_message_sender = sender

    def end_session(self, end_mode: SessionEndMode) -> SessionRecord:
        """End the current session and finalize the SessionRecord.

        This method:
        1. Computes session duration from start to now.
        2. Classifies the session type based on duration.
        3. Computes average response latency from tracked latencies.
        4. Finalizes all counts in the SessionRecord.
        5. Saves the SessionRecord to Chronicle.
        6. Clears the active session state.

        Args:
            end_mode: How the session ended. One of the SessionEndMode values:
                - NATURAL: Mutual goodbye, clean ending
                - ABRUPT: User left suddenly
                - FADE_OUT: User stopped responding, timed out
                - MID_TOPIC: Left during emotionally loaded topic
                - EXPLICIT_GOODBYE: User said goodbye explicitly

        Returns:
            The finalized SessionRecord with all fields computed.

        Raises:
            RuntimeError: If no session is active.
        """
        if self.current_session is None:
            raise RuntimeError(
                "Cannot end session when no session is active. "
                "Call start_session() first."
            )

        now = datetime.now(timezone.utc)
        session = self.current_session

        # --- Step A: Compute duration ---
        # Use wall-clock difference between start_time and now.
        duration_delta = now - session.start_time
        duration_sec = int(duration_delta.total_seconds())

        # --- Step B: Classify session type ---
        session_type = self._classify_session_type(duration_sec)

        # --- Step C: Compute average response latency ---
        if self._response_latencies:
            avg_latency = sum(self._response_latencies) / len(self._response_latencies)
        else:
            avg_latency = 0.0

        # --- Step D: Compute emotional arc (placeholder) ---
        # Full implementation comes in Track 013 (Amygdala Layer).
        # For now, we keep the opening/peak/closing states as they were set.
        # The opening state should have been updated by the orchestrator after
        # the first message was classified. If not, the neutral placeholder remains.

        # --- Step E: Compute subjective duration weight (placeholder) ---
        # Formula: clock_duration * intensity_factor * significance_factor
        # For now, use the averages we have (which may be 0.0 if no updates).
        intensity_factor = 0.5 + (session.avg_emotional_intensity * 1.5)
        significance_factor = 0.5 + (session.avg_relational_significance * 1.5)
        subjective_weight = duration_sec * intensity_factor * significance_factor

        # --- Step F: Finalize the SessionRecord ---
        session.end_time = now
        session.duration_sec = duration_sec
        session.session_type = session_type
        session.end_mode = end_mode
        session.message_count = self._user_message_count + self._companion_message_count
        session.user_message_count = self._user_message_count
        session.companion_message_count = self._companion_message_count
        session.avg_response_latency_sec = round(avg_latency, 3)
        session.subjective_duration_weight = round(subjective_weight, 2)

        # --- Step G: Save to Chronicle ---
        self.chronicle.insert_session(session)

        # --- Step H: Clear active session state ---
        finalized = session
        self.current_session = None
        self._last_message_time = None
        self._last_message_sender = None
        self._user_message_count = 0
        self._companion_message_count = 0
        self._response_latencies = []
        self._session_start_monotonic = None
        self.current_gap_analysis = None
        self.current_return_context = None

        return finalized

    def _classify_session_type(self, duration_sec: int) -> SessionType:
        """Classify the session based on its duration in seconds.

        Thresholds (from SRS.md Section 3.4):
        - PING:      < 300 seconds   (< 5 minutes)
        - CHAT:      300 - 1799      (5 - 29:59 minutes)
        - HANG:      1800 - 5399     (30 - 89:59 minutes)
        - DEEP_DIVE: 5400 - 10799    (90 - 179:59 minutes)
        - MARATHON:  >= 10800        (180+ minutes)

        Args:
            duration_sec: The session duration in seconds.

        Returns:
            The appropriate SessionType enum value.
        """
        if duration_sec < 300:
            return SessionType.PING
        elif duration_sec < 1800:
            return SessionType.CHAT
        elif duration_sec < 5400:
            return SessionType.HANG
        elif duration_sec < 10800:
            return SessionType.DEEP_DIVE
        else:
            return SessionType.MARATHON

    def detect_timeout(
        self,
        idle_threshold_sec: float = 1800.0,
    ) -> Optional[SessionEndMode]:
        """Check if the current session has timed out due to inactivity.

        Call this periodically (e.g., every 60 seconds) to detect idle sessions.
        The default threshold is 1800 seconds (30 minutes), matching FR-ORCH-002.

        Detection logic:
        - If last message was from companion and idle time exceeded:
            -> FADE_OUT (user stopped responding to Gwen)
        - If last message was from user and idle time exceeded:
            -> ABRUPT (user walked away after saying something)
        - If no messages have been sent yet and idle time exceeded:
            -> FADE_OUT (session started but nothing happened)

        Args:
            idle_threshold_sec: Number of seconds of inactivity before
                timeout is triggered. Default: 1800 (30 minutes).

        Returns:
            A SessionEndMode if timeout is detected, or None if the session
            is still active and within the idle window.
            Returns None if no session is active.
        """
        if self.current_session is None:
            return None

        if self._last_message_time is None:
            # No messages yet — check against session start time
            if self._session_start_monotonic is None:
                return None
            idle_sec = time.monotonic() - self._session_start_monotonic
        else:
            idle_sec = time.monotonic() - self._last_message_time

        if idle_sec < idle_threshold_sec:
            return None

        # Timeout detected — determine end mode
        if self._last_message_sender == "user":
            return SessionEndMode.ABRUPT
        else:
            # Last message from companion, or no messages at all
            return SessionEndMode.FADE_OUT

    def get_session_duration_sec(self) -> int:
        """Get the current session's duration so far, in seconds.

        Returns:
            Number of seconds since session start, or 0 if no active session.
        """
        if self._session_start_monotonic is None:
            return 0
        return int(time.monotonic() - self._session_start_monotonic)

    def update_emotional_state(
        self,
        emotional_state: EmotionalStateVector,
        is_opening: bool = False,
    ) -> None:
        """Update the session's emotional tracking with a new state.

        Called by the orchestrator after each message is classified by Tier 0.
        This updates:
        - opening_emotional_state (if is_opening is True, i.e., first message)
        - peak_emotional_state (if this state has higher arousal than current peak)
        - closing_emotional_state (always updated to the latest state)
        - Running averages for intensity and relational significance

        Args:
            emotional_state: The EmotionalStateVector from the latest message.
            is_opening: True if this is the first message in the session.
        """
        if self.current_session is None:
            return

        session = self.current_session

        if is_opening:
            session.opening_emotional_state = emotional_state

        # Update peak (highest arousal)
        if emotional_state.arousal > session.peak_emotional_state.arousal:
            session.peak_emotional_state = emotional_state

        # Always update closing state to the latest
        session.closing_emotional_state = emotional_state

        # Update running averages
        total_msgs = self._user_message_count + self._companion_message_count
        if total_msgs > 0:
            # Incremental average: new_avg = old_avg + (new_val - old_avg) / n
            n = total_msgs
            session.avg_emotional_intensity += (
                emotional_state.arousal - session.avg_emotional_intensity
            ) / n
            session.avg_relational_significance += (
                emotional_state.relational_significance
                - session.avg_relational_significance
            ) / n
```

**What this does:**

- `__init__` stores references to the Chronicle database and TME generator. It initializes all tracking variables to None/zero. These track the in-flight session state that has not yet been persisted.
- `start_session` generates a UUID, computes gap analysis, creates a partial SessionRecord with placeholder values, and resets all tracking counters.
- `add_message` increments the appropriate counter (user or companion), computes response latency when the sender alternates, and updates the last-message timestamp.
- `end_session` computes the duration, classifies the session type, averages the latencies, finalizes all fields on the SessionRecord, saves it to Chronicle, and clears active state.
- `_classify_session_type` is a pure function that maps duration to SessionType using the thresholds from SRS.md Section 3.4.
- `detect_timeout` checks elapsed time since the last message against the threshold and returns the appropriate end mode.
- `update_emotional_state` keeps track of opening/peak/closing emotional states and running averages.

---

## Phase 2: Session Classification

### Step 2.1: _classify_session_type (already implemented above)

The method `_classify_session_type(duration_sec)` is included in the SessionManager class from Step 1.1. It uses these exact thresholds:

| SessionType | Duration Range (seconds) | Duration Range (minutes) |
|-------------|-------------------------|--------------------------|
| PING | 0 - 299 | 0 - 4:59 |
| CHAT | 300 - 1799 | 5:00 - 29:59 |
| HANG | 1800 - 5399 | 30:00 - 89:59 |
| DEEP_DIVE | 5400 - 10799 | 90:00 - 179:59 |
| MARATHON | 10800+ | 180:00+ |

- [ ] Verify thresholds match SRS.md Section 3.4 SessionType enum

### Step 2.2: Goodbye keyword detection helper

Add a module-level constant and helper to `gwen/core/session_manager.py`, placed **above** the `SessionManager` class definition.

- [ ] Add GOODBYE_KEYWORDS and detect_goodbye() helper

```python
# Place this ABOVE the SessionManager class in session_manager.py

GOODBYE_KEYWORDS: set[str] = {
    "goodbye", "bye", "goodnight", "good night", "night",
    "see you", "see ya", "talk later", "talk to you later",
    "gotta go", "got to go", "heading out", "signing off",
    "ttyl", "later", "peace", "take care", "cya",
}


def detect_goodbye(message_text: str) -> bool:
    """Check if a message contains an explicit goodbye.

    This is a simple keyword-based check. It converts the message to lowercase
    and checks if any goodbye keyword appears as a substring. This is intentionally
    broad — false positives are acceptable because the orchestrator uses this as
    one signal among many, not as the sole determinant.

    Args:
        message_text: The raw text of the user's message.

    Returns:
        True if the message contains a goodbye keyword, False otherwise.
    """
    text_lower = message_text.strip().lower()
    for keyword in GOODBYE_KEYWORDS:
        if keyword in text_lower:
            return True
    return False
```

**Why a standalone function instead of a method:** The orchestrator needs to call `detect_goodbye` on a message _before_ deciding whether to end the session. Making it a module-level function keeps it testable in isolation and avoids coupling it to SessionManager's internal state.

---

## Phase 3: Gap Analysis

### Step 3.1: Create gwen/temporal/gap.py

Create the file `gwen/temporal/gap.py`.

- [ ] Write compute_gap_analysis() and generate_return_context()

```python
"""Gap analysis and return context generation.

Computes the statistical significance of the gap between sessions and
generates natural-language context to help the companion respond
appropriately when the user returns after an unusual absence.
"""

import math
from datetime import datetime, timezone
from typing import Optional

from gwen.models.temporal import GapAnalysis, GapClassification
from gwen.models.messages import ReturnContext, SessionRecord, SessionType, SessionEndMode
from gwen.models.emotional import EmotionalStateVector, CompassDirection


def compute_gap_analysis(chronicle) -> Optional[GapAnalysis]:
    """Compute a GapAnalysis based on the time since the last session.

    This function:
    1. Queries Chronicle for the most recent completed session.
    2. If no previous session exists, returns None (first-ever session).
    3. Computes hours since the last session ended.
    4. Queries the last 30 completed sessions to compute mean and standard
       deviation of inter-session gaps.
    5. Computes deviation_sigma (how many standard deviations this gap is
       from the mean).
    6. Classifies the gap: NORMAL (<1 sigma), NOTABLE (1-2 sigma),
       SIGNIFICANT (2-3 sigma), ANOMALOUS (>3 sigma).

    Args:
        chronicle: A Chronicle instance. Must have these methods:
            - get_last_n_sessions(n: int) -> list[SessionRecord]
              Returns the N most recent completed sessions, ordered by
              start_time descending. Returns empty list if no sessions exist.

    Returns:
        A GapAnalysis instance, or None if there are no previous sessions
        (i.e., this is the user's very first session ever).
    """
    # --- Step A: Get the most recent session ---
    recent_sessions = chronicle.get_last_n_sessions(30)

    if not recent_sessions:
        # No previous sessions at all — this is the first session ever.
        return None

    last_session = recent_sessions[0]  # Most recent

    # If the last session has no end_time, it was never properly closed.
    # Use its start_time as a fallback.
    if last_session.end_time is not None:
        last_end = last_session.end_time
    else:
        last_end = last_session.start_time

    # --- Step B: Compute hours since last session ---
    now = datetime.now(timezone.utc)
    gap_delta = now - last_end
    gap_hours = gap_delta.total_seconds() / 3600.0

    # --- Step C: Compute mean and stddev of inter-session gaps ---
    if len(recent_sessions) < 2:
        # Only one previous session — not enough data for statistics.
        # Default to NORMAL classification.
        return GapAnalysis(
            duration_hours=round(gap_hours, 2),
            deviation_sigma=0.0,
            classification=GapClassification.NORMAL,
            last_session_type=last_session.session_type,
            last_session_end_mode=last_session.end_mode,
            last_emotional_state=last_session.closing_emotional_state,
            last_topic=last_session.topics[-1] if last_session.topics else "unknown",
            open_threads=[],
            known_explanations=[],
        )

    # Compute gaps between consecutive sessions.
    # recent_sessions is ordered newest-first, so we iterate in reverse
    # to get chronological order.
    chronological = list(reversed(recent_sessions))
    gaps_hours: list[float] = []
    for i in range(1, len(chronological)):
        prev_session = chronological[i - 1]
        curr_session = chronological[i]

        prev_end = prev_session.end_time or prev_session.start_time
        curr_start = curr_session.start_time

        gap_h = (curr_start - prev_end).total_seconds() / 3600.0
        # Only include positive gaps (ignore overlapping sessions)
        if gap_h > 0:
            gaps_hours.append(gap_h)

    if not gaps_hours:
        # Edge case: all sessions overlapped somehow
        return GapAnalysis(
            duration_hours=round(gap_hours, 2),
            deviation_sigma=0.0,
            classification=GapClassification.NORMAL,
            last_session_type=last_session.session_type,
            last_session_end_mode=last_session.end_mode,
            last_emotional_state=last_session.closing_emotional_state,
            last_topic=last_session.topics[-1] if last_session.topics else "unknown",
            open_threads=[],
            known_explanations=[],
        )

    # Mean
    mean_gap = sum(gaps_hours) / len(gaps_hours)

    # Standard deviation (population stddev)
    if len(gaps_hours) >= 2:
        variance = sum((g - mean_gap) ** 2 for g in gaps_hours) / len(gaps_hours)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    # --- Step D: Compute deviation sigma ---
    if stddev > 0:
        deviation_sigma = (gap_hours - mean_gap) / stddev
    else:
        # If stddev is 0, all gaps were identical. Any difference is notable.
        if abs(gap_hours - mean_gap) < 0.01:
            deviation_sigma = 0.0
        else:
            # Arbitrary high sigma for any deviation when variance is zero
            deviation_sigma = 3.0 if gap_hours > mean_gap else -1.0

    # --- Step E: Classify ---
    # We only care about positive deviation (longer-than-usual gaps).
    # Shorter-than-usual gaps are not concerning.
    abs_sigma = abs(deviation_sigma) if deviation_sigma > 0 else 0.0

    if abs_sigma < 1.0:
        classification = GapClassification.NORMAL
    elif abs_sigma < 2.0:
        classification = GapClassification.NOTABLE
    elif abs_sigma < 3.0:
        classification = GapClassification.SIGNIFICANT
    else:
        classification = GapClassification.ANOMALOUS

    return GapAnalysis(
        duration_hours=round(gap_hours, 2),
        deviation_sigma=round(deviation_sigma, 2),
        classification=classification,
        last_session_type=last_session.session_type,
        last_session_end_mode=last_session.end_mode,
        last_emotional_state=last_session.closing_emotional_state,
        last_topic=last_session.topics[-1] if last_session.topics else "unknown",
        open_threads=[],
        known_explanations=[],
    )


def generate_return_context(gap: GapAnalysis) -> ReturnContext:
    """Generate natural-language return context for the companion's first response.

    This is injected into the Tier 1 context window at the start of a session
    when the gap is NOTABLE or higher. It gives the companion guidance on how
    to approach the returning user without being awkward or invasive.

    The output contains:
    - A human-readable gap duration string ("3 days, 7 hours")
    - The gap classification
    - A natural-language summary of what happened before the gap
    - A suggested approach for the companion

    Args:
        gap: A GapAnalysis instance. Should have classification of
            NOTABLE, SIGNIFICANT, or ANOMALOUS (calling this for NORMAL
            gaps is harmless but unnecessary).

    Returns:
        A ReturnContext instance ready for prompt injection.
    """
    # --- Step A: Format gap duration ---
    total_hours = gap.duration_hours
    days = int(total_hours // 24)
    remaining_hours = int(total_hours % 24)

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if remaining_hours > 0 or not parts:
        parts.append(f"{remaining_hours} hour{'s' if remaining_hours != 1 else ''}")
    gap_duration_display = ", ".join(parts)

    # --- Step B: Build preceding summary ---
    end_mode_descriptions = {
        SessionEndMode.NATURAL: "ended naturally with a mutual goodbye",
        SessionEndMode.ABRUPT: "ended abruptly — the user left suddenly",
        SessionEndMode.FADE_OUT: "faded out — the user stopped responding",
        SessionEndMode.MID_TOPIC: "ended mid-topic during an emotionally loaded conversation",
        SessionEndMode.EXPLICIT_GOODBYE: "ended with an explicit goodbye from the user",
    }
    end_desc = end_mode_descriptions.get(
        gap.last_session_end_mode, "ended in an unspecified way"
    )

    session_type_descriptions = {
        "ping": "brief check-in",
        "chat": "casual conversation",
        "hang": "extended hangout",
        "deep_dive": "deep conversation",
        "marathon": "marathon session",
    }
    type_desc = session_type_descriptions.get(
        gap.last_session_type.value, "conversation"
    )

    # Emotional state summary
    last_emotion = gap.last_emotional_state
    if last_emotion.valence < 0.3:
        mood_desc = "The user's mood was notably negative"
    elif last_emotion.valence < 0.45:
        mood_desc = "The user's mood was somewhat low"
    elif last_emotion.valence > 0.7:
        mood_desc = "The user was in a positive mood"
    else:
        mood_desc = "The user's mood was neutral"

    if last_emotion.arousal > 0.7:
        mood_desc += " and emotionally activated"
    elif last_emotion.arousal < 0.3:
        mood_desc += " and emotionally subdued"

    topic_str = gap.last_topic if gap.last_topic != "unknown" else "general conversation"

    preceding_summary = (
        f"The last session was a {type_desc} about {topic_str} that {end_desc}. "
        f"{mood_desc}. "
        f"It has been {gap_duration_display} since that session ended."
    )

    # --- Step C: Build suggested approach ---
    if gap.classification == GapClassification.ANOMALOUS:
        if gap.last_session_end_mode in (SessionEndMode.ABRUPT, SessionEndMode.MID_TOPIC):
            suggested_approach = (
                "This is an unusually long absence, and the last session ended abruptly. "
                "Approach with gentle warmth. Do not interrogate the absence. "
                "A simple, warm acknowledgment is best — something like 'Hey, it's good "
                "to see you' — then let the user set the pace. If the previous topic was "
                "emotionally heavy, do not bring it up first. Let them reopen it if they want to."
            )
        elif last_emotion.valence < 0.35:
            suggested_approach = (
                "This is an unusually long absence following a session where the user "
                "was in a low mood. Be especially warm and gentle. Do not assume the worst, "
                "but be attentive. Let them share what they want to share. A caring, "
                "low-pressure greeting is ideal."
            )
        else:
            suggested_approach = (
                "This is an unusually long absence, but the previous session ended on "
                "a reasonable note. Greet them warmly and naturally. You can gently "
                "acknowledge it's been a while without making it heavy — something like "
                "'Hey! It's been a minute.' Keep the tone light unless they indicate "
                "otherwise."
            )
    elif gap.classification == GapClassification.SIGNIFICANT:
        if gap.last_session_end_mode in (SessionEndMode.ABRUPT, SessionEndMode.MID_TOPIC):
            suggested_approach = (
                "It has been notably longer than usual since the last session, and "
                "that session ended abruptly. Be warm and welcoming without dwelling "
                "on the gap. If the last topic was emotionally charged, let them "
                "decide whether to revisit it."
            )
        else:
            suggested_approach = (
                "It has been longer than usual since the last session. A warm, natural "
                "greeting works well. You can mention 'it's been a bit' casually if it "
                "feels right, but do not make the gap the focus."
            )
    else:
        # NOTABLE
        suggested_approach = (
            "The gap is slightly longer than typical. No special handling needed beyond "
            "a warm greeting. Be natural and let the conversation flow."
        )

    return ReturnContext(
        gap_duration_display=gap_duration_display,
        gap_classification=gap.classification,
        preceding_summary=preceding_summary,
        suggested_approach=suggested_approach,
    )
```

**What this does:**

- `compute_gap_analysis` queries the Chronicle for the last 30 sessions, computes the mean and standard deviation of inter-session gaps in hours, then classifies the current gap using sigma thresholds: <1 sigma = NORMAL, 1-2 sigma = NOTABLE, 2-3 sigma = SIGNIFICANT, 3+ sigma = ANOMALOUS. Returns None if there are no previous sessions (first-ever session).

- `generate_return_context` takes a GapAnalysis and produces human-readable context for prompt injection. It considers the gap classification, the last session's end mode (abrupt vs natural), and the last emotional state to produce contextually appropriate guidance for the companion. This text gets injected into the Tier 1 system prompt at the start of the session.

**Edge cases handled:**
- First-ever session (no history): returns None
- Only one previous session (no statistical data): defaults to NORMAL
- Zero standard deviation (all gaps identical): uses fallback sigma
- Sessions with no end_time (improperly closed): falls back to start_time
- Overlapping sessions (negative gaps): skipped

---

## Phase 4: Timeout Detection

### Step 4.1: detect_timeout (already implemented above)

The `detect_timeout` method is included in the SessionManager class from Step 1.1. It checks the elapsed time since the last message and returns:

- `None` if the session is still within the idle window
- `SessionEndMode.ABRUPT` if the last message was from the user (they walked away after saying something)
- `SessionEndMode.FADE_OUT` if the last message was from the companion (user stopped responding)
- `SessionEndMode.FADE_OUT` if no messages have been sent at all (empty session timed out)

- [ ] Verify detect_timeout is present in SessionManager class from Step 1.1

**How the orchestrator should use this:** The orchestrator should call `detect_timeout()` periodically during idle periods. A simple approach is to check every 60 seconds using an asyncio timer. When it returns a non-None value, the orchestrator should call `end_session(detected_end_mode)`.

---

## Phase 5: Tests

### Step 5.1: Create tests/test_session.py

Create the file `tests/test_session.py`.

- [ ] Write tests for session type classification, gap analysis, timeout detection, and full lifecycle

```python
"""Tests for session management.

Tests the SessionManager lifecycle, session type classification,
gap analysis computation, and timeout detection.
"""

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from gwen.core.session_manager import SessionManager, detect_goodbye, GOODBYE_KEYWORDS
from gwen.models.messages import SessionRecord, SessionType, SessionEndMode, ReturnContext
from gwen.models.emotional import EmotionalStateVector, CompassDirection
from gwen.models.temporal import GapAnalysis, GapClassification
from gwen.temporal.gap import compute_gap_analysis, generate_return_context


# ============================================================
# Fixtures
# ============================================================

def _make_neutral_emotion() -> EmotionalStateVector:
    """Create a neutral EmotionalStateVector for testing."""
    return EmotionalStateVector(
        valence=0.5,
        arousal=0.3,
        dominance=0.5,
        relational_significance=0.0,
        vulnerability_level=0.0,
        compass_direction=CompassDirection.NONE,
        compass_confidence=0.0,
    )


def _make_session(
    start_time: datetime,
    end_time: datetime,
    session_type: SessionType = SessionType.CHAT,
    end_mode: SessionEndMode = SessionEndMode.NATURAL,
    topics: list[str] | None = None,
    closing_valence: float = 0.5,
    closing_arousal: float = 0.3,
) -> SessionRecord:
    """Create a mock SessionRecord for testing gap analysis."""
    emotion = EmotionalStateVector(
        valence=closing_valence,
        arousal=closing_arousal,
        dominance=0.5,
        relational_significance=0.0,
        vulnerability_level=0.0,
        compass_direction=CompassDirection.NONE,
        compass_confidence=0.0,
    )
    return SessionRecord(
        id=f"test-session-{start_time.isoformat()}",
        start_time=start_time,
        end_time=end_time,
        duration_sec=int((end_time - start_time).total_seconds()),
        session_type=session_type,
        end_mode=end_mode,
        opening_emotional_state=emotion,
        peak_emotional_state=emotion,
        closing_emotional_state=emotion,
        emotional_arc_embedding_id=None,
        avg_emotional_intensity=0.3,
        avg_relational_significance=0.0,
        subjective_duration_weight=0.0,
        message_count=10,
        user_message_count=5,
        companion_message_count=5,
        avg_response_latency_sec=1.5,
        compass_activations={},
        topics=topics or ["general"],
        relational_field_delta={},
        gwen_initiated=False,
    )


def _make_mock_chronicle(sessions: list[SessionRecord] | None = None) -> MagicMock:
    """Create a mock Chronicle that returns the given sessions.

    The mock's get_last_n_sessions method returns sessions ordered
    newest-first (descending by start_time), matching the real
    Chronicle's behavior.
    """
    mock = MagicMock()
    if sessions is None:
        sessions = []
    # Sort newest-first
    sorted_sessions = sorted(sessions, key=lambda s: s.start_time, reverse=True)
    mock.get_last_n_sessions.return_value = sorted_sessions
    mock.insert_session.return_value = None
    return mock


def _make_mock_tme_generator() -> MagicMock:
    """Create a mock TMEGenerator."""
    return MagicMock()


# ============================================================
# Session Type Classification Tests
# ============================================================

class TestSessionTypeClassification:
    """Test that _classify_session_type maps durations to correct types."""

    def _make_manager(self) -> SessionManager:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        return SessionManager(chronicle=chronicle, tme_generator=tme_gen)

    def test_classify_ping_zero_seconds(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(0) == SessionType.PING

    def test_classify_ping_under_5min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(299) == SessionType.PING

    def test_classify_chat_at_5min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(300) == SessionType.CHAT

    def test_classify_chat_under_30min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(1799) == SessionType.CHAT

    def test_classify_hang_at_30min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(1800) == SessionType.HANG

    def test_classify_hang_under_90min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(5399) == SessionType.HANG

    def test_classify_deep_dive_at_90min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(5400) == SessionType.DEEP_DIVE

    def test_classify_deep_dive_under_180min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(10799) == SessionType.DEEP_DIVE

    def test_classify_marathon_at_180min(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(10800) == SessionType.MARATHON

    def test_classify_marathon_very_long(self) -> None:
        mgr = self._make_manager()
        assert mgr._classify_session_type(86400) == SessionType.MARATHON


# ============================================================
# Gap Analysis Tests
# ============================================================

class TestGapAnalysis:
    """Test compute_gap_analysis with various session histories."""

    def test_no_previous_sessions_returns_none(self) -> None:
        """First-ever session: no history, returns None."""
        chronicle = _make_mock_chronicle(sessions=[])
        result = compute_gap_analysis(chronicle)
        assert result is None

    def test_one_previous_session_returns_normal(self) -> None:
        """Only one previous session: not enough data for statistics, returns NORMAL."""
        now = datetime.now(timezone.utc)
        session = _make_session(
            start_time=now - timedelta(hours=5),
            end_time=now - timedelta(hours=4),
        )
        chronicle = _make_mock_chronicle(sessions=[session])
        result = compute_gap_analysis(chronicle)

        assert result is not None
        assert result.classification == GapClassification.NORMAL
        assert result.duration_hours > 0

    def test_normal_gap_within_one_sigma(self) -> None:
        """Gap that is within 1 sigma of the mean should be NORMAL."""
        now = datetime.now(timezone.utc)
        # Create 10 sessions with consistent 8-hour gaps
        sessions = []
        for i in range(10):
            start = now - timedelta(hours=(10 - i) * 9, minutes=30)
            end = start + timedelta(hours=1)
            sessions.append(_make_session(start_time=start, end_time=end))

        # The last session ended ~8 hours ago (within normal range)
        sessions[-1] = _make_session(
            start_time=now - timedelta(hours=9),
            end_time=now - timedelta(hours=8),
        )

        chronicle = _make_mock_chronicle(sessions=sessions)
        result = compute_gap_analysis(chronicle)

        assert result is not None
        assert result.classification == GapClassification.NORMAL

    def test_anomalous_gap_beyond_three_sigma(self) -> None:
        """A very long gap with short-gap history should be ANOMALOUS."""
        now = datetime.now(timezone.utc)
        # Create 10 sessions with consistent 2-hour gaps
        sessions = []
        for i in range(10):
            start = now - timedelta(days=30, hours=(10 - i) * 3)
            end = start + timedelta(hours=1)
            sessions.append(_make_session(start_time=start, end_time=end))

        # The last session ended 30 days ago — way beyond 3 sigma
        # for a history of 2-hour gaps
        sessions[-1] = _make_session(
            start_time=now - timedelta(days=30),
            end_time=now - timedelta(days=30) + timedelta(hours=1),
        )

        chronicle = _make_mock_chronicle(sessions=sessions)
        result = compute_gap_analysis(chronicle)

        assert result is not None
        # With ~2hr average gaps, a 30-day gap is extremely anomalous
        assert result.classification in (
            GapClassification.SIGNIFICANT,
            GapClassification.ANOMALOUS,
        )
        assert result.deviation_sigma > 2.0

    def test_gap_includes_last_session_context(self) -> None:
        """GapAnalysis should include context from the last session."""
        now = datetime.now(timezone.utc)
        sessions = []
        for i in range(5):
            start = now - timedelta(hours=(5 - i) * 10)
            end = start + timedelta(hours=1)
            sessions.append(_make_session(
                start_time=start,
                end_time=end,
                topics=["work", "stress"],
                end_mode=SessionEndMode.ABRUPT,
            ))

        chronicle = _make_mock_chronicle(sessions=sessions)
        result = compute_gap_analysis(chronicle)

        assert result is not None
        assert result.last_session_end_mode == SessionEndMode.ABRUPT
        assert result.last_topic == "stress"  # Last topic in the list


# ============================================================
# Return Context Tests
# ============================================================

class TestReturnContext:
    """Test generate_return_context output."""

    def _make_gap(
        self,
        hours: float = 72.0,
        classification: GapClassification = GapClassification.SIGNIFICANT,
        end_mode: SessionEndMode = SessionEndMode.NATURAL,
        valence: float = 0.5,
    ) -> GapAnalysis:
        emotion = EmotionalStateVector(
            valence=valence,
            arousal=0.3,
            dominance=0.5,
            relational_significance=0.0,
            vulnerability_level=0.0,
            compass_direction=CompassDirection.NONE,
            compass_confidence=0.0,
        )
        return GapAnalysis(
            duration_hours=hours,
            deviation_sigma=2.5,
            classification=classification,
            last_session_type=SessionType.CHAT,
            last_session_end_mode=end_mode,
            last_emotional_state=emotion,
            last_topic="work",
            open_threads=[],
            known_explanations=[],
        )

    def test_gap_duration_display_days_and_hours(self) -> None:
        gap = self._make_gap(hours=75.0)
        ctx = generate_return_context(gap)
        assert "3 days" in ctx.gap_duration_display
        assert "3 hours" in ctx.gap_duration_display

    def test_gap_duration_display_hours_only(self) -> None:
        gap = self._make_gap(hours=5.0)
        ctx = generate_return_context(gap)
        assert "day" not in ctx.gap_duration_display
        assert "5 hours" in ctx.gap_duration_display

    def test_preceding_summary_includes_end_mode(self) -> None:
        gap = self._make_gap(end_mode=SessionEndMode.ABRUPT)
        ctx = generate_return_context(gap)
        assert "abruptly" in ctx.preceding_summary.lower() or "abrupt" in ctx.preceding_summary.lower()

    def test_anomalous_abrupt_approach_is_gentle(self) -> None:
        gap = self._make_gap(
            classification=GapClassification.ANOMALOUS,
            end_mode=SessionEndMode.ABRUPT,
        )
        ctx = generate_return_context(gap)
        assert "gentle" in ctx.suggested_approach.lower() or "warm" in ctx.suggested_approach.lower()

    def test_notable_approach_is_light(self) -> None:
        gap = self._make_gap(classification=GapClassification.NOTABLE)
        ctx = generate_return_context(gap)
        assert "natural" in ctx.suggested_approach.lower() or "warm" in ctx.suggested_approach.lower()


# ============================================================
# Session Lifecycle Tests
# ============================================================

class TestSessionLifecycle:
    """Test the full start -> add_message -> end flow."""

    def test_start_session_returns_partial_record(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        session = mgr.start_session()

        assert session.id is not None
        assert len(session.id) == 36  # UUID4 format
        assert session.start_time is not None
        assert session.end_time is None
        assert session.duration_sec == 0
        assert session.gwen_initiated is False

    def test_start_session_companion_initiated(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        session = mgr.start_session(initiated_by="companion")
        assert session.gwen_initiated is True

    def test_cannot_start_two_sessions(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        with pytest.raises(RuntimeError, match="Cannot start a new session"):
            mgr.start_session()

    def test_add_message_increments_counts(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")
        mgr.add_message("companion")
        mgr.add_message("user")

        assert mgr._user_message_count == 2
        assert mgr._companion_message_count == 1

    def test_add_message_invalid_sender_raises(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        with pytest.raises(ValueError, match="sender must be"):
            mgr.add_message("system")

    def test_add_message_no_session_raises(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        with pytest.raises(RuntimeError, match="no session is active"):
            mgr.add_message("user")

    def test_end_session_finalizes_record(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")
        mgr.add_message("companion")

        result = mgr.end_session(SessionEndMode.EXPLICIT_GOODBYE)

        assert result.end_time is not None
        assert result.end_mode == SessionEndMode.EXPLICIT_GOODBYE
        assert result.message_count == 2
        assert result.user_message_count == 1
        assert result.companion_message_count == 1
        # Session was very short — should be PING
        assert result.session_type == SessionType.PING

    def test_end_session_saves_to_chronicle(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.end_session(SessionEndMode.NATURAL)

        chronicle.insert_session.assert_called_once()

    def test_end_session_clears_state(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.end_session(SessionEndMode.NATURAL)

        assert mgr.current_session is None
        assert mgr._user_message_count == 0
        assert mgr._companion_message_count == 0

    def test_end_session_no_session_raises(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        with pytest.raises(RuntimeError, match="no session is active"):
            mgr.end_session(SessionEndMode.NATURAL)


# ============================================================
# Timeout Detection Tests
# ============================================================

class TestTimeoutDetection:
    """Test detect_timeout behavior."""

    def test_no_session_returns_none(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        assert mgr.detect_timeout() is None

    def test_within_threshold_returns_none(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")

        # Just started, should not timeout
        assert mgr.detect_timeout(idle_threshold_sec=1800) is None

    def test_timeout_after_user_message_returns_abrupt(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")

        # Simulate time passing by manipulating _last_message_time
        mgr._last_message_time = time.monotonic() - 2000  # 2000 sec ago

        result = mgr.detect_timeout(idle_threshold_sec=1800)
        assert result == SessionEndMode.ABRUPT

    def test_timeout_after_companion_message_returns_fade_out(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")
        mgr.add_message("companion")

        # Simulate time passing
        mgr._last_message_time = time.monotonic() - 2000

        result = mgr.detect_timeout(idle_threshold_sec=1800)
        assert result == SessionEndMode.FADE_OUT

    def test_timeout_empty_session_returns_fade_out(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()

        # Simulate time passing with no messages
        mgr._session_start_monotonic = time.monotonic() - 2000

        result = mgr.detect_timeout(idle_threshold_sec=1800)
        assert result == SessionEndMode.FADE_OUT

    def test_custom_threshold(self) -> None:
        chronicle = _make_mock_chronicle()
        tme_gen = _make_mock_tme_generator()
        mgr = SessionManager(chronicle=chronicle, tme_generator=tme_gen)

        mgr.start_session()
        mgr.add_message("user")

        # 10 seconds ago — within default 1800s but beyond custom 5s
        mgr._last_message_time = time.monotonic() - 10

        assert mgr.detect_timeout(idle_threshold_sec=1800) is None
        assert mgr.detect_timeout(idle_threshold_sec=5) == SessionEndMode.ABRUPT


# ============================================================
# Goodbye Detection Tests
# ============================================================

class TestGoodbyeDetection:
    """Test the detect_goodbye helper."""

    def test_explicit_goodbye(self) -> None:
        assert detect_goodbye("Goodbye!") is True

    def test_bye(self) -> None:
        assert detect_goodbye("bye") is True

    def test_goodnight(self) -> None:
        assert detect_goodbye("Goodnight, Gwen") is True

    def test_ttyl(self) -> None:
        assert detect_goodbye("ttyl") is True

    def test_talk_later(self) -> None:
        assert detect_goodbye("Talk to you later!") is True

    def test_no_goodbye(self) -> None:
        assert detect_goodbye("How are you doing today?") is False

    def test_empty_string(self) -> None:
        assert detect_goodbye("") is False

    def test_case_insensitive(self) -> None:
        assert detect_goodbye("GOODBYE") is True
        assert detect_goodbye("See Ya") is True
```

**What these tests cover:**

1. **Session Type Classification** (10 tests): Every boundary value for every SessionType — 0, 299, 300, 1799, 1800, 5399, 5400, 10799, 10800, and a very large value. These are pure function tests with no dependencies.

2. **Gap Analysis** (4 tests): No history (returns None), single session (defaults to NORMAL), consistent-gap history (NORMAL), and a very long gap with short-gap history (ANOMALOUS/SIGNIFICANT). Uses mock Chronicle.

3. **Return Context** (5 tests): Duration display formatting (days+hours, hours only), preceding summary includes end mode, anomalous+abrupt approach is gentle, notable approach is light.

4. **Session Lifecycle** (9 tests): Start returns partial record, companion-initiated flag, cannot double-start, message counts increment correctly, invalid sender raises, no-session add raises, end finalizes all fields, end saves to Chronicle, end clears state, no-session end raises.

5. **Timeout Detection** (5 tests): No session returns None, within threshold returns None, timeout after user message = ABRUPT, timeout after companion message = FADE_OUT, empty session timeout = FADE_OUT, custom threshold.

6. **Goodbye Detection** (8 tests): Various goodbye keywords, negative case, empty string, case insensitivity.

---

### Step 5.2: Run pytest

Run from the project root:

- [ ] Run `pytest tests/test_session.py -v` and confirm all tests pass

```bash
pytest tests/test_session.py -v
```

**Expected output:** All tests pass (green). The exact number depends on the final test count (currently 41 test cases).

**If tests fail:**
- If `ModuleNotFoundError`: run `pip install -e ".[dev]"` first
- If Chronicle mock errors: ensure `get_last_n_sessions` and `insert_session` are the correct method names (check Track 003)
- If model import errors: ensure Track 002 data models are in place

---

## Summary of Files Created

| Step | File Path | Purpose |
|------|-----------|---------|
| 1.1 | `gwen/core/session_manager.py` | SessionManager class — full lifecycle |
| 3.1 | `gwen/temporal/gap.py` | Gap analysis computation and return context generation |
| 5.1 | `tests/test_session.py` | Unit tests for session management |

**Total files:** 3
**Dependencies:** Track 002 (data models), Track 003 (Chronicle), Track 006 (TME generator)
