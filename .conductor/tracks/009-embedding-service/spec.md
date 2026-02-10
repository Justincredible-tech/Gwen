# Spec: Embedding Service

## 1. Context & Goal
Build the EmbeddingService that generates semantic embeddings via qwen3-embedding:0.6b (1024-dim) and emotional embeddings via direct 5D encoding, and stores both in ChromaDB. This is the foundation for memory retrieval. References SRS.md FR-MEM-006.

## 2. Technical Approach
- Semantic embeddings: call Ollama /api/embed with qwen3-embedding:0.6b model
- Emotional embeddings: direct 5D vector [valence, arousal, dominance, relational_significance, vulnerability_level]
- Store in ChromaDB with metadata (session_id, timestamp, sender, emotional dimensions)
- Async: embedding generation can happen after response is sent to user

## 3. Requirements
- [ ] EmbeddingService class with generate_semantic_embedding(text) -> list[float] (1024-dim)
- [ ] generate_emotional_embedding(state: EmotionalStateVector) -> list[float] (5-dim)
- [ ] store_embeddings(message: MessageRecord) stores both in ChromaDB collections
- [ ] ChromaDB metadata includes session_id, timestamp, sender, valence, arousal, storage_strength, embedding_model
- [ ] Non-blocking embedding generation (async)

## 4. Verification Plan
- [ ] Semantic embedding returns 1024-dim vector
- [ ] Emotional embedding returns 5-dim vector matching EmotionalStateVector dimensions
- [ ] Store and retrieve from ChromaDB works
- [ ] Similarity search returns semantically similar messages
- [ ] pytest tests/test_embeddings.py passes
