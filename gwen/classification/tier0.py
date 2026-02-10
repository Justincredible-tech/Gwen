"""Tier 0 classification — prompt definition and model caller.

This module defines the simplified prompt that asks the 0.6B model for only 4 fields
(valence, arousal, topic, safety_keywords). All other emotional dimensions are computed
deterministically by the ClassificationRuleEngine in rule_engine.py.
"""

from __future__ import annotations

from gwen.models.classification import Tier0RawOutput
from gwen.classification.parser import Tier0Parser

# Type hint only — avoid circular import at runtime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gwen.core.model_manager import AdaptiveModelManager

TIER0_CLASSIFICATION_PROMPT = """Classify this message emotionally. Return ONLY valid JSON.

Context: {tme_summary}
Recent: {last_3_messages}
Message: {message_text}

Return JSON:
{{"valence": "negative", "arousal": "high", "topic": "brief_label", "safety_keywords": []}}

valence: very_negative | negative | neutral | positive | very_positive
arousal: low | moderate | high
topic: 1-3 word label
safety_keywords: list any concerning words/phrases about self-harm, violence, hopelessness, or dissociation. Empty list if none.

JSON only."""

TIER0_RETRY_PROMPT = """Classify: "{message_text}"
{{"valence":"","arousal":"","topic":"","safety_keywords":[]}}"""


class Tier0Classifier:
    """Calls the Tier 0 model to produce a raw emotional classification.

    This class formats the prompt, sends it to the 0.6B model via AdaptiveModelManager,
    and parses the response through the Tier0Parser's 4-layer safety net.
    """

    def __init__(self, model_manager: AdaptiveModelManager) -> None:
        """Initialize with a model manager for Tier 0 inference.

        Args:
            model_manager: The AdaptiveModelManager instance that handles Ollama calls.
        """
        self.model_manager = model_manager
        self.parser = Tier0Parser()

    async def classify(
        self,
        message: str,
        tme_summary: str,
        recent_messages: str,
    ) -> Tier0RawOutput:
        """Classify a message using Tier 0 with retry on failure.

        Args:
            message: The raw user message text.
            tme_summary: A compact string summary of the current TME.
            recent_messages: The last 3 messages formatted as a string.

        Returns:
            Tier0RawOutput — always valid, never None.
        """
        result = await self._call_and_parse(message, tme_summary, recent_messages)

        # Layer 3: If we got FALLBACK, retry once with simpler prompt
        if result == self.parser.FALLBACK:
            result = await self._retry_simple(message)

        return result

    async def _call_and_parse(
        self,
        message: str,
        tme_summary: str,
        recent_messages: str,
    ) -> Tier0RawOutput:
        """Format the full prompt, call the model, parse the response."""
        prompt = TIER0_CLASSIFICATION_PROMPT.format(
            tme_summary=tme_summary,
            last_3_messages=recent_messages,
            message_text=message,
        )
        raw_text = await self.model_manager.generate(tier=0, prompt=prompt)
        return self.parser.parse(raw_text)

    async def _retry_simple(self, message: str) -> Tier0RawOutput:
        """Retry with a drastically simplified fill-in-the-blank prompt."""
        prompt = TIER0_RETRY_PROMPT.format(
            message_text=message[:100],
        )
        raw_text = await self.model_manager.generate(tier=0, prompt=prompt)
        return self.parser.parse(raw_text)


async def classify_with_retry(
    model_manager: AdaptiveModelManager,
    parser: Tier0Parser,
    message: str,
    tme_summary: str,
    recent: str,
    max_retries: int = 1,
) -> Tier0RawOutput:
    """Classify a message with retry on parse failure — standalone function version.

    Args:
        model_manager: AdaptiveModelManager for Tier 0 inference.
        parser: A Tier0Parser instance.
        message: The raw user message text.
        tme_summary: Compact TME summary string.
        recent: Last 3 messages as formatted string.
        max_retries: Number of retry attempts with simplified prompt. Default 1.

    Returns:
        Tier0RawOutput — always valid, never None.
    """
    prompt = TIER0_CLASSIFICATION_PROMPT.format(
        tme_summary=tme_summary,
        last_3_messages=recent,
        message_text=message,
    )
    raw = await model_manager.generate(tier=0, prompt=prompt)
    result = parser.parse(raw)

    if result == parser.FALLBACK and max_retries > 0:
        simple_prompt = TIER0_RETRY_PROMPT.format(
            message_text=message[:100],
        )
        raw = await model_manager.generate(tier=0, prompt=simple_prompt)
        result = parser.parse(raw)

    return result
