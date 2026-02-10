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

from datetime import datetime, timezone
from typing import Optional

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.messages import (
    MessageRecord,
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
        1. Compute end_time and duration if not already set
        2. Classify session type from duration
        3. Compute emotional arc (opening, peak, closing states)
        4. Compute average emotional intensity and relational significance
        5. Compute subjective time weight
        6. Compute message count statistics
        7. Extract topics from messages
        8. Compute compass activation counts
        9. Set relational_field_delta to empty dict (placeholder for Track 017)
        10. Save the finalized SessionRecord to Chronicle
        11. Clear the Stream (working memory)
        12. Return the finalized SessionRecord

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

        # Normalise both timestamps to avoid naive/aware mismatch
        end = session.end_time
        start = session.start_time
        if end.tzinfo is not None and start.tzinfo is None:
            start = start.replace(tzinfo=end.tzinfo)
        elif start.tzinfo is not None and end.tzinfo is None:
            end = end.replace(tzinfo=start.tzinfo)

        duration_sec = int((end - start).total_seconds())
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

    Topics are sourced from the compass_skill_used field on each message.
    A richer topic extraction (using Tier 0 topic field) will be available
    in later tracks.

    Parameters
    ----------
    messages : list[MessageRecord]
        All messages in the session.

    Returns
    -------
    list[str]
        Deduplicated, sorted list of topic strings. May be empty.
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
    last_standard_consolidation_time : datetime, optional
        When the last standard consolidation ran. If None, consolidation
        is assumed to have never run, and the function returns True.

    Returns
    -------
    bool
        True if standard consolidation should be triggered, False otherwise.
    """
    now = datetime.now(timezone.utc)

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
    # chronicle may not yet have the get_sessions_since method.
    try:
        recent_sessions = chronicle.get_sessions_since(
            last_standard_consolidation_time
        )
        if len(recent_sessions) >= STANDARD_CONSOLIDATION_SESSION_THRESHOLD:
            return True
    except AttributeError:
        pass

    return False
