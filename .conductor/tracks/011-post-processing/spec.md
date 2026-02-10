# Spec: Response Post-Processing

## 1. Context & Goal
Build Phase 7 of the message lifecycle: after Tier 1 generates a response, we tag it emotionally, store both messages in Chronicle, generate embeddings, and update session statistics. References SRS.md Section 4.7.

## 2. Technical Approach
- Post-processor runs after every Tier 1 response
- Re-classifies companion's response through Tier 0 (to track Gwen's emotional trajectory)
- Stores messages in Chronicle with full metadata
- Generates embeddings asynchronously
- Updates session stats (message counts, latency)

## 3. Requirements
- [ ] PostProcessor class with process() that handles all Phase 7 steps
- [ ] Tag companion response emotionally (Tier 0 + Rule Engine)
- [ ] Store both user and companion MessageRecords in Chronicle
- [ ] Generate and store embeddings for both messages
- [ ] Update session statistics (counts, latency)
- [ ] Update Stream with both messages
- [ ] Return companion MessageRecord

## 4. Verification Plan
- [ ] Both messages stored in Chronicle after processing
- [ ] Companion response has emotional tags
- [ ] Session stats updated correctly
- [ ] Stream contains both messages
- [ ] pytest tests/test_post_processing.py passes
