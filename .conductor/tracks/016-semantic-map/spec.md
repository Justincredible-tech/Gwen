# Spec: Semantic Map (Knowledge Graph)

## 1. Context & Goal
Build the Map (Tier 3: Semantic Memory) -- a NetworkX knowledge graph that stores entities and relationships extracted from conversations. Entities have bi-temporal validity and emotional weight. References SRS.md Sections 3.5 and FR-MEM-003.

## 2. Technical Approach
- NetworkX directed graph (DiGraph)
- Entities as nodes with MapEntity attributes
- Relationships as edges with MapEdge attributes
- Bi-temporal validity (valid_from, valid_until)
- Persistence via JSON serialization to disk
- Emotional weight from source conversations
- Sensitivity classification based on emotional patterns

## 3. Requirements
- [ ] SemanticMap class wrapping NetworkX DiGraph
- [ ] add_entity(entity: MapEntity) -- add node with all attributes
- [ ] add_edge(edge: MapEdge) -- add edge with all attributes
- [ ] query_related(entity_id, max_depth) -> list[MapEntity] -- BFS traversal
- [ ] invalidate_entity(entity_id, reason) -- set valid_until to now
- [ ] get_sensitive_topics(threshold) -> list[MapEntity]
- [ ] save_to_disk() and load_from_disk() -- JSON serialization
- [ ] get_entity(entity_id) -> MapEntity
- [ ] search_entities(name_query) -> list[MapEntity] -- substring match

## 4. Verification Plan
- [ ] Add entity and retrieve it with all attributes
- [ ] Add edge between entities and traverse
- [ ] BFS finds related entities within max_depth
- [ ] Invalidation sets valid_until
- [ ] Save and load preserves full graph
- [ ] Sensitive topics filtered by threshold
- [ ] pytest tests/test_semantic_map.py passes
