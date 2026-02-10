"""Personality module loader.

Loads companion personality definitions from YAML files, validates
required fields, and produces PersonalityModule dataclass instances.
"""

from pathlib import Path
from typing import Any

import yaml

from gwen.models.personality import PersonalityModule
from gwen.models.emotional import EmotionalStateVector, CompassDirection


# These fields MUST exist in the YAML file. If any are missing,
# loading fails with a clear error message.
REQUIRED_FIELDS: list[str] = [
    "id",
    "name",
    "version",
    "backstory",
    "speech_patterns",
    "core_values",
    "core_prompt",
    "grounded_mode_rules",
]


class PersonalityLoader:
    """Loads and validates personality module YAML files.

    Usage:
        loader = PersonalityLoader()
        personality = loader.load_from_file("data/personalities/gwen.yaml")
    """

    def load_from_file(self, path: str) -> PersonalityModule:
        """Load a personality module from a YAML file.

        Args:
            path: The file path to the YAML personality file.

        Returns:
            A fully populated PersonalityModule instance.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            ValueError: If required fields are missing.
            yaml.YAMLError: If the file contains invalid YAML syntax.
        """
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"Personality file not found: {file_path.resolve()}\n"
                f"Expected a YAML file at this location. Check that the path "
                f"is correct and the file exists."
            )

        with open(file_path, "r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(
                f"Personality file {path} did not parse to a dictionary. "
                f"Got {type(raw).__name__}. Check the YAML structure."
            )

        self._validate_required_fields(raw, path)
        default_mood = self._parse_default_mood(raw.get("default_mood"))

        personality = PersonalityModule(
            id=raw["id"],
            name=raw["name"],
            version=raw["version"],
            backstory=raw["backstory"],
            cultural_background=raw.get("cultural_background", ""),
            age_description=raw.get("age_description", ""),
            appearance_description=raw.get("appearance_description", ""),
            speech_patterns=raw["speech_patterns"],
            vocabulary_notes=raw.get("vocabulary_notes", ""),
            pet_names=raw.get("pet_names", []),
            catchphrases=raw.get("catchphrases", []),
            tone_range=raw.get("tone_range", ""),
            core_values=raw["core_values"],
            ethical_boundaries=raw.get("ethical_boundaries", []),
            topics_of_passion=raw.get("topics_of_passion", []),
            topics_to_avoid=raw.get("topics_to_avoid", []),
            default_mood=default_mood,
            emotional_range=raw.get("emotional_range", ""),
            joy_expression=raw.get("joy_expression", ""),
            sadness_expression=raw.get("sadness_expression", ""),
            anger_expression=raw.get("anger_expression", ""),
            affection_expression=raw.get("affection_expression", ""),
            relationship_style=raw.get("relationship_style", ""),
            flirtation_level=raw.get("flirtation_level", "none"),
            boundary_style=raw.get("boundary_style", ""),
            coaching_approach=raw.get("coaching_approach", ""),
            grounded_mode_rules=raw["grounded_mode_rules"],
            immersion_mode_rules=raw.get("immersion_mode_rules", []),
            core_prompt=raw["core_prompt"],
            emotional_prompt=raw.get("emotional_prompt", ""),
            coaching_prompt=raw.get("coaching_prompt", ""),
            coaching_prompt_north=raw.get("coaching_prompt_north", ""),
            coaching_prompt_south=raw.get("coaching_prompt_south", ""),
            coaching_prompt_west=raw.get("coaching_prompt_west", ""),
            coaching_prompt_east=raw.get("coaching_prompt_east", ""),
            intimate_prompt=raw.get("intimate_prompt", ""),
        )

        return personality

    def _validate_required_fields(
        self, raw: dict[str, Any], file_path: str
    ) -> None:
        """Check that all required fields are present in the YAML data.

        Raises:
            ValueError: If any required fields are missing. Lists ALL
                missing fields, not just the first one found.
        """
        missing: list[str] = []
        for field_name in REQUIRED_FIELDS:
            if field_name not in raw:
                missing.append(field_name)
            elif raw[field_name] is None:
                missing.append(f"{field_name} (present but null)")
            elif isinstance(raw[field_name], str) and raw[field_name].strip() == "":
                missing.append(f"{field_name} (present but empty)")

        if missing:
            raise ValueError(
                f"Personality file '{file_path}' is missing required fields:\n"
                f"  {', '.join(missing)}\n"
                f"\n"
                f"Required fields are: {', '.join(REQUIRED_FIELDS)}\n"
                f"Add these fields to the YAML file and try again."
            )

    def _parse_default_mood(
        self, mood_data: dict[str, float] | None
    ) -> EmotionalStateVector:
        """Convert the default_mood YAML mapping to an EmotionalStateVector.

        If no mood data is provided, returns a neutral default.
        """
        if mood_data is None:
            return EmotionalStateVector(
                valence=0.5,
                arousal=0.3,
                dominance=0.5,
                relational_significance=0.0,
                vulnerability_level=0.0,
                compass_direction=CompassDirection.NONE,
                compass_confidence=0.0,
            )

        return EmotionalStateVector(
            valence=float(mood_data.get("valence", 0.5)),
            arousal=float(mood_data.get("arousal", 0.3)),
            dominance=float(mood_data.get("dominance", 0.5)),
            relational_significance=float(
                mood_data.get("relational_significance", 0.0)
            ),
            vulnerability_level=float(
                mood_data.get("vulnerability_level", 0.0)
            ),
            compass_direction=CompassDirection.NONE,
            compass_confidence=0.0,
        )
