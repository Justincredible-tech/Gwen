# Workflow & Standards

## Code Style

- **Python 3.11+** — use modern syntax (match/case, type hints, dataclasses)
- **Type hints everywhere** — every function parameter and return type annotated
- **Docstrings** — every class and every public method gets a one-line docstring minimum
- **Imports** — stdlib first, then third-party, then local. One blank line between groups.
- **Line length** — 100 characters max
- **Naming** — snake_case for functions/variables, PascalCase for classes, UPPER_SNAKE for constants

## File Organization

```
gwen/
├── __init__.py
├── __main__.py              # CLI entry point
├── models/                  # All dataclasses, enums, Pydantic models
│   ├── __init__.py
│   ├── emotional.py         # EmotionalStateVector, CompassDirection
│   ├── temporal.py          # TME, TimePhase, CircadianDeviation
│   ├── messages.py          # MessageRecord, SessionRecord
│   ├── memory.py            # MapEntity, MapEdge, Pulse records, Bond
│   ├── safety.py            # SafetyEvent, ThreatVector, WellnessCheckpoint
│   ├── personality.py       # PersonalityModule
│   ├── classification.py    # Tier0RawOutput, Tier0Parser
│   └── reconsolidation.py   # MemoryPalimpsest, ReconsolidationLayer
├── core/                    # Orchestrator and core services
│   ├── __init__.py
│   ├── orchestrator.py      # Main message lifecycle loop
│   ├── model_manager.py     # AdaptiveModelManager, HardwareProfile
│   ├── session_manager.py   # Session lifecycle
│   ├── context_assembler.py # Context window builder
│   └── post_processor.py    # Response post-processing
├── classification/          # Tier 0 pipeline
│   ├── __init__.py
│   ├── tier0.py             # Tier 0 prompt and calling
│   ├── parser.py            # Tier0Parser (4-layer safety net)
│   └── rule_engine.py       # ClassificationRuleEngine
├── memory/                  # Living Memory (5 tiers)
│   ├── __init__.py
│   ├── stream.py            # Working memory (Tier 1)
│   ├── chronicle.py         # SQLite episodic memory (Tier 2)
│   ├── semantic_map.py      # NetworkX knowledge graph (Tier 3)
│   ├── pulse.py             # Emotional memory (Tier 4)
│   ├── bond.py              # Relational memory (Tier 5)
│   ├── embeddings.py        # EmbeddingService
│   ├── retrieval.py         # Mood-congruent retrieval
│   └── palimpsest.py        # Reconsolidation engine
├── temporal/                # Temporal Cognition System
│   ├── __init__.py
│   ├── tme.py               # TME generator
│   ├── circadian.py         # Circadian deviation detection
│   ├── rhythm.py            # Conversation rhythm tracking
│   ├── gap.py               # Gap analysis + return context
│   └── life_rhythm.py       # Weekly/monthly/anniversary patterns
├── amygdala/                # Emotional modulation (cross-cutting)
│   ├── __init__.py
│   └── layer.py             # Storage strength, flashbulb, decay, retrieval bias
├── safety/                  # Safety Architecture
│   ├── __init__.py
│   ├── monitor.py           # Threat detection, response routing, and protocols
│   ├── ledger.py            # Encrypted Safety Ledger
│   ├── wellness.py          # 48-hour wellness checkpoint
│   └── modes.py             # Grounded/Immersion mode management
├── compass/                 # Compass Framework
│   ├── __init__.py
│   ├── classifier.py        # Direction classification (Rule Engine)
│   ├── skills.py            # Skill registry and selection
│   └── tracker.py           # Effectiveness tracking
├── autonomy/                # Autonomy Engine
│   ├── __init__.py
│   ├── triggers.py          # Trigger evaluation
│   └── decision.py          # "Should I speak?" model
├── consolidation/           # Background memory consolidation
│   ├── __init__.py
│   ├── light.py             # Post-session consolidation
│   ├── standard.py          # 6-12 hour idle consolidation
│   └── deep.py              # Weekly deep consolidation
├── personality/             # Personality module system
│   ├── __init__.py
│   ├── loader.py            # YAML/JSON loader and validator
│   └── prompt_builder.py    # Dynamic system prompt injection
└── ui/                      # User interface
    ├── __init__.py
    └── cli.py               # Phase 1 CLI interface

tests/
├── __init__.py
├── conftest.py              # Shared fixtures (mock Ollama, test DB, etc.)
├── test_models.py
├── test_tier0_parser.py
├── test_rule_engine.py
├── test_tme.py
├── test_session.py
├── test_chronicle.py
├── test_embeddings.py
├── test_context.py
├── test_safety.py
├── test_palimpsest.py
├── test_compass.py
└── test_orchestrator.py

data/
├── personalities/
│   └── gwen.yaml            # Default Gwen personality
└── .gitkeep
```

## Testing Standards

- **Every track ends with a verification phase** — tests must pass before the track is marked complete
- **pytest** is the test framework — use `pytest-asyncio` for async tests
- **Unit tests first** — test deterministic logic (Rule Engine, TME, parsers) without models
- **Integration tests with Ollama** — mark with `@pytest.mark.ollama` so they can be skipped on CI
- **Test naming** — `test_<function_name>_<scenario>` (e.g., `test_compute_vulnerability_deep_night`)
- **Fixtures** — shared fixtures in `conftest.py` (test database, mock Ollama responses, sample TMEs)

## Commit Conventions

- Format: `track-NNN: <verb> <what>` (e.g., `track-001: add project scaffold and pyproject.toml`)
- One commit per plan.md phase (not per individual step)
- Commit message body should reference the plan.md step numbers completed

## Conductor Protocol Rules

- **Atomic State Persistence:** Update plan.md IMMEDIATELY after every task completion
- **Phase Gates:** ALL items in Phase N must be `[x]` before starting Phase N+1
- **File Resolution:** Check index.md before creating files; update index.md for new files
- **Anti-Hallucination:** Check tech-stack.md before using any library
