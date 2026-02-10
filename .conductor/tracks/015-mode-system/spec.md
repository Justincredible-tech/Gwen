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
- [x] ModeManager with current_mode property (default: "grounded")
- [x] Acknowledgment Gate: present_consent() -> str (consent text), verify_consent(user_input) -> bool (checks exact phrase)
- [x] activate_immersion() that requires passing Acknowledgment Gate, swaps model, logs to Safety Ledger, starts wellness timer
- [x] deactivate_immersion() instant switch back to Grounded, swaps model, logs
- [x] WellnessCheckpoint: tracks cumulative Immersion hours
- [x] trigger_checkpoint() presents 3 questions, logs responses, detects concern patterns
- [x] Checkpoint CANNOT be skipped/disabled/snoozed

## 4. Verification Plan
- [x] Default mode is Grounded
- [x] Cannot activate Immersion without correct consent phrase
- [x] Mode change swaps models and logs to Safety Ledger
- [x] Wellness checkpoint triggers after 48 cumulative hours
- [x] Concern pattern detection works ("I don't need other people" -> flagged)
- [x] pytest tests/test_modes.py passes
