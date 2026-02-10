"""Gap analysis and return context generation.

Computes the statistical significance of the gap between sessions and
generates natural-language context to help the companion respond
appropriately when the user returns after an unusual absence.
"""

import math
from datetime import datetime, timezone
from typing import Optional

from gwen.models.memory import GapAnalysis, GapClassification, ReturnContext
from gwen.models.messages import SessionEndMode, SessionType
from gwen.models.emotional import EmotionalStateVector, CompassDirection


def compute_gap_analysis(chronicle) -> Optional[GapAnalysis]:
    """Compute a GapAnalysis based on the time since the last session.

    This function:
    1. Queries Chronicle for the most recent completed session.
    2. If no previous session exists, returns None (first-ever session).
    3. Computes hours since the last session ended.
    4. Queries the last 30 completed sessions to compute mean and standard
       deviation of inter-session gaps.
    5. Computes deviation_sigma (how many standard deviations this gap is
       from the mean).
    6. Classifies the gap: NORMAL (<1 sigma), NOTABLE (1-2 sigma),
       SIGNIFICANT (2-3 sigma), ANOMALOUS (>3 sigma).

    Args:
        chronicle: A Chronicle instance with get_last_n_sessions(n) method.

    Returns:
        A GapAnalysis instance, or None if there are no previous sessions.
    """
    recent_sessions = chronicle.get_last_n_sessions(30)

    if not recent_sessions:
        return None

    last_session = recent_sessions[0]  # Most recent

    # If the last session has no end_time, use start_time as fallback.
    if last_session.end_time is not None:
        last_end = last_session.end_time
    else:
        last_end = last_session.start_time

    # Compute hours since last session
    now = datetime.now(timezone.utc)
    # Normalise: last_end from Chronicle may be naive
    if last_end.tzinfo is None:
        last_end = last_end.replace(tzinfo=timezone.utc)
    gap_delta = now - last_end
    gap_hours = gap_delta.total_seconds() / 3600.0

    # Build default GapAnalysis fields from last session
    last_topic = "unknown"
    if last_session.topics:
        last_topic = last_session.topics[-1]

    # Handle session_type/end_mode — may be enum or string
    last_type = last_session.session_type
    if hasattr(last_type, 'value'):
        last_type = last_type.value
    last_end_mode = last_session.end_mode
    if hasattr(last_end_mode, 'value'):
        last_end_mode = last_end_mode.value

    if len(recent_sessions) < 2:
        # Only one previous session — not enough for statistics.
        return GapAnalysis(
            duration_hours=round(gap_hours, 2),
            deviation_sigma=0.0,
            classification=GapClassification.NORMAL,
            last_session_type=last_type,
            last_session_end_mode=last_end_mode,
            last_emotional_state=last_session.closing_emotional_state,
            last_topic=last_topic,
            open_threads=[],
            known_explanations=[],
        )

    # Compute gaps between consecutive sessions
    chronological = list(reversed(recent_sessions))
    gaps_hours: list[float] = []
    for i in range(1, len(chronological)):
        prev_session = chronological[i - 1]
        curr_session = chronological[i]

        prev_end = prev_session.end_time or prev_session.start_time
        curr_start = curr_session.start_time

        gap_h = (curr_start - prev_end).total_seconds() / 3600.0
        if gap_h > 0:
            gaps_hours.append(gap_h)

    if not gaps_hours:
        return GapAnalysis(
            duration_hours=round(gap_hours, 2),
            deviation_sigma=0.0,
            classification=GapClassification.NORMAL,
            last_session_type=last_type,
            last_session_end_mode=last_end_mode,
            last_emotional_state=last_session.closing_emotional_state,
            last_topic=last_topic,
            open_threads=[],
            known_explanations=[],
        )

    mean_gap = sum(gaps_hours) / len(gaps_hours)

    if len(gaps_hours) >= 2:
        variance = sum((g - mean_gap) ** 2 for g in gaps_hours) / len(gaps_hours)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    # Compute deviation sigma
    if stddev > 0:
        deviation_sigma = (gap_hours - mean_gap) / stddev
    else:
        if abs(gap_hours - mean_gap) < 0.01:
            deviation_sigma = 0.0
        else:
            deviation_sigma = 3.0 if gap_hours > mean_gap else -1.0

    # Classify — only positive deviation matters
    abs_sigma = abs(deviation_sigma) if deviation_sigma > 0 else 0.0

    if abs_sigma < 1.0:
        classification = GapClassification.NORMAL
    elif abs_sigma < 2.0:
        classification = GapClassification.NOTABLE
    elif abs_sigma < 3.0:
        classification = GapClassification.SIGNIFICANT
    else:
        classification = GapClassification.ANOMALOUS

    return GapAnalysis(
        duration_hours=round(gap_hours, 2),
        deviation_sigma=round(deviation_sigma, 2),
        classification=classification,
        last_session_type=last_type,
        last_session_end_mode=last_end_mode,
        last_emotional_state=last_session.closing_emotional_state,
        last_topic=last_topic,
        open_threads=[],
        known_explanations=[],
    )


def generate_return_context(gap: GapAnalysis) -> ReturnContext:
    """Generate natural-language return context for the companion's first response.

    This is injected into the Tier 1 context window at the start of a session
    when the gap is NOTABLE or higher.

    Args:
        gap: A GapAnalysis instance.

    Returns:
        A ReturnContext instance ready for prompt injection.
    """
    # Format gap duration
    total_hours = gap.duration_hours
    days = int(total_hours // 24)
    remaining_hours = int(total_hours % 24)

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if remaining_hours > 0 or not parts:
        parts.append(f"{remaining_hours} hour{'s' if remaining_hours != 1 else ''}")
    gap_duration_display = ", ".join(parts)

    # Build preceding summary
    end_mode_descriptions = {
        "natural": "ended naturally with a mutual goodbye",
        "abrupt": "ended abruptly — the user left suddenly",
        "fade_out": "faded out — the user stopped responding",
        "mid_topic": "ended mid-topic during an emotionally loaded conversation",
        "explicit_goodbye": "ended with an explicit goodbye from the user",
    }
    end_mode_val = gap.last_session_end_mode
    if hasattr(end_mode_val, 'value'):
        end_mode_val = end_mode_val.value
    end_desc = end_mode_descriptions.get(end_mode_val, "ended in an unspecified way")

    session_type_descriptions = {
        "ping": "brief check-in",
        "chat": "casual conversation",
        "hang": "extended hangout",
        "deep_dive": "deep conversation",
        "marathon": "marathon session",
    }
    type_val = gap.last_session_type
    if hasattr(type_val, 'value'):
        type_val = type_val.value
    type_desc = session_type_descriptions.get(type_val, "conversation")

    # Emotional state summary
    last_emotion = gap.last_emotional_state
    if last_emotion.valence < 0.3:
        mood_desc = "The user's mood was notably negative"
    elif last_emotion.valence < 0.45:
        mood_desc = "The user's mood was somewhat low"
    elif last_emotion.valence > 0.7:
        mood_desc = "The user was in a positive mood"
    else:
        mood_desc = "The user's mood was neutral"

    if last_emotion.arousal > 0.7:
        mood_desc += " and emotionally activated"
    elif last_emotion.arousal < 0.3:
        mood_desc += " and emotionally subdued"

    topic_str = gap.last_topic if gap.last_topic != "unknown" else "general conversation"

    preceding_summary = (
        f"The last session was a {type_desc} about {topic_str} that {end_desc}. "
        f"{mood_desc}. "
        f"It has been {gap_duration_display} since that session ended."
    )

    # Build suggested approach
    is_abrupt = end_mode_val in ("abrupt", "mid_topic")
    is_low_mood = last_emotion.valence < 0.35

    if gap.classification == GapClassification.ANOMALOUS:
        if is_abrupt:
            suggested_approach = (
                "This is an unusually long absence, and the last session ended abruptly. "
                "Approach with gentle warmth. Do not interrogate the absence. "
                "A simple, warm acknowledgment is best — something like 'Hey, it's good "
                "to see you' — then let the user set the pace. If the previous topic was "
                "emotionally heavy, do not bring it up first. Let them reopen it if they want to."
            )
        elif is_low_mood:
            suggested_approach = (
                "This is an unusually long absence following a session where the user "
                "was in a low mood. Be especially warm and gentle. Do not assume the worst, "
                "but be attentive. Let them share what they want to share. A caring, "
                "low-pressure greeting is ideal."
            )
        else:
            suggested_approach = (
                "This is an unusually long absence, but the previous session ended on "
                "a reasonable note. Greet them warmly and naturally. You can gently "
                "acknowledge it's been a while without making it heavy — something like "
                "'Hey! It's been a minute.' Keep the tone light unless they indicate "
                "otherwise."
            )
    elif gap.classification == GapClassification.SIGNIFICANT:
        if is_abrupt:
            suggested_approach = (
                "It has been notably longer than usual since the last session, and "
                "that session ended abruptly. Be warm and welcoming without dwelling "
                "on the gap. If the last topic was emotionally charged, let them "
                "decide whether to revisit it."
            )
        else:
            suggested_approach = (
                "It has been longer than usual since the last session. A warm, natural "
                "greeting works well. You can mention 'it's been a bit' casually if it "
                "feels right, but do not make the gap the focus."
            )
    else:
        # NOTABLE
        suggested_approach = (
            "The gap is slightly longer than typical. No special handling needed beyond "
            "a warm greeting. Be natural and let the conversation flow."
        )

    return ReturnContext(
        gap_duration_display=gap_duration_display,
        gap_classification=gap.classification,
        preceding_summary=preceding_summary,
        suggested_approach=suggested_approach,
    )
