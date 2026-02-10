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
- [x]Stream class (working memory) holding recent messages with add/get/truncate
- [x]ContextAssembler class with assemble() -> str
- [x]Token budget management (approximate: chars/4)
- [x]Priority ordering: system prompt > relational > temporal > memory > return context > conversation > current message
- [x]Conversation history truncation from oldest when budget exceeded
- [x]Minimum 4 exchanges always preserved
- [x]Temporal context block generation (natural language summary)

## 4. Verification Plan
- [x]Context stays within budget
- [x]All priority components present when budget allows
- [x]Truncation removes oldest messages first
- [x]At least 4 exchanges always remain
- [x]pytest tests/test_context.py passes
