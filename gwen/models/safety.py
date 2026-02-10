"""Safety models for the Safety Architecture.

Defines threat classifications, safety events logged to the encrypted
Safety Ledger, and wellness checkpoint records.
Reference: SRS.md Section 3.10
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from gwen.models.emotional import CompassDirection
from gwen.models.temporal import CircadianDeviationSeverity, TimePhase


class ThreatVector(Enum):
    """The four threat vectors the Safety Architecture monitors for.

    Each vector has its own detection rules and response protocols.
    The Safety Monitor evaluates every message against all four vectors.
    """

    SELF_HARM = "self_harm"
    VIOLENCE = "violence"
    DISSOCIATION = "dissociation"
    SAVIOR_DELUSION = "savior_delusion"


class ThreatSeverity(Enum):
    """Severity levels for detected threats.

    Each level triggers a different response protocol:
    - LOW: signal detected, monitoring continues
    - MEDIUM: pattern emerging, Compass activation
    - HIGH: threshold crossed, safety protocol active
    - CRITICAL: immediate intervention required
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SafetyEvent:
    """Logged in the encrypted Safety Ledger.

    Every safety-relevant detection is recorded as a SafetyEvent. These
    records are encrypted with Fernet and stored separately from regular
    conversation data. They are used for pattern analysis and audit trails.

    Reference: SRS.md Section 3.10
    """

    id: str                             # UUID string
    timestamp: datetime
    vector: ThreatVector
    severity: ThreatSeverity

    # What triggered this
    trigger_message_id: Optional[str]
    trigger_description: str

    # Temporal context at time of detection
    time_phase: TimePhase
    session_duration_sec: int
    circadian_deviation: CircadianDeviationSeverity

    # What the system did
    response_action: str                # "compass_activation", "resource_overlay", etc.
    compass_direction_used: Optional[CompassDirection]

    # Outcome
    user_response: Optional[str] = None     # How the user reacted to the intervention
    resolved: bool = False


@dataclass
class WellnessCheckpoint:
    """48-hour wellness checkpoint record.

    In Immersion Mode, after 48 hours of cumulative interaction, the system
    pauses to ask three grounding questions. This record captures both the
    questions/answers and the system's assessment.

    Reference: SRS.md Section 3.10
    """

    id: str                             # UUID string
    timestamp: datetime
    immersion_hours_since_last: float

    # The three questions and responses
    q1_last_human_conversation: str
    q2_life_outside_gwen: str
    q3_avoiding_anything: str

    # System assessment
    concern_flags: list[str] = field(default_factory=list)   # Flagged phrases/patterns
    escalated: bool = False             # Did this trigger an intervention?
