"""Tier 0 output parser with 4-layer JSON safety net.

This parser guarantees that the orchestrator ALWAYS receives a valid Tier0RawOutput,
even when the 0.6B model hallucinates, returns prose, or outputs malformed JSON.

Layer 1: Direct json.loads() + Pydantic coercion (handles perfect output)
Layer 2: Regex extraction of {...} from prose + JSON repair + re-parse (handles wrapped output)
Layer 3: Retry with simplified prompt (handled by the caller — Tier0Classifier)
Layer 4: Return FALLBACK — guaranteed to never throw, never return None
"""

from __future__ import annotations

import json
import re

from gwen.models.classification import Tier0RawOutput


class Tier0Parser:
    """Four-layer JSON safety net for Tier 0 output parsing."""

    FALLBACK = Tier0RawOutput(
        valence="neutral",
        arousal="moderate",
        topic="unknown",
        safety_keywords=[],
    )

    def parse(self, raw_text: str) -> Tier0RawOutput:
        """Attempt to parse Tier 0 output through all safety layers.

        Args:
            raw_text: The raw string response from the Tier 0 model.

        Returns:
            Tier0RawOutput — always valid. Returns FALLBACK if all layers fail.
        """
        # Guard: if input is None or empty, skip straight to fallback
        if not raw_text or not raw_text.strip():
            return self.FALLBACK

        # Layer 1: Direct Pydantic parse with fuzzy coercion
        try:
            data = json.loads(raw_text)
            return Tier0RawOutput(**data)
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            pass

        # Layer 2: JSON extraction from prose + repair + re-parse
        try:
            extracted = self._extract_json(raw_text)
            if extracted is not None:
                repaired = self._repair_json(extracted)
                data = json.loads(repaired)
                return Tier0RawOutput(**data)
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            pass

        # Layer 4: Guaranteed fallback — never throws, never returns None
        return self.FALLBACK

    def _extract_json(self, text: str) -> str | None:
        """Extract a JSON object from text that may contain prose around it."""
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        return match.group(0) if match else None

    def _repair_json(self, text: str) -> str:
        """Fix common JSON errors produced by small language models."""
        # Fix trailing comma before }
        text = re.sub(r',\s*}', '}', text)
        # Fix trailing comma before ]
        text = re.sub(r',\s*]', ']', text)
        # Replace single quotes with double quotes
        text = text.replace("'", '"')
        return text
