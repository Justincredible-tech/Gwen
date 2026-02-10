"""Response Post-Processing: Phase 7 of the message lifecycle.

After Tier 1 generates a response, the PostProcessor:
1. Classifies the companion's response emotionally (Tier 0 + Rule Engine)
2. Creates a companion MessageRecord
3. Stores both user and companion messages in Chronicle (SQLite)
4. Adds both messages to the Stream (working memory)
5. Updates session statistics (companion message count)
6. Generates embeddings for both messages (async, non-blocking)

References: SRS.md Section 4.7.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.messages import MessageRecord

logger = logging.getLogger(__name__)


class PostProcessor:
    """Handles Phase 7 of the message lifecycle: response post-processing.

    After Tier 1 generates a response text, the PostProcessor performs all
    bookkeeping: emotional tagging of the response, Chronicle storage,
    Stream update, session stat tracking, and async embedding generation.

    Dependencies are accepted as objects (duck typing) to avoid circular
    imports. This is consistent with the pattern used in ContextAssembler.
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
        self.tier0_classifier = tier0_classifier
        self.rule_engine = rule_engine
        self.chronicle = chronicle
        self.embedding_service = embedding_service
        self.stream = stream
        self.session_manager = session_manager

    async def process(
        self,
        user_message: MessageRecord,
        response_text: str,
        tme: object,
    ) -> MessageRecord:
        """Process a Tier 1 response through all Phase 7 steps.

        Args:
            user_message: The user's MessageRecord (already classified).
            response_text: The raw text from Tier 1.
            tme: The TemporalMetadataEnvelope for this exchange.

        Returns:
            A fully populated companion MessageRecord.
        """
        start_time = datetime.now()

        # Step 1: Classify companion response emotionally
        companion_emotional_state = await self._classify_response(
            response_text, tme
        )

        # Step 2: Create companion MessageRecord
        companion_message = self._create_companion_message(
            response_text=response_text,
            session_id=user_message.session_id,
            tme=tme,
            emotional_state=companion_emotional_state,
        )

        # Step 3: Store user message in Chronicle
        try:
            self.chronicle.insert_message(user_message)
        except Exception:
            logger.exception("Failed to store user message in Chronicle")

        # Step 4: Store companion message in Chronicle
        try:
            self.chronicle.insert_message(companion_message)
        except Exception:
            logger.exception("Failed to store companion message in Chronicle")

        # Step 5: Add both to Stream (working memory)
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

        # Step 6: Update session statistics (companion message only;
        # the user message is already tracked by the orchestrator before
        # response generation, which preserves correct latency measurement)
        try:
            self.session_manager.add_message("companion")
        except Exception:
            logger.exception("Failed to update session statistics")

        # Step 7: Generate embeddings (async, non-blocking)
        if self.embedding_service is not None:
            asyncio.create_task(
                self._generate_embeddings_background(
                    [user_message, companion_message]
                )
            )

        # Step 8: Log and return
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(
            "Post-processing complete (%.1fms). User: %s, Companion: %s",
            elapsed_ms,
            user_message.id,
            companion_message.id,
        )

        return companion_message

    async def _classify_response(
        self,
        response_text: str,
        tme: object,
    ) -> EmotionalStateVector:
        """Classify the companion's response through Tier 0 + Rule Engine.

        Returns a neutral fallback state if classification fails.
        """
        try:
            # Build TME summary for Tier 0 prompt
            tme_summary = ""
            try:
                tme_summary = f"{tme.time_phase.value}, {tme.day_of_week}"
            except AttributeError:
                pass

            # Format recent messages from Stream as a string for Tier 0
            recent_str = "(no prior messages)"
            try:
                recent = self.stream.get_recent(3)
                if recent:
                    lines = []
                    for m in recent:
                        role = "User" if m["role"] == "user" else "Gwen"
                        lines.append(f"{role}: {m['content'][:100]}")
                    recent_str = "\n".join(lines)
            except (AttributeError, TypeError):
                pass

            # Tier 0 classification
            tier0_output = await self.tier0_classifier.classify(
                message=response_text,
                tme_summary=tme_summary,
                recent_messages=recent_str,
            )

            # Rule Engine: compute full EmotionalStateVector
            recent_texts: list[str] = []
            try:
                recent_texts = [m["content"] for m in self.stream.get_recent(3)]
            except (AttributeError, TypeError):
                pass

            emotional_state = self.rule_engine.classify(
                raw=tier0_output,
                tme=tme,
                message=response_text,
                recent_messages=recent_texts,
            )

            return emotional_state

        except Exception:
            logger.exception(
                "Failed to classify companion response. Using neutral fallback."
            )
            return self._neutral_fallback()

    def _neutral_fallback(self) -> EmotionalStateVector:
        """Create a neutral EmotionalStateVector for fallback scenarios."""
        return EmotionalStateVector(
            valence=0.5,
            arousal=0.3,
            dominance=0.5,
            relational_significance=0.3,
            vulnerability_level=0.2,
            compass_direction=CompassDirection.NONE,
        )

    def _create_companion_message(
        self,
        response_text: str,
        session_id: str,
        tme: object,
        emotional_state: EmotionalStateVector,
    ) -> MessageRecord:
        """Create a companion MessageRecord with full metadata."""
        return MessageRecord(
            id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=datetime.now(),
            sender="companion",
            content=response_text,
            tme=tme,
            emotional_state=emotional_state,
            storage_strength=emotional_state.storage_strength,
            is_flashbulb=emotional_state.is_flashbulb,
            compass_direction=emotional_state.compass_direction,
            compass_skill_used=None,
        )

    async def _generate_embeddings_background(
        self,
        messages: list[MessageRecord],
    ) -> None:
        """Generate embeddings for messages in the background.

        Each message is processed independently — if one fails, the others
        are still attempted. Errors are logged but never re-raised.
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
                logger.exception(
                    "Failed to generate embeddings for %s message %s",
                    message.sender,
                    message.id,
                )
