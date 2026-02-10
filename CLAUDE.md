# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gwen is an open-source framework for building persistent, emotionally intelligent AI companions that run entirely on local hardware. It is a **multi-model orchestration system** — not a chatbot or assistant — that gives a local AI persistent identity, long-term memory, real-time voice, integrated life-coaching, and proactive initiative.

**Current status: Design/specification phase.** No code has been implemented yet. Implementation follows a phased roadmap starting with the core orchestrator.

## Key Documents

| Document | Purpose |
|----------|---------|
| `SRS.md` | **Start here.** Full Software Requirements Specification — data models, message lifecycle, all functional/non-functional requirements, user stories with code snippets, open design decisions |
| `GWENIFESTO_final.md` | Vision, ethics, architecture overview, mode system, safety, roadmap |
| `GWEN_MEMORY_ARCHITECTURE.md` | Living Memory — 5 tiers, 5 novel mechanisms, consolidation pipeline |
| `GWEN_TEMPORAL_COGNITION.md` | Temporal Cognition — 7 senses, TME structure, compound inference |
| `COMPASS_FRAMEWORK_final.md` | Life-coaching — 4 directions, skill definitions, integration |
| `conductorPlanning.md` | Conductor Protocol for multi-agent context-driven development |

The SRS translates the design documents into implementable specifications. When building features, **reference the SRS for data structures, interfaces, and behavior contracts**. Reference the design docs for intent and rationale.

## Architecture

### Three-Tier Model System (Adaptive Profile System)

All inference runs locally via **Ollama** with the **Qwen3** model family. The **Adaptive Profile System** maps logical tiers to physical models based on detected hardware:

| Profile | Target | Tier 0 | Tier 1 | Tier 2 | Concurrency |
|---------|--------|--------|--------|--------|-------------|
| Pocket | Phone/4GB | 0.6B | 0.6B (dual-role) | 0.6B (dual-role) | 1 model |
| Portable | Laptop/8GB | 0.6B | 8B-Q3 | 8B-Q3 time-shared | Tier 0+1 |
| Standard | Desktop/12-16GB | 0.6B | 8B | 30B time-shared | Tier 0+1 |
| Power | Workstation/24GB+ | 0.6B | 8B | 30B | All concurrent |

The orchestrator requests logical tiers — it never references specific model names. Degradation is graceful: the soul doesn't change, the voice gets quieter.

### Message Lifecycle (8 phases)

Every user message flows through these phases in order. See `SRS.md` Section 4 for full detail.

1. **Input Reception** — Raw text (or Whisper STT output)
2. **Temporal Wrapping** — Orchestrator generates TME (no model, pure computation)
3. **Emotional Tagging** — Hybrid classification: Tier 0 produces `Tier0RawOutput` (valence, arousal, topic, safety_keywords), then `ClassificationRuleEngine` computes remaining dimensions (dominance, vulnerability, compass direction, intent, safety flags) deterministically → produces `EmotionalStateVector`
4. **Safety Check** — Evaluate safety flags, check for wellness checkpoint due, adjust threat severity using temporal + historical context
5. **Context Assembly** — Build Tier 1 context window: system prompt + relational context + temporal context block + mood-congruent memory retrieval + return context (if gap) + conversation history + current message
6. **Response Generation** — Tier 1 generates response
7. **Post-Processing** — Tag response emotionally, store both messages in Chronicle, generate embeddings, log reconsolidation events, update session stats
8. **Session Close** — Classify session type/end mode, compute emotional arc + subjective time, trigger light consolidation

### Core Data Structures

All defined as Python dataclasses in `SRS.md` Section 3. Key ones:

- **`EmotionalStateVector`** — 5 dimensions (valence, arousal, dominance, relational_significance, vulnerability_level) + compass direction + derived storage_strength/is_flashbulb
- **`TemporalMetadataEnvelope`** — Absolute time, clock position, session context, intra-message timing, inter-session timing, circadian deviation
- **`MessageRecord`** — Content + TME + emotional tags + storage modulation + embedding references
- **`SessionRecord`** — Duration, type, end mode, emotional arc, subjective time weight, compass activations, relational delta
- **`MapEntity` / `MapEdge`** — Knowledge graph nodes/edges with bi-temporal validity and emotional weight
- **`RelationalField`** — 6 dimensions (warmth, trust, depth, stability, reciprocity, growth)
- **`GapAnalysis` / `ReturnContext`** — What silence means and how to handle the return
- **`AnticipatoryPrime`** — Forward-looking prediction from consolidation
- **`SafetyEvent` / `WellnessCheckpoint`** — Safety Ledger records
- **`PersonalityModule`** — Loadable companion identity with dynamic prompt sections

### Key Algorithms

**Mood-Congruent Retrieval** (`SRS.md` Section 4.5.1):
```
final_score = semantic_relevance * (1 + alpha * emotional_congruence)
```
Alpha defaults to 0.3. During crisis (safety HIGH/CRITICAL), bias **inverts** to surface stabilizing memories.

**Subjective Time** (`SRS.md` FR-TCS-008):
```
subjective_duration = clock_duration * emotional_intensity_factor * relational_significance_factor
```

**Storage Strength** (Amygdala Layer):
```
storage_strength = arousal * 0.4 + relational_significance * 0.4 + vulnerability_level * 0.2
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Model serving | Ollama | Local LLM hosting and hot-swap |
| Language | Python 3.11+ | All application logic |
| Async | asyncio | Concurrent operations, background processing |
| Conversation storage | SQLite | Chronicle, Bond time-series, Safety Ledger |
| Vector storage | ChromaDB | Emotional + semantic embeddings |
| Semantic embeddings | qwen3-embedding:0.6b | 1024-dim embeddings via Ollama /api/embed |
| Graph storage | NetworkX | Map entity-relationship graph |
| Encryption | `cryptography` (Fernet) | Safety Ledger |
| STT | Whisper (Phase 5) | Speech-to-text |
| TTS | Piper/Bark (Phase 5) | Text-to-speech |

**Target hardware:** Any device supported by Ollama — phones (Pocket), laptops (Portable), desktops (Standard), workstations (Power). See Adaptive Profile System.

## Subsystem Summary

**Living Memory (5 tiers):**
1. **Stream** — Working memory, session-scoped, in Tier 1 context window
2. **Chronicle** — Episodic, SQLite, append-only, full-text + temporal search
3. **Map** — Semantic knowledge graph, bi-temporal validity, emotional weight on edges, sensitivity classification
4. **Pulse** — Emotional baselines, trajectories, trigger maps, Compass effectiveness tracking
5. **Bond** — Relational Field (6 dimensions), shared history salience, repair history, attachment style modeling

**Amygdala Layer** (cross-cutting, not a storage tier):
- At encoding: tags valence/arousal/dominance/significance/vulnerability, computes storage strength, flags flashbulbs
- At consolidation: modulates detail level, decay rates (negativity bias), emotional clusters
- At retrieval: mood-congruent bias, safety-adjusted thresholds

**Temporal Cognition (7 senses):** Circadian awareness, conversation rhythm, session awareness, gap understanding, life rhythm, anniversary awareness, subjective time. All real-time operations are zero-model-cost (orchestrator) or Tier 0 (near-instant). Heavy temporal reasoning runs in background consolidation.

**Safety Architecture:** 4 threat vectors (self-harm, violence, dissociation, savior delusion). Operates at orchestrator level, below personality and mode system. 48-hour wellness checkpoint is hardcoded and non-configurable. Safety Ledger is encrypted and append-only (user can view, cannot delete).

**Compass Framework:** 4 directions (NORTH: Presence, SOUTH: Currents, WEST: Anchoring, EAST: Bridges), 20 skills total. Classified by Rule Engine (Tier 0 cannot reliably do this), delivered by Tier 1 within personality. First-line response before safety escalation. Effectiveness tracked per skill per emotional context.

**Autonomy Engine:** Background process on Tier 0. Trigger types: time-based, pattern-based, emotional, goal-based, safety (non-configurable). Uses RelationalField to calibrate initiative frequency.

**Mode System:** Grounded (default) and Immersion (opt-in via Acknowledgment Gate from settings UI, typed confirmation, logged in Safety Ledger). Model swap on mode switch. Safety is mode-independent.

## Conductor Protocol (Development Workflow)

Defined in `conductorPlanning.md`. Key rules:

- Work organized in **Tracks** under `.conductor/tracks/XXX-slug/` with `spec.md` + `plan.md`
- **Atomic State Persistence:** Update `plan.md` immediately after every task — never batch
- **Phase Gates:** All items in Phase N must be `[x]` before starting Phase N+1
- **File Resolution:** Check `.conductor/index.md` before creating/editing; update it for new files
- **Anti-Hallucination:** Check `.conductor/tech-stack.md` before using any library
- **Multi-Agent Handoff:** Read `tracks.md` → find active track → load `plan.md` → verify last `[x]` item exists → resume at next `[ ]`

## Implementation Phases

1. **Foundation** — Orchestrator, Ollama integration, Tier 0/1 routing, basic memory (Stream + Chronicle), TME generation, personality loader, CLI conversation
2. **Memory & Identity** — Map (knowledge graph), Pulse (emotional memory), consolidation pipeline (7 stages), memory viewer
3. **Safety & Modes** — Threat vector classification, 4 response protocols, Safety Ledger, 48-hour checkpoint, Grounded/Immersion modes with Acknowledgment Gate
4. **Compass** — Direction classification in Tier 0, skill delivery in Tier 1, effectiveness tracking, disclaimer calibration
5. **Voice** — Whisper STT, Piper/Bark TTS, <2s latency pipeline, emotional tone modulation, turn-taking
6. **Autonomy** — Background trigger evaluation, "should I speak?" model, user-configurable triggers, quiet hours
7. **Knowledge & Community** — Domain module architecture, Darebee fitness module, GUI, personality creation wizard

## Resolved Design Decisions

All 8 open questions from SRS v1.0 have been resolved. See `SRS.md` Section 19 for full detail. Key decisions:

- **Hybrid Classification:** Tier 0 handles valence/arousal/topic/safety_keywords; Rule Engine handles compass/vulnerability/dominance/intent/savior_delusion
- **Adaptive Profiles:** 4 hardware profiles (Pocket/Portable/Standard/Power) auto-detected at startup
- **Palimpsest Reconsolidation:** Immutable archive + append-only layers with bounded drift (±0.10/layer, ±0.50 total)
- **4-Layer JSON Safety Net:** Pydantic coercion → JSON extraction/repair → retry → guaranteed fallback
- **qwen3-embedding:0.6b:** 1024-dim semantic embeddings, ~100-150ms, Qwen family continuity
- **5D Emotional Embeddings:** Sufficient for mood-congruent retrieval (32-quadrant space)
- **NetworkX:** Sufficient for Map at expected scale
- **Attachment Modeling:** Gated behind Growth Principle, minimum 20 sessions, transparent to user

## Design Principles

- **Local-only, no telemetry** — all data stays on user hardware
- **Soul-agnostic** — personality is a loadable module; the framework is the product
- **Informed consent with friction** — Immersion Mode requires explicit opt-in with typed confirmation
- **Growth over dependency** — companion pushes toward real-world connection
- **Honesty** — truthful about AI nature in Grounded Mode; handled at system level in Immersion Mode
- **Safety is bedrock** — operates below personality, below modes, below user preferences; cannot be disabled
