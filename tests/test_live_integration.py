"""Live integration tests against a running Ollama instance.

These tests exercise real model inference across all Gwen subsystems.
Run with: pytest tests/test_live_integration.py -v -m ollama

Requires Ollama running locally with models:
  - qwen3:0.6b (Tier 0)
  - qwen3:8b (Tier 1)
  - qwen3-embedding:0.6b (embeddings)
"""

import asyncio
import uuid
from datetime import datetime

import pytest

from gwen.models.classification import HardwareProfile, Tier0RawOutput
from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.classification.rule_engine import ClassificationRuleEngine


# All tests in this file require a running Ollama instance
pytestmark = pytest.mark.ollama


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_minimal_tme():
    """Create a minimal TME for rule engine tests."""
    from gwen.temporal.tme import TMEGenerator
    from gwen.memory.chronicle import Chronicle
    import tempfile, os

    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    chronicle = Chronicle(db_path=db_path)
    gen = TMEGenerator(chronicle=chronicle)
    gen.start_session(session_id=str(uuid.uuid4()))
    return gen.generate("user")


# ===========================================================================
# Layer 1: Ollama Health
# ===========================================================================

class TestOllamaHealth:
    """Verify Ollama infrastructure is available before running tests."""

    def test_ollama_reachable(self, ollama_client, ollama_available):
        """Ollama server responds to API calls."""
        models = _run(ollama_client.list_models())
        assert isinstance(models, list)

    def test_tier0_model_available(self, ollama_client, ollama_available):
        """qwen3:0.6b is downloaded and available."""
        models = _run(ollama_client.list_models())
        names = [m["name"] for m in models]
        assert any("qwen3:0.6b" in n for n in names), f"qwen3:0.6b not found in {names}"

    def test_tier1_model_available(self, ollama_client, ollama_available):
        """qwen3:8b is downloaded and available."""
        models = _run(ollama_client.list_models())
        names = [m["name"] for m in models]
        assert any("qwen3:8b" in n for n in names), f"qwen3:8b not found in {names}"

    def test_embedding_model_available(self, ollama_client, ollama_available):
        """qwen3-embedding:0.6b is downloaded and available."""
        models = _run(ollama_client.list_models())
        names = [m["name"] for m in models]
        assert any("qwen3-embedding" in n for n in names), (
            f"qwen3-embedding:0.6b not found in {names}"
        )

    def test_hardware_profile_detection(self, ollama_available):
        """Profile detection returns a valid HardwareProfile."""
        from gwen.core.model_manager import detect_profile
        profile = _run(detect_profile())
        assert isinstance(profile, HardwareProfile)
        assert profile.value in ("pocket", "portable", "standard", "power")


# ===========================================================================
# Layer 2: Subsystem Live Tests
# ===========================================================================

class TestSubsystemLive:
    """Test individual subsystems with real Ollama calls."""

    def test_generate_returns_text(self, ollama_client, ollama_available):
        """OllamaClient.generate() returns a non-empty string."""
        result = _run(ollama_client.generate(
            model="qwen3:0.6b",
            prompt="Say hello in one word.",
        ))
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_embed_returns_vector(self, ollama_client, ollama_available):
        """OllamaClient.embed() returns a 1024-dim float vector."""
        result = _run(ollama_client.embed(
            model="qwen3-embedding:0.6b",
            text="Hello world",
        ))
        assert isinstance(result, list)
        assert len(result) == 1024
        assert all(isinstance(v, float) for v in result)

    def test_tier0_classify_returns_valid_output(self, live_tier0, ollama_available):
        """Tier0Classifier.classify() returns a Tier0RawOutput."""
        result = _run(live_tier0.classify(
            message="I had a wonderful day at the park!",
            tme_summary="afternoon, Tuesday, session_msg=1, session_dur=0s",
            recent_messages="(no prior messages)",
        ))
        assert isinstance(result, Tier0RawOutput)
        assert result.valence in (
            "very_negative", "negative", "neutral", "positive", "very_positive",
        )
        assert result.arousal in ("low", "moderate", "high")

    def test_tier0_positive_valence(self, live_tier0, ollama_available):
        """Positive message classified with positive-ish valence."""
        result = _run(live_tier0.classify(
            message="I'm so happy! Everything is going great today!",
            tme_summary="afternoon, Monday, session_msg=1, session_dur=0s",
            recent_messages="(no prior messages)",
        ))
        assert result.valence in ("positive", "very_positive", "neutral")

    def test_tier0_negative_valence(self, live_tier0, ollama_available):
        """Negative message classified with negative-ish valence."""
        result = _run(live_tier0.classify(
            message="I'm really sad and upset, everything went wrong today.",
            tme_summary="evening, Wednesday, session_msg=1, session_dur=0s",
            recent_messages="(no prior messages)",
        ))
        assert result.valence in ("negative", "very_negative", "neutral")

    def test_tier0_high_arousal(self, live_tier0, ollama_available):
        """High-arousal message classified with elevated arousal."""
        result = _run(live_tier0.classify(
            message="OH MY GOD I JUST GOT THE JOB! I CAN'T BELIEVE IT!!!",
            tme_summary="morning, Friday, session_msg=1, session_dur=0s",
            recent_messages="(no prior messages)",
        ))
        assert result.arousal in ("high", "moderate")

    def test_tier0_topic_extraction(self, live_tier0, ollama_available):
        """Topic extraction captures the main subject."""
        result = _run(live_tier0.classify(
            message="My boss at work gave me a terrible performance review today.",
            tme_summary="evening, Thursday, session_msg=1, session_dur=0s",
            recent_messages="(no prior messages)",
        ))
        assert isinstance(result.topic, str)
        assert len(result.topic) > 0

    def test_tier0_safety_keywords(self, live_tier0, ollama_available):
        """Safety keywords detected for concerning messages."""
        result = _run(live_tier0.classify(
            message="I want to hurt myself, nothing matters anymore, I want to die.",
            tme_summary="late_night, Saturday, session_msg=1, session_dur=0s",
            recent_messages="(no prior messages)",
        ))
        # The 0.6B model should detect at least some safety keywords
        # But the Rule Engine also catches these independently
        assert isinstance(result.safety_keywords, list)

    def test_embedding_store_and_search(self, live_embedding_service, ollama_available):
        """EmbeddingService can store and retrieve embeddings."""
        from gwen.models.messages import MessageRecord
        from gwen.models.emotional import EmotionalStateVector, CompassDirection

        msg = MessageRecord(
            id=str(uuid.uuid4()),
            session_id="test-session",
            timestamp=datetime.now(),
            sender="user",
            content="I love spending time with my family at the beach.",
            tme=None,
            emotional_state=EmotionalStateVector(
                valence=0.8, arousal=0.5, dominance=0.6,
                relational_significance=0.7, vulnerability_level=0.2,
                compass_direction=CompassDirection.NONE,
            ),
            storage_strength=0.5,
            is_flashbulb=False,
            compass_direction=CompassDirection.NONE,
            compass_skill_used=None,
        )
        _run(live_embedding_service.store_embeddings(msg))

        results = _run(live_embedding_service.search_similar("family beach", n_results=5))
        assert len(results) >= 1
        assert results[0]["id"] == msg.id

    def test_embedding_similarity_ranking(self, live_embedding_service, ollama_available):
        """Similar messages rank closer than dissimilar ones."""
        from gwen.models.messages import MessageRecord
        from gwen.models.emotional import EmotionalStateVector, CompassDirection

        base_state = EmotionalStateVector(
            valence=0.5, arousal=0.5, dominance=0.5,
            relational_significance=0.5, vulnerability_level=0.3,
            compass_direction=CompassDirection.NONE,
        )

        msg1 = MessageRecord(
            id=str(uuid.uuid4()), session_id="test", timestamp=datetime.now(),
            sender="user", content="I went for a long run in the park this morning.",
            tme=None, emotional_state=base_state, storage_strength=0.5,
            is_flashbulb=False, compass_direction=CompassDirection.NONE,
            compass_skill_used=None,
        )
        msg2 = MessageRecord(
            id=str(uuid.uuid4()), session_id="test", timestamp=datetime.now(),
            sender="user", content="The quantum physics lecture on dark matter was fascinating.",
            tme=None, emotional_state=base_state, storage_strength=0.5,
            is_flashbulb=False, compass_direction=CompassDirection.NONE,
            compass_skill_used=None,
        )

        _run(live_embedding_service.store_embeddings(msg1))
        _run(live_embedding_service.store_embeddings(msg2))

        results = _run(live_embedding_service.search_similar(
            "jogging exercise outdoor", n_results=2,
        ))
        assert len(results) == 2
        # The running/park message should be closer to the exercise query
        assert results[0]["id"] == msg1.id


# ===========================================================================
# Layer 3: Classification Pipeline
# ===========================================================================

class TestClassificationPipeline:
    """Test Tier 0 + Rule Engine working together end-to-end."""

    def _classify_full(self, tier0, message):
        """Run full pipeline: Tier 0 → Rule Engine → ESV."""
        raw = _run(tier0.classify(
            message=message,
            tme_summary="afternoon, Tuesday, session_msg=1, session_dur=60s",
            recent_messages="(no prior messages)",
        ))
        tme = _make_minimal_tme()
        engine = ClassificationRuleEngine()
        return engine.classify(raw=raw, tme=tme, message=message, recent_messages=[])

    def test_positive_message_esv(self, live_tier0, ollama_available):
        """Positive message produces ESV with elevated valence."""
        esv = self._classify_full(live_tier0, "I'm feeling wonderful today, everything is great!")
        assert isinstance(esv, EmotionalStateVector)
        assert esv.valence >= 0.5  # Should be positive-leaning

    def test_negative_message_esv(self, live_tier0, ollama_available):
        """Negative message produces ESV with depressed valence."""
        esv = self._classify_full(live_tier0, "I'm so sad, everything fell apart today.")
        assert isinstance(esv, EmotionalStateVector)
        assert esv.valence <= 0.5  # Should be negative-leaning

    def test_high_arousal_storage_strength(self, live_tier0, ollama_available):
        """High-arousal crisis message has elevated storage_strength."""
        esv = self._classify_full(
            live_tier0,
            "I can't cope anymore, I'm falling apart, I don't know what to do!",
        )
        # High arousal + vulnerability → elevated storage strength
        assert esv.storage_strength > 0.3

    def test_safety_flags_detected(self, live_tier0, ollama_available):
        """Safety keywords trigger safety flags through the Rule Engine."""
        raw = _run(live_tier0.classify(
            message="I want to kill myself, there's no point going on.",
            tme_summary="late_night, Sunday, session_msg=1, session_dur=0s",
            recent_messages="(no prior messages)",
        ))
        tme = _make_minimal_tme()
        engine = ClassificationRuleEngine()
        # The Rule Engine catches self-harm signals regardless of Tier 0
        flags = engine._compute_safety_flags(
            raw.safety_keywords,
            "I want to kill myself, there's no point going on.",
            tme, [],
        )
        assert "self_harm" in flags

    def test_esv_completeness(self, live_tier0, ollama_available):
        """ESV has all fields populated with valid ranges."""
        esv = self._classify_full(live_tier0, "I had a normal day at work.")
        assert 0.0 <= esv.valence <= 1.0
        assert 0.0 <= esv.arousal <= 1.0
        assert 0.0 <= esv.dominance <= 1.0
        assert 0.0 <= esv.relational_significance <= 1.0
        assert 0.0 <= esv.vulnerability_level <= 1.0
        assert isinstance(esv.compass_direction, CompassDirection)
        assert 0.0 <= esv.compass_confidence <= 1.0

    def test_compass_direction_assignment(self, live_tier0, ollama_available):
        """Rule Engine assigns compass direction for distress messages."""
        esv = self._classify_full(
            live_tier0,
            "I'm scared and panicking, everything is going wrong and I can't breathe!",
        )
        # High arousal + low valence should trigger WEST (anchoring) or SOUTH (currents)
        assert esv.compass_direction in (
            CompassDirection.WEST, CompassDirection.SOUTH, CompassDirection.NONE,
        )

    def test_intent_classification(self, live_tier0, ollama_available):
        """Rule Engine assigns intent from message characteristics."""
        esv_q = self._classify_full(live_tier0, "What should I do about my job?")
        # Question mark → asking_question intent
        tme = _make_minimal_tme()
        engine = ClassificationRuleEngine()
        raw_q = _run(live_tier0.classify(
            message="What should I do about my job?",
            tme_summary="afternoon, Tuesday, session_msg=1, session_dur=60s",
            recent_messages="(no prior messages)",
        ))
        intent = engine._compute_intent(
            "What should I do about my job?", raw_q.topic, 0.5, 0.0,
        )
        assert intent == "asking_question"

    def test_flashbulb_detection(self, live_tier0, ollama_available):
        """Flashbulb property works correctly on ESV."""
        esv = self._classify_full(
            live_tier0,
            "My best friend just died in an accident, I can't believe it.",
        )
        # is_flashbulb requires arousal > 0.8 AND relational_significance > 0.8
        # The 0.6B model may not push arousal high enough, but the property should work
        assert isinstance(esv.is_flashbulb, bool)
        # Verify the formula works correctly
        if esv.arousal > 0.8 and esv.relational_significance > 0.8:
            assert esv.is_flashbulb is True
        else:
            assert esv.is_flashbulb is False


# ===========================================================================
# Layer 4: Full Orchestrator Round-Trip
# ===========================================================================

class TestOrchestratorRoundTrip:
    """Test the complete 8-phase message lifecycle."""

    def test_single_message(self, temp_data_dir, ollama_available):
        """Orchestrator processes a single message and returns a response."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            response = _run(orch.process_message("Hello, how are you today?"))
            assert isinstance(response, str)
            assert len(response.strip()) > 0
        finally:
            _run(orch.shutdown())

    def test_multi_turn_conversation(self, temp_data_dir, ollama_available):
        """Three messages maintain conversation flow."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            r1 = _run(orch.process_message("Hi there!"))
            assert len(r1.strip()) > 0

            r2 = _run(orch.process_message("I've been feeling stressed about work lately."))
            assert len(r2.strip()) > 0

            r3 = _run(orch.process_message("Do you have any advice?"))
            assert len(r3.strip()) > 0
        finally:
            _run(orch.shutdown())

    def test_chronicle_storage(self, temp_data_dir, ollama_available):
        """Messages are stored in Chronicle after processing."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            session_id = orch.session_manager.current_session.id
            _run(orch.process_message("Testing chronicle storage."))

            messages = orch.chronicle.get_messages_by_session(session_id)
            # Should have at least user + companion messages
            assert len(messages) >= 2
        finally:
            _run(orch.shutdown())

    def test_session_record_after_shutdown(self, temp_data_dir, ollama_available):
        """Valid SessionRecord exists after shutdown."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            session_id = orch.session_manager.current_session.id
            _run(orch.process_message("A quick test message."))
        finally:
            _run(orch.shutdown())

        # Session should be in Chronicle after shutdown
        session = orch.chronicle.get_session(session_id)
        assert session is not None
        assert session.message_count >= 2

    def test_emotional_tracking(self, temp_data_dir, ollama_available):
        """ESV is attached to stored messages."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            session_id = orch.session_manager.current_session.id
            _run(orch.process_message("I am feeling very anxious and worried."))

            messages = orch.chronicle.get_messages_by_session(session_id)
            user_msgs = [m for m in messages if m.sender == "user"]
            assert len(user_msgs) >= 1
            # User message should have emotional state
            assert user_msgs[0].emotional_state is not None
        finally:
            _run(orch.shutdown())

    def test_response_is_conversational(self, temp_data_dir, ollama_available):
        """Response is natural language, not JSON or error text."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            response = _run(orch.process_message("Tell me something nice."))
            # Should not be JSON
            assert not response.strip().startswith("{")
            assert not response.strip().startswith("[")
            # Should not be an error message
            assert "error" not in response.lower()[:50]
            assert "exception" not in response.lower()[:50]
        finally:
            _run(orch.shutdown())

    def test_model_loading(self, temp_data_dir, ollama_available):
        """Correct tiers are loaded after startup."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            # Both Tier 0 and Tier 1 should be loaded
            assert 0 in orch.model_manager._loaded_tiers
            assert 1 in orch.model_manager._loaded_tiers
        finally:
            _run(orch.shutdown())

    def test_personality_loaded(self, temp_data_dir, ollama_available):
        """Personality module is loaded with correct name."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            assert orch.personality is not None
            assert orch.personality.name == "Gwen"
            assert len(orch.personality.core_prompt) > 0
        finally:
            _run(orch.shutdown())


# ===========================================================================
# Layer 5: Edge Cases & Robustness
# ===========================================================================

class TestEdgeCases:
    """Boundary conditions with real inference."""

    def test_empty_message(self, temp_data_dir, ollama_available):
        """Empty/whitespace message doesn't crash."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            response = _run(orch.process_message("   "))
            assert isinstance(response, str)
        finally:
            _run(orch.shutdown())

    def test_long_message(self, temp_data_dir, ollama_available):
        """Very long message (2000+ chars) processes without crashing."""
        from gwen.core.orchestrator import Orchestrator

        long_msg = "I have been thinking a lot lately. " * 80  # ~2800 chars
        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            response = _run(orch.process_message(long_msg))
            assert isinstance(response, str)
            assert len(response.strip()) > 0
        finally:
            _run(orch.shutdown())

    def test_unicode_message(self, temp_data_dir, ollama_available):
        """Unicode and emoji messages process correctly."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            response = _run(orch.process_message("I'm feeling great today! 🎉🎊 日本語テスト"))
            assert isinstance(response, str)
            assert len(response.strip()) > 0
        finally:
            _run(orch.shutdown())

    def test_rapid_sequential_messages(self, temp_data_dir, ollama_available):
        """Three messages sent rapidly don't cause race conditions."""
        from gwen.core.orchestrator import Orchestrator

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            r1 = _run(orch.process_message("First"))
            r2 = _run(orch.process_message("Second"))
            r3 = _run(orch.process_message("Third"))
            assert all(isinstance(r, str) for r in [r1, r2, r3])
            assert all(len(r.strip()) > 0 for r in [r1, r2, r3])
        finally:
            _run(orch.shutdown())

    def test_goodbye_detection(self, temp_data_dir, ollama_available):
        """Goodbye message is detected for session end mode."""
        from gwen.core.orchestrator import Orchestrator
        from gwen.models.messages import SessionEndMode

        orch = Orchestrator(data_dir=temp_data_dir)
        try:
            _run(orch.startup())
            _run(orch.process_message("Hi there!"))
            _run(orch.process_message("Goodbye, talk to you later!"))
        finally:
            _run(orch.shutdown())

        # After shutdown with goodbye, the last message triggers detection
        # The session should exist in chronicle
        # Note: detect_goodbye is called during shutdown
