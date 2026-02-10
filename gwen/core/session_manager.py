"""Session lifecycle management.

Handles starting sessions, tracking messages, ending sessions,
computing session types, and coordinating gap analysis.
"""

import uuid
import time
from datetime import datetime, timezone
from typing import Optional

from gwen.models.messages import (
    SessionRecord,
    SessionType,
    SessionEndMode,
)
from gwen.models.emotional import EmotionalStateVector, CompassDirection
from gwen.models.memory import GapAnalysis, GapClassification, ReturnContext
from gwen.memory.chronicle import Chronicle
from gwen.temporal.tme import TMEGenerator
from gwen.temporal.gap import compute_gap_analysis, generate_return_context


GOODBYE_KEYWORDS: set[str] = {
    "goodbye", "bye", "goodnight", "good night", "night",
    "see you", "see ya", "talk later", "talk to you later",
    "gotta go", "got to go", "heading out", "signing off",
    "ttyl", "later", "peace", "take care", "cya",
}


def detect_goodbye(message_text: str) -> bool:
    """Check if a message contains an explicit goodbye.

    This is a simple keyword-based check. It converts the message to lowercase
    and checks if any goodbye keyword appears as a substring.

    Args:
        message_text: The raw text of the user's message.

    Returns:
        True if the message contains a goodbye keyword, False otherwise.
    """
    text_lower = message_text.strip().lower()
    for keyword in GOODBYE_KEYWORDS:
        if keyword in text_lower:
            return True
    return False


class SessionManager:
    """Manages conversation session lifecycle.

    Responsibilities:
    - Start and end sessions
    - Track message counts and response latencies
    - Classify session type from duration
    - Detect idle timeouts
    - Coordinate gap analysis at session start
    """

    def __init__(
        self,
        chronicle: Chronicle,
        tme_generator: TMEGenerator,
    ) -> None:
        self.chronicle = chronicle
        self.tme_generator = tme_generator

        self.current_session: Optional[SessionRecord] = None

        self._last_message_time: Optional[float] = None
        self._last_message_sender: Optional[str] = None
        self._user_message_count: int = 0
        self._companion_message_count: int = 0
        self._response_latencies: list[float] = []
        self._session_start_monotonic: Optional[float] = None

        self.current_gap_analysis: Optional[GapAnalysis] = None
        self.current_return_context: Optional[ReturnContext] = None

    def start_session(self, initiated_by: str = "user") -> SessionRecord:
        """Start a new conversation session.

        Args:
            initiated_by: Who started the session ("user" or "companion").

        Returns:
            A partially-filled SessionRecord.

        Raises:
            RuntimeError: If a session is already active.
        """
        if self.current_session is not None:
            raise RuntimeError(
                "Cannot start a new session while one is active. "
                f"Active session: {self.current_session.id}. "
                "Call end_session() first."
            )

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Compute gap analysis
        self.current_gap_analysis = compute_gap_analysis(self.chronicle)

        # Generate return context if gap is notable+
        self.current_return_context = None
        if self.current_gap_analysis is not None:
            classification = self.current_gap_analysis.classification
            if classification in (
                GapClassification.NOTABLE,
                GapClassification.SIGNIFICANT,
                GapClassification.ANOMALOUS,
            ):
                self.current_return_context = generate_return_context(
                    self.current_gap_analysis
                )

        neutral_emotion = EmotionalStateVector(
            valence=0.5,
            arousal=0.3,
            dominance=0.5,
            relational_significance=0.0,
            vulnerability_level=0.0,
            compass_direction=CompassDirection.NONE,
            compass_confidence=0.0,
        )

        session = SessionRecord(
            id=session_id,
            start_time=now,
            end_time=None,
            duration_sec=0,
            session_type=SessionType.PING,
            end_mode=SessionEndMode.NATURAL,
            opening_emotional_state=neutral_emotion,
            peak_emotional_state=neutral_emotion,
            closing_emotional_state=neutral_emotion,
            emotional_arc_embedding_id=None,
            avg_emotional_intensity=0.0,
            avg_relational_significance=0.0,
            subjective_duration_weight=0.0,
            message_count=0,
            user_message_count=0,
            companion_message_count=0,
            avg_response_latency_sec=0.0,
            compass_activations={},
            topics=[],
            relational_field_delta={},
            gwen_initiated=(initiated_by == "companion"),
        )

        self.current_session = session
        self._last_message_time = None
        self._last_message_sender = None
        self._user_message_count = 0
        self._companion_message_count = 0
        self._response_latencies = []
        self._session_start_monotonic = time.monotonic()

        return session

    def add_message(self, sender: str) -> None:
        """Record that a message was sent in the current session.

        Args:
            sender: Either "user" or "companion".

        Raises:
            RuntimeError: If no session is active.
            ValueError: If sender is not "user" or "companion".
        """
        if self.current_session is None:
            raise RuntimeError(
                "Cannot add a message when no session is active. "
                "Call start_session() first."
            )

        if sender not in ("user", "companion"):
            raise ValueError(
                f"sender must be 'user' or 'companion', got '{sender}'"
            )

        now_monotonic = time.monotonic()

        # Track response latency when sender alternates
        if self._last_message_time is not None and self._last_message_sender != sender:
            latency = now_monotonic - self._last_message_time
            self._response_latencies.append(latency)

        if sender == "user":
            self._user_message_count += 1
        else:
            self._companion_message_count += 1

        self._last_message_time = now_monotonic
        self._last_message_sender = sender

    def end_session(self, end_mode: SessionEndMode) -> SessionRecord:
        """End the current session and finalize the SessionRecord.

        Args:
            end_mode: How the session ended.

        Returns:
            The finalized SessionRecord.

        Raises:
            RuntimeError: If no session is active.
        """
        if self.current_session is None:
            raise RuntimeError(
                "Cannot end session when no session is active. "
                "Call start_session() first."
            )

        now = datetime.now(timezone.utc)
        session = self.current_session

        duration_delta = now - session.start_time
        duration_sec = int(duration_delta.total_seconds())

        session_type = self._classify_session_type(duration_sec)

        if self._response_latencies:
            avg_latency = sum(self._response_latencies) / len(self._response_latencies)
        else:
            avg_latency = 0.0

        # Subjective duration weight
        intensity_factor = 0.5 + (session.avg_emotional_intensity * 1.5)
        significance_factor = 0.5 + (session.avg_relational_significance * 1.5)
        subjective_weight = duration_sec * intensity_factor * significance_factor

        # Finalize
        session.end_time = now
        session.duration_sec = duration_sec
        session.session_type = session_type
        session.end_mode = end_mode
        session.message_count = self._user_message_count + self._companion_message_count
        session.user_message_count = self._user_message_count
        session.companion_message_count = self._companion_message_count
        session.avg_response_latency_sec = round(avg_latency, 3)
        session.subjective_duration_weight = round(subjective_weight, 2)

        # Save to Chronicle
        self.chronicle.insert_session(session)

        # Clear state
        finalized = session
        self.current_session = None
        self._last_message_time = None
        self._last_message_sender = None
        self._user_message_count = 0
        self._companion_message_count = 0
        self._response_latencies = []
        self._session_start_monotonic = None
        self.current_gap_analysis = None
        self.current_return_context = None

        return finalized

    def _classify_session_type(self, duration_sec: int) -> SessionType:
        """Classify the session based on duration in seconds.

        Thresholds (SRS.md Section 3.4):
        - PING:      < 300s   (< 5 min)
        - CHAT:      300-1799 (5-29:59 min)
        - HANG:      1800-5399 (30-89:59 min)
        - DEEP_DIVE: 5400-10799 (90-179:59 min)
        - MARATHON:  >= 10800 (180+ min)
        """
        if duration_sec < 300:
            return SessionType.PING
        elif duration_sec < 1800:
            return SessionType.CHAT
        elif duration_sec < 5400:
            return SessionType.HANG
        elif duration_sec < 10800:
            return SessionType.DEEP_DIVE
        else:
            return SessionType.MARATHON

    def detect_timeout(
        self,
        idle_threshold_sec: float = 1800.0,
    ) -> Optional[SessionEndMode]:
        """Check if the current session has timed out due to inactivity.

        Args:
            idle_threshold_sec: Seconds of inactivity before timeout. Default: 1800.

        Returns:
            A SessionEndMode if timeout detected, or None if still active.
        """
        if self.current_session is None:
            return None

        if self._last_message_time is None:
            if self._session_start_monotonic is None:
                return None
            idle_sec = time.monotonic() - self._session_start_monotonic
        else:
            idle_sec = time.monotonic() - self._last_message_time

        if idle_sec < idle_threshold_sec:
            return None

        if self._last_message_sender == "user":
            return SessionEndMode.ABRUPT
        else:
            return SessionEndMode.FADE_OUT

    def get_session_duration_sec(self) -> int:
        """Get the current session's duration so far, in seconds."""
        if self._session_start_monotonic is None:
            return 0
        return int(time.monotonic() - self._session_start_monotonic)

    def update_emotional_state(
        self,
        emotional_state: EmotionalStateVector,
        is_opening: bool = False,
    ) -> None:
        """Update the session's emotional tracking with a new state.

        Args:
            emotional_state: The EmotionalStateVector from the latest message.
            is_opening: True if this is the first message in the session.
        """
        if self.current_session is None:
            return

        session = self.current_session

        if is_opening:
            session.opening_emotional_state = emotional_state

        if emotional_state.arousal > session.peak_emotional_state.arousal:
            session.peak_emotional_state = emotional_state

        session.closing_emotional_state = emotional_state

        total_msgs = self._user_message_count + self._companion_message_count
        if total_msgs > 0:
            n = total_msgs
            session.avg_emotional_intensity += (
                emotional_state.arousal - session.avg_emotional_intensity
            ) / n
            session.avg_relational_significance += (
                emotional_state.relational_significance
                - session.avg_relational_significance
            ) / n
