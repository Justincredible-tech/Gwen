# Spec: Temporal Intelligence & Autonomy Engine

## 1. Context & Goal
Build the remaining temporal senses (circadian deviation, conversation rhythm, life rhythm, anniversary awareness) and the Autonomy Engine (background trigger evaluation, "should I speak?" decision model). Plus standard and deep consolidation pipelines. References SRS.md Sections 7 and 12.

## 2. Technical Approach
- Circadian deviation: compare current time to 30-day rolling baseline
- Conversation rhythm: track message density and latency within sessions
- Life rhythm: build day-of-week emotional profiles after 4+ weeks
- Anniversary: store dates in Map, detect proximity
- Autonomy: background async loop evaluating trigger conditions
- Consolidation: standard (6-12hr idle) and deep (weekly) using Tier 2

## 3. Requirements
- [x] CircadianDeviationDetector: compute deviation from baseline
- [x] ConversationRhythmTracker: message density, latency anomalies
- [x] LifeRhythmDetector: weekly emotional shapes, monthly patterns
- [x] AnniversaryDetector: date proximity, automatic safety elevation
- [x] AutonomyEngine: background trigger evaluation loop
- [x] TriggerEvaluator: time-based, pattern-based, emotional, goal-based, safety triggers
- [x] "Should I speak?" decision model
- [x] StandardConsolidation: entity extraction, baseline updates, trigger map updates
- [x] DeepConsolidation: pattern analysis, anticipatory primes, anniversary detection

## 4. Verification Plan
- [x] Circadian deviation correctly flags unusual hours
- [x] Rhythm tracker detects acceleration/deceleration
- [x] Autonomy engine evaluates triggers correctly
- [x] "Should I speak?" respects quiet hours and relational state
- [x] Consolidation creates Map entities from conversation data
- [x] pytest tests pass
