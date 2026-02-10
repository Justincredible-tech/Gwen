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
        self._last_msg_time: Optional[datetime] = None
        self._last_user_msg_time: Optional[datetime] = None
        self._last_companion_msg_time: Optional[datetime] = None

        # Rolling counters for message density
        self._user_msg_timestamps: list[datetime] = []

    def start_session(self, session_id: Optional[str] = None) -> str:
        """Start a new session and reset all session-scoped state.

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

    def generate(self, message_sender: str) -> TemporalMetadataEnvelope:
        """Generate a complete TME for the current message.

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
        day_of_week: str = now.strftime("%A")
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
        circadian_deviation_severity: CircadianDeviationSeverity = (
            CircadianDeviationSeverity.NONE
        )
        circadian_deviation_type: Optional[str] = None

        # --- Update internal state AFTER computing the TME ---
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

    def _compute_intra_message_timing(
        self,
        now: datetime,
        message_sender: str,
    ) -> dict:
        """Compute timing between messages within the current session."""
        time_since_last_msg_sec: Optional[float] = None
        if self._last_msg_time is not None:
            delta = (now - self._last_msg_time).total_seconds()
            time_since_last_msg_sec = delta

        time_since_last_user_msg_sec: Optional[float] = None
        if self._last_user_msg_time is not None:
            delta = (now - self._last_user_msg_time).total_seconds()
            time_since_last_user_msg_sec = delta

        time_since_last_gwen_msg_sec: Optional[float] = None
        if self._last_companion_msg_time is not None:
            delta = (now - self._last_companion_msg_time).total_seconds()
            time_since_last_gwen_msg_sec = delta

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

    def _compute_inter_session_timing(self) -> dict:
        """Compute timing between sessions by querying the Chronicle."""
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

        try:
            last_session_end: Optional[datetime] = (
                self._chronicle.get_last_session_end(
                    exclude_session_id=self._session_id
                )
            )
        except (AttributeError, Exception):
            return defaults

        hours_since_last_session: Optional[float] = None
        if last_session_end is not None:
            delta = (now - last_session_end).total_seconds() / 3600.0
            hours_since_last_session = delta

        cutoff_7d: datetime = now - timedelta(days=7)
        cutoff_30d: datetime = now - timedelta(days=30)

        try:
            sessions_last_7_days: int = (
                self._chronicle.count_sessions_since(cutoff_7d)
            )
            sessions_last_30_days: int = (
                self._chronicle.count_sessions_since(cutoff_30d)
            )
        except (AttributeError, Exception):
            sessions_last_7_days = 0
            sessions_last_30_days = 0

        avg_session_gap_30d_hours: Optional[float] = None
        try:
            session_times: list[datetime] = (
                self._chronicle.get_session_start_times_since(cutoff_30d)
            )
            if len(session_times) >= 2:
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
