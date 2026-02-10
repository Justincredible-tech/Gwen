"""'Should I speak?' decision model — determines when to initiate contact.

Takes the list of active triggers from the TriggerEvaluator and applies
relational and temporal filters to decide whether the companion should
actually reach out.

Reference: SRS.md Section 12
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ShouldISpeakDecision:
    """Decides whether the companion should initiate contact.

    The decision model balances trigger urgency against relational
    readiness and temporal appropriateness (quiet hours).

    Decision logic
    --------------
    1. If there are no triggers: NO (nothing to say)
    2. If any trigger is type "safety": YES (override everything)
    3. If current time is in quiet hours: NO (unless safety)
    4. If bond warmth < 0.3: NO (too early in relationship)
    5. If any trigger has urgency "high": YES
    6. If bond warmth > 0.5: YES (relationship is warm enough)
    7. Otherwise: NO

    Usage
    -----
    >>> decision = ShouldISpeakDecision()
    >>> should_speak = decision.decide(
    ...     triggers=[{"type": "emotional", "urgency": "high", ...}],
    ...     bond_warmth=0.6,
    ...     current_time=datetime.now(timezone.utc),
    ...     quiet_hours_start=23,
    ...     quiet_hours_end=7,
    ... )
    >>> print(should_speak)  # True
    """

    def decide(
        self,
        triggers: list[dict[str, Any]],
        bond_warmth: float,
        current_time: datetime,
        quiet_hours_start: int = 23,
        quiet_hours_end: int = 7,
    ) -> bool:
        """Determine whether the companion should initiate contact.

        Parameters
        ----------
        triggers : list[dict[str, Any]]
            The list of active triggers from TriggerEvaluator.
            Each dict has keys ``type``, ``urgency``, ``description``.
        bond_warmth : float
            The current warmth dimension of the RelationalField (0.0-1.0).
            Represents how warm the relationship is.
        current_time : datetime
            The current UTC time.
        quiet_hours_start : int
            Hour when quiet hours begin (default 23 = 11pm).
            During quiet hours, the companion does not initiate contact
            unless there is a safety trigger.
        quiet_hours_end : int
            Hour when quiet hours end (default 7 = 7am).

        Returns
        -------
        bool
            True if the companion should initiate contact.
            False if it should remain silent.
        """
        # 1. No triggers → do not speak
        if not triggers:
            logger.debug("No triggers active. Decision: do not speak.")
            return False

        # 2. Safety triggers override everything
        has_safety = any(t["type"] == "safety" for t in triggers)
        if has_safety:
            logger.info(
                "Safety trigger active. Decision: SPEAK (safety override)."
            )
            return True

        # 3. Quiet hours check
        current_hour = current_time.hour
        in_quiet_hours = self._is_in_quiet_hours(
            current_hour, quiet_hours_start, quiet_hours_end
        )
        if in_quiet_hours:
            logger.debug(
                "Currently in quiet hours (%d:00-%d:00). "
                "Decision: do not speak.",
                quiet_hours_start, quiet_hours_end,
            )
            return False

        # 4. Relationship too early
        if bond_warmth < 0.3:
            logger.debug(
                "Bond warmth %.2f < 0.3 (too early in relationship). "
                "Decision: do not speak.",
                bond_warmth,
            )
            return False

        # 5. High-urgency trigger
        has_high = any(t["urgency"] == "high" for t in triggers)
        if has_high:
            logger.info(
                "High-urgency trigger active. Decision: SPEAK."
            )
            return True

        # 6. Warm enough relationship
        if bond_warmth > 0.5:
            logger.info(
                "Bond warmth %.2f > 0.5 with active triggers. "
                "Decision: SPEAK.",
                bond_warmth,
            )
            return True

        # 7. Default: do not speak
        logger.debug(
            "No sufficient conditions met. Decision: do not speak."
        )
        return False

    @staticmethod
    def _is_in_quiet_hours(
        current_hour: int,
        start: int,
        end: int,
    ) -> bool:
        """Check if the current hour falls within quiet hours.

        Handles the case where quiet hours span midnight (e.g., 23:00-07:00).

        Parameters
        ----------
        current_hour : int
            Hour to check (0-23).
        start : int
            Hour when quiet hours begin (0-23).
        end : int
            Hour when quiet hours end (0-23).

        Returns
        -------
        bool
            True if current_hour is within the quiet window.
        """
        if start <= end:
            # Quiet hours do not span midnight (e.g., 01:00-06:00)
            return start <= current_hour < end
        else:
            # Quiet hours span midnight (e.g., 23:00-07:00)
            return current_hour >= start or current_hour < end
