"""Tests for the Compass Framework — skill registry, selection, and tracking.

Run with:
    pytest tests/test_compass.py -v
"""

from pathlib import Path

from gwen.compass.skills import (
    CompassSkill,
    SKILL_REGISTRY,
    get_skills_for_direction,
)
from gwen.compass.classifier import (
    SkillSelector,
    generate_compass_prompt,
    should_add_disclaimer,
)
from gwen.compass.tracker import EffectivenessTracker
from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.memory import CompassEffectivenessRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_esv(
    valence: float = 0.5,
    arousal: float = 0.5,
) -> EmotionalStateVector:
    """Create an EmotionalStateVector with sensible defaults."""
    return EmotionalStateVector(
        valence=valence,
        arousal=arousal,
        dominance=0.5,
        relational_significance=0.5,
        vulnerability_level=0.5,
        compass_direction=CompassDirection.NONE,
        compass_confidence=0.0,
    )


def _make_effectiveness_record(
    skill_name: str = "check_in",
    direction: CompassDirection = CompassDirection.NORTH,
    effectiveness_score: float = 0.7,
) -> CompassEffectivenessRecord:
    """Create a CompassEffectivenessRecord with sensible defaults."""
    return CompassEffectivenessRecord(
        skill_name=skill_name,
        direction=direction,
        context_emotional_state=_make_esv(),
        pre_trajectory=_make_esv(valence=0.3),
        post_trajectory=_make_esv(valence=0.6),
        time_to_effect_sec=300,
        user_accepted=True,
        effectiveness_score=effectiveness_score,
    )


# ---------------------------------------------------------------------------
# Tests: Skill Registry
# ---------------------------------------------------------------------------

class TestSkillRegistry:
    """Tests for the SKILL_REGISTRY and get_skills_for_direction."""

    def test_registry_has_20_skills(self) -> None:
        """The registry should contain exactly 20 skills."""
        assert len(SKILL_REGISTRY) == 20

    def test_5_skills_per_direction(self) -> None:
        """Each direction (except NONE) should have exactly 5 skills."""
        for direction in [
            CompassDirection.NORTH,
            CompassDirection.SOUTH,
            CompassDirection.WEST,
            CompassDirection.EAST,
        ]:
            skills = get_skills_for_direction(direction)
            assert len(skills) == 5, (
                f"Direction {direction.value} has {len(skills)} skills, expected 5"
            )

    def test_none_direction_returns_empty(self) -> None:
        """CompassDirection.NONE should return no skills."""
        skills = get_skills_for_direction(CompassDirection.NONE)
        assert len(skills) == 0

    def test_all_skill_names_unique(self) -> None:
        """Every skill name in the registry should be unique."""
        names = [s.name for s in SKILL_REGISTRY]
        assert len(names) == len(set(names)), (
            f"Duplicate skill names found: {[n for n in names if names.count(n) > 1]}"
        )

    def test_all_skills_have_prompt_text(self) -> None:
        """Every skill should have a non-empty prompt_text."""
        for skill in SKILL_REGISTRY:
            assert len(skill.prompt_text) > 50, (
                f"Skill '{skill.name}' has too short prompt_text "
                f"({len(skill.prompt_text)} chars)"
            )

    def test_all_skills_have_trigger_phrases(self) -> None:
        """Every skill should have at least one trigger phrase."""
        for skill in SKILL_REGISTRY:
            assert len(skill.trigger_phrases) >= 1, (
                f"Skill '{skill.name}' has no trigger phrases"
            )

    def test_north_skills_correct(self) -> None:
        """NORTH skills should include check_in, anchor_breath, body_scan,
        reality_check, permission_slip."""
        north = get_skills_for_direction(CompassDirection.NORTH)
        names = {s.name for s in north}
        expected = {"check_in", "anchor_breath", "body_scan",
                    "reality_check", "permission_slip"}
        assert names == expected

    def test_south_skills_correct(self) -> None:
        """SOUTH skills should include fuel_check, emotion_map, containment,
        pattern_mirror, reframe."""
        south = get_skills_for_direction(CompassDirection.SOUTH)
        names = {s.name for s in south}
        expected = {"fuel_check", "emotion_map", "containment",
                    "pattern_mirror", "reframe"}
        assert names == expected

    def test_west_skills_correct(self) -> None:
        """WEST skills should include pause_protocol, safe_landing,
        damage_assessment, survival_kit, steady_state."""
        west = get_skills_for_direction(CompassDirection.WEST)
        names = {s.name for s in west}
        expected = {"pause_protocol", "safe_landing", "damage_assessment",
                    "survival_kit", "steady_state"}
        assert names == expected

    def test_east_skills_correct(self) -> None:
        """EAST skills should include connection_nudge, script_builder,
        boundary_coach, repair_guide, perspective_swap."""
        east = get_skills_for_direction(CompassDirection.EAST)
        names = {s.name for s in east}
        expected = {"connection_nudge", "script_builder", "boundary_coach",
                    "repair_guide", "perspective_swap"}
        assert names == expected


# ---------------------------------------------------------------------------
# Tests: Skill Selector
# ---------------------------------------------------------------------------

class TestSkillSelector:
    """Tests for SkillSelector.select_skill."""

    def test_none_direction_returns_none(self) -> None:
        """NONE direction should return None (no skill needed)."""
        selector = SkillSelector()
        result = selector.select_skill(
            direction=CompassDirection.NONE,
            emotional_state=_make_esv(),
        )
        assert result is None

    def test_returns_skill_for_valid_direction(self) -> None:
        """A valid direction should return a CompassSkill."""
        selector = SkillSelector()
        result = selector.select_skill(
            direction=CompassDirection.NORTH,
            emotional_state=_make_esv(),
        )
        assert result is not None
        assert isinstance(result, CompassSkill)
        assert result.direction == CompassDirection.NORTH

    def test_trigger_phrase_boosts_score(self) -> None:
        """A message containing a trigger phrase should boost the matching skill."""
        selector = SkillSelector()
        # "I don't know how I feel" is a trigger for check_in
        result = selector.select_skill(
            direction=CompassDirection.NORTH,
            emotional_state=_make_esv(),
            message="I don't know how I feel right now",
        )
        assert result is not None
        assert result.name == "check_in"

    def test_effectiveness_history_boosts_score(self) -> None:
        """A skill with high effectiveness should be preferred."""
        selector = SkillSelector(
            effectiveness_history={
                "fuel_check": 0.9,   # High effectiveness
                "emotion_map": 0.1,  # Low effectiveness
            }
        )
        result = selector.select_skill(
            direction=CompassDirection.SOUTH,
            emotional_state=_make_esv(),
        )
        assert result is not None
        assert result.name == "fuel_check"

    def test_variety_penalty_applied(self) -> None:
        """Recently used skills should be penalised."""
        selector = SkillSelector(
            recent_skills=["check_in", "anchor_breath", "body_scan",
                           "reality_check"],
        )
        # All NORTH skills except permission_slip are in recent_skills
        result = selector.select_skill(
            direction=CompassDirection.NORTH,
            emotional_state=_make_esv(),
        )
        assert result is not None
        assert result.name == "permission_slip"

    def test_recent_skills_updated_after_selection(self) -> None:
        """After selection, the selected skill should be added to recent_skills."""
        selector = SkillSelector()
        selector.select_skill(
            direction=CompassDirection.WEST,
            emotional_state=_make_esv(),
        )
        assert len(selector.recent_skills) >= 1

    def test_recent_skills_capped_at_10(self) -> None:
        """recent_skills should never exceed 10 entries."""
        selector = SkillSelector(
            recent_skills=[f"skill_{i}" for i in range(10)],
        )
        selector.select_skill(
            direction=CompassDirection.EAST,
            emotional_state=_make_esv(),
        )
        assert len(selector.recent_skills) <= 10


# ---------------------------------------------------------------------------
# Tests: Effectiveness Tracker
# ---------------------------------------------------------------------------

class TestEffectivenessTracker:
    """Tests for EffectivenessTracker."""

    def test_log_and_compute(self, tmp_path: Path) -> None:
        """Logging a record and computing effectiveness should return the score."""
        tracker = EffectivenessTracker(
            data_path=tmp_path / "eff.json"
        )
        record = _make_effectiveness_record(effectiveness_score=0.8)
        tracker.log_usage(record)

        score = tracker.compute_effectiveness(
            "check_in", CompassDirection.NORTH
        )
        assert abs(score - 0.8) < 1e-9

    def test_average_across_multiple_records(self, tmp_path: Path) -> None:
        """Effectiveness should be the average across multiple records."""
        tracker = EffectivenessTracker(
            data_path=tmp_path / "eff.json"
        )
        tracker.log_usage(_make_effectiveness_record(effectiveness_score=0.6))
        tracker.log_usage(_make_effectiveness_record(effectiveness_score=0.8))
        tracker.log_usage(_make_effectiveness_record(effectiveness_score=1.0))

        score = tracker.compute_effectiveness(
            "check_in", CompassDirection.NORTH
        )
        assert abs(score - 0.8) < 1e-9  # (0.6 + 0.8 + 1.0) / 3 = 0.8

    def test_no_records_returns_zero(self, tmp_path: Path) -> None:
        """No records for a skill should return 0.0."""
        tracker = EffectivenessTracker(
            data_path=tmp_path / "eff.json"
        )
        score = tracker.compute_effectiveness(
            "nonexistent_skill", CompassDirection.NORTH
        )
        assert score == 0.0

    def test_persistence_to_disk(self, tmp_path: Path) -> None:
        """Records should survive a save/reload cycle."""
        data_path = tmp_path / "eff.json"
        tracker1 = EffectivenessTracker(data_path=data_path)
        tracker1.log_usage(_make_effectiveness_record(effectiveness_score=0.7))

        # Create a new tracker from the same file
        tracker2 = EffectivenessTracker(data_path=data_path)
        score = tracker2.compute_effectiveness(
            "check_in", CompassDirection.NORTH
        )
        assert abs(score - 0.7) < 1e-9

    def test_get_skill_history(self, tmp_path: Path) -> None:
        """get_skill_history should return all records for a skill."""
        tracker = EffectivenessTracker(
            data_path=tmp_path / "eff.json"
        )
        tracker.log_usage(_make_effectiveness_record(
            skill_name="fuel_check", effectiveness_score=0.5,
            direction=CompassDirection.SOUTH,
        ))
        tracker.log_usage(_make_effectiveness_record(
            skill_name="fuel_check", effectiveness_score=0.9,
            direction=CompassDirection.SOUTH,
        ))
        tracker.log_usage(_make_effectiveness_record(
            skill_name="check_in", effectiveness_score=0.7,
        ))

        history = tracker.get_skill_history("fuel_check")
        assert len(history) == 2

    def test_get_effectiveness_map(self, tmp_path: Path) -> None:
        """get_effectiveness_map should return scores for all skills with records."""
        tracker = EffectivenessTracker(
            data_path=tmp_path / "eff.json"
        )
        tracker.log_usage(_make_effectiveness_record(
            skill_name="check_in", effectiveness_score=0.8,
        ))
        tracker.log_usage(_make_effectiveness_record(
            skill_name="fuel_check", effectiveness_score=0.6,
            direction=CompassDirection.SOUTH,
        ))

        eff_map = tracker.get_effectiveness_map()
        assert "check_in" in eff_map
        assert "fuel_check" in eff_map
        assert abs(eff_map["check_in"] - 0.8) < 1e-9
        assert abs(eff_map["fuel_check"] - 0.6) < 1e-9


# ---------------------------------------------------------------------------
# Tests: Prompt Integration
# ---------------------------------------------------------------------------

class TestPromptIntegration:
    """Tests for generate_compass_prompt and should_add_disclaimer."""

    def test_generate_prompt_includes_skill_name(self) -> None:
        """The generated prompt should reference the skill name."""
        skill = get_skills_for_direction(CompassDirection.NORTH)[0]
        prompt = generate_compass_prompt(skill)
        assert skill.name in prompt

    def test_generate_prompt_includes_direction(self) -> None:
        """The generated prompt should reference the direction."""
        skill = get_skills_for_direction(CompassDirection.SOUTH)[0]
        prompt = generate_compass_prompt(skill)
        assert "currents" in prompt

    def test_generate_prompt_includes_prompt_text(self) -> None:
        """The generated prompt should include the skill's prompt_text."""
        skill = get_skills_for_direction(CompassDirection.WEST)[0]
        prompt = generate_compass_prompt(skill)
        assert skill.prompt_text in prompt

    def test_generate_prompt_with_coaching_approach(self) -> None:
        """Different coaching approaches should produce different prefixes."""
        skill = get_skills_for_direction(CompassDirection.EAST)[0]
        direct_prompt = generate_compass_prompt(skill, coaching_approach="direct")
        gentle_prompt = generate_compass_prompt(skill, coaching_approach="gentle")
        assert "straightforward" in direct_prompt
        assert "soft" in gentle_prompt

    def test_disclaimer_high_over_reliance(self) -> None:
        """Over-reliance > 0.7 should always trigger disclaimer."""
        assert should_add_disclaimer(0.8) is True
        assert should_add_disclaimer(1.0) is True

    def test_disclaimer_low_over_reliance_probability(self) -> None:
        """Over-reliance < 0.3 should rarely trigger disclaimer.

        We run 1000 trials and check that the rate is roughly 10%.
        With N=1000 and p=0.10, the expected count is 100.
        We allow a wide margin (50-200) to avoid flaky tests.
        """
        count = sum(
            should_add_disclaimer(0.1)
            for _ in range(1000)
        )
        assert 20 < count < 250, (
            f"Expected ~100 disclaimers out of 1000, got {count}"
        )

    def test_disclaimer_medium_over_reliance_probability(self) -> None:
        """Over-reliance 0.3-0.7 should trigger disclaimer ~30% of the time.

        We run 1000 trials and check that the rate is roughly 30%.
        Allow a wide margin (150-450) to avoid flaky tests.
        """
        count = sum(
            should_add_disclaimer(0.5)
            for _ in range(1000)
        )
        assert 150 < count < 500, (
            f"Expected ~300 disclaimers out of 1000, got {count}"
        )
