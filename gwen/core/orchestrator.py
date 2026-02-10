"""Basic orchestrator for the Gwen companion framework.

Chains the core subsystems together into a working conversation loop:
Input -> TME -> Tier 0 classify -> Context assembly -> Tier 1 generate -> Output

This is the simplified Phase 1 orchestrator. The full version (Track 010+)
adds memory retrieval, embedding, post-processing, and safety monitoring.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from gwen.core.model_manager import AdaptiveModelManager, detect_profile
from gwen.core.session_manager import SessionManager, detect_goodbye
from gwen.core.post_processor import PostProcessor
from gwen.consolidation.light import SessionCloser, should_trigger_standard_consolidation
from gwen.temporal.tme import TMEGenerator
from gwen.classification.tier0 import Tier0Classifier
from gwen.classification.rule_engine import ClassificationRuleEngine
from gwen.memory.chronicle import Chronicle
from gwen.memory.stream import Stream
from gwen.personality.loader import PersonalityLoader
from gwen.personality.prompt_builder import PromptBuilder
from gwen.models.personality import PersonalityModule
from gwen.models.messages import MessageRecord, SessionEndMode

logger = logging.getLogger(__name__)


# Default personality file path, relative to the project data directory.
DEFAULT_PERSONALITY_PATH = "data/personalities/gwen.yaml"

# Maximum number of recent messages to include in the simplified context.
# Full context assembly (Track 010) will replace this with a token-budget
# aware assembler.
MAX_RECENT_MESSAGES = 20


def _format_tme_summary(tme) -> str:
    """Build a compact TME summary string for the Tier 0 prompt."""
    return (
        f"{tme.time_phase.value}, "
        f"{tme.day_of_week}, "
        f"session_msg={tme.msg_index_in_session}, "
        f"session_dur={tme.session_duration_sec}s"
    )


def _format_recent_messages(history: list[dict[str, str]], count: int = 3) -> str:
    """Format the last N messages as a compact string for Tier 0 context."""
    recent = history[-count:] if len(history) > count else history
    if not recent:
        return "(no prior messages)"
    lines = []
    for msg in recent:
        role = "User" if msg["role"] == "user" else "Gwen"
        # Truncate long messages for Tier 0 context
        content = msg["content"][:100]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _format_conversation_for_tier1(
    history: list[dict[str, str]],
) -> str:
    """Format conversation history into a prompt string for Tier 1.

    The /api/generate endpoint takes a single prompt string, so we
    format the conversation as labeled turns.
    """
    if not history:
        return ""
    lines = []
    for msg in history:
        if msg["role"] == "user":
            lines.append(f"User: {msg['content']}")
        else:
            lines.append(f"Gwen: {msg['content']}")
    # Add the Gwen prefix so the model continues as Gwen
    lines.append("Gwen:")
    return "\n".join(lines)


class Orchestrator:
    """Chains all subsystems into a working conversation loop.

    This is the Phase 1 orchestrator that provides a basic but functional
    conversation experience. It implements phases 1 (TME), 2 (Tier 0),
    3 (simplified context), and 6 (Tier 1 generation) of the message
    lifecycle defined in SRS.md Section 4.

    Phases 4 (safety) and 5 (full memory retrieval) are stubbed and will
    be implemented in later tracks.
    """

    def __init__(
        self,
        data_dir: str = "~/.gwen/data",
        personality_path: str = DEFAULT_PERSONALITY_PATH,
    ) -> None:
        """Initialize the orchestrator.

        This only stores configuration. Actual subsystem initialization
        happens in startup() because it involves async operations.

        Args:
            data_dir: Path to the data directory for Chronicle storage.
            personality_path: Path to the personality YAML file.
        """
        self.data_dir = str(Path(data_dir).expanduser())
        self.personality_path = personality_path

        # Subsystems (initialized in startup())
        self.model_manager: Optional[AdaptiveModelManager] = None
        self.chronicle: Optional[Chronicle] = None
        self.tme_generator: Optional[TMEGenerator] = None
        self.session_manager: Optional[SessionManager] = None
        self.tier0_classifier: Optional[Tier0Classifier] = None
        self.rule_engine: Optional[ClassificationRuleEngine] = None
        self.personality: Optional[PersonalityModule] = None
        self.prompt_builder: Optional[PromptBuilder] = None
        self.stream: Optional[Stream] = None
        self.post_processor: Optional[PostProcessor] = None

        # Conversation history for simplified context assembly.
        self._message_history: list[dict[str, str]] = []

        # Track whether this is the first message (for gap context injection)
        self._is_first_message: bool = True

    async def startup(self) -> None:
        """Initialize all subsystems and start a session.

        Call this once before calling process_message().

        Raises:
            FileNotFoundError: If the personality file does not exist.
            RuntimeError: If Ollama is not running or models cannot be loaded.
        """
        logger.info("Starting Gwen orchestrator...")

        # --- Step 1: Data directory ---
        data_path = Path(self.data_dir)
        data_path.mkdir(parents=True, exist_ok=True)
        logger.info("Data directory: %s", data_path.resolve())

        # --- Step 2: Chronicle ---
        db_path = str(data_path / "chronicle.db")
        self.chronicle = Chronicle(db_path=db_path)
        logger.info("Chronicle initialized: %s", db_path)

        # --- Step 3: Model Manager ---
        profile = await detect_profile()
        self.model_manager = AdaptiveModelManager(profile)
        logger.info(
            "Model manager initialized. Profile: %s",
            self.model_manager.profile.value,
        )

        # --- Step 4: Load models ---
        await self.model_manager.ensure_tier_loaded(0)
        logger.info("Tier 0 model loaded.")
        await self.model_manager.ensure_tier_loaded(1)
        logger.info("Tier 1 model loaded.")

        # --- Step 5: Load personality ---
        loader = PersonalityLoader()
        self.personality = loader.load_from_file(self.personality_path)
        logger.info("Personality loaded: %s", self.personality.name)

        # --- Step 6: Initialize subsystems ---
        self.tme_generator = TMEGenerator(chronicle=self.chronicle)
        self.session_manager = SessionManager(
            chronicle=self.chronicle,
            tme_generator=self.tme_generator,
        )
        self.tier0_classifier = Tier0Classifier(model_manager=self.model_manager)
        self.rule_engine = ClassificationRuleEngine()
        self.prompt_builder = PromptBuilder()

        # --- Step 7: Stream and PostProcessor ---
        self.stream = Stream(max_messages=50)
        self.post_processor = PostProcessor(
            tier0_classifier=self.tier0_classifier,
            rule_engine=self.rule_engine,
            chronicle=self.chronicle,
            embedding_service=None,  # Configured in later tracks
            stream=self.stream,
            session_manager=self.session_manager,
        )
        logger.info("Stream and PostProcessor initialized.")

        # --- Step 8: Start session ---
        session = self.session_manager.start_session(initiated_by="user")
        # Persist the session stub so that FK constraints on messages work
        self.chronicle.insert_session(session)
        # Also start the TME generator's session tracking
        self.tme_generator.start_session(session_id=session.id)
        logger.info("Session started: %s", session.id)

        self._message_history = []
        self._is_first_message = True

    async def process_message(self, user_input: str) -> str:
        """Process a user message through the full pipeline and return a response.

        Pipeline stages:
        1. Generate TME (no model call)
        2. Run Tier 0 classification (0.6B model call)
        3. Parse + Rule Engine enhancement (no model call)
        4. Assemble simplified context (system prompt + recent messages)
        5. Generate response via Tier 1 (8B model call)
        6. Record the exchange in session tracking

        Args:
            user_input: The raw text message from the user.

        Returns:
            The companion's response text.

        Raises:
            RuntimeError: If startup() has not been called.
        """
        if self.model_manager is None or self.session_manager is None:
            raise RuntimeError(
                "Orchestrator not initialized. Call startup() first."
            )

        # --- Phase 1: Generate TME ---
        tme = self.tme_generator.generate("user")
        logger.debug("TME generated: phase=%s", tme.time_phase.value)

        # --- Phase 2: Tier 0 classification ---
        tme_summary = _format_tme_summary(tme)
        recent_str = _format_recent_messages(self._message_history)

        raw_output = await self.tier0_classifier.classify(
            message=user_input,
            tme_summary=tme_summary,
            recent_messages=recent_str,
        )

        # --- Phase 2b: Rule Engine enhancement ---
        recent_texts = [
            msg["content"] for msg in self._message_history[-3:]
        ]
        emotional_state = self.rule_engine.classify(
            raw=raw_output,
            tme=tme,
            message=user_input,
            recent_messages=recent_texts,
        )
        logger.debug(
            "Classification: valence=%.2f, arousal=%.2f, compass=%s",
            emotional_state.valence,
            emotional_state.arousal,
            emotional_state.compass_direction.value,
        )

        # --- Phase 2c: Update session emotional tracking ---
        self.session_manager.update_emotional_state(
            emotional_state,
            is_opening=self._is_first_message,
        )
        self.session_manager.add_message("user")

        # --- Phase 2d: Create user MessageRecord ---
        user_message = MessageRecord(
            id=str(uuid.uuid4()),
            session_id=self.session_manager.current_session.id,
            timestamp=datetime.now(),
            sender="user",
            content=user_input,
            tme=tme,
            emotional_state=emotional_state,
            storage_strength=emotional_state.storage_strength,
            is_flashbulb=emotional_state.is_flashbulb,
            compass_direction=emotional_state.compass_direction,
            compass_skill_used=None,
        )

        # --- Phase 3: Assemble simplified context ---
        include_emotional = emotional_state.arousal > 0.6

        # Build return context block for first message if gap is notable
        return_context_block = ""
        if self._is_first_message and self.session_manager.current_return_context:
            rc = self.session_manager.current_return_context
            return_context_block = (
                f"The user is returning after {rc.gap_duration_display}. "
                f"Gap classification: {rc.gap_classification.value}. "
                f"{rc.preceding_summary} "
                f"Suggested approach: {rc.suggested_approach}"
            )

        system_prompt = self.prompt_builder.build_system_prompt(
            personality=self.personality,
            mode="grounded",
            compass_direction=emotional_state.compass_direction,
            include_emotional=include_emotional,
            return_context_block=return_context_block,
        )

        # Add the user message to history
        self._message_history.append({
            "role": "user",
            "content": user_input,
        })

        # Trim history to MAX_RECENT_MESSAGES
        if len(self._message_history) > MAX_RECENT_MESSAGES:
            self._message_history = self._message_history[-MAX_RECENT_MESSAGES:]

        # --- Phase 4: Generate response via Tier 1 ---
        prompt = _format_conversation_for_tier1(self._message_history)
        response_text = await self.model_manager.generate(
            tier=1,
            prompt=prompt,
            system=system_prompt,
            options={
                "num_predict": 512,
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 20,
                "repeat_penalty": 1.15,
            },
        )

        # Clean up: strip any "Gwen:" prefix the model might echo
        response_text = response_text.strip()
        if response_text.startswith("Gwen:"):
            response_text = response_text[5:].strip()

        # --- Phase 5: Post-processing (Phase 7 of the message lifecycle) ---
        self._message_history.append({
            "role": "assistant",
            "content": response_text,
        })
        await self.post_processor.process(
            user_message=user_message,
            response_text=response_text,
            tme=tme,
        )
        # Generate TME for the companion message too
        self.tme_generator.generate("companion")

        # --- Phase 6: Clear first-message flag ---
        self._is_first_message = False

        return response_text

    async def shutdown(self) -> None:
        """End the current session and clean up resources.

        Call this when the conversation is ending (user typed quit,
        window closed, etc.).

        Uses SessionCloser (Phase 8) for rich session finalization:
        emotional arc from actual messages, topic extraction, compass
        activation counts, and subjective time computation.
        """
        if self.session_manager is None:
            return

        if self.session_manager.current_session is None:
            logger.info("No active session to end.")
            return

        # Determine end mode from the last message
        if self._message_history:
            last_msg = self._message_history[-1]
            if last_msg["role"] == "user" and detect_goodbye(last_msg["content"]):
                end_mode = SessionEndMode.EXPLICIT_GOODBYE
            else:
                end_mode = SessionEndMode.NATURAL
        else:
            end_mode = SessionEndMode.NATURAL

        session = self.session_manager.current_session
        session.end_mode = end_mode

        # Get all messages from Chronicle for rich arc computation
        messages = self.chronicle.get_messages_by_session(session.id)

        if messages:
            # Phase 8: Use SessionCloser for rich computation + Chronicle save
            closer = SessionCloser(
                chronicle=self.chronicle,
                session_manager=self.session_manager,
            )
            finalized = await closer.close(
                session=session,
                messages=messages,
                stream=self.stream,
            )

            # Check if standard consolidation should trigger
            if should_trigger_standard_consolidation(
                chronicle=self.chronicle,
                last_standard_consolidation_time=getattr(
                    self, "_last_standard_consolidation", None
                ),
            ):
                pass  # TODO(track-020): schedule standard consolidation

            logger.info(
                "Session ended: id=%s, type=%s, duration=%ds, messages=%d",
                finalized.id,
                finalized.session_type.value,
                finalized.duration_sec,
                finalized.message_count,
            )
        else:
            # No messages stored yet — fall back to basic end_session
            finalized = self.session_manager.end_session(end_mode)
            logger.info("Empty session ended: id=%s", finalized.id)
            return

        # Clean up session manager state so a new session can start.
        # The internal counters will be reset by the next start_session() call.
        self.session_manager.current_session = None
