# Spec: Emotional Memory (Pulse & Bond)

## 1. Context & Goal
Build Pulse (Tier 4: Emotional Memory) and Bond (Tier 5: Relational Memory). Pulse tracks emotional baselines, trajectories, and trigger maps. Bond tracks the 6-dimensional relational field and attachment style indicators. References SRS.md Sections 3.6, 3.7, FR-MEM-004, FR-MEM-005.

## 2. Technical Approach
- Pulse: rolling baselines stored as JSON, trajectories as records in SQLite
- Bond: single BondState object, updated incrementally after each session
- Trigger map: probabilistic associations built over time
- Attachment style: estimated after 20+ sessions from behavioral indicators

## 3. Requirements
- [ ] PulseManager: maintain emotional baselines (overall, per day-of-week, per time-phase)
- [ ] Update baselines from new session data
- [ ] Store and query emotional trajectories
- [ ] TriggerMap: build associations between contexts and emotional changes
- [ ] BondManager: maintain RelationalField (6 dimensions)
- [ ] Update relational field after each session
- [ ] Track field history (time-series)
- [ ] Attachment style estimation (minimum 20 sessions)

## 4. Verification Plan
- [ ] Baseline computation averages correctly
- [ ] Baseline updates incrementally with new data
- [ ] Bond field updates in correct direction after positive/negative sessions
- [ ] Attachment style not estimated until 20+ sessions
- [ ] pytest tests/test_emotional_memory.py passes
