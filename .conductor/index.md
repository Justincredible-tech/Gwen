# File Index

Maps logical names to physical file paths. Updated as files are created.

## Project Root
| Logical Name | Path | Track |
|-------------|------|-------|
| pyproject.toml | `pyproject.toml` | 001 |
| README | `README.md` | 001 |
| SRS | `SRS.md` | pre-existing |
| Gwenifesto | `GWENIFESTO_final.md` | pre-existing |
| Memory Architecture | `GWEN_MEMORY_ARCHITECTURE.md` | pre-existing |
| Temporal Cognition | `GWEN_TEMPORAL_COGNITION.md` | pre-existing |
| Compass Framework | `COMPASS_FRAMEWORK_final.md` | pre-existing |
| Conductor Planning | `conductorPlanning.md` | pre-existing |

## Package: gwen/
| Logical Name | Path | Track |
|-------------|------|-------|
| Package init | `gwen/__init__.py` | 001 |
| CLI entry | `gwen/__main__.py` | 008 |

## Models: gwen/models/
| Logical Name | Path | Track |
|-------------|------|-------|
| Models init | `gwen/models/__init__.py` | 002 |
| Emotional models | `gwen/models/emotional.py` | 002 |
| Temporal models | `gwen/models/temporal.py` | 002 |
| Message models | `gwen/models/messages.py` | 002 |
| Memory models | `gwen/models/memory.py` | 002 |
| Safety models | `gwen/models/safety.py` | 002 |
| Personality models | `gwen/models/personality.py` | 002 |
| Classification models | `gwen/models/classification.py` | 002 |
| Reconsolidation models | `gwen/models/reconsolidation.py` | 002 |

## Core: gwen/core/
| Logical Name | Path | Track |
|-------------|------|-------|
| Core init | `gwen/core/__init__.py` | 004 |
| Model Manager | `gwen/core/model_manager.py` | 004 |
| Orchestrator | `gwen/core/orchestrator.py` | 008 |
| Session Manager | `gwen/core/session_manager.py` | 007 |
| Context Assembler | `gwen/core/context_assembler.py` | 010 |
| Post Processor | `gwen/core/post_processor.py` | 011 |

## Classification: gwen/classification/
| Logical Name | Path | Track |
|-------------|------|-------|
| Classification init | `gwen/classification/__init__.py` | 005 |
| Tier 0 caller | `gwen/classification/tier0.py` | 005 |
| Tier 0 parser | `gwen/classification/parser.py` | 005 |
| Rule Engine | `gwen/classification/rule_engine.py` | 005 |

## Memory: gwen/memory/
| Logical Name | Path | Track |
|-------------|------|-------|
| Memory init | `gwen/memory/__init__.py` | 003 |
| Chronicle | `gwen/memory/chronicle.py` | 003 |
| Stream | `gwen/memory/stream.py` | 010 |
| Semantic Map | `gwen/memory/semantic_map.py` | 016 |
| Pulse | `gwen/memory/pulse.py` | 017 |
| Bond | `gwen/memory/bond.py` | 017 |
| Embeddings | `gwen/memory/embeddings.py` | 009 |
| Retrieval | `gwen/memory/retrieval.py` | 013 |
| Palimpsest | `gwen/memory/palimpsest.py` | 018 |

## Temporal: gwen/temporal/
| Logical Name | Path | Track |
|-------------|------|-------|
| Temporal init | `gwen/temporal/__init__.py` | 006 |
| TME Generator | `gwen/temporal/tme.py` | 006 |
| Circadian | `gwen/temporal/circadian.py` | 020 |
| Rhythm | `gwen/temporal/rhythm.py` | 020 |
| Gap Analysis | `gwen/temporal/gap.py` | 007 |
| Life Rhythm | `gwen/temporal/life_rhythm.py` | 020 |

## Amygdala: gwen/amygdala/
| Logical Name | Path | Track |
|-------------|------|-------|
| Amygdala init | `gwen/amygdala/__init__.py` | 013 |
| Amygdala Layer | `gwen/amygdala/layer.py` | 013 |

## Safety: gwen/safety/
| Logical Name | Path | Track |
|-------------|------|-------|
| Safety init | `gwen/safety/__init__.py` | 014 |
| Safety Monitor | `gwen/safety/monitor.py` | 014 |
| Safety Ledger | `gwen/safety/ledger.py` | 014 |
| Wellness Checkpoint | `gwen/safety/wellness.py` | 015 |
| Mode Manager | `gwen/safety/modes.py` | 015 |

## Compass: gwen/compass/
| Logical Name | Path | Track |
|-------------|------|-------|
| Compass init | `gwen/compass/__init__.py` | 019 |
| Compass Classifier | `gwen/compass/classifier.py` | 019 |
| Compass Skills | `gwen/compass/skills.py` | 019 |
| Compass Tracker | `gwen/compass/tracker.py` | 019 |

## Autonomy: gwen/autonomy/
| Logical Name | Path | Track |
|-------------|------|-------|
| Autonomy init | `gwen/autonomy/__init__.py` | 020 |
| Triggers | `gwen/autonomy/triggers.py` | 020 |
| Decision | `gwen/autonomy/decision.py` | 020 |

## Consolidation: gwen/consolidation/
| Logical Name | Path | Track |
|-------------|------|-------|
| Consolidation init | `gwen/consolidation/__init__.py` | 012 |
| Light Consolidation | `gwen/consolidation/light.py` | 012 |
| Standard Consolidation | `gwen/consolidation/standard.py` | 020 |
| Deep Consolidation | `gwen/consolidation/deep.py` | 020 |

## Personality: gwen/personality/
| Logical Name | Path | Track |
|-------------|------|-------|
| Personality init | `gwen/personality/__init__.py` | 008 |
| Personality Loader | `gwen/personality/loader.py` | 008 |
| Prompt Builder | `gwen/personality/prompt_builder.py` | 008 |

## UI: gwen/ui/
| Logical Name | Path | Track |
|-------------|------|-------|
| UI init | `gwen/ui/__init__.py` | 008 |
| CLI | `gwen/ui/cli.py` | 008 |

## Tests: tests/
| Logical Name | Path | Track |
|-------------|------|-------|
| Test config | `tests/conftest.py` | 001 |
| Test models | `tests/test_models.py` | 002 |
| Test parser | `tests/test_tier0_parser.py` | 005 |
| Test rule engine | `tests/test_rule_engine.py` | 005 |
| Test TME | `tests/test_tme.py` | 006 |
| Test session | `tests/test_session.py` | 007 |
| Test chronicle | `tests/test_chronicle.py` | 003 |
| Test embeddings | `tests/test_embeddings.py` | 009 |
| Test context | `tests/test_context.py` | 010 |
| Test amygdala | `tests/test_amygdala.py` | 013 |
| Test safety | `tests/test_safety.py` | 014 |
| Test semantic map | `tests/test_semantic_map.py` | 016 |
| Test palimpsest | `tests/test_palimpsest.py` | 018 |
| Test compass | `tests/test_compass.py` | 019 |
| Test model manager | `tests/test_model_manager.py` | 004 |
| Test orchestrator | `tests/test_orchestrator.py` | 008 |

## Data: data/
| Logical Name | Path | Track |
|-------------|------|-------|
| Gwen personality | `data/personalities/gwen.yaml` | 008 |
