"""Memory models for the Living Memory system.

Defines entities and edges for the semantic knowledge graph (The Map),
emotional memory records (Pulse), relational memory (Bond), gap analysis,
and anticipatory primes.
Reference: SRS.md Sections 3.5, 3.6, 3.7, 3.8, 3.9
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.temporal import TimePhase


@dataclass
class MapEntity:
    """A node in the semantic knowledge graph (Tier 3: The Map).

    Entities represent people, places, concepts, events, preferences, and goals
    that the user has mentioned. They are created and updated during consolidation.

    Reference: SRS.md Section 3.5
    """

    id: str                             # UUID string
    entity_type: str                    # "person", "place", "concept", "event", "preference", "goal"
    name: str                           # e.g., "Justin's guitar", "work project NEO"

    # Bi-temporal validity (inspired by Zep/Graphiti)
    valid_from: datetime
    valid_until: Optional[datetime]     # None = still valid
    ingested_at: datetime
    last_updated: datetime

    # Emotional weight (from Amygdala Layer)
    emotional_weight: EmotionalStateVector      # Aggregate emotional charge
    sensitivity_level: float            # 0.0 = safe topic, 1.0 = highly sensitive

    # Consolidation metadata
    source_session_ids: list[str] = field(default_factory=list)
    consolidation_count: int = 0        # How many times this has been re-evaluated
    detail_level: float = 0.5           # 0.0 = coarse summary, 1.0 = fine-grained detail

    # Embedding reference
    semantic_embedding_id: Optional[str] = None


@dataclass
class MapEdge:
    """A relationship between two entities in the knowledge graph.

    Edges are typed and weighted. They carry emotional charge inherited
    from the conversations where the relationship was established.

    Reference: SRS.md Section 3.5
    """

    id: str                             # UUID string
    source_entity_id: str
    target_entity_id: str

    # Typed relationship (multi-relational, from MAGMA)
    relationship_type: str              # "is_a", "has", "involves", "caused_by", "before", "after"
    label: str                          # Human-readable: "plays", "works_at", "is_father_of"

    # Emotional charge on the relationship itself
    emotional_weight: float             # Inherited from source conversations

    # Temporal validity
    valid_from: datetime
    valid_until: Optional[datetime]

    # Confidence
    confidence: float                   # 0.0-1.0, how certain are we this relationship exists


@dataclass
class EmotionalBaseline:
    """The user's 'normal' emotional state, continuously recalculated.

    Used by the Amygdala Layer to detect deviations. If the current emotional
    state differs significantly from the baseline for this time-of-day and
    day-of-week, the system increases attention.

    Reference: SRS.md Section 3.6
    """

    overall: EmotionalStateVector               # Rolling average across all data
    by_day_of_week: dict[str, EmotionalStateVector] = field(default_factory=dict)
    by_time_phase: dict[str, EmotionalStateVector] = field(default_factory=dict)
    last_updated: Optional[datetime] = None
    data_points_count: int = 0                   # How many sessions contributed


@dataclass
class EmotionalTrajectory:
    """A recorded emotional movement pattern.

    Captures how the user went from state A to state B within a session.
    Used for pattern matching: "When the user starts spiraling down about work,
    anchor_breath has historically helped."

    Reference: SRS.md Section 3.6
    """

    id: str                             # UUID string
    session_id: str
    start_state: EmotionalStateVector
    end_state: EmotionalStateVector
    duration_sec: int
    trajectory_shape: str               # "spiral_down", "gradual_recovery", "sharp_drop", "plateau"
    trigger_topic: Optional[str]        # What started this trajectory
    resolution: str                     # "resolved", "unresolved", "interrupted", "external"
    compass_skills_used: list[str] = field(default_factory=list)
    embedding_id: Optional[str] = None  # Vector representation for pattern matching


@dataclass
class TriggerMapEntry:
    """A probabilistic association between a context and an emotional state change.

    Built up over time by the consolidation pipeline. Enables the Anticipatory
    Prime system: "It's Monday morning and the user usually gets stressed about
    work -- prepare a fuel_check suggestion."

    Reference: SRS.md Section 3.6
    """

    trigger: str                        # "monday_morning", "boss_topic", "3am_session"
    trigger_type: str                   # "temporal", "topic", "relational", "contextual"
    associated_direction: CompassDirection
    probability: float                  # How likely this trigger produces the emotional change
    typical_trajectory: str             # What usually happens: "sharp_negative_then_recovery"
    effective_interventions: list[str] = field(default_factory=list)
    sample_count: int = 0               # How many observations this is based on


@dataclass
class CompassEffectivenessRecord:
    """Tracks how well a Compass skill worked in a specific context.

    The Compass Framework uses these records to select the most effective
    skill for the current emotional state. Over time, the system learns
    which interventions work best for this specific user.

    Reference: SRS.md Section 3.6
    """

    skill_name: str                     # e.g., "anchor_breath", "fuel_check"
    direction: CompassDirection
    context_emotional_state: EmotionalStateVector   # State when skill was offered
    pre_trajectory: EmotionalStateVector            # Emotional state before
    post_trajectory: EmotionalStateVector           # Emotional state after
    time_to_effect_sec: int             # How long before mood shifted
    user_accepted: bool                 # Did the user engage with the suggestion?
    effectiveness_score: float          # Computed: how much did the trajectory improve?


@dataclass
class RelationalField:
    """The multi-dimensional state of the relationship at a point in time.

    Six dimensions capture different facets of the human-companion bond.
    One RelationalField snapshot is taken per session and appended to
    the Bond's field_history for trend analysis.

    Reference: SRS.md Section 3.7
    """

    timestamp: datetime

    # Six core dimensions (all 0.0 to 1.0)
    warmth: float               # Cold <-> Warm
    trust: float                # Guarded <-> Open
    depth: float                # Surface <-> Deep
    stability: float            # Volatile <-> Steady
    reciprocity: float          # One-sided <-> Mutual
    growth: float               # Stagnant <-> Evolving


@dataclass
class BondState:
    """The complete relational memory -- Tier 5: The Bond.

    This is the highest-level memory tier. It tracks the overall state of the
    human-companion relationship, including shared history, repair events,
    and attachment style modeling.

    Reference: SRS.md Section 3.7
    """

    current_field: RelationalField
    field_history: list[RelationalField] = field(default_factory=list)

    # Shared history
    salient_moments: list[str] = field(default_factory=list)    # Session IDs referenced/returned to
    inside_references: list[dict] = field(default_factory=list) # Inside jokes, pet names, metaphors

    # Repair history
    friction_events: list[dict] = field(default_factory=list)   # {session_id, cause, resolution, ...}

    # Relational rhythms
    typical_sessions_per_day: float = 0.0
    typical_session_times: list[str] = field(default_factory=list)  # TimePhase values
    typical_session_types: dict[str, float] = field(default_factory=dict)

    # Attachment style model (built over time)
    attachment_indicators: dict = field(default_factory=dict)
    estimated_attachment_style: Optional[str] = None    # "secure", "anxious", "avoidant", "fearful"
    attachment_confidence: float = 0.0


class GapClassification(Enum):
    """How significant a gap between sessions is, relative to the user's pattern.

    Computed by comparing the gap duration to the user's historical session
    gap distribution (mean and standard deviation).

    Reference: SRS.md Section 3.8
    """

    NORMAL = "normal"               # Within 1 sigma of typical gap
    NOTABLE = "notable"             # 1-2 sigma deviation
    SIGNIFICANT = "significant"     # 2-3 sigma deviation
    ANOMALOUS = "anomalous"         # 3+ sigma deviation
    EXPLAINED = "explained"         # User gave advance notice


@dataclass
class GapAnalysis:
    """Analysis of the time gap between two sessions.

    Computed when a new session starts. If the gap is NOTABLE or higher,
    a ReturnContext is generated and injected into the model's prompt.

    Reference: SRS.md Section 3.8
    """

    duration_hours: float
    deviation_sigma: float          # Standard deviations from mean

    classification: GapClassification

    # What preceded the gap
    last_session_type: str          # SessionType value
    last_session_end_mode: str      # SessionEndMode value
    last_emotional_state: EmotionalStateVector
    last_topic: str
    open_threads: list[str] = field(default_factory=list)   # Unresolved topics or promises

    # Known explanations
    known_explanations: list[str] = field(default_factory=list)


@dataclass
class ReturnContext:
    """Injected into the model's prompt when user returns after a notable gap.

    This gives the companion awareness of how long the user was away, what
    was happening before they left, and guidance on how to handle the return.

    Reference: SRS.md Section 3.8
    """

    gap_duration_display: str           # "3 days, 7 hours"
    gap_classification: GapClassification
    preceding_summary: str              # Natural language summary of context
    suggested_approach: str             # Natural language guidance for companion


@dataclass
class AnticipatoryPrime:
    """A forward-looking prediction generated during consolidation.

    The system uses accumulated patterns to predict what the user might
    need in upcoming sessions. These primes are loaded at session start
    and influence the Compass Framework's skill selection.

    Reference: SRS.md Section 3.9
    """

    id: str                             # UUID string
    prediction: str                     # "elevated_stress", "positive_momentum", "anniversary_effect"
    confidence: float                   # 0.0-1.0
    basis: str                          # Human-readable explanation of the prediction sources
    suggested_response: str             # e.g., "compass:south:fuel_check + gentle_inquiry"
    expiry: datetime                    # When this prime is no longer relevant
    generated_at: datetime
    source_consolidation_id: str
