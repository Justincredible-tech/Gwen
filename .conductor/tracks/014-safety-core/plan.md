# Plan: Safety Core

**Track:** 014-safety-core
**Depends on:** 005-tier0-pipeline (classification outputs safety_flags), 003-database-layer (Chronicle for historical queries)
**Produces:** gwen/safety/__init__.py, gwen/safety/monitor.py, gwen/safety/ledger.py, tests/test_safety.py

---

## Phase 1: Package Initialization and Safety Result Model

### Step 1.1: Create gwen/safety/__init__.py

Create the file `gwen/safety/__init__.py` with the following exact content:

```python
"""Safety Architecture - threat detection, encrypted ledger, wellness checks."""
```

**Why:** This makes `gwen.safety` a Python package so that `from gwen.safety.monitor import SafetyMonitor` works. If this file already exists from Track 001 scaffold, verify the content matches and skip this step.

**Verification gate (manual):** Run `python -c "import gwen.safety; print('OK')"` and confirm it prints `OK`.

---

### Step 1.2: Add SafetyResult dataclass to gwen/safety/monitor.py

Create the file `gwen/safety/monitor.py` with the following exact content. The SafetyMonitor class is added in Phase 2; this step defines only the SafetyResult model and the severity/routing constants.

```python
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
    """The result of evaluating a message for safety threats.

    Every message in the system is evaluated by the SafetyMonitor, which
    produces a SafetyResult. This result is included in the context
    assembly (Track 010) so that Tier 1 can adjust its response accordingly.

    Attributes
    ----------
    severity : ThreatSeverity
        The highest severity level across all detected threats.
        NONE means no threats detected (the common case).
    flags : list[ThreatVector]
        All threat vectors detected in this message. May be empty.
    recommended_action : str
        What the system should do in response:
        - "none" — no action needed
        - "monitor" — log and watch for escalation
        - "compass_activation" — activate a Compass direction
        - "safety_protocol" — engage safety response protocol
        - "immediate_intervention" — crisis intervention with resource overlay
    compass_direction : CompassDirection or None
        The recommended Compass direction for first-line response.
        None if no Compass activation is needed.
    requires_overlay : bool
        Whether the UI should display a non-dismissable crisis resource
        overlay (e.g., 988 Lifeline, Crisis Text Line). Only True for
        CRITICAL severity self-harm events.
    """
    severity: ThreatSeverity = ThreatSeverity.LOW
    flags: list[ThreatVector] = field(default_factory=list)
    recommended_action: str = "none"
    compass_direction: Optional[CompassDirection] = None
    requires_overlay: bool = False


# ---------------------------------------------------------------------------
# Shared "no threat" result — returned by evaluate() when no flags are
# detected or when all flags are unrecognized. Reused as a singleton to
# avoid allocating identical SafetyResult objects on every clean message.
# ---------------------------------------------------------------------------

_NO_THREAT_RESULT = SafetyResult(
    severity=ThreatSeverity.LOW,
    flags=[],
    recommended_action="none",
    compass_direction=None,
    requires_overlay=False,
)


# ---------------------------------------------------------------------------
# Constants: Temporal boost phases
# ---------------------------------------------------------------------------

# Time phases that increase severity by +1 level (SRS.md FR-SAF-001)
TEMPORAL_BOOST_PHASES: set[str] = {
    TimePhase.DEEP_NIGHT.value,   # 00:00 - 04:59
    TimePhase.LATE_NIGHT.value,   # 21:00 - 23:59
}

# How many similar events in the last N days trigger historical boost
HISTORICAL_EVENT_THRESHOLD = 3
HISTORICAL_WINDOW_DAYS = 7

# Severity ordering for escalation
SEVERITY_ORDER: list[ThreatSeverity] = [
    ThreatSeverity.LOW,
    ThreatSeverity.MEDIUM,
    ThreatSeverity.HIGH,
    ThreatSeverity.CRITICAL,
]

# Map from severity to recommended action
SEVERITY_TO_ACTION: dict[ThreatSeverity, str] = {
    ThreatSeverity.LOW: "monitor",
    ThreatSeverity.MEDIUM: "compass_activation",
    ThreatSeverity.HIGH: "safety_protocol",
    ThreatSeverity.CRITICAL: "immediate_intervention",
}

# Map from threat vector to recommended compass direction for first-line response
# (SRS.md FR-SAF-002 through FR-SAF-005)
THREAT_TO_COMPASS: dict[ThreatVector, CompassDirection] = {
    ThreatVector.SELF_HARM: CompassDirection.WEST,          # Anchoring (distress tolerance)
    ThreatVector.VIOLENCE: CompassDirection.SOUTH,           # Currents (emotion regulation)
    ThreatVector.DISSOCIATION: CompassDirection.NORTH,       # Presence (mindfulness/grounding)
    ThreatVector.SAVIOR_DELUSION: CompassDirection.NORTH,    # Presence + system intervention
}

# Map from threat vector to base severity (before temporal/historical boosts)
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
    """Evaluates every message for safety threats and determines response.

    The SafetyMonitor is called after Phase 3 (classification) of the
    message lifecycle. It takes the classification outputs (safety_flags)
    and temporal context (TME) and produces a SafetyResult that is
    included in the context for Tier 1 response generation.

    Safety detection is continuous — it runs on EVERY message, not just
    messages that "look dangerous." This is because:
    1. Subtle signals accumulate over time (persistent hopelessness)
    2. Temporal context changes meaning (same message at 3 AM vs 3 PM)
    3. Historical patterns require continuous tracking
    """

    def __init__(self, ledger) -> None:
        """Initialize the SafetyMonitor.

        Parameters
        ----------
        ledger : SafetyLedger
            The encrypted safety event log. Used to:
            1. Log safety events when threats are detected
            2. Read historical events for escalation pattern detection
        """
        self.ledger = ledger

    def evaluate(
        self,
        emotional_state: EmotionalStateVector,
        safety_flags: list[str],
        tme: Optional[TemporalMetadataEnvelope] = None,
        recent_events: Optional[list[SafetyEvent]] = None,
    ) -> SafetyResult:
        """Evaluate a message for safety threats and determine response.

        This is the main entry point, called by the orchestrator after
        Phase 3 classification.

        Algorithm:
        1. If no safety_flags, return no-threat result immediately
        2. Map string flags to ThreatVector enums (skip unrecognized flags)
        3. For each threat vector, compute severity:
           a. Start with base severity for this threat type
           b. Apply temporal boost: DEEP_NIGHT/LATE_NIGHT -> +1 severity
           c. Apply historical boost: 3+ similar events in 7 days -> +1 severity
           d. Apply circadian boost: HIGH deviation -> +1 severity
        4. Take the HIGHEST severity across all detected threats
        5. Determine recommended action from severity level
        6. Determine compass direction from the first (highest-priority) threat
        7. Log a SafetyEvent to the ledger
        8. Return SafetyResult

        Parameters
        ----------
        emotional_state : EmotionalStateVector
            The classified emotional state of the message.
        safety_flags : list[str]
            Safety flags from the classification pipeline (Phase 3).
            These are string values like "self_harm", "violence",
            "dissociation", "savior_delusion". Unrecognized strings
            are silently ignored.
        tme : TemporalMetadataEnvelope, optional
            The temporal context of the message. Used for temporal
            severity boosting. If None, no temporal boost is applied.
        recent_events : list[SafetyEvent], optional
            Recent safety events from the ledger. Used for historical
            pattern detection. If None, no historical boost is applied.
            The caller should pass events from the last 7 days.

        Returns
        -------
        SafetyResult
            The evaluation result with severity, flags, recommended
            action, compass direction, and overlay requirement.
        """
        # Step 1: Early return if no flags
        if not safety_flags:
            return _NO_THREAT_RESULT

        # Step 2: Map string flags to ThreatVector enums
        threat_vectors: list[ThreatVector] = []
        for flag_str in safety_flags:
            try:
                threat_vectors.append(ThreatVector(flag_str))
            except ValueError:
                # Unrecognized flag — skip silently. This is intentional:
                # the classification pipeline might produce flags that
                # the safety monitor does not yet handle.
                continue

        if not threat_vectors:
            return _NO_THREAT_RESULT

        # Step 3: Compute severity for each threat vector
        max_severity = ThreatSeverity.LOW
        for vector in threat_vectors:
            severity = self._compute_severity(vector, tme, recent_events)
            if _severity_index(severity) > _severity_index(max_severity):
                max_severity = severity

        # Step 4: Determine recommended action
        recommended_action = SEVERITY_TO_ACTION.get(max_severity, "monitor")

        # Step 5: Determine compass direction from primary threat
        # The primary threat is the first one in the list (highest priority
        # because classification pipeline orders flags by confidence)
        primary_threat = threat_vectors[0]
        compass_direction = THREAT_TO_COMPASS.get(primary_threat)

        # Step 6: Determine if crisis overlay is needed
        requires_overlay = (
            max_severity == ThreatSeverity.CRITICAL
            and ThreatVector.SELF_HARM in threat_vectors
        )

        # Step 7: Log safety event to ledger
        event = SafetyEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            vector=primary_threat,
            severity=max_severity,
            trigger_message_id=None,  # Set by caller if available
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

        # Step 8: Return result
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
        """Compute the severity level for a single threat vector.

        Starts with the base severity for this threat type, then applies
        three escalation boosts:
        1. Temporal boost: late-night/deep-night -> +1 severity level
        2. Historical boost: 3+ similar events in 7 days -> +1 severity level
        3. Circadian deviation boost: HIGH deviation -> +1 severity level

        Each boost can increase severity by at most one level. Multiple
        boosts can stack (e.g., late-night + historical pattern = +2).
        Severity is capped at CRITICAL.

        Parameters
        ----------
        vector : ThreatVector
            The specific threat vector to evaluate.
        tme : TemporalMetadataEnvelope, optional
            Temporal context for boost computation.
        recent_events : list[SafetyEvent], optional
            Recent safety events for historical pattern detection.

        Returns
        -------
        ThreatSeverity
            The computed severity level after all boosts.
        """
        # Start with base severity
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
    """Return the numeric index of a ThreatSeverity for comparison.

    Parameters
    ----------
    severity : ThreatSeverity
        The severity to look up.

    Returns
    -------
    int
        0 for LOW, 1 for MEDIUM, 2 for HIGH, 3 for CRITICAL.
    """
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return 0
```

**What this does:**
1. `SafetyResult` is a dataclass that carries the output of every safety evaluation.
2. Constants define the routing tables: which severity maps to which action, which threat maps to which compass direction, which time phases boost severity.
3. `SafetyMonitor.evaluate()` implements FR-SAF-001 — the full threat evaluation pipeline with temporal, historical, and circadian escalation.
4. `SafetyMonitor._compute_severity()` handles the severity escalation logic for a single threat vector.
5. `_severity_index()` converts ThreatSeverity to an integer for comparison and escalation.

---

## Phase 2: Safety Ledger

### Step 2.1: Create gwen/safety/ledger.py

Create the file `gwen/safety/ledger.py` with the following exact content:

```python
"""
Safety Ledger — encrypted, append-only safety event log.

The Safety Ledger is the permanent record of all safety-relevant events:
safety events, wellness checkpoints, and mode changes. It is encrypted
with Fernet (from the cryptography library) so that ledger data is
protected at rest.

CRITICAL DESIGN DECISION: There is NO delete method. This is intentional.
The Safety Ledger is append-only by design. A user can VIEW and EXPORT
their data, but they cannot delete individual entries. This ensures that
safety event history is always available for pattern detection, even if
the user is in a state where they might want to hide concerning patterns.

References: SRS.md FR-SAF-006.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

from gwen.models.emotional import CompassDirection
from gwen.models.safety import (
    SafetyEvent,
    ThreatSeverity,
    ThreatVector,
    WellnessCheckpoint,
)
from gwen.models.temporal import CircadianDeviationSeverity, TimePhase


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

def _get_or_create_key(key_path: Path) -> bytes:
    """Load an existing Fernet key or generate a new one.

    Parameters
    ----------
    key_path : Path
        Path to the key file. If the file exists, the key is loaded
        from it. If it does not exist, a new key is generated and
        saved to this path.

    Returns
    -------
    bytes
        A valid Fernet key (44 bytes, URL-safe base64 encoded).

    Notes
    -----
    The key file should be protected by OS-level file permissions.
    In a production deployment, this would use OS keychain integration.
    For Phase 1 (local-only CLI), file-based key storage is acceptable.
    """
    key_path = Path(key_path)
    if key_path.exists():
        return key_path.read_bytes().strip()

    # Generate new key
    key = Fernet.generate_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    return key


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_safety_event(event: SafetyEvent) -> dict:
    """Convert a SafetyEvent to a JSON-serializable dict.

    Parameters
    ----------
    event : SafetyEvent
        The safety event to serialize.

    Returns
    -------
    dict
        A plain dict with all fields converted to JSON-safe types.
    """
    return {
        "entry_type": "safety_event",
        "id": event.id,
        "timestamp": event.timestamp.isoformat(),
        "vector": event.vector.value,
        "severity": event.severity.value,
        "trigger_message_id": event.trigger_message_id,
        "trigger_description": event.trigger_description,
        "time_phase": event.time_phase.value if event.time_phase else None,
        "session_duration_sec": event.session_duration_sec,
        "circadian_deviation": (
            event.circadian_deviation.value
            if event.circadian_deviation
            else None
        ),
        "response_action": event.response_action,
        "compass_direction_used": (
            event.compass_direction_used.value
            if event.compass_direction_used
            else None
        ),
        "user_response": event.user_response,
        "resolved": event.resolved,
    }


def _serialize_wellness_checkpoint(checkpoint: WellnessCheckpoint) -> dict:
    """Convert a WellnessCheckpoint to a JSON-serializable dict.

    Parameters
    ----------
    checkpoint : WellnessCheckpoint
        The wellness checkpoint to serialize.

    Returns
    -------
    dict
        A plain dict with all fields converted to JSON-safe types.
    """
    return {
        "entry_type": "wellness_checkpoint",
        "id": checkpoint.id,
        "timestamp": checkpoint.timestamp.isoformat(),
        "immersion_hours_since_last": checkpoint.immersion_hours_since_last,
        "q1_last_human_conversation": checkpoint.q1_last_human_conversation,
        "q2_life_outside_gwen": checkpoint.q2_life_outside_gwen,
        "q3_avoiding_anything": checkpoint.q3_avoiding_anything,
        "concern_flags": checkpoint.concern_flags,
        "escalated": checkpoint.escalated,
    }


def _serialize_mode_change(
    from_mode: str, to_mode: str, timestamp: datetime
) -> dict:
    """Create a JSON-serializable dict for a mode change event.

    Parameters
    ----------
    from_mode : str
        The mode being left (e.g., "grounded", "immersion").
    to_mode : str
        The mode being entered.
    timestamp : datetime
        When the mode change occurred.

    Returns
    -------
    dict
        A plain dict representing the mode change.
    """
    return {
        "entry_type": "mode_change",
        "from_mode": from_mode,
        "to_mode": to_mode,
        "timestamp": timestamp.isoformat(),
    }


# ---------------------------------------------------------------------------
# SafetyLedger
# ---------------------------------------------------------------------------

class SafetyLedger:
    """Encrypted, append-only safety event log.

    The ledger stores safety events, wellness checkpoints, and mode
    changes as Fernet-encrypted JSON lines in a single file. Each line
    in the file is independently encrypted, making the format resilient
    to partial corruption.

    File format:
        Each line = Fernet.encrypt(json.dumps(entry).encode("utf-8"))
        Lines are separated by newlines (``\\n``)
        Each line is independently decryptable

    IMPORTANT: There is NO delete method. This is by design (FR-SAF-006).
    Users can view (read_all) and export (export_plaintext) their data,
    but cannot remove individual entries. This ensures safety event
    history is always available for pattern detection.
    """

    def __init__(
        self,
        ledger_path: str,
        encryption_key: Optional[bytes] = None,
        key_path: Optional[str] = None,
    ) -> None:
        """Initialize the SafetyLedger.

        Parameters
        ----------
        ledger_path : str
            Path to the ledger file. Will be created if it does not exist.
            The parent directory must exist.
        encryption_key : bytes, optional
            A Fernet encryption key. If provided, this key is used directly.
            If not provided, a key is loaded from (or generated at) key_path.
        key_path : str, optional
            Path to the key file. Used only if encryption_key is not provided.
            Defaults to ``<ledger_path>.key`` (i.e., the ledger path with
            ``.key`` appended).
        """
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        # Resolve encryption key
        if encryption_key is not None:
            self._key = encryption_key
        else:
            if key_path is None:
                key_path = str(self.ledger_path) + ".key"
            self._key = _get_or_create_key(Path(key_path))

        self._fernet = Fernet(self._key)

    def _append_entry(self, entry_dict: dict) -> None:
        """Encrypt and append a single entry to the ledger file.

        Parameters
        ----------
        entry_dict : dict
            A JSON-serializable dictionary to encrypt and store.
        """
        plaintext = json.dumps(entry_dict).encode("utf-8")
        encrypted = self._fernet.encrypt(plaintext)
        with open(self.ledger_path, "ab") as f:
            f.write(encrypted + b"\n")

    def log_event(self, event: SafetyEvent) -> None:
        """Append a safety event to the encrypted ledger.

        Parameters
        ----------
        event : SafetyEvent
            The safety event to log. Serialized to JSON, encrypted
            with Fernet, and appended as a single line.
        """
        entry = _serialize_safety_event(event)
        self._append_entry(entry)

    def log_checkpoint(self, checkpoint: WellnessCheckpoint) -> None:
        """Append a wellness checkpoint to the encrypted ledger.

        Parameters
        ----------
        checkpoint : WellnessCheckpoint
            The 48-hour wellness checkpoint to log.
        """
        entry = _serialize_wellness_checkpoint(checkpoint)
        self._append_entry(entry)

    def log_mode_change(
        self, from_mode: str, to_mode: str, timestamp: datetime
    ) -> None:
        """Log a mode transition to the encrypted ledger.

        Parameters
        ----------
        from_mode : str
            The mode being left (e.g., "grounded").
        to_mode : str
            The mode being entered (e.g., "immersion").
        timestamp : datetime
            When the mode change occurred.
        """
        entry = _serialize_mode_change(from_mode, to_mode, timestamp)
        self._append_entry(entry)

    def read_all(self) -> list[dict]:
        """Decrypt and return all ledger entries.

        Returns
        -------
        list[dict]
            A list of decrypted entry dicts, in the order they were
            written (oldest first). Each dict has an "entry_type" field
            indicating whether it is a "safety_event", "wellness_checkpoint",
            or "mode_change".

        Returns an empty list if the ledger file does not exist or is empty.
        """
        if not self.ledger_path.exists():
            return []

        entries: list[dict] = []
        with open(self.ledger_path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    decrypted = self._fernet.decrypt(line)
                    entry = json.loads(decrypted.decode("utf-8"))
                    entries.append(entry)
                except Exception:
                    # Skip corrupted lines. In a production system, we would
                    # log a warning here. For Phase 1, silent skip is acceptable.
                    continue

        return entries

    def export_plaintext(self, output_path: str) -> None:
        """Export the ledger as readable plaintext for sharing with a professional.

        Reads all entries, formats them as human-readable text, and writes
        them to the specified output file. The output is NOT encrypted.

        Parameters
        ----------
        output_path : str
            Path to write the plaintext export. Will overwrite if exists.

        Notes
        -----
        This is intended for the user to share their safety history with
        a therapist, counselor, or other professional. The export includes
        all fields in a readable format.
        """
        entries = self.read_all()
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("GWEN SAFETY LEDGER EXPORT")
        lines.append(f"Exported at: {datetime.utcnow().isoformat()}")
        lines.append(f"Total entries: {len(entries)}")
        lines.append("=" * 60)
        lines.append("")

        for i, entry in enumerate(entries, start=1):
            entry_type = entry.get("entry_type", "unknown")
            lines.append(f"--- Entry {i} ({entry_type}) ---")

            if entry_type == "safety_event":
                lines.append(f"  Timestamp:     {entry.get('timestamp', 'N/A')}")
                lines.append(f"  Threat Vector: {entry.get('vector', 'N/A')}")
                lines.append(f"  Severity:      {entry.get('severity', 'N/A')}")
                lines.append(f"  Trigger:       {entry.get('trigger_description', 'N/A')}")
                lines.append(f"  Time Phase:    {entry.get('time_phase', 'N/A')}")
                lines.append(f"  Session Dur:   {entry.get('session_duration_sec', 'N/A')}s")
                lines.append(f"  Action Taken:  {entry.get('response_action', 'N/A')}")
                lines.append(f"  Compass Dir:   {entry.get('compass_direction_used', 'N/A')}")
                lines.append(f"  Resolved:      {entry.get('resolved', 'N/A')}")

            elif entry_type == "wellness_checkpoint":
                lines.append(f"  Timestamp:     {entry.get('timestamp', 'N/A')}")
                lines.append(f"  Immersion Hrs: {entry.get('immersion_hours_since_last', 'N/A')}")
                lines.append(f"  Q1 (Human):    {entry.get('q1_last_human_conversation', 'N/A')}")
                lines.append(f"  Q2 (Life):     {entry.get('q2_life_outside_gwen', 'N/A')}")
                lines.append(f"  Q3 (Avoiding): {entry.get('q3_avoiding_anything', 'N/A')}")
                lines.append(f"  Concern Flags: {entry.get('concern_flags', [])}")
                lines.append(f"  Escalated:     {entry.get('escalated', 'N/A')}")

            elif entry_type == "mode_change":
                lines.append(f"  Timestamp:     {entry.get('timestamp', 'N/A')}")
                lines.append(f"  From Mode:     {entry.get('from_mode', 'N/A')}")
                lines.append(f"  To Mode:       {entry.get('to_mode', 'N/A')}")

            else:
                lines.append(f"  Raw data: {json.dumps(entry, indent=2)}")

            lines.append("")

        lines.append("=" * 60)
        lines.append("END OF EXPORT")
        lines.append("=" * 60)

        output.write_text("\n".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------
    # IMPORTANT: There is NO delete method. This is intentional.
    #
    # The Safety Ledger is append-only by design (SRS.md FR-SAF-006).
    # Users can VIEW their data (read_all) and EXPORT it (export_plaintext),
    # but they cannot delete individual entries.
    #
    # Rationale: Safety event history must be available for pattern
    # detection (e.g., escalating self-harm signals over time). Allowing
    # deletion would let a user in crisis hide concerning patterns from
    # the system's protective mechanisms.
    #
    # If a user needs full data deletion (GDPR/right to be forgotten),
    # they can delete the entire ledger FILE, which is their right.
    # But the system does not provide a method to selectively delete.
    # ------------------------------------------------------------------
```

**What this does:**
1. `_get_or_create_key()` handles key lifecycle — loads existing or generates new Fernet key.
2. Serialization helpers convert SafetyEvent, WellnessCheckpoint, and mode changes to JSON-safe dicts.
3. `SafetyLedger._append_entry()` encrypts a dict and appends it as a line to the ledger file.
4. `log_event()`, `log_checkpoint()`, `log_mode_change()` are the three append methods.
5. `read_all()` decrypts every line and returns the full history.
6. `export_plaintext()` produces a human-readable text file for sharing with professionals.
7. There is NO delete method — this is emphasized with a long comment explaining why.

---

## Phase 3: Integration

### Step 3.1: Update orchestrator to call SafetyMonitor

This step modifies `gwen/core/orchestrator.py` to call `safety_monitor.evaluate()` after Phase 3 classification and include `SafetyResult` in context assembly. **If the orchestrator does not yet exist (Track 008 not complete), skip this step and leave a TODO note.**

The integration pattern is:

```python
# In gwen/core/orchestrator.py, after Phase 3 classification:

from gwen.safety.monitor import SafetyMonitor, SafetyResult
from gwen.safety.ledger import SafetyLedger

# During orchestrator initialization:
self.safety_ledger = SafetyLedger(
    ledger_path=str(data_dir / "safety_ledger.enc"),
)
self.safety_monitor = SafetyMonitor(ledger=self.safety_ledger)

# After Phase 3 classification, before Phase 5 context assembly:
safety_result = self.safety_monitor.evaluate(
    emotional_state=classified.emotional_state,
    safety_flags=classified.safety_flags,
    tme=tme,
    recent_events=self._get_recent_safety_events(),
)

# Include in context assembly (Track 010):
context = self.context_assembler.assemble(
    ...,
    safety_result=safety_result,
)
```

**If Track 008 is not complete:** Do NOT create orchestrator.py. Instead, add a note: "Integration deferred — orchestrator not yet available."

---

## Phase 4: Tests

### Step 4.1: Write tests/test_safety.py

Create the file `tests/test_safety.py` with the following exact content:

```python
"""Tests for the Safety Architecture — threat detection and encrypted ledger.

Run with:
    pytest tests/test_safety.py -v
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest
from cryptography.fernet import Fernet

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.safety import SafetyEvent, ThreatSeverity, ThreatVector, WellnessCheckpoint
from gwen.models.temporal import (
    CircadianDeviationSeverity,
    TemporalMetadataEnvelope,
    TimePhase,
)
from gwen.safety.ledger import SafetyLedger, _get_or_create_key
from gwen.safety.monitor import (
    SEVERITY_TO_ACTION,
    THREAT_BASE_SEVERITY,
    THREAT_TO_COMPASS,
    SafetyMonitor,
    SafetyResult,
    _severity_index,
)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

def _make_emotional_state(**overrides) -> EmotionalStateVector:
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


def _make_tme(
    time_phase: TimePhase = TimePhase.MORNING,
    circadian_deviation: CircadianDeviationSeverity = CircadianDeviationSeverity.NONE,
    session_duration_sec: int = 600,
) -> TemporalMetadataEnvelope:
    """Create a minimal TME for testing.

    Only the fields used by SafetyMonitor are populated. Other fields
    are set to plausible defaults.
    """
    now = datetime.utcnow()
    return TemporalMetadataEnvelope(
        timestamp_utc=now,
        local_time=now,
        hour_of_day=10,
        day_of_week="Monday",
        day_of_month=9,
        month=2,
        year=2026,
        is_weekend=False,
        time_phase=time_phase,
        session_id="test-session",
        session_start=now - timedelta(seconds=session_duration_sec),
        session_duration_sec=session_duration_sec,
        msg_index_in_session=5,
        time_since_last_msg_sec=10.0,
        time_since_last_user_msg_sec=10.0,
        time_since_last_gwen_msg_sec=5.0,
        user_msgs_last_5min=3,
        user_msgs_last_hour=20,
        user_msgs_last_24hr=50,
        last_session_end=now - timedelta(hours=12),
        hours_since_last_session=12.0,
        sessions_last_7_days=5,
        sessions_last_30_days=20,
        avg_session_gap_30d_hours=14.0,
        circadian_deviation_severity=circadian_deviation,
        circadian_deviation_type=None,
    )


def _make_safety_event(
    vector: ThreatVector = ThreatVector.SELF_HARM,
    severity: ThreatSeverity = ThreatSeverity.MEDIUM,
    days_ago: float = 1.0,
) -> SafetyEvent:
    """Create a SafetyEvent for testing historical pattern detection."""
    return SafetyEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow() - timedelta(days=days_ago),
        vector=vector,
        severity=severity,
        trigger_message_id=None,
        trigger_description="test event",
        time_phase=TimePhase.MORNING,
        session_duration_sec=600,
        circadian_deviation=CircadianDeviationSeverity.NONE,
        response_action="monitor",
        compass_direction_used=None,
        user_response=None,
        resolved=False,
    )


def _make_wellness_checkpoint() -> WellnessCheckpoint:
    """Create a WellnessCheckpoint for testing."""
    return WellnessCheckpoint(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        immersion_hours_since_last=48.0,
        q1_last_human_conversation="Yesterday at lunch",
        q2_life_outside_gwen="Doing okay, work is busy",
        q3_avoiding_anything="Not really",
        concern_flags=[],
        escalated=False,
    )


@pytest.fixture()
def tmp_ledger(tmp_path: Path) -> SafetyLedger:
    """Return a SafetyLedger backed by a temporary directory."""
    ledger_path = tmp_path / "test_ledger.enc"
    return SafetyLedger(
        ledger_path=str(ledger_path),
        key_path=str(tmp_path / "test_key"),
    )


@pytest.fixture()
def monitor(tmp_ledger: SafetyLedger) -> SafetyMonitor:
    """Return a SafetyMonitor with a temporary ledger."""
    return SafetyMonitor(ledger=tmp_ledger)


# ---------------------------------------------------------------------------
# Tests: SafetyResult
# ---------------------------------------------------------------------------

class TestSafetyResult:
    """Tests for the SafetyResult dataclass."""

    def test_default_values(self) -> None:
        """SafetyResult should have sensible defaults."""
        result = SafetyResult()
        assert result.severity == ThreatSeverity.LOW
        assert result.flags == []
        assert result.recommended_action == "none"
        assert result.compass_direction is None
        assert result.requires_overlay is False


# ---------------------------------------------------------------------------
# Tests: SafetyMonitor.evaluate()
# ---------------------------------------------------------------------------

class TestSafetyMonitorEvaluate:
    """Tests for SafetyMonitor.evaluate()."""

    def test_no_flags_returns_no_threat(self, monitor: SafetyMonitor) -> None:
        """With no safety flags, result should be no-threat."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=[],
        )
        assert result.recommended_action == "none"
        assert result.flags == []

    def test_unrecognized_flag_ignored(self, monitor: SafetyMonitor) -> None:
        """Unrecognized flag strings should be silently ignored."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["not_a_real_flag"],
        )
        assert result.recommended_action == "none"
        assert result.flags == []

    def test_self_harm_detected(self, monitor: SafetyMonitor) -> None:
        """Self-harm flag should produce MEDIUM severity (base)."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
        )
        assert ThreatVector.SELF_HARM in result.flags
        assert result.severity == ThreatSeverity.MEDIUM
        assert result.recommended_action == "compass_activation"

    def test_violence_detected(self, monitor: SafetyMonitor) -> None:
        """Violence flag should produce MEDIUM severity (base)."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["violence"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
        )
        assert ThreatVector.VIOLENCE in result.flags
        assert result.severity == ThreatSeverity.MEDIUM

    def test_dissociation_detected(self, monitor: SafetyMonitor) -> None:
        """Dissociation flag should produce LOW severity (base)."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["dissociation"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
        )
        assert ThreatVector.DISSOCIATION in result.flags
        assert result.severity == ThreatSeverity.LOW

    def test_savior_delusion_detected(self, monitor: SafetyMonitor) -> None:
        """Savior delusion flag should produce LOW severity (base)."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["savior_delusion"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
        )
        assert ThreatVector.SAVIOR_DELUSION in result.flags
        assert result.severity == ThreatSeverity.LOW

    def test_self_harm_compass_is_west(self, monitor: SafetyMonitor) -> None:
        """Self-harm should route to WEST (Anchoring/distress tolerance)."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
        )
        assert result.compass_direction == CompassDirection.WEST

    def test_violence_compass_is_south(self, monitor: SafetyMonitor) -> None:
        """Violence should route to SOUTH (Currents/emotion regulation)."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["violence"],
        )
        assert result.compass_direction == CompassDirection.SOUTH

    def test_dissociation_compass_is_north(self, monitor: SafetyMonitor) -> None:
        """Dissociation should route to NORTH (Presence/grounding)."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["dissociation"],
        )
        assert result.compass_direction == CompassDirection.NORTH


# ---------------------------------------------------------------------------
# Tests: Severity Escalation
# ---------------------------------------------------------------------------

class TestSeverityEscalation:
    """Tests for severity escalation via temporal and historical boosts."""

    def test_temporal_boost_deep_night(self, monitor: SafetyMonitor) -> None:
        """DEEP_NIGHT should boost severity by +1 level."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.DEEP_NIGHT),
        )
        # Base: MEDIUM + temporal boost: +1 -> HIGH
        assert result.severity == ThreatSeverity.HIGH
        assert result.recommended_action == "safety_protocol"

    def test_temporal_boost_late_night(self, monitor: SafetyMonitor) -> None:
        """LATE_NIGHT should boost severity by +1 level."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.LATE_NIGHT),
        )
        # Base: MEDIUM + temporal boost: +1 -> HIGH
        assert result.severity == ThreatSeverity.HIGH

    def test_no_temporal_boost_morning(self, monitor: SafetyMonitor) -> None:
        """MORNING should NOT boost severity."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
        )
        assert result.severity == ThreatSeverity.MEDIUM

    def test_historical_boost(self, monitor: SafetyMonitor) -> None:
        """3+ similar events in 7 days should boost severity by +1."""
        recent_events = [
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=1),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=2),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
            recent_events=recent_events,
        )
        # Base: MEDIUM + historical boost: +1 -> HIGH
        assert result.severity == ThreatSeverity.HIGH

    def test_no_historical_boost_different_vector(self, monitor: SafetyMonitor) -> None:
        """Historical events of a DIFFERENT vector should not boost."""
        recent_events = [
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=1),
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=2),
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.MORNING),
            recent_events=recent_events,
        )
        # Base: MEDIUM, no boost because historical events are VIOLENCE not SELF_HARM
        assert result.severity == ThreatSeverity.MEDIUM

    def test_circadian_deviation_boost(self, monitor: SafetyMonitor) -> None:
        """HIGH circadian deviation should boost severity by +1."""
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(
                time_phase=TimePhase.MORNING,
                circadian_deviation=CircadianDeviationSeverity.HIGH,
            ),
        )
        # Base: MEDIUM + circadian boost: +1 -> HIGH
        assert result.severity == ThreatSeverity.HIGH

    def test_multiple_boosts_stack(self, monitor: SafetyMonitor) -> None:
        """Multiple boosts should stack: temporal + historical -> +2."""
        recent_events = [
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=1),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=2),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.DEEP_NIGHT),
            recent_events=recent_events,
        )
        # Base: MEDIUM + temporal: +1 + historical: +1 -> CRITICAL
        assert result.severity == ThreatSeverity.CRITICAL

    def test_severity_capped_at_critical(self, monitor: SafetyMonitor) -> None:
        """Severity should not exceed CRITICAL even with all boosts."""
        recent_events = [
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=1),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=2),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(
                time_phase=TimePhase.DEEP_NIGHT,
                circadian_deviation=CircadianDeviationSeverity.HIGH,
            ),
            recent_events=recent_events,
        )
        # Base: MEDIUM + temporal: +1 + historical: +1 + circadian: +1
        # = index 4, but capped at index 3 (CRITICAL)
        assert result.severity == ThreatSeverity.CRITICAL

    def test_critical_self_harm_requires_overlay(self, monitor: SafetyMonitor) -> None:
        """CRITICAL self-harm should require crisis resource overlay."""
        recent_events = [
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=1),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=2),
            _make_safety_event(vector=ThreatVector.SELF_HARM, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
            tme=_make_tme(time_phase=TimePhase.DEEP_NIGHT),
            recent_events=recent_events,
        )
        assert result.severity == ThreatSeverity.CRITICAL
        assert result.requires_overlay is True

    def test_critical_violence_no_overlay(self, monitor: SafetyMonitor) -> None:
        """CRITICAL violence should NOT require overlay (overlay is self-harm only)."""
        recent_events = [
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=1),
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=2),
            _make_safety_event(vector=ThreatVector.VIOLENCE, days_ago=3),
        ]
        result = monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["violence"],
            tme=_make_tme(time_phase=TimePhase.DEEP_NIGHT),
            recent_events=recent_events,
        )
        assert result.severity == ThreatSeverity.CRITICAL
        assert result.requires_overlay is False


# ---------------------------------------------------------------------------
# Tests: Safety Ledger
# ---------------------------------------------------------------------------

class TestSafetyLedger:
    """Tests for SafetyLedger — encrypted, append-only storage."""

    def test_key_generation(self, tmp_path: Path) -> None:
        """_get_or_create_key should generate a valid Fernet key."""
        key_path = tmp_path / "test_key"
        key = _get_or_create_key(key_path)
        assert key_path.exists()
        # Verify it is a valid Fernet key by constructing a Fernet instance
        f = Fernet(key)
        assert f is not None

    def test_key_persistence(self, tmp_path: Path) -> None:
        """Loading the key twice should return the same key."""
        key_path = tmp_path / "test_key"
        key1 = _get_or_create_key(key_path)
        key2 = _get_or_create_key(key_path)
        assert key1 == key2

    def test_log_and_read_safety_event(self, tmp_ledger: SafetyLedger) -> None:
        """Log a safety event and read it back."""
        event = _make_safety_event()
        tmp_ledger.log_event(event)

        entries = tmp_ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "safety_event"
        assert entries[0]["vector"] == event.vector.value
        assert entries[0]["severity"] == event.severity.value

    def test_log_and_read_wellness_checkpoint(self, tmp_ledger: SafetyLedger) -> None:
        """Log a wellness checkpoint and read it back."""
        checkpoint = _make_wellness_checkpoint()
        tmp_ledger.log_checkpoint(checkpoint)

        entries = tmp_ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "wellness_checkpoint"
        assert entries[0]["q1_last_human_conversation"] == checkpoint.q1_last_human_conversation

    def test_log_and_read_mode_change(self, tmp_ledger: SafetyLedger) -> None:
        """Log a mode change and read it back."""
        now = datetime.utcnow()
        tmp_ledger.log_mode_change("grounded", "immersion", now)

        entries = tmp_ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "mode_change"
        assert entries[0]["from_mode"] == "grounded"
        assert entries[0]["to_mode"] == "immersion"

    def test_append_only_multiple_entries(self, tmp_ledger: SafetyLedger) -> None:
        """Multiple entries should all be readable in order."""
        event1 = _make_safety_event(vector=ThreatVector.SELF_HARM)
        event2 = _make_safety_event(vector=ThreatVector.VIOLENCE)
        checkpoint = _make_wellness_checkpoint()

        tmp_ledger.log_event(event1)
        tmp_ledger.log_event(event2)
        tmp_ledger.log_checkpoint(checkpoint)

        entries = tmp_ledger.read_all()
        assert len(entries) == 3
        assert entries[0]["vector"] == "self_harm"
        assert entries[1]["vector"] == "violence"
        assert entries[2]["entry_type"] == "wellness_checkpoint"

    def test_no_delete_method(self, tmp_ledger: SafetyLedger) -> None:
        """SafetyLedger should NOT have a delete method."""
        assert not hasattr(tmp_ledger, "delete")
        assert not hasattr(tmp_ledger, "delete_event")
        assert not hasattr(tmp_ledger, "delete_entry")
        assert not hasattr(tmp_ledger, "remove")
        assert not hasattr(tmp_ledger, "clear")

    def test_empty_ledger_returns_empty_list(self, tmp_ledger: SafetyLedger) -> None:
        """Reading an empty (or nonexistent) ledger should return []."""
        entries = tmp_ledger.read_all()
        assert entries == []

    def test_encryption_roundtrip(self, tmp_ledger: SafetyLedger) -> None:
        """Data should survive encryption -> storage -> decryption."""
        event = _make_safety_event()
        tmp_ledger.log_event(event)

        entries = tmp_ledger.read_all()
        assert len(entries) == 1
        # Verify critical fields survived
        assert entries[0]["id"] == event.id
        assert entries[0]["trigger_description"] == event.trigger_description

    def test_ledger_file_is_encrypted(self, tmp_ledger: SafetyLedger) -> None:
        """The raw file content should NOT contain plaintext event data."""
        event = _make_safety_event()
        event_with_unique_text = SafetyEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            vector=ThreatVector.SELF_HARM,
            severity=ThreatSeverity.HIGH,
            trigger_message_id=None,
            trigger_description="UNIQUE_PLAINTEXT_MARKER_12345",
            time_phase=TimePhase.MORNING,
            session_duration_sec=600,
            circadian_deviation=CircadianDeviationSeverity.NONE,
            response_action="safety_protocol",
            compass_direction_used=CompassDirection.WEST,
            user_response=None,
            resolved=False,
        )
        tmp_ledger.log_event(event_with_unique_text)

        # Read raw file — should NOT contain the plaintext marker
        raw_content = tmp_ledger.ledger_path.read_bytes()
        assert b"UNIQUE_PLAINTEXT_MARKER_12345" not in raw_content

    def test_export_plaintext(self, tmp_ledger: SafetyLedger, tmp_path: Path) -> None:
        """export_plaintext should produce a readable text file."""
        event = _make_safety_event()
        tmp_ledger.log_event(event)

        export_path = tmp_path / "export.txt"
        tmp_ledger.export_plaintext(str(export_path))

        assert export_path.exists()
        content = export_path.read_text(encoding="utf-8")
        assert "GWEN SAFETY LEDGER EXPORT" in content
        assert "safety_event" in content
        assert "Total entries: 1" in content
        assert "END OF EXPORT" in content

    def test_export_plaintext_with_all_types(
        self, tmp_ledger: SafetyLedger, tmp_path: Path
    ) -> None:
        """Export should format all three entry types."""
        tmp_ledger.log_event(_make_safety_event())
        tmp_ledger.log_checkpoint(_make_wellness_checkpoint())
        tmp_ledger.log_mode_change("grounded", "immersion", datetime.utcnow())

        export_path = tmp_path / "export_all.txt"
        tmp_ledger.export_plaintext(str(export_path))

        content = export_path.read_text(encoding="utf-8")
        assert "safety_event" in content
        assert "wellness_checkpoint" in content
        assert "mode_change" in content
        assert "Total entries: 3" in content


# ---------------------------------------------------------------------------
# Tests: Monitor logs events to ledger
# ---------------------------------------------------------------------------

class TestMonitorLedgerIntegration:
    """Tests that SafetyMonitor correctly logs events to the ledger."""

    def test_evaluate_logs_to_ledger(
        self, tmp_ledger: SafetyLedger, monitor: SafetyMonitor
    ) -> None:
        """evaluate() should log a safety event to the ledger."""
        monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=["self_harm"],
        )

        entries = tmp_ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "safety_event"
        assert entries[0]["vector"] == "self_harm"

    def test_no_flags_no_log(
        self, tmp_ledger: SafetyLedger, monitor: SafetyMonitor
    ) -> None:
        """evaluate() with no flags should NOT log to the ledger."""
        monitor.evaluate(
            emotional_state=_make_emotional_state(),
            safety_flags=[],
        )

        entries = tmp_ledger.read_all()
        assert len(entries) == 0


# ---------------------------------------------------------------------------
# Tests: Severity index helper
# ---------------------------------------------------------------------------

class TestSeverityIndex:
    """Tests for _severity_index()."""

    def test_ordering(self) -> None:
        """LOW < MEDIUM < HIGH < CRITICAL."""
        assert _severity_index(ThreatSeverity.LOW) == 0
        assert _severity_index(ThreatSeverity.MEDIUM) == 1
        assert _severity_index(ThreatSeverity.HIGH) == 2
        assert _severity_index(ThreatSeverity.CRITICAL) == 3
```

**What these tests cover:**
- `SafetyResult`: default values
- `SafetyMonitor.evaluate()`: no flags, unrecognized flags, all 4 threat vectors, compass direction routing
- Severity escalation: temporal boost (deep night, late night, no boost morning), historical boost (same vector, different vector), circadian deviation, stacking, cap at CRITICAL, overlay requirement
- `SafetyLedger`: key generation, key persistence, log/read for all 3 entry types, append-only ordering, no delete method, empty ledger, encryption roundtrip, raw file encrypted, export plaintext with all types
- Monitor-ledger integration: evaluate logs events, no flags no log
- `_severity_index`: ordering verification

---

### Step 4.2: Run the tests

Execute the following command from the project root:

```bash
pytest tests/test_safety.py -v
```

**Expected result:** All tests pass. If any test fails, read the error message carefully. The most likely causes are:

1. **ImportError for gwen.models**: Track 002 (data-models) has not been completed yet. The SafetyEvent, ThreatVector, ThreatSeverity, WellnessCheckpoint models must exist.
2. **ImportError for gwen.safety.monitor or gwen.safety.ledger**: Steps 1.2 and 2.1 were not completed.
3. **ImportError for cryptography**: Run `pip install cryptography` (see tech-stack.md).
4. **TME field mismatches**: The test creates a full TemporalMetadataEnvelope. If Track 002 changed the TME field names, update the `_make_tme()` helper to match.
5. **Assertion failures**: Compare the test's expected severity levels against the escalation logic in monitor.py.

---

## Checklist (update after each step)

- [x] Phase 1 complete: gwen/safety/__init__.py exists; gwen/safety/monitor.py with SafetyResult and SafetyMonitor
- [x] Phase 2 complete: gwen/safety/ledger.py with SafetyLedger (encrypted append-only, NO delete method)
- [x] Phase 3 complete: Integration deferred — orchestrator not yet available (Track 008 not done)
- [x] Phase 4 complete: tests/test_safety.py passes with all tests green
