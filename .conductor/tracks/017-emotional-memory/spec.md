# Spec: Emotional Memory (Pulse & Bond)

## 1. Context & Goal
Build Pulse (Tier 4: Emotional Memory) and Bond (Tier 5: Relational Memory). Pulse tracks emotional baselines, trajectories, and trigger maps. Bond tracks the 6-dimensional relational field and attachment style indicators. References SRS.md Sections 3.6, 3.7, FR-MEM-004, FR-MEM-005.

## 2. Technical Approach
- Pulse: rolling baselines stored as JSON, trajectories as records in SQLite
- Bond: single BondState object, updated incrementally after each session
- Trigger map: probabilistic associations built over time
- Attachment style: estimated after 20+ sessions from behavioral indicators

## 3. Requirements
- [x] PulseManager: maintain emotional baselines (overall, per day-of-week, per time-phase)
- [x] Update baselines from new session data
- [x] Store and query emotional trajectories
- [x] TriggerMap: build associations between contexts and emotional changes
- [x] BondManager: maintain RelationalField (6 dimensions)
- [x] Update relational field after each session
- [x] Track field history (time-series)
- [x] Attachment style estimation (minimum 20 sessions)

## 4. Verification Plan
- [x] Baseline computation averages correctly
- [x] Baseline updates incrementally with new data
- [x] Bond field updates in correct direction after positive/negative sessions
- [x] Attachment style not estimated until 20+ sessions
- [x] pytest tests/test_emotional_memory.py passes
