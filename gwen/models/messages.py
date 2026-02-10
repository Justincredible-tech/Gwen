"""Message and session record models.

Defines the fundamental units of conversation storage: individual messages
(MessageRecord) and complete sessions (SessionRecord).
Reference: SRS.md Sections 3.3, 3.4, 3.12
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.temporal import TemporalMetadataEnvelope, TimePhase


class SessionType(Enum):
    """Classification of session by duration.

    Determined when a session ends, based on total elapsed time.
    Used for pattern analysis and the Bond's relational rhythm tracking.
    """

    PING = "ping"               # Less than 5 minutes
    CHAT = "chat"               # 5-30 minutes
    HANG = "hang"               # 30-90 minutes
    DEEP_DIVE = "deep_dive"     # 90-180 minutes
    MARATHON = "marathon"       # 180+ minutes


class SessionEndMode(Enum):
    """How a session ended.

    Detected by the Session Manager based on behavioral signals.
    Critical for Gap Analysis: an ABRUPT or MID_TOPIC ending followed
    by a long gap is treated differently than a NATURAL ending.
    """

    NATURAL = "natural"                     # Mutual goodbye, clean ending
    ABRUPT = "abrupt"                       # User left suddenly mid-conversation
    FADE_OUT = "fade_out"                   # User stopped responding, session timed out
    MID_TOPIC = "mid_topic"                 # Left in the middle of an emotionally loaded topic
    EXPLICIT_GOODBYE = "explicit_goodbye"   # User said goodbye explicitly


@dataclass
class MessageRecord:
    """A single message in a conversation, stored in the Chronicle.

    This is the fundamental unit of conversation storage. Every user message
    and every companion response becomes a MessageRecord. The record includes
    the raw content, the temporal context at the time of the message, the
    emotional tagging applied by the Amygdala Layer, and references to
    vector embeddings in ChromaDB.

    Reference: SRS.md Section 3.3
    """

    id: str                             # UUID string
    session_id: str                     # Which session this belongs to
    timestamp: datetime
    sender: str                         # "user" or "companion"
    content: str                        # The raw message text

    # Temporal context (snapshot of TME at time of message)
    tme: TemporalMetadataEnvelope

    # Emotional tagging (applied by Amygdala Layer via Tier 0)
    emotional_state: EmotionalStateVector

    # Storage modulation (computed by Amygdala Layer)
    storage_strength: float             # 0.0-1.0, from EmotionalStateVector
    is_flashbulb: bool                  # High-arousal + high-significance

    # Compass activation
    compass_direction: CompassDirection
    compass_skill_used: Optional[str]   # e.g., "fuel_check", "anchor_breath"

    # Embedding references (populated after encoding)
    semantic_embedding_id: Optional[str] = None    # ChromaDB ID
    emotional_embedding_id: Optional[str] = None   # ChromaDB ID


@dataclass
class SessionRecord:
    """A complete conversation session.

    Created when a session starts, updated continuously, finalized when
    the session ends. The emotional arc captures the trajectory from
    opening to closing. The subjective duration weight is used by the
    temporal system to weigh "felt time" vs clock time.

    Reference: SRS.md Section 3.4
    """

    id: str                                     # UUID string
    start_time: datetime
    end_time: Optional[datetime]
    duration_sec: int
    session_type: SessionType
    end_mode: SessionEndMode

    # Emotional arc
    opening_emotional_state: EmotionalStateVector
    peak_emotional_state: EmotionalStateVector          # Highest arousal point
    closing_emotional_state: EmotionalStateVector
    emotional_arc_embedding_id: Optional[str]           # ChromaDB ID for arc similarity

    # Subjective time weight
    avg_emotional_intensity: float
    avg_relational_significance: float
    subjective_duration_weight: float   # clock_duration * intensity * significance

    # Statistics
    message_count: int
    user_message_count: int
    companion_message_count: int
    avg_response_latency_sec: float

    # Compass activity
    compass_activations: dict = field(default_factory=dict)  # {CompassDirection.value: count}

    # Conversation topics (extracted by Tier 0)
    topics: list[str] = field(default_factory=list)

    # Relational delta (how did the relationship change?)
    relational_field_delta: dict = field(default_factory=dict)  # {dimension: change_amount}

    # Was this session initiated by the Autonomy Engine?
    gwen_initiated: bool = False


class ConsolidationType(Enum):
    """The three consolidation passes that refine memory over time.

    LIGHT runs after every session ends.
    STANDARD runs every 6-12 hours during idle periods.
    DEEP runs weekly or after major emotional events.
    Reference: SRS.md Section 3.12
    """

    LIGHT = "light"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass
class ConsolidationJob:
    """Record of a consolidation run.

    Tracks what was processed and what was produced, for auditability
    and debugging. Stored in SQLite alongside session records.

    Reference: SRS.md Section 3.12
    """

    id: str                                     # UUID string
    type: ConsolidationType
    started_at: datetime
    completed_at: Optional[datetime]

    # What was processed
    sessions_processed: list[str] = field(default_factory=list)  # Session IDs

    # Results summary
    map_entities_created: int = 0
    map_entities_updated: int = 0
    map_edges_created: int = 0
    pulse_baselines_updated: bool = False
    trigger_map_entries_updated: int = 0
    bond_field_updated: bool = False
    reconsolidation_events: int = 0
    anticipatory_primes_generated: int = 0
    decay_events_processed: int = 0

    # Error tracking
    errors: list[str] = field(default_factory=list)
