# Spec: Ollama Integration

## 1. Context & Goal
Build the AdaptiveModelManager that auto-detects hardware and maps logical tiers (0, 1, 2) to physical Ollama models. The orchestrator never knows which physical model it's talking to — it requests a tier. References SRS.md Sections 2.2 and 3.16.

## 2. Technical Approach
- HTTP calls to Ollama API (localhost:11434) via urllib.request (no extra deps needed)
- Hardware detection via Ollama's /api/ps and system info
- 4 hardware profiles: Pocket (2-4GB), Portable (6-8GB), Standard (12-16GB), Power (24GB+)
- Async model loading/unloading

## 3. Requirements
- [ ] HardwareProfile enum (POCKET, PORTABLE, STANDARD, POWER) — already in models, import it
- [ ] AdaptiveModelManager class with profile detection
- [ ] TIER_MAPS: mapping from profile → {tier → model_name}
- [ ] CONCURRENCY: mapping from profile → {max_concurrent, tier2_strategy}
- [ ] detect_profile() static method that queries Ollama for available VRAM
- [ ] get_model_for_tier(tier) method
- [ ] ensure_tier_loaded(tier) method that handles VRAM concurrency
- [ ] generate(tier, prompt, **kwargs) method that sends prompt to the right model
- [ ] Graceful fallback if Ollama is not running

## 4. Verification Plan
- [ ] detect_profile() returns a valid HardwareProfile based on available VRAM
- [ ] get_model_for_tier() returns correct model names for each profile
- [ ] generate() with Tier 0 returns a response from qwen3:0.6b
- [ ] pytest tests/test_model_manager.py passes (unit tests + one integration test with Ollama)
