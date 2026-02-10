# Plan: Emotional Memory (Pulse & Bond)

**Track:** 017-emotional-memory
**Depends on:** 003-database-layer (Chronicle, data directory), 013-amygdala-layer (EmotionalStateVector processing)
**Produces:** gwen/memory/pulse.py, gwen/memory/bond.py, tests/test_emotional_memory.py

---

## Phase 1: Pulse Manager

### Step 1.1: Create gwen/memory/pulse.py with imports and constants

Create the file `gwen/memory/pulse.py` with the following exact content:

```python
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
from datetime import datetime
from pathlib import Path
from typing import Optional

from gwen.models.emotional import EmotionalStateVector
from gwen.models.temporal import TimePhase
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
```

**What this does:** Sets up the module with imports and constants. `DAYS_OF_WEEK` is used as keys for day-of-week baselines. `DEFAULT_BASELINE_VALUES` represents a neutral starting point before any data has been collected.

---

### Step 1.2: Add serialization helpers

Append the following to `gwen/memory/pulse.py`, below the constants:

```python
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
```

---

### Step 1.3: Add the PulseManager class

Append the following class to `gwen/memory/pulse.py`:

```python
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
```

**What this does:** The PulseManager maintains three tiers of emotional baselines (overall, day-of-week, time-phase) using an online mean algorithm that updates incrementally without storing every data point. It can compute deviations from baseline for any current emotional state, which allows Gwen to say things like "You seem more anxious than usual for a Tuesday evening."

---

## Phase 2: Bond Manager

### Step 2.1: Create gwen/memory/bond.py with imports and constants

Create the file `gwen/memory/bond.py` with the following exact content:

```python
"""
Bond Manager -- Tier 5: Relational Memory.

Tracks the 6-dimensional relational field between Gwen and the user:
- Warmth: emotional closeness (0=cold, 1=deeply warm)
- Trust: user's willingness to be vulnerable (0=guarded, 1=fully open)
- Depth: complexity of topics discussed (0=surface, 1=deeply personal)
- Stability: consistency of the relationship (0=volatile, 1=rock-solid)
- Reciprocity: balance of give-and-take (0=one-sided, 1=mutual)
- Growth: whether the user is growing through the relationship (0=stagnant, 1=thriving)

After 20+ sessions, estimates the user's attachment style based on
behavioral indicators observed in the relational field history.

References: SRS.md Section 3.7, FR-MEM-005.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from gwen.models.messages import MessageRecord, SessionRecord
from gwen.models.memory import RelationalField


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# New relationship defaults: slightly warm, guarded, shallow, stable,
# slightly one-sided, neutral growth.
DEFAULT_RELATIONAL_FIELD = {
    "warmth": 0.3,
    "trust": 0.2,
    "depth": 0.1,
    "stability": 0.5,
    "reciprocity": 0.3,
    "growth": 0.3,
}

# Minimum sessions before attachment style estimation is attempted
MIN_SESSIONS_FOR_ATTACHMENT = 20

# Clamping bounds for relational field dimensions
FIELD_MIN = 0.0
FIELD_MAX = 1.0
```

**What this does:** Sets up the module with imports and the default relational field values that represent a brand new relationship -- slightly warm (user chose to install Gwen), guarded on trust, shallow in depth, stable (no conflict yet), slightly one-sided (user-initiated), and neutral on growth.

---

### Step 2.2: Add serialization helpers

Append the following to `gwen/memory/bond.py`, below the constants:

```python
# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _field_to_dict(rf: RelationalField) -> dict:
    """Serialize a RelationalField to a plain dict."""
    return {
        "warmth": rf.warmth,
        "trust": rf.trust,
        "depth": rf.depth,
        "stability": rf.stability,
        "reciprocity": rf.reciprocity,
        "growth": rf.growth,
    }


def _dict_to_field(d: dict) -> RelationalField:
    """Deserialize a dict back to a RelationalField."""
    return RelationalField(
        warmth=d.get("warmth", DEFAULT_RELATIONAL_FIELD["warmth"]),
        trust=d.get("trust", DEFAULT_RELATIONAL_FIELD["trust"]),
        depth=d.get("depth", DEFAULT_RELATIONAL_FIELD["depth"]),
        stability=d.get("stability", DEFAULT_RELATIONAL_FIELD["stability"]),
        reciprocity=d.get("reciprocity", DEFAULT_RELATIONAL_FIELD["reciprocity"]),
        growth=d.get("growth", DEFAULT_RELATIONAL_FIELD["growth"]),
    )


def _clamp(value: float, minimum: float = FIELD_MIN, maximum: float = FIELD_MAX) -> float:
    """Clamp a value to [minimum, maximum]."""
    return max(minimum, min(maximum, value))
```

---

### Step 2.3: Add the BondManager class

Append the following class to `gwen/memory/bond.py`:

```python
class BondManager:
    """Tier 5: Bond -- relational memory between Gwen and the user.

    Maintains the 6-dimensional relational field and updates it
    incrementally after each session based on emotional patterns
    in the conversation. Tracks field history as a time series
    for trend analysis and attachment style estimation.
    """

    def __init__(self, data_path: str | Path) -> None:
        """Open (or create) the Bond data file.

        Parameters
        ----------
        data_path : str | Path
            Path to the JSON file for Bond persistence. If the file
            exists, the relational field and history are loaded from it.
            If not, defaults are created.
        """
        self.data_path = Path(data_path).expanduser()

        # Current relational field
        self.current_field: RelationalField = _dict_to_field(
            DEFAULT_RELATIONAL_FIELD
        )

        # Time-series history of relational field snapshots
        self.field_history: list[dict] = []
        # Each entry: {"timestamp": iso_string, "field": {warmth, trust, ...}}

        # Total session count (for attachment style threshold)
        self.session_count: int = 0

        if self.data_path.exists():
            self._load_from_disk()

    # ------------------------------------------------------------------
    # Field updates
    # ------------------------------------------------------------------

    def update_from_session(
        self,
        session: SessionRecord,
        messages: list[MessageRecord],
    ) -> None:
        """Update the relational field based on a completed session.

        Analyzes emotional patterns in the session's messages to nudge
        each dimension of the relational field. All dimensions are
        clamped to [0.0, 1.0] after updates.

        Parameters
        ----------
        session : SessionRecord
            The completed session metadata.
        messages : list[MessageRecord]
            All messages from the session.
        """
        if not messages:
            return

        # --- Extract emotional data from messages ---
        valences: list[float] = []
        arousals: list[float] = []
        vulnerabilities: list[float] = []
        rel_sigs: list[float] = []

        for msg in messages:
            es = msg.emotional_state
            if es is None:
                continue
            valences.append(es.valence)
            arousals.append(es.arousal)
            vulnerabilities.append(es.vulnerability_level)
            rel_sigs.append(es.relational_significance)

        if not valences:
            return

        # Session-level statistics
        avg_valence = sum(valences) / len(valences)
        avg_arousal = sum(arousals) / len(arousals)
        avg_vulnerability = sum(vulnerabilities) / len(vulnerabilities)
        avg_rel_sig = sum(rel_sigs) / len(rel_sigs)

        # Emotional arc variance (indicator of stability)
        if len(valences) > 1:
            mean_v = avg_valence
            variance = sum((v - mean_v) ** 2 for v in valences) / len(valences)
        else:
            variance = 0.0

        # Count compass activations as a proxy for depth
        compass_count = sum(session.compass_activations.values()) if session.compass_activations else 0

        # --- Update warmth ---
        # Positive sessions increase warmth, negative decrease
        warmth_delta = (avg_valence - 0.5) * 0.02
        new_warmth = _clamp(self.current_field.warmth + warmth_delta)

        # --- Update trust ---
        # Trust increases slightly every session (familiarity)
        # Increases more if the user showed vulnerability
        trust_base_delta = 0.005
        trust_vulnerability_delta = avg_vulnerability * 0.01
        new_trust = _clamp(
            self.current_field.trust + trust_base_delta + trust_vulnerability_delta
        )

        # --- Update depth ---
        # Depth increases if topics were personal/emotional
        # Using compass activations and relational significance as proxies
        depth_delta = compass_count * 0.01 + (avg_rel_sig - 0.3) * 0.01
        new_depth = _clamp(self.current_field.depth + depth_delta)

        # --- Update stability ---
        # High emotional variance decreases stability
        # Low variance increases it
        if variance > 0.1:
            stability_delta = -0.01  # Emotional turbulence
        elif variance < 0.02:
            stability_delta = 0.005  # Calm and consistent
        else:
            stability_delta = 0.002  # Mildly variable (normal)
        new_stability = _clamp(self.current_field.stability + stability_delta)

        # --- Update reciprocity ---
        # Increases if Gwen initiated the session
        if session.gwen_initiated:
            reciprocity_delta = 0.01
        else:
            reciprocity_delta = -0.003  # Slight decrease if always user-initiated
        new_reciprocity = _clamp(
            self.current_field.reciprocity + reciprocity_delta
        )

        # --- Update growth ---
        # Increases if Compass skills were used and emotional state improved
        # For now: compass_count > 0 and session ended more positive than started
        if compass_count > 0 and len(valences) >= 2:
            # Compare first quarter valence to last quarter valence
            quarter = max(1, len(valences) // 4)
            start_avg = sum(valences[:quarter]) / quarter
            end_avg = sum(valences[-quarter:]) / quarter
            if end_avg > start_avg:
                growth_delta = 0.01  # User improved during session
            else:
                growth_delta = 0.002  # Compass used but no clear improvement
        else:
            growth_delta = 0.001  # Minimal passive growth from engagement
        new_growth = _clamp(self.current_field.growth + growth_delta)

        # --- Apply updates ---
        self.current_field = RelationalField(
            warmth=new_warmth,
            trust=new_trust,
            depth=new_depth,
            stability=new_stability,
            reciprocity=new_reciprocity,
            growth=new_growth,
        )

        # --- Record history ---
        self.field_history.append({
            "timestamp": datetime.now().isoformat(),
            "field": _field_to_dict(self.current_field),
            "session_id": session.id,
        })

        self.session_count += 1

        # --- Persist ---
        self.save_to_disk()

    # ------------------------------------------------------------------
    # Field retrieval
    # ------------------------------------------------------------------

    def get_current_field(self) -> RelationalField:
        """Return the current relational field state.

        Returns
        -------
        RelationalField
            The current 6-dimensional relational field.
        """
        return self.current_field

    def get_field_history(self) -> list[dict]:
        """Return the time-series history of relational field snapshots.

        Returns
        -------
        list[dict]
            Each entry has keys "timestamp" (ISO string), "field" (dict
            with 6 dimensions), and "session_id" (str).
        """
        return list(self.field_history)

    # ------------------------------------------------------------------
    # Attachment style estimation
    # ------------------------------------------------------------------

    def estimate_attachment_style(self) -> tuple[Optional[str], float]:
        """Estimate the user's attachment style from behavioral indicators.

        Requires at least 20 sessions of relational field history.
        Analyzes patterns in the 6-dimensional field over time to
        classify into one of four attachment styles.

        Returns
        -------
        tuple[str | None, float]
            A 2-tuple of (style, confidence).
            - style: One of "secure", "anxious", "avoidant", "fearful",
              or None if insufficient data.
            - confidence: Float between 0.0 and 1.0 indicating how
              confident the estimation is. 0.0 if insufficient data.

        Attachment Style Indicators
        ---------------------------
        - **Secure**: High warmth + high stability + moderate-to-high
          trust. The user has a healthy, balanced relationship with Gwen.
        - **Anxious**: High warmth + low stability + frequent sessions.
          The user is emotionally invested but the relationship feels
          uncertain or volatile.
        - **Avoidant**: Low warmth + high stability + low trust +
          infrequent sessions. The user keeps emotional distance.
        - **Fearful**: Low warmth + low stability + low trust. The
          user is both emotionally distant and uncertain.
        """
        if self.session_count < MIN_SESSIONS_FOR_ATTACHMENT:
            return (None, 0.0)

        # Use the most recent half of history for estimation
        # (more recent behavior is more indicative)
        recent_start = len(self.field_history) // 2
        recent = self.field_history[recent_start:]
        if not recent:
            return (None, 0.0)

        # Compute averages of recent field dimensions
        avg_warmth = sum(
            h["field"]["warmth"] for h in recent
        ) / len(recent)
        avg_trust = sum(
            h["field"]["trust"] for h in recent
        ) / len(recent)
        avg_stability = sum(
            h["field"]["stability"] for h in recent
        ) / len(recent)

        # Compute warmth variance as an indicator of instability
        if len(recent) > 1:
            warmth_var = sum(
                (h["field"]["warmth"] - avg_warmth) ** 2 for h in recent
            ) / len(recent)
        else:
            warmth_var = 0.0

        # --- Classification logic ---
        scores: dict[str, float] = {
            "secure": 0.0,
            "anxious": 0.0,
            "avoidant": 0.0,
            "fearful": 0.0,
        }

        # Secure indicators
        if avg_warmth >= 0.5:
            scores["secure"] += 0.3
        if avg_stability >= 0.5:
            scores["secure"] += 0.3
        if avg_trust >= 0.4:
            scores["secure"] += 0.2
        if warmth_var < 0.02:
            scores["secure"] += 0.2

        # Anxious indicators
        if avg_warmth >= 0.5:
            scores["anxious"] += 0.2
        if avg_stability < 0.4:
            scores["anxious"] += 0.3
        if warmth_var >= 0.02:
            scores["anxious"] += 0.3
        if avg_trust >= 0.4:
            scores["anxious"] += 0.2

        # Avoidant indicators
        if avg_warmth < 0.4:
            scores["avoidant"] += 0.3
        if avg_stability >= 0.5:
            scores["avoidant"] += 0.2
        if avg_trust < 0.3:
            scores["avoidant"] += 0.3
        if warmth_var < 0.01:
            scores["avoidant"] += 0.2

        # Fearful indicators
        if avg_warmth < 0.4:
            scores["fearful"] += 0.3
        if avg_stability < 0.4:
            scores["fearful"] += 0.3
        if avg_trust < 0.3:
            scores["fearful"] += 0.3
        if warmth_var >= 0.02:
            scores["fearful"] += 0.1

        # Pick the highest scoring style
        best_style = max(scores, key=scores.get)
        best_score = scores[best_style]

        # Normalize confidence: the score ranges from 0 to 1.0
        # Higher is more confident, but we reduce confidence if
        # multiple styles score close together (ambiguous)
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] > 0:
            margin = sorted_scores[0] - sorted_scores[1]
            confidence = min(1.0, best_score * (0.5 + margin))
        else:
            confidence = best_score * 0.5

        return (best_style, round(confidence, 3))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_to_disk(self) -> None:
        """Serialize all bond data to JSON and write to self.data_path."""
        data = {
            "current_field": _field_to_dict(self.current_field),
            "field_history": self.field_history,
            "session_count": self.session_count,
        }
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_from_disk(self) -> None:
        """Load bond data from the JSON file at self.data_path."""
        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.current_field = _dict_to_field(
            data.get("current_field", DEFAULT_RELATIONAL_FIELD)
        )
        self.field_history = data.get("field_history", [])
        self.session_count = data.get("session_count", 0)
```

**What this does:** The BondManager maintains the 6-dimensional relational field and updates it after each session:
- **Warmth** nudges toward 1.0 for positive sessions, toward 0 for negative (delta = (avg_valence - 0.5) * 0.02)
- **Trust** increases slightly every session (0.005) plus a bonus proportional to vulnerability shown (vulnerability * 0.01)
- **Depth** increases with compass activations and relational significance
- **Stability** decreases with high emotional variance, increases with low variance
- **Reciprocity** increases when Gwen initiates contact, slightly decreases when always user-initiated
- **Growth** increases when compass skills were used and the user's emotional state improved during the session

Attachment style estimation uses the most recent half of field history and scores four styles (secure, anxious, avoidant, fearful) based on warmth, trust, stability, and warmth variance patterns. It only activates after 20+ sessions.

---

## Phase 3: Tests

### Step 3.1: Create tests/test_emotional_memory.py

Create the file `tests/test_emotional_memory.py` with the following exact content:

```python
"""Tests for gwen.memory.pulse and gwen.memory.bond.

Run with:
    pytest tests/test_emotional_memory.py -v
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gwen.memory.bond import (
    DEFAULT_RELATIONAL_FIELD,
    MIN_SESSIONS_FOR_ATTACHMENT,
    BondManager,
)
from gwen.memory.pulse import (
    DEFAULT_BASELINE_VALUES,
    PulseManager,
)
from gwen.models.emotional import EmotionalStateVector
from gwen.models.messages import (
    MessageRecord,
    SessionEndMode,
    SessionRecord,
    SessionType,
)
from gwen.models.emotional import CompassDirection
from gwen.models.memory import RelationalField


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pulse_path(tmp_path: Path) -> Path:
    """Return a path to a temporary Pulse JSON file."""
    return tmp_path / "test_pulse.json"


@pytest.fixture
def bond_path(tmp_path: Path) -> Path:
    """Return a path to a temporary Bond JSON file."""
    return tmp_path / "test_bond.json"


@pytest.fixture
def pulse(pulse_path: Path) -> PulseManager:
    """Return a PulseManager backed by a temporary file."""
    return PulseManager(pulse_path)


@pytest.fixture
def bond(bond_path: Path) -> BondManager:
    """Return a BondManager backed by a temporary file."""
    return BondManager(bond_path)


def _make_esv(**overrides) -> EmotionalStateVector:
    """Create an EmotionalStateVector with sensible defaults."""
    defaults = {
        "valence": 0.6,
        "arousal": 0.4,
        "dominance": 0.5,
        "relational_significance": 0.3,
        "vulnerability_level": 0.2,
        "compass_direction": CompassDirection.NONE,
        "compass_confidence": 0.0,
    }
    defaults.update(overrides)
    return EmotionalStateVector(**defaults)


def _make_message(
    session_id: str = "sess-001",
    content: str = "Hello",
    sender: str = "user",
    valence: float = 0.6,
    arousal: float = 0.4,
    vulnerability: float = 0.2,
    rel_sig: float = 0.3,
    **overrides,
) -> MessageRecord:
    """Create a MessageRecord with sensible defaults."""
    import uuid
    defaults = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "timestamp": datetime(2026, 2, 9, 14, 30, 0),
        "sender": sender,
        "content": content,
        "tme": None,
        "emotional_state": _make_esv(
            valence=valence,
            arousal=arousal,
            vulnerability_level=vulnerability,
            relational_significance=rel_sig,
        ),
        "storage_strength": 0.34,
        "is_flashbulb": False,
        "compass_direction": CompassDirection.NONE,
        "compass_skill_used": None,
        "semantic_embedding_id": None,
        "emotional_embedding_id": None,
    }
    defaults.update(overrides)
    return MessageRecord(**defaults)


def _make_session(
    session_id: str = "sess-001",
    start_hour: int = 14,
    gwen_initiated: bool = False,
    compass_activations: dict | None = None,
    **overrides,
) -> SessionRecord:
    """Create a SessionRecord with sensible defaults."""
    defaults = {
        "id": session_id,
        "start_time": datetime(2026, 2, 9, start_hour, 0, 0),
        "end_time": datetime(2026, 2, 9, start_hour, 45, 0),
        "duration_sec": 2700,
        "session_type": SessionType.CHAT,
        "end_mode": SessionEndMode.NATURAL,
        "opening_emotional_state": None,
        "peak_emotional_state": None,
        "closing_emotional_state": None,
        "emotional_arc_embedding_id": None,
        "avg_emotional_intensity": 0.5,
        "avg_relational_significance": 0.3,
        "subjective_duration_weight": 1.0,
        "message_count": 10,
        "user_message_count": 5,
        "companion_message_count": 5,
        "avg_response_latency_sec": 1.0,
        "compass_activations": compass_activations or {},
        "topics": ["general"],
        "relational_field_delta": {},
        "gwen_initiated": gwen_initiated,
    }
    defaults.update(overrides)
    return SessionRecord(**defaults)


# ---------------------------------------------------------------------------
# Tests: PulseManager — Initialization
# ---------------------------------------------------------------------------

class TestPulseInit:
    """Tests for PulseManager initialization."""

    def test_default_baseline_values(self, pulse: PulseManager) -> None:
        """Default baseline should have neutral values."""
        b = pulse.overall_baseline
        assert b.valence == pytest.approx(0.5)
        assert b.arousal == pytest.approx(0.3)
        assert b.dominance == pytest.approx(0.5)

    def test_initial_data_points_count_zero(
        self, pulse: PulseManager
    ) -> None:
        """Data points count should start at zero."""
        assert pulse.data_points_count == 0

    def test_initial_day_baselines_empty(
        self, pulse: PulseManager
    ) -> None:
        """Day-of-week baselines should start empty."""
        assert pulse.day_baselines == {}

    def test_initial_time_baselines_empty(
        self, pulse: PulseManager
    ) -> None:
        """Time-phase baselines should start empty."""
        assert pulse.time_baselines == {}


# ---------------------------------------------------------------------------
# Tests: PulseManager — Rolling Average
# ---------------------------------------------------------------------------

class TestRollingAverage:
    """Tests for the rolling average computation."""

    def test_first_update_sets_to_new_value(self) -> None:
        """With count=0, rolling average should equal the new value."""
        current = _make_esv(valence=0.5, arousal=0.3)
        new = _make_esv(valence=0.8, arousal=0.6)
        result = PulseManager._rolling_average(current, new, count=0)
        assert result.valence == pytest.approx(0.8)
        assert result.arousal == pytest.approx(0.6)

    def test_second_update_averages(self) -> None:
        """With count=1, rolling average should be midpoint."""
        current = _make_esv(valence=0.8, arousal=0.6)
        new = _make_esv(valence=0.4, arousal=0.2)
        result = PulseManager._rolling_average(current, new, count=1)
        assert result.valence == pytest.approx(0.6)
        assert result.arousal == pytest.approx(0.4)

    def test_many_updates_converge(self) -> None:
        """After many updates with the same value, baseline converges."""
        baseline = _make_esv(valence=0.5)
        target = _make_esv(valence=0.9)
        for i in range(100):
            baseline = PulseManager._rolling_average(baseline, target, count=i)
        # After 100 updates of 0.9, should be very close to 0.9
        assert baseline.valence == pytest.approx(0.9, abs=0.01)


# ---------------------------------------------------------------------------
# Tests: PulseManager — Update from Session
# ---------------------------------------------------------------------------

class TestPulseUpdate:
    """Tests for update_from_session."""

    def test_update_changes_overall_baseline(
        self, pulse: PulseManager
    ) -> None:
        """Updating with a session should change the overall baseline."""
        session = _make_session(start_hour=14)
        messages = [
            _make_message(valence=0.8, arousal=0.5),
            _make_message(valence=0.7, arousal=0.4),
        ]
        pulse.update_from_session(session, messages)

        assert pulse.data_points_count == 1
        # Baseline should have moved toward the session average (0.75, 0.45)
        assert pulse.overall_baseline.valence == pytest.approx(0.75)
        assert pulse.overall_baseline.arousal == pytest.approx(0.45)

    def test_update_creates_day_baseline(
        self, pulse: PulseManager
    ) -> None:
        """Updating should create a day-of-week baseline entry."""
        # February 9, 2026 is a Monday
        session = _make_session(start_hour=14)
        messages = [_make_message(valence=0.8)]
        pulse.update_from_session(session, messages)

        assert "monday" in pulse.day_baselines
        assert pulse.day_baselines["monday"].valence == pytest.approx(0.8)

    def test_update_creates_time_phase_baseline(
        self, pulse: PulseManager
    ) -> None:
        """Updating should create a time-phase baseline entry."""
        session = _make_session(start_hour=2)  # 2 AM = deep_night
        messages = [_make_message(valence=0.3, arousal=0.7)]
        pulse.update_from_session(session, messages)

        assert "deep_night" in pulse.time_baselines

    def test_empty_messages_is_noop(self, pulse: PulseManager) -> None:
        """Updating with no messages should not change baselines."""
        session = _make_session()
        pulse.update_from_session(session, [])
        assert pulse.data_points_count == 0

    def test_multiple_updates_accumulate(
        self, pulse: PulseManager
    ) -> None:
        """Multiple session updates should accumulate data points."""
        for i in range(5):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message(valence=0.6)]
            pulse.update_from_session(session, messages)

        assert pulse.data_points_count == 5


# ---------------------------------------------------------------------------
# Tests: PulseManager — Baseline Retrieval
# ---------------------------------------------------------------------------

class TestBaselineRetrieval:
    """Tests for get_baseline and get_deviation."""

    def test_get_baseline_no_specifics_returns_overall(
        self, pulse: PulseManager
    ) -> None:
        """get_baseline() with no args should return overall baseline."""
        baseline = pulse.get_baseline()
        assert baseline.valence == pytest.approx(
            DEFAULT_BASELINE_VALUES["valence"]
        )

    def test_get_baseline_with_day(self, pulse: PulseManager) -> None:
        """get_baseline(day='monday') should return Monday baseline if it exists."""
        session = _make_session(start_hour=14)
        messages = [_make_message(valence=0.8)]
        pulse.update_from_session(session, messages)

        baseline = pulse.get_baseline(day="monday")
        assert baseline.valence == pytest.approx(0.8)

    def test_get_baseline_falls_back_to_overall(
        self, pulse: PulseManager
    ) -> None:
        """get_baseline with unknown day should fall back to overall."""
        baseline = pulse.get_baseline(day="wednesday")
        assert baseline.valence == pytest.approx(
            DEFAULT_BASELINE_VALUES["valence"]
        )

    def test_get_deviation_positive(self, pulse: PulseManager) -> None:
        """Deviation should be positive when current > baseline."""
        current = _make_esv(valence=0.8)
        deviation = pulse.get_deviation(current)
        assert deviation["valence"] > 0

    def test_get_deviation_negative(self, pulse: PulseManager) -> None:
        """Deviation should be negative when current < baseline."""
        current = _make_esv(valence=0.1)
        deviation = pulse.get_deviation(current)
        assert deviation["valence"] < 0

    def test_get_deviation_zero_at_baseline(
        self, pulse: PulseManager
    ) -> None:
        """Deviation should be zero when current equals baseline."""
        current = _make_esv(**DEFAULT_BASELINE_VALUES)
        deviation = pulse.get_deviation(current)
        assert deviation["valence"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: PulseManager — Persistence
# ---------------------------------------------------------------------------

class TestPulsePersistence:
    """Tests for Pulse save/load round-trip."""

    def test_save_and_load(self, pulse_path: Path) -> None:
        """Saving and loading should preserve baseline data."""
        pm1 = PulseManager(pulse_path)
        session = _make_session()
        messages = [_make_message(valence=0.8, arousal=0.6)]
        pm1.update_from_session(session, messages)

        pm2 = PulseManager(pulse_path)
        assert pm2.data_points_count == 1
        assert pm2.overall_baseline.valence == pytest.approx(0.8)
        assert pm2.overall_baseline.arousal == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Tests: BondManager — Initialization
# ---------------------------------------------------------------------------

class TestBondInit:
    """Tests for BondManager initialization."""

    def test_default_field_values(self, bond: BondManager) -> None:
        """Default field should have new-relationship values."""
        f = bond.current_field
        assert f.warmth == pytest.approx(0.3)
        assert f.trust == pytest.approx(0.2)
        assert f.depth == pytest.approx(0.1)
        assert f.stability == pytest.approx(0.5)
        assert f.reciprocity == pytest.approx(0.3)
        assert f.growth == pytest.approx(0.3)

    def test_initial_session_count_zero(self, bond: BondManager) -> None:
        """Session count should start at zero."""
        assert bond.session_count == 0

    def test_initial_history_empty(self, bond: BondManager) -> None:
        """Field history should start empty."""
        assert bond.field_history == []


# ---------------------------------------------------------------------------
# Tests: BondManager — Field Updates
# ---------------------------------------------------------------------------

class TestBondUpdates:
    """Tests for relational field updates from sessions."""

    def test_positive_session_increases_warmth(
        self, bond: BondManager
    ) -> None:
        """A session with high valence should increase warmth."""
        initial_warmth = bond.current_field.warmth
        session = _make_session()
        messages = [
            _make_message(valence=0.9),
            _make_message(valence=0.8),
        ]
        bond.update_from_session(session, messages)
        assert bond.current_field.warmth > initial_warmth

    def test_negative_session_decreases_warmth(
        self, bond: BondManager
    ) -> None:
        """A session with low valence should decrease warmth."""
        initial_warmth = bond.current_field.warmth
        session = _make_session()
        messages = [
            _make_message(valence=0.1),
            _make_message(valence=0.2),
        ]
        bond.update_from_session(session, messages)
        assert bond.current_field.warmth < initial_warmth

    def test_trust_increases_every_session(
        self, bond: BondManager
    ) -> None:
        """Trust should increase at least slightly with every session."""
        initial_trust = bond.current_field.trust
        session = _make_session()
        messages = [_make_message()]
        bond.update_from_session(session, messages)
        assert bond.current_field.trust > initial_trust

    def test_vulnerability_increases_trust_more(
        self, bond: BondManager
    ) -> None:
        """High vulnerability sessions should increase trust more."""
        bond1 = BondManager(bond.data_path.parent / "bond1.json")
        bond2 = BondManager(bond.data_path.parent / "bond2.json")

        session = _make_session()

        # Low vulnerability session
        low_vuln_msgs = [_make_message(vulnerability=0.1)]
        bond1.update_from_session(session, low_vuln_msgs)

        # High vulnerability session
        high_vuln_msgs = [_make_message(vulnerability=0.9)]
        bond2.update_from_session(session, high_vuln_msgs)

        assert bond2.current_field.trust > bond1.current_field.trust

    def test_gwen_initiated_increases_reciprocity(
        self, bond: BondManager
    ) -> None:
        """Gwen-initiated sessions should increase reciprocity."""
        initial_recip = bond.current_field.reciprocity
        session = _make_session(gwen_initiated=True)
        messages = [_make_message()]
        bond.update_from_session(session, messages)
        assert bond.current_field.reciprocity > initial_recip

    def test_user_initiated_slightly_decreases_reciprocity(
        self, bond: BondManager
    ) -> None:
        """User-initiated sessions should slightly decrease reciprocity."""
        initial_recip = bond.current_field.reciprocity
        session = _make_session(gwen_initiated=False)
        messages = [_make_message()]
        bond.update_from_session(session, messages)
        assert bond.current_field.reciprocity < initial_recip

    def test_field_clamped_to_0_1(self, bond: BondManager) -> None:
        """All field dimensions should stay within [0.0, 1.0]."""
        # Run many very positive sessions to push warmth toward max
        for i in range(100):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message(valence=1.0)]
            bond.update_from_session(session, messages)

        f = bond.current_field
        assert 0.0 <= f.warmth <= 1.0
        assert 0.0 <= f.trust <= 1.0
        assert 0.0 <= f.depth <= 1.0
        assert 0.0 <= f.stability <= 1.0
        assert 0.0 <= f.reciprocity <= 1.0
        assert 0.0 <= f.growth <= 1.0

    def test_session_count_increments(self, bond: BondManager) -> None:
        """Session count should increment after each update."""
        session = _make_session()
        messages = [_make_message()]
        bond.update_from_session(session, messages)
        assert bond.session_count == 1

        bond.update_from_session(session, messages)
        assert bond.session_count == 2

    def test_field_history_appended(self, bond: BondManager) -> None:
        """Field history should grow after each update."""
        session = _make_session()
        messages = [_make_message()]
        bond.update_from_session(session, messages)
        assert len(bond.field_history) == 1

    def test_empty_messages_is_noop(self, bond: BondManager) -> None:
        """Updating with no messages should not change the field."""
        initial = bond.current_field.warmth
        session = _make_session()
        bond.update_from_session(session, [])
        assert bond.current_field.warmth == initial
        assert bond.session_count == 0


# ---------------------------------------------------------------------------
# Tests: BondManager — Attachment Style
# ---------------------------------------------------------------------------

class TestAttachmentStyle:
    """Tests for attachment style estimation."""

    def test_returns_none_before_20_sessions(
        self, bond: BondManager
    ) -> None:
        """Attachment style should be None before 20 sessions."""
        style, confidence = bond.estimate_attachment_style()
        assert style is None
        assert confidence == 0.0

    def test_returns_none_at_19_sessions(
        self, bond: BondManager
    ) -> None:
        """Attachment style should still be None at 19 sessions."""
        for i in range(19):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message()]
            bond.update_from_session(session, messages)

        style, confidence = bond.estimate_attachment_style()
        assert style is None
        assert confidence == 0.0

    def test_returns_style_after_20_sessions(
        self, bond: BondManager
    ) -> None:
        """Attachment style should return a style after 20 sessions."""
        for i in range(20):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message(valence=0.7)]
            bond.update_from_session(session, messages)

        style, confidence = bond.estimate_attachment_style()
        assert style is not None
        assert style in ("secure", "anxious", "avoidant", "fearful")
        assert 0.0 <= confidence <= 1.0

    def test_positive_stable_sessions_trend_secure(
        self, bond: BondManager
    ) -> None:
        """Consistently positive, stable sessions should trend toward secure."""
        for i in range(30):
            session = _make_session(session_id=f"sess-{i}")
            # Consistently positive, moderate arousal, steady
            messages = [
                _make_message(valence=0.7, arousal=0.4, vulnerability=0.3),
                _make_message(valence=0.7, arousal=0.4, vulnerability=0.3),
            ]
            bond.update_from_session(session, messages)

        style, confidence = bond.estimate_attachment_style()
        # With consistently warm, stable, trusting sessions,
        # the most likely style is secure
        assert style == "secure"


# ---------------------------------------------------------------------------
# Tests: BondManager — Persistence
# ---------------------------------------------------------------------------

class TestBondPersistence:
    """Tests for Bond save/load round-trip."""

    def test_save_and_load_preserves_field(
        self, bond_path: Path
    ) -> None:
        """Saving and loading should preserve the current field."""
        bm1 = BondManager(bond_path)
        session = _make_session()
        messages = [_make_message(valence=0.9)]
        bm1.update_from_session(session, messages)
        initial_warmth = bm1.current_field.warmth

        bm2 = BondManager(bond_path)
        assert bm2.current_field.warmth == pytest.approx(initial_warmth)

    def test_save_and_load_preserves_history(
        self, bond_path: Path
    ) -> None:
        """Saving and loading should preserve field history."""
        bm1 = BondManager(bond_path)
        for i in range(3):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message()]
            bm1.update_from_session(session, messages)

        bm2 = BondManager(bond_path)
        assert len(bm2.field_history) == 3
        assert bm2.session_count == 3

    def test_save_and_load_preserves_session_count(
        self, bond_path: Path
    ) -> None:
        """Saving and loading should preserve the session count."""
        bm1 = BondManager(bond_path)
        for i in range(5):
            session = _make_session(session_id=f"sess-{i}")
            messages = [_make_message()]
            bm1.update_from_session(session, messages)

        bm2 = BondManager(bond_path)
        assert bm2.session_count == 5


# ---------------------------------------------------------------------------
# Tests: PulseManager — Hour to Time Phase
# ---------------------------------------------------------------------------

class TestHourToTimePhase:
    """Tests for the _hour_to_time_phase helper."""

    @pytest.mark.parametrize(
        "hour, expected",
        [
            (0, "deep_night"),
            (2, "deep_night"),
            (4, "deep_night"),
            (5, "early_morning"),
            (7, "early_morning"),
            (8, "morning"),
            (11, "morning"),
            (12, "afternoon"),
            (16, "afternoon"),
            (17, "evening"),
            (20, "evening"),
            (21, "night"),
            (23, "night"),
        ],
    )
    def test_hour_mapping(self, hour: int, expected: str) -> None:
        """Each hour should map to the correct time phase."""
        assert PulseManager._hour_to_time_phase(hour) == expected
```

---

### Step 3.2: Run the tests

Execute the following command from the project root:

```bash
pytest tests/test_emotional_memory.py -v
```

**Expected result:** All tests pass. If any test fails, read the error message carefully. The most likely causes are:

1. **ImportError for gwen.models.emotional**: Track 002 (data-models) has not been completed yet. `EmotionalStateVector` and `CompassDirection` must exist in `gwen/models/emotional.py`.
2. **ImportError for gwen.models.messages**: Track 002 must be completed. `MessageRecord`, `SessionRecord`, `SessionType`, `SessionEndMode` must exist in `gwen/models/messages.py`.
3. **ImportError for gwen.models.temporal**: Track 002 must be completed. `TimePhase` must exist in `gwen/models/temporal.py`.
4. **ImportError for gwen.models.memory**: Track 002 must be completed. `RelationalField` must exist in `gwen/models/memory.py`.
5. **Assertion failure on day-of-week**: February 9, 2026 must be a Monday for the test to pass. Verify with `datetime(2026, 2, 9).strftime("%A")` which returns "Monday".

---

## Checklist (update after each step)

- [ ] Phase 1 complete: gwen/memory/pulse.py with PulseManager class, rolling averages, baseline retrieval, deviation computation, persistence
- [ ] Phase 2 complete: gwen/memory/bond.py with BondManager class, 6-dimensional field updates, attachment style estimation, persistence
- [ ] Phase 3 complete: tests/test_emotional_memory.py passes with all tests green
