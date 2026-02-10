"""Context Assembler: Builds the full Tier 1 prompt within a token budget.

Assembles the context window that Tier 1 (Voice model) receives for response
generation. Components are added in priority order, and conversation history
is truncated from the oldest when the budget is exceeded.

Priority order (SRS Section 4.5):
  1. System prompt (always present)
  2. Temporal context block (always present)
  3. Return context (if user is returning after a notable gap)
  4. Memory context (placeholder until Track 013 wires mood-congruent retrieval)
  5. Conversation history (truncated from oldest, min 4 exchanges kept)
  6. Current message

References: SRS.md Section 4.5.
"""

from __future__ import annotations

import logging

from gwen.memory.stream import Stream, estimate_tokens, generate_temporal_block

logger = logging.getLogger(__name__)


class ContextAssembler:
    """Builds the complete Tier 1 context prompt within a token budget.

    If the total exceeds the budget, conversation history is truncated from
    the oldest messages first, but a minimum of MIN_EXCHANGES (4) are always
    preserved.

    Usage:
        assembler = ContextAssembler(
            personality=personality_module,
            prompt_builder=prompt_builder,
            stream=stream,
        )
        context = await assembler.assemble(
            message_content="Hello!",
            tme=tme,
            session=session,
        )
    """

    TOKEN_BUDGET = 6000
    RESPONSE_RESERVE = 2000
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
            personality: A PersonalityModule instance (Track 008).
            prompt_builder: A PromptBuilder instance (Track 008).
                            Must have build_system_prompt(personality, mode, ...).
            stream: A Stream instance holding recent messages.
            embedding_service: Optional EmbeddingService (Track 009).
        """
        self.personality = personality
        self.prompt_builder = prompt_builder
        self.stream = stream
        self.embedding_service = embedding_service

    async def assemble(
        self,
        message_content: str,
        tme: object,
        session: object,
        emotional_state: object = None,
        mode: str = "grounded",
        safety_result: object = None,
        return_context: object = None,
        gap_analysis: object = None,
        anticipatory_primes: list | None = None,
    ) -> str:
        """Assemble the full Tier 1 context prompt within the token budget.

        Args:
            message_content: The current user message text.
            tme: The TemporalMetadataEnvelope for this message.
            session: The current SessionRecord.
            emotional_state: Optional EmotionalStateVector for context-dependent
                             prompt sections (emotional prompt, compass direction).
            mode: "grounded" or "immersion". Default: "grounded".
            safety_result: Optional safety evaluation result (reserved for Track 014).
            return_context: Optional ReturnContext for gap-based context.
            gap_analysis: Optional GapAnalysis for temporal context generation.
            anticipatory_primes: Optional list of active AnticipatoryPrime instances.

        Returns:
            A single string containing the complete context prompt for Tier 1.
        """
        remaining_budget = self.TOKEN_BUDGET
        sections = []

        # --- 1. SYSTEM PROMPT (always included, highest priority) ---
        try:
            compass_direction = None
            include_emotional = False
            return_context_block = ""

            if emotional_state is not None:
                compass_direction = getattr(emotional_state, "compass_direction", None)
                arousal = getattr(emotional_state, "arousal", 0.0)
                include_emotional = arousal > 0.6

            if return_context is not None:
                try:
                    gap_class = return_context.gap_classification
                    gap_class_val = gap_class.value if hasattr(gap_class, "value") else str(gap_class)
                    return_context_block = (
                        f"The user is returning after {return_context.gap_duration_display}. "
                        f"Gap classification: {gap_class_val}. "
                        f"{return_context.preceding_summary} "
                        f"Suggested approach: {return_context.suggested_approach}"
                    )
                except AttributeError:
                    logger.exception("Failed to build return context block")

            # Build system prompt args based on what PromptBuilder accepts
            build_kwargs = {"personality": self.personality, "mode": mode}
            if compass_direction is not None:
                build_kwargs["compass_direction"] = compass_direction
            if include_emotional:
                build_kwargs["include_emotional"] = True
            if return_context_block:
                build_kwargs["return_context_block"] = return_context_block

            system_prompt = self.prompt_builder.build_system_prompt(**build_kwargs)
        except Exception:
            logger.exception("PromptBuilder failed, using minimal system prompt.")
            system_prompt = "You are Gwen, a caring AI companion. Be warm, thoughtful, and genuine."

        system_tokens = estimate_tokens(system_prompt)
        sections.append(system_prompt)
        remaining_budget -= system_tokens
        logger.debug("System prompt: %d tokens, remaining: %d", system_tokens, remaining_budget)

        # --- 2. TEMPORAL CONTEXT BLOCK (always included) ---
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

        # --- 3. MEMORY CONTEXT (placeholder for Track 013) ---
        if self.embedding_service is not None:
            memory_section = "\n\n[Memory Context]\nNo memories retrieved yet."
        else:
            memory_section = "\n\n[Memory Context]\nMemory system not yet active."

        memory_tokens = estimate_tokens(memory_section)
        sections.append(memory_section)
        remaining_budget -= memory_tokens
        logger.debug("Memory context: %d tokens, remaining: %d", memory_tokens, remaining_budget)

        # --- 4. CONVERSATION HISTORY (truncated from oldest if budget exceeded) ---
        current_message_text = f"\n\nUser: {message_content}"
        current_message_tokens = estimate_tokens(current_message_text)

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

        # --- 5. CURRENT MESSAGE (always included) ---
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

    def _truncate_conversation(
        self,
        messages: list[dict],
        available_tokens: int,
        min_exchanges: int = 4,
    ) -> list[dict]:
        """Truncate conversation history to fit within a token budget.

        Removes messages from the OLDEST end until the total fits.
        Always preserves at least min_exchanges * 2 messages, even if
        that exceeds the budget (the minimum guarantee takes priority).
        """
        if not messages:
            return []

        min_messages = min_exchanges * 2
        truncated = list(messages)

        while len(truncated) > min_messages:
            total_text = "\n".join(
                f"{'User' if m['role'] == 'user' else 'Gwen'}: {m['content']}"
                for m in truncated
            )
            total_tokens = estimate_tokens(total_text)

            if total_tokens <= available_tokens:
                break

            truncated.pop(0)

        return truncated
