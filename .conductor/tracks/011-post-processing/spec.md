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
- [x] PostProcessor class with process() that handles all Phase 7 steps
- [x] Tag companion response emotionally (Tier 0 + Rule Engine)
- [x] Store both user and companion MessageRecords in Chronicle
- [x] Generate and store embeddings for both messages
- [x] Update session statistics (counts, latency)
- [x] Update Stream with both messages
- [x] Return companion MessageRecord

## 4. Verification Plan
- [x] Both messages stored in Chronicle after processing
- [x] Companion response has emotional tags
- [x] Session stats updated correctly
- [x] Stream contains both messages
- [x] pytest tests/test_post_processing.py passes
