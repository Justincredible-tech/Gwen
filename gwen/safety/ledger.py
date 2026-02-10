"""
Safety Ledger — encrypted, append-only safety event log.

The Safety Ledger is the permanent record of all safety-relevant events.
It is encrypted with Fernet so that ledger data is protected at rest.

CRITICAL: There is NO delete method. This is intentional (FR-SAF-006).

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
    """Load an existing Fernet key or generate a new one."""
    key_path = Path(key_path)
    if key_path.exists():
        return key_path.read_bytes().strip()

    key = Fernet.generate_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    return key


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_safety_event(event: SafetyEvent) -> dict:
    """Convert a SafetyEvent to a JSON-serializable dict."""
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
    """Convert a WellnessCheckpoint to a JSON-serializable dict."""
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
    """Create a JSON-serializable dict for a mode change event."""
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

    File format:
        Each line = Fernet.encrypt(json.dumps(entry).encode("utf-8"))
        Lines are separated by newlines
        Each line is independently decryptable

    IMPORTANT: There is NO delete method. This is by design (FR-SAF-006).
    """

    def __init__(
        self,
        ledger_path: str,
        encryption_key: Optional[bytes] = None,
        key_path: Optional[str] = None,
    ) -> None:
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        if encryption_key is not None:
            self._key = encryption_key
        else:
            if key_path is None:
                key_path = str(self.ledger_path) + ".key"
            self._key = _get_or_create_key(Path(key_path))

        self._fernet = Fernet(self._key)

    def _append_entry(self, entry_dict: dict) -> None:
        """Encrypt and append a single entry to the ledger file."""
        plaintext = json.dumps(entry_dict).encode("utf-8")
        encrypted = self._fernet.encrypt(plaintext)
        with open(self.ledger_path, "ab") as f:
            f.write(encrypted + b"\n")

    def log_event(self, event: SafetyEvent) -> None:
        """Append a safety event to the encrypted ledger."""
        entry = _serialize_safety_event(event)
        self._append_entry(entry)

    def log_checkpoint(self, checkpoint: WellnessCheckpoint) -> None:
        """Append a wellness checkpoint to the encrypted ledger."""
        entry = _serialize_wellness_checkpoint(checkpoint)
        self._append_entry(entry)

    def log_mode_change(
        self, from_mode: str, to_mode: str, timestamp: datetime
    ) -> None:
        """Log a mode transition to the encrypted ledger."""
        entry = _serialize_mode_change(from_mode, to_mode, timestamp)
        self._append_entry(entry)

    def read_all(self) -> list[dict]:
        """Decrypt and return all ledger entries.

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
                    continue

        return entries

    def export_plaintext(self, output_path: str) -> None:
        """Export the ledger as readable plaintext for sharing with a professional."""
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
    # See SRS.md FR-SAF-006 for rationale.
    # ------------------------------------------------------------------
