# Spec: Session Manager

## 1. Context & Goal
Build session lifecycle management — start sessions, end sessions, detect timeouts, classify session types, and compute gap analysis. This is the backbone of conversation state. References SRS.md FR-ORCH-002, FR-TCS-004, FR-TCS-005.

## 2. Technical Approach
- SessionManager class handles full lifecycle
- Session state held in memory during active session, persisted to Chronicle on close
- Gap analysis uses Chronicle history for statistical comparison
- Session classification by duration thresholds

## 3. Requirements
- [ ] SessionManager with start_session() -> SessionRecord (partial)
- [ ] end_session(end_mode) that finalizes and saves SessionRecord
- [ ] detect_session_timeout() for idle detection (30 min default)
- [ ] Session type classification (duration-based: PING <5min, CHAT 5-30, HANG 30-90, DEEP_DIVE 90-180, MARATHON 180+)
- [ ] GapAnalysis computation at session start
- [ ] ReturnContext generation for NOTABLE+ gaps
- [ ] Track message counts, response latencies during session

## 4. Verification Plan
- [ ] start_session creates valid partial SessionRecord
- [ ] end_session computes correct session type by duration
- [ ] Gap analysis correctly classifies gaps by deviation sigma
- [ ] Timeout detection triggers with correct end_mode
- [ ] pytest tests/test_session.py passes
