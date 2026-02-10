# Spec: Context Assembler

## 1. Context & Goal
Build the Context Assembler that constructs the full Tier 1 prompt within a token budget. This includes system prompt, relational context, temporal context block, memory retrieval, return context, conversation history, and the current message. References SRS.md Section 4.5.

## 2. Technical Approach
- Token budget ~6000 tokens (rough estimate: 1 token ~ 4 chars)
- Components assembled in priority order
- Stream (working memory) holds recent conversation
- Memory retrieval placeholder (full mood-congruent retrieval in Track 013)
- Truncation strategy: remove oldest conversation history first

## 3. Requirements
- [ ] Stream class (working memory) holding recent messages with add/get/truncate
- [ ] ContextAssembler class with assemble() -> str
- [ ] Token budget management (approximate: chars/4)
- [ ] Priority ordering: system prompt > relational > temporal > memory > return context > conversation > current message
- [ ] Conversation history truncation from oldest when budget exceeded
- [ ] Minimum 4 exchanges always preserved
- [ ] Temporal context block generation (natural language summary)

## 4. Verification Plan
- [ ] Context stays within budget
- [ ] All priority components present when budget allows
- [ ] Truncation removes oldest messages first
- [ ] At least 4 exchanges always remain
- [ ] pytest tests/test_context.py passes
