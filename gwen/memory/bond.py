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


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _field_to_dict(rf: RelationalField) -> dict:
    """Serialize a RelationalField to a plain dict."""
    return {
        "timestamp": rf.timestamp.isoformat(),
        "warmth": rf.warmth,
        "trust": rf.trust,
        "depth": rf.depth,
        "stability": rf.stability,
        "reciprocity": rf.reciprocity,
        "growth": rf.growth,
    }


def _dict_to_field(d: dict) -> RelationalField:
    """Deserialize a dict back to a RelationalField."""
    ts = d.get("timestamp")
    if isinstance(ts, str):
        timestamp = datetime.fromisoformat(ts)
    else:
        timestamp = ts if isinstance(ts, datetime) else datetime.now()

    return RelationalField(
        timestamp=timestamp,
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
        self.current_field: RelationalField = RelationalField(
            timestamp=datetime.now(),
            **DEFAULT_RELATIONAL_FIELD,
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
        now = datetime.now()
        self.current_field = RelationalField(
            timestamp=now,
            warmth=new_warmth,
            trust=new_trust,
            depth=new_depth,
            stability=new_stability,
            reciprocity=new_reciprocity,
            growth=new_growth,
        )

        # --- Record history ---
        self.field_history.append({
            "timestamp": now.isoformat(),
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
        best_style = max(scores, key=lambda k: scores[k])
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
