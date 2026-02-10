"""Dynamic system prompt builder.

Assembles the system prompt from personality module sections based on
the current conversation context (mode, compass activation, emotional state).
"""

from gwen.models.personality import PersonalityModule
from gwen.models.emotional import CompassDirection


class PromptBuilder:
    """Builds system prompts from personality module sections.

    The prompt is assembled dynamically based on the current context:
    - core_prompt is ALWAYS included
    - Mode-specific rules are always included
    - emotional_prompt is included during emotional conversations
    - coaching_prompt is included when the Compass framework is active

    Usage:
        builder = PromptBuilder()
        prompt = builder.build_system_prompt(
            personality=gwen_personality,
            mode="grounded",
            compass_direction=CompassDirection.SOUTH,
            include_emotional=True,
        )
    """

    def build_system_prompt(
        self,
        personality: PersonalityModule,
        mode: str = "grounded",
        compass_direction: CompassDirection = CompassDirection.NONE,
        include_emotional: bool = False,
        return_context_block: str = "",
    ) -> str:
        """Build the complete system prompt for a Tier 1 model call.

        Sections are assembled in order:
        1. Core prompt (always)
        2. Mode-specific rules (always)
        3. Emotional prompt (if include_emotional is True)
        4. Coaching prompt (if compass_direction is not NONE)
        5. Return context block (if provided, for gap-based context)

        Args:
            personality: The loaded PersonalityModule instance.
            mode: Either "grounded" or "immersion". Default: "grounded".
            compass_direction: The detected Compass direction for this message.
            include_emotional: Whether to include the emotional_prompt section.
            return_context_block: Natural-language block from ReturnContext system.

        Returns:
            The complete system prompt as a single string.
        """
        sections: list[str] = []

        # --- Section 1: Core prompt (always included) ---
        core = personality.core_prompt.strip()
        if core:
            sections.append(core)

        # --- Section 2: Mode-specific rules ---
        if mode == "immersion" and personality.immersion_mode_rules:
            rules = personality.immersion_mode_rules
            header = "[MODE: Immersion]"
        else:
            rules = personality.grounded_mode_rules
            header = "[MODE: Grounded]"

        if rules:
            rules_text = "\n".join(f"- {rule}" for rule in rules)
            sections.append(f"{header}\n{rules_text}")

        # --- Section 3: Emotional prompt (context-dependent) ---
        if include_emotional:
            emotional = personality.emotional_prompt.strip()
            if emotional:
                sections.append(f"[EMOTIONAL CONTEXT]\n{emotional}")

        # --- Section 4: Coaching prompt (context-dependent, direction-specific) ---
        if compass_direction != CompassDirection.NONE:
            direction_label = compass_direction.value.upper()
            # Use direction-specific prompt if available, fall back to generic
            direction_prompts = {
                "NORTH": personality.coaching_prompt_north,
                "SOUTH": personality.coaching_prompt_south,
                "WEST": personality.coaching_prompt_west,
                "EAST": personality.coaching_prompt_east,
            }
            coaching = direction_prompts.get(direction_label, "").strip()
            if not coaching:
                coaching = personality.coaching_prompt.strip()
            if coaching:
                sections.append(
                    f"[COMPASS: {direction_label}]\n{coaching}"
                )

        # --- Section 5: Return context (gap-based) ---
        if return_context_block.strip():
            sections.append(
                f"[RETURN CONTEXT]\n{return_context_block.strip()}"
            )

        return "\n\n".join(sections)
