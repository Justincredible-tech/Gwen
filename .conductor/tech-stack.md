# Tech Stack

## Runtime

| Technology | Version | Purpose | Install |
|-----------|---------|---------|---------|
| Python | 3.11+ | All application logic | System install or pyenv |
| asyncio | stdlib | Concurrent operations, background processing | Built-in |
| Ollama | latest | Local LLM hosting, model management, embedding API | https://ollama.ai |

## Models (via Ollama)

| Model | Size | Role | Install |
|-------|------|------|---------|
| qwen3:0.6b | ~400MB | Tier 0: Router, classifier, safety keywords | `ollama pull qwen3:0.6b` |
| qwen3:8b | ~5GB | Tier 1: Primary conversation (Grounded Mode) | `ollama pull qwen3:8b` |
| qwen3-coder:30b | ~18GB | Tier 2: Complex reasoning, consolidation | `ollama pull qwen3-coder:30b` |
| qwen3-embedding:0.6b | ~400MB | Semantic embeddings (1024-dim) | `ollama pull qwen3-embedding:0.6b` |

**Note:** Not all models need to be installed. The Adaptive Profile System detects hardware and only uses models that fit. At minimum, only `qwen3:0.6b` and `qwen3-embedding:0.6b` are needed (Pocket profile).

## Python Dependencies

| Package | Version | Purpose | Install |
|---------|---------|---------|---------|
| pydantic | >=2.0 | Data validation, Tier0RawOutput parsing, field coercion | `pip install pydantic` |
| chromadb | >=0.4.0 | Vector storage for semantic + emotional embeddings | `pip install chromadb` |
| networkx | >=3.0 | Knowledge graph (The Map) | `pip install networkx` |
| cryptography | >=41.0 | Fernet encryption for Safety Ledger | `pip install cryptography` |
| pyyaml | >=6.0 | Personality module loading | `pip install pyyaml` |
| pytest | >=7.0 | Testing | `pip install pytest` |
| pytest-asyncio | >=0.21 | Async test support | `pip install pytest-asyncio` |

## Future Dependencies (not needed yet)

| Package | Purpose | Phase |
|---------|---------|-------|
| whisper (openai-whisper) | Speech-to-text | Phase 5 (Voice) |
| piper-tts | Text-to-speech | Phase 5 (Voice) |

## Anti-Hallucination Rule

**Do NOT use any library not listed above.** If you need a new dependency, add it to this file FIRST with justification, then use it.
