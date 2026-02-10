# Plan: Live Integration Testing

## Phase 1: Setup
- [x] Create conductor track files (spec.md, plan.md)
- [x] Update tracks.md and index.md
- [x] Add integration fixtures to tests/conftest.py

## Phase 2: Implementation
- [x] Create tests/test_live_integration.py
- [x] Layer 1: Ollama health (5 tests)
- [x] Layer 2: Subsystem live (10 tests)
- [x] Layer 3: Classification pipeline (8 tests)
- [x] Layer 4: Full orchestrator round-trip (8 tests)
- [x] Layer 5: Edge cases (5 tests)

## Phase 3: Verification
- [x] Run live integration tests against Ollama
- [x] Fix any failures
- [x] Verify existing unit tests unaffected (586 passed)
- [x] Update conductor docs

## Bugs Found & Fixed
- **FOREIGN KEY constraint failure**: Orchestrator wasn't inserting session into Chronicle at startup, causing PostProcessor's insert_message to fail on FK constraint. Fixed by adding `chronicle.insert_session(session)` after `start_session()` and changing `INSERT INTO` to `INSERT OR REPLACE INTO` in Chronicle.
- **Naive/aware datetime mismatch**: SessionManager uses `datetime.now(timezone.utc)` for start_time, but SessionCloser sets end_time from message timestamps (naive). Fixed by normalizing both timestamps before subtraction in light.py.
- **MessageRecord constructor**: Test code was missing required `compass_skill_used` parameter.
- **Windows tmpdir cleanup**: SQLite connection held open prevented temp directory cleanup on Windows. Fixed with `ignore_cleanup_errors=True`.
