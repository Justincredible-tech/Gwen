"""Trigger evaluation — determines what conditions warrant proactive outreach.

The TriggerEvaluator scans multiple signal sources (time, patterns,
emotional state, safety) and produces a list of trigger dicts describing
what was detected and how urgent it is.

Reference: SRS.md Section 12
"""

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TriggerEvaluator:
    """Evaluates trigger conditions for proactive companion outreach.

    The evaluator checks five categories of triggers:
    1. Time-based: morning greeting window, evening check-in window
    2. Pattern-based: user typically messages at this time but has not
    3. Emotional: last session ended with low valence
    4. Safety: wellness checkpoint is due
    5. Goal-based: user has a goal with a deadline approaching

    Each trigger includes a type, urgency level, and description.

    Usage
    -----
    >>> evaluator = TriggerEvaluator()
    >>> triggers = evaluator.evaluate_triggers(
    ...     current_time=datetime.now(timezone.utc),
    ...     last_session_end=some_datetime,
    ...     last_session_closing_valence=0.2,
    ...     hours_since_last_session=18.0,
    ...     user_typical_active_hours=[8, 9, 10, 14, 15, 20, 21],
    ...     user_messaged_today=False,
    ...     wellness_checkpoint_due=False,
    ...     cumulative_immersion_hours=0.0,
    ... )
    >>> for t in triggers:
    ...     print(t["type"], t["urgency"], t["description"])
    """

    # Morning greeting window: 7:00 - 9:59 local time
    MORNING_WINDOW_START: int = 7
    MORNING_WINDOW_END: int = 10

    # Evening check-in window: 19:00 - 21:59 local time
    EVENING_WINDOW_START: int = 19
    EVENING_WINDOW_END: int = 22

    # Valence threshold: if last session ended below this, emotional trigger fires
    LOW_VALENCE_THRESHOLD: float = 0.3

    # Hours threshold: if it has been longer than this, pattern trigger fires
    LONG_ABSENCE_HOURS: float = 48.0

    # Wellness checkpoint: after this many cumulative immersion hours
    WELLNESS_CHECKPOINT_HOURS: float = 48.0

    def evaluate_triggers(
        self,
        current_time: datetime,
        last_session_end: Optional[datetime] = None,
        last_session_closing_valence: Optional[float] = None,
        hours_since_last_session: Optional[float] = None,
        user_typical_active_hours: Optional[list[int]] = None,
        user_messaged_today: bool = False,
        wellness_checkpoint_due: bool = False,
        cumulative_immersion_hours: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Evaluate all trigger conditions and return a list of active triggers.

        Parameters
        ----------
        current_time : datetime
            The current UTC time.
        last_session_end : datetime | None
            When the last session ended.  None if no sessions exist yet.
        last_session_closing_valence : float | None
            The valence of the user's emotional state at the end of
            the last session.  None if no sessions exist yet.
        hours_since_last_session : float | None
            How many hours since the last session ended.
        user_typical_active_hours : list[int] | None
            The hours (0-23) when the user is typically active.
        user_messaged_today : bool
            Whether the user has sent any messages today.
        wellness_checkpoint_due : bool
            Whether a wellness checkpoint is overdue.
        cumulative_immersion_hours : float
            Total hours spent in immersion mode since last checkpoint.

        Returns
        -------
        list[dict[str, Any]]
            Each dict has keys:
            - ``type`` (str): "time_based", "pattern_based", "emotional",
              "safety", or "goal_based"
            - ``urgency`` (str): "low", "medium", or "high"
            - ``description`` (str): Human-readable description of the
              trigger condition
        """
        triggers: list[dict[str, Any]] = []

        current_hour = current_time.hour

        # ---- 1. Time-based triggers ----

        # Morning greeting
        if (
            self.MORNING_WINDOW_START <= current_hour < self.MORNING_WINDOW_END
            and not user_messaged_today
        ):
            triggers.append({
                "type": "time_based",
                "urgency": "low",
                "description": (
                    f"Morning greeting window ({self.MORNING_WINDOW_START}:00-"
                    f"{self.MORNING_WINDOW_END}:00) and user has not "
                    f"messaged today."
                ),
            })

        # Evening check-in
        if (
            self.EVENING_WINDOW_START <= current_hour < self.EVENING_WINDOW_END
            and not user_messaged_today
        ):
            triggers.append({
                "type": "time_based",
                "urgency": "low",
                "description": (
                    f"Evening check-in window ({self.EVENING_WINDOW_START}:00-"
                    f"{self.EVENING_WINDOW_END}:00) and user has not "
                    f"messaged today."
                ),
            })

        # ---- 2. Pattern-based triggers ----

        if user_typical_active_hours and not user_messaged_today:
            if current_hour in user_typical_active_hours:
                triggers.append({
                    "type": "pattern_based",
                    "urgency": "medium",
                    "description": (
                        f"User is typically active at hour {current_hour} "
                        f"but has not messaged today."
                    ),
                })

        # Long absence
        if (
            hours_since_last_session is not None
            and hours_since_last_session > self.LONG_ABSENCE_HOURS
        ):
            triggers.append({
                "type": "pattern_based",
                "urgency": "medium",
                "description": (
                    f"User has been absent for "
                    f"{hours_since_last_session:.1f} hours "
                    f"(threshold: {self.LONG_ABSENCE_HOURS:.0f} hours)."
                ),
            })

        # ---- 3. Emotional triggers ----

        if (
            last_session_closing_valence is not None
            and last_session_closing_valence < self.LOW_VALENCE_THRESHOLD
        ):
            triggers.append({
                "type": "emotional",
                "urgency": "high",
                "description": (
                    f"Last session ended with low valence "
                    f"({last_session_closing_valence:.2f} < "
                    f"{self.LOW_VALENCE_THRESHOLD:.2f}). "
                    f"User may still be struggling."
                ),
            })

        # ---- 4. Safety triggers ----

        if wellness_checkpoint_due:
            triggers.append({
                "type": "safety",
                "urgency": "high",
                "description": (
                    "Wellness checkpoint is due (48-hour immersion "
                    "threshold reached)."
                ),
            })

        if cumulative_immersion_hours >= self.WELLNESS_CHECKPOINT_HOURS:
            if not wellness_checkpoint_due:
                triggers.append({
                    "type": "safety",
                    "urgency": "high",
                    "description": (
                        f"Cumulative immersion time "
                        f"({cumulative_immersion_hours:.1f} hours) has "
                        f"reached the wellness checkpoint threshold "
                        f"({self.WELLNESS_CHECKPOINT_HOURS:.0f} hours)."
                    ),
                })

        return triggers
