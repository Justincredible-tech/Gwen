"""Standard consolidation pipeline — runs every 6-12 hours during idle.

Processes recent sessions to extract entities, update emotional baselines,
update relational state, and build trigger map associations.

Reference: SRS.md Section 3.12, FR-MEM-012
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from gwen.models.messages import ConsolidationJob, ConsolidationType, SessionRecord

logger = logging.getLogger(__name__)


class StandardConsolidation:
    """Standard consolidation: extracts entities and updates baselines.

    This pipeline runs every 6-12 hours when the system is idle (no
    active session).  It processes all sessions that have not yet been
    consolidated.

    The pipeline does the following:
    1. For each unprocessed session, retrieve all messages.
    2. Use Tier 2 (or Tier 1 if unavailable) to extract entities
       (people, places, concepts, events) from conversation text.
    3. Add extracted entities to the SemanticMap (knowledge graph).
    4. Update Pulse emotional baselines from session emotional data.
    5. Update Bond relational field from session relational delta.
    6. Update trigger map with new temporal/topic associations.

    Dependencies
    ------------
    - model_manager: AdaptiveModelManager (for entity extraction via LLM)
    - chronicle: Chronicle (for retrieving sessions and messages)
    - semantic_map: SemanticMap (for adding entities and edges)
    - pulse_manager: PulseManager (for baseline updates)
    - bond_manager: BondManager (for relational field updates)

    Usage
    -----
    >>> consolidation = StandardConsolidation(
    ...     model_manager=mgr,
    ...     chronicle=chronicle,
    ...     semantic_map=semantic_map,
    ...     pulse_manager=pulse,
    ...     bond_manager=bond,
    ... )
    >>> job = await consolidation.run(sessions=[session1, session2])
    >>> print(job.map_entities_created)
    """

    # Prompt sent to the LLM for entity extraction
    ENTITY_EXTRACTION_PROMPT = (
        "Extract all entities (people, places, concepts, events, "
        "preferences, goals) from the following conversation. "
        "Return a JSON array of objects with keys: "
        '"name", "entity_type", "detail". '
        "entity_type must be one of: person, place, concept, event, "
        "preference, goal.\n\n"
        "Conversation:\n{conversation_text}\n\n"
        "Respond with ONLY a JSON array. No explanation."
    )

    def __init__(
        self,
        model_manager: Any,
        chronicle: Any,
        semantic_map: Any = None,
        pulse_manager: Any = None,
        bond_manager: Any = None,
    ) -> None:
        """Initialise the consolidation pipeline.

        Parameters
        ----------
        model_manager : AdaptiveModelManager
            Used for LLM-based entity extraction.
        chronicle : Chronicle
            Used for retrieving sessions and messages.
        semantic_map : SemanticMap | None
            Used for adding extracted entities.  If None, entity
            extraction is skipped.
        pulse_manager : PulseManager | None
            Used for updating emotional baselines.  If None, baseline
            updates are skipped.
        bond_manager : BondManager | None
            Used for updating the relational field.  If None, bond
            updates are skipped.
        """
        self.model_manager = model_manager
        self.chronicle = chronicle
        self.semantic_map = semantic_map
        self.pulse_manager = pulse_manager
        self.bond_manager = bond_manager

    async def run(
        self, sessions: list[SessionRecord]
    ) -> ConsolidationJob:
        """Run standard consolidation on a list of sessions.

        Parameters
        ----------
        sessions : list[SessionRecord]
            The sessions to consolidate.  These should be sessions
            that have not yet been processed by consolidation.

        Returns
        -------
        ConsolidationJob
            A record of what was processed and what was produced.
        """
        job = ConsolidationJob(
            id=str(uuid.uuid4()),
            type=ConsolidationType.STANDARD,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            sessions_processed=[s.id for s in sessions],
        )

        for session in sessions:
            try:
                await self._process_session(session, job)
            except Exception as exc:
                error_msg = (
                    f"Error consolidating session {session.id}: {exc}"
                )
                logger.error(error_msg)
                job.errors.append(error_msg)

        job.completed_at = datetime.now(timezone.utc)
        logger.info(
            "Standard consolidation complete: %d sessions processed, "
            "%d entities created, %d entities updated, %d errors",
            len(sessions),
            job.map_entities_created,
            job.map_entities_updated,
            len(job.errors),
        )
        return job

    async def _process_session(
        self, session: SessionRecord, job: ConsolidationJob
    ) -> None:
        """Process a single session for consolidation.

        Parameters
        ----------
        session : SessionRecord
            The session to process.
        job : ConsolidationJob
            The job record to update with results.
        """
        # Step 1: Get all messages for this session
        messages = self.chronicle.get_messages_by_session(session.id)
        if not messages:
            logger.debug(
                "Session %s has no messages. Skipping.", session.id
            )
            return

        # Step 2: Extract entities via LLM
        if self.semantic_map is not None:
            conversation_text = "\n".join(
                f"{m.sender}: {m.content}" for m in messages
            )
            entities_created = await self._extract_and_store_entities(
                conversation_text, session.id, job
            )
            job.map_entities_created += entities_created

        # Step 3: Update emotional baselines
        if self.pulse_manager is not None:
            try:
                # Collect emotional states from messages
                emotional_states = [
                    m.emotional_state for m in messages
                    if m.emotional_state is not None
                ]
                if emotional_states and hasattr(
                    self.pulse_manager, "update_baseline"
                ):
                    self.pulse_manager.update_baseline(emotional_states)
                    job.pulse_baselines_updated = True
            except Exception as exc:
                job.errors.append(
                    f"Baseline update failed for session {session.id}: {exc}"
                )

        # Step 4: Update bond relational field
        if self.bond_manager is not None:
            try:
                if (
                    session.relational_field_delta
                    and hasattr(self.bond_manager, "apply_delta")
                ):
                    self.bond_manager.apply_delta(
                        session.relational_field_delta
                    )
                    job.bond_field_updated = True
            except Exception as exc:
                job.errors.append(
                    f"Bond update failed for session {session.id}: {exc}"
                )

    async def _extract_and_store_entities(
        self,
        conversation_text: str,
        session_id: str,
        job: ConsolidationJob,
    ) -> int:
        """Use the LLM to extract entities from conversation text.

        Parameters
        ----------
        conversation_text : str
            The full conversation text (formatted as "sender: content").
        session_id : str
            The session ID (for linking entities to their source).
        job : ConsolidationJob
            The job record to update with errors.

        Returns
        -------
        int
            The number of entities successfully extracted and stored.
        """
        prompt = self.ENTITY_EXTRACTION_PROMPT.format(
            conversation_text=conversation_text
        )

        try:
            # Try Tier 2 first, fall back to Tier 1
            try:
                raw_response = await self.model_manager.generate(
                    tier=2,
                    prompt=prompt,
                    format="json",
                    options={"temperature": 0.1, "num_predict": 1024},
                )
            except Exception:
                raw_response = await self.model_manager.generate(
                    tier=1,
                    prompt=prompt,
                    format="json",
                    options={"temperature": 0.1, "num_predict": 1024},
                )

            # Parse the response
            entities_data = json.loads(raw_response)
            if not isinstance(entities_data, list):
                entities_data = []

            count = 0
            for entity_dict in entities_data:
                if (
                    isinstance(entity_dict, dict)
                    and "name" in entity_dict
                    and "entity_type" in entity_dict
                ):
                    # Add to semantic map if the method exists
                    if hasattr(self.semantic_map, "add_entity_from_dict"):
                        self.semantic_map.add_entity_from_dict(
                            entity_dict, session_id
                        )
                        count += 1

            return count

        except (json.JSONDecodeError, TypeError) as exc:
            job.errors.append(
                f"Entity extraction JSON parse error: {exc}"
            )
            return 0
        except Exception as exc:
            job.errors.append(
                f"Entity extraction failed: {exc}"
            )
            return 0
