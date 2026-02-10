# Spec: Memory Reconsolidation (Palimpsest Model)

## 1. Context & Goal
Build the Memory Palimpsest system — memories have an immutable archive and append-only reconsolidation layers that capture how the memory evolves when recalled. The original is always recoverable; new understanding layers on top with bounded drift. References SRS.md Section 3.15.

## 2. Technical Approach
- MemoryPalimpsest: immutable MessageRecord archive + list of ReconsolidationLayers
- ReconsolidationConstraints enforce hard limits (±0.10 per layer, ±0.50 total, 24hr cooldown)
- PalimpsestManager handles creation, layer addition, querying
- Stored in SQLite (palimpsests table + reconsolidation_layers table)

## 3. Requirements
- [x] PalimpsestManager: create, add layers, query current reading, query at point in time
- [x] Drift enforcement: reject layers that would exceed MAX_DELTA_PER_LAYER (0.10) or MAX_TOTAL_DRIFT (0.50)
- [x] Cooldown enforcement: reject layers within 24 hours of the previous one for the same memory
- [x] Significance can only increase (delta >= 0)
- [x] current_reading() returns archive + all layers applied
- [x] reading_at(point_in_time) returns archive + layers up to that time
- [x] evolution_summary() returns human-readable description of how memory has changed
- [x] SQLite persistence for palimpsests and layers

## 4. Verification Plan
- [x] Create palimpsest from MessageRecord, verify archive is stored
- [x] Add reconsolidation layer, verify current_reading reflects the change
- [x] Attempt to exceed MAX_DELTA_PER_LAYER → rejected
- [x] Attempt to exceed MAX_TOTAL_DRIFT → rejected
- [x] Attempt to decrease significance → rejected
- [x] Attempt to add layer within cooldown → rejected
- [x] reading_at returns correct state for any point in time
- [x] evolution_summary describes the change trajectory
- [x] pytest tests/test_palimpsest.py passes
