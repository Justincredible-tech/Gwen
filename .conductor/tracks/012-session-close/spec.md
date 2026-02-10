# Spec: Session Close & Light Consolidation

## 1. Context & Goal
Build Phase 8 of the message lifecycle: when a session ends, classify it, compute the emotional arc, calculate subjective time, save the SessionRecord, and trigger light consolidation. References SRS.md Section 4.8, FR-TCS-004, FR-TCS-008.

## 2. Technical Approach
- SessionCloser handles all Phase 8 logic
- Light consolidation archives Stream to Chronicle (already happening per-message, so this is mostly cleanup)
- Subjective time: clock_duration * emotional_intensity * relational_significance
- Emotional arc: opening state (first message), peak state (highest arousal), closing state (last message)

## 3. Requirements
- [ ] SessionCloser class with close(session, stream, chronicle) method
- [ ] Emotional arc computation (opening, peak, closing EmotionalStateVectors)
- [ ] Subjective time computation
- [ ] Relational field delta computation (placeholder — real computation in Track 017)
- [ ] Save complete SessionRecord to Chronicle
- [ ] Light consolidation: clear Stream, unload Tier 1 if idle timeout configured
- [ ] Evaluate if standard consolidation should trigger

## 4. Verification Plan
- [ ] Session type classified correctly from duration
- [ ] Emotional arc captures opening, peak (highest arousal), closing states
- [ ] Subjective time computed correctly
- [ ] SessionRecord saved with all fields
- [ ] pytest tests/test_session_close.py passes
