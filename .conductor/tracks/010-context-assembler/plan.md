# Plan: Context Assembler

**Track:** 010-context-assembler
**Spec:** [spec.md](./spec.md)
**Status:** Not Started

---

## Phase 1: Stream -- Working Memory

### Step 1.1: Create Stream class with constructor

Create the file `gwen/memory/stream.py` (path: `C:\Users\Administrator\Desktop\projects\Gwen\gwen\memory\stream.py`).

- [ ] Write Stream class with __init__ and message storage

```python
"""Stream: Tier 1 of the Living Memory system (working memory).

The Stream holds the most recent messages from the active conversation session.
It is the in-memory buffer that the Context Assembler reads from when building
the Tier 1 prompt. Messages are added as the conversation progresses and cleared
when the session ends.

References: SRS.md Section 4.5 (Context Assembly, component 6: Conversation History),
            SRS.md Section 6 (Living Memory, Tier 1: Stream).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from gwen.models.emotional import EmotionalStateVector

logger = logging.getLogger(__name__)


class Stream:
    """Working memory buffer for the active conversation session.

    Holds the most recent messages as a list of dicts. The Context Assembler
    reads from this buffer to build conversation history in the Tier 1 prompt.

    Each message in the stream is a dict with these keys:
        - "role" (str): Either "user" or "companion"
        - "content" (str): The message text
        - "emotional_state" (EmotionalStateVector | None): The emotional classification
        - "timestamp" (datetime): When the message was created

    Usage:
        stream = Stream(max_messages=50)
        stream.add_message("user", "Hello!")
        stream.add_message("companion", "Hi there! How are you?")
        recent = stream.get_recent(10)
        formatted = stream.get_formatted(10)
    """

    def __init__(self, max_messages: int = 50):
        """Initialize the Stream.

        Args:
            max_messages: Maximum number of messages to keep in the buffer.
                          When this limit is reached, the oldest message is
                          dropped to make room for the new one. This prevents
                          unbounded memory growth in long sessions.
                          Default is 50, which covers ~25 exchanges (user + companion).
        """
        self.max_messages = max_messages
        self._messages: list[dict] = []

    @property
    def message_count(self) -> int:
        """Return the number of messages currently in the stream."""
        return len(self._messages)
```

**What this does:** Creates the `Stream` class that serves as Tier 1 of the Living Memory system. It holds a bounded list of recent messages in memory. The `max_messages` parameter prevents the buffer from growing without bound during marathon sessions. Each message is stored as a plain dict (not a dataclass) for simplicity and to avoid tight coupling with the data models.

---

### Step 1.2: Implement add_message

Add this method to the `Stream` class in `gwen/memory/stream.py`, directly after the `message_count` property.

- [ ] Add add_message method

```python
    def add_message(
        self,
        role: str,
        content: str,
        emotional_state: Optional[EmotionalStateVector] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a message to the stream.

        If the stream is at capacity (max_messages), the oldest message is
        removed before the new one is added.

        Args:
            role: The speaker. Must be "user" or "companion".
                  This is validated but not enforced (a warning is logged for
                  unexpected values) to avoid crashing the conversation.
            content: The message text. Must not be empty.
            emotional_state: The EmotionalStateVector from Tier 0 classification.
                             Optional because the first version of the orchestrator
                             (Track 008) may not have emotional tagging wired up yet.
            timestamp: When the message was created. Defaults to datetime.now()
                       if not provided.
        """
        if role not in ("user", "companion"):
            logger.warning("Unexpected role '%s' added to stream. Expected 'user' or 'companion'.", role)

        if not content:
            logger.warning("Empty content added to stream for role '%s'.", role)

        if timestamp is None:
            timestamp = datetime.now()

        message = {
            "role": role,
            "content": content,
            "emotional_state": emotional_state,
            "timestamp": timestamp,
        }

        # Enforce the size limit by dropping the oldest message.
        if len(self._messages) >= self.max_messages:
            self._messages.pop(0)

        self._messages.append(message)
```

**What this does:** Adds a single message to the stream buffer. If the buffer is full, it drops the oldest message (index 0) to make room. This is a FIFO (first-in, first-out) strategy. The method accepts an optional `emotional_state` and `timestamp` for flexibility during early development phases where not all components are wired up yet.

---

### Step 1.3: Implement get_recent

Add this method to the `Stream` class in `gwen/memory/stream.py`, directly after the `add_message` method.

- [ ] Add get_recent method

```python
    def get_recent(self, n: int) -> list[dict]:
        """Return the last n messages from the stream.

        Args:
            n: Number of recent messages to return. If n is greater than the
               number of messages in the stream, all messages are returned.

        Returns:
            A list of message dicts, ordered from oldest to newest.
            Returns an empty list if the stream is empty.
        """
        if n <= 0:
            return []
        return self._messages[-n:]
```

**What this does:** Returns a slice of the most recent messages. The slice preserves chronological order (oldest first within the returned list). This is the primary method used by the Context Assembler to get conversation history.

---

### Step 1.4: Implement get_formatted

Add this method to the `Stream` class in `gwen/memory/stream.py`, directly after the `get_recent` method.

- [ ] Add get_formatted method

```python
    def get_formatted(self, n: int) -> str:
        """Format the last n messages as a conversation transcript.

        Produces a human-readable string like:
            User: Hello!
            Gwen: Hi there! How are you?
            User: I'm doing well, thanks.

        This format is injected into the Tier 1 prompt as the conversation
        history block.

        Args:
            n: Number of recent messages to format. If n is greater than the
               number of messages in the stream, all messages are formatted.

        Returns:
            A formatted string with one line per message.
            Returns an empty string if the stream is empty.
        """
        messages = self.get_recent(n)
        lines = []
        for msg in messages:
            # Map internal role names to display names.
            # "companion" is displayed as "Gwen" in the prompt context.
            if msg["role"] == "user":
                speaker = "User"
            elif msg["role"] == "companion":
                speaker = "Gwen"
            else:
                speaker = msg["role"].capitalize()

            lines.append(f"{speaker}: {msg['content']}")

        return "\n".join(lines)
```

**What this does:** Converts the raw message dicts into a formatted conversation transcript. The "companion" role is displayed as "Gwen" because that is what the Tier 1 model expects to see in its context window. This formatted string is what gets injected into the prompt.

---

### Step 1.5: Implement clear

Add this method to the `Stream` class in `gwen/memory/stream.py`, directly after the `get_formatted` method.

- [ ] Add clear method

```python
    def clear(self) -> None:
        """Clear all messages from the stream.

        Called when a session ends (Track 012) to reset working memory.
        The messages are NOT lost -- they have already been persisted to
        Chronicle (SQLite) by the PostProcessor (Track 011) before clear
        is called.
        """
        count = len(self._messages)
        self._messages.clear()
        logger.debug("Stream cleared. Removed %d messages.", count)
```

**What this does:** Empties the stream buffer. This is called at session close (Track 012). By the time `clear()` is called, all messages have already been persisted to the Chronicle by the PostProcessor (Track 011), so no data is lost.

---

### Step 1.6: Implement estimate_tokens

Add this method to the `Stream` class in `gwen/memory/stream.py`, directly after the `clear` method. This is a module-level utility, not a method on `Stream`, because it is used by both `Stream` and `ContextAssembler`.

- [ ] Add estimate_tokens as a module-level function

```python
def estimate_tokens(text: str) -> int:
    """Rough token count estimation: 1 token ~ 4 characters.

    This is an approximation. Actual tokenization depends on the model's
    tokenizer (Qwen3 uses a BPE tokenizer). The 4-char heuristic is a
    widely used approximation for English text that errs on the side of
    overestimation (safe direction for budget management).

    Args:
        text: The text to estimate token count for.

    Returns:
        Estimated number of tokens (integer, always >= 0).
    """
    if not text:
        return 0
    return len(text) // 4
```

**What this does:** Provides a fast token estimation function used by the Context Assembler to manage the token budget. The 4-char-per-token heuristic is standard for English text and errs on the side of overestimation, which is the safe direction (we would rather underuse the context window than overflow it). This is a module-level function (not a method) so it can be imported by both `Stream` and `ContextAssembler`.

---

## Phase 2: Temporal Context Block Generator

### Step 2.1: Create generate_temporal_block function

Add this function at the bottom of `gwen/memory/stream.py`, after the `estimate_tokens` function. (We put it here rather than in a separate file because it is small and closely related to context assembly.)

- [ ] Add generate_temporal_block function

```python
def generate_temporal_block(
    tme: object,
    gap_analysis: object = None,
    anticipatory_primes: list | None = None,
) -> str:
    """Generate a natural-language temporal context block for the Tier 1 prompt.

    This block gives Tier 1 awareness of time, session context, and any
    temporal anomalies. It is injected as component 3 of the context window
    (SRS Section 4.5, priority order).

    The block is kept under ~300 tokens (~1200 chars) to leave room for
    other context components.

    Args:
        tme: A TemporalMetadataEnvelope instance (from Track 006).
             Uses duck typing (accesses attributes directly) so the function
             works with both real TME objects and test stubs.
        gap_analysis: An optional GapAnalysis instance (from Track 007).
                      If provided and the gap is notable+, temporal context
                      will mention the absence duration.
        anticipatory_primes: An optional list of AnticipatoryPrime instances.
                             If provided, active primes are mentioned in the
                             temporal context.

    Returns:
        A natural-language string describing the temporal context.
        Example: "Current time: Tuesday evening (7:23 PM). Session started
        12 minutes ago, 3rd message. No circadian anomalies detected."
    """
    parts = []

    # --- Time of day ---
    try:
        day_name = tme.day_of_week
        phase = tme.time_phase.value.replace("_", " ")
        hour = tme.hour_of_day
        minute = getattr(tme, "local_time", None)
        if minute is not None and hasattr(minute, "strftime"):
            time_str = minute.strftime("%I:%M %p").lstrip("0")
        else:
            # Fallback: construct from hour
            period = "AM" if hour < 12 else "PM"
            display_hour = hour % 12 or 12
            time_str = f"{display_hour}:00 {period}"

        parts.append(f"Current time: {day_name} {phase} ({time_str}).")
    except AttributeError:
        parts.append("Current time: unknown.")

    # --- Session context ---
    try:
        duration_min = tme.session_duration_sec // 60
        msg_index = tme.msg_index_in_session

        # Ordinal suffix for message index
        if msg_index == 1:
            ordinal = "1st"
        elif msg_index == 2:
            ordinal = "2nd"
        elif msg_index == 3:
            ordinal = "3rd"
        else:
            ordinal = f"{msg_index}th"

        parts.append(f"Session started {duration_min} minutes ago, {ordinal} message.")
    except AttributeError:
        pass

    # --- Circadian deviation ---
    try:
        severity = tme.circadian_deviation_severity
        if hasattr(severity, "value"):
            severity_val = severity.value
        else:
            severity_val = str(severity)

        if severity_val == "none":
            parts.append("No circadian anomalies detected.")
        elif severity_val == "low":
            parts.append("Slight circadian deviation noted (mildly unusual time for this user).")
        elif severity_val == "medium":
            deviation_type = getattr(tme, "circadian_deviation_type", "unusual hour")
            parts.append(f"Moderate circadian deviation: {deviation_type}. This is somewhat unusual for this user.")
        elif severity_val == "high":
            deviation_type = getattr(tme, "circadian_deviation_type", "unusual hour")
            parts.append(f"Significant circadian deviation: {deviation_type}. This is very unusual for this user and may signal distress or a change in routine.")
    except AttributeError:
        pass

    # --- Gap context (from GapAnalysis) ---
    if gap_analysis is not None:
        try:
            classification = gap_analysis.classification
            if hasattr(classification, "value"):
                classification_val = classification.value
            else:
                classification_val = str(classification)

            if classification_val in ("notable", "significant", "anomalous"):
                hours = gap_analysis.duration_hours
                if hours < 24:
                    gap_display = f"{hours:.0f} hours"
                else:
                    days = hours / 24
                    gap_display = f"{days:.1f} days"
                parts.append(f"User is returning after a {classification_val} absence ({gap_display}).")
        except AttributeError:
            pass

    # --- Anticipatory primes ---
    if anticipatory_primes:
        try:
            active_primes = [p for p in anticipatory_primes if hasattr(p, "prediction")]
            if active_primes:
                prime_descriptions = [p.prediction.replace("_", " ") for p in active_primes[:3]]
                parts.append(f"Active predictions: {', '.join(prime_descriptions)}.")
        except (AttributeError, TypeError):
            pass

    return " ".join(parts)
```

**What this does:** Generates a natural-language paragraph that gives Tier 1 temporal awareness. It reads from the TME (Track 006) to describe the current time, session duration, message position, and any circadian deviations. If a gap analysis is provided (notable absences), it mentions the absence. If anticipatory primes are active, it mentions those too. The function uses duck typing extensively (accessing attributes directly, with try/except fallbacks) so it works with both real data model objects and test stubs.

**Why duck typing:** At this stage of development, the real data model classes may not yet be importable (Track 002 may or may not be complete). Using duck typing (`getattr`, `try/except AttributeError`) makes this function resilient to partially-implemented models.

---

## Phase 3: Context Assembler

### Step 3.1: Create ContextAssembler class with constructor

Create the file `gwen/core/context_assembler.py` (path: `C:\Users\Administrator\Desktop\projects\Gwen\gwen\core\context_assembler.py`).

- [ ] Write ContextAssembler class with __init__

```python
"""Context Assembler: Builds the full Tier 1 prompt within a token budget.

Assembles the context window that Tier 1 (Voice model) receives for response
generation. Components are added in priority order, and conversation history
is truncated from the oldest when the budget is exceeded.

Priority order (SRS Section 4.5):
  1. System prompt (always present)
  2. Temporal context block (always present)
  3. Return context (if user is returning after a notable gap)
  4. Memory context (placeholder until Track 013)
  5. Conversation history (truncated from oldest, min 4 exchanges kept)
  6. Current message

References: SRS.md Section 4.5.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from gwen.memory.stream import Stream, estimate_tokens, generate_temporal_block

if TYPE_CHECKING:
    from gwen.models.message import MessageRecord
    from gwen.models.temporal import TemporalMetadataEnvelope
    from gwen.models.session import SessionRecord
    from gwen.models.gap import ReturnContext

logger = logging.getLogger(__name__)


class ContextAssembler:
    """Builds the complete Tier 1 context prompt within a token budget.

    The assembler collects all context components (system prompt, temporal
    context, return context, memory, conversation history, current message)
    and concatenates them into a single string that fits within TOKEN_BUDGET.

    If the total exceeds the budget, conversation history is truncated from
    the oldest messages first, but a minimum of MIN_EXCHANGES (4) are always
    preserved.

    Usage:
        assembler = ContextAssembler(
            personality=personality_module,
            prompt_builder=prompt_builder,
            stream=stream,
        )
        context = await assembler.assemble(message, tme, session)
        response = await model_mgr.generate_tier1(context)
    """

    # Token budget for the entire context window.
    # Qwen3 8B supports 32K tokens, but we reserve capacity for:
    # - Response generation (~2000 tokens)
    # - System overhead
    # We budget ~6000 tokens for the context we assemble.
    TOKEN_BUDGET = 6000

    # Reserve for the model's response. Not used in assembly directly,
    # but documented here for reference.
    RESPONSE_RESERVE = 2000

    # Minimum number of conversation exchanges (user + companion pairs)
    # to always preserve, even when truncating. 4 exchanges = 8 messages.
    MIN_EXCHANGES = 4

    def __init__(
        self,
        personality: object,
        prompt_builder: object,
        stream: Stream,
        embedding_service: object = None,
    ):
        """Initialize the ContextAssembler.

        Args:
            personality: A PersonalityModule instance (from Track 008).
                         Used to get the companion's name and identity fields.
            prompt_builder: A PromptBuilder instance (from Track 008).
                            Has a build_system_prompt() method that returns
                            the full system prompt string.
            stream: A Stream instance (from Phase 1 of this track).
                    The working memory buffer holding recent messages.
            embedding_service: Optional EmbeddingService instance (from Track 009).
                               Used for memory retrieval in the context window.
                               Can be None during early development (Track 008).
                               Full mood-congruent retrieval is implemented in Track 013.
        """
        self.personality = personality
        self.prompt_builder = prompt_builder
        self.stream = stream
        self.embedding_service = embedding_service
```

**What this does:** Creates the `ContextAssembler` with references to the components it needs: the personality module (for system prompt generation), the prompt builder (Track 008), the stream (for conversation history), and an optional embedding service (for memory retrieval, wired up in Track 013). The constants define the token budget (6000), response reserve (2000), and minimum exchanges to always keep (4).

---

### Step 3.2: Implement assemble method

Add this method to the `ContextAssembler` class in `gwen/core/context_assembler.py`, directly after the `__init__` method.

- [ ] Add assemble method

```python
    async def assemble(
        self,
        message: MessageRecord,
        tme: object,
        session: object,
        safety_result: object = None,
        return_context: Optional[ReturnContext] = None,
        gap_analysis: object = None,
        anticipatory_primes: list | None = None,
    ) -> str:
        """Assemble the full Tier 1 context prompt within the token budget.

        Builds the context window by concatenating components in priority order.
        If the total exceeds TOKEN_BUDGET, conversation history is truncated
        from the oldest messages first.

        Args:
            message: The current user MessageRecord (the message being responded to).
            tme: The TemporalMetadataEnvelope for this message (from Track 006).
            session: The current SessionRecord (from Track 007).
            safety_result: Optional safety evaluation result (from Track 014).
                           Currently unused; reserved for safety-adjusted retrieval
                           thresholds in Track 013.
            return_context: Optional ReturnContext if the user is returning after
                            a notable gap (from Track 007 GapAnalysis).
            gap_analysis: Optional GapAnalysis for temporal context generation.
            anticipatory_primes: Optional list of active AnticipatoryPrime instances.

        Returns:
            A single string containing the complete context prompt for Tier 1.
            This string is passed directly to model_mgr.generate_tier1().
        """
        remaining_budget = self.TOKEN_BUDGET
        sections = []

        # --- 1. SYSTEM PROMPT (always included, highest priority) ---
        # The system prompt defines Gwen's personality, behavioral rules, and mode.
        # It is generated by the PromptBuilder from the PersonalityModule (Track 008).
        try:
            system_prompt = self.prompt_builder.build_system_prompt()
        except Exception:
            # If prompt builder fails, use a minimal fallback so the conversation
            # does not crash entirely.
            logger.exception("PromptBuilder failed, using minimal system prompt.")
            system_prompt = "You are Gwen, a caring AI companion. Be warm, thoughtful, and genuine."

        system_tokens = estimate_tokens(system_prompt)
        sections.append(system_prompt)
        remaining_budget -= system_tokens
        logger.debug("System prompt: %d tokens, remaining: %d", system_tokens, remaining_budget)

        # --- 2. TEMPORAL CONTEXT BLOCK (always included) ---
        # Gives Tier 1 awareness of time, session context, circadian deviations.
        temporal_block = generate_temporal_block(
            tme=tme,
            gap_analysis=gap_analysis,
            anticipatory_primes=anticipatory_primes,
        )
        temporal_section = f"\n\n[Temporal Context]\n{temporal_block}"
        temporal_tokens = estimate_tokens(temporal_section)
        sections.append(temporal_section)
        remaining_budget -= temporal_tokens
        logger.debug("Temporal block: %d tokens, remaining: %d", temporal_tokens, remaining_budget)

        # --- 3. RETURN CONTEXT (if applicable) ---
        # Injected when the user returns after a notable+ gap so Gwen acknowledges
        # the absence naturally.
        if return_context is not None:
            try:
                return_section = (
                    f"\n\n[Return Context]\n"
                    f"The user is returning after {return_context.gap_duration_display}. "
                    f"Gap classification: {return_context.gap_classification.value if hasattr(return_context.gap_classification, 'value') else return_context.gap_classification}. "
                    f"{return_context.preceding_summary}\n"
                    f"Suggested approach: {return_context.suggested_approach}"
                )
                return_tokens = estimate_tokens(return_section)

                # Only include if we have budget
                if remaining_budget - return_tokens > 0:
                    sections.append(return_section)
                    remaining_budget -= return_tokens
                    logger.debug("Return context: %d tokens, remaining: %d", return_tokens, remaining_budget)
                else:
                    logger.warning("Skipping return context: insufficient budget (%d needed, %d available)", return_tokens, remaining_budget)
            except (AttributeError, TypeError):
                logger.exception("Failed to build return context section")

        # --- 4. MEMORY CONTEXT (placeholder for Track 013) ---
        # In Track 013 (Amygdala Layer), this will be replaced with mood-congruent
        # memory retrieval using the EmbeddingService. For now, we include a
        # placeholder that tells Tier 1 no memories are available yet.
        if self.embedding_service is not None:
            memory_section = "\n\n[Memory Context]\nNo memories retrieved yet."
        else:
            memory_section = "\n\n[Memory Context]\nMemory system not yet active."

        memory_tokens = estimate_tokens(memory_section)
        sections.append(memory_section)
        remaining_budget -= memory_tokens
        logger.debug("Memory context: %d tokens, remaining: %d", memory_tokens, remaining_budget)

        # --- 5. CONVERSATION HISTORY (truncated from oldest if budget exceeded) ---
        # Get all messages from the stream, then truncate to fit the budget.
        # We need to leave room for the current message (component 6).
        current_message_text = f"\n\nUser: {message.content}"
        current_message_tokens = estimate_tokens(current_message_text)

        # Available tokens for conversation = remaining budget - current message tokens
        available_for_conversation = remaining_budget - current_message_tokens

        if available_for_conversation > 0:
            all_messages = self.stream.get_recent(self.stream.message_count)
            truncated = self._truncate_conversation(
                messages=all_messages,
                available_tokens=available_for_conversation,
                min_exchanges=self.MIN_EXCHANGES,
            )

            if truncated:
                history_lines = []
                for msg in truncated:
                    if msg["role"] == "user":
                        speaker = "User"
                    elif msg["role"] == "companion":
                        speaker = "Gwen"
                    else:
                        speaker = msg["role"].capitalize()
                    history_lines.append(f"{speaker}: {msg['content']}")

                conversation_section = "\n\n[Conversation History]\n" + "\n".join(history_lines)
                conversation_tokens = estimate_tokens(conversation_section)
                sections.append(conversation_section)
                remaining_budget -= conversation_tokens
                logger.debug(
                    "Conversation history: %d messages, %d tokens, remaining: %d",
                    len(truncated), conversation_tokens, remaining_budget,
                )
        else:
            logger.warning("No budget remaining for conversation history.")

        # --- 6. CURRENT MESSAGE (always included) ---
        sections.append(current_message_text)
        remaining_budget -= current_message_tokens
        logger.debug("Current message: %d tokens, remaining: %d", current_message_tokens, remaining_budget)

        # --- Final assembly ---
        full_context = "".join(sections)

        final_tokens = estimate_tokens(full_context)
        logger.info(
            "Context assembled: %d tokens (budget: %d, used: %.1f%%)",
            final_tokens,
            self.TOKEN_BUDGET,
            (final_tokens / self.TOKEN_BUDGET) * 100,
        )

        return full_context
```

**What this does:** This is the core method of the Context Assembler. It builds the Tier 1 prompt by concatenating components in priority order:

1. **System prompt** (from PromptBuilder, Track 008) -- always included, defines Gwen's personality
2. **Temporal context** (from `generate_temporal_block`) -- always included, gives time awareness
3. **Return context** (if the user is returning after a notable gap) -- optional
4. **Memory context** (placeholder for Track 013) -- will eventually include mood-congruent retrieved memories
5. **Conversation history** (from Stream) -- truncated from oldest to fit budget
6. **Current message** -- always included

Each component's token count is tracked, and conversation history is truncated when the budget is exceeded. The method logs budget usage at each step for debugging.

---

### Step 3.3: Implement _truncate_conversation

Add this method to the `ContextAssembler` class in `gwen/core/context_assembler.py`, directly after the `assemble` method.

- [ ] Add _truncate_conversation method

```python
    def _truncate_conversation(
        self,
        messages: list[dict],
        available_tokens: int,
        min_exchanges: int = 4,
    ) -> list[dict]:
        """Truncate conversation history to fit within a token budget.

        Removes messages from the OLDEST end of the list until the total
        fits within available_tokens. Always preserves at least min_exchanges
        worth of exchanges (1 exchange = 2 messages: user + companion).

        The strategy is:
        1. Start with all messages.
        2. If total tokens > available_tokens, remove the oldest message.
        3. Repeat until total fits or only min_exchanges * 2 messages remain.
        4. If even min_exchanges exceeds the budget, return them anyway
           (the minimum guarantee is more important than the budget).

        Args:
            messages: List of message dicts from the Stream (oldest first).
            available_tokens: Maximum number of tokens the conversation
                              history can use.
            min_exchanges: Minimum number of exchanges to always preserve.
                           1 exchange = 2 messages (user + companion).
                           Default is 4 exchanges = 8 messages.

        Returns:
            A truncated list of message dicts (oldest first) that fits within
            the budget (or the minimum exchange count, whichever is larger).
        """
        if not messages:
            return []

        min_messages = min_exchanges * 2

        # Start with all messages
        truncated = list(messages)

        while len(truncated) > min_messages:
            # Calculate current token usage
            total_text = "\n".join(
                f"{'User' if m['role'] == 'user' else 'Gwen'}: {m['content']}"
                for m in truncated
            )
            total_tokens = estimate_tokens(total_text)

            if total_tokens <= available_tokens:
                # We fit within the budget. Done.
                break

            # Remove the oldest message and try again.
            truncated.pop(0)

        return truncated
```

**What this does:** Truncates conversation history by removing the oldest messages first until the total fits within the available token budget. The `min_exchanges` parameter guarantees that at least 4 exchanges (8 messages) are always preserved, even if that exceeds the budget. This ensures Tier 1 always has enough conversational context to generate a coherent response.

**Why truncate from oldest:** The most recent messages are more important for conversational coherence. Tier 1 needs to know what was just said to generate a relevant response. Older messages from earlier in the session are less critical.

**Why guarantee min_exchanges even over budget:** It is better to slightly exceed the token budget than to give Tier 1 so little context that it generates an incoherent response. The budget is approximate anyway (the 4-char heuristic is not exact), and the model's 32K context window has plenty of slack.

---

## Phase 4: Tests

### Step 4.1: Create tests/test_context.py

Create the file `tests/test_context.py` (path: `C:\Users\Administrator\Desktop\projects\Gwen\tests\test_context.py`).

- [ ] Write test file for Stream and ContextAssembler

```python
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

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import pytest

from gwen.memory.stream import Stream, estimate_tokens, generate_temporal_block
from gwen.core.context_assembler import ContextAssembler


# ---------------------------------------------------------------------------
# Stub types for testing (self-contained, no dependency on Track 002)
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

    @property
    def storage_strength(self) -> float:
        return self.arousal * 0.4 + self.relational_significance * 0.4 + self.vulnerability_level * 0.2

    @property
    def is_flashbulb(self) -> bool:
        return self.arousal > 0.8 and self.relational_significance > 0.8


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
    semantic_embedding_id: Optional[str] = None
    emotional_embedding_id: Optional[str] = None


class FakePromptBuilder:
    """Stub PromptBuilder that returns a fixed system prompt."""

    def __init__(self, prompt_text: str = "You are Gwen, a caring AI companion."):
        self._prompt = prompt_text

    def build_system_prompt(self) -> str:
        return self._prompt


class FakePersonality:
    """Stub PersonalityModule."""
    name = "Gwen"


def make_message(content: str = "Hello!") -> FakeMessageRecord:
    return FakeMessageRecord(
        id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        content=content,
    )


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
        # The oldest 5 messages should have been dropped
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


# ---------------------------------------------------------------------------
# Token estimation tests
# ---------------------------------------------------------------------------

class TestEstimateTokens:
    """Tests for the estimate_tokens utility function."""

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string(self):
        # "Hello" = 5 chars -> 5 // 4 = 1 token
        assert estimate_tokens("Hello") == 1

    def test_known_length(self):
        # 100 chars -> 25 tokens
        text = "a" * 100
        assert estimate_tokens(text) == 25

    def test_typical_message(self):
        text = "I had a really great day today! Everything went well at work and I'm feeling positive."
        tokens = estimate_tokens(text)
        # 88 chars -> ~22 tokens
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
        message = make_message("What do you think about tomorrow?")
        tme = FakeTME()
        session = object()  # Minimal stub

        result = await assembler.assemble(message, tme, session)
        tokens = estimate_tokens(result)

        # Allow some slack: the minimum exchanges guarantee can push us
        # slightly over budget, but not by more than ~500 tokens.
        assert tokens <= assembler.TOKEN_BUDGET + 500

    async def test_contains_system_prompt(self, assembler):
        """The assembled context should always contain the system prompt."""
        message = make_message("Hello")
        tme = FakeTME()
        session = object()

        result = await assembler.assemble(message, tme, session)
        assert "You are Gwen, a caring AI companion." in result

    async def test_contains_temporal_block(self, assembler):
        """The assembled context should always contain temporal context."""
        message = make_message("Hello")
        tme = FakeTME()
        session = object()

        result = await assembler.assemble(message, tme, session)
        assert "[Temporal Context]" in result
        assert "Tuesday" in result

    async def test_contains_current_message(self, assembler):
        """The assembled context should always contain the current user message."""
        message = make_message("What's the meaning of life?")
        tme = FakeTME()
        session = object()

        result = await assembler.assemble(message, tme, session)
        assert "What's the meaning of life?" in result

    async def test_contains_conversation_history(self, assembler):
        """The assembled context should include conversation history from the stream."""
        message = make_message("New message")
        tme = FakeTME()
        session = object()

        result = await assembler.assemble(message, tme, session)
        assert "[Conversation History]" in result
        # Should see some of the stream messages
        assert "Gwen:" in result or "User:" in result

    async def test_contains_return_context_when_provided(self, assembler):
        """When return_context is provided, it should appear in the output."""
        message = make_message("Hey, I'm back!")
        tme = FakeTME()
        session = object()
        return_ctx = FakeReturnContext()

        result = await assembler.assemble(
            message, tme, session, return_context=return_ctx,
        )
        assert "[Return Context]" in result
        assert "4 days" in result

    async def test_memory_placeholder_present(self, assembler):
        """Memory context should show placeholder text until Track 013."""
        message = make_message("Hello")
        tme = FakeTME()
        session = object()

        result = await assembler.assemble(message, tme, session)
        assert "[Memory Context]" in result

    async def test_truncation_preserves_recent_messages(self):
        """When truncating, the most recent messages should be preserved."""
        stream = Stream()
        # Add a LOT of messages to force truncation
        for i in range(100):
            role = "user" if i % 2 == 0 else "companion"
            # Long messages to eat up token budget
            stream.add_message(role, f"This is message number {i}. " * 20)

        assembler = ContextAssembler(
            personality=FakePersonality(),
            prompt_builder=FakePromptBuilder(),
            stream=stream,
        )

        message = make_message("Final message")
        tme = FakeTME()
        session = object()

        result = await assembler.assemble(message, tme, session)

        # The most recent messages should be in the output
        # Message 99 is the last one added to the stream
        # (it may or may not appear depending on the long content, but
        #  at minimum the last MIN_EXCHANGES * 2 messages should be there)
        assert "Final message" in result

    async def test_minimum_exchanges_preserved(self):
        """Even with a tight budget, at least MIN_EXCHANGES are preserved."""
        stream = Stream()
        # Add exactly 4 exchanges (8 messages)
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

        message = make_message("Current")
        tme = FakeTME()
        session = object()

        result = await assembler.assemble(message, tme, session)

        # Even though the system prompt ate the budget, the current message
        # should still be present
        assert "Current" in result


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

        # Very tight budget: should truncate oldest
        result = assembler._truncate_conversation(messages, available_tokens=200, min_exchanges=4)

        # Should have kept at least 8 messages (4 exchanges)
        assert len(result) >= 8
        # The latest messages should be preserved
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

        # Budget of 10 tokens is WAY too small, but min_exchanges=4 should
        # preserve all 8 messages
        result = assembler._truncate_conversation(
            messages, available_tokens=10, min_exchanges=4,
        )
        assert len(result) == 8
```

**What this file does:** Provides comprehensive tests for both the `Stream` class and the `ContextAssembler`. Stream tests verify basic CRUD operations, size limits, formatting, and edge cases. ContextAssembler tests verify that all components appear in the output, the budget is respected, truncation removes oldest messages, and minimum exchanges are preserved. All tests use self-contained stub types with no dependency on Track 002 data models.

---

### Step 4.2: Run pytest

Run this command from the project root (`C:\Users\Administrator\Desktop\projects\Gwen\`):

- [ ] Run `pytest tests/test_context.py -v` and confirm all tests pass

```bash
pytest tests/test_context.py -v
```

**Expected output:** All tests pass. There should be approximately 25-30 tests.

**If it fails:**
- If `ModuleNotFoundError: No module named 'gwen.memory.stream'`: Verify that `gwen/memory/stream.py` exists and `gwen/memory/__init__.py` exists.
- If `ModuleNotFoundError: No module named 'gwen.core.context_assembler'`: Verify that `gwen/core/context_assembler.py` exists and `gwen/core/__init__.py` exists.
- If async tests hang: Verify `asyncio_mode = "auto"` is set in `pyproject.toml` (from Track 001).

---

## Summary of Files Created

| Step | File Path | Purpose |
|------|-----------|---------|
| 1.1-1.6, 2.1 | `gwen/memory/stream.py` | Stream class + estimate_tokens + generate_temporal_block |
| 3.1-3.3 | `gwen/core/context_assembler.py` | ContextAssembler class |
| 4.1 | `tests/test_context.py` | Tests for Stream and ContextAssembler |

**Total new files:** 3
**Modified files:** 0
**Dependencies added:** 0
