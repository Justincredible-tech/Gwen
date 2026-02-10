"""Conversation Rhythm Tracker — monitors message density and latency.

Tracks message timestamps within a single session and detects anomalies
such as sudden pauses (user stopped replying for much longer than usual)
and acceleration (user is typing much faster than usual, possibly
indicating agitation).

Reference: SRS.md Section 7
"""

import logging
from datetime import datetime
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
