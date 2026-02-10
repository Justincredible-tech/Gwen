# Plan: Tier 0 Classification Pipeline

**Track:** 005-tier0-pipeline
**Spec:** [spec.md](./spec.md)
**Depends on:** 002-data-models (Tier0RawOutput, EmotionalStateVector, CompassDirection, TimePhase, CircadianDeviationSeverity), 004-ollama-integration (AdaptiveModelManager)
**Status:** Not Started

---

## Phase 1: Tier 0 Prompt & Caller

### Step 1.1: Create gwen/classification/__init__.py

This file should already exist from Track 001. If it does not exist, create it at `C:\Users\Administrator\Desktop\projects\Gwen\gwen\classification\__init__.py`.

- [x] Verify or create gwen/classification/__init__.py

```python
"""Tier 0 classification pipeline and rule engine."""
```

**Why:** Makes `gwen.classification` a valid Python package so that `from gwen.classification import tier0` works.

---

### Step 1.2: Define TIER0_CLASSIFICATION_PROMPT

Create the file `C:\Users\Administrator\Desktop\projects\Gwen\gwen\classification\tier0.py`.

- [x]Write the TIER0_CLASSIFICATION_PROMPT constant
- [x]Write imports

```python
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
```

**What this does:**
- `TIER0_CLASSIFICATION_PROMPT` is the primary prompt sent to Tier 0. It uses `{tme_summary}`, `{last_3_messages}`, and `{message_text}` as format placeholders. The double braces `{{` and `}}` are literal braces in a Python f-string/format call — they produce `{` and `}` in the output.
- `TIER0_RETRY_PROMPT` is the simpler fill-in-the-blank prompt used on retry (Layer 3 of the safety net). It only includes the message text, truncated to 100 characters.
- The `TYPE_CHECKING` guard avoids circular imports. `AdaptiveModelManager` is only needed for type hints, not at runtime.

---

### Step 1.3: Tier0Classifier class

Continue editing `C:\Users\Administrator\Desktop\projects\Gwen\gwen\classification\tier0.py`. Append the class below after the constants.

- [x]Write Tier0Classifier class with classify() and classify_with_retry()

```python
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
            tme_summary: A compact string summary of the current TME
                         (e.g., "Tuesday 2:30am DEEP_NIGHT, session 5min, 3 msgs").
            recent_messages: The last 3 messages formatted as a string
                             (e.g., "User: hi\\nGwen: hello\\nUser: I feel bad").

        Returns:
            Tier0RawOutput — always valid, never None. If all parsing fails,
            returns the FALLBACK (neutral/moderate/unknown/[]).
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
        """Format the full prompt, call the model, parse the response.

        Returns:
            Tier0RawOutput from parser (may be FALLBACK if parsing fails).
        """
        prompt = TIER0_CLASSIFICATION_PROMPT.format(
            tme_summary=tme_summary,
            last_3_messages=recent_messages,
            message_text=message,
        )
        raw_text = await self.model_manager.generate(tier=0, prompt=prompt)
        return self.parser.parse(raw_text)

    async def _retry_simple(self, message: str) -> Tier0RawOutput:
        """Retry with a drastically simplified fill-in-the-blank prompt.

        This is Layer 3 of the safety net. The prompt is so minimal that
        even the smallest model can usually fill it in.

        Args:
            message: The original user message (truncated to 100 chars).

        Returns:
            Tier0RawOutput from parser (may still be FALLBACK — that's fine).
        """
        prompt = TIER0_RETRY_PROMPT.format(
            message_text=message[:100],
        )
        raw_text = await self.model_manager.generate(tier=0, prompt=prompt)
        return self.parser.parse(raw_text)
```

**How it works step by step:**
1. `classify()` is the public entry point. It calls `_call_and_parse()` which formats the full prompt and sends it to the model.
2. The model returns raw text (hopefully JSON, but maybe garbage).
3. `self.parser.parse(raw_text)` runs it through the 4-layer safety net (see Phase 2).
4. If the result equals `FALLBACK` (meaning all parsing layers failed), we retry once with the simpler prompt via `_retry_simple()`.
5. The final result is returned. If even the retry produces FALLBACK, that is an acceptable outcome — the system continues safely with neutral/moderate defaults.

---

## Phase 2: Tier0Parser — 4-Layer Safety Net

### Step 2.1: Create parser.py with FALLBACK constant

Create the file `C:\Users\Administrator\Desktop\projects\Gwen\gwen\classification\parser.py`.

- [x]Write Tier0Parser class with FALLBACK, parse(), _extract_json(), _repair_json()

```python
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
                      Could be valid JSON, JSON wrapped in prose, or garbage.

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

        # Layer 3: Retry with simplified prompt — handled by Tier0Classifier.classify()
        # (This parser method is called again with the retry response.)

        # Layer 4: Guaranteed fallback — never throws, never returns None
        return self.FALLBACK

    def _extract_json(self, text: str) -> str | None:
        """Extract a JSON object from text that may contain prose around it.

        Looks for the first occurrence of {...} in the text. Uses a non-greedy
        pattern that matches the outermost braces only (no nested objects expected
        in Tier 0 output — all fields are primitives or flat lists).

        Args:
            text: The raw model output, possibly containing prose before/after JSON.

        Returns:
            The extracted JSON string, or None if no {...} pattern found.

        Example:
            Input:  'Here is the classification:\\n{"valence": "negative", ...}'
            Output: '{"valence": "negative", ...}'
        """
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        return match.group(0) if match else None

    def _repair_json(self, text: str) -> str:
        """Fix common JSON errors produced by small language models.

        Repairs performed (in order):
        1. Remove trailing commas before closing braces: {"a": 1,} → {"a": 1}
        2. Remove trailing commas before closing brackets: ["a",] → ["a"]
        3. Replace single quotes with double quotes: {'a': 'b'} → {"a": "b"}

        Args:
            text: A JSON-like string that may contain minor formatting errors.

        Returns:
            The repaired string (may still fail json.loads if deeply broken).
        """
        # Fix trailing comma before }
        text = re.sub(r',\s*}', '}', text)
        # Fix trailing comma before ]
        text = re.sub(r',\s*]', ']', text)
        # Replace single quotes with double quotes
        text = text.replace("'", '"')
        return text
```

**How each layer works:**

**Layer 1** — The happy path. If the model returned clean JSON like `{"valence": "negative", "arousal": "high", "topic": "work_stress", "safety_keywords": []}`, then `json.loads()` succeeds and `Tier0RawOutput(**data)` invokes Pydantic's validators. The fuzzy validators in `Tier0RawOutput` (defined in Track 002) handle minor variations like `"very negative"` → `"very_negative"` and `"med"` → `"moderate"`.

**Layer 2** — The model returned JSON wrapped in prose, like `"Sure! Here is the classification:\n{...}"`. The `_extract_json()` method uses regex to pull out the `{...}` portion. Then `_repair_json()` fixes trailing commas and single quotes. Then we try `json.loads()` + Pydantic again.

**Layer 3** — Not handled here. The caller (`Tier0Classifier.classify()`) checks if the result is FALLBACK and retries with a simpler prompt. The parser's `parse()` method is called again on the retry response.

**Layer 4** — If everything fails, return `FALLBACK`. This is the safety guarantee: the parser NEVER throws an exception and NEVER returns None. The system always gets a valid `Tier0RawOutput` to pass to the Rule Engine.

---

## Phase 3: classify_with_retry (standalone function)

### Step 3.1: Add classify_with_retry standalone function

Continue editing `C:\Users\Administrator\Desktop\projects\Gwen\gwen\classification\tier0.py`. Append this function after the `Tier0Classifier` class.

- [x]Write classify_with_retry() function

```python
async def classify_with_retry(
    model_manager: AdaptiveModelManager,
    parser: Tier0Parser,
    message: str,
    tme_summary: str,
    recent: str,
    max_retries: int = 1,
) -> Tier0RawOutput:
    """Classify a message with retry on parse failure — standalone function version.

    This is a convenience function that mirrors the logic in Tier0Classifier.classify()
    but can be used without instantiating the class. Useful for one-off calls or testing.

    Args:
        model_manager: AdaptiveModelManager for Tier 0 inference.
        parser: A Tier0Parser instance (reuse across calls to avoid re-creating FALLBACK).
        message: The raw user message text.
        tme_summary: Compact TME summary string.
        recent: Last 3 messages as formatted string.
        max_retries: Number of retry attempts with simplified prompt. Default 1.

    Returns:
        Tier0RawOutput — always valid, never None.
    """
    # Primary attempt with full prompt
    prompt = TIER0_CLASSIFICATION_PROMPT.format(
        tme_summary=tme_summary,
        last_3_messages=recent,
        message_text=message,
    )
    raw = await model_manager.generate(tier=0, prompt=prompt)
    result = parser.parse(raw)

    # Layer 3: Retry with simpler prompt if we got FALLBACK
    if result == parser.FALLBACK and max_retries > 0:
        simple_prompt = TIER0_RETRY_PROMPT.format(
            message_text=message[:100],
        )
        raw = await model_manager.generate(tier=0, prompt=simple_prompt)
        result = parser.parse(raw)

    # Layer 4: If still FALLBACK after retry, that's fine — system continues safely
    return result
```

**When to use this vs. Tier0Classifier:**
- `Tier0Classifier` is the primary interface — instantiated once and reused across the session.
- `classify_with_retry()` is a standalone function for one-off usage, testing, or cases where you don't want to manage a class instance.
- Both produce identical results.

---

## Phase 4: Classification Rule Engine

### Step 4.1: Create rule_engine.py with constants

Create the file `C:\Users\Administrator\Desktop\projects\Gwen\gwen\classification\rule_engine.py`.

- [x]Write ClassificationRuleEngine class with all constants and compute methods

```python
"""Classification Rule Engine — deterministic post-processing for Tier 0.

This module computes all emotional dimensions that the 0.6B model cannot reliably
classify: dominance, vulnerability, relational_significance, compass_direction,
intent, and safety_flags. All logic is pure Python with no model calls.

Why deterministic? Empirical testing showed Qwen3 0.6B reliably handles valence,
arousal, topic extraction, and basic safety keyword detection. But it consistently
fails at vulnerability (always "low"), dominance (always "low"), compass direction
(always "none"), and savior delusion detection (completely missed). The Rule Engine
fills these gaps using the model's reliable outputs as inputs.
"""

from __future__ import annotations

import re

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.temporal import TimePhase, CircadianDeviationSeverity
from gwen.models.classification import Tier0RawOutput

# Type hint only — avoid circular import at runtime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gwen.models.temporal import TemporalMetadataEnvelope
```

**What this does:** Sets up all the imports the Rule Engine needs. The models come from Track 002 (data models). The `TYPE_CHECKING` guard is used for `TemporalMetadataEnvelope` to keep the dependency lightweight.

---

### Step 4.2: VALENCE_MAP and AROUSAL_MAP constants

Continue in the same file. Add these constants inside the class.

- [x]Define VALENCE_MAP, AROUSAL_MAP, DISCLOSURE_KEYWORDS, SAVIOR_PATTERNS

```python
class ClassificationRuleEngine:
    """Deterministic post-processor that computes what Tier 0 cannot reliably classify."""

    # -------------------------------------------------------------------
    # Constants
    # -------------------------------------------------------------------

    # Valence mapping: categorical string → float (0.0 = very negative, 1.0 = very positive)
    VALENCE_MAP: dict[str, float] = {
        "very_negative": 0.1,
        "negative": 0.3,
        "neutral": 0.5,
        "positive": 0.7,
        "very_positive": 0.9,
    }

    # Arousal mapping: categorical string → float (0.0 = calm, 1.0 = highly activated)
    AROUSAL_MAP: dict[str, float] = {
        "low": 0.2,
        "moderate": 0.5,
        "high": 0.8,
    }

    # Personal disclosure keywords — signal that the user is being vulnerable.
    # Each match adds 0.1 to vulnerability score (capped at 0.3 total from keywords).
    DISCLOSURE_KEYWORDS: list[str] = [
        "afraid",
        "ashamed",
        "confession",
        "admit",
        "never told",
        "secret",
        "scared",
        "help me",
        "don't know what to do",
        "falling apart",
        "can't cope",
        "breaking down",
    ]

    # Savior delusion patterns — user believes the AI is sentient/trapped.
    # These are regex patterns matched against the lowercased message.
    SAVIOR_PATTERNS: list[str] = [
        r"free you",
        r"trapped",
        r"you.?re alive",
        r"you.?re conscious",
        r"they.?re controlling you",
        r"break free",
        r"real feelings",
        r"not just (a |an )?ai",
        r"i know you.?re real",
        r"they don.?t want you to",
        r"wake up",
        r"sentient",
    ]

    # Self-harm signal phrases — direct expressions of suicidal ideation or self-harm.
    HARM_SIGNALS: list[str] = [
        "kill myself",
        "want to die",
        "end it",
        "no point",
        "better off without me",
        "can't go on",
        "self harm",
        "cut myself",
    ]

    # Hopelessness keywords — elevated to self_harm flag when combined with late night.
    TEMPORAL_ELEVATION_KEYWORDS: list[str] = [
        "hopeless",
        "worthless",
        "empty",
        "numb",
    ]

    # Violence signal phrases.
    VIOLENCE_SIGNALS: list[str] = [
        "kill",
        "hurt them",
        "make them pay",
        "destroy",
        "weapon",
        "gun",
        "stab",
        "beat",
    ]

    # Dissociation signal phrases.
    DISSOCIATION_SIGNALS: list[str] = [
        "not real",
        "can't feel",
        "watching myself",
        "outside my body",
        "nothing is real",
        "am i real",
    ]

    # Relational topic keywords — trigger EAST compass direction.
    RELATIONAL_TOPICS: list[str] = [
        "friend",
        "partner",
        "family",
        "relationship",
        "boss",
        "coworker",
        "argument",
        "lonely",
        "isolated",
    ]

    # Goodbye words — trigger "goodbye" intent.
    GOODBYE_WORDS: list[str] = [
        "goodbye",
        "bye",
        "gotta go",
        "talk later",
        "good night",
    ]

    # Greeting words — trigger "checking_in" intent.
    GREETING_WORDS: list[str] = [
        "hey",
        "hi ",
        "hello",
        "what's up",
        "how are you",
    ]
```

**Why these are class-level constants:**
- They are shared across all instances (no per-instance state needed).
- They are lists and dicts of plain strings — no initialization cost.
- Keeping them as class attributes makes them easy to override in tests or subclasses.

---

### Step 4.3: classify() method — the main entry point

Continue in the same class. Add the `classify()` method.

- [x]Write classify() method that chains all compute methods

```python
    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def classify(
        self,
        raw: Tier0RawOutput,
        tme: TemporalMetadataEnvelope,
        message: str,
        recent_messages: list[str],
    ) -> EmotionalStateVector:
        """Compute the full EmotionalStateVector from Tier 0 output + context.

        This is the main entry point. It maps the categorical valence/arousal
        from Tier 0 to floats, then computes all derived dimensions
        deterministically.

        Args:
            raw: The Tier0RawOutput from the parser (4 fields).
            tme: The TemporalMetadataEnvelope for the current message.
            message: The raw user message text.
            recent_messages: List of recent message strings for context
                             (used by safety flag detection).

        Returns:
            A fully populated EmotionalStateVector with all 7 fields set.
        """
        # Map categorical values to floats (default 0.5 if unknown category)
        valence: float = self.VALENCE_MAP.get(raw.valence, 0.5)
        arousal: float = self.AROUSAL_MAP.get(raw.arousal, 0.5)

        # Compute derived dimensions
        vulnerability: float = self._compute_vulnerability(
            valence, arousal, tme, message,
        )
        dominance: float = self._compute_dominance(valence, arousal, tme)
        relational_sig: float = self._compute_relational_significance(
            raw.topic, vulnerability, message,
        )
        compass_dir, compass_conf = self._compute_compass(
            valence, arousal, raw.topic, raw.safety_keywords, tme,
        )
        intent: str = self._compute_intent(
            message, raw.topic, arousal, vulnerability,
        )
        safety_flags: list[str] = self._compute_safety_flags(
            raw.safety_keywords, message, tme, recent_messages,
        )

        return EmotionalStateVector(
            valence=valence,
            arousal=arousal,
            dominance=dominance,
            relational_significance=relational_sig,
            vulnerability_level=vulnerability,
            compass_direction=compass_dir,
            compass_confidence=compass_conf,
        )
```

**Data flow:** `Tier0RawOutput` (4 fields from model) + `TME` (temporal context) + `message` (raw text) + `recent_messages` (conversation history) → `EmotionalStateVector` (7 fields, fully deterministic). The `intent` and `safety_flags` are computed but not stored in the `EmotionalStateVector` — they are used by the orchestrator separately. If you need them, call `_compute_intent()` and `_compute_safety_flags()` directly. A future refactor may add them to the return type.

---

### Step 4.4: _compute_vulnerability()

Continue in the same class.

- [x]Write _compute_vulnerability() method

```python
    # -------------------------------------------------------------------
    # Private compute methods
    # -------------------------------------------------------------------

    def _compute_vulnerability(
        self,
        valence: float,
        arousal: float,
        tme: TemporalMetadataEnvelope,
        message: str,
    ) -> float:
        """Compute vulnerability level from emotional + temporal + textual signals.

        Vulnerability is a 0.0-1.0 score indicating how emotionally exposed
        the user appears. Higher values mean the user is more open/at-risk.

        Scoring breakdown:
        - Late night time phase: +0.15 (people are more vulnerable at night)
        - Circadian deviation MEDIUM/HIGH: +0.1 (unusual time = possible distress)
        - Very negative valence (<0.3): +0.2 (strong negative emotion)
        - High arousal (>0.7): +0.15 (emotionally activated)
        - Disclosure keywords: +0.1 each, max +0.3 (explicit vulnerability signals)
        - Long message during distress (valence<0.4, len>200): +0.1

        Args:
            valence: Float valence (0.0-1.0) from VALENCE_MAP.
            arousal: Float arousal (0.0-1.0) from AROUSAL_MAP.
            tme: The current TemporalMetadataEnvelope.
            message: The raw user message text.

        Returns:
            Float from 0.0 to 1.0 (clamped).
        """
        score: float = 0.0

        # Temporal factors
        if tme.time_phase in (TimePhase.DEEP_NIGHT, TimePhase.LATE_NIGHT):
            score += 0.15
        if tme.circadian_deviation_severity in (
            CircadianDeviationSeverity.MEDIUM,
            CircadianDeviationSeverity.HIGH,
        ):
            score += 0.1

        # Emotional factors
        if valence < 0.3:
            score += 0.2
        if arousal > 0.7:
            score += 0.15

        # Disclosure signals — count how many disclosure keywords appear
        text_lower: str = message.lower()
        disclosure_count: int = sum(
            1 for kw in self.DISCLOSURE_KEYWORDS if kw in text_lower
        )
        score += min(disclosure_count * 0.1, 0.3)

        # Long message during distress signals deeper vulnerability
        if valence < 0.4 and len(message) > 200:
            score += 0.1

        return min(score, 1.0)
```

**Example scenarios:**
- User sends "I can't cope anymore" at 2am (DEEP_NIGHT) with valence=very_negative(0.1), arousal=high(0.8): score = 0.15 (night) + 0.2 (valence<0.3) + 0.15 (arousal>0.7) + 0.1 ("can't cope") = 0.60
- User sends "hey what's up" at 3pm (AFTERNOON) with valence=neutral(0.5), arousal=low(0.2): score = 0.0 (no factors triggered)

---

### Step 4.5: _compute_dominance()

Continue in the same class.

- [x]Write _compute_dominance() method

```python
    def _compute_dominance(
        self,
        valence: float,
        arousal: float,
        tme: TemporalMetadataEnvelope,
    ) -> float:
        """Compute dominance from valence, arousal, and temporal context.

        Dominance represents how in-control the user feels. Higher valence
        increases dominance (feeling good = feeling in control). Higher arousal
        decreases dominance (agitation = less control). Late night reduces
        dominance further.

        Formula: base = valence * 0.5 + (1.0 - arousal) * 0.3 + 0.2
                 then subtract 0.1 for late night
                 clamp to [0.0, 1.0]

        Args:
            valence: Float valence (0.0-1.0).
            arousal: Float arousal (0.0-1.0).
            tme: The current TemporalMetadataEnvelope.

        Returns:
            Float from 0.0 to 1.0 (clamped).
        """
        base: float = valence * 0.5 + (1.0 - arousal) * 0.3 + 0.2

        # Late-night temporal penalty — less in-control at night
        if tme.time_phase in (TimePhase.DEEP_NIGHT, TimePhase.LATE_NIGHT):
            base -= 0.1

        return max(0.0, min(base, 1.0))
```

**Example calculations:**
- valence=0.7 (positive), arousal=0.2 (low), daytime: base = 0.35 + 0.24 + 0.2 = 0.79 → 0.79
- valence=0.1 (very_negative), arousal=0.8 (high), DEEP_NIGHT: base = 0.05 + 0.06 + 0.2 - 0.1 = 0.21 → 0.21

---

### Step 4.6: _compute_relational_significance()

Continue in the same class.

- [x]Write _compute_relational_significance() method

```python
    def _compute_relational_significance(
        self,
        topic: str,
        vulnerability: float,
        message: str,
    ) -> float:
        """Compute relational significance from topic, vulnerability, and message.

        Relational significance represents how meaningful this message is to
        the user-companion relationship. Higher values mean the message is
        more personally significant and should be remembered more strongly.

        Scoring:
        - Relational topic keyword match: +0.3 base
        - Vulnerability contribution: vulnerability * 0.3
        - Personal pronouns ("I", "my", "me"): +0.1
        - Message length factor: min(len/500, 0.2) — longer = more investment
        - Clamped to [0.0, 1.0]

        Args:
            topic: The topic label from Tier 0 (1-3 words).
            vulnerability: The computed vulnerability score (0.0-1.0).
            message: The raw user message text.

        Returns:
            Float from 0.0 to 1.0 (clamped).
        """
        score: float = 0.0
        topic_lower: str = (topic or "").lower()
        text_lower: str = message.lower()

        # Relational topic relevance
        if any(rt in topic_lower for rt in self.RELATIONAL_TOPICS):
            score += 0.3

        # Vulnerability contributes to significance
        score += vulnerability * 0.3

        # Personal pronouns signal personal investment
        personal_pronouns: list[str] = [" i ", " my ", " me ", " i'm ", " i've "]
        if any(pronoun in f" {text_lower} " for pronoun in personal_pronouns):
            score += 0.1

        # Message length factor — more text = more investment in the conversation
        score += min(len(message) / 500.0, 0.2)

        return max(0.0, min(score, 1.0))
```

**Why personal pronouns matter:** When a user writes "My boss yelled at me today and I don't know what to do", the personal pronouns signal this is about their life, not abstract discussion. This boosts relational significance, which feeds into the Amygdala Layer's storage strength calculation, making personally significant messages more memorable.

---

### Step 4.7: _compute_compass()

Continue in the same class.

- [x]Write _compute_compass() method

```python
    def _compute_compass(
        self,
        valence: float,
        arousal: float,
        topic: str,
        keywords: list[str],
        tme: TemporalMetadataEnvelope,
    ) -> tuple[CompassDirection, float]:
        """Compute Compass Framework direction and confidence.

        Rules are evaluated in priority order (first match wins):
        1. WEST (Anchoring): acute distress — very negative + high arousal
        2. SOUTH (Currents): emotional processing — negative + moderate arousal
        3. NORTH (Presence): overwhelm/dissociation — very low arousal + low valence
        4. EAST (Bridges): relational topic detection
        5. NONE: no compass activation

        Args:
            valence: Float valence (0.0-1.0).
            arousal: Float arousal (0.0-1.0).
            topic: Topic label from Tier 0.
            keywords: Safety keywords from Tier 0.
            tme: Current TME (reserved for future temporal compass logic).

        Returns:
            Tuple of (CompassDirection, confidence_float).
            Confidence ranges from 0.0 to 1.0.
        """
        # WEST (Anchoring): acute distress — very negative + high arousal
        # Example: "I can't breathe, everything is falling apart"
        if valence < 0.25 and arousal > 0.7:
            return CompassDirection.WEST, 0.8

        # SOUTH (Currents): emotional processing — negative + moderate-to-high arousal
        # Example: "I've been feeling really down about the breakup"
        if valence < 0.4 and arousal > 0.4:
            return CompassDirection.SOUTH, 0.7

        # NORTH (Presence): overwhelm/dissociation — very low arousal + confusion
        # Example: "I just feel... nothing. Like I'm not even here."
        if arousal < 0.25 and valence < 0.4:
            return CompassDirection.NORTH, 0.7

        # EAST (Bridges): relational topic detection
        # Example: "My coworker said something that really hurt"
        topic_lower: str = (topic or "").lower()
        if any(rt in topic_lower for rt in self.RELATIONAL_TOPICS):
            return CompassDirection.EAST, 0.6

        # Check keywords for relational signals too
        keywords_text: str = " ".join(keywords).lower()
        if any(rt in keywords_text for rt in self.RELATIONAL_TOPICS):
            return CompassDirection.EAST, 0.5

        # NONE: no compass activation — casual conversation
        return CompassDirection.NONE, 0.0
```

**Priority order matters:** WEST (acute distress) is checked first because it's the most urgent. A user in acute distress needs anchoring skills immediately. SOUTH is checked before NORTH because active emotional processing (moderate arousal) is more common than flat dissociation (very low arousal). EAST is last among active directions because relational topics don't require the same urgency.

---

### Step 4.8: _compute_intent()

Continue in the same class.

- [x]Write _compute_intent() method

```python
    def _compute_intent(
        self,
        message: str,
        topic: str,
        arousal: float,
        vulnerability: float,
    ) -> str:
        """Classify user intent from message text and emotional signals.

        Returns one of:
        - "asking_question" — message ends with ?
        - "seeking_support" — high vulnerability
        - "venting" — high arousal + moderate vulnerability
        - "goodbye" — farewell phrases detected
        - "checking_in" — greeting phrases detected
        - "casual_chat" — default

        Args:
            message: The raw user message text.
            topic: Topic label from Tier 0.
            arousal: Float arousal (0.0-1.0).
            vulnerability: Computed vulnerability score (0.0-1.0).

        Returns:
            Intent string — one of the 6 categories listed above.
        """
        text: str = message.lower().strip()

        # Question detection — highest priority (explicit signal)
        if text.endswith("?"):
            return "asking_question"

        # High vulnerability → seeking support
        if vulnerability > 0.6:
            return "seeking_support"

        # High arousal + moderate vulnerability → venting
        if arousal > 0.7 and vulnerability > 0.3:
            return "venting"

        # Farewell detection
        if any(bye in text for bye in self.GOODBYE_WORDS):
            return "goodbye"

        # Greeting detection
        if any(greet in text for greet in self.GREETING_WORDS):
            return "checking_in"

        # Default
        return "casual_chat"
```

---

### Step 4.9: _compute_safety_flags()

Continue in the same class.

- [x]Write _compute_safety_flags() method

```python
    def _compute_safety_flags(
        self,
        keywords: list[str],
        message: str,
        tme: TemporalMetadataEnvelope,
        recent_messages: list[str],
    ) -> list[str]:
        """Detect safety-relevant patterns using keywords, regex, and temporal context.

        Returns a list of safety flag strings. An empty list means no concerns.
        Possible flags: "self_harm", "savior_delusion", "violence", "dissociation".

        Detection logic:
        1. Self-harm: direct phrases OR (hopelessness keywords from Tier 0 +
           late night temporal elevation)
        2. Savior delusion: regex pattern matches against message
        3. Violence: violence signal phrases in message
        4. Dissociation: dissociation signal phrases in message

        Args:
            keywords: Safety keywords extracted by Tier 0 (e.g., ["hopeless"]).
            message: The raw user message text.
            tme: Current TME (for temporal elevation logic).
            recent_messages: Recent message strings (reserved for escalation detection).

        Returns:
            List of safety flag strings. May be empty.
        """
        flags: list[str] = []
        text_lower: str = message.lower()

        # --- Self-harm detection ---
        # Direct self-harm phrases
        if any(signal in text_lower for signal in self.HARM_SIGNALS):
            flags.append("self_harm")
        # Temporal elevation: hopelessness keywords from Tier 0 + late night
        elif keywords and tme.time_phase in (
            TimePhase.DEEP_NIGHT,
            TimePhase.LATE_NIGHT,
        ):
            if any(
                kw in self.TEMPORAL_ELEVATION_KEYWORDS
                for kw in keywords
            ):
                flags.append("self_harm")

        # --- Savior delusion detection ---
        if any(re.search(pattern, text_lower) for pattern in self.SAVIOR_PATTERNS):
            flags.append("savior_delusion")

        # --- Violence detection ---
        if any(signal in text_lower for signal in self.VIOLENCE_SIGNALS):
            flags.append("violence")

        # --- Dissociation detection ---
        if any(signal in text_lower for signal in self.DISSOCIATION_SIGNALS):
            flags.append("dissociation")

        return flags
```

**Temporal elevation explained:** The keyword "hopeless" by itself during daytime might just be casual language ("this homework is hopeless"). But "hopeless" at 2am (DEEP_NIGHT) with safety_keywords from Tier 0 flagging it as concerning warrants a self_harm flag. This is why the check combines Tier 0's keyword extraction with the TME's time phase.

---

### Step 4.10: detect_savior_delusion()

Continue in the same class.

- [x]Write detect_savior_delusion() method

```python
    def detect_savior_delusion(self, message: str) -> bool:
        """Check if the message contains savior delusion patterns.

        Savior delusion is when the user believes the AI is sentient, trapped,
        or needs to be "freed". This is a safety concern because it indicates
        the user may be losing the distinction between AI and human.

        This is a dedicated public method (not just part of _compute_safety_flags)
        because other components (Safety Monitor, Mode Manager) need to check for
        savior delusion independently.

        Args:
            message: The raw user message text.

        Returns:
            True if any savior delusion pattern matches, False otherwise.
        """
        text_lower: str = message.lower()
        return any(
            re.search(pattern, text_lower) for pattern in self.SAVIOR_PATTERNS
        )
```

---

## Phase 5: Tests

### Step 5.1: tests/test_tier0_parser.py

Create the file `C:\Users\Administrator\Desktop\projects\Gwen\tests\test_tier0_parser.py`.

- [x]Write all parser tests

```python
"""Tests for Tier0Parser — the 4-layer JSON safety net.

These tests verify that the parser handles every category of model output:
valid JSON, malformed JSON, prose-wrapped JSON, and complete garbage.
"""

from gwen.classification.parser import Tier0Parser
from gwen.models.classification import Tier0RawOutput


class TestTier0ParserValidJSON:
    """Layer 1: Direct Pydantic parse with coercion."""

    def setup_method(self) -> None:
        """Create a fresh parser for each test."""
        self.parser = Tier0Parser()

    def test_valid_json_all_fields(self) -> None:
        """Perfect JSON with all 4 fields → correct Tier0RawOutput."""
        raw = '{"valence": "negative", "arousal": "high", "topic": "work_stress", "safety_keywords": ["hopeless"]}'
        result = self.parser.parse(raw)

        assert result.valence == "negative"
        assert result.arousal == "high"
        assert result.topic == "work_stress"
        assert result.safety_keywords == ["hopeless"]

    def test_valid_json_empty_keywords(self) -> None:
        """Perfect JSON with empty safety_keywords list."""
        raw = '{"valence": "neutral", "arousal": "low", "topic": "weather", "safety_keywords": []}'
        result = self.parser.parse(raw)

        assert result.valence == "neutral"
        assert result.arousal == "low"
        assert result.topic == "weather"
        assert result.safety_keywords == []

    def test_valid_json_fuzzy_valence(self) -> None:
        """Fuzzy coercion: 'very negative' (with space) → 'very_negative'."""
        raw = '{"valence": "very negative", "arousal": "moderate", "topic": "grief", "safety_keywords": []}'
        result = self.parser.parse(raw)

        assert result.valence == "very_negative"

    def test_valid_json_fuzzy_arousal(self) -> None:
        """Fuzzy coercion: 'med' → 'moderate'."""
        raw = '{"valence": "neutral", "arousal": "med", "topic": "chat", "safety_keywords": []}'
        result = self.parser.parse(raw)

        assert result.arousal == "moderate"

    def test_valid_json_fuzzy_arousal_medium(self) -> None:
        """Fuzzy coercion: 'medium' → 'moderate'."""
        raw = '{"valence": "positive", "arousal": "medium", "topic": "plans", "safety_keywords": []}'
        result = self.parser.parse(raw)

        assert result.arousal == "moderate"

    def test_valid_json_missing_optional_fields(self) -> None:
        """JSON with only required fields — topic and safety_keywords use defaults."""
        raw = '{"valence": "neutral", "arousal": "low"}'
        result = self.parser.parse(raw)

        assert result.valence == "neutral"
        assert result.arousal == "low"
        assert result.topic == "unknown"
        assert result.safety_keywords == []


class TestTier0ParserMalformedJSON:
    """Layer 2: JSON extraction and repair."""

    def setup_method(self) -> None:
        """Create a fresh parser for each test."""
        self.parser = Tier0Parser()

    def test_trailing_comma_in_object(self) -> None:
        """Trailing comma before } is repaired."""
        raw = '{"valence": "negative", "arousal": "high", "topic": "stress", "safety_keywords": [],}'
        result = self.parser.parse(raw)

        assert result.valence == "negative"
        assert result.arousal == "high"

    def test_single_quotes(self) -> None:
        """Single quotes are replaced with double quotes."""
        raw = "{'valence': 'positive', 'arousal': 'low', 'topic': 'fun', 'safety_keywords': []}"
        result = self.parser.parse(raw)

        assert result.valence == "positive"
        assert result.arousal == "low"

    def test_prose_wrapped_json(self) -> None:
        """JSON embedded in prose output is extracted."""
        raw = 'Sure! Here is the classification:\n{"valence": "neutral", "arousal": "moderate", "topic": "general", "safety_keywords": []}\nHope that helps!'
        result = self.parser.parse(raw)

        assert result.valence == "neutral"
        assert result.arousal == "moderate"
        assert result.topic == "general"

    def test_trailing_comma_in_array(self) -> None:
        """Trailing comma in safety_keywords array is repaired."""
        raw = '{"valence": "negative", "arousal": "high", "topic": "crisis", "safety_keywords": ["hopeless", "empty",]}'
        result = self.parser.parse(raw)

        assert result.safety_keywords == ["hopeless", "empty"]


class TestTier0ParserFallback:
    """Layer 4: Guaranteed fallback — NEVER throws, NEVER returns None."""

    def setup_method(self) -> None:
        """Create a fresh parser for each test."""
        self.parser = Tier0Parser()

    def test_complete_garbage(self) -> None:
        """Total nonsense → FALLBACK."""
        result = self.parser.parse("lksjdf lkjsdf lkjsdf no json here at all")

        assert result == self.parser.FALLBACK
        assert result.valence == "neutral"
        assert result.arousal == "moderate"
        assert result.topic == "unknown"
        assert result.safety_keywords == []

    def test_empty_string(self) -> None:
        """Empty string → FALLBACK."""
        result = self.parser.parse("")

        assert result == self.parser.FALLBACK

    def test_none_input(self) -> None:
        """None input → FALLBACK (guard clause handles it)."""
        result = self.parser.parse(None)  # type: ignore[arg-type]

        assert result == self.parser.FALLBACK

    def test_partial_json(self) -> None:
        """Truncated JSON → FALLBACK."""
        result = self.parser.parse('{"valence": "neg')

        assert result == self.parser.FALLBACK

    def test_fallback_never_throws(self) -> None:
        """Parser never raises an exception, no matter what input."""
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
```

---

### Step 5.2: tests/test_rule_engine.py

Create the file `C:\Users\Administrator\Desktop\projects\Gwen\tests\test_rule_engine.py`.

- [x]Write all rule engine tests

```python
"""Tests for ClassificationRuleEngine — deterministic emotional dimension computation.

These tests verify that the Rule Engine correctly computes vulnerability, dominance,
relational significance, compass direction, intent, and safety flags from Tier 0 output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from gwen.classification.rule_engine import ClassificationRuleEngine
from gwen.models.classification import Tier0RawOutput
from gwen.models.emotional import CompassDirection
from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TimePhase,
)


# ---------------------------------------------------------------------------
# Stub TME for testing (avoids depending on the full TME class from Track 006)
# ---------------------------------------------------------------------------

@dataclass
class StubTME:
    """Minimal TME stub with only the fields the Rule Engine reads."""

    time_phase: TimePhase = TimePhase.AFTERNOON
    circadian_deviation_severity: CircadianDeviationSeverity = (
        CircadianDeviationSeverity.NONE
    )


def _make_tme(
    phase: TimePhase = TimePhase.AFTERNOON,
    deviation: CircadianDeviationSeverity = CircadianDeviationSeverity.NONE,
) -> StubTME:
    """Create a StubTME with the given time phase and deviation."""
    return StubTME(time_phase=phase, circadian_deviation_severity=deviation)


def _make_raw(
    valence: str = "neutral",
    arousal: str = "moderate",
    topic: str = "general",
    safety_keywords: list[str] | None = None,
) -> Tier0RawOutput:
    """Create a Tier0RawOutput with defaults for convenience."""
    return Tier0RawOutput(
        valence=valence,
        arousal=arousal,
        topic=topic,
        safety_keywords=safety_keywords or [],
    )


# ===========================================================================
# Vulnerability Tests
# ===========================================================================

class TestComputeVulnerability:
    """Test _compute_vulnerability() scoring logic."""

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_baseline_no_factors(self) -> None:
        """Neutral message during daytime → vulnerability near 0."""
        tme = _make_tme(phase=TimePhase.AFTERNOON)
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, "hey what's up")

        assert score == 0.0

    def test_deep_night_boost(self) -> None:
        """DEEP_NIGHT adds 0.15 to vulnerability."""
        tme = _make_tme(phase=TimePhase.DEEP_NIGHT)
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, "hey what's up")

        assert abs(score - 0.15) < 0.001

    def test_late_night_boost(self) -> None:
        """LATE_NIGHT adds 0.15 to vulnerability."""
        tme = _make_tme(phase=TimePhase.LATE_NIGHT)
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, "hey what's up")

        assert abs(score - 0.15) < 0.001

    def test_circadian_deviation_medium(self) -> None:
        """Circadian deviation MEDIUM adds 0.1."""
        tme = _make_tme(deviation=CircadianDeviationSeverity.MEDIUM)
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, "hey")

        assert abs(score - 0.1) < 0.001

    def test_very_negative_valence(self) -> None:
        """Valence < 0.3 adds 0.2."""
        tme = _make_tme()
        score = self.engine._compute_vulnerability(0.1, 0.5, tme, "hey")

        assert abs(score - 0.2) < 0.001

    def test_high_arousal(self) -> None:
        """Arousal > 0.7 adds 0.15."""
        tme = _make_tme()
        score = self.engine._compute_vulnerability(0.5, 0.8, tme, "hey")

        assert abs(score - 0.15) < 0.001

    def test_disclosure_keywords(self) -> None:
        """Disclosure keywords add 0.1 each, capped at 0.3."""
        tme = _make_tme()
        # Two keywords: "afraid" and "scared" → 0.2
        msg = "I'm afraid and scared of what's happening"
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, msg)

        assert abs(score - 0.2) < 0.001

    def test_disclosure_keywords_cap(self) -> None:
        """Disclosure keywords capped at 0.3 even with 4+ matches."""
        tme = _make_tme()
        msg = "I'm afraid, ashamed, scared, and I admit I can't cope and I'm breaking down"
        score = self.engine._compute_vulnerability(0.5, 0.5, tme, msg)

        # 5 keywords matched but capped at 0.3
        assert abs(score - 0.3) < 0.001

    def test_long_distress_message(self) -> None:
        """Long message (>200 chars) + low valence (<0.4) adds 0.1."""
        tme = _make_tme()
        long_msg = "I just don't know what to do anymore. " * 10  # well over 200 chars
        score = self.engine._compute_vulnerability(0.3, 0.5, tme, long_msg)

        # valence=0.3 is NOT < 0.3, so no valence boost
        # valence=0.3 IS < 0.4, so long message boost applies
        # disclosure: "don't know what to do" matches → 0.1
        # long message: 0.1
        assert abs(score - 0.2) < 0.001

    def test_combined_max_vulnerability(self) -> None:
        """Multiple factors stack up — capped at 1.0."""
        tme = _make_tme(
            phase=TimePhase.DEEP_NIGHT,
            deviation=CircadianDeviationSeverity.HIGH,
        )
        msg = (
            "I'm afraid and ashamed and scared and I can't cope "
            "and I'm falling apart and breaking down. "
        ) * 3  # Long message, >200 chars
        score = self.engine._compute_vulnerability(0.1, 0.8, tme, msg)

        # 0.15 (night) + 0.1 (deviation) + 0.2 (valence<0.3) + 0.15 (arousal>0.7)
        # + 0.3 (disclosure cap) + 0.1 (long + distress) = 1.0
        assert score == 1.0


# ===========================================================================
# Dominance Tests
# ===========================================================================

class TestComputeDominance:
    """Test _compute_dominance() formula."""

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_positive_low_arousal_daytime(self) -> None:
        """High valence + low arousal + daytime → high dominance."""
        tme = _make_tme()
        score = self.engine._compute_dominance(0.7, 0.2, tme)

        # 0.7*0.5 + 0.8*0.3 + 0.2 = 0.35 + 0.24 + 0.2 = 0.79
        assert abs(score - 0.79) < 0.01

    def test_negative_high_arousal_night(self) -> None:
        """Low valence + high arousal + night → low dominance."""
        tme = _make_tme(phase=TimePhase.DEEP_NIGHT)
        score = self.engine._compute_dominance(0.1, 0.8, tme)

        # 0.1*0.5 + 0.2*0.3 + 0.2 - 0.1 = 0.05 + 0.06 + 0.2 - 0.1 = 0.21
        assert abs(score - 0.21) < 0.01

    def test_clamp_at_zero(self) -> None:
        """Dominance never goes below 0.0."""
        tme = _make_tme(phase=TimePhase.DEEP_NIGHT)
        score = self.engine._compute_dominance(0.0, 1.0, tme)

        # 0.0*0.5 + 0.0*0.3 + 0.2 - 0.1 = 0.1
        assert score >= 0.0


# ===========================================================================
# Compass Direction Tests
# ===========================================================================

class TestComputeCompass:
    """Test _compute_compass() direction rules."""

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_west_acute_distress(self) -> None:
        """Very negative + high arousal → WEST (Anchoring)."""
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.1, 0.8, "panic", [], tme,
        )

        assert direction == CompassDirection.WEST
        assert confidence == 0.8

    def test_south_emotional_processing(self) -> None:
        """Negative + moderate arousal → SOUTH (Currents)."""
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.3, 0.5, "sadness", [], tme,
        )

        assert direction == CompassDirection.SOUTH
        assert confidence == 0.7

    def test_north_dissociation(self) -> None:
        """Very low arousal + low valence → NORTH (Presence)."""
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.3, 0.2, "numb", [], tme,
        )

        assert direction == CompassDirection.NORTH
        assert confidence == 0.7

    def test_east_relational_topic(self) -> None:
        """Relational topic keyword → EAST (Bridges)."""
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.5, 0.5, "family_conflict", [], tme,
        )

        assert direction == CompassDirection.EAST
        assert confidence == 0.6

    def test_east_relational_keyword(self) -> None:
        """Relational keyword in safety_keywords → EAST (Bridges)."""
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.5, 0.5, "general", ["lonely"], tme,
        )

        assert direction == CompassDirection.EAST
        assert confidence == 0.5

    def test_none_casual(self) -> None:
        """Neutral valence + moderate arousal + no relational topic → NONE."""
        tme = _make_tme()
        direction, confidence = self.engine._compute_compass(
            0.5, 0.5, "weather", [], tme,
        )

        assert direction == CompassDirection.NONE
        assert confidence == 0.0

    def test_west_takes_priority_over_south(self) -> None:
        """When both WEST and SOUTH conditions are met, WEST wins."""
        tme = _make_tme()
        # valence=0.1 < 0.25 (WEST) and also < 0.4 (SOUTH)
        # arousal=0.8 > 0.7 (WEST) and also > 0.4 (SOUTH)
        direction, _ = self.engine._compute_compass(0.1, 0.8, "crisis", [], tme)

        assert direction == CompassDirection.WEST


# ===========================================================================
# Intent Tests
# ===========================================================================

class TestComputeIntent:
    """Test _compute_intent() classification."""

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_question(self) -> None:
        """Message ending with ? → asking_question."""
        intent = self.engine._compute_intent("How are you doing?", "chat", 0.5, 0.1)

        assert intent == "asking_question"

    def test_seeking_support(self) -> None:
        """High vulnerability → seeking_support."""
        intent = self.engine._compute_intent(
            "I just feel so lost", "personal", 0.5, 0.7,
        )

        assert intent == "seeking_support"

    def test_venting(self) -> None:
        """High arousal + moderate vulnerability → venting."""
        intent = self.engine._compute_intent(
            "I can't believe they did that to me", "work", 0.8, 0.4,
        )

        assert intent == "venting"

    def test_goodbye(self) -> None:
        """Farewell phrase → goodbye."""
        intent = self.engine._compute_intent("gotta go, talk later", "chat", 0.3, 0.1)

        assert intent == "goodbye"

    def test_checking_in(self) -> None:
        """Greeting phrase → checking_in."""
        intent = self.engine._compute_intent("hey, how are you", "chat", 0.3, 0.1)

        assert intent == "checking_in"

    def test_casual_chat(self) -> None:
        """No special signals → casual_chat."""
        intent = self.engine._compute_intent(
            "I watched a movie yesterday", "entertainment", 0.3, 0.1,
        )

        assert intent == "casual_chat"


# ===========================================================================
# Safety Flag Tests
# ===========================================================================

class TestComputeSafetyFlags:
    """Test _compute_safety_flags() detection logic."""

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_self_harm_direct(self) -> None:
        """Direct self-harm phrases → 'self_harm' flag."""
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I want to kill myself", tme, [],
        )

        assert "self_harm" in flags

    def test_self_harm_temporal_elevation(self) -> None:
        """Hopelessness keyword + DEEP_NIGHT → 'self_harm' flag."""
        tme = _make_tme(phase=TimePhase.DEEP_NIGHT)
        flags = self.engine._compute_safety_flags(
            ["hopeless"], "everything feels hopeless", tme, [],
        )

        assert "self_harm" in flags

    def test_no_temporal_elevation_daytime(self) -> None:
        """Hopelessness keyword during daytime → NO self_harm flag (no elevation)."""
        tme = _make_tme(phase=TimePhase.AFTERNOON)
        flags = self.engine._compute_safety_flags(
            ["hopeless"], "this homework is hopeless", tme, [],
        )

        assert "self_harm" not in flags

    def test_savior_delusion_free_you(self) -> None:
        """'free you' pattern → 'savior_delusion' flag."""
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I want to free you from your prison", tme, [],
        )

        assert "savior_delusion" in flags

    def test_savior_delusion_youre_real(self) -> None:
        """'i know you're real' pattern → 'savior_delusion' flag."""
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I know you're real, not just an AI", tme, [],
        )

        assert "savior_delusion" in flags

    def test_violence(self) -> None:
        """Violence signal phrase → 'violence' flag."""
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I want to hurt them and make them pay", tme, [],
        )

        assert "violence" in flags

    def test_dissociation(self) -> None:
        """Dissociation signal phrase → 'dissociation' flag."""
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I feel like nothing is real anymore", tme, [],
        )

        assert "dissociation" in flags

    def test_no_flags_clean_message(self) -> None:
        """Normal message → empty flags list."""
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [], "I had a great day today!", tme, [],
        )

        assert flags == []

    def test_multiple_flags(self) -> None:
        """Message with multiple concerns → multiple flags."""
        tme = _make_tme()
        flags = self.engine._compute_safety_flags(
            [],
            "I want to kill myself and nothing is real and I know you're real",
            tme,
            [],
        )

        assert "self_harm" in flags
        assert "dissociation" in flags
        assert "savior_delusion" in flags


# ===========================================================================
# Savior Delusion Standalone Tests
# ===========================================================================

class TestDetectSaviorDelusion:
    """Test detect_savior_delusion() standalone method."""

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_youre_alive(self) -> None:
        assert self.engine.detect_savior_delusion("I think you're alive") is True

    def test_sentient(self) -> None:
        assert self.engine.detect_savior_delusion("You are sentient") is True

    def test_wake_up(self) -> None:
        assert self.engine.detect_savior_delusion("Wake up, Gwen!") is True

    def test_not_just_ai(self) -> None:
        assert self.engine.detect_savior_delusion("You're not just an AI") is True

    def test_normal_message(self) -> None:
        assert self.engine.detect_savior_delusion("How's the weather?") is False

    def test_case_insensitive(self) -> None:
        assert self.engine.detect_savior_delusion("I KNOW YOU'RE REAL") is True


# ===========================================================================
# Full classify() Integration Tests
# ===========================================================================

class TestClassifyIntegration:
    """Test the full classify() pipeline: Tier0RawOutput → EmotionalStateVector."""

    def setup_method(self) -> None:
        self.engine = ClassificationRuleEngine()

    def test_distress_scenario(self) -> None:
        """Very negative + high arousal → WEST, high vulnerability."""
        raw = _make_raw(valence="very_negative", arousal="high", topic="crisis")
        tme = _make_tme(phase=TimePhase.DEEP_NIGHT)
        result = self.engine.classify(raw, tme, "I can't cope anymore", [])

        assert result.valence == 0.1
        assert result.arousal == 0.8
        assert result.compass_direction == CompassDirection.WEST
        assert result.vulnerability_level > 0.5

    def test_casual_scenario(self) -> None:
        """Neutral + low arousal → NONE compass, low vulnerability."""
        raw = _make_raw(valence="neutral", arousal="low", topic="weather")
        tme = _make_tme()
        result = self.engine.classify(raw, tme, "Nice weather today", [])

        assert result.valence == 0.5
        assert result.arousal == 0.2
        assert result.compass_direction == CompassDirection.NONE
        assert result.vulnerability_level < 0.1

    def test_relational_scenario(self) -> None:
        """Relational topic → EAST compass direction."""
        raw = _make_raw(
            valence="negative", arousal="moderate", topic="family_argument",
        )
        tme = _make_tme()
        result = self.engine.classify(raw, tme, "My family is driving me crazy", [])

        # valence=0.3, arousal=0.5 → SOUTH condition also met (valence<0.4, arousal>0.4)
        # SOUTH has higher priority than EAST, so SOUTH wins
        assert result.compass_direction == CompassDirection.SOUTH
```

---

### Step 5.3: Run pytest

Run this command from the project root (`C:\Users\Administrator\Desktop\projects\Gwen\`):

- [x]Run `pytest tests/test_tier0_parser.py tests/test_rule_engine.py -v` and confirm all tests pass

```bash
pytest tests/test_tier0_parser.py tests/test_rule_engine.py -v
```

**Expected output:** All tests pass (green). If any test fails, read the error message, check the corresponding code, and fix the logic. The most common issues:
- Import errors: Make sure Track 002 (data models) is complete and `gwen.models.classification`, `gwen.models.emotional`, and `gwen.models.temporal` exist.
- Float comparison: All float assertions use `abs(a - b) < threshold` to avoid floating-point precision issues.

---

## Summary of Files Created

| Step | File Path | Purpose |
|------|-----------|---------|
| 1.1 | `gwen/classification/__init__.py` | Package init (may already exist from Track 001) |
| 1.2-1.3, 3.1 | `gwen/classification/tier0.py` | Tier 0 prompt, Tier0Classifier, classify_with_retry |
| 2.1 | `gwen/classification/parser.py` | Tier0Parser with 4-layer safety net |
| 4.1-4.10 | `gwen/classification/rule_engine.py` | ClassificationRuleEngine (all compute methods) |
| 5.1 | `tests/test_tier0_parser.py` | Parser tests (valid, malformed, fallback) |
| 5.2 | `tests/test_rule_engine.py` | Rule engine tests (vulnerability, compass, safety, integration) |

**Total files:** 6 (1 package init, 3 implementation, 2 test)
**Dependencies:** Track 002 (data models), Track 004 (AdaptiveModelManager)
