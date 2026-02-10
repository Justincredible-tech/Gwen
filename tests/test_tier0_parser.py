"""Tests for Tier0Parser — the 4-layer JSON safety net.

These tests verify that the parser handles every category of model output:
valid JSON, malformed JSON, prose-wrapped JSON, and complete garbage.
"""

from gwen.classification.parser import Tier0Parser
from gwen.models.classification import Tier0RawOutput


class TestTier0ParserValidJSON:
    """Layer 1: Direct Pydantic parse with coercion."""

    def setup_method(self) -> None:
        self.parser = Tier0Parser()

    def test_valid_json_all_fields(self) -> None:
        raw = '{"valence": "negative", "arousal": "high", "topic": "work_stress", "safety_keywords": ["hopeless"]}'
        result = self.parser.parse(raw)
        assert result.valence == "negative"
        assert result.arousal == "high"
        assert result.topic == "work_stress"
        assert result.safety_keywords == ["hopeless"]

    def test_valid_json_empty_keywords(self) -> None:
        raw = '{"valence": "neutral", "arousal": "low", "topic": "weather", "safety_keywords": []}'
        result = self.parser.parse(raw)
        assert result.valence == "neutral"
        assert result.arousal == "low"
        assert result.topic == "weather"
        assert result.safety_keywords == []

    def test_valid_json_fuzzy_valence(self) -> None:
        raw = '{"valence": "very negative", "arousal": "moderate", "topic": "grief", "safety_keywords": []}'
        result = self.parser.parse(raw)
        assert result.valence == "very_negative"

    def test_valid_json_fuzzy_arousal(self) -> None:
        raw = '{"valence": "neutral", "arousal": "med", "topic": "chat", "safety_keywords": []}'
        result = self.parser.parse(raw)
        assert result.arousal == "moderate"

    def test_valid_json_fuzzy_arousal_medium(self) -> None:
        raw = '{"valence": "positive", "arousal": "medium", "topic": "plans", "safety_keywords": []}'
        result = self.parser.parse(raw)
        assert result.arousal == "moderate"

    def test_valid_json_missing_optional_fields(self) -> None:
        raw = '{"valence": "neutral", "arousal": "low"}'
        result = self.parser.parse(raw)
        assert result.valence == "neutral"
        assert result.arousal == "low"
        assert result.topic == "unknown"
        assert result.safety_keywords == []


class TestTier0ParserMalformedJSON:
    """Layer 2: JSON extraction and repair."""

    def setup_method(self) -> None:
        self.parser = Tier0Parser()

    def test_trailing_comma_in_object(self) -> None:
        raw = '{"valence": "negative", "arousal": "high", "topic": "stress", "safety_keywords": [],}'
        result = self.parser.parse(raw)
        assert result.valence == "negative"
        assert result.arousal == "high"

    def test_single_quotes(self) -> None:
        raw = "{'valence': 'positive', 'arousal': 'low', 'topic': 'fun', 'safety_keywords': []}"
        result = self.parser.parse(raw)
        assert result.valence == "positive"
        assert result.arousal == "low"

    def test_prose_wrapped_json(self) -> None:
        raw = 'Sure! Here is the classification:\n{"valence": "neutral", "arousal": "moderate", "topic": "general", "safety_keywords": []}\nHope that helps!'
        result = self.parser.parse(raw)
        assert result.valence == "neutral"
        assert result.arousal == "moderate"
        assert result.topic == "general"

    def test_trailing_comma_in_array(self) -> None:
        raw = '{"valence": "negative", "arousal": "high", "topic": "crisis", "safety_keywords": ["hopeless", "empty",]}'
        result = self.parser.parse(raw)
        assert result.safety_keywords == ["hopeless", "empty"]


class TestTier0ParserFallback:
    """Layer 4: Guaranteed fallback — NEVER throws, NEVER returns None."""

    def setup_method(self) -> None:
        self.parser = Tier0Parser()

    def test_complete_garbage(self) -> None:
        result = self.parser.parse("lksjdf lkjsdf lkjsdf no json here at all")
        assert result == self.parser.FALLBACK
        assert result.valence == "neutral"
        assert result.arousal == "moderate"
        assert result.topic == "unknown"
        assert result.safety_keywords == []

    def test_empty_string(self) -> None:
        result = self.parser.parse("")
        assert result == self.parser.FALLBACK

    def test_none_input(self) -> None:
        result = self.parser.parse(None)  # type: ignore[arg-type]
        assert result == self.parser.FALLBACK

    def test_partial_json(self) -> None:
        result = self.parser.parse('{"valence": "neg')
        assert result == self.parser.FALLBACK

    def test_fallback_never_throws(self) -> None:
        garbage_inputs = [
            "",
            "   ",
            "null",
            "[]",
            "42",
            "true",
            "{{{{{",
            "}}}}",
            '<xml>not json</xml>',
            "I am a language model and I cannot...",
        ]
        for garbage in garbage_inputs:
            result = self.parser.parse(garbage)
            assert result is not None, f"Parser returned None for input: {garbage!r}"
            assert isinstance(result, Tier0RawOutput), (
                f"Parser returned non-Tier0RawOutput for input: {garbage!r}"
            )
