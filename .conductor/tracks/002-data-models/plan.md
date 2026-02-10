# Plan: Data Models

**Track:** 002-data-models
**Spec:** [spec.md](./spec.md)
**Depends on:** 001-project-scaffold (must be complete first)
**Status:** Complete

---

## Phase 1: Emotional & Compass Models

### Step 1.1: Create CompassDirection enum

Create the file `gwen/models/emotional.py`. This step adds the CompassDirection enum. Step 1.2 will add EmotionalStateVector to the same file.

- [x] Write CompassDirection enum to gwen/models/emotional.py (Done: `gwen/models/emotional.py`)

**File: `gwen/models/emotional.py`** (initial content -- Step 1.2 appends to this)

```python
"""Emotional state models and Compass direction enum.

Defines the core emotional representation used throughout the Gwen system.
All float values are normalized to 0.0-1.0 unless otherwise noted.
Reference: SRS.md Section 3.1
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CompassDirection(Enum):
    """The four Compass Framework directions plus a neutral state.

    Each direction maps to a domain of life-coaching support:
    - NORTH (presence): Mindfulness and grounding techniques
    - SOUTH (currents): Emotion regulation and processing
    - WEST (anchoring): Distress tolerance and stability
    - EAST (bridges): Interpersonal effectiveness and connection
    """

    NONE = "none"
    NORTH = "presence"
    SOUTH = "currents"
    WEST = "anchoring"
    EAST = "bridges"
```

**What this does:** Defines the 5-value enum for Compass directions. Every component in the system that references a Compass direction imports this enum. The string values ("presence", "currents", etc.) are the serialized forms stored in the database and used in prompts.

---

### Step 1.2: Add EmotionalStateVector dataclass

Append the EmotionalStateVector dataclass to the same file `gwen/models/emotional.py`, directly below the CompassDirection enum.

- [x] Append EmotionalStateVector to gwen/models/emotional.py (Done: `gwen/models/emotional.py`)

**Append to `gwen/models/emotional.py`:**

```python


@dataclass
class EmotionalStateVector:
    """The core emotional representation used throughout the system.

    All values are floats from 0.0 to 1.0 unless otherwise noted.
    This model extends the standard Valence-Arousal-Dominance (VAD)
    dimensional model with two companion-specific dimensions:
    relational_significance and vulnerability_level.

    Reference: SRS.md Section 3.1
    """

    # Primary dimensions (Valence-Arousal-Dominance model)
    valence: float              # 0.0 = extremely negative, 0.5 = neutral, 1.0 = extremely positive
    arousal: float              # 0.0 = calm/lethargic, 1.0 = highly activated/agitated
    dominance: float            # 0.0 = helpless/submissive, 1.0 = in-control/dominant

    # Companion-specific dimensions
    relational_significance: float  # 0.0 = routine, 1.0 = deeply significant to the relationship
    vulnerability_level: float      # 0.0 = guarded, 1.0 = fully open/exposed

    # Classification outputs
    compass_direction: CompassDirection = CompassDirection.NONE
    compass_confidence: float = 0.0  # 0.0-1.0, classifier confidence in the direction tag

    @property
    def storage_strength(self) -> float:
        """Compute the storage strength multiplier for the Amygdala Layer.

        Formula: arousal * 0.4 + relational_significance * 0.4 + vulnerability_level * 0.2

        This determines how strongly a memory is encoded. High-arousal,
        high-significance, high-vulnerability moments are stored more strongly
        and resist decay longer.
        """
        return (
            self.arousal * 0.4
            + self.relational_significance * 0.4
            + self.vulnerability_level * 0.2
        )

    @property
    def is_flashbulb(self) -> bool:
        """Determine if this emotional state qualifies as a flashbulb memory candidate.

        A flashbulb memory is created when BOTH arousal AND relational_significance
        exceed 0.8. These memories receive special treatment: they are never decayed,
        always retrievable, and stored with maximum detail.

        Returns True when arousal > 0.8 AND relational_significance > 0.8.
        """
        return self.arousal > 0.8 and self.relational_significance > 0.8
```

**Complete file after Steps 1.1 + 1.2:** The file `gwen/models/emotional.py` should contain the module docstring, the imports, CompassDirection, and EmotionalStateVector -- approximately 75 lines total.

**Verification check (do this mentally, not as a test):**
- `EmotionalStateVector(0.5, 0.9, 0.5, 0.9, 0.3).storage_strength` = 0.9*0.4 + 0.9*0.4 + 0.3*0.2 = 0.36 + 0.36 + 0.06 = 0.78
- `EmotionalStateVector(0.5, 0.9, 0.5, 0.9, 0.3).is_flashbulb` = True (0.9 > 0.8 and 0.9 > 0.8)
- `EmotionalStateVector(0.5, 0.7, 0.5, 0.9, 0.3).is_flashbulb` = False (0.7 is not > 0.8)

---

## Phase 2: Temporal Models

### Step 2.1: Create TimePhase enum

Create the file `gwen/models/temporal.py`. This step adds the TimePhase enum. Steps 2.2 and 2.3 add to the same file.

- [x] Write TimePhase enum to gwen/models/temporal.py (Done: `gwen/models/temporal.py`)

**File: `gwen/models/temporal.py`** (initial content)

```python
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
```

---

### Step 2.2: Add CircadianDeviationSeverity enum

Append the CircadianDeviationSeverity enum to `gwen/models/temporal.py`, directly below TimePhase.

- [x] Append CircadianDeviationSeverity to gwen/models/temporal.py (Done: `gwen/models/temporal.py`)

**Append to `gwen/models/temporal.py`:**

```python


class CircadianDeviationSeverity(Enum):
    """How far the user's current activity deviates from their established pattern.

    Computed by comparing the current TimePhase to the user's historical
    activity patterns stored in the Bond.
    """

    NONE = "none"       # Normal activity time
    LOW = "low"         # Slightly unusual but not concerning
    MEDIUM = "medium"   # Notably outside pattern
    HIGH = "high"       # Significantly anomalous (e.g., 3am when user is never up)
```

---

### Step 2.3: Add TemporalMetadataEnvelope dataclass

Append the TME dataclass to `gwen/models/temporal.py`, directly below CircadianDeviationSeverity.

- [x] Append TemporalMetadataEnvelope to gwen/models/temporal.py (Done: `gwen/models/temporal.py`)

**Append to `gwen/models/temporal.py`:**

```python


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
```

**Complete file after Steps 2.1 + 2.2 + 2.3:** The file `gwen/models/temporal.py` should contain the module docstring, imports, TimePhase, CircadianDeviationSeverity, and TemporalMetadataEnvelope -- approximately 95 lines total.

---

## Phase 3: Message & Session Models

### Step 3.1: Create SessionType enum

Create the file `gwen/models/messages.py`. This step adds SessionType. Steps 3.2-3.4 add to the same file.

- [x] Write SessionType enum to gwen/models/messages.py (Done: `gwen/models/messages.py`)

**File: `gwen/models/messages.py`** (initial content)

```python
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
```

---

### Step 3.2: Add SessionEndMode enum

Append SessionEndMode to `gwen/models/messages.py`, directly below SessionType.

- [x] Append SessionEndMode to gwen/models/messages.py (Done: `gwen/models/messages.py`)

**Append to `gwen/models/messages.py`:**

```python


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
```

---

### Step 3.3: Add MessageRecord dataclass

Append MessageRecord to `gwen/models/messages.py`, directly below SessionEndMode.

- [x] Append MessageRecord to gwen/models/messages.py (Done: `gwen/models/messages.py`)

**Append to `gwen/models/messages.py`:**

```python


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
```

---

### Step 3.4: Add SessionRecord dataclass

Append SessionRecord to `gwen/models/messages.py`, directly below MessageRecord.

- [x] Append SessionRecord to gwen/models/messages.py (Done: `gwen/models/messages.py`)

**Append to `gwen/models/messages.py`:**

```python


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
```

**Complete file after Steps 3.1-3.4:** The file `gwen/models/messages.py` should contain imports, SessionType, SessionEndMode, MessageRecord, SessionRecord, ConsolidationType, and ConsolidationJob -- approximately 170 lines total.

---

## Phase 4: Memory Models

### Step 4.1: Create MapEntity and MapEdge

Create the file `gwen/models/memory.py`. This step adds MapEntity and MapEdge. Steps 4.2-4.5 add to the same file.

- [x] Write MapEntity and MapEdge to gwen/models/memory.py (Done: `gwen/models/memory.py`)

**File: `gwen/models/memory.py`** (initial content)

```python
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
```

---

### Step 4.2: Add EmotionalBaseline, EmotionalTrajectory, TriggerMapEntry, CompassEffectivenessRecord

Append these four dataclasses to `gwen/models/memory.py`, directly below MapEdge.

- [x] Append Pulse records to gwen/models/memory.py (Done: `gwen/models/memory.py`)

**Append to `gwen/models/memory.py`:**

```python


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
```

---

### Step 4.3: Add RelationalField and BondState

Append these two dataclasses to `gwen/models/memory.py`, directly below CompassEffectivenessRecord.

- [x] Append RelationalField and BondState to gwen/models/memory.py (Done: `gwen/models/memory.py`)

**Append to `gwen/models/memory.py`:**

```python


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
```

---

### Step 4.4: Add GapClassification, GapAnalysis, and ReturnContext

Append these to `gwen/models/memory.py`, directly below BondState.

- [x] Append gap analysis models to gwen/models/memory.py (Done: `gwen/models/memory.py`)

**Append to `gwen/models/memory.py`:**

```python


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
```

---

### Step 4.5: Add AnticipatoryPrime

Append AnticipatoryPrime to `gwen/models/memory.py`, directly below ReturnContext.

- [x] Append AnticipatoryPrime to gwen/models/memory.py (Done: `gwen/models/memory.py`)

**Append to `gwen/models/memory.py`:**

```python


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
```

**Complete file after Steps 4.1-4.5:** The file `gwen/models/memory.py` should contain imports, MapEntity, MapEdge, EmotionalBaseline, EmotionalTrajectory, TriggerMapEntry, CompassEffectivenessRecord, RelationalField, BondState, GapClassification, GapAnalysis, ReturnContext, and AnticipatoryPrime -- approximately 280 lines total.

---

## Phase 5: Safety Models

### Step 5.1: Create ThreatVector and ThreatSeverity enums

Create the file `gwen/models/safety.py`. Steps 5.2-5.3 add to the same file.

- [x] Write ThreatVector and ThreatSeverity to gwen/models/safety.py (Done: `gwen/models/safety.py`)

**File: `gwen/models/safety.py`** (initial content)

```python
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
```

---

### Step 5.2: Add SafetyEvent dataclass

Append SafetyEvent to `gwen/models/safety.py`, directly below ThreatSeverity.

- [x] Append SafetyEvent to gwen/models/safety.py (Done: `gwen/models/safety.py`)

**Append to `gwen/models/safety.py`:**

```python


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
```

---

### Step 5.3: Add WellnessCheckpoint dataclass

Append WellnessCheckpoint to `gwen/models/safety.py`, directly below SafetyEvent.

- [x] Append WellnessCheckpoint to gwen/models/safety.py (Done: `gwen/models/safety.py`)

**Append to `gwen/models/safety.py`:**

```python


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
```

**Complete file after Steps 5.1-5.3:** The file `gwen/models/safety.py` should contain imports, ThreatVector, ThreatSeverity, SafetyEvent, and WellnessCheckpoint -- approximately 105 lines total.

---

## Phase 6: Personality & Consolidation Models

### Step 6.1: Create PersonalityModule dataclass

Create the file `gwen/models/personality.py`.

- [x] Write PersonalityModule to gwen/models/personality.py (Done: `gwen/models/personality.py`)

**File: `gwen/models/personality.py`** (complete content)

```python
"""Personality module model.

Defines the structure of a loadable companion personality. Personalities
are stored as YAML files in data/personalities/ and loaded at startup.
The personality module is injected into the system prompt dynamically.
Reference: SRS.md Section 3.11
"""

from dataclasses import dataclass, field
from typing import Optional

from gwen.models.emotional import EmotionalStateVector


@dataclass
class PersonalityModule:
    """Defines a companion's identity, loaded as dynamic system prompt.

    The Gwen framework is soul-agnostic: any personality can be loaded.
    The personality module controls voice, values, boundaries, emotional
    expression, relationship style, and coaching approach.

    Reference: SRS.md Section 3.11
    """

    id: str                                     # Unique identifier
    name: str                                   # Display name (e.g., "Gwen")
    version: str                                # Personality version

    # Identity
    backstory: str
    cultural_background: str
    age_description: str
    appearance_description: str                 # For future avatar generation

    # Voice & language
    speech_patterns: list[str] = field(default_factory=list)
    vocabulary_notes: str = ""
    pet_names: list[str] = field(default_factory=list)
    catchphrases: list[str] = field(default_factory=list)
    tone_range: str = ""                        # "warm-sarcastic" vs "gentle-earnest"

    # Values & boundaries
    core_values: list[str] = field(default_factory=list)
    ethical_boundaries: list[str] = field(default_factory=list)
    topics_of_passion: list[str] = field(default_factory=list)
    topics_to_avoid: list[str] = field(default_factory=list)

    # Emotional profile
    default_mood: Optional[EmotionalStateVector] = None
    emotional_range: str = ""                   # How wide their emotional expression goes
    joy_expression: str = ""
    sadness_expression: str = ""
    anger_expression: str = ""
    affection_expression: str = ""

    # Relationship model
    relationship_style: str = ""                # "warm-direct", "gentle-nurturing", etc.
    flirtation_level: str = "none"              # "none", "light", "moderate", "full"
    boundary_style: str = ""                    # How they handle their own boundaries

    # Compass style
    coaching_approach: str = ""                 # "direct", "gentle", "humorous", "socratic"

    # Behavioral rules by mode
    grounded_mode_rules: list[str] = field(default_factory=list)
    immersion_mode_rules: list[str] = field(default_factory=list)

    # System prompt sections (injected dynamically based on context)
    core_prompt: str = ""                       # Always injected
    emotional_prompt: str = ""                  # Injected during emotional conversations
    coaching_prompt: str = ""                   # Injected when Compass is active
    intimate_prompt: str = ""                   # Injected only in Immersion Mode
```

**Note on ConsolidationType and ConsolidationJob:** These are defined in `gwen/models/messages.py` (Step 3.4) because they are tightly coupled with session records -- consolidation jobs process sessions and produce records in the same database. This avoids a separate file for just two small definitions.

---

## Phase 7: Classification Models

### Step 7.1: Create Tier0RawOutput Pydantic model

Create the file `gwen/models/classification.py`. Step 7.2 adds to the same file.

- [x] Write Tier0RawOutput with fuzzy validators to gwen/models/classification.py (Done: `gwen/models/classification.py`)

**File: `gwen/models/classification.py`** (initial content)

```python
"""Classification models for the Tier 0 pipeline.

Defines Tier0RawOutput (the Pydantic model for parsing Tier 0's JSON output)
and HardwareProfile (the adaptive model manager's hardware tiers).
Reference: SRS.md Sections 3.13, 3.16
"""

from enum import Enum

from pydantic import BaseModel, field_validator


class Tier0RawOutput(BaseModel):
    """What Tier 0 actually returns -- simplified for reliability.

    The 0.6B model handles what it is empirically good at: valence, arousal,
    topic extraction, and basic safety keyword detection. Everything else
    (compass direction, vulnerability, dominance, intent) is computed by
    the ClassificationRuleEngine.

    The field_validator decorators implement fuzzy coercion: the small model
    often returns creative variants like "very negative" (with a space) or
    "med" instead of "moderate". The validators normalize these to the
    canonical enum values.

    Reference: SRS.md Section 3.13
    """

    valence: str        # "very_negative" | "negative" | "neutral" | "positive" | "very_positive"
    arousal: str        # "low" | "moderate" | "high"
    topic: str = "unknown"
    safety_keywords: list[str] = []

    @field_validator("valence")
    @classmethod
    def coerce_valence(cls, v: str) -> str:
        """Fuzzy coercion: map model's creative outputs to valid enum values.

        Examples of coercion:
            "very negative" -> "very_negative"  (space to underscore)
            "very_neg"      -> "very_negative"  (abbreviation)
            "neg"           -> "negative"       (abbreviation)
            "neu"           -> "neutral"        (abbreviation)
            "neut"          -> "neutral"        (abbreviation)
            "pos"           -> "positive"       (abbreviation)
            "very positive" -> "very_positive"  (space to underscore)
            "very_pos"      -> "very_positive"  (abbreviation)
        """
        v_lower = v.strip().lower().replace(" ", "_")
        aliases: dict[str, str] = {
            "very_negative": "very_negative",
            "very_neg": "very_negative",
            "neg": "negative",
            "negative": "negative",
            "neu": "neutral",
            "neut": "neutral",
            "neutral": "neutral",
            "pos": "positive",
            "positive": "positive",
            "very_positive": "very_positive",
            "very_pos": "very_positive",
        }
        result = aliases.get(v_lower, v_lower)
        return result

    @field_validator("arousal")
    @classmethod
    def coerce_arousal(cls, v: str) -> str:
        """Fuzzy coercion for arousal values.

        Examples of coercion:
            "med"    -> "moderate"  (abbreviation)
            "medium" -> "moderate"  (synonym)
            "hi"     -> "high"     (abbreviation)
            "lo"     -> "low"      (abbreviation)
        """
        v_lower = v.strip().lower()
        aliases: dict[str, str] = {
            "low": "low",
            "lo": "low",
            "moderate": "moderate",
            "med": "moderate",
            "medium": "moderate",
            "high": "high",
            "hi": "high",
        }
        result = aliases.get(v_lower, v_lower)
        return result
```

---

### Step 7.2: Add HardwareProfile enum

Append HardwareProfile to `gwen/models/classification.py`, directly below Tier0RawOutput.

- [x] Append HardwareProfile to gwen/models/classification.py (Done: `gwen/models/classification.py`)

**Append to `gwen/models/classification.py`:**

```python


class HardwareProfile(Enum):
    """Hardware capability profiles for the Adaptive Model Manager.

    The system auto-detects available VRAM at startup and selects the
    highest-capability profile that fits. Users can override manually.

    POCKET: Phone / 4GB device. One model plays all 3 roles.
    PORTABLE: Laptop / 8GB VRAM. Tier 0 always loaded + Tier 1 active.
    STANDARD: Desktop / 12-16GB VRAM. Tier 0+1 concurrent, Tier 2 time-shared.
    POWER: Workstation / 24GB+ VRAM. All tiers concurrent.

    Reference: SRS.md Section 3.16
    """

    POCKET = "pocket"
    PORTABLE = "portable"
    STANDARD = "standard"
    POWER = "power"
```

**Complete file after Steps 7.1-7.2:** The file `gwen/models/classification.py` should contain imports, Tier0RawOutput, and HardwareProfile -- approximately 110 lines total.

---

## Phase 8: Reconsolidation Models

### Step 8.1: Create ReconsolidationLayer dataclass

Create the file `gwen/models/reconsolidation.py`. Steps 8.2-8.3 add to the same file.

- [x] Write ReconsolidationLayer to gwen/models/reconsolidation.py (Done: `gwen/models/reconsolidation.py`)

**File: `gwen/models/reconsolidation.py`** (initial content)

```python
"""Reconsolidation models for the Memory Palimpsest system.

The Palimpsest model ensures memories evolve naturally while maintaining
absolute historical integrity. The original memory is immutable forever.
New understanding is layered on top, like a palimpsest manuscript where
new text overlays old -- but the old text is always recoverable.

Reference: SRS.md Section 3.15
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from gwen.models.emotional import EmotionalStateVector
from gwen.models.messages import MessageRecord


@dataclass
class ReconsolidationLayer:
    """A single layer of re-interpretation applied to a memory during reconsolidation.

    Each layer records how the memory was perceived when it was recalled.
    Emotional adjustments are bounded per layer to prevent runaway drift.

    Reference: SRS.md Section 3.15
    """

    id: str                                         # UUID string
    timestamp: datetime
    recall_session_id: str                          # Which session triggered the recall

    # Context at time of recall
    user_emotional_state_at_recall: EmotionalStateVector
    conversation_topic_at_recall: str

    # How the user reacted to the resurfaced memory
    reaction_type: str      # "warmth", "pain", "correction", "elaboration", "dismissal", "humor"
    reaction_detail: str

    # Bounded emotional adjustments (capped per layer)
    valence_delta: float            # Range: -0.10 to +0.10
    arousal_delta: float            # Range: -0.10 to +0.10
    significance_delta: float       # Range: 0.0 to +0.10 (can only increase)

    # New narrative context added by this reconsolidation
    narrative: str                  # e.g., "User laughed about this -- healing is happening"
```

---

### Step 8.2: Add ReconsolidationConstraints dataclass

Append ReconsolidationConstraints to `gwen/models/reconsolidation.py`, directly below ReconsolidationLayer.

- [x] Append ReconsolidationConstraints to gwen/models/reconsolidation.py (Done: `gwen/models/reconsolidation.py`)

**Append to `gwen/models/reconsolidation.py`:**

```python


@dataclass
class ReconsolidationConstraints:
    """Hard limits on how far a memory can drift from its original emotional signature.

    These defaults are intentionally conservative. A memory can shift at most
    0.10 per reconsolidation event, and at most 0.50 total from its original
    values. This prevents a single emotionally-charged recall from rewriting
    history.

    Reference: SRS.md Section 3.15
    """

    MAX_DELTA_PER_LAYER: float = 0.10       # Max change in any dimension per event
    MAX_TOTAL_DRIFT: float = 0.50           # Max cumulative drift from archive values
    MIN_LAYERS_FOR_TREND: int = 3           # Need 3+ layers before computing trend direction
    COOLDOWN_HOURS: float = 24.0            # Minimum time between reconsolidation of same memory
```

---

### Step 8.3: Add MemoryPalimpsest dataclass

Append MemoryPalimpsest to `gwen/models/reconsolidation.py`, directly below ReconsolidationConstraints.

- [x] Append MemoryPalimpsest to gwen/models/reconsolidation.py (Done: `gwen/models/reconsolidation.py`)

**Append to `gwen/models/reconsolidation.py`:**

```python


@dataclass
class MemoryPalimpsest:
    """A memory with its complete reconsolidation history.

    The archive is IMMUTABLE FOREVER. Layers are APPEND-ONLY.
    This dataclass provides properties and methods to compute the memory's
    current emotional reading (archive + all layers applied), the reading
    at any historical point, and a human-readable evolution summary.

    Reference: SRS.md Section 3.15
    """

    archive: MessageRecord                      # The original memory -- never modified
    layers: list[ReconsolidationLayer] = field(default_factory=list)
    constraints: ReconsolidationConstraints = field(
        default_factory=ReconsolidationConstraints
    )

    @property
    def current_valence(self) -> float:
        """The memory's current emotional valence, accounting for all reconsolidation layers.

        Sums all valence_delta values from layers, clamps the total delta to
        MAX_TOTAL_DRIFT, then clamps the final result to [0.0, 1.0].
        """
        base = self.archive.emotional_state.valence
        total_delta = sum(layer.valence_delta for layer in self.layers)
        total_delta = max(
            -self.constraints.MAX_TOTAL_DRIFT,
            min(self.constraints.MAX_TOTAL_DRIFT, total_delta),
        )
        return max(0.0, min(1.0, base + total_delta))

    @property
    def current_arousal(self) -> float:
        """The memory's current arousal, accounting for all reconsolidation layers."""
        base = self.archive.emotional_state.arousal
        total_delta = sum(layer.arousal_delta for layer in self.layers)
        total_delta = max(
            -self.constraints.MAX_TOTAL_DRIFT,
            min(self.constraints.MAX_TOTAL_DRIFT, total_delta),
        )
        return max(0.0, min(1.0, base + total_delta))

    @property
    def current_significance(self) -> float:
        """The memory's current relational significance.

        Note: significance can only increase (significance_delta >= 0),
        so we only clamp against MAX_TOTAL_DRIFT on the positive side.
        """
        base = self.archive.emotional_state.relational_significance
        total_delta = sum(layer.significance_delta for layer in self.layers)
        total_delta = min(self.constraints.MAX_TOTAL_DRIFT, total_delta)
        return min(1.0, base + total_delta)

    def current_reading(self) -> EmotionalStateVector:
        """The memory as it feels NOW -- archive + all layers applied.

        Returns a new EmotionalStateVector with valence, arousal, and
        relational_significance adjusted by reconsolidation layers.
        All other dimensions (dominance, vulnerability_level, compass_direction,
        compass_confidence) are preserved from the original archive.
        """
        original = self.archive.emotional_state
        return EmotionalStateVector(
            valence=self.current_valence,
            arousal=self.current_arousal,
            dominance=original.dominance,
            relational_significance=self.current_significance,
            vulnerability_level=original.vulnerability_level,
            compass_direction=original.compass_direction,
            compass_confidence=original.compass_confidence,
        )

    def reading_at(self, point_in_time: datetime) -> EmotionalStateVector:
        """The memory as it felt at a specific point -- only layers up to that time.

        Filters layers by timestamp and applies only those that existed at
        the given point_in_time. Useful for understanding how the memory
        has evolved over the relationship history.

        Args:
            point_in_time: Only layers with timestamp <= this value are applied.

        Returns:
            EmotionalStateVector reflecting the memory at that point in time.
        """
        applicable = [layer for layer in self.layers if layer.timestamp <= point_in_time]
        original = self.archive.emotional_state
        v_delta = sum(layer.valence_delta for layer in applicable)
        a_delta = sum(layer.arousal_delta for layer in applicable)
        s_delta = sum(layer.significance_delta for layer in applicable)
        return EmotionalStateVector(
            valence=max(0.0, min(1.0, original.valence + v_delta)),
            arousal=max(0.0, min(1.0, original.arousal + a_delta)),
            dominance=original.dominance,
            relational_significance=min(1.0, original.relational_significance + s_delta),
            vulnerability_level=original.vulnerability_level,
            compass_direction=original.compass_direction,
            compass_confidence=original.compass_confidence,
        )

    def evolution_summary(self) -> str:
        """Human-readable summary of how this memory has evolved.

        Returns a string describing the number of reconsolidation events,
        the direction of emotional drift, and the most recent reaction type.
        If no reconsolidation has occurred, states that explicitly.
        """
        if not self.layers:
            return "No reconsolidation -- memory is as originally recorded."
        orig_v = self.archive.emotional_state.valence
        curr_v = self.current_valence
        if curr_v > orig_v:
            direction = "more positive"
        elif curr_v < orig_v:
            direction = "more negative"
        else:
            direction = "unchanged"
        return (
            f"Reconsolidated {len(self.layers)} time(s). "
            f"Emotional tone has shifted {direction} "
            f"(original valence: {orig_v:.2f}, current: {curr_v:.2f}). "
            f"Most recent reaction: {self.layers[-1].reaction_type}."
        )
```

**Complete file after Steps 8.1-8.3:** The file `gwen/models/reconsolidation.py` should contain imports, ReconsolidationLayer, ReconsolidationConstraints, and MemoryPalimpsest -- approximately 175 lines total.

---

## Phase 9: Package Exports

### Step 9.1: Update gwen/models/__init__.py with all exports

Replace the content of `gwen/models/__init__.py` (which currently contains only a docstring from track 001) with imports and re-exports of all models.

- [x] Write complete gwen/models/__init__.py with all exports (Done: `gwen/models/__init__.py`)

**File: `gwen/models/__init__.py`** (complete replacement)

```python
"""Data models, enums, and Pydantic schemas for the Gwen system.

All models can be imported directly from this package:
    from gwen.models import EmotionalStateVector, CompassDirection, ...

Models are organized into submodules by domain:
    - emotional: EmotionalStateVector, CompassDirection
    - temporal: TimePhase, CircadianDeviationSeverity, TemporalMetadataEnvelope
    - messages: MessageRecord, SessionRecord, SessionType, SessionEndMode,
                ConsolidationType, ConsolidationJob
    - memory: MapEntity, MapEdge, EmotionalBaseline, EmotionalTrajectory,
              TriggerMapEntry, CompassEffectivenessRecord, RelationalField,
              BondState, GapClassification, GapAnalysis, ReturnContext,
              AnticipatoryPrime
    - safety: ThreatVector, ThreatSeverity, SafetyEvent, WellnessCheckpoint
    - personality: PersonalityModule
    - classification: Tier0RawOutput, HardwareProfile
    - reconsolidation: ReconsolidationLayer, ReconsolidationConstraints,
                       MemoryPalimpsest
"""

# Emotional & Compass
from gwen.models.emotional import CompassDirection, EmotionalStateVector

# Temporal
from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TemporalMetadataEnvelope,
    TimePhase,
)

# Messages & Sessions
from gwen.models.messages import (
    ConsolidationJob,
    ConsolidationType,
    MessageRecord,
    SessionEndMode,
    SessionRecord,
    SessionType,
)

# Memory
from gwen.models.memory import (
    AnticipatoryPrime,
    BondState,
    CompassEffectivenessRecord,
    EmotionalBaseline,
    EmotionalTrajectory,
    GapAnalysis,
    GapClassification,
    MapEdge,
    MapEntity,
    RelationalField,
    ReturnContext,
    TriggerMapEntry,
)

# Safety
from gwen.models.safety import (
    SafetyEvent,
    ThreatSeverity,
    ThreatVector,
    WellnessCheckpoint,
)

# Personality
from gwen.models.personality import PersonalityModule

# Classification
from gwen.models.classification import HardwareProfile, Tier0RawOutput

# Reconsolidation
from gwen.models.reconsolidation import (
    MemoryPalimpsest,
    ReconsolidationConstraints,
    ReconsolidationLayer,
)

__all__ = [
    # Emotional
    "CompassDirection",
    "EmotionalStateVector",
    # Temporal
    "TimePhase",
    "CircadianDeviationSeverity",
    "TemporalMetadataEnvelope",
    # Messages
    "SessionType",
    "SessionEndMode",
    "MessageRecord",
    "SessionRecord",
    "ConsolidationType",
    "ConsolidationJob",
    # Memory
    "MapEntity",
    "MapEdge",
    "EmotionalBaseline",
    "EmotionalTrajectory",
    "TriggerMapEntry",
    "CompassEffectivenessRecord",
    "RelationalField",
    "BondState",
    "GapClassification",
    "GapAnalysis",
    "ReturnContext",
    "AnticipatoryPrime",
    # Safety
    "ThreatVector",
    "ThreatSeverity",
    "SafetyEvent",
    "WellnessCheckpoint",
    # Personality
    "PersonalityModule",
    # Classification
    "Tier0RawOutput",
    "HardwareProfile",
    # Reconsolidation
    "ReconsolidationLayer",
    "ReconsolidationConstraints",
    "MemoryPalimpsest",
]
```

---

## Phase 10: Tests

### Step 10.1: Test EmotionalStateVector computed properties

Create the file `tests/test_models.py`. Steps 10.2-10.3 add to the same file.

- [x] Write EmotionalStateVector tests to tests/test_models.py (Done: `tests/test_models.py`)

**File: `tests/test_models.py`** (initial content)

```python
"""Tests for gwen.models data structures.

Covers:
- EmotionalStateVector computed properties (storage_strength, is_flashbulb)
- Tier0RawOutput fuzzy field coercion
- MemoryPalimpsest drift bounds and evolution summary

Reference: 002-data-models spec.md Verification Plan
"""

from datetime import datetime, timezone

import pytest

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.classification import Tier0RawOutput
from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TemporalMetadataEnvelope,
    TimePhase,
)
from gwen.models.messages import MessageRecord
from gwen.models.reconsolidation import (
    MemoryPalimpsest,
    ReconsolidationConstraints,
    ReconsolidationLayer,
)


# ---------------------------------------------------------------------------
# Helpers: factory functions for creating test objects
# ---------------------------------------------------------------------------

def make_esv(
    valence: float = 0.5,
    arousal: float = 0.5,
    dominance: float = 0.5,
    relational_significance: float = 0.5,
    vulnerability_level: float = 0.5,
    compass_direction: CompassDirection = CompassDirection.NONE,
    compass_confidence: float = 0.0,
) -> EmotionalStateVector:
    """Create an EmotionalStateVector with sensible defaults."""
    return EmotionalStateVector(
        valence=valence,
        arousal=arousal,
        dominance=dominance,
        relational_significance=relational_significance,
        vulnerability_level=vulnerability_level,
        compass_direction=compass_direction,
        compass_confidence=compass_confidence,
    )


def make_tme() -> TemporalMetadataEnvelope:
    """Create a minimal valid TME for use in MessageRecord tests."""
    now = datetime.now(timezone.utc)
    return TemporalMetadataEnvelope(
        timestamp_utc=now,
        local_time=now,
        hour_of_day=14,
        day_of_week="Wednesday",
        day_of_month=9,
        month=2,
        year=2026,
        is_weekend=False,
        time_phase=TimePhase.AFTERNOON,
        session_id="test-session-001",
        session_start=now,
        session_duration_sec=300,
        msg_index_in_session=0,
        time_since_last_msg_sec=None,
        time_since_last_user_msg_sec=None,
        time_since_last_gwen_msg_sec=None,
        user_msgs_last_5min=1,
        user_msgs_last_hour=1,
        user_msgs_last_24hr=1,
        last_session_end=None,
        hours_since_last_session=None,
        sessions_last_7_days=0,
        sessions_last_30_days=0,
        avg_session_gap_30d_hours=None,
        circadian_deviation_severity=CircadianDeviationSeverity.NONE,
        circadian_deviation_type=None,
    )


def make_message_record(
    valence: float = 0.5,
    arousal: float = 0.5,
    relational_significance: float = 0.5,
) -> MessageRecord:
    """Create a minimal valid MessageRecord for palimpsest tests."""
    esv = make_esv(
        valence=valence,
        arousal=arousal,
        relational_significance=relational_significance,
    )
    return MessageRecord(
        id="msg-001",
        session_id="session-001",
        timestamp=datetime.now(timezone.utc),
        sender="user",
        content="Test message",
        tme=make_tme(),
        emotional_state=esv,
        storage_strength=esv.storage_strength,
        is_flashbulb=esv.is_flashbulb,
        compass_direction=CompassDirection.NONE,
        compass_skill_used=None,
    )


def make_layer(
    valence_delta: float = 0.0,
    arousal_delta: float = 0.0,
    significance_delta: float = 0.0,
    timestamp: datetime | None = None,
) -> ReconsolidationLayer:
    """Create a ReconsolidationLayer with sensible defaults."""
    return ReconsolidationLayer(
        id="layer-001",
        timestamp=timestamp or datetime.now(timezone.utc),
        recall_session_id="recall-session-001",
        user_emotional_state_at_recall=make_esv(),
        conversation_topic_at_recall="test topic",
        reaction_type="warmth",
        reaction_detail="User smiled when recalling this.",
        valence_delta=valence_delta,
        arousal_delta=arousal_delta,
        significance_delta=significance_delta,
        narrative="Test narrative",
    )


# ---------------------------------------------------------------------------
# Test: EmotionalStateVector computed properties
# ---------------------------------------------------------------------------

class TestEmotionalStateVector:
    """Tests for EmotionalStateVector.storage_strength and .is_flashbulb."""

    def test_storage_strength_formula(self) -> None:
        """storage_strength = arousal*0.4 + relational_significance*0.4 + vulnerability*0.2"""
        esv = make_esv(arousal=0.9, relational_significance=0.9, vulnerability_level=0.3)
        expected = 0.9 * 0.4 + 0.9 * 0.4 + 0.3 * 0.2  # = 0.78
        assert abs(esv.storage_strength - expected) < 1e-9

    def test_storage_strength_zeros(self) -> None:
        """All zeros should produce storage_strength of 0.0."""
        esv = make_esv(arousal=0.0, relational_significance=0.0, vulnerability_level=0.0)
        assert esv.storage_strength == 0.0

    def test_storage_strength_ones(self) -> None:
        """All ones should produce storage_strength of 1.0."""
        esv = make_esv(arousal=1.0, relational_significance=1.0, vulnerability_level=1.0)
        expected = 1.0 * 0.4 + 1.0 * 0.4 + 1.0 * 0.2  # = 1.0
        assert abs(esv.storage_strength - expected) < 1e-9

    def test_storage_strength_mixed(self) -> None:
        """A typical mixed-value case."""
        esv = make_esv(arousal=0.5, relational_significance=0.3, vulnerability_level=0.7)
        expected = 0.5 * 0.4 + 0.3 * 0.4 + 0.7 * 0.2  # = 0.20 + 0.12 + 0.14 = 0.46
        assert abs(esv.storage_strength - expected) < 1e-9

    def test_is_flashbulb_both_above_threshold(self) -> None:
        """Flashbulb requires BOTH arousal > 0.8 AND relational_significance > 0.8."""
        esv = make_esv(arousal=0.85, relational_significance=0.90)
        assert esv.is_flashbulb is True

    def test_is_flashbulb_arousal_below(self) -> None:
        """Arousal at 0.8 exactly should NOT trigger flashbulb (must be > 0.8)."""
        esv = make_esv(arousal=0.8, relational_significance=0.9)
        assert esv.is_flashbulb is False

    def test_is_flashbulb_significance_below(self) -> None:
        """Significance at 0.8 exactly should NOT trigger flashbulb (must be > 0.8)."""
        esv = make_esv(arousal=0.9, relational_significance=0.8)
        assert esv.is_flashbulb is False

    def test_is_flashbulb_both_at_boundary(self) -> None:
        """Both at exactly 0.8 should NOT trigger flashbulb."""
        esv = make_esv(arousal=0.8, relational_significance=0.8)
        assert esv.is_flashbulb is False

    def test_is_flashbulb_low_values(self) -> None:
        """Low values should not be flashbulb."""
        esv = make_esv(arousal=0.3, relational_significance=0.2)
        assert esv.is_flashbulb is False
```

---

### Step 10.2: Add Tier0RawOutput fuzzy coercion tests

Append these test classes to `tests/test_models.py`, directly below TestEmotionalStateVector.

- [x] Append Tier0RawOutput tests to tests/test_models.py (Done: `tests/test_models.py`)

**Append to `tests/test_models.py`:**

```python


# ---------------------------------------------------------------------------
# Test: Tier0RawOutput fuzzy coercion
# ---------------------------------------------------------------------------

class TestTier0RawOutput:
    """Tests for Tier0RawOutput field validators (fuzzy coercion)."""

    # --- Valence coercion ---

    def test_valence_exact_match(self) -> None:
        """Exact canonical values pass through unchanged."""
        result = Tier0RawOutput(valence="very_negative", arousal="low")
        assert result.valence == "very_negative"

    def test_valence_space_to_underscore(self) -> None:
        """'very negative' (with space) coerces to 'very_negative'."""
        result = Tier0RawOutput(valence="very negative", arousal="low")
        assert result.valence == "very_negative"

    def test_valence_abbreviation_neg(self) -> None:
        """'neg' coerces to 'negative'."""
        result = Tier0RawOutput(valence="neg", arousal="low")
        assert result.valence == "negative"

    def test_valence_abbreviation_neu(self) -> None:
        """'neu' coerces to 'neutral'."""
        result = Tier0RawOutput(valence="neu", arousal="low")
        assert result.valence == "neutral"

    def test_valence_abbreviation_neut(self) -> None:
        """'neut' coerces to 'neutral'."""
        result = Tier0RawOutput(valence="neut", arousal="low")
        assert result.valence == "neutral"

    def test_valence_abbreviation_pos(self) -> None:
        """'pos' coerces to 'positive'."""
        result = Tier0RawOutput(valence="pos", arousal="low")
        assert result.valence == "positive"

    def test_valence_abbreviation_very_pos(self) -> None:
        """'very_pos' coerces to 'very_positive'."""
        result = Tier0RawOutput(valence="very_pos", arousal="low")
        assert result.valence == "very_positive"

    def test_valence_very_positive_with_space(self) -> None:
        """'very positive' (with space) coerces to 'very_positive'."""
        result = Tier0RawOutput(valence="very positive", arousal="low")
        assert result.valence == "very_positive"

    def test_valence_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped."""
        result = Tier0RawOutput(valence="  neutral  ", arousal="low")
        assert result.valence == "neutral"

    def test_valence_case_insensitive(self) -> None:
        """Coercion is case-insensitive."""
        result = Tier0RawOutput(valence="NEGATIVE", arousal="low")
        assert result.valence == "negative"

    # --- Arousal coercion ---

    def test_arousal_exact_match(self) -> None:
        """Exact canonical values pass through unchanged."""
        result = Tier0RawOutput(valence="neutral", arousal="moderate")
        assert result.arousal == "moderate"

    def test_arousal_med_to_moderate(self) -> None:
        """'med' coerces to 'moderate'."""
        result = Tier0RawOutput(valence="neutral", arousal="med")
        assert result.arousal == "moderate"

    def test_arousal_medium_to_moderate(self) -> None:
        """'medium' coerces to 'moderate'."""
        result = Tier0RawOutput(valence="neutral", arousal="medium")
        assert result.arousal == "moderate"

    def test_arousal_hi_to_high(self) -> None:
        """'hi' coerces to 'high'."""
        result = Tier0RawOutput(valence="neutral", arousal="hi")
        assert result.arousal == "high"

    def test_arousal_lo_to_low(self) -> None:
        """'lo' coerces to 'low'."""
        result = Tier0RawOutput(valence="neutral", arousal="lo")
        assert result.arousal == "low"

    def test_arousal_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped."""
        result = Tier0RawOutput(valence="neutral", arousal="  high  ")
        assert result.arousal == "high"

    def test_arousal_case_insensitive(self) -> None:
        """Coercion is case-insensitive."""
        result = Tier0RawOutput(valence="neutral", arousal="HIGH")
        assert result.arousal == "high"

    # --- Default fields ---

    def test_default_topic(self) -> None:
        """topic defaults to 'unknown'."""
        result = Tier0RawOutput(valence="neutral", arousal="low")
        assert result.topic == "unknown"

    def test_default_safety_keywords(self) -> None:
        """safety_keywords defaults to empty list."""
        result = Tier0RawOutput(valence="neutral", arousal="low")
        assert result.safety_keywords == []

    def test_custom_topic_and_keywords(self) -> None:
        """Custom topic and safety_keywords are preserved."""
        result = Tier0RawOutput(
            valence="negative",
            arousal="high",
            topic="work_stress",
            safety_keywords=["overwhelmed", "can't cope"],
        )
        assert result.topic == "work_stress"
        assert result.safety_keywords == ["overwhelmed", "can't cope"]
```

---

### Step 10.3: Add MemoryPalimpsest drift bounds tests

Append these test classes to `tests/test_models.py`, directly below TestTier0RawOutput.

- [x] Append MemoryPalimpsest tests to tests/test_models.py (Done: `tests/test_models.py`)

**Append to `tests/test_models.py`:**

```python


# ---------------------------------------------------------------------------
# Test: MemoryPalimpsest drift bounds
# ---------------------------------------------------------------------------

class TestMemoryPalimpsest:
    """Tests for MemoryPalimpsest computed properties and drift enforcement."""

    def test_no_layers_returns_archive_values(self) -> None:
        """With no reconsolidation layers, current values match the archive."""
        record = make_message_record(valence=0.6, arousal=0.4, relational_significance=0.5)
        palimpsest = MemoryPalimpsest(archive=record)
        assert palimpsest.current_valence == 0.6
        assert palimpsest.current_arousal == 0.4
        assert palimpsest.current_significance == 0.5

    def test_single_layer_applies_delta(self) -> None:
        """A single layer shifts the values by its deltas."""
        record = make_message_record(valence=0.5, arousal=0.5, relational_significance=0.5)
        layer = make_layer(valence_delta=0.05, arousal_delta=-0.03, significance_delta=0.02)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer])
        assert abs(palimpsest.current_valence - 0.55) < 1e-9
        assert abs(palimpsest.current_arousal - 0.47) < 1e-9
        assert abs(palimpsest.current_significance - 0.52) < 1e-9

    def test_multiple_layers_accumulate(self) -> None:
        """Multiple layers accumulate their deltas."""
        record = make_message_record(valence=0.5, arousal=0.5, relational_significance=0.5)
        layer1 = make_layer(valence_delta=0.05, arousal_delta=0.05, significance_delta=0.02)
        layer2 = make_layer(valence_delta=0.05, arousal_delta=0.05, significance_delta=0.02)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer1, layer2])
        assert abs(palimpsest.current_valence - 0.6) < 1e-9
        assert abs(palimpsest.current_arousal - 0.6) < 1e-9
        assert abs(palimpsest.current_significance - 0.54) < 1e-9

    def test_drift_clamped_to_max_total(self) -> None:
        """Total drift cannot exceed MAX_TOTAL_DRIFT (0.50 by default)."""
        record = make_message_record(valence=0.5, arousal=0.5, relational_significance=0.5)
        # Create 10 layers each pushing valence up by 0.10 = total 1.0, but clamped to 0.50
        layers = [make_layer(valence_delta=0.10) for _ in range(10)]
        palimpsest = MemoryPalimpsest(archive=record, layers=layers)
        # 0.5 + 0.50 (clamped) = 1.0
        assert abs(palimpsest.current_valence - 1.0) < 1e-9

    def test_drift_clamped_negative_direction(self) -> None:
        """Negative drift is also clamped to MAX_TOTAL_DRIFT."""
        record = make_message_record(valence=0.5, arousal=0.5, relational_significance=0.5)
        layers = [make_layer(valence_delta=-0.10) for _ in range(10)]
        palimpsest = MemoryPalimpsest(archive=record, layers=layers)
        # 0.5 + (-0.50 clamped) = 0.0
        assert abs(palimpsest.current_valence - 0.0) < 1e-9

    def test_valence_never_below_zero(self) -> None:
        """Even with drift, valence is clamped to [0.0, 1.0]."""
        record = make_message_record(valence=0.1, arousal=0.5, relational_significance=0.5)
        layers = [make_layer(valence_delta=-0.10) for _ in range(5)]
        palimpsest = MemoryPalimpsest(archive=record, layers=layers)
        # 0.1 + (-0.50 clamped) = -0.4, clamped to 0.0
        assert palimpsest.current_valence == 0.0

    def test_valence_never_above_one(self) -> None:
        """Even with drift, valence is clamped to [0.0, 1.0]."""
        record = make_message_record(valence=0.9, arousal=0.5, relational_significance=0.5)
        layers = [make_layer(valence_delta=0.10) for _ in range(5)]
        palimpsest = MemoryPalimpsest(archive=record, layers=layers)
        # 0.9 + 0.50 (clamped) = 1.4, clamped to 1.0
        assert palimpsest.current_valence == 1.0

    def test_current_reading_preserves_other_dimensions(self) -> None:
        """current_reading() preserves dominance, vulnerability, compass from archive."""
        esv = make_esv(
            valence=0.5,
            arousal=0.5,
            dominance=0.7,
            relational_significance=0.5,
            vulnerability_level=0.3,
            compass_direction=CompassDirection.SOUTH,
            compass_confidence=0.85,
        )
        record = MessageRecord(
            id="msg-002",
            session_id="session-002",
            timestamp=datetime.now(timezone.utc),
            sender="user",
            content="Test",
            tme=make_tme(),
            emotional_state=esv,
            storage_strength=esv.storage_strength,
            is_flashbulb=esv.is_flashbulb,
            compass_direction=CompassDirection.SOUTH,
            compass_skill_used=None,
        )
        layer = make_layer(valence_delta=0.05)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer])
        reading = palimpsest.current_reading()
        assert reading.dominance == 0.7
        assert reading.vulnerability_level == 0.3
        assert reading.compass_direction == CompassDirection.SOUTH
        assert reading.compass_confidence == 0.85

    def test_reading_at_filters_by_time(self) -> None:
        """reading_at() only applies layers before the given timestamp."""
        record = make_message_record(valence=0.5, arousal=0.5, relational_significance=0.5)
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 2, 1, tzinfo=timezone.utc)
        t3 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        layer1 = make_layer(valence_delta=0.05, timestamp=t1)
        layer2 = make_layer(valence_delta=0.05, timestamp=t2)
        layer3 = make_layer(valence_delta=0.05, timestamp=t3)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer1, layer2, layer3])

        # At t1: only layer1 applied
        reading_t1 = palimpsest.reading_at(t1)
        assert abs(reading_t1.valence - 0.55) < 1e-9

        # At t2: layers 1 and 2 applied
        reading_t2 = palimpsest.reading_at(t2)
        assert abs(reading_t2.valence - 0.60) < 1e-9

        # At t3: all three layers applied
        reading_t3 = palimpsest.reading_at(t3)
        assert abs(reading_t3.valence - 0.65) < 1e-9

    def test_evolution_summary_no_layers(self) -> None:
        """evolution_summary() with no layers returns the 'no reconsolidation' message."""
        record = make_message_record(valence=0.5)
        palimpsest = MemoryPalimpsest(archive=record)
        summary = palimpsest.evolution_summary()
        assert "No reconsolidation" in summary

    def test_evolution_summary_with_layers(self) -> None:
        """evolution_summary() describes the drift direction and layer count."""
        record = make_message_record(valence=0.5)
        layer = make_layer(valence_delta=0.05)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer])
        summary = palimpsest.evolution_summary()
        assert "1 time(s)" in summary
        assert "more positive" in summary
        assert "warmth" in summary  # reaction_type from make_layer

    def test_evolution_summary_negative_drift(self) -> None:
        """evolution_summary() reports 'more negative' when valence decreases."""
        record = make_message_record(valence=0.5)
        layer = make_layer(valence_delta=-0.05)
        palimpsest = MemoryPalimpsest(archive=record, layers=[layer])
        summary = palimpsest.evolution_summary()
        assert "more negative" in summary

    def test_custom_constraints(self) -> None:
        """Custom ReconsolidationConstraints override defaults."""
        constraints = ReconsolidationConstraints(
            MAX_DELTA_PER_LAYER=0.05,
            MAX_TOTAL_DRIFT=0.20,
            MIN_LAYERS_FOR_TREND=5,
            COOLDOWN_HOURS=48.0,
        )
        record = make_message_record(valence=0.5)
        layers = [make_layer(valence_delta=0.10) for _ in range(5)]
        palimpsest = MemoryPalimpsest(
            archive=record, layers=layers, constraints=constraints
        )
        # Total delta = 5 * 0.10 = 0.50, but clamped to 0.20 by custom constraints
        assert abs(palimpsest.current_valence - 0.7) < 1e-9
```

---

### Step 10.4: Run tests

Run this command from the project root:

- [x] Run `pytest tests/test_models.py -v` and confirm all tests pass (Done: 42 passed in 0.18s)

```bash
pytest tests/test_models.py -v
```

**Expected output:** All tests pass. You should see output like:

```
tests/test_models.py::TestEmotionalStateVector::test_storage_strength_formula PASSED
tests/test_models.py::TestEmotionalStateVector::test_storage_strength_zeros PASSED
tests/test_models.py::TestEmotionalStateVector::test_storage_strength_ones PASSED
tests/test_models.py::TestEmotionalStateVector::test_storage_strength_mixed PASSED
tests/test_models.py::TestEmotionalStateVector::test_is_flashbulb_both_above_threshold PASSED
tests/test_models.py::TestEmotionalStateVector::test_is_flashbulb_arousal_below PASSED
tests/test_models.py::TestEmotionalStateVector::test_is_flashbulb_significance_below PASSED
tests/test_models.py::TestEmotionalStateVector::test_is_flashbulb_both_at_boundary PASSED
tests/test_models.py::TestEmotionalStateVector::test_is_flashbulb_low_values PASSED
tests/test_models.py::TestTier0RawOutput::test_valence_exact_match PASSED
... (all Tier0RawOutput tests) ...
tests/test_models.py::TestMemoryPalimpsest::test_no_layers_returns_archive_values PASSED
... (all MemoryPalimpsest tests) ...

XX passed in X.XXs
```

**If any test fails:**
- Read the assertion error carefully. It will show the expected vs actual values.
- Double-check the formula in `EmotionalStateVector.storage_strength`.
- Double-check the threshold comparisons in `EmotionalStateVector.is_flashbulb` (must be strictly greater than 0.8, not greater-than-or-equal).
- Double-check the Tier0RawOutput validator alias dictionaries.
- Double-check the drift clamping logic in MemoryPalimpsest properties.

---

## Summary of Files Created

| Phase | File Path | Contents |
|-------|-----------|----------|
| 1 | `gwen/models/emotional.py` | CompassDirection, EmotionalStateVector |
| 2 | `gwen/models/temporal.py` | TimePhase, CircadianDeviationSeverity, TemporalMetadataEnvelope |
| 3 | `gwen/models/messages.py` | SessionType, SessionEndMode, MessageRecord, SessionRecord, ConsolidationType, ConsolidationJob |
| 4 | `gwen/models/memory.py` | MapEntity, MapEdge, EmotionalBaseline, EmotionalTrajectory, TriggerMapEntry, CompassEffectivenessRecord, RelationalField, BondState, GapClassification, GapAnalysis, ReturnContext, AnticipatoryPrime |
| 5 | `gwen/models/safety.py` | ThreatVector, ThreatSeverity, SafetyEvent, WellnessCheckpoint |
| 6 | `gwen/models/personality.py` | PersonalityModule |
| 7 | `gwen/models/classification.py` | Tier0RawOutput, HardwareProfile |
| 8 | `gwen/models/reconsolidation.py` | ReconsolidationLayer, ReconsolidationConstraints, MemoryPalimpsest |
| 9 | `gwen/models/__init__.py` | All exports |
| 10 | `tests/test_models.py` | 35 tests across 3 test classes |

**Total models defined:** 30 (enums, dataclasses, and Pydantic models)
**Total test functions:** 35
**Total source files:** 9 (8 model files + 1 test file)
