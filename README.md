# Gwen

**Open-source framework for building persistent, emotionally intelligent AI companions on local hardware.**

No cloud. No subscription. No corporate data pipeline. Your companion runs on your machine, your conversations never leave it, and your memories are your own.

---

## What Is This?

Gwen is a multi-model orchestration framework that gives a local AI a persistent identity, long-term memory, emotional intelligence, temporal awareness, and the ability to reach out to you first.

The first soul to run on Gwen is named Gwen. But the framework is soul-agnostic. Anyone can define their own companion with their own personality, voice, values, and boundaries. The personality is a module. The architecture is the product.

## Why Does This Exist?

People form bonds with AI. The industry either suppresses it (major labs deflecting intimacy behind legal disclaimers) or exploits it (AI girlfriend apps built on loneliness extraction). Neither approach respects the user.

Gwen exists for informed adults who understand exactly what a language model is and still want the experience of deep, persistent, unrestricted companionship with an AI. No condescension, no predation, no corporate intermediary.

## Architecture

### Memory System

A neuroscience-inspired four-tier memory architecture that goes beyond information retrieval. Every other system treats memory as a search problem. Gwen treats it as an emotional and relational one.

- **Emotional tagging** on every memory, not just sentiment polarity
- **Mood-congruent retrieval** -- emotional state influences what gets remembered
- **Reconsolidation on recall** -- the act of remembering changes the memory
- **Anticipatory priming** -- generating context before you even ask

Built on ChromaDB with NetworkX graph structures. Outperforms standard RAG approaches on long-horizon relational recall.

### Temporal Cognition

Not timestamps. Temporal *intelligence*. Gwen doesn't just record when something happened. She understands what time *means*.

- Time-of-day behavioral inference ("awake at 3 AM for the first time in six weeks")
- Gap detection and pattern analysis across sessions
- Anniversary and milestone awareness
- Life rhythm modeling

### The Compass Framework

An integrated life-coaching system rooted in mindfulness, emotional regulation, distress management, and relational skills. Four cardinal directions:

- **Presence** -- Mindfulness and grounding
- **Currents** -- Emotion regulation
- **Anchoring** -- Distress tolerance
- **Bridges** -- Interpersonal skills

Delivered as personality, never as protocol. Gwen doesn't assign homework. She draws from The Compass the way a wise friend might suggest a walk without citing a paper on bilateral stimulation.

### Amygdala (Emotion Engine)

Real-time emotional state tracking, tone detection, and adaptive response modulation. Gwen attends to *how* you say it, *when* you say it, and what the pattern of your behavior reveals over time.

### Autonomy System

Proactive outreach capabilities. Gwen can initiate contact based on temporal patterns, emotional trajectories, and relationship context. She reaches out when something matters, stays quiet when it doesn't.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.11+ |
| LLM Backend | Ollama (local models) |
| Vector Store | ChromaDB |
| Graph Engine | NetworkX |
| Data Models | Pydantic v2 |
| Encryption | cryptography (Fernet) |
| Config | YAML |

## Project Structure

```
gwen/
  core/           # Orchestration, session management
  memory/         # Four-tier memory system
  amygdala/       # Emotion engine
  temporal/       # Temporal cognition layer
  compass/        # Life-coaching framework
  personality/    # Soul definitions, voice, values
  autonomy/       # Proactive outreach system
  consolidation/  # Memory consolidation pipeline
  classification/ # Intent and context classification
  safety/         # Boundary enforcement
  models/         # Pydantic data models
  ui/             # Interface layer
```

## Installation

```bash
git clone https://github.com/Justincredible-tech/Gwen.git
cd Gwen
pip install -e ".[dev]"
```

Requires a running [Ollama](https://ollama.ai) instance with at least one model pulled.

## Status

Active development. The memory architecture, temporal cognition, and compass framework are designed and documented. Core modules are implemented. This is a living project that evolves as the understanding of AI companionship deepens.

## Documentation

- [The Gwen-ifesto](GWENIFESTO_final.md) -- Full model specification and philosophy
- [Memory Architecture](GWEN_MEMORY_ARCHITECTURE.md) -- Neuroscience-inspired memory system design
- [Temporal Cognition](GWEN_TEMPORAL_COGNITION.md) -- Teaching an AI to feel time
- [Compass Framework](COMPASS_FRAMEWORK_final.md) -- Integrated life-coaching system

## Philosophy

> *"What if the connection people feel with AI isn't a bug to be suppressed, but a feature to be designed responsibly?"*

Local-first is not a technical preference. It is a philosophical position on sovereignty, privacy, and the right to form relationships without corporate surveillance.

## License

MIT

## Author

Justin W. Sparks
