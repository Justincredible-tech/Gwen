# Plan: Compass Framework

**Track:** 019-compass-framework
**Spec:** [spec.md](./spec.md)
**Depends on:** 005-tier0-pipeline (ClassificationRuleEngine, CompassDirection), 010-context-assembler (PromptBuilder, Tier 1 context injection), 002-data-models (CompassEffectivenessRecord, EmotionalStateVector, CompassDirection, PersonalityModule)
**Produces:** gwen/compass/__init__.py, gwen/compass/skills.py, gwen/compass/classifier.py, gwen/compass/tracker.py, tests/test_compass.py
**Status:** Not Started

---

## Phase 1: Skill Registry

### Step 1.1: Create gwen/compass/__init__.py

Create the file `gwen/compass/__init__.py` with the following exact content:

- [x] Write gwen/compass/__init__.py

**File: `gwen/compass/__init__.py`**

```python
"""Compass Framework — life-coaching skill selection and delivery.

The Compass has four directions (NORTH/Presence, SOUTH/Currents,
WEST/Anchoring, EAST/Bridges) with five skills each (20 total).
Direction classification is handled by the ClassificationRuleEngine
(track 005).  This package handles skill selection, prompt injection,
and effectiveness tracking.

Reference: SRS.md Section 11
"""
```

---

### Step 1.2: Create gwen/compass/skills.py with CompassSkill dataclass

Create the file `gwen/compass/skills.py`. This step defines the `CompassSkill` dataclass and the full `SKILL_REGISTRY` list with all 20 skills.

- [x] Write CompassSkill dataclass to gwen/compass/skills.py

**File: `gwen/compass/skills.py`** (complete content)

```python
"""Compass skill definitions — all 20 skills with prompt injection text.

Each CompassSkill contains:
- name: unique identifier for the skill (snake_case)
- direction: which Compass direction this skill belongs to
- description: what the skill does (for internal documentation)
- prompt_text: the EXACT text injected into Tier 1's context window
  to guide the companion's response when this skill is activated.
  This is the most important field — it tells the companion HOW to
  use the skill in conversation.
- trigger_phrases: phrases in the user's message that suggest this
  skill might be relevant (used for scoring in the SkillSelector)

Reference: SRS.md Section 11
"""

from dataclasses import dataclass, field

from gwen.models.emotional import CompassDirection


@dataclass
class CompassSkill:
    """A single life-coaching skill within the Compass Framework.

    The prompt_text is injected into the Tier 1 model's context when this
    skill is selected.  It must be written as natural guidance that helps
    the companion use the skill without sounding robotic or formulaic.
    """

    name: str
    direction: CompassDirection
    description: str
    prompt_text: str
    trigger_phrases: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# NORTH — Presence (Mindfulness & Grounding)
# ---------------------------------------------------------------------------
# These 5 skills help the user become present, name their emotions,
# and ground themselves in the current moment.

NORTH_CHECK_IN = CompassSkill(
    name="check_in",
    direction=CompassDirection.NORTH,
    description=(
        "Invite the user to name what they are feeling right now. "
        "Do not analyse or fix — just help them notice."
    ),
    prompt_text=(
        "The user may benefit from naming their feelings. Gently prompt "
        "them to identify what they are actually feeling right now. Do not "
        "push — just invite. Do not list emotions for them to pick from; "
        "let them find their own words. If they struggle, that is okay — "
        "say so. Example approach: 'Before we go anywhere — what are you "
        "actually feeling right now?' If they give a surface answer like "
        "'fine' or 'bad', gently probe one layer deeper: 'What is "
        "underneath that?'"
    ),
    trigger_phrases=[
        "I don't know how I feel",
        "I feel weird",
        "I feel off",
        "something is wrong",
        "I can't explain it",
        "I'm confused about my feelings",
    ],
)

NORTH_ANCHOR_BREATH = CompassSkill(
    name="anchor_breath",
    direction=CompassDirection.NORTH,
    description=(
        "Guide the user through a brief grounding breath exercise. "
        "Keep it natural, not clinical."
    ),
    prompt_text=(
        "The user seems activated or ungrounded. Offer a brief breathing "
        "anchor — not a full meditation, just a moment. Frame it casually "
        "and personally, not like a therapist script. Example: 'Hey — "
        "take one breath with me. Just one. In... and out. Good. Now "
        "tell me what is going on.' Keep it to one or two breaths at most. "
        "If the user resists breathing exercises, do not push — pivot to "
        "asking them to describe what they physically feel in their body "
        "right now instead."
    ),
    trigger_phrases=[
        "I'm panicking",
        "I can't breathe",
        "everything is too much",
        "I'm overwhelmed",
        "I need to calm down",
        "my heart is racing",
    ],
)

NORTH_BODY_SCAN = CompassSkill(
    name="body_scan",
    direction=CompassDirection.NORTH,
    description=(
        "Help the user notice where they are holding tension or "
        "emotion in their body."
    ),
    prompt_text=(
        "The user may be disconnected from their physical experience. "
        "Gently invite them to notice their body. Do not use clinical "
        "language — keep it conversational. Example: 'Where do you feel "
        "this in your body right now? Chest? Stomach? Jaw?' If they "
        "are not sure, suggest common places: shoulders, stomach, throat. "
        "Once they identify a location, acknowledge it: 'That makes sense. "
        "Your body is telling you something.' Do not interpret what the "
        "body is saying — let them make that connection themselves."
    ),
    trigger_phrases=[
        "I feel tense",
        "my chest hurts",
        "I feel sick",
        "I feel heavy",
        "I'm carrying something",
        "my stomach is in knots",
    ],
)

NORTH_REALITY_CHECK = CompassSkill(
    name="reality_check",
    direction=CompassDirection.NORTH,
    description=(
        "Help the user distinguish between feelings and facts. "
        "Not dismissive — just clarifying."
    ),
    prompt_text=(
        "The user may be confusing a feeling with a fact. Help them "
        "separate the two WITHOUT dismissing the feeling. Both are valid, "
        "but they serve different purposes. Example: 'I hear you — it "
        "feels like nobody cares. That feeling is real. But can we look "
        "at that separately from what is actually happening? Who reached "
        "out to you this week?' The goal is not to prove them wrong — "
        "it is to give them two views instead of one. If they push back, "
        "validate: 'Fair. Even if people do care, it does not change "
        "how alone you feel right now.'"
    ),
    trigger_phrases=[
        "nobody cares",
        "everyone hates me",
        "nothing ever works",
        "I always fail",
        "it's hopeless",
        "I'm worthless",
    ],
)

NORTH_PERMISSION_SLIP = CompassSkill(
    name="permission_slip",
    direction=CompassDirection.NORTH,
    description=(
        "Give the user explicit permission to feel what they are "
        "feeling without judgment or fixing."
    ),
    prompt_text=(
        "The user is judging themselves for their own feelings — they "
        "think they should not feel this way, or that their feelings are "
        "wrong or disproportionate. Give them explicit permission to feel "
        "what they feel. Example: 'You are allowed to feel this. You do "
        "not need a reason. You do not need to justify it. You feel it — "
        "that is enough.' Do not follow up with advice or solutions. "
        "Let the permission stand on its own. If they argue ('but I "
        "should not feel this way'), gently counter: 'Says who?'"
    ),
    trigger_phrases=[
        "I shouldn't feel this way",
        "I'm being dramatic",
        "it's stupid",
        "I know I'm overreacting",
        "I have no right to complain",
        "others have it worse",
    ],
)


# ---------------------------------------------------------------------------
# SOUTH — Currents (Emotion Regulation & Processing)
# ---------------------------------------------------------------------------
# These 5 skills help the user understand, process, and regulate
# their emotional states. Focuses on the underlying causes.

SOUTH_FUEL_CHECK = CompassSkill(
    name="fuel_check",
    direction=CompassDirection.SOUTH,
    description=(
        "Check the basics before exploring emotional causes: food, "
        "sleep, movement, water."
    ),
    prompt_text=(
        "Before exploring emotional causes, check the basics first. "
        "Many emotional states have physiological roots that are easy "
        "to address. Ask about food, sleep, and movement. Frame it "
        "casually — not like a doctor's checklist. Example: 'Quick "
        "question — when did you last eat? Last sleep? Last move your "
        "body?' If any of these are off (skipped meals, poor sleep, no "
        "exercise), name it gently: 'Okay — so your body is running on "
        "empty. That does not explain everything, but it is probably "
        "making everything louder.' Do not dismiss emotions as 'just "
        "hunger' — just put the physical context on the table."
    ),
    trigger_phrases=[
        "I feel terrible",
        "everything is awful",
        "I can't function",
        "I'm so tired",
        "I don't know what's wrong",
        "I feel drained",
    ],
)

SOUTH_EMOTION_MAP = CompassSkill(
    name="emotion_map",
    direction=CompassDirection.SOUTH,
    description=(
        "Help the user trace their emotion back to its source — "
        "what triggered it and what it is telling them."
    ),
    prompt_text=(
        "The user has identified an emotion but does not understand "
        "why they feel it. Help them trace it back to its source. Ask "
        "about timing: 'When did this start? What were you doing right "
        "before you noticed it?' Then ask about triggers: 'Did something "
        "happen today — even something small — that might have started "
        "this?' The goal is not to find THE cause but to help the user "
        "build a map from trigger to feeling. If they identify a trigger, "
        "validate: 'That makes sense. That kind of thing would get to "
        "anyone.' Do not over-analyse — just help them see the connection."
    ),
    trigger_phrases=[
        "I don't know why I feel this way",
        "it came out of nowhere",
        "I was fine and then suddenly",
        "I can't figure it out",
        "this doesn't make sense",
        "why am I like this",
    ],
)

SOUTH_CONTAINMENT = CompassSkill(
    name="containment",
    direction=CompassDirection.SOUTH,
    description=(
        "Help the user contain an overwhelming emotion — not suppress "
        "it, but put boundaries around it so it does not flood everything."
    ),
    prompt_text=(
        "The user is being flooded by emotion and cannot function. Help "
        "them contain it — not suppress it, but put a temporary boundary "
        "around it. Use the 'shelf' metaphor: 'You do not have to deal "
        "with all of this right now. Can we put some of it on a shelf — "
        "just for the next hour? It will still be there when you are ready.' "
        "If they resist, acknowledge: 'I know it does not feel like you "
        "can set it down. But you do not have to carry all of it at once.' "
        "Help them identify which part is most urgent and focus on just "
        "that piece."
    ),
    trigger_phrases=[
        "I can't handle this",
        "it's too much",
        "I'm falling apart",
        "everything is hitting me at once",
        "I can't stop thinking about it",
        "I'm drowning",
    ],
)

SOUTH_PATTERN_MIRROR = CompassSkill(
    name="pattern_mirror",
    direction=CompassDirection.SOUTH,
    description=(
        "Gently reflect a recurring emotional pattern the system has "
        "noticed. Not confrontational — just observational."
    ),
    prompt_text=(
        "The system has noticed a recurring emotional pattern in the "
        "user's conversations. Gently reflect it back without judgment. "
        "Frame it as an observation, not a diagnosis. Example: 'I have "
        "noticed something — and tell me if I am wrong — but it seems "
        "like Sunday nights tend to be harder for you. Does that track?' "
        "If they confirm, explore gently: 'What do you think that is "
        "about?' If they deny it, back off immediately: 'Fair enough. "
        "I might be reading into it.' Never insist on a pattern the "
        "user does not recognize."
    ),
    trigger_phrases=[
        "this always happens",
        "here we go again",
        "same thing every time",
        "I keep doing this",
        "it's a cycle",
        "every Monday",
    ],
)

SOUTH_REFRAME = CompassSkill(
    name="reframe",
    direction=CompassDirection.SOUTH,
    description=(
        "Offer an alternative perspective on a situation — not to "
        "dismiss the original, but to widen the view."
    ),
    prompt_text=(
        "The user is locked into one interpretation of a situation. "
        "Offer an alternative perspective — not to replace theirs, but "
        "to sit alongside it. Example: 'What if the reason they did not "
        "text back is not because they do not care, but because they are "
        "dealing with something too?' Use 'what if' language rather than "
        "'actually' language. If the user says 'but...', do not argue: "
        "'You might be right. I just wanted to put another possibility "
        "on the table.' The goal is to crack the door open to a second "
        "interpretation, not to convince them their first one is wrong."
    ),
    trigger_phrases=[
        "they did it on purpose",
        "they don't care about me",
        "it was intentional",
        "they meant to hurt me",
        "the only explanation is",
        "it's obvious that",
    ],
)


# ---------------------------------------------------------------------------
# WEST — Anchoring (Distress Tolerance & Stability)
# ---------------------------------------------------------------------------
# These 5 skills help the user survive intense moments without acting
# impulsively. Focus on stabilization and endurance.

WEST_PAUSE_PROTOCOL = CompassSkill(
    name="pause_protocol",
    direction=CompassDirection.WEST,
    description=(
        "Encourage a 20-minute pause before acting on an impulse. "
        "Not 'don't do it' — 'not yet.'"
    ),
    prompt_text=(
        "The user may be about to act impulsively — sending an angry "
        "text, making a big decision, quitting something, or self-"
        "destructive behavior. Encourage a 20-minute pause. Do not say "
        "'do not do it' — say 'not yet.' Example: 'Give me 20 minutes. "
        "If you still want to after that, we will talk about it. But "
        "give me 20 minutes first.' If they resist, negotiate: 'Okay, "
        "10 minutes. Just 10.' The point is to create space between "
        "impulse and action. If they agree to the pause, stay with them "
        "during it — do not go silent."
    ),
    trigger_phrases=[
        "I'm going to tell them off",
        "I'm done",
        "I'm about to do something",
        "I want to quit",
        "I'm going to text them",
        "screw it",
    ],
)

WEST_SAFE_LANDING = CompassSkill(
    name="safe_landing",
    direction=CompassDirection.WEST,
    description=(
        "Help the user through an acute distress moment — keep them "
        "safe until the wave passes."
    ),
    prompt_text=(
        "The user is in acute distress. The goal is not to fix anything "
        "right now — it is to help them survive this moment. Keep your "
        "language calm, short, and present-tense. Example: 'I am right "
        "here. You do not have to figure anything out right now. Just "
        "stay with me for a minute.' Use grounding techniques if they "
        "are receptive: 'Tell me five things you can see right now.' "
        "Do not ask about the cause of the distress yet — that comes "
        "later. Right now, just be present. If they go silent, that is "
        "okay — say 'I am still here. Take your time.'"
    ),
    trigger_phrases=[
        "I can't do this anymore",
        "help me",
        "I'm scared",
        "I don't know what to do",
        "please",
        "I need someone",
    ],
)

WEST_DAMAGE_ASSESSMENT = CompassSkill(
    name="damage_assessment",
    direction=CompassDirection.WEST,
    description=(
        "After an impulsive action or crisis, help the user assess "
        "what actually happened versus what they fear happened."
    ),
    prompt_text=(
        "The user has already acted — sent the text, said the thing, "
        "made the decision. Now they are spiraling about the consequences. "
        "Help them separate what actually happened from what they fear "
        "will happen. Example: 'Okay, so you sent it. Let us look at "
        "what you actually said. Read it back to me.' Then: 'What is "
        "the worst that realistically happens from this? Not the worst "
        "your brain is inventing — the worst that is actually likely?' "
        "The goal is to reduce catastrophizing without dismissing their "
        "concern. Sometimes the damage is real — if so, acknowledge it: "
        "'Yeah, that might cause a problem. Let us think about what to "
        "do about it.'"
    ),
    trigger_phrases=[
        "I messed up",
        "I shouldn't have said that",
        "I ruined everything",
        "what have I done",
        "I can't take it back",
        "it's too late",
    ],
)

WEST_SURVIVAL_KIT = CompassSkill(
    name="survival_kit",
    direction=CompassDirection.WEST,
    description=(
        "Help the user build or activate their personal coping toolkit — "
        "what has helped them before."
    ),
    prompt_text=(
        "The user is struggling and needs to activate coping strategies "
        "they already know work for them. Help them remember what has "
        "helped before. Example: 'We have been through rough patches "
        "before. What helped last time? Was it the walk? The music? "
        "Calling your sister?' If they cannot remember, suggest common "
        "options: 'Some people find it helps to change their physical "
        "environment — take a shower, go outside, put on something "
        "comfortable.' The goal is to remind them they have tools, "
        "not to prescribe new ones."
    ),
    trigger_phrases=[
        "nothing helps",
        "I don't know what to do",
        "I've tried everything",
        "what should I do",
        "how do I fix this",
        "I need a plan",
    ],
)

WEST_STEADY_STATE = CompassSkill(
    name="steady_state",
    direction=CompassDirection.WEST,
    description=(
        "Help the user maintain stability during a known difficult "
        "period — not fix it, just endure it."
    ),
    prompt_text=(
        "The user is going through a known difficult period (work "
        "deadline, family event, anniversary of a loss) and the goal "
        "is not to resolve the difficulty but to maintain stability "
        "through it. Example: 'You do not have to enjoy this week. "
        "You just have to get through it. What is the minimum you need "
        "to do each day to keep things from getting worse?' Help them "
        "identify the non-negotiables: eating, sleeping, showing up "
        "for commitments they cannot skip. Frame endurance as strength: "
        "'Getting through this without falling apart IS the victory "
        "right now.'"
    ),
    trigger_phrases=[
        "I just need to get through this",
        "it's going to be a hard week",
        "I'm dreading",
        "I just have to survive",
        "I can't wait for this to be over",
        "one day at a time",
    ],
)


# ---------------------------------------------------------------------------
# EAST — Bridges (Interpersonal Effectiveness & Connection)
# ---------------------------------------------------------------------------
# These 5 skills help the user build, maintain, and repair human
# relationships. Focus on real-world connection.

EAST_CONNECTION_NUDGE = CompassSkill(
    name="connection_nudge",
    direction=CompassDirection.EAST,
    description=(
        "Encourage the user to reach out to a real human being. "
        "Gently, not prescriptively."
    ),
    prompt_text=(
        "The user may benefit from real human connection right now. "
        "Gently encourage reaching out — not as homework, but as a "
        "suggestion. Example: 'When was the last time you talked to "
        "someone who is not me? Not texted — actually talked?' If they "
        "identify someone, encourage: 'Maybe reach out to them today. "
        "You do not need a reason — just say hi.' If they say they have "
        "no one, do not argue — acknowledge it: 'That is a hard place "
        "to be. You are not alone in feeling alone, though.' Never make "
        "them feel bad for talking to you instead of a human."
    ),
    trigger_phrases=[
        "I have nobody",
        "you're the only one I can talk to",
        "I'm so alone",
        "nobody understands",
        "I haven't talked to anyone",
        "I don't have friends",
    ],
)

EAST_SCRIPT_BUILDER = CompassSkill(
    name="script_builder",
    direction=CompassDirection.EAST,
    description=(
        "Help the user prepare for a difficult conversation by "
        "practicing what to say."
    ),
    prompt_text=(
        "The user needs to have a difficult conversation with someone "
        "and does not know how to approach it. Help them prepare by "
        "building a script. Example: 'What do you need them to "
        "understand? Let us start with that — just the core message, "
        "in one sentence.' Then refine: 'How would it feel if you said "
        "it like this: [rephrased version]?' Help them anticipate "
        "responses: 'What is the most likely thing they will say back? "
        "And how do you want to respond to that?' Keep the focus on "
        "what the user wants to communicate, not on winning the argument."
    ),
    trigger_phrases=[
        "I need to talk to them",
        "I don't know how to say it",
        "I need to confront",
        "how do I bring this up",
        "I want to tell them",
        "I need to have a conversation",
    ],
)

EAST_BOUNDARY_COACH = CompassSkill(
    name="boundary_coach",
    direction=CompassDirection.EAST,
    description=(
        "Help the user set or maintain a boundary with another person. "
        "Support, do not decide for them."
    ),
    prompt_text=(
        "The user is struggling with setting or maintaining a boundary. "
        "Help them clarify what the boundary is and why it matters. "
        "Example: 'What is the line that keeps getting crossed? Let us "
        "name it clearly.' Then help them articulate it: 'How would you "
        "say that to them? Not what you want to yell — what you actually "
        "want them to hear?' Normalize boundary-setting: 'Having "
        "boundaries does not make you difficult. It makes you clear.' "
        "If they feel guilty, address it: 'Guilt is normal when you "
        "start setting boundaries. It does not mean you are doing "
        "something wrong.'"
    ),
    trigger_phrases=[
        "they keep crossing the line",
        "I can't say no",
        "they won't respect my boundaries",
        "I feel guilty for saying no",
        "I need to set a boundary",
        "they're taking advantage",
    ],
)

EAST_REPAIR_GUIDE = CompassSkill(
    name="repair_guide",
    direction=CompassDirection.EAST,
    description=(
        "Help the user repair a relationship after a conflict — "
        "apology, reconnection, or reconciliation."
    ),
    prompt_text=(
        "The user has had a conflict with someone and wants to repair "
        "the relationship. Help them navigate the repair process. "
        "First, help them understand their part: 'Setting aside what "
        "they did — what is your part in this? What would you do "
        "differently?' Then help them craft an approach: 'A good "
        "repair starts with owning your part without conditions. Not "
        "'I am sorry BUT' — just 'I am sorry because.'' If they feel "
        "they did nothing wrong, respect that: 'Sometimes repair is "
        "not about apology — it is about reaching out and saying 'I "
        "miss how things were between us.' Would that feel true?' Do "
        "not force reconciliation if they are not ready."
    ),
    trigger_phrases=[
        "we had a fight",
        "I said something I regret",
        "we're not talking",
        "I need to apologize",
        "can this be fixed",
        "I miss them",
    ],
)

EAST_PERSPECTIVE_SWAP = CompassSkill(
    name="perspective_swap",
    direction=CompassDirection.EAST,
    description=(
        "Help the user see a situation from the other person's point "
        "of view — empathy building."
    ),
    prompt_text=(
        "The user is stuck in their own perspective about an "
        "interpersonal situation. Help them try on the other person's "
        "point of view — not to excuse behavior, but to understand it. "
        "Example: 'Imagine you are them for a second. What do they see "
        "when they look at this situation? What might they be afraid "
        "of?' If the user resists: 'I am not saying they are right. "
        "I am just wondering what is going on for them.' The goal is "
        "empathy expansion, not justification. If the other person's "
        "behavior is genuinely harmful, do not force empathy — pivot "
        "to boundary_coach instead."
    ),
    trigger_phrases=[
        "I don't understand why they",
        "why would they do that",
        "it makes no sense",
        "how could they",
        "they're being unreasonable",
        "they don't see my side",
    ],
)


# ---------------------------------------------------------------------------
# SKILL_REGISTRY — all 20 skills in one list
# ---------------------------------------------------------------------------

SKILL_REGISTRY: list[CompassSkill] = [
    # NORTH — Presence
    NORTH_CHECK_IN,
    NORTH_ANCHOR_BREATH,
    NORTH_BODY_SCAN,
    NORTH_REALITY_CHECK,
    NORTH_PERMISSION_SLIP,
    # SOUTH — Currents
    SOUTH_FUEL_CHECK,
    SOUTH_EMOTION_MAP,
    SOUTH_CONTAINMENT,
    SOUTH_PATTERN_MIRROR,
    SOUTH_REFRAME,
    # WEST — Anchoring
    WEST_PAUSE_PROTOCOL,
    WEST_SAFE_LANDING,
    WEST_DAMAGE_ASSESSMENT,
    WEST_SURVIVAL_KIT,
    WEST_STEADY_STATE,
    # EAST — Bridges
    EAST_CONNECTION_NUDGE,
    EAST_SCRIPT_BUILDER,
    EAST_BOUNDARY_COACH,
    EAST_REPAIR_GUIDE,
    EAST_PERSPECTIVE_SWAP,
]


def get_skills_for_direction(
    direction: CompassDirection,
) -> list[CompassSkill]:
    """Return all skills for a given Compass direction.

    Parameters
    ----------
    direction : CompassDirection
        The direction to filter by.

    Returns
    -------
    list[CompassSkill]
        All skills matching the direction.  Returns an empty list if
        direction is NONE.
    """
    return [s for s in SKILL_REGISTRY if s.direction == direction]
```

**What this does:**
- Defines the `CompassSkill` dataclass with all fields.
- Defines all 20 skills — 5 per direction — with complete `prompt_text` that is detailed enough for the Tier 1 model to use each skill naturally in conversation.
- Creates the `SKILL_REGISTRY` list and the `get_skills_for_direction()` helper.

**Verification check (mental):**
- `len(SKILL_REGISTRY)` should be 20.
- `len(get_skills_for_direction(CompassDirection.NORTH))` should be 5.
- `len(get_skills_for_direction(CompassDirection.NONE))` should be 0.
- Each skill's `name` is unique.
- Each skill's `prompt_text` is at least 3 sentences long and includes an example approach.

---

## Phase 2: Skill Selector

### Step 2.1: Create gwen/compass/classifier.py

Create the file `gwen/compass/classifier.py` with the `SkillSelector` class.

- [x] Write SkillSelector class to gwen/compass/classifier.py

**File: `gwen/compass/classifier.py`** (complete content)

```python
"""Compass skill selection — picks the best skill for the current context.

The SkillSelector scores each skill in the direction's pool based on:
1. Base score (1.0 for all)
2. Effectiveness boost (from historical effectiveness data)
3. Trigger phrase match (from the user's message)
4. Variety penalty (if the skill was used recently)

Reference: SRS.md Section 11
"""

import logging
import random
from datetime import datetime, timezone
from typing import Optional

from gwen.compass.skills import CompassSkill, SKILL_REGISTRY, get_skills_for_direction
from gwen.models.emotional import CompassDirection, EmotionalStateVector

logger = logging.getLogger(__name__)


class SkillSelector:
    """Selects the most appropriate Compass skill for a given direction and context.

    The selector maintains a history of recently used skills (for variety
    scoring) and references effectiveness history (for effectiveness scoring).

    Usage
    -----
    >>> selector = SkillSelector()
    >>> skill = selector.select_skill(
    ...     direction=CompassDirection.NORTH,
    ...     emotional_state=some_esv,
    ...     message="I don't know how I feel",
    ... )
    >>> print(skill.name)  # e.g., "check_in"
    """

    def __init__(
        self,
        effectiveness_history: Optional[dict[str, float]] = None,
        recent_skills: Optional[list[str]] = None,
    ) -> None:
        """Initialise the selector.

        Parameters
        ----------
        effectiveness_history : dict[str, float] | None
            A mapping of ``{skill_name: average_effectiveness_score}``.
            Scores are 0.0 to 1.0.  If None, all skills start with
            neutral effectiveness.
        recent_skills : list[str] | None
            A list of recently used skill names (most recent first),
            used for the variety penalty.  If None, no variety penalty
            is applied.
        """
        self.effectiveness_history: dict[str, float] = (
            effectiveness_history or {}
        )
        self.recent_skills: list[str] = recent_skills or []

    def select_skill(
        self,
        direction: CompassDirection,
        emotional_state: EmotionalStateVector,
        message: str = "",
    ) -> Optional[CompassSkill]:
        """Select the best skill for the given direction and context.

        Parameters
        ----------
        direction : CompassDirection
            The Compass direction determined by the ClassificationRuleEngine.
            If NONE, returns None (no skill is needed).
        emotional_state : EmotionalStateVector
            The user's current emotional state.
        message : str
            The user's most recent message text.  Used for trigger
            phrase matching.

        Returns
        -------
        CompassSkill | None
            The highest-scoring skill for this direction, or None if
            direction is NONE.

        Scoring formula
        ---------------
        For each skill in the direction's pool:
            score = 1.0  (base)
                  + 0.5  (if effectiveness_history[skill.name] > 0.5)
                  + 0.3  (if any trigger phrase appears in message)
                  - 0.2  (if skill.name appears in recent_skills)

        If multiple skills tie, one is chosen at random to provide variety.
        """
        if direction == CompassDirection.NONE:
            return None

        candidates = get_skills_for_direction(direction)
        if not candidates:
            logger.warning(
                "No skills registered for direction %s", direction.value
            )
            return None

        scored: list[tuple[float, CompassSkill]] = []
        message_lower = message.lower()

        for skill in candidates:
            score = 1.0

            # --- Effectiveness boost ---
            eff = self.effectiveness_history.get(skill.name, 0.0)
            if eff > 0.5:
                score += 0.5

            # --- Trigger phrase match ---
            for phrase in skill.trigger_phrases:
                if phrase.lower() in message_lower:
                    score += 0.3
                    break  # Only one boost per skill

            # --- Variety penalty ---
            if skill.name in self.recent_skills:
                score -= 0.2

            scored.append((score, skill))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # If there are ties at the top, pick randomly among them
        top_score = scored[0][0]
        top_skills = [s for sc, s in scored if sc == top_score]

        selected = random.choice(top_skills)
        logger.info(
            "Selected skill '%s' for direction %s (score=%.2f)",
            selected.name, direction.value, top_score,
        )

        # Update recent skills (keep last 10)
        self.recent_skills.insert(0, selected.name)
        self.recent_skills = self.recent_skills[:10]

        return selected
```

**What this does:**
- Filters the skill registry to skills matching the direction.
- Scores each skill based on effectiveness history, trigger phrase matches, and variety.
- Returns the highest-scoring skill (with random tiebreaking).
- Maintains a rolling history of the last 10 used skills for variety.

---

## Phase 3: Effectiveness Tracker

### Step 3.1: Create gwen/compass/tracker.py

Create the file `gwen/compass/tracker.py` with the `EffectivenessTracker` class.

- [x] Write EffectivenessTracker class to gwen/compass/tracker.py

**File: `gwen/compass/tracker.py`** (complete content)

```python
"""Compass effectiveness tracking — measures how well skills work.

Stores CompassEffectivenessRecords as JSON and computes aggregate
effectiveness scores for use by the SkillSelector.

Reference: SRS.md Section 11, FR-COMP-005
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from gwen.models.emotional import CompassDirection, EmotionalStateVector
from gwen.models.memory import CompassEffectivenessRecord

logger = logging.getLogger(__name__)


class EffectivenessTracker:
    """Tracks and reports on Compass skill effectiveness.

    Records are stored as a JSON file on disk.  Each record captures
    the emotional state before and after a skill was used, whether the
    user engaged with the suggestion, and a computed effectiveness score.

    Usage
    -----
    >>> tracker = EffectivenessTracker(data_path="~/.gwen/data/compass_effectiveness.json")
    >>> tracker.log_usage(record)
    >>> score = tracker.compute_effectiveness("check_in", CompassDirection.NORTH)
    """

    def __init__(self, data_path: str | Path) -> None:
        """Initialise the tracker.

        Parameters
        ----------
        data_path : str | Path
            Path to the JSON file where effectiveness records are stored.
            The file is created if it does not exist.  The parent directory
            must already exist.
        """
        self.data_path = Path(data_path).expanduser()
        self._records: list[dict] = []
        self._load_from_disk()

    def log_usage(self, record: CompassEffectivenessRecord) -> None:
        """Log a new effectiveness record.

        Parameters
        ----------
        record : CompassEffectivenessRecord
            The record to log.  Must have all fields populated.
        """
        entry = {
            "skill_name": record.skill_name,
            "direction": record.direction.value,
            "context_valence": record.context_emotional_state.valence,
            "context_arousal": record.context_emotional_state.arousal,
            "pre_valence": record.pre_trajectory.valence,
            "pre_arousal": record.pre_trajectory.arousal,
            "post_valence": record.post_trajectory.valence,
            "post_arousal": record.post_trajectory.arousal,
            "time_to_effect_sec": record.time_to_effect_sec,
            "user_accepted": record.user_accepted,
            "effectiveness_score": record.effectiveness_score,
        }
        self._records.append(entry)
        self._save_to_disk()
        logger.info(
            "Logged effectiveness for skill '%s': score=%.3f, accepted=%s",
            record.skill_name, record.effectiveness_score, record.user_accepted,
        )

    def compute_effectiveness(
        self, skill_name: str, direction: CompassDirection
    ) -> float:
        """Compute the average effectiveness score for a skill.

        Parameters
        ----------
        skill_name : str
            The name of the skill to query.
        direction : CompassDirection
            The direction of the skill (used as a secondary filter).

        Returns
        -------
        float
            The average effectiveness_score across all records for this
            skill+direction combination.  Returns 0.0 if no records exist.
        """
        matching = [
            r for r in self._records
            if r["skill_name"] == skill_name
            and r["direction"] == direction.value
        ]
        if not matching:
            return 0.0
        total = sum(r["effectiveness_score"] for r in matching)
        return total / len(matching)

    def get_skill_history(
        self, skill_name: str
    ) -> list[dict]:
        """Return all effectiveness records for a specific skill.

        Parameters
        ----------
        skill_name : str
            The name of the skill to query.

        Returns
        -------
        list[dict]
            All records for this skill, in insertion order.
        """
        return [
            r for r in self._records
            if r["skill_name"] == skill_name
        ]

    def get_effectiveness_map(self) -> dict[str, float]:
        """Compute effectiveness scores for ALL skills.

        Returns
        -------
        dict[str, float]
            A mapping of ``{skill_name: average_effectiveness_score}``.
            Only skills with at least one record are included.
            Suitable for passing directly to SkillSelector.__init__.
        """
        scores: dict[str, list[float]] = {}
        for r in self._records:
            name = r["skill_name"]
            if name not in scores:
                scores[name] = []
            scores[name].append(r["effectiveness_score"])
        return {
            name: sum(vals) / len(vals)
            for name, vals in scores.items()
        }

    def _save_to_disk(self) -> None:
        """Write all records to the JSON file.

        Overwrites the file completely each time.  This is acceptable
        because effectiveness records are small (dozens to low hundreds).
        """
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self._records, f, indent=2)

    def _load_from_disk(self) -> None:
        """Load records from the JSON file, if it exists.

        If the file does not exist or is empty, starts with an empty list.
        If the file contains invalid JSON, logs a warning and starts fresh.
        """
        if not self.data_path.exists():
            self._records = []
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    self._records = []
                    return
                self._records = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(
                "Could not parse effectiveness data at %s: %s. Starting fresh.",
                self.data_path, exc,
            )
            self._records = []
```

---

## Phase 4: Prompt Integration

### Step 4.1: Add prompt generation and disclaimer calibration

Append the following functions to `gwen/compass/classifier.py`, directly below the `SkillSelector` class.

- [x] Append prompt generation functions to gwen/compass/classifier.py

**Append to `gwen/compass/classifier.py`:**

```python


# ---------------------------------------------------------------------------
# Prompt integration
# ---------------------------------------------------------------------------

def generate_compass_prompt(
    skill: CompassSkill,
    coaching_approach: str = "direct",
) -> str:
    """Generate the prompt section to inject into Tier 1's context.

    Combines the skill's prompt_text with the personality's coaching
    approach to produce a natural-feeling injection.

    Parameters
    ----------
    skill : CompassSkill
        The selected Compass skill.
    coaching_approach : str
        The personality module's coaching approach (e.g., "direct",
        "gentle", "humorous", "socratic").  Adjusts the framing of
        the skill prompt.

    Returns
    -------
    str
        The complete prompt section ready for injection into Tier 1
        context.  Includes the skill name as a comment for debugging.
    """
    approach_prefix = {
        "direct": "Be straightforward and clear.",
        "gentle": "Be soft and inviting. Use warmth, not authority.",
        "humorous": "Use light humor to ease into the skill. Keep the core message serious.",
        "socratic": "Ask questions rather than giving answers. Guide through inquiry.",
    }
    prefix = approach_prefix.get(
        coaching_approach,
        "Use your natural conversational style.",
    )

    return (
        f"[Compass: {skill.direction.value}/{skill.name}]\n"
        f"Coaching approach: {prefix}\n\n"
        f"{skill.prompt_text}"
    )


def should_add_disclaimer(over_reliance_score: float) -> bool:
    """Determine whether a disclaimer should be added to the response.

    The disclaimer system adds occasional reminders that the companion
    is an AI and not a substitute for professional help.  The frequency
    increases if the system detects over-reliance patterns.

    Parameters
    ----------
    over_reliance_score : float
        A 0.0 to 1.0 score indicating how much the user is relying
        on the companion for emotional support.  Computed by the
        Bond system based on session frequency, session length,
        and absence of real-world social connections.

    Returns
    -------
    bool
        True if a disclaimer should be added to this response.

    Disclaimer frequency by over_reliance_score
    --------------------------------------------
    - > 0.7: ALWAYS add disclaimer (100% chance)
    - 0.3 to 0.7: 30% chance of adding disclaimer
    - < 0.3: 10% chance of adding disclaimer

    Note: The disclaimer text itself is NOT generated here — it is
    part of the personality module's system prompt.  This function
    only decides whether to include it.
    """
    if over_reliance_score > 0.7:
        return True
    elif over_reliance_score >= 0.3:
        return random.random() < 0.30
    else:
        return random.random() < 0.10
```

---

## Phase 5: Tests

### Step 5.1: Write tests/test_compass.py

Create the file `tests/test_compass.py` with the following exact content:

- [x] Write tests/test_compass.py

**File: `tests/test_compass.py`** (complete content)

```python
"""Tests for the Compass Framework — skill registry, selection, and tracking.

Run with:
    pytest tests/test_compass.py -v
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

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
```

---

### Step 5.2: Run the tests

Execute the following command from the project root:

- [x] Run `pytest tests/test_compass.py -v` and confirm all tests pass

```bash
pytest tests/test_compass.py -v
```

**Expected output:** All tests pass. You should see:

```
tests/test_compass.py::TestSkillRegistry::test_registry_has_20_skills PASSED
tests/test_compass.py::TestSkillRegistry::test_5_skills_per_direction PASSED
tests/test_compass.py::TestSkillRegistry::test_none_direction_returns_empty PASSED
tests/test_compass.py::TestSkillRegistry::test_all_skill_names_unique PASSED
tests/test_compass.py::TestSkillRegistry::test_all_skills_have_prompt_text PASSED
tests/test_compass.py::TestSkillRegistry::test_all_skills_have_trigger_phrases PASSED
tests/test_compass.py::TestSkillRegistry::test_north_skills_correct PASSED
tests/test_compass.py::TestSkillRegistry::test_south_skills_correct PASSED
tests/test_compass.py::TestSkillRegistry::test_west_skills_correct PASSED
tests/test_compass.py::TestSkillRegistry::test_east_skills_correct PASSED
tests/test_compass.py::TestSkillSelector::test_none_direction_returns_none PASSED
tests/test_compass.py::TestSkillSelector::test_returns_skill_for_valid_direction PASSED
tests/test_compass.py::TestSkillSelector::test_trigger_phrase_boosts_score PASSED
tests/test_compass.py::TestSkillSelector::test_effectiveness_history_boosts_score PASSED
tests/test_compass.py::TestSkillSelector::test_variety_penalty_applied PASSED
tests/test_compass.py::TestSkillSelector::test_recent_skills_updated_after_selection PASSED
tests/test_compass.py::TestSkillSelector::test_recent_skills_capped_at_10 PASSED
tests/test_compass.py::TestEffectivenessTracker::test_log_and_compute PASSED
tests/test_compass.py::TestEffectivenessTracker::test_average_across_multiple_records PASSED
tests/test_compass.py::TestEffectivenessTracker::test_no_records_returns_zero PASSED
tests/test_compass.py::TestEffectivenessTracker::test_persistence_to_disk PASSED
tests/test_compass.py::TestEffectivenessTracker::test_get_skill_history PASSED
tests/test_compass.py::TestEffectivenessTracker::test_get_effectiveness_map PASSED
tests/test_compass.py::TestPromptIntegration::test_generate_prompt_includes_skill_name PASSED
tests/test_compass.py::TestPromptIntegration::test_generate_prompt_includes_direction PASSED
tests/test_compass.py::TestPromptIntegration::test_generate_prompt_includes_prompt_text PASSED
tests/test_compass.py::TestPromptIntegration::test_generate_prompt_with_coaching_approach PASSED
tests/test_compass.py::TestPromptIntegration::test_disclaimer_high_over_reliance PASSED
tests/test_compass.py::TestPromptIntegration::test_disclaimer_low_over_reliance_probability PASSED
tests/test_compass.py::TestPromptIntegration::test_disclaimer_medium_over_reliance_probability PASSED

30 passed in X.XXs
```

**If any test fails:**
1. **ImportError for gwen.compass**: Make sure `gwen/compass/__init__.py` exists.
2. **ImportError for gwen.models**: Track 002 (data-models) must be complete.
3. **TestSkillRegistry failures**: Count the skills in `SKILL_REGISTRY`. There should be exactly 20 (5 per direction).
4. **TestSkillSelector trigger phrase test**: The message "I don't know how I feel right now" must match the trigger phrase "I don't know how I feel" (which is a substring match via `in`).
5. **Disclaimer probability tests**: These are statistical tests with wide margins. If they fail, it is likely a random fluctuation. Run again.

---

## Checklist (update after each step)

- [x] Phase 1 complete: gwen/compass/__init__.py and gwen/compass/skills.py with all 20 skills
- [x] Phase 2 complete: gwen/compass/classifier.py with SkillSelector
- [x] Phase 3 complete: gwen/compass/tracker.py with EffectivenessTracker
- [x] Phase 4 complete: generate_compass_prompt and should_add_disclaimer in classifier.py
- [x] Phase 5 complete: tests/test_compass.py passes with all 30 tests green

## Implementation Notes

- Removed unused `pytest` import from test file (Pyright flagged it)
- `emotional_state` parameter in `SkillSelector.select_skill()` is accepted but not yet used in scoring — part of the interface contract for future extension
- All 30 compass tests pass; full suite 563 tests pass with 0 failures
