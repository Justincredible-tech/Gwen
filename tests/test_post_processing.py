"""Tests for the PostProcessor (Phase 7 of the message lifecycle).

Tests verify:
- Both user and companion messages are stored in Chronicle
- Companion response gets emotional tags
- Session statistics are updated for companion message
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
from unittest.mock import AsyncMock, MagicMock

import pytest

from gwen.core.post_processor import PostProcessor
from gwen.memory.stream import Stream


# ---------------------------------------------------------------------------
# Stub types for testing (self-contained, no dependency on Track 002 models)
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
        return (
            self.arousal * 0.4
            + self.relational_significance * 0.4
            + self.vulnerability_level * 0.2
        )

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
    circadian_deviation_severity: CircadianDeviationSeverity = (
        CircadianDeviationSeverity.NONE
    )


@dataclass
class FakeMessageRecord:
    id: str = ""
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    sender: str = "user"
    content: str = ""
    tme: object = None
    emotional_state: FakeEmotionalStateVector = field(
        default_factory=FakeEmotionalStateVector
    )
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
            valence=0.65,
            arousal=0.45,
            dominance=0.50,
            relational_significance=0.70,
            vulnerability_level=0.30,
        ),
        storage_strength=0.5,
        is_flashbulb=False,
        compass_direction=CompassDirection.NONE,
    )


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------

def make_mock_tier0():
    """Create a mock Tier0Classifier with correct interface."""
    mock = AsyncMock()
    mock.classify = AsyncMock(return_value=FakeTier0Output())
    return mock


def make_mock_rule_engine(
    emotional_state: FakeEmotionalStateVector | None = None,
):
    """Create a mock ClassificationRuleEngine with correct interface."""
    mock = MagicMock()
    if emotional_state is None:
        emotional_state = FakeEmotionalStateVector(
            valence=0.6,
            arousal=0.4,
            dominance=0.5,
            relational_significance=0.5,
            vulnerability_level=0.3,
            compass_direction=CompassDirection.NONE,
        )
    mock.classify = MagicMock(return_value=emotional_state)
    return mock


def make_mock_chronicle():
    """Create a mock Chronicle with insert_message method."""
    mock = MagicMock()
    mock.insert_message = MagicMock()
    return mock


def make_mock_embedding_service():
    """Create a mock EmbeddingService with async store_embeddings method."""
    mock = AsyncMock()
    mock.store_embeddings = AsyncMock()
    return mock


def make_mock_session_manager():
    """Create a mock SessionManager with add_message(sender: str) method."""
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
# Tests: PostProcessor.process() — the main Phase 7 method
# ---------------------------------------------------------------------------

class TestPostProcessorProcess:
    """Tests for the happy path of PostProcessor.process()."""

    async def test_returns_companion_message(self, post_processor):
        """process() should return a MessageRecord for the companion."""
        user_msg = make_user_message("Hello there!")
        tme = FakeTME()

        result = await post_processor.process(user_msg, "Hi! How are you?", tme)

        assert result is not None
        assert result.sender == "companion"
        assert result.content == "Hi! How are you?"
        assert result.id  # Should have a UUID
        assert result.session_id == user_msg.session_id

    async def test_companion_gets_emotional_tags(self, post_processor):
        """The companion message should have an emotional state."""
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

    async def test_session_stats_updated_for_companion(self, post_processor):
        """session_manager.add_message should be called once for companion."""
        user_msg = make_user_message()
        tme = FakeTME()

        await post_processor.process(user_msg, "Response text", tme)

        session_mgr = post_processor.session_manager
        # Only companion message tracked (user already tracked by orchestrator)
        session_mgr.add_message.assert_called_once_with("companion")

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
        """If embedding_service is None, embedding generation is skipped."""
        pp = PostProcessor(
            tier0_classifier=make_mock_tier0(),
            rule_engine=make_mock_rule_engine(),
            chronicle=make_mock_chronicle(),
            embedding_service=None,
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
        call_kwargs = tier0.classify.call_kwargs if hasattr(tier0.classify, "call_kwargs") else {}
        call_args = tier0.classify.call_args
        # The response text should be in the call
        assert "I hear you and I care." in str(call_args)

    async def test_rule_engine_called_for_response(self, post_processor):
        """Rule Engine should process the Tier 0 output for the companion."""
        user_msg = make_user_message()
        tme = FakeTME()

        await post_processor.process(user_msg, "Response text", tme)

        rule_engine = post_processor.rule_engine
        rule_engine.classify.assert_called_once()
        # Verify it was called with correct parameter names
        call_kwargs = rule_engine.classify.call_args.kwargs
        assert "raw" in call_kwargs
        assert "tme" in call_kwargs
        assert "message" in call_kwargs
        assert "recent_messages" in call_kwargs


# ---------------------------------------------------------------------------
# Tests: Resilience — graceful failure handling
# ---------------------------------------------------------------------------

class TestPostProcessorResilience:
    """Tests for graceful degradation in the PostProcessor."""

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

        assert result is not None
        assert result.emotional_state is not None
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

        result = await pp.process(user_msg, "Response", tme)
        assert result is not None

        # Give background task time to run (and fail gracefully)
        await asyncio.sleep(0.1)


# ---------------------------------------------------------------------------
# Tests: Background embedding generation
# ---------------------------------------------------------------------------

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
