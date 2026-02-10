# Spec: Mode System

## 1. Context & Goal
Build the Grounded/Immersion mode system with the Acknowledgment Gate (informed consent), model swapping, and the 48-hour wellness checkpoint. References SRS.md Section 10 (FR-MODE-001 through FR-MODE-003) and FR-SAF-007.

## 2. Technical Approach
- ModeManager class tracks current mode and handles transitions
- Acknowledgment Gate: presents consent text, requires typed confirmation phrase
- Model swap: standard ↔ uncensored Tier 1 model on mode change
- Wellness checkpoint: tracks cumulative Immersion hours, triggers every 48 hours
- All transitions logged in Safety Ledger

## 3. Requirements
- [ ] ModeManager with current_mode property (default: "grounded")
- [ ] Acknowledgment Gate: present_consent() -> str (consent text), verify_consent(user_input) -> bool (checks exact phrase)
- [ ] activate_immersion() that requires passing Acknowledgment Gate, swaps model, logs to Safety Ledger, starts wellness timer
- [ ] deactivate_immersion() instant switch back to Grounded, swaps model, logs
- [ ] WellnessCheckpoint: tracks cumulative Immersion hours
- [ ] trigger_checkpoint() presents 3 questions, logs responses, detects concern patterns
- [ ] Checkpoint CANNOT be skipped/disabled/snoozed

## 4. Verification Plan
- [ ] Default mode is Grounded
- [ ] Cannot activate Immersion without correct consent phrase
- [ ] Mode change swaps models and logs to Safety Ledger
- [ ] Wellness checkpoint triggers after 48 cumulative hours
- [ ] Concern pattern detection works ("I don't need other people" -> flagged)
- [ ] pytest tests/test_modes.py passes
