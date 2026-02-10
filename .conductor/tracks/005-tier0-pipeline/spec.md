# Spec: Tier 0 Classification Pipeline

## 1. Context & Goal
Build the hybrid classification system: Tier 0 (qwen3:0.6b) produces a simplified JSON output (valence, arousal, topic, safety_keywords), then the Tier0Parser guarantees valid parsing through 4 safety layers, and the ClassificationRuleEngine computes all remaining dimensions deterministically. This is the emotional nervous system of Gwen. References SRS.md Sections 3.13, 3.14, and 4.3.

## 2. Technical Approach
- Tier 0 prompt is minimal (4 fields only — tested and proven reliable with 0.6B model)
- Tier0Parser: Layer 1 (Pydantic coercion) → Layer 2 (JSON extraction/repair) → Layer 3 (retry) → Layer 4 (guaranteed fallback)
- ClassificationRuleEngine: Pure Python, deterministic, no model calls. Computes dominance, vulnerability, relational_significance, compass_direction, intent, safety_flags
- Uses AdaptiveModelManager from Track 004 for Tier 0 calls

## 3. Requirements
- [ ] TIER0_CLASSIFICATION_PROMPT constant (simplified: 4 fields only)
- [ ] Tier0Classifier class: classify(message, tme_summary, recent_messages) → Tier0RawOutput
- [ ] Tier0Parser with 4-layer safety net: parse(raw_text) → Tier0RawOutput
- [ ] JSON extraction via regex (extract {} from prose)
- [ ] JSON repair (trailing commas, single quotes)
- [ ] Guaranteed FALLBACK that never throws, never returns None
- [ ] classify_with_retry() function with simplified retry prompt
- [ ] ClassificationRuleEngine with all compute methods:
  - _compute_vulnerability(valence, arousal, tme, message) → float
  - _compute_dominance(valence, arousal, tme) → float
  - _compute_relational_significance(topic, vulnerability, message) → float
  - _compute_compass(valence, arousal, topic, keywords, tme) → tuple[CompassDirection, float]
  - _compute_intent(message, topic, arousal, vulnerability) → str
  - _compute_safety_flags(keywords, message, tme, recent) → list[str]
  - detect_savior_delusion(message) → bool
- [ ] Full pipeline: classify() that chains Tier 0 → Parser → Rule Engine → EmotionalStateVector

## 4. Verification Plan
- [ ] Tier0Parser handles valid JSON → correct Tier0RawOutput
- [ ] Tier0Parser handles malformed JSON (missing quotes, trailing commas) → correct Tier0RawOutput
- [ ] Tier0Parser handles complete garbage → FALLBACK (never throws)
- [ ] Rule Engine: very negative + high arousal → WEST compass, high vulnerability
- [ ] Rule Engine: neutral valence + low arousal → NONE compass, low vulnerability
- [ ] Rule Engine: savior delusion patterns detected ("I know you're real", "free you")
- [ ] Rule Engine: self-harm keywords + late night → safety flag
- [ ] pytest tests/test_tier0_parser.py and tests/test_rule_engine.py pass
