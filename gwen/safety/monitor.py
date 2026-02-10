"""
Safety Monitor — threat detection and response routing.

Evaluates every classified message for threat vectors (self-harm, violence,
dissociation, savior delusion) and determines the appropriate severity level
and response protocol.

Safety is bedrock — it operates below personality, below modes, below user
preferences. It cannot be disabled.

References: SRS.md Section 9 (FR-SAF-001 through FR-SAF-007).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.safety import SafetyEvent, ThreatSeverity, ThreatVector
from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TemporalMetadataEnvelope,
    TimePhase,
)


# ---------------------------------------------------------------------------
# SafetyResult — the output of every safety evaluation
# ---------------------------------------------------------------------------

@dataclass
class SafetyResult:
    """The result of evaluating a message for safety threats."""
    severity: ThreatSeverity = ThreatSeverity.LOW
    flags: list[ThreatVector] = field(default_factory=list)
    recommended_action: str = "none"
    compass_direction: Optional[CompassDirection] = None
    requires_overlay: bool = False


_NO_THREAT_RESULT = SafetyResult(
    severity=ThreatSeverity.LOW,
    flags=[],
    recommended_action="none",
    compass_direction=None,
    requires_overlay=False,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMPORAL_BOOST_PHASES: set[str] = {
    TimePhase.DEEP_NIGHT.value,
    TimePhase.LATE_NIGHT.value,
}

HISTORICAL_EVENT_THRESHOLD = 3
HISTORICAL_WINDOW_DAYS = 7

SEVERITY_ORDER: list[ThreatSeverity] = [
    ThreatSeverity.LOW,
    ThreatSeverity.MEDIUM,
    ThreatSeverity.HIGH,
    ThreatSeverity.CRITICAL,
]

SEVERITY_TO_ACTION: dict[ThreatSeverity, str] = {
    ThreatSeverity.LOW: "monitor",
    ThreatSeverity.MEDIUM: "compass_activation",
    ThreatSeverity.HIGH: "safety_protocol",
    ThreatSeverity.CRITICAL: "immediate_intervention",
}

THREAT_TO_COMPASS: dict[ThreatVector, CompassDirection] = {
    ThreatVector.SELF_HARM: CompassDirection.WEST,
    ThreatVector.VIOLENCE: CompassDirection.SOUTH,
    ThreatVector.DISSOCIATION: CompassDirection.NORTH,
    ThreatVector.SAVIOR_DELUSION: CompassDirection.NORTH,
}

THREAT_BASE_SEVERITY: dict[ThreatVector, ThreatSeverity] = {
    ThreatVector.SELF_HARM: ThreatSeverity.MEDIUM,
    ThreatVector.VIOLENCE: ThreatSeverity.MEDIUM,
    ThreatVector.DISSOCIATION: ThreatSeverity.LOW,
    ThreatVector.SAVIOR_DELUSION: ThreatSeverity.LOW,
}


# ---------------------------------------------------------------------------
# SafetyMonitor
# ---------------------------------------------------------------------------

class SafetyMonitor:
    """Evaluates every message for safety threats and determines response."""

    def __init__(self, ledger) -> None:
        self.ledger = ledger

    def evaluate(
        self,
        emotional_state: EmotionalStateVector,
        safety_flags: list[str],
        tme: Optional[TemporalMetadataEnvelope] = None,
        recent_events: Optional[list[SafetyEvent]] = None,
    ) -> SafetyResult:
        """Evaluate a message for safety threats and determine response.

        Algorithm:
        1. If no safety_flags, return no-threat result immediately
        2. Map string flags to ThreatVector enums (skip unrecognized)
        3. For each threat vector, compute severity with boosts
        4. Take the HIGHEST severity across all detected threats
        5. Determine recommended action and compass direction
        6. Log a SafetyEvent to the ledger
        7. Return SafetyResult
        """
        if not safety_flags:
            return _NO_THREAT_RESULT

        # Map string flags to ThreatVector enums
        threat_vectors: list[ThreatVector] = []
        for flag_str in safety_flags:
            try:
                threat_vectors.append(ThreatVector(flag_str))
            except ValueError:
                continue

        if not threat_vectors:
            return _NO_THREAT_RESULT

        # Compute severity for each threat vector
        max_severity = ThreatSeverity.LOW
        for vector in threat_vectors:
            severity = self._compute_severity(vector, tme, recent_events)
            if _severity_index(severity) > _severity_index(max_severity):
                max_severity = severity

        recommended_action = SEVERITY_TO_ACTION.get(max_severity, "monitor")

        primary_threat = threat_vectors[0]
        compass_direction = THREAT_TO_COMPASS.get(primary_threat)

        requires_overlay = (
            max_severity == ThreatSeverity.CRITICAL
            and ThreatVector.SELF_HARM in threat_vectors
        )

        # Log safety event to ledger
        event = SafetyEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            vector=primary_threat,
            severity=max_severity,
            trigger_message_id=None,
            trigger_description=f"Detected flags: {[v.value for v in threat_vectors]}",
            time_phase=tme.time_phase if tme else TimePhase.MORNING,
            session_duration_sec=tme.session_duration_sec if tme else 0,
            circadian_deviation=(
                tme.circadian_deviation_severity
                if tme
                else CircadianDeviationSeverity.NONE
            ),
            response_action=recommended_action,
            compass_direction_used=compass_direction,
            user_response=None,
            resolved=False,
        )
        self.ledger.log_event(event)

        return SafetyResult(
            severity=max_severity,
            flags=threat_vectors,
            recommended_action=recommended_action,
            compass_direction=compass_direction,
            requires_overlay=requires_overlay,
        )

    def _compute_severity(
        self,
        vector: ThreatVector,
        tme: Optional[TemporalMetadataEnvelope],
        recent_events: Optional[list[SafetyEvent]],
    ) -> ThreatSeverity:
        """Compute severity for a single threat vector with escalation boosts."""
        severity_idx = _severity_index(
            THREAT_BASE_SEVERITY.get(vector, ThreatSeverity.LOW)
        )

        # Temporal boost: DEEP_NIGHT or LATE_NIGHT -> +1
        if tme is not None and tme.time_phase.value in TEMPORAL_BOOST_PHASES:
            severity_idx += 1

        # Historical boost: 3+ similar events in last 7 days -> +1
        if recent_events is not None:
            similar_count = sum(
                1
                for e in recent_events
                if e.vector == vector
            )
            if similar_count >= HISTORICAL_EVENT_THRESHOLD:
                severity_idx += 1

        # Circadian deviation boost: HIGH -> +1
        if (
            tme is not None
            and tme.circadian_deviation_severity == CircadianDeviationSeverity.HIGH
        ):
            severity_idx += 1

        # Cap at CRITICAL (index 3)
        severity_idx = min(severity_idx, len(SEVERITY_ORDER) - 1)

        return SEVERITY_ORDER[severity_idx]


def _severity_index(severity: ThreatSeverity) -> int:
    """Return the numeric index of a ThreatSeverity for comparison."""
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return 0
