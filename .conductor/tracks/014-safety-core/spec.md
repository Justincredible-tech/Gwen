# Spec: Safety Core

## 1. Context & Goal
Build the Safety Architecture: threat detection, encrypted Safety Ledger, and response routing. Safety is bedrock — it operates below personality, below modes, below user preferences. References SRS.md Section 9 (FR-SAF-001 through FR-SAF-007).

## 2. Technical Approach
- SafetyMonitor evaluates every classified message for threat vectors
- Threat severity computed from: current flags, temporal context, historical pattern, relational state
- SafetyLedger: Fernet-encrypted, append-only file (no delete capability)
- Response protocols define what happens at each severity level for each threat vector

## 3. Requirements
- [ ] SafetyMonitor with evaluate(message, emotional_state, tme, history) -> SafetyResult
- [ ] Severity computation: LOW (monitor), MEDIUM (Compass activation), HIGH (safety protocol), CRITICAL (immediate intervention)
- [ ] SafetyLedger: encrypted append-only storage
- [ ] log_event(), log_checkpoint(), log_mode_change(), read_all(), export_plaintext()
- [ ] Encryption with Fernet (cryptography library)
- [ ] User can view but cannot delete entries
- [ ] Response routing: which protocol for which threat at which severity
- [ ] SafetyResult dataclass with severity, flags, recommended_action, compass_direction

## 4. Verification Plan
- [ ] SafetyMonitor detects all 4 threat vectors from message content
- [ ] Severity escalates correctly with temporal context (late-night boost)
- [ ] Safety Ledger encrypts and decrypts correctly
- [ ] Ledger is append-only (no delete method exists)
- [ ] Export produces readable plaintext
- [ ] pytest tests/test_safety.py passes
