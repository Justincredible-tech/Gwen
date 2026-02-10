# Spec: Live Integration Testing

## 1. Context & Goal
Create a comprehensive live integration test suite that exercises all Gwen subsystems against a running Ollama instance. Validates that the full message lifecycle works end-to-end with real model inference. This is the first testing track that uses real LLM calls instead of mocks.

## 2. Technical Approach
- 5-layer test architecture: health → subsystem → classification → orchestrator → edge cases
- All tests marked `@pytest.mark.ollama` for selective execution
- Session-scoped fixtures for Ollama connections (avoid cold starts)
- Function-scoped fixtures for databases (test isolation)
- Wide assertion ranges for 0.6B model imprecision

## 3. Requirements
- [x] Layer 1: Ollama health checks (reachability, model availability, profile detection)
- [x] Layer 2: Subsystem live tests (generate, embed, classify, store, search)
- [x] Layer 3: Classification pipeline (Tier 0 + Rule Engine end-to-end)
- [x] Layer 4: Full orchestrator round-trip (8-phase message lifecycle)
- [x] Layer 5: Edge cases and robustness (empty, long, unicode, rapid, goodbye)
- [x] Integration fixtures in conftest.py

## 4. Verification Plan
- [x] All 36 live integration tests pass against running Ollama
- [x] Existing 586 unit tests unaffected
- [x] Tests can be selectively run with `pytest -m ollama`
