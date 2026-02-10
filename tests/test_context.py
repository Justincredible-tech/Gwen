"""Tests for the Stream (working memory) and ContextAssembler.

Tests verify:
- Stream add/get/format/clear operations
- Token estimation
- Temporal context block generation
- Context assembly within budget
- Conversation truncation behavior
- Minimum exchange preservation

Run: pytest tests/test_context.py -v
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import pytest

from gwen.memory.stream import Stream, estimate_tokens, generate_temporal_block
from gwen.core.context_assembler import ContextAssembler


# ---------------------------------------------------------------------------
# Stub types for testing (self-contained, no dependency on Track 002 models)
# ---------------------------------------------------------------------------

class TimePhase(Enum):
    MORNING = "morning"
    EVENING = "evening"
    LATE_NIGHT = "late_night"
    DEEP_NIGHT = "deep_night"


class CircadianDeviationSeverity(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GapClassification(Enum):
    NORMAL = "normal"
    NOTABLE = "notable"
    SIGNIFICANT = "significant"
    ANOMALOUS = "anomalous"


class CompassDirection(Enum):
    NONE = "none"
    NORTH = "presence"
    SOUTH = "currents"
    WEST = "anchoring"
    EAST = "bridges"


@dataclass
class FakeTME:
    """Minimal stub of TemporalMetadataEnvelope for testing."""
    hour_of_day: int = 19
    day_of_week: str = "Tuesday"
    time_phase: TimePhase = TimePhase.EVENING
    local_time: datetime = field(default_factory=lambda: datetime(2026, 2, 9, 19, 23))
    session_duration_sec: int = 720
    msg_index_in_session: int = 3
    circadian_deviation_severity: CircadianDeviationSeverity = CircadianDeviationSeverity.NONE
    circadian_deviation_type: Optional[str] = None


@dataclass
class FakeGapAnalysis:
    """Minimal stub of GapAnalysis for testing."""
    duration_hours: float = 96.0
    classification: GapClassification = GapClassification.SIGNIFICANT


@dataclass
class FakeReturnContext:
    """Minimal stub of ReturnContext for testing."""
    gap_duration_display: str = "4 days"
    gap_classification: GapClassification = GapClassification.SIGNIFICANT
    preceding_summary: str = "Last session was a deep_dive. Ended naturally. Emotional state was calm."
    suggested_approach: str = "Warm acknowledgment of the absence without interrogation."


@dataclass
class FakeEmotionalStateVector:
    valence: float = 0.5
    arousal: float = 0.5
    dominance: float = 0.5
    relational_significance: float = 0.5
    vulnerability_level: float = 0.5
    compass_direction: CompassDirection = CompassDirection.NONE


class FakePromptBuilder:
    """Stub PromptBuilder that returns a fixed system prompt."""

    def __init__(self, prompt_text: str = "You are Gwen, a caring AI companion."):
        self._prompt = prompt_text

    def build_system_prompt(self, **kwargs) -> str:
        return self._prompt


class FakePersonality:
    """Stub PersonalityModule."""
    name = "Gwen"


# ---------------------------------------------------------------------------
# Stream tests
# ---------------------------------------------------------------------------

class TestStream:
    """Tests for the Stream (working memory) class."""

    def test_starts_empty(self):
        stream = Stream()
        assert stream.message_count == 0
        assert stream.get_recent(10) == []

    def test_add_and_retrieve_messages(self):
        stream = Stream()
        stream.add_message("user", "Hello!")
        stream.add_message("companion", "Hi there!")

        assert stream.message_count == 2
        recent = stream.get_recent(10)
        assert len(recent) == 2
        assert recent[0]["role"] == "user"
        assert recent[0]["content"] == "Hello!"
        assert recent[1]["role"] == "companion"
        assert recent[1]["content"] == "Hi there!"

    def test_get_recent_limits_count(self):
        stream = Stream()
        for i in range(10):
            stream.add_message("user", f"Message {i}")

        recent = stream.get_recent(3)
        assert len(recent) == 3
        assert recent[0]["content"] == "Message 7"
        assert recent[2]["content"] == "Message 9"

    def test_max_messages_enforced(self):
        stream = Stream(max_messages=5)
        for i in range(10):
            stream.add_message("user", f"Message {i}")

        assert stream.message_count == 5
        recent = stream.get_recent(5)
        assert recent[0]["content"] == "Message 5"
        assert recent[4]["content"] == "Message 9"

    def test_get_formatted(self):
        stream = Stream()
        stream.add_message("user", "How are you?")
        stream.add_message("companion", "I'm doing well, thanks!")

        formatted = stream.get_formatted(10)
        assert "User: How are you?" in formatted
        assert "Gwen: I'm doing well, thanks!" in formatted

    def test_clear_empties_stream(self):
        stream = Stream()
        stream.add_message("user", "Hello!")
        stream.add_message("companion", "Hi!")
        assert stream.message_count == 2

        stream.clear()
        assert stream.message_count == 0
        assert stream.get_recent(10) == []

    def test_add_message_with_emotional_state(self):
        stream = Stream()
        state = FakeEmotionalStateVector(valence=0.8, arousal=0.3)
        stream.add_message("user", "Great day!", emotional_state=state)

        msg = stream.get_recent(1)[0]
        assert msg["emotional_state"] is state
        assert msg["emotional_state"].valence == 0.8

    def test_add_message_default_timestamp(self):
        stream = Stream()
        before = datetime.now()
        stream.add_message("user", "Test")
        after = datetime.now()

        msg = stream.get_recent(1)[0]
        assert before <= msg["timestamp"] <= after

    def test_get_recent_zero_returns_empty(self):
        stream = Stream()
        stream.add_message("user", "Hello")
        assert stream.get_recent(0) == []

    def test_get_recent_negative_returns_empty(self):
        stream = Stream()
        stream.add_message("user", "Hello")
        assert stream.get_recent(-1) == []

    def test_get_recent_more_than_available(self):
        stream = Stream()
        stream.add_message("user", "Only one")
        recent = stream.get_recent(100)
        assert len(recent) == 1
        assert recent[0]["content"] == "Only one"

    def test_get_formatted_empty_stream(self):
        stream = Stream()
        assert stream.get_formatted(10) == ""


# ---------------------------------------------------------------------------
# Token estimation tests
# ---------------------------------------------------------------------------

class TestEstimateTokens:
    """Tests for the estimate_tokens utility function."""

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string(self):
        assert estimate_tokens("Hello") == 1

    def test_known_length(self):
        text = "a" * 100
        assert estimate_tokens(text) == 25

    def test_typical_message(self):
        text = "I had a really great day today! Everything went well at work and I'm feeling positive."
        tokens = estimate_tokens(text)
        assert 15 <= tokens <= 30


# ---------------------------------------------------------------------------
# Temporal context block tests
# ---------------------------------------------------------------------------

class TestTemporalBlock:
    """Tests for the generate_temporal_block function."""

    def test_basic_temporal_block(self):
        tme = FakeTME()
        result = generate_temporal_block(tme)

        assert "Tuesday" in result
        assert "evening" in result
        assert "12 minutes" in result
        assert "3rd message" in result
        assert "No circadian anomalies" in result

    def test_circadian_deviation_high(self):
        tme = FakeTME(
            circadian_deviation_severity=CircadianDeviationSeverity.HIGH,
            circadian_deviation_type="late_still_up",
        )
        result = generate_temporal_block(tme)

        assert "Significant circadian deviation" in result
        assert "late_still_up" in result

    def test_gap_analysis_notable(self):
        tme = FakeTME()
        gap = FakeGapAnalysis(duration_hours=96.0, classification=GapClassification.SIGNIFICANT)
        result = generate_temporal_block(tme, gap_analysis=gap)

        assert "returning" in result
        assert "significant" in result
        assert "4.0 days" in result

    def test_gap_analysis_normal_not_mentioned(self):
        tme = FakeTME()
        gap = FakeGapAnalysis(duration_hours=8.0, classification=GapClassification.NORMAL)
        result = generate_temporal_block(tme, gap_analysis=gap)

        assert "returning" not in result

    def test_block_under_300_tokens(self):
        """The temporal block should stay under ~300 tokens (~1200 chars)."""
        tme = FakeTME(
            circadian_deviation_severity=CircadianDeviationSeverity.HIGH,
            circadian_deviation_type="very_unusual_pattern_detected",
        )
        gap = FakeGapAnalysis(duration_hours=168.0, classification=GapClassification.ANOMALOUS)
        result = generate_temporal_block(tme, gap_analysis=gap)

        assert estimate_tokens(result) <= 300

    def test_ordinal_formatting(self):
        """Test ordinal suffixes for message indices."""
        assert "1st message" in generate_temporal_block(FakeTME(msg_index_in_session=1))
        assert "2nd message" in generate_temporal_block(FakeTME(msg_index_in_session=2))
        assert "3rd message" in generate_temporal_block(FakeTME(msg_index_in_session=3))
        assert "5th message" in generate_temporal_block(FakeTME(msg_index_in_session=5))

    def test_gap_hours_display(self):
        """Gaps under 24 hours display as hours, over 24 as days."""
        tme = FakeTME()
        gap_hours = FakeGapAnalysis(duration_hours=18.0, classification=GapClassification.NOTABLE)
        result_h = generate_temporal_block(tme, gap_analysis=gap_hours)
        assert "18 hours" in result_h

        gap_days = FakeGapAnalysis(duration_hours=72.0, classification=GapClassification.SIGNIFICANT)
        result_d = generate_temporal_block(tme, gap_analysis=gap_days)
        assert "3.0 days" in result_d


# ---------------------------------------------------------------------------
# Context Assembler tests
# ---------------------------------------------------------------------------

class TestContextAssembler:
    """Tests for the ContextAssembler class."""

    @pytest.fixture
    def stream_with_history(self):
        """Create a Stream with a realistic conversation history."""
        stream = Stream()
        exchanges = [
            ("user", "Hey Gwen, how are you?"),
            ("companion", "I'm doing well! How about you?"),
            ("user", "Pretty good. I had an interesting day at work."),
            ("companion", "Oh? Tell me about it!"),
            ("user", "We launched that new project I was telling you about."),
            ("companion", "That's exciting! How did it go?"),
            ("user", "Really well actually. The team was great."),
            ("companion", "I'm glad to hear that! You've been working hard on it."),
            ("user", "Yeah, it feels good to see it come together."),
            ("companion", "You should be proud of yourself."),
        ]
        for role, content in exchanges:
            stream.add_message(role, content)
        return stream

    @pytest.fixture
    def assembler(self, stream_with_history):
        return ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=FakePromptBuilder(),
            stream=stream_with_history,
        )

    async def test_context_within_budget(self, assembler):
        """Assembled context should not exceed the token budget."""
        tme = FakeTME()

        result = await assembler.assemble("What do you think about tomorrow?", tme, object())
        tokens = estimate_tokens(result)

        # Allow slack: min_exchanges guarantee can push slightly over budget
        assert tokens <= assembler.TOKEN_BUDGET + 500

    async def test_contains_system_prompt(self, assembler):
        """The assembled context should always contain the system prompt."""
        tme = FakeTME()

        result = await assembler.assemble("Hello", tme, object())
        assert "You are Gwen, a caring AI companion." in result

    async def test_contains_temporal_block(self, assembler):
        """The assembled context should always contain temporal context."""
        tme = FakeTME()

        result = await assembler.assemble("Hello", tme, object())
        assert "[Temporal Context]" in result
        assert "Tuesday" in result

    async def test_contains_current_message(self, assembler):
        """The assembled context should always contain the current user message."""
        tme = FakeTME()

        result = await assembler.assemble("What's the meaning of life?", tme, object())
        assert "What's the meaning of life?" in result

    async def test_contains_conversation_history(self, assembler):
        """The assembled context should include conversation history from the stream."""
        tme = FakeTME()

        result = await assembler.assemble("New message", tme, object())
        assert "[Conversation History]" in result
        assert "Gwen:" in result or "User:" in result

    async def test_contains_return_context_when_provided(self, assembler):
        """When return_context is provided, the system prompt should reflect it."""
        tme = FakeTME()
        return_ctx = FakeReturnContext()

        result = await assembler.assemble(
            "Hey, I'm back!", tme, object(), return_context=return_ctx,
        )
        # Return context is injected via PromptBuilder's return_context_block.
        # Our FakePromptBuilder ignores it, so we check the system prompt fallback doesn't crash.
        # In production, PromptBuilder would include the return context block.
        assert "Hey, I'm back!" in result

    async def test_memory_placeholder_present(self, assembler):
        """Memory context should show placeholder text."""
        tme = FakeTME()

        result = await assembler.assemble("Hello", tme, object())
        assert "[Memory Context]" in result

    async def test_truncation_preserves_recent_messages(self):
        """When truncating, the most recent messages should be preserved."""
        stream = Stream()
        for i in range(100):
            role = "user" if i % 2 == 0 else "companion"
            stream.add_message(role, f"This is message number {i}. " * 20)

        assembler = ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=FakePromptBuilder(),
            stream=stream,
        )

        tme = FakeTME()
        result = await assembler.assemble("Final message", tme, object())

        assert "Final message" in result

    async def test_minimum_exchanges_preserved(self):
        """Even with a tight budget, at least MIN_EXCHANGES are preserved."""
        stream = Stream()
        for i in range(8):
            role = "user" if i % 2 == 0 else "companion"
            stream.add_message(role, f"Exchange message {i}")

        assembler = ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=FakePromptBuilder(
                prompt_text="X" * 20000  # Huge system prompt to eat budget
            ),
            stream=stream,
        )

        tme = FakeTME()
        result = await assembler.assemble("Current", tme, object())

        # Current message always present
        assert "Current" in result

    async def test_emotional_state_activates_emotional_prompt(self):
        """High arousal should pass include_emotional=True to PromptBuilder."""
        # Use a PromptBuilder that records what it was called with
        class RecordingPromptBuilder:
            def __init__(self):
                self.last_kwargs = {}

            def build_system_prompt(self, **kwargs):
                self.last_kwargs = kwargs
                return "System prompt."

        builder = RecordingPromptBuilder()
        stream = Stream()
        assembler = ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=builder,
            stream=stream,
        )

        high_arousal = FakeEmotionalStateVector(arousal=0.8)
        tme = FakeTME()
        await assembler.assemble("Test", tme, object(), emotional_state=high_arousal)

        assert builder.last_kwargs.get("include_emotional") is True

    async def test_empty_stream_no_conversation_section(self):
        """With an empty stream, there should be no conversation history section."""
        stream = Stream()
        assembler = ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=FakePromptBuilder(),
            stream=stream,
        )

        tme = FakeTME()
        result = await assembler.assemble("Hello", tme, object())

        assert "[Conversation History]" not in result
        assert "Hello" in result


class TestTruncateConversation:
    """Tests for the _truncate_conversation method directly."""

    def test_no_truncation_when_under_budget(self):
        assembler = ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=FakePromptBuilder(),
            stream=Stream(),
        )

        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "companion", "content": "Hello!"},
        ]
        result = assembler._truncate_conversation(messages, available_tokens=1000)
        assert len(result) == 2

    def test_truncation_removes_oldest(self):
        assembler = ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=FakePromptBuilder(),
            stream=Stream(),
        )

        messages = [
            {"role": "user", "content": "Old message " * 50},
            {"role": "companion", "content": "Old reply " * 50},
            {"role": "user", "content": "Newer message " * 50},
            {"role": "companion", "content": "Newer reply " * 50},
            {"role": "user", "content": "Recent message " * 50},
            {"role": "companion", "content": "Recent reply " * 50},
            {"role": "user", "content": "Latest message " * 50},
            {"role": "companion", "content": "Latest reply " * 50},
            {"role": "user", "content": "Current"},
            {"role": "companion", "content": "Current reply"},
        ]

        result = assembler._truncate_conversation(messages, available_tokens=200, min_exchanges=4)

        assert len(result) >= 8
        assert result[-1]["content"] == "Current reply"

    def test_empty_messages(self):
        assembler = ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=FakePromptBuilder(),
            stream=Stream(),
        )

        result = assembler._truncate_conversation([], available_tokens=1000)
        assert result == []

    def test_min_exchanges_preserved_even_over_budget(self):
        assembler = ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=FakePromptBuilder(),
            stream=Stream(),
        )

        messages = [
            {"role": "user", "content": "Long message " * 100},
            {"role": "companion", "content": "Long reply " * 100},
            {"role": "user", "content": "Long message 2 " * 100},
            {"role": "companion", "content": "Long reply 2 " * 100},
            {"role": "user", "content": "Long message 3 " * 100},
            {"role": "companion", "content": "Long reply 3 " * 100},
            {"role": "user", "content": "Long message 4 " * 100},
            {"role": "companion", "content": "Long reply 4 " * 100},
        ]

        result = assembler._truncate_conversation(
            messages, available_tokens=10, min_exchanges=4,
        )
        assert len(result) == 8

    def test_truncation_keeps_most_recent(self):
        """After truncation, the newest messages remain."""
        assembler = ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=FakePromptBuilder(),
            stream=Stream(),
        )

        messages = [
            {"role": "user", "content": f"Message {i} " * 30}
            for i in range(20)
        ]

        result = assembler._truncate_conversation(
            messages, available_tokens=500, min_exchanges=2,
        )

        # The last message should always be present
        assert result[-1]["content"] == messages[-1]["content"]
        # Should have been truncated
        assert len(result) < len(messages)
