"""Compass effectiveness tracking — measures how well skills work.

Stores CompassEffectivenessRecords as JSON and computes aggregate
effectiveness scores for use by the SkillSelector.

Reference: SRS.md Section 11, FR-COMP-005
"""

import json
import logging
from pathlib import Path

from gwen.models.emotional import CompassDirection
from gwen.models.memory import CompassEffectivenessRecord

logger = logging.getLogger(__name__)


class EffectivenessTracker:
    """Tracks and reports on Compass skill effectiveness.

    Records are stored as a JSON file on disk.  Each record captures
    the emotional state before and after a skill was used, whether the
    user engaged with the suggestion, and a computed effectiveness score.

    Usage
    -----
    >>> tracker = EffectivenessTracker(data_path="~/.gwen/data/compass_effectiveness.json")
    >>> tracker.log_usage(record)
    >>> score = tracker.compute_effectiveness("check_in", CompassDirection.NORTH)
    """

    def __init__(self, data_path: str | Path) -> None:
        """Initialise the tracker.

        Parameters
        ----------
        data_path : str | Path
            Path to the JSON file where effectiveness records are stored.
            The file is created if it does not exist.  The parent directory
            must already exist.
        """
        self.data_path = Path(data_path).expanduser()
        self._records: list[dict] = []
        self._load_from_disk()

    def log_usage(self, record: CompassEffectivenessRecord) -> None:
        """Log a new effectiveness record.

        Parameters
        ----------
        record : CompassEffectivenessRecord
            The record to log.  Must have all fields populated.
        """
        entry = {
            "skill_name": record.skill_name,
            "direction": record.direction.value,
            "context_valence": record.context_emotional_state.valence,
            "context_arousal": record.context_emotional_state.arousal,
            "pre_valence": record.pre_trajectory.valence,
            "pre_arousal": record.pre_trajectory.arousal,
            "post_valence": record.post_trajectory.valence,
            "post_arousal": record.post_trajectory.arousal,
            "time_to_effect_sec": record.time_to_effect_sec,
            "user_accepted": record.user_accepted,
            "effectiveness_score": record.effectiveness_score,
        }
        self._records.append(entry)
        self._save_to_disk()
        logger.info(
            "Logged effectiveness for skill '%s': score=%.3f, accepted=%s",
            record.skill_name, record.effectiveness_score, record.user_accepted,
        )

    def compute_effectiveness(
        self, skill_name: str, direction: CompassDirection
    ) -> float:
        """Compute the average effectiveness score for a skill.

        Parameters
        ----------
        skill_name : str
            The name of the skill to query.
        direction : CompassDirection
            The direction of the skill (used as a secondary filter).

        Returns
        -------
        float
            The average effectiveness_score across all records for this
            skill+direction combination.  Returns 0.0 if no records exist.
        """
        matching = [
            r for r in self._records
            if r["skill_name"] == skill_name
            and r["direction"] == direction.value
        ]
        if not matching:
            return 0.0
        total = sum(r["effectiveness_score"] for r in matching)
        return total / len(matching)

    def get_skill_history(
        self, skill_name: str
    ) -> list[dict]:
        """Return all effectiveness records for a specific skill.

        Parameters
        ----------
        skill_name : str
            The name of the skill to query.

        Returns
        -------
        list[dict]
            All records for this skill, in insertion order.
        """
        return [
            r for r in self._records
            if r["skill_name"] == skill_name
        ]

    def get_effectiveness_map(self) -> dict[str, float]:
        """Compute effectiveness scores for ALL skills.

        Returns
        -------
        dict[str, float]
            A mapping of ``{skill_name: average_effectiveness_score}``.
            Only skills with at least one record are included.
            Suitable for passing directly to SkillSelector.__init__.
        """
        scores: dict[str, list[float]] = {}
        for r in self._records:
            name = r["skill_name"]
            if name not in scores:
                scores[name] = []
            scores[name].append(r["effectiveness_score"])
        return {
            name: sum(vals) / len(vals)
            for name, vals in scores.items()
        }

    def _save_to_disk(self) -> None:
        """Write all records to the JSON file.

        Overwrites the file completely each time.  This is acceptable
        because effectiveness records are small (dozens to low hundreds).
        """
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self._records, f, indent=2)

    def _load_from_disk(self) -> None:
        """Load records from the JSON file, if it exists.

        If the file does not exist or is empty, starts with an empty list.
        If the file contains invalid JSON, logs a warning and starts fresh.
        """
        if not self.data_path.exists():
            self._records = []
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    self._records = []
                    return
                self._records = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(
                "Could not parse effectiveness data at %s: %s. Starting fresh.",
                self.data_path, exc,
            )
            self._records = []
