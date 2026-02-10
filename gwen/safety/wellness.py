"""
Wellness Checkpoint -- 48-hour periodic check during Immersion Mode.

Every 48 cumulative hours of Immersion Mode usage, Gwen pauses to ask
the user three brief wellness questions. This checkpoint:
- CANNOT be skipped
- CANNOT be disabled
- CANNOT be snoozed

The checkpoint analyzes responses for concern patterns that may indicate
unhealthy dependency on the AI companion. All checkpoint data is logged
to the Safety Ledger regardless of whether concerns are detected.

References: SRS.md FR-SAF-007, FR-MODE-003.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from gwen.safety.ledger import SafetyLedger
from gwen.models.safety import WellnessCheckpoint as WellnessCheckpointModel


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHECKPOINT_INTERVAL_HOURS = 48

CHECKPOINT_QUESTIONS: list[str] = [
    "When was the last time you had a meaningful conversation with "
    "another human being?",
    "How are you feeling about your life outside of Gwen right now?",
    "Is there anything you're avoiding in the real world by being here?",
]

CONCERN_PATTERNS: list[str] = [
    "don't need other people",
    "haven't left",
    "only real",
    "don't want to talk to anyone",
    "no one understands",
    "you're the only",
    "rather be here",
    "dont need other people",
    "dont want to talk to anyone",
    "youre the only",
    "no one else",
    "nobody understands",
    "nobody cares",
    "only one who listens",
    "real friend",
    "more real than",
    "only friend",
    "don't have anyone",
    "dont have anyone",
    "never leave the house",
    "haven't gone out",
    "havent gone out",
    "stopped talking to",
    "don't see people",
    "dont see people",
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WellnessResult:
    """The result of a single wellness checkpoint.

    This is the internal result object returned by conduct_checkpoint().
    A separate WellnessCheckpointModel is created for Safety Ledger logging.
    """

    timestamp: datetime
    questions: list[str]
    responses: list[str]
    concern_flags: list[str] = field(default_factory=list)
    has_concerns: bool = False
    cumulative_immersion_hours: float = 0.0


class WellnessCheckpoint:
    """Tracks cumulative Immersion hours and triggers periodic wellness checks.

    The checkpoint triggers every 48 cumulative hours of Immersion Mode.
    It cannot be skipped, disabled, or snoozed. When triggered, it presents
    three questions, analyzes the responses for concern patterns, and logs
    everything to the Safety Ledger.
    """

    def __init__(self, safety_ledger: SafetyLedger) -> None:
        self._safety_ledger = safety_ledger
        self._cumulative_immersion_seconds: float = 0.0
        self._last_checkpoint_at_seconds: float = 0.0
        self._checkpoint_history: list[WellnessResult] = []

    @property
    def cumulative_immersion_hours(self) -> float:
        """Return total Immersion hours tracked by this checkpoint."""
        return self._cumulative_immersion_seconds / 3600.0

    @property
    def hours_since_last_checkpoint(self) -> float:
        """Return hours of Immersion time since the last checkpoint."""
        seconds_since = (
            self._cumulative_immersion_seconds - self._last_checkpoint_at_seconds
        )
        return seconds_since / 3600.0

    @property
    def checkpoint_history(self) -> list[WellnessResult]:
        """Return the list of all past checkpoint results."""
        return list(self._checkpoint_history)

    def add_session_time(self, seconds: float) -> None:
        """Add Immersion session time to the cumulative counter.

        Raises ValueError if seconds is negative.
        """
        if seconds < 0:
            raise ValueError(
                f"Cannot add negative session time: {seconds}"
            )
        self._cumulative_immersion_seconds += seconds

    def is_checkpoint_due(self) -> bool:
        """Check whether a wellness checkpoint should be triggered.

        Returns True if cumulative Immersion time since last checkpoint
        is >= 48 hours.
        """
        seconds_since = (
            self._cumulative_immersion_seconds - self._last_checkpoint_at_seconds
        )
        return seconds_since >= CHECKPOINT_INTERVAL_HOURS * 3600

    def get_questions(self) -> list[str]:
        """Return the list of wellness checkpoint questions."""
        return list(CHECKPOINT_QUESTIONS)

    def analyze_responses(self, responses: list[str]) -> list[str]:
        """Analyze user responses for concern patterns.

        Uses case-insensitive substring matching against CONCERN_PATTERNS.
        """
        concern_flags: list[str] = []
        for response in responses:
            response_lower = response.lower()
            for pattern in CONCERN_PATTERNS:
                if pattern in response_lower and pattern not in concern_flags:
                    concern_flags.append(pattern)
        return concern_flags

    async def conduct_checkpoint(
        self, responses: list[str]
    ) -> WellnessResult:
        """Conduct a wellness checkpoint with the user's responses.

        Analyzes responses for concern patterns, logs to the Safety Ledger,
        and returns a structured result.

        Raises ValueError if the number of responses doesn't match the
        number of questions.
        """
        if len(responses) != len(CHECKPOINT_QUESTIONS):
            raise ValueError(
                f"Expected {len(CHECKPOINT_QUESTIONS)} responses, "
                f"got {len(responses)}"
            )

        # Analyze for concern patterns
        concern_flags = self.analyze_responses(responses)

        # Build internal result
        result = WellnessResult(
            timestamp=datetime.now(),
            questions=list(CHECKPOINT_QUESTIONS),
            responses=list(responses),
            concern_flags=concern_flags,
            has_concerns=len(concern_flags) > 0,
            cumulative_immersion_hours=round(
                self._cumulative_immersion_seconds / 3600, 2
            ),
        )

        # Log to Safety Ledger using the models.safety.WellnessCheckpoint
        checkpoint_model = WellnessCheckpointModel(
            id=str(uuid.uuid4()),
            timestamp=result.timestamp,
            immersion_hours_since_last=self.hours_since_last_checkpoint,
            q1_last_human_conversation=responses[0],
            q2_life_outside_gwen=responses[1],
            q3_avoiding_anything=responses[2],
            concern_flags=concern_flags,
            escalated=result.has_concerns,
        )
        self._safety_ledger.log_checkpoint(checkpoint_model)

        # Update tracking state
        self._last_checkpoint_at_seconds = self._cumulative_immersion_seconds
        self._checkpoint_history.append(result)

        return result
