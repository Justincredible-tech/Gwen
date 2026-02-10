# Spec: TME Generator

## 1. Context & Goal
Build the Temporal Metadata Envelope (TME) generator. This wraps every message with rich temporal context — all computed from system clocks and SQLite queries, zero model inference. The TME is the foundation of Gwen's temporal awareness. References SRS.md Sections 3.2 and 7 (FR-TCS-001).

## 2. Technical Approach
- Pure Python datetime computation (no external libraries)
- Session state tracked in memory
- Inter-session statistics queried from Chronicle SQLite
- TimePhase computed from local hour
- Circadian deviation starts as NONE until enough data accumulates

## 3. Requirements
- [ ] TMEGenerator class that produces TemporalMetadataEnvelope for any message
- [ ] TimePhase computation from local hour (7 phases with correct boundaries)
- [ ] Session context tracking (session_id, start time, message index, duration)
- [ ] Intra-message timing (time since last message, user messages in last 5min/1hr/24hr)
- [ ] Inter-session timing (hours since last session, sessions in last 7/30 days, avg gap)
- [ ] Circadian deviation: NONE until 30+ days of data, then compare to baseline
- [ ] Weekend detection

## 4. Verification Plan
- [ ] TimePhase correctly maps all hours (0-23) to phases
- [ ] TME for first message has None for time_since_last_msg
- [ ] TME for second message has correct time_since_last_msg
- [ ] Weekend detection works for Saturday and Sunday
- [ ] pytest tests/test_tme.py passes
