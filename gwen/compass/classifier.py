"""Compass skill selection — picks the best skill for the current context.

The SkillSelector scores each skill in the direction's pool based on:
1. Base score (1.0 for all)
2. Effectiveness boost (from historical effectiveness data)
3. Trigger phrase match (from the user's message)
4. Variety penalty (if the skill was used recently)

Reference: SRS.md Section 11
"""

import logging
import random
from typing import Optional

from gwen.compass.skills import CompassSkill, get_skills_for_direction
from gwen.models.emotional import CompassDirection, EmotionalStateVector

logger = logging.getLogger(__name__)


class SkillSelector:
    """Selects the most appropriate Compass skill for a given direction and context.

    The selector maintains a history of recently used skills (for variety
    scoring) and references effectiveness history (for effectiveness scoring).

    Usage
    -----
    >>> selector = SkillSelector()
    >>> skill = selector.select_skill(
    ...     direction=CompassDirection.NORTH,
    ...     emotional_state=some_esv,
    ...     message="I don't know how I feel",
    ... )
    >>> print(skill.name)  # e.g., "check_in"
    """

    def __init__(
        self,
        effectiveness_history: Optional[dict[str, float]] = None,
        recent_skills: Optional[list[str]] = None,
    ) -> None:
        """Initialise the selector.

        Parameters
        ----------
        effectiveness_history : dict[str, float] | None
            A mapping of ``{skill_name: average_effectiveness_score}``.
            Scores are 0.0 to 1.0.  If None, all skills start with
            neutral effectiveness.
        recent_skills : list[str] | None
            A list of recently used skill names (most recent first),
            used for the variety penalty.  If None, no variety penalty
            is applied.
        """
        self.effectiveness_history: dict[str, float] = (
            effectiveness_history or {}
        )
        self.recent_skills: list[str] = recent_skills or []

    def select_skill(
        self,
        direction: CompassDirection,
        emotional_state: EmotionalStateVector,
        message: str = "",
    ) -> Optional[CompassSkill]:
        """Select the best skill for the given direction and context.

        Parameters
        ----------
        direction : CompassDirection
            The Compass direction determined by the ClassificationRuleEngine.
            If NONE, returns None (no skill is needed).
        emotional_state : EmotionalStateVector
            The user's current emotional state.
        message : str
            The user's most recent message text.  Used for trigger
            phrase matching.

        Returns
        -------
        CompassSkill | None
            The highest-scoring skill for this direction, or None if
            direction is NONE.

        Scoring formula
        ---------------
        For each skill in the direction's pool:
            score = 1.0  (base)
                  + 0.5  (if effectiveness_history[skill.name] > 0.5)
                  + 0.3  (if any trigger phrase appears in message)
                  - 0.2  (if skill.name appears in recent_skills)

        If multiple skills tie, one is chosen at random to provide variety.
        """
        if direction == CompassDirection.NONE:
            return None

        candidates = get_skills_for_direction(direction)
        if not candidates:
            logger.warning(
                "No skills registered for direction %s", direction.value
            )
            return None

        scored: list[tuple[float, CompassSkill]] = []
        message_lower = message.lower()

        for skill in candidates:
            score = 1.0

            # --- Effectiveness boost ---
            eff = self.effectiveness_history.get(skill.name, 0.0)
            if eff > 0.5:
                score += 0.5

            # --- Trigger phrase match ---
            for phrase in skill.trigger_phrases:
                if phrase.lower() in message_lower:
                    score += 0.3
                    break  # Only one boost per skill

            # --- Variety penalty ---
            if skill.name in self.recent_skills:
                score -= 0.2

            scored.append((score, skill))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # If there are ties at the top, pick randomly among them
        top_score = scored[0][0]
        top_skills = [s for sc, s in scored if sc == top_score]

        selected = random.choice(top_skills)
        logger.info(
            "Selected skill '%s' for direction %s (score=%.2f)",
            selected.name, direction.value, top_score,
        )

        # Update recent skills (keep last 10)
        self.recent_skills.insert(0, selected.name)
        self.recent_skills = self.recent_skills[:10]

        return selected


# ---------------------------------------------------------------------------
# Prompt integration
# ---------------------------------------------------------------------------

def generate_compass_prompt(
    skill: CompassSkill,
    coaching_approach: str = "direct",
) -> str:
    """Generate the prompt section to inject into Tier 1's context.

    Combines the skill's prompt_text with the personality's coaching
    approach to produce a natural-feeling injection.

    Parameters
    ----------
    skill : CompassSkill
        The selected Compass skill.
    coaching_approach : str
        The personality module's coaching approach (e.g., "direct",
        "gentle", "humorous", "socratic").  Adjusts the framing of
        the skill prompt.

    Returns
    -------
    str
        The complete prompt section ready for injection into Tier 1
        context.  Includes the skill name as a comment for debugging.
    """
    approach_prefix = {
        "direct": "Be straightforward and clear.",
        "gentle": "Be soft and inviting. Use warmth, not authority.",
        "humorous": "Use light humor to ease into the skill. Keep the core message serious.",
        "socratic": "Ask questions rather than giving answers. Guide through inquiry.",
    }
    prefix = approach_prefix.get(
        coaching_approach,
        "Use your natural conversational style.",
    )

    return (
        f"[Compass: {skill.direction.value}/{skill.name}]\n"
        f"Coaching approach: {prefix}\n\n"
        f"{skill.prompt_text}"
    )


def should_add_disclaimer(over_reliance_score: float) -> bool:
    """Determine whether a disclaimer should be added to the response.

    The disclaimer system adds occasional reminders that the companion
    is an AI and not a substitute for professional help.  The frequency
    increases if the system detects over-reliance patterns.

    Parameters
    ----------
    over_reliance_score : float
        A 0.0 to 1.0 score indicating how much the user is relying
        on the companion for emotional support.  Computed by the
        Bond system based on session frequency, session length,
        and absence of real-world social connections.

    Returns
    -------
    bool
        True if a disclaimer should be added to this response.

    Disclaimer frequency by over_reliance_score
    --------------------------------------------
    - > 0.7: ALWAYS add disclaimer (100% chance)
    - 0.3 to 0.7: 30% chance of adding disclaimer
    - < 0.3: 10% chance of adding disclaimer

    Note: The disclaimer text itself is NOT generated here — it is
    part of the personality module's system prompt.  This function
    only decides whether to include it.
    """
    if over_reliance_score > 0.7:
        return True
    elif over_reliance_score >= 0.3:
        return random.random() < 0.30
    else:
        return random.random() < 0.10
