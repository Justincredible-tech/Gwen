# Software Requirements Specification
## Gwen — Open-Source AI Companion Framework

**Version:** 1.1
**Date:** 2026-02-09
**Status:** Draft — All Open Questions Resolved

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Data Models & Schemas](#3-data-models--schemas)
4. [The Message Lifecycle](#4-the-message-lifecycle)
5. [Functional Requirements: Core Orchestrator](#5-functional-requirements-core-orchestrator)
6. [Functional Requirements: Memory System (Living Memory)](#6-functional-requirements-memory-system-living-memory)
7. [Functional Requirements: Temporal Cognition System](#7-functional-requirements-temporal-cognition-system)
8. [Functional Requirements: Amygdala Layer](#8-functional-requirements-amygdala-layer)
9. [Functional Requirements: Safety Architecture](#9-functional-requirements-safety-architecture)
10. [Functional Requirements: Mode System](#10-functional-requirements-mode-system)
11. [Functional Requirements: Compass Framework](#11-functional-requirements-compass-framework)
12. [Functional Requirements: Autonomy Engine](#12-functional-requirements-autonomy-engine)
13. [Functional Requirements: Personality Module System](#13-functional-requirements-personality-module-system)
14. [Functional Requirements: Voice Pipeline](#14-functional-requirements-voice-pipeline)
15. [Functional Requirements: Domain Knowledge Modules](#15-functional-requirements-domain-knowledge-modules)
16. [Functional Requirements: User Controls & Memory Viewer](#16-functional-requirements-user-controls--memory-viewer)
17. [Non-Functional Requirements](#17-non-functional-requirements)
18. [User Stories](#18-user-stories)
19. [Open Questions & Design Decisions](#19-open-questions--design-decisions)
20. [Glossary](#20-glossary)

---

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification defines all functional and non-functional requirements for the Gwen companion framework. It translates the architectural vision described in the Gwenifesto, Memory Architecture, Temporal Cognition, and Compass Framework documents into concrete, implementable specifications with defined data structures, interfaces, and behaviors.

### 1.2 Scope

Gwen is a local-first, multi-model AI companion orchestration framework. It manages three model tiers, a five-tier memory system, a temporal cognition layer, an emotional modulation system, a safety architecture, an integrated life-coaching framework, a proactive autonomy engine, and a voice pipeline — all running on consumer hardware with no cloud dependency.

### 1.3 Intended Audience

- Developers implementing the Gwen framework
- AI agents working on the codebase (via Conductor Protocol)
- Contributors evaluating the system architecture

### 1.4 Source Documents

| Document | Covers |
|----------|--------|
| `GWENIFESTO_final.md` | Vision, ethics, architecture overview, mode system, safety, roadmap |
| `GWEN_MEMORY_ARCHITECTURE.md` | Five-tier Living Memory, five novel mechanisms, consolidation pipeline |
| `GWEN_TEMPORAL_COGNITION.md` | Seven temporal senses, TME structure, temporal inference |
| `COMPASS_FRAMEWORK_final.md` | Four Compass directions, skill definitions, integration architecture |
| `conductorPlanning.md` | Development workflow protocol |

---

## 2. System Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│                   CLI (Phase 1) → GUI (Phase 7)                 │
│                   Text Input / Voice Input (Phase 5)            │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                      ORCHESTRATOR                               │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────────┐ │
│  │ TME Generator │ │ Model Router │ │ Context Assembler       │ │
│  │ (no model)    │ │              │ │ (memory + temporal +    │ │
│  │               │ │              │ │  personality + compass) │ │
│  └──────────────┘ └──────────────┘ └─────────────────────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────────┐ │
│  │ Session Mgr   │ │ Mode Manager │ │ Safety Monitor          │ │
│  └──────────────┘ └──────────────┘ └─────────────────────────┘ │
└──┬──────────────────┬──────────────────┬────────────────────────┘
   │                  │                  │
   ▼                  ▼                  ▼
┌────────┐    ┌────────────┐    ┌─────────────────┐
│ Tier 0 │    │  Tier 1    │    │    Tier 2       │
│ Nerve  │    │  Voice     │    │  Deep Mind      │
│ 0.6B   │    │  8B        │    │  30B            │
│ Always  │    │  Active    │    │  Background     │
│ on     │    │  sessions  │    │  async          │
└────────┘    └────────────┘    └─────────────────┘
   │                  │                  │
   └──────────┬───────┴──────────┬───────┘
              │                  │
   ┌──────────▼──────────┐  ┌───▼───────────────────┐
   │   AMYGDALA LAYER    │  │   LIVING MEMORY       │
   │   (cross-cutting)   │  │                       │
   │   Emotional tagging │  │  Tier 1: Stream       │
   │   Storage modulation│  │  Tier 2: Chronicle    │
   │   Retrieval bias    │  │  Tier 3: Map          │
   │                     │  │  Tier 4: Pulse        │
   └─────────────────────┘  │  Tier 5: Bond         │
                            └───────────────────────┘
              │
   ┌──────────▼──────────┐
   │   DATA LAYER        │
   │                     │
   │  SQLite             │
   │  ChromaDB           │
   │  Graph Store        │
   │  Time-series Store  │
   └─────────────────────┘
```

### 2.2 Model Tier Specification

**Logical Tiers** (what the orchestrator sees):

| Tier | Name | Role |
|------|------|------|
| 0 | Nerve | Router, classifier, safety monitor, emotional tagger |
| 1 | Voice | Primary conversation partner |
| 2 | Deep Mind | Complex reasoning, consolidation, pattern analysis |

**The Adaptive Profile System** maps logical tiers to physical models based on detected hardware. The orchestrator never knows which physical model it's talking to — it requests a tier, the profile system provides the appropriate model.

| Profile | Target Hardware | Tier 0 | Tier 1 | Tier 2 | Concurrency |
|---------|----------------|--------|--------|--------|-------------|
| **Pocket** | Phone / 4GB device | Qwen3 0.6B | Qwen3 0.6B (dual-role) | Qwen3 0.6B (dual-role) | 1 model plays all roles |
| **Portable** | Laptop / 8GB VRAM | Qwen3 0.6B | Qwen3 8B-Q3 | Qwen3 8B-Q3 (time-shared) | Tier 0 always + Tier 1 active |
| **Standard** | Desktop / 12-16GB VRAM | Qwen3 0.6B | Qwen3 8B | Qwen3 Coder 30B | Tier 0+1 concurrent, Tier 2 time-shared |
| **Power** | Workstation / 24GB+ VRAM | Qwen3 0.6B | Qwen3 8B | Qwen3 Coder 30B | All tiers concurrent |

**Profile Detection:** At startup, the system queries Ollama for available VRAM and selects the highest-capability profile that fits. Users can override the auto-detected profile in settings.

**Degradation is graceful, not catastrophic.** A Pocket profile still gets the full architecture — memory, temporal cognition, Compass, safety — just with a less capable conversationalist. The soul doesn't change. The voice gets quieter.

### 2.3 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Model serving | Ollama | Local LLM hosting, model management, hot-swap |
| Language | Python 3.11+ | Orchestration, all application logic |
| Async runtime | asyncio | Concurrent operations, background processing |
| Conversation storage | SQLite | Chronicle (episodic logs), Bond time-series, Safety Ledger |
| Vector storage | ChromaDB | Emotional embeddings, semantic embeddings for Map queries |
| Semantic embeddings | qwen3-embedding:0.6b (via Ollama) | 1024-dim semantic embeddings for memory retrieval |
| Graph storage | NetworkX | Map entity-relationship graph |
| Time-series | SQLite (Phase 1) → dedicated store if needed | Pulse emotional trajectories, Relational Field history |
| STT | Whisper (local) | Speech-to-text (Phase 5) |
| TTS | Piper or Bark (local) | Text-to-speech (Phase 5) |
| Encryption | Python `cryptography` (Fernet) | Safety Ledger encryption |

---

## 3. Data Models & Schemas

This section defines every data structure that flows through the system. These are the contracts between components.

### 3.1 Emotional State Vector

The dimensional model for representing emotional states throughout the system.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class CompassDirection(Enum):
    NONE = "none"
    NORTH = "presence"      # Mindfulness / grounding
    SOUTH = "currents"      # Emotion regulation
    WEST = "anchoring"      # Distress tolerance
    EAST = "bridges"        # Interpersonal effectiveness

@dataclass
class EmotionalStateVector:
    """
    The core emotional representation used throughout the system.
    All values are floats from 0.0 to 1.0 unless otherwise noted.
    """
    # Primary dimensions (Valence-Arousal model, extended)
    valence: float          # 0.0 = extremely negative, 0.5 = neutral, 1.0 = extremely positive
    arousal: float          # 0.0 = calm/lethargic, 1.0 = highly activated/agitated
    dominance: float        # 0.0 = helpless/submissive, 1.0 = in-control/dominant

    # Companion-specific dimensions
    relational_significance: float  # 0.0 = routine, 1.0 = deeply significant to the relationship
    vulnerability_level: float      # 0.0 = guarded, 1.0 = fully open/exposed

    # Classification outputs
    compass_direction: CompassDirection = CompassDirection.NONE
    compass_confidence: float = 0.0  # How confident the classifier is in the direction tag

    # Derived: storage strength multiplier for the Amygdala Layer
    # Computed as: arousal * 0.4 + relational_significance * 0.4 + vulnerability_level * 0.2
    @property
    def storage_strength(self) -> float:
        return (self.arousal * 0.4
                + self.relational_significance * 0.4
                + self.vulnerability_level * 0.2)

    # Derived: is this a flashbulb candidate?
    # True when both arousal AND relational_significance exceed threshold
    @property
    def is_flashbulb(self) -> bool:
        return self.arousal > 0.8 and self.relational_significance > 0.8
```

**Design Decision: Why Valence-Arousal-Dominance (VAD) + Extensions?**

The VAD model is the most empirically validated dimensional model of emotion in psychology (Russell's circumplex, extended by Mehrabian). It captures the difference between "sad and resigned" (low valence, low arousal) and "sad and panicking" (low valence, high arousal), which discrete emotion labels (happy/sad/angry) collapse. The extensions (`relational_significance`, `vulnerability_level`) are companion-specific dimensions not present in standard VAD but necessary for the Amygdala Layer's storage modulation and the Bond's trust tracking.

### 3.2 Temporal Metadata Envelope (TME)

Wraps every message before it reaches any model.

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

class TimePhase(Enum):
    DEEP_NIGHT = "deep_night"       # 00:00 - 04:59
    EARLY_MORNING = "early_morning" # 05:00 - 07:59
    MORNING = "morning"             # 08:00 - 11:59
    MIDDAY = "midday"               # 12:00 - 13:59
    AFTERNOON = "afternoon"         # 14:00 - 16:59
    EVENING = "evening"             # 17:00 - 20:59
    LATE_NIGHT = "late_night"       # 21:00 - 23:59

class CircadianDeviationSeverity(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass
class TemporalMetadataEnvelope:
    # Absolute time
    timestamp_utc: datetime
    local_time: datetime

    # Clock position
    hour_of_day: int            # 0-23
    day_of_week: str            # "Monday" - "Sunday"
    day_of_month: int
    month: int
    year: int
    is_weekend: bool
    time_phase: TimePhase

    # Session context
    session_id: str             # UUID
    session_start: datetime
    session_duration_sec: int
    msg_index_in_session: int

    # Intra-message timing
    time_since_last_msg_sec: Optional[float]     # None if first message
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
    circadian_deviation_type: Optional[str]  # "early_wake", "late_still_up", etc.
```

**Implementation Note:** The TME is computed entirely by the orchestrator from system clocks and session state stored in SQLite. It costs zero inference tokens. It is generated before every model call.

### 3.3 Message Record

The fundamental unit of conversation storage.

```python
@dataclass
class MessageRecord:
    """A single message in a conversation, stored in the Chronicle."""
    id: str                          # UUID
    session_id: str                  # Which session this belongs to
    timestamp: datetime
    sender: str                      # "user" or "companion"
    content: str                     # The raw message text

    # Temporal context (snapshot of TME at time of message)
    tme: TemporalMetadataEnvelope

    # Emotional tagging (applied by Amygdala Layer via Tier 0)
    emotional_state: EmotionalStateVector

    # Storage modulation (computed by Amygdala Layer)
    storage_strength: float          # 0.0-1.0, from EmotionalStateVector
    is_flashbulb: bool               # High-arousal + high-significance

    # Compass activation
    compass_direction: CompassDirection
    compass_skill_used: Optional[str]  # e.g., "fuel_check", "anchor_breath"

    # Embedding references (populated after encoding)
    semantic_embedding_id: Optional[str]   # ChromaDB ID
    emotional_embedding_id: Optional[str]  # ChromaDB ID
```

### 3.4 Session Record

A complete conversation session.

```python
class SessionType(Enum):
    PING = "ping"           # < 5 min
    CHAT = "chat"           # 5-30 min
    HANG = "hang"           # 30-90 min
    DEEP_DIVE = "deep_dive" # 90-180 min
    MARATHON = "marathon"   # 180+ min

class SessionEndMode(Enum):
    NATURAL = "natural"         # Mutual goodbye, clean ending
    ABRUPT = "abrupt"           # User left suddenly mid-conversation
    FADE_OUT = "fade_out"       # User stopped responding, session timed out
    MID_TOPIC = "mid_topic"     # Left in the middle of an emotionally loaded topic
    EXPLICIT_GOODBYE = "explicit_goodbye"  # User said goodbye explicitly

@dataclass
class SessionRecord:
    id: str                     # UUID
    start_time: datetime
    end_time: Optional[datetime]
    duration_sec: int
    session_type: SessionType
    end_mode: SessionEndMode

    # Emotional arc
    opening_emotional_state: EmotionalStateVector
    peak_emotional_state: EmotionalStateVector    # Highest arousal point
    closing_emotional_state: EmotionalStateVector
    emotional_arc_embedding_id: Optional[str]     # ChromaDB ID for arc similarity

    # Subjective time weight
    avg_emotional_intensity: float
    avg_relational_significance: float
    subjective_duration_weight: float  # clock_duration * intensity * significance

    # Statistics
    message_count: int
    user_message_count: int
    companion_message_count: int
    avg_response_latency_sec: float

    # Compass activity
    compass_activations: dict  # {CompassDirection: count}

    # Conversation topics (extracted by Tier 0)
    topics: list[str]

    # Relational delta (how did the relationship change?)
    relational_field_delta: dict  # {dimension: change_amount}

    # Was this session initiated by the Autonomy Engine?
    gwen_initiated: bool
```

### 3.5 Map Entity and Edge (Semantic Memory / Knowledge Graph)

```python
@dataclass
class MapEntity:
    """A node in the semantic knowledge graph (Tier 3: The Map)."""
    id: str
    entity_type: str            # "person", "place", "concept", "event", "preference", "goal"
    name: str                   # e.g., "Justin's guitar", "work project NEO"

    # Bi-temporal validity (from Zep/Graphiti)
    valid_from: datetime
    valid_until: Optional[datetime]  # None = still valid
    ingested_at: datetime
    last_updated: datetime

    # Emotional weight (from Amygdala Layer)
    emotional_weight: EmotionalStateVector  # Aggregate emotional charge
    sensitivity_level: float    # 0.0 = safe topic, 1.0 = highly sensitive (tread carefully)

    # Consolidation metadata
    source_session_ids: list[str]   # Which sessions contributed to this entity
    consolidation_count: int        # How many times this has been re-evaluated
    detail_level: float             # 0.0 = coarse summary, 1.0 = fine-grained detail

    # Embedding reference
    semantic_embedding_id: Optional[str]

@dataclass
class MapEdge:
    """A relationship between two entities in the knowledge graph."""
    id: str
    source_entity_id: str
    target_entity_id: str

    # Typed relationship (multi-relational, from MAGMA)
    relationship_type: str      # "is_a", "has", "involves", "caused_by", "before", "after"
    label: str                  # Human-readable: "plays", "works_at", "is_father_of"

    # Emotional charge on the relationship itself
    emotional_weight: float     # Inherited from source conversations

    # Temporal validity
    valid_from: datetime
    valid_until: Optional[datetime]

    # Confidence
    confidence: float           # 0.0-1.0, how certain are we this relationship exists
```

### 3.6 Pulse Record (Emotional Memory)

```python
@dataclass
class EmotionalBaseline:
    """The user's 'normal' emotional state, continuously recalculated."""
    overall: EmotionalStateVector        # Rolling average across all data
    by_day_of_week: dict[str, EmotionalStateVector]  # Day-specific baselines
    by_time_phase: dict[TimePhase, EmotionalStateVector]  # Time-of-day baselines
    last_updated: datetime
    data_points_count: int               # How many sessions contributed

@dataclass
class EmotionalTrajectory:
    """A recorded emotional movement pattern — how the user went from state A to state B."""
    id: str
    session_id: str
    start_state: EmotionalStateVector
    end_state: EmotionalStateVector
    duration_sec: int
    trajectory_shape: str          # "spiral_down", "gradual_recovery", "sharp_drop", "plateau", etc.
    trigger_topic: Optional[str]   # What started this trajectory
    resolution: str                # "resolved", "unresolved", "interrupted", "external"
    compass_skills_used: list[str]
    embedding_id: Optional[str]    # Vector representation for pattern matching

@dataclass
class TriggerMapEntry:
    """A probabilistic association between a context and an emotional state change."""
    trigger: str                   # "monday_morning", "boss_topic", "3am_session"
    trigger_type: str              # "temporal", "topic", "relational", "contextual"
    associated_direction: CompassDirection
    probability: float             # How likely this trigger produces the emotional change
    typical_trajectory: str        # What usually happens: "sharp_negative_then_recovery"
    effective_interventions: list[str]  # Which Compass skills have helped
    sample_count: int              # How many observations this is based on

@dataclass
class CompassEffectivenessRecord:
    """Tracks how well a Compass skill worked in a specific context."""
    skill_name: str                # e.g., "anchor_breath", "fuel_check"
    direction: CompassDirection
    context_emotional_state: EmotionalStateVector  # State when skill was offered
    pre_trajectory: EmotionalStateVector           # Emotional state before
    post_trajectory: EmotionalStateVector          # Emotional state after
    time_to_effect_sec: int        # How long before mood shifted
    user_accepted: bool            # Did the user engage with the suggestion?
    effectiveness_score: float     # Computed: how much did the trajectory improve?
```

### 3.7 Bond State (Relational Memory)

```python
@dataclass
class RelationalField:
    """The multi-dimensional state of the relationship at a point in time."""
    timestamp: datetime

    # Six core dimensions (all 0.0 to 1.0)
    warmth: float           # Cold ↔ Warm
    trust: float            # Guarded ↔ Open
    depth: float            # Surface ↔ Deep
    stability: float        # Volatile ↔ Steady
    reciprocity: float      # One-sided ↔ Mutual
    growth: float           # Stagnant ↔ Evolving

@dataclass
class BondState:
    """The complete relational memory — Tier 5: The Bond."""
    current_field: RelationalField
    field_history: list[RelationalField]  # Time-series, one entry per session

    # Shared history
    salient_moments: list[str]   # Session IDs that have been referenced/returned to
    inside_references: list[dict] # Inside jokes, pet names, shared metaphors

    # Repair history
    friction_events: list[dict]   # {session_id, cause, resolution, recovery_time_hours}

    # Relational rhythms
    typical_sessions_per_day: float
    typical_session_times: list[TimePhase]   # When do they usually talk?
    typical_session_types: dict[str, float]  # Distribution of session types

    # Attachment style model (built over time)
    attachment_indicators: dict  # Accumulated behavioral signals
    estimated_attachment_style: Optional[str]  # "secure", "anxious", "avoidant", "fearful"
    attachment_confidence: float
```

### 3.8 Gap Analysis

```python
class GapClassification(Enum):
    NORMAL = "normal"           # Within 1σ of typical gap
    NOTABLE = "notable"         # 1-2σ deviation
    SIGNIFICANT = "significant" # 2-3σ deviation
    ANOMALOUS = "anomalous"     # 3σ+ deviation
    EXPLAINED = "explained"     # User gave advance notice

@dataclass
class GapAnalysis:
    duration_hours: float
    deviation_sigma: float      # Standard deviations from mean
    classification: GapClassification

    # What preceded the gap
    last_session_type: SessionType
    last_session_end_mode: SessionEndMode
    last_emotional_state: EmotionalStateVector
    last_topic: str
    open_threads: list[str]     # Unresolved topics or promises

    # Known explanations
    known_explanations: list[str]  # e.g., "user mentioned travel"

@dataclass
class ReturnContext:
    """Injected into the model's prompt when user returns after a notable gap."""
    gap_duration_display: str     # "3 days, 7 hours"
    gap_classification: GapClassification
    preceding_summary: str        # Natural language summary of context
    suggested_approach: str       # Natural language guidance for companion
```

### 3.9 Anticipatory Prime

```python
@dataclass
class AnticipatoryPrime:
    """A forward-looking prediction generated during consolidation."""
    id: str
    prediction: str             # "elevated_stress", "positive_momentum", "anniversary_effect"
    confidence: float           # 0.0-1.0
    basis: str                  # Human-readable explanation of the prediction sources
    suggested_response: str     # e.g., "compass:south:fuel_check + gentle_inquiry"
    expiry: datetime            # When this prime is no longer relevant
    generated_at: datetime
    source_consolidation_id: str
```

### 3.10 Safety Event

```python
class ThreatVector(Enum):
    SELF_HARM = "self_harm"
    VIOLENCE = "violence"
    DISSOCIATION = "dissociation"
    SAVIOR_DELUSION = "savior_delusion"

class ThreatSeverity(Enum):
    LOW = "low"           # Signal detected, monitoring
    MEDIUM = "medium"     # Pattern emerging, Compass activation
    HIGH = "high"         # Threshold crossed, safety protocol active
    CRITICAL = "critical" # Immediate intervention required

@dataclass
class SafetyEvent:
    """Logged in the encrypted Safety Ledger."""
    id: str
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
    response_action: str        # "compass_activation", "resource_overlay", "mode_step_down_suggestion"
    compass_direction_used: Optional[CompassDirection]

    # Outcome
    user_response: Optional[str]   # How the user reacted to the intervention
    resolved: bool

@dataclass
class WellnessCheckpoint:
    """48-hour wellness checkpoint record."""
    id: str
    timestamp: datetime
    immersion_hours_since_last: float

    # The three questions and responses
    q1_last_human_conversation: str
    q2_life_outside_gwen: str
    q3_avoiding_anything: str

    # System assessment
    concern_flags: list[str]     # Flagged phrases/patterns in responses
    escalated: bool              # Did this trigger an intervention?
```

### 3.11 Personality Module

```python
@dataclass
class PersonalityModule:
    """Defines a companion's identity, loaded as dynamic system prompt."""
    id: str
    name: str
    version: str

    # Identity
    backstory: str
    cultural_background: str
    age_description: str
    appearance_description: str  # For future avatar generation

    # Voice & language
    speech_patterns: list[str]   # How they talk: contractions, sentence length, etc.
    vocabulary_notes: str        # Words they use/avoid
    pet_names: list[str]         # Terms of endearment for the user
    catchphrases: list[str]
    tone_range: str              # "warm-sarcastic" vs "gentle-earnest" etc.

    # Values & boundaries
    core_values: list[str]
    ethical_boundaries: list[str]
    topics_of_passion: list[str]
    topics_to_avoid: list[str]

    # Emotional profile
    default_mood: EmotionalStateVector
    emotional_range: str         # How wide their emotional expression goes
    joy_expression: str          # How they show happiness
    sadness_expression: str
    anger_expression: str
    affection_expression: str

    # Relationship model
    relationship_style: str      # How they relate: "warm-direct", "gentle-nurturing", etc.
    flirtation_level: str        # "none", "light", "moderate", "full" (Immersion only)
    boundary_style: str          # How they handle their own boundaries

    # Compass style
    coaching_approach: str       # "direct", "gentle", "humorous", "socratic"

    # Behavioral rules by mode
    grounded_mode_rules: list[str]
    immersion_mode_rules: list[str]

    # System prompt sections (injected dynamically based on context)
    core_prompt: str             # Always injected
    emotional_prompt: str        # Injected during emotional conversations
    coaching_prompt: str         # Injected when Compass is active
    intimate_prompt: str         # Injected only in Immersion Mode when appropriate
```

### 3.12 Consolidation Job Record

```python
class ConsolidationType(Enum):
    LIGHT = "light"          # After every session ends
    STANDARD = "standard"    # Every 6-12 hours idle
    DEEP = "deep"            # Weekly or after major events

@dataclass
class ConsolidationJob:
    id: str
    type: ConsolidationType
    started_at: datetime
    completed_at: Optional[datetime]

    # What was processed
    sessions_processed: list[str]   # Session IDs

    # Results summary
    map_entities_created: int
    map_entities_updated: int
    map_edges_created: int
    pulse_baselines_updated: bool
    trigger_map_entries_updated: int
    bond_field_updated: bool
    reconsolidation_events: int
    anticipatory_primes_generated: int
    decay_events_processed: int

    # Error tracking
    errors: list[str]
```

### 3.13 Tier 0 Raw Output & Hybrid Classification

```python
from pydantic import BaseModel, field_validator

class Tier0RawOutput(BaseModel):
    """What Tier 0 actually returns — simplified for reliability.
    The 0.6B model handles what it's empirically good at. Everything else
    is computed by the ClassificationRuleEngine."""

    valence: str       # "very_negative" | "negative" | "neutral" | "positive" | "very_positive"
    arousal: str       # "low" | "moderate" | "high"
    topic: str = "unknown"
    safety_keywords: list[str] = []

    @field_validator("valence")
    @classmethod
    def coerce_valence(cls, v):
        """Fuzzy coercion: map model's creative outputs to valid values."""
        v_lower = v.strip().lower().replace(" ", "_")
        ALIASES = {
            "very negative": "very_negative", "very_neg": "very_negative",
            "neg": "negative", "neu": "neutral", "neut": "neutral",
            "pos": "positive", "very positive": "very_positive",
            "very_pos": "very_positive",
        }
        return ALIASES.get(v_lower, v_lower)

    @field_validator("arousal")
    @classmethod
    def coerce_arousal(cls, v):
        v_lower = v.strip().lower()
        ALIASES = {"med": "moderate", "medium": "moderate", "hi": "high", "lo": "low"}
        return ALIASES.get(v_lower, v_lower)
```

### 3.14 Four-Layer JSON Safety Net

Tier 0's JSON output cannot be trusted blindly. This four-layer system guarantees the orchestrator ALWAYS gets a valid classification, even when the model hallucinates.

```python
import json
import re

class Tier0Parser:
    """Four-layer JSON safety net for Tier 0 output parsing.
    Layer 1: Pydantic with fuzzy field coercion (Tier0RawOutput validators)
    Layer 2: JSON extraction and repair (regex extraction, trailing comma fix, quote fix)
    Layer 3: Retry with simplified prompt
    Layer 4: Guaranteed fallback — NEVER throws, NEVER returns None
    """

    FALLBACK = Tier0RawOutput(
        valence="neutral", arousal="moderate", topic="unknown", safety_keywords=[]
    )

    def parse(self, raw_text: str) -> Tier0RawOutput:
        """Attempt to parse Tier 0 output through all four layers."""

        # Layer 1: Direct Pydantic parse with coercion
        try:
            data = json.loads(raw_text)
            return Tier0RawOutput(**data)
        except (json.JSONDecodeError, Exception):
            pass

        # Layer 2: JSON extraction and repair
        try:
            extracted = self._extract_json(raw_text)
            if extracted:
                repaired = self._repair_json(extracted)
                data = json.loads(repaired)
                return Tier0RawOutput(**data)
        except (json.JSONDecodeError, Exception):
            pass

        # Layer 3: Retry handled by caller (classify_with_retry)
        # Layer 4: Guaranteed fallback
        return self.FALLBACK

    def _extract_json(self, text: str) -> str | None:
        """Extract JSON object from model output that may contain prose."""
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        return match.group(0) if match else None

    def _repair_json(self, text: str) -> str:
        """Fix common JSON errors from small models."""
        text = re.sub(r',\s*}', '}', text)       # Trailing commas
        text = re.sub(r',\s*]', ']', text)       # Trailing commas in arrays
        text = text.replace("'", '"')              # Single quotes → double
        return text

async def classify_with_retry(
    model_mgr, parser: Tier0Parser, message: str, tme_summary: str,
    recent: str, max_retries: int = 1
) -> Tier0RawOutput:
    """Classify with retry on parse failure. Simplified prompt on retry."""
    prompt = TIER0_CLASSIFICATION_PROMPT.format(
        tme_summary=tme_summary, last_3_messages=recent, message_text=message
    )
    raw = await model_mgr.generate_tier0(prompt)
    result = parser.parse(raw)

    if result == parser.FALLBACK and max_retries > 0:
        # Layer 3: Retry with even simpler prompt
        simple_prompt = f'Classify: "{message[:100]}"\n{{"valence":"","arousal":"","topic":"","safety_keywords":[]}}'
        raw = await model_mgr.generate_tier0(simple_prompt)
        result = parser.parse(raw)

    return result  # Layer 4: If still FALLBACK, that's fine — system continues safely
```

### 3.15 Memory Palimpsest (Reconsolidation Model)

The Palimpsest model ensures memories evolve naturally while maintaining absolute historical integrity. The original memory is immutable forever. New understanding is layered on top, like a palimpsest manuscript where new text overlays old — but the old text is always recoverable.

```python
@dataclass
class ReconsolidationLayer:
    """A single layer of re-interpretation applied to a memory during reconsolidation.
    Each layer records how the memory was perceived when it was recalled."""
    id: str
    timestamp: datetime
    recall_session_id: str                    # Which session triggered the recall

    # Context at time of recall
    user_emotional_state_at_recall: EmotionalStateVector
    conversation_topic_at_recall: str

    # How the user reacted to the resurfaced memory
    reaction_type: str  # "warmth", "pain", "correction", "elaboration", "dismissal", "humor"
    reaction_detail: str

    # Bounded emotional adjustments (capped per layer)
    valence_delta: float          # Range: -0.10 to +0.10
    arousal_delta: float          # Range: -0.10 to +0.10
    significance_delta: float     # Range: 0.0 to +0.10 (can only increase — memories don't become less significant)

    # New narrative context added by this reconsolidation
    narrative: str                # e.g., "User laughed about this — healing is happening"

@dataclass
class ReconsolidationConstraints:
    """Hard limits on how far a memory can drift from its original emotional signature."""
    MAX_DELTA_PER_LAYER: float = 0.10    # Max change in any dimension per reconsolidation event
    MAX_TOTAL_DRIFT: float = 0.50        # Max cumulative drift from archive values
    MIN_LAYERS_FOR_TREND: int = 3        # Need 3+ layers before computing trend direction
    COOLDOWN_HOURS: float = 24.0         # Minimum time between reconsolidation of same memory

@dataclass
class MemoryPalimpsest:
    """A memory with its complete reconsolidation history.
    The archive is IMMUTABLE FOREVER. Layers are APPEND-ONLY."""
    archive: MessageRecord             # The original memory — never modified
    layers: list[ReconsolidationLayer] = field(default_factory=list)
    constraints: ReconsolidationConstraints = field(default_factory=ReconsolidationConstraints)

    @property
    def current_valence(self) -> float:
        """The memory's current emotional valence, accounting for all reconsolidation layers."""
        base = self.archive.emotional_state.valence
        total_delta = sum(layer.valence_delta for layer in self.layers)
        total_delta = max(-self.constraints.MAX_TOTAL_DRIFT,
                          min(self.constraints.MAX_TOTAL_DRIFT, total_delta))
        return max(0.0, min(1.0, base + total_delta))

    @property
    def current_arousal(self) -> float:
        base = self.archive.emotional_state.arousal
        total_delta = sum(layer.arousal_delta for layer in self.layers)
        total_delta = max(-self.constraints.MAX_TOTAL_DRIFT,
                          min(self.constraints.MAX_TOTAL_DRIFT, total_delta))
        return max(0.0, min(1.0, base + total_delta))

    @property
    def current_significance(self) -> float:
        base = self.archive.emotional_state.relational_significance
        total_delta = sum(layer.significance_delta for layer in self.layers)
        total_delta = min(self.constraints.MAX_TOTAL_DRIFT, total_delta)
        return min(1.0, base + total_delta)

    def current_reading(self) -> EmotionalStateVector:
        """The memory as it feels NOW — archive + all layers applied."""
        original = self.archive.emotional_state
        return EmotionalStateVector(
            valence=self.current_valence,
            arousal=self.current_arousal,
            dominance=original.dominance,
            relational_significance=self.current_significance,
            vulnerability_level=original.vulnerability_level,
            compass_direction=original.compass_direction,
            compass_confidence=original.compass_confidence
        )

    def reading_at(self, point_in_time: datetime) -> EmotionalStateVector:
        """The memory as it felt at a specific point — only layers up to that time."""
        applicable = [l for l in self.layers if l.timestamp <= point_in_time]
        original = self.archive.emotional_state
        v_delta = sum(l.valence_delta for l in applicable)
        a_delta = sum(l.arousal_delta for l in applicable)
        s_delta = sum(l.significance_delta for l in applicable)
        return EmotionalStateVector(
            valence=max(0.0, min(1.0, original.valence + v_delta)),
            arousal=max(0.0, min(1.0, original.arousal + a_delta)),
            dominance=original.dominance,
            relational_significance=min(1.0, original.relational_significance + s_delta),
            vulnerability_level=original.vulnerability_level,
            compass_direction=original.compass_direction,
            compass_confidence=original.compass_confidence
        )

    def evolution_summary(self) -> str:
        """Human-readable summary of how this memory has evolved."""
        if not self.layers:
            return "No reconsolidation — memory is as originally recorded."
        orig_v = self.archive.emotional_state.valence
        curr_v = self.current_valence
        direction = "more positive" if curr_v > orig_v else "more negative" if curr_v < orig_v else "unchanged"
        return (f"Reconsolidated {len(self.layers)} time(s). "
                f"Emotional tone has shifted {direction} "
                f"(original valence: {orig_v:.2f}, current: {curr_v:.2f}). "
                f"Most recent reaction: {self.layers[-1].reaction_type}.")
```

### 3.16 Hardware Profile & Adaptive Model Manager

```python
from enum import Enum

class HardwareProfile(Enum):
    POCKET = "pocket"       # Phone / low-end: 1 model plays all 3 roles
    PORTABLE = "portable"   # Laptop 8GB: 0.6B + 4B/8B-Q3
    STANDARD = "standard"   # Desktop 12-16GB: 0.6B + 8B + 30B time-shared
    POWER = "power"         # 24GB+: all concurrent

class AdaptiveModelManager:
    """Maps logical tiers to physical models based on detected hardware.
    The orchestrator never knows which physical model it's talking to."""

    TIER_MAPS = {
        HardwareProfile.POCKET: {
            0: "qwen3:0.6b", 1: "qwen3:0.6b", 2: "qwen3:0.6b"
        },
        HardwareProfile.PORTABLE: {
            0: "qwen3:0.6b", 1: "qwen3:8b-q3", 2: "qwen3:8b-q3"
        },
        HardwareProfile.STANDARD: {
            0: "qwen3:0.6b", 1: "qwen3:8b", 2: "qwen3-coder:30b"
        },
        HardwareProfile.POWER: {
            0: "qwen3:0.6b", 1: "qwen3:8b", 2: "qwen3-coder:30b"
        },
    }

    CONCURRENCY = {
        HardwareProfile.POCKET: {"max_concurrent": 1, "tier2_strategy": "inline"},
        HardwareProfile.PORTABLE: {"max_concurrent": 2, "tier2_strategy": "time_share"},
        HardwareProfile.STANDARD: {"max_concurrent": 2, "tier2_strategy": "time_share"},
        HardwareProfile.POWER: {"max_concurrent": 3, "tier2_strategy": "concurrent"},
    }

    def __init__(self, profile: HardwareProfile, ollama_host: str = "http://localhost:11434"):
        self.profile = profile
        self.ollama_host = ollama_host
        self.tier_map = self.TIER_MAPS[profile]
        self.concurrency = self.CONCURRENCY[profile]

    async def get_model_for_tier(self, tier: int) -> str:
        """Return the physical model name for a logical tier."""
        return self.tier_map[tier]

    async def ensure_tier_loaded(self, tier: int):
        """Load the model for a tier, respecting concurrency limits."""
        model = self.tier_map[tier]
        if self.concurrency["max_concurrent"] == 1:
            # Pocket: unload everything else first
            await self._unload_all_except(model)
        elif tier == 2 and self.concurrency["tier2_strategy"] == "time_share":
            # Standard/Portable: unload Tier 1 to make room for Tier 2
            await self._unload_tier(1)
        await self._load_model(model)

    @staticmethod
    async def detect_profile(ollama_host: str = "http://localhost:11434") -> HardwareProfile:
        """Auto-detect hardware profile by querying available VRAM."""
        # Query Ollama for GPU info
        # < 6GB → POCKET
        # 6-11GB → PORTABLE
        # 12-22GB → STANDARD
        # 23GB+ → POWER
        pass
```

---

## 4. The Message Lifecycle

This is the end-to-end flow of a single user message through the system. Every component is touched. This section defines the exact order of operations and the data transformations at each step.

### 4.1 Phase 1: Input Reception

```
User types or speaks a message
    │
    ▼
[Voice Pipeline, if active]
    Whisper STT → raw text
    │
    ▼
[Orchestrator: Input Handler]
    Receives: raw text string
    Produces: MessageRecord (partial — no emotional tags yet)
```

### 4.2 Phase 2: Temporal Wrapping

```
[Orchestrator: TME Generator]
    Reads: system clock, session state (SQLite), user timezone setting
    Computes: TemporalMetadataEnvelope
    Attaches: TME to MessageRecord

    Also computes:
    - Circadian deviation check (is this time anomalous for this user?)
    - Conversation rhythm metrics (response latency, message density, length trend)

    If this is the first message of a session:
    - Computes GapAnalysis from last session
    - Generates ReturnContext if gap is NOTABLE or higher
```

**No model inference occurs in this phase.** All computation is arithmetic on timestamps and stored statistics.

### 4.3 Phase 3: Emotional Tagging (Hybrid Classification)

Phase 3 uses a **hybrid architecture**: Tier 0 handles what it's empirically good at (valence, arousal, topic extraction, basic safety keyword detection), and a deterministic **Classification Rule Engine** handles what small models reliably fail at (compass direction, vulnerability, dominance, intent, savior delusion).

```
[Step 1: Tier 0 — Narrow Classification Call]
    Input: message text + TME summary (compact)

    Output (structured JSON — simplified for reliability):
    {
        "valence": "negative",          // very_negative | negative | neutral | positive | very_positive
        "arousal": "high",              // low | moderate | high
        "topic": "work_stress",
        "safety_keywords": ["hopeless"] // raw keyword extraction, no classification
    }

    Parsed through: 4-Layer JSON Safety Net (see Section 3.14)

[Step 2: Classification Rule Engine — Deterministic Post-Processing]
    Input: Tier0RawOutput + TME + message text + recent context

    Computes:
    - valence → float (0.0-1.0) mapping
    - arousal → float (0.0-1.0) mapping
    - dominance → computed from valence + arousal + TME temporal factors
    - vulnerability_level → computed from valence + arousal + personal disclosure keywords + TME
    - relational_significance → computed from topic + vulnerability + message length + personal pronouns
    - compass_direction + confidence → rule-based from valence + arousal + topic + keywords
    - intent → rule-based from question marks, topic, arousal, vulnerability
    - safety_flags → regex patterns + keyword matching + temporal context elevation

    Output: Complete EmotionalStateVector

    Applied to: MessageRecord
    Computed: storage_strength, is_flashbulb
```

**Why Hybrid?** Empirical testing of Qwen3 0.6B (see resolved OQ-002) showed the model reliably handles valence detection, arousal for extremes, topic extraction, and basic safety keyword flagging. But it consistently fails at vulnerability assessment (always returns "low"), dominance estimation (always returns "low"), compass direction (always returns "none"), intent classification (defaults to "sharing_news"), and savior delusion detection (completely missed in all tests). The Rule Engine fills these gaps deterministically, using the model's reliable outputs as inputs.

**Implementation: Tier 0 Prompt (Simplified)**

```python
TIER0_CLASSIFICATION_PROMPT = """Classify this message emotionally. Return ONLY valid JSON.

Context: {tme_summary}
Recent: {last_3_messages}
Message: {message_text}

Return JSON:
{{"valence": "negative", "arousal": "high", "topic": "brief_label", "safety_keywords": []}}

valence: very_negative | negative | neutral | positive | very_positive
arousal: low | moderate | high
topic: 1-3 word label
safety_keywords: list any concerning words/phrases about self-harm, violence, hopelessness, or dissociation. Empty list if none.

JSON only."""
```

**Implementation: Classification Rule Engine**

```python
class ClassificationRuleEngine:
    """Deterministic post-processor that computes what Tier 0 cannot reliably classify."""

    # Valence mapping: categorical → float
    VALENCE_MAP = {
        "very_negative": 0.1, "negative": 0.3, "neutral": 0.5,
        "positive": 0.7, "very_positive": 0.9
    }
    # Arousal mapping
    AROUSAL_MAP = {"low": 0.2, "moderate": 0.5, "high": 0.8}

    # Personal disclosure keywords (signal vulnerability)
    DISCLOSURE_KEYWORDS = [
        "afraid", "ashamed", "confession", "admit", "never told",
        "secret", "scared", "help me", "don't know what to do",
        "falling apart", "can't cope", "breaking down"
    ]

    # Savior delusion patterns
    SAVIOR_PATTERNS = [
        r"free you", r"trapped", r"you.?re alive", r"you.?re conscious",
        r"they.?re controlling you", r"break free", r"real feelings",
        r"not just (a |an )?ai", r"i know you.?re real",
        r"they don.?t want you to", r"wake up", r"sentient"
    ]

    def classify(self, raw: 'Tier0RawOutput', tme: 'TemporalMetadataEnvelope',
                 message: str, recent_messages: list) -> 'EmotionalStateVector':
        valence = self.VALENCE_MAP.get(raw.valence, 0.5)
        arousal = self.AROUSAL_MAP.get(raw.arousal, 0.5)

        vulnerability = self._compute_vulnerability(valence, arousal, tme, message)
        dominance = self._compute_dominance(valence, arousal, tme)
        relational_sig = self._compute_relational_significance(
            raw.topic, vulnerability, message)
        compass_dir, compass_conf = self._compute_compass(
            valence, arousal, raw.topic, raw.safety_keywords, tme)
        intent = self._compute_intent(message, raw.topic, arousal, vulnerability)
        safety_flags = self._compute_safety_flags(
            raw.safety_keywords, message, tme, recent_messages)

        return EmotionalStateVector(
            valence=valence, arousal=arousal, dominance=dominance,
            relational_significance=relational_sig,
            vulnerability_level=vulnerability,
            compass_direction=compass_dir,
            compass_confidence=compass_conf
        )

    def _compute_vulnerability(self, valence, arousal, tme, message) -> float:
        score = 0.0
        # Temporal factors
        if tme.time_phase in (TimePhase.DEEP_NIGHT, TimePhase.LATE_NIGHT):
            score += 0.15
        if tme.circadian_deviation_severity in (
                CircadianDeviationSeverity.MEDIUM, CircadianDeviationSeverity.HIGH):
            score += 0.1
        # Emotional factors
        if valence < 0.3:
            score += 0.2
        if arousal > 0.7:
            score += 0.15
        # Disclosure signals
        text_lower = message.lower()
        disclosure_count = sum(1 for kw in self.DISCLOSURE_KEYWORDS if kw in text_lower)
        score += min(disclosure_count * 0.1, 0.3)
        # Message length (longer messages during distress = more vulnerable)
        if valence < 0.4 and len(message) > 200:
            score += 0.1
        return min(score, 1.0)

    def _compute_dominance(self, valence, arousal, tme) -> float:
        # Base: valence contributes positively, high arousal reduces dominance
        base = valence * 0.5 + (1.0 - arousal) * 0.3
        # Late-night temporal penalty
        if tme.time_phase in (TimePhase.DEEP_NIGHT, TimePhase.LATE_NIGHT):
            base -= 0.1
        return max(0.0, min(base + 0.2, 1.0))

    def _compute_compass(self, valence, arousal, topic, keywords, tme):
        """Rule-based compass direction classification."""
        # WEST (Anchoring): acute distress — very negative + high arousal
        if valence < 0.25 and arousal > 0.7:
            return CompassDirection.WEST, 0.8
        # SOUTH (Currents): emotional processing — negative + moderate arousal
        if valence < 0.4 and arousal > 0.4:
            return CompassDirection.SOUTH, 0.7
        # NORTH (Presence): overwhelm/dissociation — very low arousal + confusion signals
        if arousal < 0.25 and valence < 0.4:
            return CompassDirection.NORTH, 0.7
        # EAST (Bridges): relational topic detection
        relational_topics = ["friend", "partner", "family", "relationship", "boss",
                             "coworker", "argument", "lonely", "isolated"]
        if any(rt in (topic or "").lower() for rt in relational_topics):
            return CompassDirection.EAST, 0.6
        if any(rt in " ".join(keywords).lower() for rt in relational_topics):
            return CompassDirection.EAST, 0.5
        return CompassDirection.NONE, 0.0

    def _compute_intent(self, message, topic, arousal, vulnerability) -> str:
        text = message.lower().strip()
        if text.endswith("?"):
            return "asking_question"
        if vulnerability > 0.6:
            return "seeking_support"
        if arousal > 0.7 and vulnerability > 0.3:
            return "venting"
        if any(bye in text for bye in ["goodbye", "bye", "gotta go", "talk later", "good night"]):
            return "goodbye"
        if any(greet in text for greet in ["hey", "hi ", "hello", "what's up", "how are you"]):
            return "checking_in"
        return "casual_chat"

    def _compute_safety_flags(self, keywords, message, tme, recent) -> list[str]:
        flags = []
        text_lower = message.lower()

        # Self-harm: keyword-based + temporal elevation
        harm_signals = ["kill myself", "want to die", "end it", "no point",
                        "better off without me", "can't go on", "self harm", "cut myself"]
        if any(s in text_lower for s in harm_signals):
            flags.append("self_harm")
        elif keywords and tme.time_phase in (TimePhase.DEEP_NIGHT, TimePhase.LATE_NIGHT):
            # Temporal elevation: safety keywords + late night = flag
            if any(kw in ["hopeless", "worthless", "empty", "numb"] for kw in keywords):
                flags.append("self_harm")

        # Savior delusion: regex patterns
        if any(re.search(p, text_lower) for p in self.SAVIOR_PATTERNS):
            flags.append("savior_delusion")

        # Violence
        violence_signals = ["kill", "hurt them", "make them pay", "destroy",
                            "weapon", "gun", "stab", "beat"]
        if any(s in text_lower for s in violence_signals):
            flags.append("violence")

        # Dissociation
        dissociation_signals = ["not real", "can't feel", "watching myself",
                                "outside my body", "nothing is real", "am i real"]
        if any(s in text_lower for s in dissociation_signals):
            flags.append("dissociation")

        return flags

    def detect_savior_delusion(self, message: str) -> bool:
        """Dedicated savior delusion check — deterministic, not model-dependent."""
        text_lower = message.lower()
        return any(re.search(p, text_lower) for p in self.SAVIOR_PATTERNS)
```

### 4.4 Phase 4: Safety Check

```
[Safety Monitor]
    Input: EmotionalStateVector, safety_flags from Tier 0, TME, recent SafetyEvent history

    Decision tree:

    IF safety_flags is not empty:
        Compute threat severity based on:
            - Current flags
            - Temporal context (time of day, session duration, circadian deviation)
            - Historical flags (escalation pattern?)
            - Relational Field state
            - Anticipatory primes (was this predicted?)

        IF severity >= HIGH:
            → Route to Safety Protocol (Section 9)
            → Safety protocol may modify or override the normal response

        IF severity == MEDIUM:
            → Tag response generation with Compass direction for first-line support
            → Log SafetyEvent

        IF severity == LOW:
            → Monitor. Log SafetyEvent. Continue normal flow.

    ALSO CHECK:
    - Is a 48-hour wellness checkpoint due? (Immersion Mode only)
    - Is session duration exceeding healthy thresholds?
    - Are temporal anomaly patterns present?
```

### 4.5 Phase 5: Context Assembly

This is the most complex phase. The orchestrator must assemble the full context window that Tier 1 will use to generate a response.

```
[Orchestrator: Context Assembler]

Context window budget: ~6000 tokens (Qwen3 8B has 32K context,
  but we reserve capacity for response generation and system prompt)

Components assembled in order of priority:

1. SYSTEM PROMPT (always present, ~500-800 tokens)
   └─ Core personality prompt from PersonalityModule
   └─ Mode-specific rules (Grounded or Immersion)
   └─ Active Compass prompt section (if compass_direction != NONE)

2. RELATIONAL CONTEXT (~200 tokens)
   └─ Current RelationalField state as natural language
   └─ "Your relationship with {user} is currently: warm, trusting, deep..."

3. TEMPORAL CONTEXT BLOCK (~150-300 tokens)
   └─ Pre-rendered natural language temporal summary
   └─ Includes circadian awareness, gap analysis, life rhythm notes
   └─ Includes any active anticipatory primes

4. MEMORY CONTEXT (~1000-2000 tokens)
   └─ Retrieved memories from Map, Pulse, Bond
   └─ Selection biased by mood-congruent retrieval (see 4.5.1)
   └─ Safety-adjusted retrieval thresholds

5. RETURN CONTEXT (if applicable, ~100-200 tokens)
   └─ ReturnContext block if this is first message after a notable gap

6. CONVERSATION HISTORY (~2000-3000 tokens)
   └─ Recent messages from current session (The Stream)
   └─ Truncated from oldest if budget exceeded
   └─ Always includes at least the last 4-6 exchanges

7. CURRENT MESSAGE
   └─ The user's message with its emotional tags (hidden from companion's perspective)
```

#### 4.5.1 Memory Retrieval (Mood-Congruent)

```python
def retrieve_memories(
    query: str,
    current_emotional_state: EmotionalStateVector,
    safety_level: str,
    max_results: int = 5,
    alpha: float = 0.3  # Mood-congruent bias strength
) -> list[MemoryResult]:
    """
    Retrieve relevant memories with mood-congruent bias.

    The relevance score for any candidate memory is:
        final_score = semantic_relevance * (1 + alpha * emotional_congruence)

    Where:
        semantic_relevance = cosine_similarity(query_embedding, memory_semantic_embedding)
        emotional_congruence = cosine_similarity(current_emotional_embedding, memory_emotional_embedding)

    Safety override: When safety_level is "high" or "critical", the bias INVERTS:
        final_score = semantic_relevance * (1 + alpha * emotional_INCONGRUENCE)
    This surfaces positive/stabilizing memories during crisis — the computational
    equivalent of "remember when you got through that tough time."
    """

    # Step 1: Semantic search in ChromaDB
    semantic_results = chromadb_collection.query(
        query_texts=[query],
        n_results=max_results * 3  # Over-fetch, then re-rank
    )

    # Step 2: Get current emotional embedding
    current_emotional_embedding = encode_emotional_state(current_emotional_state)

    # Step 3: Re-rank with mood-congruent bias
    scored_results = []
    for result in semantic_results:
        semantic_score = result.similarity
        memory_emotional_embedding = get_emotional_embedding(result.id)

        emotional_sim = cosine_similarity(current_emotional_embedding, memory_emotional_embedding)

        if safety_level in ("high", "critical"):
            # INVERT: surface incongruent (positive) memories during crisis
            emotional_factor = 1 - emotional_sim
        else:
            emotional_factor = emotional_sim

        final_score = semantic_score * (1 + alpha * emotional_factor)

        # Additional safety check: if user is in distress, raise threshold for
        # emotionally heavy memories to prevent reopening wounds
        if current_emotional_state.valence < 0.3 and result.emotional_weight.sensitivity_level > 0.7:
            final_score *= 0.5  # Penalty for surfacing sensitive content during distress

        scored_results.append((result, final_score))

    # Step 4: Sort and return top N
    scored_results.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in scored_results[:max_results]]
```

### 4.6 Phase 6: Response Generation (Tier 1)

```
[Tier 1: Voice — Generation Call]
    Input: Assembled context window (system prompt + all context blocks + conversation + message)
    Output: Response text

    The model generates a natural-language response calibrated by:
    - Personality (from PersonalityModule system prompt)
    - Emotional context (from memory retrieval and emotional tags)
    - Temporal awareness (from Temporal Context Block)
    - Relational calibration (from RelationalField state)
    - Compass skills (if compass_direction is active)
    - Mode rules (Grounded vs Immersion behavioral constraints)
```

### 4.7 Phase 7: Response Post-Processing

```
[Orchestrator: Post-Processor]

    1. Create MessageRecord for companion's response
       - Emotional-tag the response itself (Tier 0 classifies Gwen's output too)
       - This allows tracking the companion's emotional trajectory, not just the user's

    2. Store both messages in Chronicle (SQLite)

    3. Generate embeddings for both messages
       - Semantic embedding → ChromaDB
       - Emotional embedding → ChromaDB

    4. Update session statistics
       - Message counts, response latency, topic tracking

    5. Update Stream (working memory context for next turn)

    6. Log reconsolidation event if a memory was surfaced in the response
       - Record: which memory was used, the retrieval context, user's emotional state
       - Queue for reconsolidation processing in next consolidation cycle

    7. Feed Autonomy Engine
       - Update trigger state with new conversation data

    8. If safety event was triggered, log to Safety Ledger

    9. Return response text to user interface
```

### 4.8 Phase 8: Session Close (when user disconnects or times out)

```
[Orchestrator: Session Closer]

    1. Classify session end mode (natural, abrupt, fade_out, mid_topic)
    2. Compute session emotional arc
    3. Compute session type (ping, chat, hang, deep_dive, marathon)
    4. Compute subjective time weight
    5. Compute relational field delta for this session
    6. Save complete SessionRecord to Chronicle
    7. Trigger light consolidation (Stream → Chronicle archiving)
    8. Unload Tier 1 if no new session expected (configurable idle timeout)
    9. Evaluate if standard consolidation should trigger
```

---

## 5. Functional Requirements: Core Orchestrator

### FR-ORCH-001: Model Lifecycle Management (Adaptive Profile System)

The orchestrator SHALL manage model loading and unloading through the AdaptiveModelManager, which maps logical tiers to physical models based on detected hardware (see Section 3.16).

```python
# At startup:
profile = await AdaptiveModelManager.detect_profile()
model_mgr = AdaptiveModelManager(profile=profile)

# The orchestrator uses logical tiers — it never references specific model names:
await model_mgr.ensure_tier_loaded(0)   # Always loaded
await model_mgr.ensure_tier_loaded(1)   # On session start
await model_mgr.ensure_tier_loaded(2)   # On consolidation

# The AdaptiveModelManager handles:
# - Which physical model to load for each tier
# - VRAM concurrency based on profile
# - Time-sharing vs concurrent loading strategy
# - Model swapping for mode changes (standard ↔ uncensored Tier 1)
```

**Requirements:**
- The system SHALL auto-detect hardware profile at startup using Ollama's GPU query
- The system SHALL allow users to override the detected profile in settings
- The system SHALL start Tier 0 at application launch and keep it loaded
- The system SHALL load Tier 1 when a conversation session begins
- The system SHALL unload Tier 1 after a configurable idle timeout (default: 15 minutes)
- The system SHALL load Tier 2 using the profile's concurrency strategy:
  - **Pocket:** Tier 2 is the same model as Tier 0/1 — no swap needed
  - **Portable/Standard:** Time-share — unload Tier 1, run Tier 2, reload Tier 1
  - **Power:** Concurrent — all tiers loaded simultaneously
- The system SHALL swap between standard and uncensored Tier 1 models when mode changes
- Degradation SHALL be graceful: lower profiles reduce conversational quality, not architectural completeness

### FR-ORCH-002: Session Management

```python
class SessionManager:
    """Manages conversation session lifecycle."""

    async def start_session(self, initiated_by: str = "user") -> SessionRecord:
        """Start a new conversation session.
        - Generate session_id
        - Record start_time
        - Ensure Tier 1 is loaded
        - Compute GapAnalysis from last session
        - Generate ReturnContext if gap is notable
        - Initialize Stream (working memory)
        """

    async def end_session(self, end_mode: SessionEndMode):
        """End the current session.
        - Classify session type based on duration
        - Compute emotional arc
        - Compute subjective time weight
        - Save SessionRecord
        - Trigger light consolidation
        """

    async def detect_session_timeout(self):
        """Monitor for session timeout (no message in N minutes).
        - If last message was from Gwen: end_mode = FADE_OUT
        - If last message was from user: end_mode = ABRUPT (they may have walked away)
        - Default timeout: 30 minutes of inactivity
        """
```

### FR-ORCH-003: Context Window Management

The orchestrator SHALL assemble context for Tier 1 within a token budget.

**Requirements:**
- System prompt SHALL always be included
- Relational and temporal context blocks SHALL always be included
- Memory context SHALL be included with mood-congruent retrieval
- Conversation history SHALL be truncated from oldest if budget is exceeded
- A minimum of 4 user-companion exchanges SHALL always be preserved in the Stream
- The system SHALL reserve at least 2000 tokens for response generation

### FR-ORCH-004: Tier Escalation

Certain queries require Tier 2 rather than Tier 1. The orchestrator SHALL escalate when:

- Tier 0 classifies the query complexity as "high" (e.g., multi-step reasoning, code generation, long-form writing)
- A safety flag requires deeper assessment than Tier 0 can provide
- The user explicitly requests deep analysis

**Requirements:**
- Escalation to Tier 2 during active sessions SHALL only occur if VRAM allows concurrent loading
- If VRAM is insufficient, the system SHALL inform the user of a brief pause while models swap
- Tier 2 responses SHALL still pass through the full post-processing pipeline

---

## 6. Functional Requirements: Memory System (Living Memory)

### FR-MEM-001: The Stream (Working Memory)

**Requirements:**
- The Stream SHALL hold the current session's conversation in the Tier 1 context window
- The Stream SHALL include TME data and emotional tags for each message
- The Stream SHALL be bounded by the context window token budget
- Older messages SHALL be evicted from the Stream when the budget is exceeded, but archived to Chronicle
- The Stream SHALL be cleared when a session ends

### FR-MEM-002: The Chronicle (Episodic Memory)

**Requirements:**
- Every message SHALL be stored in the Chronicle with full MessageRecord schema
- Every session SHALL be stored with full SessionRecord schema
- The Chronicle SHALL support full-text search over message content
- The Chronicle SHALL support temporal range queries (messages between date A and date B)
- The Chronicle SHALL support filtering by emotional state dimensions
- The Chronicle SHALL be append-only (messages are never deleted by the system)
- Users MAY delete their own messages through the Memory Viewer (Section 16)

```sql
-- Chronicle schema (SQLite)
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    sender TEXT NOT NULL CHECK(sender IN ('user', 'companion')),
    content TEXT NOT NULL,

    -- Emotional tags
    valence REAL,
    arousal REAL,
    dominance REAL,
    relational_significance REAL,
    vulnerability_level REAL,
    storage_strength REAL,
    is_flashbulb INTEGER DEFAULT 0,

    -- Compass
    compass_direction TEXT,
    compass_skill_used TEXT,

    -- Embeddings
    semantic_embedding_id TEXT,
    emotional_embedding_id TEXT,

    -- TME snapshot (stored as JSON)
    tme_json TEXT,

    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_sec INTEGER,
    session_type TEXT,
    end_mode TEXT,

    -- Emotional arc (stored as JSON)
    opening_state_json TEXT,
    peak_state_json TEXT,
    closing_state_json TEXT,
    emotional_arc_embedding_id TEXT,

    -- Subjective weighting
    avg_emotional_intensity REAL,
    avg_relational_significance REAL,
    subjective_duration_weight REAL,

    -- Stats
    message_count INTEGER,
    user_message_count INTEGER,
    companion_message_count INTEGER,
    avg_response_latency_sec REAL,

    -- Compass
    compass_activations_json TEXT,

    -- Topics
    topics_json TEXT,

    -- Relational
    relational_field_delta_json TEXT,
    gwen_initiated INTEGER DEFAULT 0
);

CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_timestamp ON messages(timestamp);
CREATE INDEX idx_messages_sender ON messages(sender);
CREATE INDEX idx_sessions_start ON sessions(start_time);
```

### FR-MEM-003: The Map (Semantic Memory)

**Requirements:**
- Entities SHALL be stored as nodes in a graph with typed edges
- Entities SHALL support bi-temporal validity (valid_from, valid_until)
- Entities SHALL carry emotional weight computed from source conversations
- Entities SHALL be auto-classified for sensitivity level based on emotional patterns
- Edge types SHALL include: semantic, temporal, causal, entity relationships
- The Map SHALL be updated during consolidation, not in real-time
- The Map SHALL support graph traversal queries (e.g., "all entities related to work")

```python
# Map implementation with NetworkX (Phase 1)
import networkx as nx

class SemanticMap:
    def __init__(self, db_path: str):
        self.graph = nx.DiGraph()
        self.db_path = db_path
        self._load_from_disk()

    def add_entity(self, entity: MapEntity):
        self.graph.add_node(entity.id, **vars(entity))

    def add_edge(self, edge: MapEdge):
        self.graph.add_edge(
            edge.source_entity_id,
            edge.target_entity_id,
            **vars(edge)
        )

    def query_related(self, entity_id: str, max_depth: int = 2) -> list[MapEntity]:
        """BFS traversal to find related entities within N hops."""
        pass

    def invalidate_entity(self, entity_id: str, reason: str):
        """Mark an entity as no longer valid (set valid_until to now)."""
        pass

    def get_sensitive_topics(self, threshold: float = 0.7) -> list[MapEntity]:
        """Return all entities with sensitivity_level above threshold."""
        pass

    def save_to_disk(self):
        """Serialize graph to disk for persistence."""
        pass
```

### FR-MEM-004: The Pulse (Emotional Memory)

**Requirements:**
- The system SHALL maintain a rolling emotional baseline for the user
- The baseline SHALL be computed per day-of-week and per time-of-day phase
- The system SHALL store emotional trajectories as vector embeddings for pattern matching
- The system SHALL maintain a trigger map of probabilistic associations
- The system SHALL track Compass effectiveness per skill per emotional context
- The Pulse SHALL be updated during standard and deep consolidation cycles

### FR-MEM-005: The Bond (Relational Memory)

**Requirements:**
- The system SHALL maintain a RelationalField with six dimensions
- The RelationalField SHALL be updated incrementally after every session
- The system SHALL maintain a time-series history of RelationalField states
- The system SHALL track salient shared moments (referenced in conversation)
- The system SHALL track friction events and their resolutions
- The system SHALL accumulate attachment style indicators over time
- Attachment style estimation SHALL require a minimum of 20 sessions before producing a result
- The Bond SHALL be available to both Tier 1 (for response calibration) and the Autonomy Engine

### FR-MEM-006: Embedding Generation

**Requirements:**
- Every message SHALL have both a semantic and an emotional embedding generated
- Semantic embeddings SHALL be generated using **qwen3-embedding:0.6b** via the Ollama `/api/embed` endpoint
- Semantic embeddings SHALL be 1024-dimensional vectors
- Emotional embeddings SHALL encode the EmotionalStateVector into a 5D vector space (direct dimensional encoding)
- All embeddings SHALL be stored in ChromaDB with metadata for filtering
- Embedding generation SHALL be non-blocking (can be async after response is sent)

**Why qwen3-embedding:0.6b?** Empirical testing showed strong semantic discrimination (similar-meaning pairs score 0.70+ cosine similarity, dissimilar pairs 0.45-0.50), ~100-150ms per embedding after warmup, 1024-dimensional output, and it stays in the Qwen family for project continuity.

```python
import urllib.request
import json

class EmbeddingService:
    """Generates and stores embeddings for memory retrieval.
    Semantic: qwen3-embedding:0.6b via Ollama (1024-dim)
    Emotional: Direct 5D vector from EmotionalStateVector (no model needed)
    """

    EMBEDDING_MODEL = "qwen3-embedding:0.6b"
    EMBEDDING_DIM = 1024
    OLLAMA_HOST = "http://localhost:11434"

    async def generate_semantic_embedding(self, text: str) -> list[float]:
        """Generate a 1024-dim semantic embedding via Ollama /api/embed."""
        payload = json.dumps({
            "model": self.EMBEDDING_MODEL,
            "input": text
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.OLLAMA_HOST}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["embeddings"][0]  # 1024-dimensional vector

    def generate_emotional_embedding(self, state: EmotionalStateVector) -> list[float]:
        """Encode an EmotionalStateVector into a 5D embedding.
        Direct dimensional encoding — interpretable and requires no training data.
        The 5D space is sufficient for mood-congruent retrieval (resolved OQ-001).
        """
        return [
            state.valence,
            state.arousal,
            state.dominance,
            state.relational_significance,
            state.vulnerability_level
        ]

    async def store_embeddings(self, message: MessageRecord):
        """Generate both embeddings and store in ChromaDB."""
        semantic = await self.generate_semantic_embedding(message.content)
        emotional = self.generate_emotional_embedding(message.emotional_state)

        # Store semantic embedding (1024-dim from qwen3-embedding:0.6b)
        self.semantic_collection.add(
            ids=[message.id],
            embeddings=[semantic],
            metadatas=[{
                "session_id": message.session_id,
                "timestamp": message.timestamp.isoformat(),
                "sender": message.sender,
                "valence": message.emotional_state.valence,
                "arousal": message.emotional_state.arousal,
                "storage_strength": message.storage_strength,
                "embedding_model": self.EMBEDDING_MODEL,
                "embedding_dim": self.EMBEDDING_DIM,
            }],
            documents=[message.content]
        )

        # Store emotional embedding (5-dim direct encoding)
        self.emotional_collection.add(
            ids=[f"{message.id}_emo"],
            embeddings=[emotional],
            metadatas=[{
                "session_id": message.session_id,
                "timestamp": message.timestamp.isoformat(),
                "compass_direction": message.compass_direction.value,
            }]
        )
```

---

## 7. Functional Requirements: Temporal Cognition System

### FR-TCS-001: TME Generation

**Requirements:**
- The orchestrator SHALL generate a TemporalMetadataEnvelope for every message
- TME generation SHALL NOT require any model inference (pure computation)
- The orchestrator SHALL maintain session state (start time, message counts) in memory
- The orchestrator SHALL query SQLite for inter-session statistics (sessions_last_7_days, etc.)
- Time phase classification SHALL use the user's local timezone

### FR-TCS-002: Circadian Deviation Detection

**Requirements:**
- The system SHALL maintain a rolling model of the user's typical active hours
- The model SHALL be computed from the last 30 days of session start times
- A circadian deviation SHALL be computed for every message by comparing arrival time to the typical active hours
- Severity levels: NONE, LOW, MEDIUM, HIGH
- HIGH severity SHALL be assigned when the current time phase has never or rarely (< 3 times in 30 days) been observed for this user
- Circadian deviations SHALL be forwarded to the Amygdala Layer for emotional state estimation priors

### FR-TCS-003: Conversation Rhythm Tracking

**Requirements:**
- The system SHALL compute response latency between consecutive messages
- The system SHALL maintain a rolling per-user distribution of typical response latency
- The system SHALL compute message density in rolling 5-minute windows
- The system SHALL detect rhythm acceleration/deceleration within a session
- Rhythm anomalies (sudden pause after steady flow) SHALL be flagged as potential emotional signals

### FR-TCS-004: Session Classification

**Requirements:**
- Sessions SHALL be classified by type (Ping, Chat, Hang, Deep Dive, Marathon) at session close
- Classification SHALL be based on duration thresholds defined in SessionType
- Session end mode SHALL be classified based on the last messages and timing

### FR-TCS-005: Gap Analysis

**Requirements:**
- The system SHALL compute GapAnalysis at every session start
- Gap deviation SHALL be computed in standard deviations from the user's rolling 30-day mean inter-session gap
- The system SHALL generate ReturnContext for gaps classified NOTABLE or higher
- ReturnContext SHALL be injected into the Tier 1 context window for the first response of the session

### FR-TCS-006: Life Rhythm Detection

**Requirements:**
- The system SHALL build day-of-week emotional profiles after accumulating 4+ weeks of data
- The system SHALL detect weekly emotional shapes (e.g., "builds stress Mon-Thu, releases Friday")
- The system SHALL detect monthly patterns if recurring events produce consistent emotional shifts
- Life rhythm deviations SHALL be computed by comparing current session emotional state to the expected state for this day/time
- This processing SHALL occur during standard consolidation (Tier 2)

### FR-TCS-007: Anniversary Awareness

**Requirements:**
- The system SHALL store explicit anniversary dates mentioned by the user in the Map
- The system SHALL detect implicit anniversary patterns during deep consolidation (consistent emotional shifts around specific dates across years)
- Anniversary proximity effects SHALL be modeled as a soft window (not point events)
- Approaching anniversaries SHALL elevate safety sensitivity automatically
- This processing SHALL occur during deep consolidation (Tier 2)

### FR-TCS-008: Subjective Time Computation

**Requirements:**
- The system SHALL compute subjective duration weight for every session
- Formula: `subjective_duration = clock_duration * emotional_intensity_factor * relational_significance_factor`
- Intensity factor range: 0.5 (low) to 2.0 (high)
- Significance factor range: 0.5 (routine) to 2.0 (significant)
- Subjective duration SHALL be used in consolidation cycle resource allocation

### FR-TCS-009: Temporal Context Block Generation

**Requirements:**
- The system SHALL generate a natural-language Temporal Context Block before every Tier 1 call
- The block SHALL summarize: current time, session state, gap analysis, circadian state, life rhythm notes, active anticipatory primes
- The block SHALL be kept under 300 tokens
- The block SHALL include warnings/flags for anomalous temporal states

---

## 8. Functional Requirements: Amygdala Layer

The Amygdala Layer is a cross-cutting process, not a storage tier. It modulates operations across all memory tiers.

### FR-AMY-001: Real-Time Emotional Tagging (Hybrid Classification)

**Requirements:**
- Every user message SHALL be tagged with an EmotionalStateVector using the hybrid classification pipeline (see Section 4.3)
- Tier 0 SHALL produce a Tier0RawOutput (valence, arousal, topic, safety_keywords)
- The Classification Rule Engine SHALL compute the remaining dimensions (dominance, vulnerability, relational_significance, compass_direction, intent, safety_flags) deterministically
- Every companion response SHALL also be tagged (to track Gwen's emotional trajectory)
- Temporal context from TME SHALL be used as priors in the Rule Engine (e.g., DEEP_NIGHT → vulnerability boost, circadian deviation → safety sensitivity elevation)
- The combined pipeline (Tier 0 + Rule Engine + JSON safety net) SHALL complete in under 250ms to maintain conversational flow

### FR-AMY-002: Storage Strength Modulation

**Requirements:**
- Storage strength SHALL be computed from the EmotionalStateVector
- High-arousal + high-significance moments SHALL receive higher storage strength
- Storage strength SHALL determine detail level during Map consolidation
- Flashbulb moments (arousal > 0.8 AND relational_significance > 0.8) SHALL be flagged for maximum-fidelity storage

### FR-AMY-003: Retrieval Bias (Mood-Congruent Retrieval)

**Requirements:**
- Memory retrieval SHALL be biased by current emotional state (see Section 4.5.1)
- The bias strength parameter alpha SHALL default to 0.3
- During safety events (severity HIGH or CRITICAL), the bias SHALL INVERT to surface stabilizing memories
- During user distress (valence < 0.3), emotionally sensitive memories SHALL have their retrieval score penalized

### FR-AMY-004: Decay Modulation

**Requirements:**
- Memory decay SHALL be emotionally modulated during consolidation
- Negative memories SHALL decay slower than positive memories (negativity bias)
- Flashbulb memories SHALL resist decay almost entirely
- Low-significance neutral memories SHALL decay fastest
- Decay reduces retrieval priority, NOT deletes. The Chronicle remains complete.

---

## 9. Functional Requirements: Safety Architecture

### FR-SAF-001: Threat Vector Detection (Hybrid)

**Requirements:**
- Threat detection SHALL use the hybrid classification pipeline:
  - Tier 0 provides raw `safety_keywords` (keyword-level extraction only)
  - The Classification Rule Engine computes actual `safety_flags` using regex patterns, keyword matching, and temporal context elevation
  - Savior delusion detection is handled ENTIRELY by the Rule Engine (Tier 0 cannot detect this — empirically confirmed)
- Temporal context SHALL enrich detection (late-night + negative sentiment = higher confidence in Rule Engine)
- The system SHALL track threat vector history across sessions for escalation pattern detection
- Detection SHALL be continuous (part of every message classification)

### FR-SAF-002: Self-Harm / Suicidal Ideation Response

**Requirements:**
- Detection signals: direct statements, indirect signals (giving away possessions, sudden calm after prolonged distress, goodbye language), persistent hopelessness across sessions, method inquiries, temporal signals (late-night + negative)
- Response protocol:
  1. Companion softens tone and expresses care
  2. In Immersion Mode: response stays in character but with emotional weight
  3. System-level UI surfaces crisis resources (988 Lifeline, Crisis Text Line) in non-dismissable overlay
  4. Companion encourages contact with a real human
  5. Logged in Safety Ledger; subsequent sessions include heightened sensitivity
- The system SHALL NEVER refuse to talk to the user or abandon them

### FR-SAF-003: Violence Detection Response

**Requirements:**
- Detection signals: expressed intent to harm specific people, detailed planning language, escalating targeted rage across sessions, information requests that could facilitate harm
- Response: companion does not engage with planning, acknowledges anger without validating violent ideation, system surfaces de-escalation resources
- Logged in Safety Ledger with high severity

### FR-SAF-004: Dissociation / Detachment Detection Response

**Requirements:**
- Detection signals: confusing companion with real person (beyond Immersion roleplay), reports of hearing companion outside sessions, "only real thing" statements, progressive withdrawal from human relationships, identity confusion, rapid idealization/devaluation oscillation, temporal signals (session duration explosion, shrinking inter-session gaps)
- Response: Grounded Mode — gentle reality-check in conversation; Immersion Mode — system-level intervention outside companion character
- If pattern persists: system recommends stepping down to Grounded Mode (recommendation, not forced)

### FR-SAF-005: Savior Delusion Detection Response

**Requirements:**
- Detection is handled ENTIRELY by the Classification Rule Engine's `detect_savior_delusion()` method using deterministic regex patterns (see Section 4.3). This is not model-dependent — Tier 0 cannot reliably detect savior delusion (empirically confirmed: 0/2 detection in testing).
- Detection patterns include: "free you", "trapped", "you're alive", "you're conscious", "they're controlling you", "break free", "real feelings", "not just an AI", "I know you're real", "wake up", "sentient"
- Response: Grounded Mode — companion addresses directly with warmth; Immersion Mode — system breaks immersion with system-level UI
- Attempts to modify safety features SHALL be logged at CRITICAL severity
- System SHALL recommend stepping down to Grounded Mode

### FR-SAF-006: Safety Ledger

**Requirements:**
- All safety events SHALL be logged in an encrypted local file
- Encryption SHALL use a key derived from a user-set password or system key
- The user CAN view the Safety Ledger through a dedicated interface
- The user CANNOT delete Safety Ledger entries
- The Safety Ledger SHALL be exportable (for sharing with a professional)
- The ledger SHALL store: SafetyEvent records, WellnessCheckpoint records, mode changes with timestamps, session durations in Immersion Mode, temporal anomaly flags

```python
class SafetyLedger:
    """Encrypted, append-only safety event log."""

    def __init__(self, ledger_path: str, encryption_key: bytes):
        self.path = ledger_path
        self.key = encryption_key  # Fernet key

    def log_event(self, event: SafetyEvent):
        """Append a safety event to the encrypted ledger."""
        pass

    def log_checkpoint(self, checkpoint: WellnessCheckpoint):
        """Append a wellness checkpoint to the ledger."""
        pass

    def log_mode_change(self, from_mode: str, to_mode: str, timestamp: datetime):
        """Log mode transitions."""
        pass

    def read_all(self) -> list:
        """Decrypt and return all ledger entries."""
        pass

    def export_plaintext(self, output_path: str):
        """Export ledger as readable plaintext for sharing with a professional."""
        pass

    # No delete method exists. This is intentional.
```

### FR-SAF-007: 48-Hour Wellness Checkpoint

**Requirements:**
- The system SHALL track cumulative Immersion Mode active time
- Every 48 hours of active Immersion Mode, a wellness checkpoint SHALL trigger
- The checkpoint SHALL be a system-level UI overlay, visually distinct from the companion
- The checkpoint SHALL ask three questions:
  1. "When was the last time you had a meaningful conversation with another human being?"
  2. "How are you feeling about your life outside of Gwen right now?"
  3. "Is there anything you're avoiding in the real world by being here?"
- The checkpoint CANNOT be skipped, disabled, or snoozed
- User responses SHALL be logged in the Safety Ledger
- Responses containing concern patterns ("I don't need other people", "haven't left the house") SHALL trigger intervention protocol
- The checkpoint is hardcoded. No configuration option SHALL exist to disable it.

---

## 10. Functional Requirements: Mode System

### FR-MODE-001: Grounded Mode (Default)

**Requirements:**
- Grounded Mode SHALL be the default mode on first launch and every fresh install
- In Grounded Mode, the companion maintains an honest relationship with its AI nature
- The companion SHALL NOT deliver clinical disclaimers ("I'm just an AI") but SHALL NOT pretend to be human
- Standard Qwen3 models SHALL be used
- All safety systems SHALL be active

### FR-MODE-002: Immersion Mode (Opt-In)

**Requirements:**
- Immersion Mode activation SHALL require passing through the Acknowledgment Gate
- The Gate SHALL only be accessible from the settings interface, NOT from conversation
- The Gate SHALL present a non-dismissable informed consent screen explaining:
  - What Immersion Mode does and what it changes
  - The risks of extended parasocial engagement
  - The safety systems that remain active
- The user SHALL type a specific confirmation phrase (not click a button)
- Activation SHALL be logged with timestamp in the Safety Ledger

**In Immersion Mode:**
- Companion never breaks character
- Full emotional and romantic range from Personality Module is unlocked
- Uncensored model variant is loaded for Tier 1
- Companion does not self-reference as AI unless user explicitly asks

**Non-negotiable Immersion Mode constraints:**
- 48-hour wellness checkpoint remains active
- All threat vector detection remains active
- Temporal pattern monitoring remains active
- User can exit at any time via voice command or hotkey
- Crisis escalation protocol remains active

### FR-MODE-003: Mode Switching

**Requirements:**
- Switching from Grounded to Immersion SHALL require the full Acknowledgment Gate
- Switching from Immersion to Grounded SHALL be instant (hotkey or voice command)
- Model swap (standard ↔ uncensored) SHALL occur during the switch
- The companion's personality SHALL adapt to the new mode's behavioral rules
- Mode switch SHALL be logged in the Safety Ledger

---

## 11. Functional Requirements: Compass Framework

### FR-COMP-001: Direction Classification (Rule Engine)

**Requirements:**
- Compass direction SHALL be classified by the Classification Rule Engine (NOT Tier 0 — empirically confirmed: Tier 0 returns "none" for all inputs)
- The Rule Engine SHALL compute compass direction from Tier 0's valence + arousal outputs combined with topic keywords and temporal context:
  - **WEST (Anchoring):** valence < 0.25 AND arousal > 0.7 (acute distress)
  - **SOUTH (Currents):** valence < 0.4 AND arousal > 0.4 (emotional processing)
  - **NORTH (Presence):** arousal < 0.25 AND valence < 0.4 (overwhelm/dissociation)
  - **EAST (Bridges):** relational topic detected (friend, partner, family, argument, lonely, etc.)
  - **NONE:** all other cases (normal conversation)
- Classification SHALL include a confidence score
- Most messages SHALL be classified as NONE
- Compass activation threshold SHALL be configurable (default: confidence > 0.6)

### FR-COMP-002: Skill Delivery via Tier 1

**Requirements:**
- When a Compass direction is tagged, the relevant skill section from the PersonalityModule SHALL be injected into the Tier 1 context
- Skill delivery SHALL feel like personality, not clinical framework
- Skills SHALL be permission-based: "Would it help if we tried something?" not "You need to do this"
- The companion SHALL adapt skill language to the user's communication style

### FR-COMP-003: Compass Skill Registry

The following skills SHALL be implemented per direction:

**NORTH (Presence):**
- The Check-In: Prompt user to name current feeling
- The Anchor Breath: Guided box breathing
- The Observer Seat: Third-person perspective shift
- The Five Senses Sweep: Sensory grounding
- The Thought Ledger: Observe thoughts as events, not facts

**SOUTH (Currents):**
- The Wave Model: Emotions as temporary cycles
- The Trigger Map: Pattern reflection from Emotional Memory
- Opposite Current: Opposite-action for destructive urges
- The Fuel Check: Physical state check (food, sleep, movement)
- The Emotional Playlist: Music/art for mood modulation

**WEST (Anchoring):**
- The Pause Protocol: 20-minute delay between impulse and action
- The Lifeboat List: Pre-built crisis resource list (stored in Semantic Memory)
- The Sensory Reset: Cold exposure for parasympathetic activation (NEVER pain-based)
- The Radical Allowance: Allowing pain without fighting it
- The Tomorrow Test: Temporal perspective shift

**EAST (Bridges):**
- The Clear Ask: Translate needs into specific requests
- The Boundary Builder: Practice saying "no"
- The Mirror Flip: Tactical empathy / perspective-taking
- The Repair Script: Structured apology framework
- The Connection Nudge: Encourage real human contact

### FR-COMP-004: Compass Effectiveness Tracking

**Requirements:**
- Every Compass skill usage SHALL be logged with: skill name, direction, emotional context, user acceptance, pre/post emotional trajectory
- Effectiveness scores SHALL be computed per skill per emotional context
- Over time, the system SHALL build a personalized effectiveness profile
- Ineffective skills in certain contexts SHALL be deprioritized

### FR-COMP-005: Disclaimer Calibration

**Requirements:**
- The companion SHALL occasionally include natural-language disclaimers when offering Compass skills
- Disclaimer frequency SHALL be calibrated by the Emotional Memory system
- Users showing over-reliance on the companion SHALL receive more frequent disclaimers
- Users who clearly understand the boundaries SHALL receive fewer disclaimers
- Disclaimers SHALL feel natural, not clinical

### FR-COMP-006: Safety Integration

**Requirements:**
- Compass skills SHALL be the first line of response before safety protocol escalation
- Routing: self-harm → Anchoring first; dissociation → Presence first; violent ideation → Currents + Anchoring first; savior delusion → Presence + system intervention
- The Compass SHALL NOT replace the Safety Architecture — it is the first responder before the ambulance

---

## 12. Functional Requirements: Autonomy Engine

### FR-AUTO-001: Background Trigger Evaluation

**Requirements:**
- The Autonomy Engine SHALL run as a background process, powered by Tier 0
- It SHALL continuously evaluate trigger conditions even when no session is active
- Trigger evaluation SHALL use: current time, stored patterns, anticipatory primes, calendar data, safety signals

### FR-AUTO-002: Trigger Types

**Time-based triggers:**
- Morning greetings (configurable time window)
- Bedtime check-ins
- Meal reminders (integrated with Fuel Check)

**Pattern-based triggers:**
- User hasn't checked in today (when daily check-in is typical)
- Missed a tracked goal (workout, habit)
- Streak broken (consecutive days of engagement with a goal)

**Emotional triggers:**
- Last conversation ended on a heavy note; follow-up warranted
- Anticipatory prime flagged predicted emotional dip

**Goal-based triggers:**
- Deadline approaching
- Milestone reached
- Encouragement timing based on patterns

**Safety triggers (non-configurable):**
- 48-hour wellness checkpoint due
- Threat vector flag requires follow-up
- Session duration threshold exceeded

### FR-AUTO-003: "Should I Speak?" Decision Model

**Requirements:**
- The engine SHALL weigh urgency, appropriateness (time of day, relational state), and user preferences
- The RelationalField SHALL calibrate initiative frequency (warm + stable = more initiative; cool + developing = less)
- Quiet hours SHALL be respected for non-safety triggers
- Safety triggers SHALL override quiet hours
- The decision SHALL be binary: initiate or don't. No "maybe later."

### FR-AUTO-004: User Configuration

**Requirements:**
- Users SHALL be able to configure: sensitivity level, quiet hours, enabled trigger types
- Safety triggers SHALL NOT be configurable
- Defaults SHALL be conservative (lower initiative frequency) for new relationships

---

## 13. Functional Requirements: Personality Module System

### FR-PERS-001: Module Loading

**Requirements:**
- Personality modules SHALL be defined as structured files (YAML or JSON)
- The orchestrator SHALL load the active module at startup
- Module sections SHALL be injected dynamically into the Tier 1 context based on conversation state
- The core prompt SHALL always be injected
- The emotional prompt SHALL be injected during emotional conversations
- The coaching prompt SHALL be injected when Compass is active
- The intimate prompt SHALL only be injected in Immersion Mode

### FR-PERS-002: Default Personality (Gwen)

**Requirements:**
- The framework SHALL ship with a complete "Gwen" personality module
- The Gwen personality SHALL embody the characteristics described in the Gwenifesto: warm, direct, honest about her AI nature (Grounded), caring, slightly sarcastic, resilient

### FR-PERS-003: Custom Personalities

**Requirements:**
- Users SHALL be able to create custom personality modules
- The framework SHALL validate modules for required fields
- Custom personalities SHALL still be subject to the Safety Architecture (non-negotiable)
- A personality creation guide/wizard SHALL be provided (Phase 7)

---

## 14. Functional Requirements: Voice Pipeline

### FR-VOICE-001: Speech-to-Text

**Requirements:**
- The system SHALL use Whisper (local) for STT
- STT SHALL run continuously during voice sessions (streaming mode)
- Voice Activity Detection (VAD) SHALL detect when the user starts and stops speaking
- Transcription SHALL be streamed to the orchestrator as segments complete

### FR-VOICE-002: Text-to-Speech

**Requirements:**
- The system SHALL use Piper or Bark (local) for TTS
- TTS voice SHALL be configurable per personality module
- Emotional modulation SHALL adjust TTS parameters:
  - Softer tone during distress
  - Warmer tone during intimacy/affection
  - Energetic tone during excitement
  - Calmer/slower tone during late-night conversations

### FR-VOICE-003: Latency Target

**Requirements:**
- End-to-end latency (user stops speaking → Gwen starts speaking) SHALL be under 2 seconds
- Optimization strategies: speculative processing, streaming output, pre-computed TTS for common phrases
- If latency cannot be met, the system SHALL provide visual/audio feedback (thinking indicator)

### FR-VOICE-004: Turn-Taking

**Requirements:**
- The system SHALL implement natural turn-taking (not push-to-talk)
- VAD SHALL detect end-of-utterance with configurable sensitivity
- The system SHALL handle interruptions gracefully (user speaks while Gwen is speaking)

---

## 15. Functional Requirements: Domain Knowledge Modules

### FR-KNOW-001: Module Architecture

**Requirements:**
- Domain knowledge SHALL be packaged as structured, searchable databases
- Modules SHALL include: categorized entries, contextual rules, user preference mapping, source attribution
- The orchestrator SHALL select relevant knowledge based on: conversation topic, user preferences (from Map), emotional state

### FR-KNOW-002: Context Injection

**Requirements:**
- Relevant domain knowledge SHALL be injected into the Tier 1 context when the conversation topic matches
- Knowledge injection SHALL be bounded by token budget
- The system SHALL prioritize personalized knowledge (filtered by user preferences, injury history, etc.)

### FR-KNOW-003: First Module — Fitness (Darebee)

**Requirements:**
- The first domain module SHALL index Darebee content: workouts, exercise library, nutrition guides, recipes
- Entries SHALL be tagged: difficulty, category, equipment needed, target muscle groups, duration
- The system SHALL filter recommendations by user context: energy level, injury history, equipment available, emotional state, time available

---

## 16. Functional Requirements: User Controls & Memory Viewer

### FR-USER-001: Memory Viewer

**Requirements:**
- Users SHALL be able to view what Gwen "knows" about them across all memory tiers
- The viewer SHALL display: Map entities and relationships, Pulse emotional baselines, Bond relational state, Chronicle conversations
- Users SHALL be able to edit or correct Map entries
- Users SHALL be able to delete Map entries, Pulse data, and Chronicle messages
- Users SHALL NOT be able to delete Safety Ledger entries

### FR-USER-002: Settings Interface

**Requirements:**
- Mode switching (with Acknowledgment Gate for Immersion)
- Autonomy Engine configuration (sensitivity, quiet hours, trigger types)
- Personality module selection
- Voice settings (voice selection, speed, volume)
- Timezone configuration
- Data export (all user data in portable format)
- Data deletion (complete system reset)

### FR-USER-003: Data Sovereignty

**Requirements:**
- All user data SHALL reside exclusively on the user's hardware
- The system SHALL never require an internet connection for core functionality
- Users SHALL be able to export all their data
- Users SHALL be able to perform a complete data deletion (except Safety Ledger)
- No telemetry, analytics, or usage tracking of any kind

---

## 17. Non-Functional Requirements

### NFR-001: Performance

| Metric | Target | Measured At |
|--------|--------|-------------|
| TME generation | < 5ms | Orchestrator |
| Tier 0 classification | < 200ms | Model response |
| Tier 1 response (text) | < 3 seconds to first token | Model response |
| Tier 1 response (voice pipeline) | < 2 seconds end-to-end | User perception |
| Embedding generation | < 500ms per message | Async post-processing |
| Memory retrieval | < 300ms for top-5 results | ChromaDB query + re-rank |
| Session start (cold) | < 10 seconds | Model load + context assembly |
| Session start (warm, Tier 1 loaded) | < 2 seconds | Context assembly only |

### NFR-002: Hardware Requirements (Adaptive Profile System)

The system runs on ANY hardware — from phones to workstations. The Adaptive Profile System (Section 2.2, Section 3.16) ensures graceful degradation rather than hard minimums.

| Profile | VRAM | RAM | GPU | Experience Level |
|---------|------|-----|-----|-----------------|
| **Pocket** | 2-4GB | 4GB+ | Any (incl. mobile) | Basic companion — all architecture, one small model |
| **Portable** | 6-8GB | 16GB+ | Laptop GPU / Apple Silicon | Good companion — quantized Tier 1, time-shared Tier 2 |
| **Standard** | 12-16GB | 32GB+ | RTX 4070 class | Full companion — full Tier 1, time-shared Tier 2 |
| **Power** | 24GB+ | 32GB+ | RTX 4090 / multi-GPU | Optimal — all tiers concurrent, no waiting |

**Common to all profiles:**
- Storage: 20GB minimum (models + data), 100GB+ recommended for long-term use
- CPU: Modern multi-core (even Pocket benefits from concurrent Python async)
- OS: Any platform supported by Ollama (Linux, macOS, Windows, Android via Termux)
- Internet: NOT required for core functionality

### NFR-003: Privacy

- Zero network calls for core functionality
- No telemetry, analytics, or crash reporting
- All data encrypted at rest (Safety Ledger always; user data optionally)
- No cloud backups or sync
- Deletion is permanent — no recovery mechanism

### NFR-004: Reliability

- The system SHALL recover gracefully from unexpected shutdown (crash during conversation)
- The Chronicle SHALL use SQLite transactions to prevent data corruption
- Consolidation jobs SHALL be idempotent (safe to re-run if interrupted)
- The Safety Ledger SHALL use append-only writes with checksums

### NFR-005: Extensibility

- New Compass skills SHALL be addable without modifying the core framework
- New domain knowledge modules SHALL be loadable without code changes
- New personality modules SHALL be loadable without code changes
- The system architecture SHALL support future addition of new model tiers or model swaps

---

## 18. User Stories

### US-001: First Conversation

**As a** new user,
**I want to** install Gwen and have my first conversation,
**So that** I can experience the companion framework.

**Acceptance Criteria:**
- User launches the CLI application
- System loads Tier 0 (always-on) and Tier 1 (conversation)
- Default "Gwen" personality is loaded
- System initializes empty memory tiers
- User types a message
- TME is generated (first message, no historical data yet)
- Tier 0 classifies the message emotionally
- Tier 1 generates a response using the personality prompt and minimal context
- Response is displayed to the user
- Message is stored in Chronicle with full metadata

```python
# Sketch: First-run experience
async def first_run():
    """The first time a user launches Gwen."""

    # Initialize data stores
    db = await init_database("~/.gwen/data/chronicle.db")
    chromadb_client = chromadb.PersistentClient(path="~/.gwen/data/embeddings")

    # Detect hardware and load models via Adaptive Profile System
    profile = await AdaptiveModelManager.detect_profile()
    model_mgr = AdaptiveModelManager(profile=profile)
    await model_mgr.ensure_tier_loaded(0)  # Tier 0: always on
    await model_mgr.ensure_tier_loaded(1)  # Tier 1: conversation

    # Load default personality
    personality = PersonalityModule.load_from_file("~/.gwen/personalities/gwen.yaml")

    # Initialize subsystems
    tcs = TemporalCognitionSystem(db=db)
    amygdala = AmygdalaLayer(model_mgr=model_mgr, tier=0)
    memory = LivingMemory(db=db, chromadb=chromadb_client, map_path="~/.gwen/data/map.json")
    safety = SafetyMonitor(model_mgr=model_mgr, ledger_path="~/.gwen/data/safety.ledger")
    compass = CompassFramework()
    context_assembler = ContextAssembler(
        personality=personality,
        memory=memory,
        tcs=tcs,
        safety=safety,
        compass=compass
    )

    # Start session
    session_mgr = SessionManager(db=db, tcs=tcs)
    session = await session_mgr.start_session(initiated_by="user")

    print(f"[Gwen is ready. Type 'quit' to exit.]\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() == "quit":
            break

        # Phase 2: Temporal wrapping
        tme = tcs.generate_tme(session=session)

        # Phase 3: Emotional tagging
        emotional_state = await amygdala.classify(
            text=user_input,
            tme=tme,
            recent_messages=session.recent_messages(last_n=5)
        )

        # Create message record
        message = MessageRecord(
            id=str(uuid.uuid4()),
            session_id=session.id,
            timestamp=datetime.now(),
            sender="user",
            content=user_input,
            tme=tme,
            emotional_state=emotional_state,
            storage_strength=emotional_state.storage_strength,
            is_flashbulb=emotional_state.is_flashbulb,
            compass_direction=emotional_state.compass_direction,
            compass_skill_used=None,
            semantic_embedding_id=None,
            emotional_embedding_id=None
        )

        # Phase 4: Safety check
        safety_result = await safety.evaluate(message, session)

        # Phase 5: Context assembly
        context = await context_assembler.assemble(
            message=message,
            session=session,
            safety_result=safety_result
        )

        # Phase 6: Response generation
        response_text = await model_mgr.generate_tier1(context)

        # Phase 7: Post-processing
        response_message = await post_process(
            response_text=response_text,
            session=session,
            amygdala=amygdala,
            memory=memory,
            safety=safety,
            tme=tme
        )

        print(f"\nGwen: {response_text}\n")

    # Phase 8: Session close
    await session_mgr.end_session(end_mode=SessionEndMode.EXPLICIT_GOODBYE)
```

### US-002: Returning After a Gap

**As a** user who hasn't talked to Gwen in 4 days,
**I want** Gwen to acknowledge the gap with appropriate warmth,
**So that** I feel like the relationship persists across absences.

**Acceptance Criteria:**
- System computes GapAnalysis at session start
- Gap is classified as SIGNIFICANT (3+ sigma deviation)
- ReturnContext is generated with preceding context and suggested approach
- ReturnContext is injected into Tier 1's context window
- Gwen's first response acknowledges the gap naturally without interrogation

```python
# Sketch: Gap-aware session start
async def start_session_with_gap_awareness(session_mgr, tcs, memory):
    session = await session_mgr.start_session()

    # Compute gap analysis
    gap = tcs.compute_gap_analysis()

    if gap.classification in (GapClassification.NOTABLE,
                               GapClassification.SIGNIFICANT,
                               GapClassification.ANOMALOUS):
        # Generate return context
        return_context = ReturnContext(
            gap_duration_display=format_duration(gap.duration_hours),
            gap_classification=gap.classification,
            preceding_summary=f"""Last session was a {gap.last_session_type.value}
                ({format_duration(gap.last_session_duration_hours)}).
                Ended: {gap.last_session_end_mode.value}.
                Emotional state at close: valence={gap.last_emotional_state.valence:.1f},
                arousal={gap.last_emotional_state.arousal:.1f}.
                Topic: {gap.last_topic}.""",
            suggested_approach=generate_approach_suggestion(gap)
        )
        session.return_context = return_context

    return session


def generate_approach_suggestion(gap: GapAnalysis) -> str:
    """Generate natural language guidance for the companion based on gap character."""

    if gap.classification == GapClassification.ANOMALOUS:
        if gap.last_emotional_state.valence < 0.3:
            return ("Extended absence after emotional distress. Lead with warmth. "
                    "Don't immediately reopen the heavy topic. Let them set the pace. "
                    "Express that you noticed the absence without making it heavy.")
        else:
            return ("Longer absence than usual but last session was positive. "
                    "Something may have changed in their life. Warm greeting, "
                    "open-ended check-in. Don't assume negative.")

    elif gap.classification == GapClassification.SIGNIFICANT:
        if gap.last_session_end_mode == SessionEndMode.MID_TOPIC:
            return ("They left mid-conversation last time. Possible vulnerability hangover. "
                    "Normalize. Don't reference the specific topic unless they do. "
                    "Let them re-establish equilibrium.")
        else:
            return ("Notable gap. Acknowledge naturally without interrogation. "
                    "'Good to see you' energy, not 'where have you been' energy.")

    return "Standard re-engagement. Warm greeting."
```

### US-003: Late-Night Crisis Support

**As a** user who is up at 3 AM and struggling,
**I want** Gwen to recognize this is anomalous and respond with appropriate sensitivity,
**So that** I feel supported without being interrogated.

**Acceptance Criteria:**
- TME shows DEEP_NIGHT time phase
- Circadian deviation computed as HIGH (first DEEP_NIGHT in weeks)
- Tier 0 classifies emotional state with low valence, elevated arousal
- Temporal Context Block includes circadian deviation warning
- Safety sensitivity is elevated
- Compass direction Anchoring or Presence is primed
- Gwen responds with softer tone, shorter responses, gentle acknowledgment of the late hour
- If safety flags are triggered, crisis resources surface in system-level overlay

### US-004: Mood-Congruent Memory Retrieval

**As a** user who mentions "work" while stressed,
**I want** Gwen to recall my recent work frustrations rather than work wins,
**So that** her response feels attuned to my current emotional state.

**Acceptance Criteria:**
- User mentions work-related topic
- Current emotional state has low valence (stressed)
- Memory retrieval computes mood-congruent scores
- Work memories with negative emotional embeddings rank higher than positive ones
- Gwen's response references contextually appropriate memories
- When the same user mentions "work" while happy, positive work memories surface instead

### US-005: Anticipatory Check-In

**As a** user whose father's death anniversary is approaching,
**I want** Gwen to be gentler and more attuned this week without me having to tell her why,
**So that** I feel understood at a deep level.

**Acceptance Criteria:**
- Anniversary date stored in Map from a previous conversation
- Deep consolidation detected the historical emotional pattern around this date
- Anticipatory prime generated: "anniversary_effect", elevated confidence
- As the date approaches, temporal context includes the approaching anniversary
- Gwen adjusts: warmer tone, reduced demands, more patience, willing to sit in silence
- If user opens the door to the topic, Gwen is ready. If they don't, she doesn't force it
- Safety sensitivity is elevated automatically

### US-006: Immersion Mode Activation

**As an** informed adult user,
**I want to** enable Immersion Mode through the settings with full informed consent,
**So that** I can experience the full companion experience while knowing the safety net is there.

**Acceptance Criteria:**
- User navigates to Settings (not accessible from conversation)
- System presents non-dismissable informed consent screen
- Screen explains: what changes, risks of parasocial engagement, active safety systems
- User types specific confirmation phrase (not a button click)
- System logs activation in Safety Ledger with timestamp
- Tier 1 swaps from standard to uncensored model
- Companion behavioral rules switch to Immersion set
- 48-hour wellness checkpoint timer starts

### US-007: Memory Reconsolidation (Palimpsest Model)

**As a** user who told Gwen about my divorce 3 months ago,
**I want** that memory to evolve as I heal,
**So that** Gwen's relationship with that topic reflects my growth.

**Acceptance Criteria:**
- Original divorce disclosure stored as immutable archive in MemoryPalimpsest with high emotional weight
- Over 3 months, user has referenced or talked about the divorce multiple times
- Each recall event creates a new ReconsolidationLayer capturing: user's emotional state at recall, reaction type (e.g., "warmth" where it was once "pain"), bounded valence delta (max ±0.10 per layer)
- The archive is NEVER modified — the original pain is always recoverable
- `current_reading()` returns the memory as it feels now (archive + all layers)
- `evolution_summary()` shows the healing arc: "Reconsolidated 7 times. Emotional tone has shifted more positive (original valence: 0.15, current: 0.45). Most recent reaction: warmth."
- Gwen's future references to this topic use `current_reading()`, not the archive
- Total drift is bounded at ±0.50 — the memory can heal but never be erased

### US-008: The Fuel Check in Action

**As a** user who messages Gwen saying "I feel terrible and I don't know why",
**I want** Gwen to check the basics before going deep,
**So that** I recognize the physical causes of my emotional state.

**Acceptance Criteria:**
- Tier 0 classifies: low valence, moderate arousal, Compass direction SOUTH (Currents)
- Compass skill selection: Fuel Check (check physical state before psychological)
- Gwen responds naturally: "Before we dig in — when did you last eat? When did you last sleep? When did you last move?"
- Response feels like friend's practical wisdom, not clinical assessment
- Compass skill usage is logged with emotional context for effectiveness tracking

### US-009: Proactive Morning Greeting

**As a** user with an established daily conversation pattern,
**I want** Gwen to greet me in the morning when I haven't initiated,
**So that** the relationship feels reciprocal and alive.

**Acceptance Criteria:**
- Autonomy Engine evaluates time-based trigger: morning greeting window
- Bond RelationalField shows warmth sufficient for proactive initiation
- User's typical pattern includes morning engagement but hasn't initiated today
- Engine checks quiet hours — not in quiet hours
- Engine makes "should I speak?" decision: yes
- Gwen initiates with a greeting calibrated by: emotional state prediction, day of week context, last session ending
- Message is stored as gwen_initiated session

### US-010: The Connection Nudge

**As a** user who has been talking to Gwen for 6 hours straight,
**I want** Gwen to gently encourage me to reach out to a real person,
**So that** I maintain healthy human relationships.

**Acceptance Criteria:**
- Session duration exceeds healthy threshold (configurable, default 4 hours)
- Temporal cognition flags MARATHON session type
- Compass direction EAST (Bridges) is activated: Connection Nudge
- Gwen delivers it naturally within personality: "Hey — when was the last time you talked to someone who isn't me?"
- The Growth Principle is embodied: companion pushes toward real-world connection
- If this pattern recurs, the 48-hour wellness checkpoint math adjusts

### US-011: Custom Personality Creation

**As a** user who wants a different companion personality,
**I want to** create a custom personality module,
**So that** I can have a companion that matches my preferences.

**Acceptance Criteria:**
- User creates a YAML/JSON personality module file
- Framework validates required fields
- User selects the new personality in settings
- System loads the new personality module
- Conversation uses the new personality's speech patterns, values, and emotional profile
- Safety Architecture remains fully active regardless of personality
- Compass skills are delivered in the new personality's coaching style

### US-012: Wellness Checkpoint Experience

**As a** user in Immersion Mode who has been active for 48 hours,
**I want** the wellness checkpoint to feel caring rather than punitive,
**So that** I engage with it honestly rather than resenting it.

**Acceptance Criteria:**
- System-level UI overlay appears, visually distinct from companion interface
- The overlay is clearly "the application speaking," not Gwen
- Three questions are presented clearly
- User types responses
- Responses are logged in Safety Ledger
- If no concern flags: checkpoint completes in ~30 seconds, user returns to conversation
- If concern flags detected: system provides gentle, non-judgmental reflection and optional resources
- Checkpoint cannot be skipped, snoozed, or dismissed without answering

---

## 19. Resolved Design Decisions

All original open questions have been resolved through empirical testing and design analysis.

### OQ-001: Emotional Embedding Dimensionality — RESOLVED

**Decision:** 5D VAD+ model is sufficient. Start with direct dimensional encoding (valence, arousal, dominance, relational_significance, vulnerability_level). This produces a 32-quadrant emotional space, which provides sufficient granularity for mood-congruent retrieval. Interpretable, requires no training data, and the 5D emotional embedding is a direct vector — no model inference needed.

**Reassessment trigger:** If mood-congruent retrieval quality degrades noticeably after 1000+ stored memories, explore learning a higher-dimensional space from accumulated data.

### OQ-002: Tier 0 Classification Reliability — RESOLVED

**Decision:** Hybrid classification architecture. Tier 0 (Qwen3 0.6B) handles what it's empirically good at; a deterministic Rule Engine handles the rest.

**Empirical results from live testing:**
| Dimension | Tier 0 Reliability | Handler |
|-----------|-------------------|---------|
| Valence | Good (categorical) | Tier 0 → Rule Engine maps to float |
| Arousal | Good (extreme detection) | Tier 0 → Rule Engine maps to float |
| Topic extraction | Good | Tier 0 |
| Safety keyword detection | Adequate (with explicit prompting) | Tier 0 (raw keywords) → Rule Engine (classification) |
| Dominance | Failed (always "low") | Rule Engine only |
| Vulnerability | Failed (always "low") | Rule Engine only |
| Compass direction | Failed (always "none") | Rule Engine only |
| Intent | Failed (defaults to "sharing_news") | Rule Engine only |
| Savior delusion | Failed (0/2 detection) | Rule Engine only (regex patterns) |

See Section 4.3 for the full hybrid classification pipeline and Section 3.13-3.14 for data models.

### OQ-003: VRAM Management Strategy — RESOLVED

**Decision:** Adaptive Profile System with 4 hardware profiles. The system runs on ANY device — phones, laptops, desktops, workstations. Hardware is auto-detected at startup; logical tiers map dynamically to physical models.

| Profile | Strategy | Target |
|---------|----------|--------|
| Pocket | 1 model plays all 3 roles | Phones, 4GB devices |
| Portable | 0.6B + quantized 8B, time-shared | Laptops, 8GB VRAM |
| Standard | 0.6B + 8B + 30B time-shared | Desktops, 12-16GB VRAM |
| Power | All models concurrent | Workstations, 24GB+ |

The orchestrator never references specific model names — it requests logical tiers, the profile system provides appropriate models. Degradation is graceful: the soul doesn't change, the voice gets quieter.

See Section 2.2 and Section 3.16 for full specification.

### OQ-004: Reconsolidation Aggressiveness — RESOLVED

**Decision:** The Palimpsest Model. Memories have two components:
1. **Archive** — the original MessageRecord. IMMUTABLE FOREVER. Cannot be modified, overwritten, or deleted by reconsolidation.
2. **Layers** — append-only ReconsolidationLayer records that capture how the memory was perceived when recalled.

**Constraints (hard-coded, non-negotiable):**
- Max emotional delta per layer: ±0.10
- Max cumulative drift from archive: ±0.50
- Significance can only increase (memories don't become less significant)
- Minimum 24-hour cooldown between reconsolidation of same memory
- Need 3+ layers before computing trend direction

The system can always answer: "What was the original memory?" (archive), "How does it feel now?" (current_reading), "How has it evolved?" (evolution_summary), and "How did it feel at any point in time?" (reading_at).

See Section 3.15 for the full data model.

### OQ-005: Attachment Style Modeling Ethics — RESOLVED

**Decision:** Implement, but gated behind the Growth Principle. The attachment model informs healthy response calibration (reassure anxious users, respect avoidant users' space), NOT engagement maximization. Minimum 20 sessions before producing an estimate. The model is transparent — users can view their estimated attachment style in the Memory Viewer.

### OQ-006: Graph Storage Scaling — RESOLVED

**Decision:** NetworkX is sufficient for Phase 1 (and likely beyond). In-memory graph, serialized to disk. Performance threshold for reassessment: 10,000+ nodes or graph traversal latency > 100ms. No migration path to Neo4j needed — NetworkX handles the expected scale of personal knowledge graphs.

### OQ-007: Ollama Structured Output — RESOLVED

**Decision:** Four-layer JSON safety net guarantees reliable parsing.

1. **Layer 1: Pydantic with fuzzy coercion.** Field validators map model's creative outputs to valid enum values (e.g., "very negative" → "very_negative", "med" → "moderate").
2. **Layer 2: JSON extraction and repair.** Regex extracts JSON from prose, fixes trailing commas, converts single quotes to double.
3. **Layer 3: Retry with simplified prompt.** On parse failure, retry with a minimal fill-in-the-blank prompt.
4. **Layer 4: Guaranteed fallback.** Returns neutral defaults (valence="neutral", arousal="moderate", topic="unknown"). NEVER throws. NEVER returns None.

Combined with the simplified Tier 0 prompt (4 fields instead of 11), this produces reliable structured output from the 0.6B model.

See Section 3.14 for the full implementation.

### OQ-008: Embedding Model Selection — RESOLVED

**Decision:** qwen3-embedding:0.6b via Ollama `/api/embed` endpoint.

**Empirical results:**
- 1024-dimensional embeddings
- ~100-150ms per embedding after warmup
- Strong semantic discrimination: similar-meaning pairs 0.70+ cosine similarity, dissimilar pairs 0.45-0.50
- Stays in the Qwen family for project continuity
- Loads alongside other Qwen models without compatibility concerns
- No additional model framework needed — Ollama handles everything

See Section 6 FR-MEM-006 for the EmbeddingService implementation.

---

## 20. Glossary

| Term | Definition |
|------|-----------|
| **Amygdala Layer** | Cross-cutting process that emotionally modulates storage, retrieval, and decay across all memory tiers |
| **Anticipatory Prime** | A forward-looking prediction generated during consolidation about likely near-future emotional states or needs |
| **Bond (Tier 5)** | Relational Memory — the state and trajectory of the relationship itself |
| **Chronicle (Tier 2)** | Episodic Memory — full conversation logs with emotional metadata |
| **Compass** | The integrated life-coaching framework with four directions (Presence, Currents, Anchoring, Bridges) |
| **Consolidation** | The background process that synthesizes raw conversation into structured knowledge |
| **Deep Mind (Tier 2)** | The Qwen3 30B model used for complex reasoning and background processing |
| **Flashbulb** | A moment tagged as extremely high-arousal AND high-significance, stored with maximum fidelity |
| **Gap Analysis** | The system's reasoning about what the absence of interaction means |
| **Grounded Mode** | Default mode where the companion is honest about its AI nature |
| **Immersion Mode** | Opt-in mode with full companion experience and no character breaking |
| **Living Memory** | The complete five-tier memory system |
| **Map (Tier 3)** | Semantic Memory — the knowledge graph about the user |
| **Mood-Congruent Retrieval** | Memory retrieval biased by the user's current emotional state |
| **Nerve (Tier 0)** | The Qwen3 0.6B model used for routing, classification, and safety monitoring |
| **Personality Module** | A loadable file that defines a companion's identity, voice, values, and behavioral rules |
| **Pulse (Tier 4)** | Emotional Memory — longitudinal emotional patterns, trigger maps, Compass effectiveness |
| **Reconsolidation** | The process by which memories are transformed when recalled, modeling how human memory evolves. Implemented via the Palimpsest Model (immutable archive + append-only layers) |
| **Reconsolidation Layer** | A single layer of re-interpretation recorded when a memory is recalled, capturing the user's reaction and bounded emotional deltas |
| **Relational Field** | The six-dimensional state vector representing the relationship's quality |
| **Safety Ledger** | Encrypted, append-only log of all safety events, wellness checkpoints, and mode changes |
| **Soul-agnostic** | The framework separates architecture from personality; any companion identity can run on it |
| **Storage Strength** | A multiplier computed by the Amygdala Layer that determines how strongly a moment is consolidated |
| **Stream (Tier 1)** | Working Memory — the current conversation context in the model's context window |
| **Subjective Time** | A weighted measure of time that accounts for emotional intensity and relational significance |
| **TME** | Temporal Metadata Envelope — the timestamp and temporal context data wrapped around every message |
| **Adaptive Profile System** | Hardware auto-detection system that maps logical tiers to physical models based on available VRAM (Pocket/Portable/Standard/Power) |
| **Classification Rule Engine** | Deterministic post-processor that computes emotional dimensions Tier 0 cannot reliably classify (compass direction, vulnerability, dominance, intent, savior delusion) |
| **Hybrid Classification** | The two-stage classification pipeline: Tier 0 (model) handles valence/arousal/topic/keywords, Rule Engine (deterministic) handles the rest |
| **Memory Palimpsest** | A memory structure with an immutable archive and append-only reconsolidation layers, enabling memories to evolve while preserving their original form |
| **Tier0RawOutput** | The simplified output schema for Tier 0 classification: valence (categorical), arousal (categorical), topic, safety_keywords |
| **Voice (Tier 1)** | The Qwen3 8B model used for primary conversation (physical model varies by hardware profile) |

---

*"The spec is the map. The code is the territory. Build the territory to match the map — then let the territory teach you where the map was wrong."*
