"""Personality module model.

Defines the structure of a loadable companion personality. Personalities
are stored as YAML files in data/personalities/ and loaded at startup.
The personality module is injected into the system prompt dynamically.
Reference: SRS.md Section 3.11
"""

from dataclasses import dataclass, field
from typing import Optional

from gwen.models.emotional import EmotionalStateVector


@dataclass
class PersonalityModule:
    """Defines a companion's identity, loaded as dynamic system prompt.

    The Gwen framework is soul-agnostic: any personality can be loaded.
    The personality module controls voice, values, boundaries, emotional
    expression, relationship style, and coaching approach.

    Reference: SRS.md Section 3.11
    """

    id: str                                     # Unique identifier
    name: str                                   # Display name (e.g., "Gwen")
    version: str                                # Personality version

    # Identity
    backstory: str
    cultural_background: str
    age_description: str
    appearance_description: str                 # For future avatar generation

    # Voice & language
    speech_patterns: list[str] = field(default_factory=list)
    vocabulary_notes: str = ""
    pet_names: list[str] = field(default_factory=list)
    catchphrases: list[str] = field(default_factory=list)
    tone_range: str = ""                        # "warm-sarcastic" vs "gentle-earnest"

    # Values & boundaries
    core_values: list[str] = field(default_factory=list)
    ethical_boundaries: list[str] = field(default_factory=list)
    topics_of_passion: list[str] = field(default_factory=list)
    topics_to_avoid: list[str] = field(default_factory=list)

    # Emotional profile
    default_mood: Optional[EmotionalStateVector] = None
    emotional_range: str = ""                   # How wide their emotional expression goes
    joy_expression: str = ""
    sadness_expression: str = ""
    anger_expression: str = ""
    affection_expression: str = ""

    # Relationship model
    relationship_style: str = ""                # "warm-direct", "gentle-nurturing", etc.
    flirtation_level: str = "none"              # "none", "light", "moderate", "full"
    boundary_style: str = ""                    # How they handle their own boundaries

    # Compass style
    coaching_approach: str = ""                 # "direct", "gentle", "humorous", "socratic"

    # Behavioral rules by mode
    grounded_mode_rules: list[str] = field(default_factory=list)
    immersion_mode_rules: list[str] = field(default_factory=list)

    # System prompt sections (injected dynamically based on context)
    core_prompt: str = ""                       # Always injected
    emotional_prompt: str = ""                  # Injected during emotional conversations
    coaching_prompt: str = ""                   # Injected when Compass is active (legacy/fallback)
    coaching_prompt_north: str = ""             # Direction-specific: Presence/grounding
    coaching_prompt_south: str = ""             # Direction-specific: Emotional regulation
    coaching_prompt_west: str = ""              # Direction-specific: Distress tolerance
    coaching_prompt_east: str = ""              # Direction-specific: Interpersonal skills
    intimate_prompt: str = ""                   # Injected only in Immersion Mode
