# Spec: Database Layer

## 1. Context & Goal
Set up SQLite for the Chronicle (episodic memory) and ChromaDB for vector embeddings. These are the persistence foundations that every memory tier builds on. References SRS.md Section 6 FR-MEM-002.

## 2. Technical Approach
- SQLite via Python's built-in sqlite3 module (no ORM)
- ChromaDB PersistentClient for vector storage
- NetworkX graph serialized to JSON for the Map
- All database files stored in a configurable data directory (~/.gwen/data/)

## 3. Requirements
- [ ] SQLite schema: messages table with all MessageRecord columns
- [ ] SQLite schema: sessions table with all SessionRecord columns
- [ ] Indexes on messages(session_id), messages(timestamp), messages(sender), sessions(start_time)
- [ ] Chronicle class with insert_message(), get_messages_by_session(), search_messages()
- [ ] ChromaDB initialization with two collections: semantic_embeddings, emotional_embeddings
- [ ] Database initialization function that creates all tables and collections
- [ ] Data directory auto-creation (~/.gwen/data/)

## 4. Verification Plan
- [ ] Insert a MessageRecord, retrieve it, verify all fields match
- [ ] Insert a SessionRecord, retrieve it, verify all fields match
- [ ] Full-text search returns correct messages
- [ ] ChromaDB collections exist and accept dummy vectors
- [ ] pytest tests/test_chronicle.py passes
