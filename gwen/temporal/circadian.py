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
        return [h for h, _ in sorted_hours[:top_n]]
