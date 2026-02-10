"""
Pulse Manager -- Tier 4: Emotional Memory.

Maintains rolling emotional baselines at three granularities:
- Overall baseline (all-time average emotional state)
- Day-of-week baselines (e.g., Mondays tend to be lower valence)
- Time-phase baselines (e.g., late-night sessions tend to be higher arousal)

These baselines allow Gwen to detect when the user's current emotional
state deviates from their personal norm, enabling more empathetic and
contextually aware responses.

References: SRS.md Section 3.6, FR-MEM-004.
"""

import json
from pathlib import Path
from typing import Optional

from gwen.models.emotional import EmotionalStateVector
from gwen.models.messages import MessageRecord, SessionRecord


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAYS_OF_WEEK: list[str] = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
]

DEFAULT_BASELINE_VALUES: dict[str, float] = {
    "valence": 0.5,
    "arousal": 0.3,
    "dominance": 0.5,
    "relational_significance": 0.3,
    "vulnerability_level": 0.2,
}


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _esv_to_dict(state: Optional[EmotionalStateVector]) -> Optional[dict]:
    """Serialize an EmotionalStateVector to a plain dict."""
    if state is None:
        return None
    return {
        "valence": state.valence,
        "arousal": state.arousal,
        "dominance": state.dominance,
        "relational_significance": state.relational_significance,
        "vulnerability_level": state.vulnerability_level,
    }


def _dict_to_esv(d: Optional[dict]) -> Optional[EmotionalStateVector]:
    """Deserialize a dict back to an EmotionalStateVector."""
    if d is None:
        return None
    return EmotionalStateVector(
        valence=d.get("valence", 0.5),
        arousal=d.get("arousal", 0.3),
        dominance=d.get("dominance", 0.5),
        relational_significance=d.get("relational_significance", 0.3),
        vulnerability_level=d.get("vulnerability_level", 0.2),
    )


def _make_default_esv() -> EmotionalStateVector:
    """Create a default EmotionalStateVector with neutral values."""
    return EmotionalStateVector(**DEFAULT_BASELINE_VALUES)


class PulseManager:
    """Tier 4: Pulse -- emotional memory and baseline tracking.

    Maintains rolling emotional baselines that represent the user's
    typical emotional state at different granularities. Uses weighted
    incremental averaging so that baselines adapt over time without
    storing every individual data point.
    """

    def __init__(self, data_path: str | Path) -> None:
        """Open (or create) the Pulse data file.

        Parameters
        ----------
        data_path : str | Path
            Path to the JSON file for Pulse persistence. If the file
            exists, baselines are loaded from it. If not, defaults are
            created.
        """
        self.data_path = Path(data_path).expanduser()

        # Overall baseline (all sessions combined)
        self.overall_baseline: EmotionalStateVector = _make_default_esv()

        # Per-day baselines: {"monday": EmotionalStateVector, ...}
        self.day_baselines: dict[str, EmotionalStateVector] = {}

        # Per-time-phase baselines: {TimePhase.DEEP_NIGHT: EmotionalStateVector, ...}
        self.time_baselines: dict[str, EmotionalStateVector] = {}

        # How many data points have contributed to the overall baseline
        self.data_points_count: int = 0

        # How many data points per day
        self.day_data_counts: dict[str, int] = {}

        # How many data points per time phase
        self.time_data_counts: dict[str, int] = {}

        if self.data_path.exists():
            self._load_from_disk()

    # ------------------------------------------------------------------
    # Baseline computation
    # ------------------------------------------------------------------

    @staticmethod
    def _rolling_average(
        current: EmotionalStateVector,
        new: EmotionalStateVector,
        count: int,
    ) -> EmotionalStateVector:
        """Compute a weighted incremental average of two emotional states.

        Uses the formula: updated = current + (new - current) / (count + 1)
        This is the online mean algorithm that avoids storing all data points.

        Parameters
        ----------
        current : EmotionalStateVector
            The current baseline state.
        new : EmotionalStateVector
            The new observation to incorporate.
        count : int
            The number of data points that have contributed to ``current``
            so far (BEFORE adding this new one).

        Returns
        -------
        EmotionalStateVector
            The updated baseline incorporating the new observation.
        """
        n = count + 1
        return EmotionalStateVector(
            valence=current.valence + (new.valence - current.valence) / n,
            arousal=current.arousal + (new.arousal - current.arousal) / n,
            dominance=current.dominance + (new.dominance - current.dominance) / n,
            relational_significance=(
                current.relational_significance
                + (new.relational_significance - current.relational_significance) / n
            ),
            vulnerability_level=(
                current.vulnerability_level
                + (new.vulnerability_level - current.vulnerability_level) / n
            ),
        )

    @staticmethod
    def _average_emotional_states(
        states: list[EmotionalStateVector],
    ) -> EmotionalStateVector:
        """Compute the simple arithmetic mean of a list of emotional states.

        Parameters
        ----------
        states : list[EmotionalStateVector]
            The states to average. Must be non-empty.

        Returns
        -------
        EmotionalStateVector
            The mean state across all dimensions.

        Raises
        ------
        ValueError
            If the list is empty.
        """
        if not states:
            raise ValueError("Cannot average an empty list of states")

        n = len(states)
        return EmotionalStateVector(
            valence=sum(s.valence for s in states) / n,
            arousal=sum(s.arousal for s in states) / n,
            dominance=sum(s.dominance for s in states) / n,
            relational_significance=sum(
                s.relational_significance for s in states
            ) / n,
            vulnerability_level=sum(
                s.vulnerability_level for s in states
            ) / n,
        )

    # ------------------------------------------------------------------
    # Update from session data
    # ------------------------------------------------------------------

    def update_from_session(
        self,
        session: SessionRecord,
        messages: list[MessageRecord],
    ) -> None:
        """Update all baselines from a completed session's messages.

        Extracts emotional states from all messages, computes the session
        average, and uses it to update the overall, day-of-week, and
        time-phase baselines.

        Parameters
        ----------
        session : SessionRecord
            The completed session metadata. Used for timestamp info
            (day of week, time phase).
        messages : list[MessageRecord]
            All messages from the session. Emotional states are
            extracted from each message's ``emotional_state`` field.
        """
        if not messages:
            return

        # Extract emotional states from messages
        states: list[EmotionalStateVector] = [
            msg.emotional_state for msg in messages
            if msg.emotional_state is not None
        ]
        if not states:
            return

        session_avg = self._average_emotional_states(states)

        # --- Update overall baseline ---
        self.overall_baseline = self._rolling_average(
            self.overall_baseline, session_avg, self.data_points_count
        )
        self.data_points_count += 1

        # --- Update day-of-week baseline ---
        day_name = session.start_time.strftime("%A").lower()
        if day_name in DAYS_OF_WEEK:
            day_count = self.day_data_counts.get(day_name, 0)
            current_day = self.day_baselines.get(
                day_name, _make_default_esv()
            )
            self.day_baselines[day_name] = self._rolling_average(
                current_day, session_avg, day_count
            )
            self.day_data_counts[day_name] = day_count + 1

        # --- Update time-phase baseline ---
        # Determine time phase from session start hour
        time_phase = self._hour_to_time_phase(session.start_time.hour)
        phase_key = time_phase
        phase_count = self.time_data_counts.get(phase_key, 0)
        current_phase = self.time_baselines.get(
            phase_key, _make_default_esv()
        )
        self.time_baselines[phase_key] = self._rolling_average(
            current_phase, session_avg, phase_count
        )
        self.time_data_counts[phase_key] = phase_count + 1

        # --- Persist ---
        self.save_to_disk()

    @staticmethod
    def _hour_to_time_phase(hour: int) -> str:
        """Map an hour (0-23) to a time phase string.

        Parameters
        ----------
        hour : int
            The hour of day (0-23).

        Returns
        -------
        str
            One of: "deep_night" (0-4), "early_morning" (5-7),
            "morning" (8-11), "afternoon" (12-16), "evening" (17-20),
            "night" (21-23).
        """
        if hour < 5:
            return "deep_night"
        elif hour < 8:
            return "early_morning"
        elif hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        elif hour < 21:
            return "evening"
        else:
            return "night"

    # ------------------------------------------------------------------
    # Baseline retrieval
    # ------------------------------------------------------------------

    def get_baseline(
        self,
        day: Optional[str] = None,
        time_phase: Optional[str] = None,
    ) -> EmotionalStateVector:
        """Return the most specific available baseline.

        Tries to return the most specific baseline available:
        1. If both day and time_phase are given, try time_phase first
           (more specific), then day, then overall.
        2. If only time_phase is given, try time_phase, then overall.
        3. If only day is given, try day, then overall.
        4. If neither is given, return overall.

        Parameters
        ----------
        day : str | None
            Day of week (lowercase, e.g., "monday"). Optional.
        time_phase : str | None
            Time phase string (e.g., "morning", "deep_night"). Optional.

        Returns
        -------
        EmotionalStateVector
            The most specific baseline available.
        """
        if time_phase and time_phase in self.time_baselines:
            return self.time_baselines[time_phase]
        if day and day.lower() in self.day_baselines:
            return self.day_baselines[day.lower()]
        return self.overall_baseline

    def get_deviation(
        self,
        current: EmotionalStateVector,
        day: Optional[str] = None,
        time_phase: Optional[str] = None,
    ) -> dict[str, float]:
        """Compare current emotional state to expected baseline.

        Returns per-dimension deviation (current - baseline). Positive
        values mean the current state is higher than the baseline;
        negative values mean it is lower.

        Parameters
        ----------
        current : EmotionalStateVector
            The user's current emotional state.
        day : str | None
            Day of week for baseline lookup. Optional.
        time_phase : str | None
            Time phase for baseline lookup. Optional.

        Returns
        -------
        dict[str, float]
            A dict with keys "valence", "arousal", "dominance",
            "relational_significance", "vulnerability_level" and
            float values representing the deviation from baseline.
        """
        baseline = self.get_baseline(day=day, time_phase=time_phase)
        return {
            "valence": current.valence - baseline.valence,
            "arousal": current.arousal - baseline.arousal,
            "dominance": current.dominance - baseline.dominance,
            "relational_significance": (
                current.relational_significance
                - baseline.relational_significance
            ),
            "vulnerability_level": (
                current.vulnerability_level
                - baseline.vulnerability_level
            ),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_to_disk(self) -> None:
        """Serialize all baseline data to JSON and write to self.data_path."""
        data = {
            "overall_baseline": _esv_to_dict(self.overall_baseline),
            "data_points_count": self.data_points_count,
            "day_baselines": {
                day: _esv_to_dict(esv)
                for day, esv in self.day_baselines.items()
            },
            "day_data_counts": self.day_data_counts,
            "time_baselines": {
                phase: _esv_to_dict(esv)
                for phase, esv in self.time_baselines.items()
            },
            "time_data_counts": self.time_data_counts,
        }
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_from_disk(self) -> None:
        """Load baseline data from the JSON file at self.data_path."""
        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.overall_baseline = (
            _dict_to_esv(data.get("overall_baseline"))
            or _make_default_esv()
        )
        self.data_points_count = data.get("data_points_count", 0)
        self.day_baselines = {
            day: _dict_to_esv(esv_dict)
            for day, esv_dict in data.get("day_baselines", {}).items()
            if esv_dict is not None
        }
        self.day_data_counts = data.get("day_data_counts", {})
        self.time_baselines = {
            phase: _dict_to_esv(esv_dict)
            for phase, esv_dict in data.get("time_baselines", {}).items()
            if esv_dict is not None
        }
        self.time_data_counts = data.get("time_data_counts", {})
