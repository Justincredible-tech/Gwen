# Spec: Amygdala Layer

## 1. Context & Goal
Build the Amygdala Layer — the cross-cutting emotional modulation system that affects storage, retrieval, and decay. Plus mood-congruent memory retrieval with safety inversion. References SRS.md Section 8 (FR-AMY-001 through FR-AMY-004) and Section 4.5.1.

## 2. Technical Approach
- AmygdalaLayer is a service class, not a storage tier — it modulates operations
- Storage strength: arousal * 0.4 + relational_significance * 0.4 + vulnerability * 0.2
- Flashbulb: arousal > 0.8 AND relational_significance > 0.8
- Mood-congruent retrieval: final_score = semantic_relevance * (1 + alpha * emotional_congruence)
- Safety inversion: during crisis, bias INVERTS to surface positive memories
- Decay modulation: negative memories decay slower, flashbulbs resist decay

## 3. Requirements
- [ ] AmygdalaLayer class with compute_storage_modulation(emotional_state) -> (storage_strength, is_flashbulb)
- [ ] Mood-congruent retrieval: retrieve_memories(query, current_state, safety_level, alpha=0.3)
- [ ] Safety inversion: when safety HIGH/CRITICAL, surface incongruent (positive) memories
- [ ] Distress penalty: penalize sensitive memories when user valence < 0.3
- [ ] Decay modulation: compute_decay_factor(emotional_state, time_elapsed) -> float
- [ ] Negativity bias in decay (negative memories decay slower)
- [ ] Flashbulb memories resist decay

## 4. Verification Plan
- [ ] Storage strength computed correctly for various emotional states
- [ ] Flashbulb triggers at correct thresholds
- [ ] Mood-congruent retrieval biases toward matching emotional memories
- [ ] Safety inversion surfaces positive memories during crisis
- [ ] Negative memories decay slower than positive
- [ ] Flashbulb memories barely decay
- [ ] pytest tests/test_amygdala.py passes
