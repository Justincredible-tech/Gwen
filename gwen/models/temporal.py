"""Temporal metadata models for the Temporal Cognition System.

Defines time phases, circadian deviation tracking, and the Temporal
Metadata Envelope (TME) that wraps every message before it reaches any model.
Reference: SRS.md Section 3.2
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class TimePhase(Enum):
    """The seven phases of the day, used for circadian awareness.

    Each phase has a distinct behavioral and emotional baseline.
    The Temporal Cognition System uses these to detect anomalies
    (e.g., the user is awake during DEEP_NIGHT when they normally sleep).
    """

    DEEP_NIGHT = "deep_night"           # 00:00 - 04:59
    EARLY_MORNING = "early_morning"     # 05:00 - 07:59
    MORNING = "morning"                 # 08:00 - 11:59
    MIDDAY = "midday"                   # 12:00 - 13:59
    AFTERNOON = "afternoon"             # 14:00 - 16:59
    EVENING = "evening"                 # 17:00 - 20:59
    LATE_NIGHT = "late_night"           # 21:00 - 23:59


class CircadianDeviationSeverity(Enum):
    """How far the user's current activity deviates from their established pattern.

    Computed by comparing the current TimePhase to the user's historical
    activity patterns stored in the Bond.
    """

    NONE = "none"       # Normal activity time
    LOW = "low"         # Slightly unusual but not concerning
    MEDIUM = "medium"   # Notably outside pattern
    HIGH = "high"       # Significantly anomalous (e.g., 3am when user is never up)


@dataclass
class TemporalMetadataEnvelope:
    """Wraps every message before it reaches any model.

    The TME is computed entirely by the orchestrator from system clocks and
    session state stored in SQLite. It costs zero inference tokens. It is
    generated before every model call.

    Reference: SRS.md Section 3.2
    """

    # Absolute time
    timestamp_utc: datetime
    local_time: datetime

    # Clock position
    hour_of_day: int                # 0-23
    day_of_week: str                # "Monday" through "Sunday"
    day_of_month: int               # 1-31
    month: int                      # 1-12
    year: int
    is_weekend: bool
    time_phase: TimePhase

    # Session context
    session_id: str                 # UUID string
    session_start: datetime
    session_duration_sec: int
    msg_index_in_session: int       # 0-based index of this message in the session

    # Intra-message timing
    time_since_last_msg_sec: Optional[float]        # None if first message in session
    time_since_last_user_msg_sec: Optional[float]
    time_since_last_gwen_msg_sec: Optional[float]
    user_msgs_last_5min: int
    user_msgs_last_hour: int
    user_msgs_last_24hr: int

    # Inter-session timing
    last_session_end: Optional[datetime]
    hours_since_last_session: Optional[float]
    sessions_last_7_days: int
    sessions_last_30_days: int
    avg_session_gap_30d_hours: Optional[float]

    # Circadian deviation (computed by orchestrator)
    circadian_deviation_severity: CircadianDeviationSeverity
    circadian_deviation_type: Optional[str]     # "early_wake", "late_still_up", etc.
