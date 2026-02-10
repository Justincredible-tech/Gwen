# Spec: Data Models

## 1. Context & Goal
Define every data structure that flows through the Gwen system as Python dataclasses, enums, and Pydantic models. These are the contracts between components -- if the models are right, everything else plugs together. References SRS.md Sections 3.1 through 3.16.

## 2. Technical Approach
- Python dataclasses for domain models
- Python enums for fixed vocabularies
- Pydantic BaseModel for Tier0RawOutput (needs validation/coercion)
- All models in gwen/models/ package, organized by domain

## 3. Requirements
- [ ] EmotionalStateVector with 5 dimensions + compass + computed properties (storage_strength, is_flashbulb)
- [ ] CompassDirection enum
- [ ] TimePhase, CircadianDeviationSeverity enums
- [ ] TemporalMetadataEnvelope with all fields
- [ ] MessageRecord with full schema
- [ ] SessionRecord, SessionType, SessionEndMode
- [ ] MapEntity, MapEdge
- [ ] EmotionalBaseline, EmotionalTrajectory, TriggerMapEntry, CompassEffectivenessRecord
- [ ] RelationalField, BondState
- [ ] GapAnalysis, GapClassification, ReturnContext
- [ ] AnticipatoryPrime
- [ ] ThreatVector, ThreatSeverity, SafetyEvent, WellnessCheckpoint
- [ ] PersonalityModule
- [ ] ConsolidationType, ConsolidationJob
- [ ] Tier0RawOutput (Pydantic) with fuzzy field validators
- [ ] ReconsolidationLayer, ReconsolidationConstraints, MemoryPalimpsest
- [ ] HardwareProfile enum
- [ ] All models importable from gwen.models

## 4. Verification Plan
- [ ] All models instantiate with valid data
- [ ] EmotionalStateVector.storage_strength computes correctly
- [ ] EmotionalStateVector.is_flashbulb triggers at correct thresholds
- [ ] Tier0RawOutput fuzzy validators coerce "very negative" to "very_negative", "med" to "moderate"
- [ ] MemoryPalimpsest enforces drift bounds
- [ ] pytest tests/test_models.py passes
