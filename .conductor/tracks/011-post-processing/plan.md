# Plan: Response Post-Processing

**Track:** 011-post-processing
**Spec:** [spec.md](./spec.md)
**Status:** Not Started

---

## Phase 1: Post Processor

### Step 1.1: Create PostProcessor class with constructor

Create the file `gwen/core/post_processor.py` (path: `C:\Users\Administrator\Desktop\projects\Gwen\gwen\core\post_processor.py`).

- [ ] Write PostProcessor class with __init__

```python
"""Response Post-Processing: Phase 7 of the message lifecycle.

After Tier 1 generates a response, the PostProcessor:
1. Classifies the companion's response emotionally (Tier 0 + Rule Engine)
2. Creates a companion MessageRecord
3. Stores both user and companion messages in Chronicle (SQLite)
4. Adds both messages to the Stream (working memory)
5. Updates session statistics
6. Generates embeddings for both messages (async, non-blocking)

This ensures every message in the system has full emotional metadata,
is persisted, and is indexed for future retrieval.

References: SRS.md Section 4.7.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from gwen.classification.tier0 import Tier0Classifier
    from gwen.classification.rule_engine import ClassificationRuleEngine
    from gwen.memory.embeddings import EmbeddingService
    from gwen.memory.stream import Stream
    from gwen.models.emotional import EmotionalStateVector
    from gwen.models.message import MessageRecord
    from gwen.models.temporal import TemporalMetadataEnvelope

logger = logging.getLogger(__name__)


class PostProcessor:
    """Handles Phase 7 of the message lifecycle: response post-processing.

    After Tier 1 generates a response text, the PostProcessor performs all
    the bookkeeping steps: emotional tagging of the response, storage in
    Chronicle, Stream update, session stat tracking, and async embedding
    generation.

    Usage:
        post_processor = PostProcessor(
            tier0_classifier=tier0,
            rule_engine=rule_engine,
            chronicle=chronicle,
            embedding_service=embedding_service,
            stream=stream,
            session_manager=session_manager,
        )

        companion_message = await post_processor.process(
            user_message=user_msg,
            response_text="I'm glad to hear that!",
            tme=tme,
        )
    """

    def __init__(
        self,
        tier0_classifier: object,
        rule_engine: object,
        chronicle: object,
        embedding_service: object,
        stream: object,
        session_manager: object,
    ):
        """Initialize the PostProcessor.

        All parameters are passed as objects (not imported types) to avoid
        circular imports. The PostProcessor uses duck typing to call methods
        on each dependency.

        Args:
            tier0_classifier: A Tier0Classifier instance (from Track 005).
                              Must have an async classify(text, tme_summary, recent_messages)
                              method that returns a Tier0RawOutput.
            rule_engine: A ClassificationRuleEngine instance (from Track 005).
                         Must have a classify(tier0_output, tme, message_text) method
                         that returns an EmotionalStateVector.
            chronicle: A Chronicle instance (from Track 003).
                       Must have an insert_message(message: MessageRecord) method.
            embedding_service: An EmbeddingService instance (from Track 009).
                               Must have an async store_embeddings(message) method.
                               Can be None if embeddings are not yet configured,
                               in which case embedding generation is skipped.
            stream: A Stream instance (from Track 010).
                    Must have an add_message(role, content, emotional_state, timestamp)
                    method.
            session_manager: A SessionManager instance (from Track 007).
                             Must have an add_message(message) method that updates
                             session statistics (message counts, latency, topics).
        """
        self.tier0_classifier = tier0_classifier
        self.rule_engine = rule_engine
        self.chronicle = chronicle
        self.embedding_service = embedding_service
        self.stream = stream
        self.session_manager = session_manager
```

**What this does:** Creates the `PostProcessor` class that orchestrates all Phase 7 operations. Each dependency is accepted as a generic `object` and used via duck typing to avoid circular imports. This is consistent with the pattern used in `ContextAssembler` (Track 010). The constructor just stores references; no I/O or computation happens here.

**Why duck typing for dependencies:** The PostProcessor sits at the intersection of many subsystems (Tier 0, Rule Engine, Chronicle, Embedding Service, Stream, Session Manager). Importing all of their concrete types would create a web of circular dependencies. By accepting `object` and using duck typing, we decouple the PostProcessor from the exact implementation of each dependency.

---

### Step 1.2: Implement the process method

Add this method to the `PostProcessor` class in `gwen/core/post_processor.py`, directly after the `__init__` method.

- [ ] Add process method

```python
    async def process(
        self,
        user_message: MessageRecord,
        response_text: str,
        tme: object,
    ) -> MessageRecord:
        """Process a Tier 1 response: tag, store, index, and return.

        This is the main entry point for Phase 7. It performs all post-processing
        steps in the correct order:

        1. Classify the companion's response emotionally (Tier 0 + Rule Engine)
        2. Create a companion MessageRecord
        3. Store user message in Chronicle
        4. Store companion message in Chronicle
        5. Add both to Stream (working memory)
        6. Update session statistics for both messages
        7. Generate embeddings for both (async, non-blocking background task)
        8. Return the companion MessageRecord

        Args:
            user_message: The user's MessageRecord, already fully populated with
                          emotional state, TME, etc. This was created by the
                          orchestrator before Tier 1 generation.
            response_text: The raw text response from Tier 1 (the model's output).
            tme: The TemporalMetadataEnvelope for this message exchange.
                 The same TME is used for both the user message and the companion
                 response (they share temporal context).

        Returns:
            A fully populated companion MessageRecord with emotional tagging,
            IDs, and all metadata. The caller (orchestrator) uses this to
            display the response and track the companion's emotional trajectory.

        Side effects:
            - Both messages stored in Chronicle (SQLite)
            - Both messages added to Stream (working memory)
            - Session statistics updated for both messages
            - Embedding generation task started in background (may complete later)
        """
        start_time = datetime.now()

        # ------------------------------------------------------------------
        # Step 1: Classify the companion's response emotionally
        # ------------------------------------------------------------------
        # We run the response through Tier 0 + Rule Engine just like we do
        # for user messages. This allows the system to track Gwen's emotional
        # trajectory over time, not just the user's.
        companion_emotional_state = await self._classify_response(response_text, tme)

        # ------------------------------------------------------------------
        # Step 2: Create companion MessageRecord
        # ------------------------------------------------------------------
        companion_message = self._create_companion_message(
            response_text=response_text,
            session_id=user_message.session_id,
            tme=tme,
            emotional_state=companion_emotional_state,
        )

        # ------------------------------------------------------------------
        # Step 3: Store user message in Chronicle
        # ------------------------------------------------------------------
        try:
            self.chronicle.insert_message(user_message)
            logger.debug("Stored user message %s in Chronicle", user_message.id)
        except Exception:
            logger.exception("Failed to store user message %s in Chronicle", user_message.id)

        # ------------------------------------------------------------------
        # Step 4: Store companion message in Chronicle
        # ------------------------------------------------------------------
        try:
            self.chronicle.insert_message(companion_message)
            logger.debug("Stored companion message %s in Chronicle", companion_message.id)
        except Exception:
            logger.exception("Failed to store companion message %s in Chronicle", companion_message.id)

        # ------------------------------------------------------------------
        # Step 5: Add both messages to Stream (working memory)
        # ------------------------------------------------------------------
        self.stream.add_message(
            role="user",
            content=user_message.content,
            emotional_state=user_message.emotional_state,
            timestamp=user_message.timestamp,
        )
        self.stream.add_message(
            role="companion",
            content=response_text,
            emotional_state=companion_emotional_state,
            timestamp=companion_message.timestamp,
        )

        # ------------------------------------------------------------------
        # Step 6: Update session statistics
        # ------------------------------------------------------------------
        try:
            self.session_manager.add_message(user_message)
            self.session_manager.add_message(companion_message)
            logger.debug("Session statistics updated for both messages")
        except Exception:
            logger.exception("Failed to update session statistics")

        # ------------------------------------------------------------------
        # Step 7: Generate embeddings (async, non-blocking)
        # ------------------------------------------------------------------
        # Embeddings are generated in a background task so that the response
        # is returned to the user immediately. If embedding generation fails,
        # it is logged but does not affect the conversation.
        if self.embedding_service is not None:
            asyncio.create_task(
                self._generate_embeddings_background([user_message, companion_message])
            )
        else:
            logger.debug("Embedding service not configured, skipping embedding generation")

        # ------------------------------------------------------------------
        # Step 8: Log timing and return
        # ------------------------------------------------------------------
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(
            "Post-processing complete for exchange in session %s (%.1fms). "
            "User msg: %s, Companion msg: %s",
            user_message.session_id,
            elapsed_ms,
            user_message.id,
            companion_message.id,
        )

        return companion_message
```

**What this does:** This is the main method that orchestrates all Phase 7 steps. The steps are:

1. **Classify response emotionally:** Runs Gwen's response through the same Tier 0 + Rule Engine pipeline used for user messages. This gives the companion's response an `EmotionalStateVector`, enabling the system to track Gwen's emotional trajectory over time.

2. **Create companion MessageRecord:** Builds a full `MessageRecord` for the companion's response with a unique ID, emotional state, storage strength, etc.

3-4. **Store in Chronicle:** Persists both the user message and companion message to SQLite. Each insertion is wrapped in try/except so a database error does not crash the conversation.

5. **Update Stream:** Adds both messages to the working memory buffer so they appear in the conversation history for the next turn.

6. **Update session stats:** Tells the SessionManager about both messages so it can track message counts, response latency, and topics.

7. **Generate embeddings:** Fires off a background `asyncio.create_task` to generate semantic and emotional embeddings for both messages. This is non-blocking -- the user sees the response immediately, and embeddings are generated in the background. If the EmbeddingService is `None` (not yet configured), this step is skipped.

8. **Return:** Returns the companion `MessageRecord` to the orchestrator.

---

Now add the helper methods. Add these to the `PostProcessor` class, directly after the `process` method.

- [ ] Add _classify_response helper method

```python
    async def _classify_response(
        self,
        response_text: str,
        tme: object,
    ) -> EmotionalStateVector:
        """Classify the companion's response through Tier 0 + Rule Engine.

        This gives the companion's response an EmotionalStateVector, just like
        user messages get. This enables tracking of the companion's emotional
        trajectory over time.

        Args:
            response_text: The companion's response text from Tier 1.
            tme: The TemporalMetadataEnvelope for this message exchange.

        Returns:
            An EmotionalStateVector for the companion's response.
            On failure, returns a neutral fallback state so the conversation
            does not crash.
        """
        try:
            # Generate a minimal TME summary for the Tier 0 prompt.
            # The TME summary is a one-line string that Tier 0 uses for
            # context-aware classification.
            tme_summary = ""
            try:
                tme_summary = f"{tme.day_of_week} {tme.time_phase.value}"
            except AttributeError:
                pass

            # Get recent messages from the stream for context.
            # We pass up to 3 recent messages so Tier 0 has conversational context.
            recent_messages = []
            try:
                recent = self.stream.get_recent(3)
                recent_messages = [m["content"] for m in recent]
            except (AttributeError, TypeError):
                pass

            # Run Tier 0 classification
            tier0_output = await self.tier0_classifier.classify(
                message=response_text,
                tme_summary=tme_summary,
                recent_messages=recent_messages,
            )

            # Run Rule Engine to compute full EmotionalStateVector
            emotional_state = self.rule_engine.classify(
                tier0_output=tier0_output,
                tme=tme,
                message_text=response_text,
            )

            return emotional_state

        except Exception:
            logger.exception(
                "Failed to classify companion response. Using neutral fallback."
            )
            # Return a neutral fallback. This import is deferred to avoid
            # circular imports at module load time.
            return self._neutral_fallback_state()

    def _neutral_fallback_state(self) -> object:
        """Create a neutral EmotionalStateVector for fallback scenarios.

        This is used when Tier 0 classification fails for any reason.
        The neutral state ensures the conversation can continue without
        emotional metadata, rather than crashing.

        Returns:
            An object with the EmotionalStateVector interface:
            valence=0.5, arousal=0.3, dominance=0.5,
            relational_significance=0.3, vulnerability_level=0.2,
            compass_direction=NONE.
        """
        try:
            from gwen.models.emotional import EmotionalStateVector, CompassDirection
            return EmotionalStateVector(
                valence=0.5,
                arousal=0.3,
                dominance=0.5,
                relational_significance=0.3,
                vulnerability_level=0.2,
                compass_direction=CompassDirection.NONE,
            )
        except ImportError:
            # If the models are not yet available (early development),
            # return a simple namespace object with the same attributes.
            class NeutralState:
                valence = 0.5
                arousal = 0.3
                dominance = 0.5
                relational_significance = 0.3
                vulnerability_level = 0.2
                compass_direction_value = "none"

                @property
                def storage_strength(self):
                    return self.arousal * 0.4 + self.relational_significance * 0.4 + self.vulnerability_level * 0.2

                @property
                def is_flashbulb(self):
                    return False

            return NeutralState()
```

**What `_classify_response` does:** Runs the companion's response through the same classification pipeline used for user messages (Tier 0 + Rule Engine). This gives the response an `EmotionalStateVector`, which enables tracking of the companion's emotional trajectory. If classification fails for any reason (Tier 0 error, Rule Engine error), it falls back to a neutral state so the conversation is never interrupted.

**What `_neutral_fallback_state` does:** Creates a safe, neutral `EmotionalStateVector` when classification fails. It first tries to import the real data model class. If that fails (early development, models not yet complete), it creates a minimal namespace object with the same attribute interface. This double-fallback ensures the PostProcessor works at every stage of development.

---

- [ ] Add _create_companion_message helper method

```python
    def _create_companion_message(
        self,
        response_text: str,
        session_id: str,
        tme: object,
        emotional_state: object,
    ) -> MessageRecord:
        """Create a companion MessageRecord with full metadata.

        Args:
            response_text: The companion's response text from Tier 1.
            session_id: The UUID of the current session.
            tme: The TemporalMetadataEnvelope for this exchange.
            emotional_state: The EmotionalStateVector from _classify_response.

        Returns:
            A fully populated MessageRecord for the companion's response.
        """
        message_id = str(uuid.uuid4())
        now = datetime.now()

        # Extract compass direction safely (duck typing)
        try:
            compass_direction = emotional_state.compass_direction
        except AttributeError:
            try:
                from gwen.models.emotional import CompassDirection
                compass_direction = CompassDirection.NONE
            except ImportError:
                compass_direction = None

        # Extract storage_strength and is_flashbulb safely
        try:
            storage_strength = emotional_state.storage_strength
        except AttributeError:
            storage_strength = 0.3

        try:
            is_flashbulb = emotional_state.is_flashbulb
        except AttributeError:
            is_flashbulb = False

        try:
            from gwen.models.message import MessageRecord
            return MessageRecord(
                id=message_id,
                session_id=session_id,
                timestamp=now,
                sender="companion",
                content=response_text,
                tme=tme,
                emotional_state=emotional_state,
                storage_strength=storage_strength,
                is_flashbulb=is_flashbulb,
                compass_direction=compass_direction,
                compass_skill_used=None,
                semantic_embedding_id=None,
                emotional_embedding_id=None,
            )
        except ImportError:
            # Fallback: create a simple namespace if MessageRecord is not yet available
            class FallbackMessage:
                pass

            msg = FallbackMessage()
            msg.id = message_id
            msg.session_id = session_id
            msg.timestamp = now
            msg.sender = "companion"
            msg.content = response_text
            msg.tme = tme
            msg.emotional_state = emotional_state
            msg.storage_strength = storage_strength
            msg.is_flashbulb = is_flashbulb
            msg.compass_direction = compass_direction
            msg.compass_skill_used = None
            msg.semantic_embedding_id = None
            msg.emotional_embedding_id = None
            return msg
```

**What this does:** Creates a fully populated `MessageRecord` for the companion's response. It tries to import the real `MessageRecord` dataclass from Track 002. If that import fails (models not yet implemented), it falls back to a simple namespace object with the same attributes. All attributes are populated using safe duck typing with fallback defaults.

---

## Phase 2: Async Embedding Task

### Step 2.1: Add background embedding generation method

Add this method to the `PostProcessor` class in `gwen/core/post_processor.py`, directly after the `_create_companion_message` method.

- [ ] Add _generate_embeddings_background method

```python
    async def _generate_embeddings_background(
        self,
        messages: list,
    ) -> None:
        """Generate embeddings for messages in the background.

        This method is called via asyncio.create_task() so it runs concurrently
        with the main conversation loop. The user sees the response immediately;
        embedding generation happens after.

        If any individual embedding fails, the error is logged but does not
        affect other messages or the conversation. This is a best-effort
        operation.

        Args:
            messages: A list of MessageRecord instances to generate embeddings for.
                      Typically contains exactly 2 elements: [user_message, companion_message].
        """
        for message in messages:
            try:
                await self.embedding_service.store_embeddings(message)
                logger.debug(
                    "Embeddings generated for %s message %s",
                    message.sender,
                    message.id,
                )
            except Exception:
                # Log the error but do NOT re-raise. Embedding failures must
                # never crash the conversation or prevent future messages.
                logger.exception(
                    "Failed to generate embeddings for %s message %s. "
                    "The message is still stored in Chronicle but will not "
                    "appear in semantic/emotional search results.",
                    message.sender,
                    message.id,
                )
```

**What this does:** Iterates through the provided messages (typically the user message and companion message from one exchange) and generates embeddings for each. Each message's embedding generation is independent -- if one fails, the other still gets processed. All errors are caught and logged. This method is designed to be called via `asyncio.create_task()` so it runs in the background without blocking the conversation.

**Why individual try/except per message:** If the Ollama server is temporarily unavailable, the first embedding call will fail. But we still want to try the second message -- the server might recover between calls. Wrapping each call individually ensures maximum resilience.

---

## Phase 3: Integration with Orchestrator

### Step 3.1: Update orchestrator to use PostProcessor

This step modifies the existing orchestrator (created in Track 008 at `gwen/core/orchestrator.py`). The following shows the pattern for integrating the PostProcessor into the message lifecycle.

- [ ] Update orchestrator.process_message() to use PostProcessor

**Before (Track 008, simplified orchestrator):**

The Track 008 orchestrator has a simplified inline post-processing step. It looks something like this:

```python
# In orchestrator.py, inside process_message():

# Phase 6: Response generation
response_text = await self.model_manager.generate_tier1(context)

# Phase 7: Post-processing (simplified in Track 008)
# ... inline code to add to stream, maybe store in chronicle ...

return response_text
```

**After (with PostProcessor integration):**

Replace the inline post-processing with a PostProcessor call. In `gwen/core/orchestrator.py`, add the PostProcessor as a dependency and update the `process_message` method.

First, add the PostProcessor to the orchestrator's `__init__`:

```python
# In the Orchestrator.__init__ method, add this parameter:
#     post_processor: PostProcessor

# Store it as an instance variable:
#     self.post_processor = post_processor
```

Then, update the `process_message` method to use it:

```python
    async def process_message(self, user_input: str) -> str:
        """Process a user message through the full lifecycle.

        Phases: 2 (Temporal) -> 3 (Emotional Tagging) -> 4 (Safety) ->
                5 (Context Assembly) -> 6 (Generation) -> 7 (Post-Processing)
        """
        # Phase 2: Temporal wrapping
        tme = self.tme_generator.generate(session=self.session)

        # Phase 3: Emotional tagging (Tier 0 + Rule Engine)
        emotional_state = await self.tier0_classifier.classify(
            message=user_input,
            tme_summary=f"{tme.day_of_week} {tme.time_phase.value}",
            recent_messages=[m["content"] for m in self.stream.get_recent(5)],
        )
        full_state = self.rule_engine.classify(
            tier0_output=emotional_state,
            tme=tme,
            message_text=user_input,
        )

        # Create user message record
        user_message = self._create_user_message(user_input, tme, full_state)

        # Phase 4: Safety check (placeholder, implemented in Track 014)
        safety_result = None

        # Phase 5: Context assembly
        context = await self.context_assembler.assemble(
            message=user_message,
            tme=tme,
            session=self.session,
            safety_result=safety_result,
        )

        # Phase 6: Response generation
        response_text = await self.model_manager.generate_tier1(context)

        # Phase 7: Post-processing (NEW: uses PostProcessor)
        companion_message = await self.post_processor.process(
            user_message=user_message,
            response_text=response_text,
            tme=tme,
        )

        return response_text
```

**What changed:** The inline post-processing code is replaced with a single `await self.post_processor.process()` call. The PostProcessor now handles all Phase 7 responsibilities: emotional tagging of the response, Chronicle storage, Stream updates, session stat tracking, and async embedding generation. The orchestrator becomes simpler and each responsibility is in the right place.

**Note:** The exact code in `orchestrator.py` depends on what was implemented in Track 008. The pattern above shows the integration point. Adapt the specific parameter names and flow to match the Track 008 implementation.

---

## Phase 4: Tests

### Step 4.1: Create tests/test_post_processing.py

Create the file `tests/test_post_processing.py` (path: `C:\Users\Administrator\Desktop\projects\Gwen\tests\test_post_processing.py`).

- [ ] Write test file for PostProcessor

```python
"""Tests for the PostProcessor (Phase 7 of the message lifecycle).

Tests verify:
- Both user and companion messages are stored in Chronicle
- Companion response gets emotional tags
- Session statistics are updated for both messages
- Stream contains both messages after processing
- Embedding generation is triggered (async)
- Graceful fallback when classification fails

Run: pytest tests/test_post_processing.py -v
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from gwen.core.post_processor import PostProcessor
from gwen.memory.stream import Stream


# ---------------------------------------------------------------------------
# Stub types for testing (self-contained, no dependency on Track 002)
# ---------------------------------------------------------------------------

class CompassDirection(Enum):
    NONE = "none"
    NORTH = "presence"
    SOUTH = "currents"
    WEST = "anchoring"
    EAST = "bridges"


class TimePhase(Enum):
    EVENING = "evening"


class CircadianDeviationSeverity(Enum):
    NONE = "none"


@dataclass
class FakeEmotionalStateVector:
    valence: float = 0.5
    arousal: float = 0.5
    dominance: float = 0.5
    relational_significance: float = 0.5
    vulnerability_level: float = 0.5
    compass_direction: CompassDirection = CompassDirection.NONE
    compass_confidence: float = 0.0

    @property
    def storage_strength(self) -> float:
        return self.arousal * 0.4 + self.relational_significance * 0.4 + self.vulnerability_level * 0.2

    @property
    def is_flashbulb(self) -> bool:
        return self.arousal > 0.8 and self.relational_significance > 0.8


@dataclass
class FakeTME:
    day_of_week: str = "Tuesday"
    time_phase: TimePhase = TimePhase.EVENING
    hour_of_day: int = 19
    session_duration_sec: int = 600
    msg_index_in_session: int = 5
    circadian_deviation_severity: CircadianDeviationSeverity = CircadianDeviationSeverity.NONE


@dataclass
class FakeMessageRecord:
    id: str = ""
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    sender: str = "user"
    content: str = ""
    tme: object = None
    emotional_state: FakeEmotionalStateVector = field(default_factory=FakeEmotionalStateVector)
    storage_strength: float = 0.5
    is_flashbulb: bool = False
    compass_direction: CompassDirection = CompassDirection.NONE
    compass_skill_used: Optional[str] = None
    semantic_embedding_id: Optional[str] = None
    emotional_embedding_id: Optional[str] = None


@dataclass
class FakeTier0Output:
    """Stub for Tier0RawOutput."""
    valence: str = "neutral"
    arousal: str = "moderate"
    topic: str = "general"
    safety_keywords: list = field(default_factory=list)


def make_user_message(content: str = "How are you doing?") -> FakeMessageRecord:
    """Factory to create a user FakeMessageRecord with sensible defaults."""
    return FakeMessageRecord(
        id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        timestamp=datetime.now(),
        sender="user",
        content=content,
        tme=FakeTME(),
        emotional_state=FakeEmotionalStateVector(
            valence=0.65, arousal=0.45, dominance=0.50,
            relational_significance=0.70, vulnerability_level=0.30,
        ),
        storage_strength=0.5,
        is_flashbulb=False,
        compass_direction=CompassDirection.NONE,
    )


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------

def make_mock_tier0():
    """Create a mock Tier0Classifier that returns a FakeTier0Output."""
    mock = AsyncMock()
    mock.classify = AsyncMock(return_value=FakeTier0Output())
    return mock


def make_mock_rule_engine(emotional_state: FakeEmotionalStateVector | None = None):
    """Create a mock ClassificationRuleEngine that returns an EmotionalStateVector."""
    mock = MagicMock()
    if emotional_state is None:
        emotional_state = FakeEmotionalStateVector(
            valence=0.6, arousal=0.4, dominance=0.5,
            relational_significance=0.5, vulnerability_level=0.3,
            compass_direction=CompassDirection.NONE,
        )
    mock.classify = MagicMock(return_value=emotional_state)
    return mock


def make_mock_chronicle():
    """Create a mock Chronicle with an insert_message method."""
    mock = MagicMock()
    mock.insert_message = MagicMock()
    return mock


def make_mock_embedding_service():
    """Create a mock EmbeddingService with an async store_embeddings method."""
    mock = AsyncMock()
    mock.store_embeddings = AsyncMock()
    return mock


def make_mock_session_manager():
    """Create a mock SessionManager with an add_message method."""
    mock = MagicMock()
    mock.add_message = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def stream():
    """Create a fresh Stream for each test."""
    return Stream(max_messages=50)


@pytest.fixture
def post_processor(stream):
    """Create a PostProcessor with all mocked dependencies."""
    return PostProcessor(
        tier0_classifier=make_mock_tier0(),
        rule_engine=make_mock_rule_engine(),
        chronicle=make_mock_chronicle(),
        embedding_service=make_mock_embedding_service(),
        stream=stream,
        session_manager=make_mock_session_manager(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPostProcessorProcess:
    """Tests for PostProcessor.process() — the main Phase 7 method."""

    async def test_returns_companion_message(self, post_processor):
        """process() should return a MessageRecord-like object for the companion."""
        user_msg = make_user_message("Hello there!")
        tme = FakeTME()

        result = await post_processor.process(user_msg, "Hi! How are you?", tme)

        assert result is not None
        assert result.sender == "companion"
        assert result.content == "Hi! How are you?"
        assert result.id  # Should have a UUID
        assert result.session_id == user_msg.session_id

    async def test_companion_gets_emotional_tags(self, post_processor):
        """The companion message should have an emotional state from classification."""
        user_msg = make_user_message()
        tme = FakeTME()

        result = await post_processor.process(user_msg, "I'm doing great!", tme)

        assert result.emotional_state is not None
        assert hasattr(result.emotional_state, "valence")
        assert hasattr(result.emotional_state, "arousal")

    async def test_both_messages_stored_in_chronicle(self, post_processor):
        """Both user and companion messages should be stored in Chronicle."""
        user_msg = make_user_message("Tell me something nice")
        tme = FakeTME()

        await post_processor.process(user_msg, "You're wonderful!", tme)

        chronicle = post_processor.chronicle
        assert chronicle.insert_message.call_count == 2

        # First call should be the user message
        first_call_msg = chronicle.insert_message.call_args_list[0][0][0]
        assert first_call_msg.sender == "user"
        assert first_call_msg.content == "Tell me something nice"

        # Second call should be the companion message
        second_call_msg = chronicle.insert_message.call_args_list[1][0][0]
        assert second_call_msg.sender == "companion"
        assert second_call_msg.content == "You're wonderful!"

    async def test_both_messages_added_to_stream(self, post_processor, stream):
        """Both user and companion messages should be added to the Stream."""
        user_msg = make_user_message("What's the weather like?")
        tme = FakeTME()

        await post_processor.process(user_msg, "It looks sunny today!", tme)

        assert stream.message_count == 2
        messages = stream.get_recent(2)
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "What's the weather like?"
        assert messages[1]["role"] == "companion"
        assert messages[1]["content"] == "It looks sunny today!"

    async def test_session_stats_updated_for_both(self, post_processor):
        """session_manager.add_message should be called for both messages."""
        user_msg = make_user_message()
        tme = FakeTME()

        await post_processor.process(user_msg, "Response text", tme)

        session_mgr = post_processor.session_manager
        assert session_mgr.add_message.call_count == 2

        # Verify the user message was passed first
        first_call_msg = session_mgr.add_message.call_args_list[0][0][0]
        assert first_call_msg.sender == "user"

        # Verify the companion message was passed second
        second_call_msg = session_mgr.add_message.call_args_list[1][0][0]
        assert second_call_msg.sender == "companion"

    async def test_embedding_generation_triggered(self, post_processor):
        """Embedding generation should be triggered as a background task."""
        user_msg = make_user_message()
        tme = FakeTME()

        await post_processor.process(user_msg, "Response", tme)

        # Give the background task a moment to start
        await asyncio.sleep(0.1)

        embed_svc = post_processor.embedding_service
        # store_embeddings should be called for both messages
        assert embed_svc.store_embeddings.call_count == 2

    async def test_embedding_skipped_when_service_is_none(self, stream):
        """If embedding_service is None, embedding generation should be skipped."""
        pp = PostProcessor(
            tier0_classifier=make_mock_tier0(),
            rule_engine=make_mock_rule_engine(),
            chronicle=make_mock_chronicle(),
            embedding_service=None,  # No embedding service
            stream=stream,
            session_manager=make_mock_session_manager(),
        )

        user_msg = make_user_message()
        tme = FakeTME()

        # Should not raise even though embedding_service is None
        result = await pp.process(user_msg, "Response", tme)
        assert result is not None
        assert result.sender == "companion"

    async def test_tier0_classification_called_for_response(self, post_processor):
        """Tier 0 should classify the companion's response text."""
        user_msg = make_user_message()
        tme = FakeTME()

        await post_processor.process(user_msg, "I hear you and I care.", tme)

        tier0 = post_processor.tier0_classifier
        tier0.classify.assert_called_once()
        call_kwargs = tier0.classify.call_args
        # The first positional arg or the 'message' kwarg should be the response text
        assert "I hear you and I care." in str(call_kwargs)

    async def test_rule_engine_called_for_response(self, post_processor):
        """Rule Engine should process the Tier 0 output for the companion response."""
        user_msg = make_user_message()
        tme = FakeTME()

        await post_processor.process(user_msg, "Response text", tme)

        rule_engine = post_processor.rule_engine
        rule_engine.classify.assert_called_once()


class TestPostProcessorResilience:
    """Tests for graceful failure handling in the PostProcessor."""

    async def test_chronicle_failure_does_not_crash(self, stream):
        """If Chronicle insert fails, the conversation should continue."""
        chronicle = make_mock_chronicle()
        chronicle.insert_message.side_effect = Exception("Database error")

        pp = PostProcessor(
            tier0_classifier=make_mock_tier0(),
            rule_engine=make_mock_rule_engine(),
            chronicle=chronicle,
            embedding_service=make_mock_embedding_service(),
            stream=stream,
            session_manager=make_mock_session_manager(),
        )

        user_msg = make_user_message()
        tme = FakeTME()

        # Should NOT raise despite Chronicle failure
        result = await pp.process(user_msg, "Response despite error", tme)
        assert result is not None
        assert result.content == "Response despite error"

    async def test_session_manager_failure_does_not_crash(self, stream):
        """If SessionManager update fails, the conversation should continue."""
        session_mgr = make_mock_session_manager()
        session_mgr.add_message.side_effect = Exception("Session error")

        pp = PostProcessor(
            tier0_classifier=make_mock_tier0(),
            rule_engine=make_mock_rule_engine(),
            chronicle=make_mock_chronicle(),
            embedding_service=make_mock_embedding_service(),
            stream=stream,
            session_manager=session_mgr,
        )

        user_msg = make_user_message()
        tme = FakeTME()

        # Should NOT raise despite session manager failure
        result = await pp.process(user_msg, "Response", tme)
        assert result is not None

    async def test_classification_failure_uses_neutral_fallback(self, stream):
        """If Tier 0 classification fails, a neutral emotional state is used."""
        tier0 = make_mock_tier0()
        tier0.classify.side_effect = Exception("Model error")

        pp = PostProcessor(
            tier0_classifier=tier0,
            rule_engine=make_mock_rule_engine(),
            chronicle=make_mock_chronicle(),
            embedding_service=make_mock_embedding_service(),
            stream=stream,
            session_manager=make_mock_session_manager(),
        )

        user_msg = make_user_message()
        tme = FakeTME()

        result = await pp.process(user_msg, "Response", tme)

        # Should have a neutral emotional state (fallback)
        assert result is not None
        assert result.emotional_state is not None
        assert hasattr(result.emotional_state, "valence")
        # Neutral fallback values
        assert result.emotional_state.valence == 0.5
        assert result.emotional_state.arousal == 0.3

    async def test_embedding_failure_does_not_crash(self, stream):
        """If embedding generation fails, the conversation should continue."""
        embed_svc = make_mock_embedding_service()
        embed_svc.store_embeddings.side_effect = Exception("Embedding error")

        pp = PostProcessor(
            tier0_classifier=make_mock_tier0(),
            rule_engine=make_mock_rule_engine(),
            chronicle=make_mock_chronicle(),
            embedding_service=embed_svc,
            stream=stream,
            session_manager=make_mock_session_manager(),
        )

        user_msg = make_user_message()
        tme = FakeTME()

        # Should NOT raise despite embedding failure
        result = await pp.process(user_msg, "Response", tme)
        assert result is not None

        # Give background task time to complete (and fail gracefully)
        await asyncio.sleep(0.1)


class TestBackgroundEmbeddingGeneration:
    """Tests for _generate_embeddings_background specifically."""

    async def test_processes_all_messages(self):
        """Should call store_embeddings for each message in the list."""
        embed_svc = make_mock_embedding_service()
        pp = PostProcessor(
            tier0_classifier=make_mock_tier0(),
            rule_engine=make_mock_rule_engine(),
            chronicle=make_mock_chronicle(),
            embedding_service=embed_svc,
            stream=Stream(),
            session_manager=make_mock_session_manager(),
        )

        msg1 = make_user_message("First")
        msg2 = FakeMessageRecord(
            id=str(uuid.uuid4()),
            session_id=msg1.session_id,
            sender="companion",
            content="Second",
        )

        await pp._generate_embeddings_background([msg1, msg2])

        assert embed_svc.store_embeddings.call_count == 2

    async def test_one_failure_does_not_stop_others(self):
        """If one embedding fails, the other should still be processed."""
        embed_svc = make_mock_embedding_service()
        # First call raises, second succeeds
        embed_svc.store_embeddings.side_effect = [
            Exception("First failed"),
            None,  # Second succeeds
        ]

        pp = PostProcessor(
            tier0_classifier=make_mock_tier0(),
            rule_engine=make_mock_rule_engine(),
            chronicle=make_mock_chronicle(),
            embedding_service=embed_svc,
            stream=Stream(),
            session_manager=make_mock_session_manager(),
        )

        msg1 = make_user_message("First")
        msg2 = FakeMessageRecord(
            id=str(uuid.uuid4()),
            session_id=msg1.session_id,
            sender="companion",
            content="Second",
        )

        # Should NOT raise despite first failure
        await pp._generate_embeddings_background([msg1, msg2])

        # Both should have been attempted
        assert embed_svc.store_embeddings.call_count == 2
```

**What this file does:** Provides comprehensive tests for the `PostProcessor`. Tests are organized into three groups:

1. **`TestPostProcessorProcess`**: Tests the happy path -- both messages stored, emotional tags applied, stream updated, session stats tracked, embeddings triggered.

2. **`TestPostProcessorResilience`**: Tests graceful degradation -- Chronicle failures, SessionManager failures, classification failures, and embedding failures all handled without crashing the conversation.

3. **`TestBackgroundEmbeddingGeneration`**: Tests the async embedding background task -- all messages processed, individual failures do not stop other messages.

All tests use mocks (from `unittest.mock`) for the dependencies, so no real database, Ollama server, or other infrastructure is needed.

---

### Step 4.2: Run pytest

Run this command from the project root (`C:\Users\Administrator\Desktop\projects\Gwen\`):

- [ ] Run `pytest tests/test_post_processing.py -v` and confirm all tests pass

```bash
pytest tests/test_post_processing.py -v
```

**Expected output:** All tests pass. There should be approximately 15-18 tests.

**If it fails:**
- If `ModuleNotFoundError: No module named 'gwen.core.post_processor'`: Verify that `gwen/core/post_processor.py` exists and `gwen/core/__init__.py` exists.
- If `ModuleNotFoundError: No module named 'gwen.memory.stream'`: The Stream module from Track 010 must be implemented first.
- If async tests hang: Verify `asyncio_mode = "auto"` is set in `pyproject.toml` (from Track 001).
- If `asyncio.create_task` tests fail with "no running event loop": Ensure pytest-asyncio >= 0.21 is installed and `asyncio_mode = "auto"` is configured.

---

## Summary of Files Created

| Step | File Path | Purpose |
|------|-----------|---------|
| 1.1-2.1 | `gwen/core/post_processor.py` | PostProcessor class with all methods |
| 3.1 | `gwen/core/orchestrator.py` | Updated orchestrator integration (modification, not new file) |
| 4.1 | `tests/test_post_processing.py` | Unit tests for PostProcessor |

**Total new files:** 2 (post_processor.py, test_post_processing.py)
**Modified files:** 1 (orchestrator.py -- add PostProcessor integration)
**Dependencies added:** 0

**Dependency chain:** This track depends on:
- Track 003 (Chronicle) for message storage
- Track 005 (Tier 0 + Rule Engine) for emotional classification
- Track 007 (Session Manager) for session statistics
- Track 009 (Embedding Service) for embedding generation
- Track 010 (Stream) for working memory
