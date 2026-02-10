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
