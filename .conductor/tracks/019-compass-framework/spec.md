# Spec: Compass Framework

## 1. Context & Goal
Build the Compass life-coaching framework: direction classification (via Rule Engine), skill selection and delivery (via Tier 1 context injection), and effectiveness tracking. The Compass has 4 directions (NORTH/Presence, SOUTH/Currents, WEST/Anchoring, EAST/Bridges) with 5 skills each (20 total). References SRS.md Section 11 (FR-COMP-001 through FR-COMP-006).

## 2. Technical Approach
- Direction classification already done by ClassificationRuleEngine (Track 005)
- Skill selection: choose the most appropriate skill for the direction + context
- Skill delivery: inject skill description into Tier 1 context via PromptBuilder
- Effectiveness tracking: log usage, measure pre/post emotional trajectory
- Disclaimer calibration: occasionally add natural disclaimers

## 3. Requirements
- [x] CompassSkillRegistry: defines all 20 skills with name, direction, description, prompt injection text
- [x] SkillSelector: select_skill(direction, emotional_state, effectiveness_history) → skill
- [x] Skill delivery: generate prompt section for selected skill
- [x] EffectivenessTracker: log usage, compute effectiveness after session
- [x] Disclaimer calibrator: determine if disclaimer should be added
- [x] Integration: Context assembler injects Compass prompt when direction != NONE

## 4. Verification Plan
- [x] All 20 skills registered with correct directions
- [x] Skill selection returns appropriate skills for each direction
- [x] Prompt injection produces natural-feeling coaching text
- [x] Effectiveness scores computed correctly
- [x] Disclaimer frequency adjusts based on over-reliance signals
- [x] pytest tests/test_compass.py passes
