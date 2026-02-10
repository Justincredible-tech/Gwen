"""Stream: Tier 1 of the Living Memory system (working memory).

The Stream holds the most recent messages from the active conversation session.
It is the in-memory buffer that the Context Assembler reads from when building
the Tier 1 prompt. Messages are added as the conversation progresses and cleared
when the session ends.

References: SRS.md Section 4.5 (Context Assembly, component 6: Conversation History),
            SRS.md Section 6 (Living Memory, Tier 1: Stream).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from gwen.models.emotional import EmotionalStateVector

logger = logging.getLogger(__name__)


class Stream:
    """Working memory buffer for the active conversation session.

    Holds the most recent messages as a list of dicts. The Context Assembler
    reads from this buffer to build conversation history in the Tier 1 prompt.

    Each message in the stream is a dict with these keys:
        - "role" (str): Either "user" or "companion"
        - "content" (str): The message text
        - "emotional_state" (EmotionalStateVector | None): The emotional classification
        - "timestamp" (datetime): When the message was created

    Usage:
        stream = Stream(max_messages=50)
        stream.add_message("user", "Hello!")
        stream.add_message("companion", "Hi there! How are you?")
        recent = stream.get_recent(10)
        formatted = stream.get_formatted(10)
    """

    def __init__(self, max_messages: int = 50):
        self.max_messages = max_messages
        self._messages: list[dict] = []

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def add_message(
        self,
        role: str,
        content: str,
        emotional_state: Optional[EmotionalStateVector] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a message to the stream.

        If the stream is at capacity, the oldest message is removed first.
        """
        if role not in ("user", "companion"):
            logger.warning("Unexpected role '%s' added to stream.", role)

        if not content:
            logger.warning("Empty content added to stream for role '%s'.", role)

        if timestamp is None:
            timestamp = datetime.now()

        message = {
            "role": role,
            "content": content,
            "emotional_state": emotional_state,
            "timestamp": timestamp,
        }

        if len(self._messages) >= self.max_messages:
            self._messages.pop(0)

        self._messages.append(message)

    def get_recent(self, n: int) -> list[dict]:
        """Return the last n messages, oldest first."""
        if n <= 0:
            return []
        return self._messages[-n:]

    def get_formatted(self, n: int) -> str:
        """Format the last n messages as a conversation transcript.

        Produces a string like:
            User: Hello!
            Gwen: Hi there! How are you?
        """
        messages = self.get_recent(n)
        lines = []
        for msg in messages:
            if msg["role"] == "user":
                speaker = "User"
            elif msg["role"] == "companion":
                speaker = "Gwen"
            else:
                speaker = msg["role"].capitalize()
            lines.append(f"{speaker}: {msg['content']}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all messages from the stream."""
        count = len(self._messages)
        self._messages.clear()
        logger.debug("Stream cleared. Removed %d messages.", count)


def estimate_tokens(text: str) -> int:
    """Rough token count estimation: 1 token ~ 4 characters.

    This approximation errs on the side of overestimation, which is the
    safe direction for budget management.
    """
    if not text:
        return 0
    return len(text) // 4


def generate_temporal_block(
    tme: object,
    gap_analysis: object = None,
    anticipatory_primes: list | None = None,
) -> str:
    """Generate a natural-language temporal context block for the Tier 1 prompt.

    Gives Tier 1 awareness of time, session context, and temporal anomalies.
    Kept under ~300 tokens (~1200 chars).

    Args:
        tme: A TemporalMetadataEnvelope instance (duck-typed).
        gap_analysis: Optional GapAnalysis instance.
        anticipatory_primes: Optional list of AnticipatoryPrime instances.

    Returns:
        A natural-language string describing the temporal context.
    """
    parts = []

    # --- Time of day ---
    try:
        day_name = tme.day_of_week
        phase = tme.time_phase.value.replace("_", " ")
        hour = tme.hour_of_day
        local_time = getattr(tme, "local_time", None)
        if local_time is not None and hasattr(local_time, "strftime"):
            time_str = local_time.strftime("%I:%M %p").lstrip("0")
        else:
            period = "AM" if hour < 12 else "PM"
            display_hour = hour % 12 or 12
            time_str = f"{display_hour}:00 {period}"
        parts.append(f"Current time: {day_name} {phase} ({time_str}).")
    except AttributeError:
        parts.append("Current time: unknown.")

    # --- Session context ---
    try:
        duration_min = tme.session_duration_sec // 60
        msg_index = tme.msg_index_in_session

        if msg_index == 1:
            ordinal = "1st"
        elif msg_index == 2:
            ordinal = "2nd"
        elif msg_index == 3:
            ordinal = "3rd"
        else:
            ordinal = f"{msg_index}th"

        parts.append(f"Session started {duration_min} minutes ago, {ordinal} message.")
    except AttributeError:
        pass

    # --- Circadian deviation ---
    try:
        severity = tme.circadian_deviation_severity
        severity_val = severity.value if hasattr(severity, "value") else str(severity)

        if severity_val == "none":
            parts.append("No circadian anomalies detected.")
        elif severity_val == "low":
            parts.append("Slight circadian deviation noted (mildly unusual time for this user).")
        elif severity_val == "medium":
            deviation_type = getattr(tme, "circadian_deviation_type", "unusual hour")
            parts.append(f"Moderate circadian deviation: {deviation_type}. This is somewhat unusual for this user.")
        elif severity_val == "high":
            deviation_type = getattr(tme, "circadian_deviation_type", "unusual hour")
            parts.append(f"Significant circadian deviation: {deviation_type}. This is very unusual for this user and may signal distress or a change in routine.")
    except AttributeError:
        pass

    # --- Gap context ---
    if gap_analysis is not None:
        try:
            classification = gap_analysis.classification
            classification_val = classification.value if hasattr(classification, "value") else str(classification)

            if classification_val in ("notable", "significant", "anomalous"):
                hours = gap_analysis.duration_hours
                if hours < 24:
                    gap_display = f"{hours:.0f} hours"
                else:
                    days = hours / 24
                    gap_display = f"{days:.1f} days"
                parts.append(f"User is returning after a {classification_val} absence ({gap_display}).")
        except AttributeError:
            pass

    # --- Anticipatory primes ---
    if anticipatory_primes:
        try:
            active_primes = [p for p in anticipatory_primes if hasattr(p, "prediction")]
            if active_primes:
                prime_descriptions = [p.prediction.replace("_", " ") for p in active_primes[:3]]
                parts.append(f"Active predictions: {', '.join(prime_descriptions)}.")
        except (AttributeError, TypeError):
            pass

    return " ".join(parts)
