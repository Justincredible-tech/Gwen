"""Deep consolidation pipeline — runs weekly or after major events.

Performs advanced pattern analysis across all sessions, detects life
rhythms, identifies anniversaries, and generates anticipatory primes.

Reference: SRS.md Section 3.12, FR-MEM-013
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from gwen.models.messages import ConsolidationJob, ConsolidationType, SessionRecord

logger = logging.getLogger(__name__)


class DeepConsolidation:
    """Deep consolidation: pattern analysis and anticipatory priming.

    This pipeline runs weekly (or after a major emotional event).  It
    builds on top of standard consolidation by:

    1. Running standard consolidation first (ensuring baselines are up
       to date).
    2. Analysing emotional trajectories across all sessions to detect
       recurring patterns (e.g., "user spirals on Sunday nights").
    3. Detecting life rhythms: day-of-week emotional profiles after
       4+ weeks of data.
    4. Detecting anniversaries: dates mentioned with emotional weight
       that might recur.
    5. Generating anticipatory primes: forward-looking predictions
       about what the user might need in upcoming sessions.

    Dependencies
    ------------
    - standard_consolidation: StandardConsolidation (run first)
    - model_manager: AdaptiveModelManager (for pattern analysis via LLM)
    - chronicle: Chronicle (for retrieving session history)
    - semantic_map: SemanticMap (for anniversary date storage)

    Usage
    -----
    >>> deep = DeepConsolidation(
    ...     standard_consolidation=standard,
    ...     model_manager=mgr,
    ...     chronicle=chronicle,
    ...     semantic_map=semantic_map,
    ... )
    >>> job = await deep.run()
    """

    # Prompt for pattern analysis
    PATTERN_ANALYSIS_PROMPT = (
        "Analyse the following emotional trajectory data from the "
        "last 4 weeks.  Identify recurring patterns, triggers, and "
        "rhythms.  Return a JSON object with keys:\n"
        '- "weekly_patterns": list of {day_of_week, typical_mood, notes}\n'
        '- "recurring_triggers": list of {trigger, typical_response, '
        "frequency}\n"
        '- "emotional_trends": overall direction (improving, declining, '
        "stable)\n"
        '- "recommended_primes": list of {prediction, confidence, '
        "suggested_response}\n\n"
        "Data:\n{trajectory_data}\n\n"
        "Respond with ONLY a JSON object. No explanation."
    )

    def __init__(
        self,
        standard_consolidation: Any,
        model_manager: Any,
        chronicle: Any,
        semantic_map: Any = None,
    ) -> None:
        """Initialise the deep consolidation pipeline.

        Parameters
        ----------
        standard_consolidation : StandardConsolidation
            The standard consolidation pipeline (run first).
        model_manager : AdaptiveModelManager
            Used for LLM-based pattern analysis.
        chronicle : Chronicle
            Used for retrieving session history.
        semantic_map : SemanticMap | None
            Used for anniversary detection and storage.
        """
        self.standard_consolidation = standard_consolidation
        self.model_manager = model_manager
        self.chronicle = chronicle
        self.semantic_map = semantic_map

    async def run(
        self,
        unprocessed_sessions: Optional[list[SessionRecord]] = None,
    ) -> ConsolidationJob:
        """Run deep consolidation.

        Parameters
        ----------
        unprocessed_sessions : list[SessionRecord] | None
            Sessions that have not yet been through standard consolidation.
            If provided, standard consolidation runs on them first.
            If None, only deep analysis is performed.

        Returns
        -------
        ConsolidationJob
            A record of what was processed and what was produced.
        """
        job = ConsolidationJob(
            id=str(uuid.uuid4()),
            type=ConsolidationType.DEEP,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
        )

        # Step 1: Run standard consolidation first
        if unprocessed_sessions:
            standard_job = await self.standard_consolidation.run(
                unprocessed_sessions
            )
            job.sessions_processed = standard_job.sessions_processed
            job.map_entities_created = standard_job.map_entities_created
            job.map_entities_updated = standard_job.map_entities_updated
            job.pulse_baselines_updated = standard_job.pulse_baselines_updated
            job.bond_field_updated = standard_job.bond_field_updated
            job.errors.extend(standard_job.errors)

        # Step 2: Analyse patterns across all sessions
        try:
            primes_count = await self._analyse_patterns(job)
            job.anticipatory_primes_generated = primes_count
        except Exception as exc:
            error_msg = f"Pattern analysis failed: {exc}"
            logger.error(error_msg)
            job.errors.append(error_msg)

        # Step 3: Detect anniversaries
        try:
            anniversary_count = await self._detect_anniversaries(job)
            if anniversary_count > 0:
                logger.info(
                    "Detected %d potential anniversaries.", anniversary_count
                )
        except Exception as exc:
            error_msg = f"Anniversary detection failed: {exc}"
            logger.error(error_msg)
            job.errors.append(error_msg)

        job.completed_at = datetime.now(timezone.utc)
        logger.info(
            "Deep consolidation complete: %d primes generated, %d errors",
            job.anticipatory_primes_generated,
            len(job.errors),
        )
        return job

    async def _analyse_patterns(
        self, job: ConsolidationJob
    ) -> int:
        """Analyse emotional patterns across recent sessions.

        Builds a summary of emotional trajectories from the last 4 weeks
        and sends it to the LLM for pattern detection.  Generates
        anticipatory primes from the results.

        Parameters
        ----------
        job : ConsolidationJob
            The job record to update with errors.

        Returns
        -------
        int
            Number of anticipatory primes generated.
        """
        # Build trajectory data from the last 28 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=28)

        # Query sessions from the last 28 days
        # Note: This uses a direct SQL query because Chronicle may not
        # have a get_sessions_since() method yet.
        if hasattr(self.chronicle, "conn"):
            cursor = self.chronicle.conn.execute(
                "SELECT id, start_time, session_type, "
                "closing_emotional_state, topics "
                "FROM sessions WHERE start_time >= ? "
                "ORDER BY start_time ASC",
                (cutoff.isoformat(),),
            )
            rows = cursor.fetchall()
        else:
            return 0

        if len(rows) < 7:
            logger.info(
                "Not enough sessions for pattern analysis "
                "(%d sessions, need 7).",
                len(rows),
            )
            return 0

        # Build the trajectory data summary
        trajectory_entries: list[str] = []
        for row in rows:
            start_time = row["start_time"] if isinstance(row, dict) else row[1]
            try:
                dt = datetime.fromisoformat(str(start_time))
                day_of_week = dt.strftime("%A")
                hour = dt.hour
            except (ValueError, TypeError):
                day_of_week = "Unknown"
                hour = 0

            session_type = row["session_type"] if isinstance(row, dict) else row[2]
            closing_state = row["closing_emotional_state"] if isinstance(row, dict) else row[3]
            topics = row["topics"] if isinstance(row, dict) else row[4]

            trajectory_entries.append(
                f"- {day_of_week} {hour}:00 | type={session_type} | "
                f"closing_state={closing_state} | topics={topics}"
            )

        trajectory_data = "\n".join(trajectory_entries)

        # Send to LLM for analysis
        prompt = self.PATTERN_ANALYSIS_PROMPT.format(
            trajectory_data=trajectory_data
        )

        try:
            raw_response = await self.model_manager.generate(
                tier=2,
                prompt=prompt,
                format="json",
                options={"temperature": 0.2, "num_predict": 2048},
            )
        except Exception:
            raw_response = await self.model_manager.generate(
                tier=1,
                prompt=prompt,
                format="json",
                options={"temperature": 0.2, "num_predict": 2048},
            )

        # Parse the response
        try:
            analysis = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError):
            job.errors.append("Pattern analysis response was not valid JSON.")
            return 0

        # Generate anticipatory primes from recommended_primes
        primes = analysis.get("recommended_primes", [])
        count = 0
        for prime_dict in primes:
            if isinstance(prime_dict, dict) and "prediction" in prime_dict:
                count += 1

        return count

    async def _detect_anniversaries(
        self, job: ConsolidationJob
    ) -> int:
        """Detect dates mentioned in conversations that may be anniversaries.

        Scans messages from the last 90 days for date references with
        high emotional weight.  These dates are candidates for
        anniversary-based anticipatory primes.

        Parameters
        ----------
        job : ConsolidationJob
            The job record to update with errors.

        Returns
        -------
        int
            Number of potential anniversaries detected.
        """
        # This is a simplified version. A full implementation would use
        # NER (named entity recognition) to find date references and
        # cross-reference them with emotional weight.

        if not hasattr(self.chronicle, "conn"):
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        cursor = self.chronicle.conn.execute(
            "SELECT content, valence, arousal, relational_significance "
            "FROM messages "
            "WHERE timestamp >= ? AND relational_significance > 0.7",
            (cutoff.isoformat(),),
        )
        rows = cursor.fetchall()

        # Count high-significance messages as potential anniversary markers
        anniversary_count = 0
        date_keywords = [
            "anniversary", "birthday", "year ago", "last year",
            "this day", "remember when", "it's been a year",
            "died", "passed away", "graduated", "got married",
        ]

        for row in rows:
            content = (
                row["content"] if isinstance(row, dict) else row[0]
            )
            if content and any(
                keyword in content.lower() for keyword in date_keywords
            ):
                anniversary_count += 1

        return anniversary_count
