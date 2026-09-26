"""Duel arithmetic (phase 2 spec §9.2). Pure: fighter snapshots in, numbers out.

The engine builds `Fighter`s from bodies and arts; everything here is a
function of them plus a seeded rng, which is what lets a solver test balance
without a database. Deviations from the spec's first draft (Guard counters a
Strike; a larger damage base) come from the balance targets in §9.5.
"""

import math
from dataclasses import dataclass

from world.body import BODY_PARTS, REGULAR

INTENTS = ("strike", "feint", "guard", "probe")
QI_OUTPUTS = ("restrained", "steady", "full", "all-in")
QI_MULT = {"restrained": 0.7, "steady": 1.0, "full": 1.3, "all-in": 1.7}
QI_COST = {"restrained": 1, "steady": 3, "full": 6, "all-in": 12}
ALL_IN_DEVIATION = 8
DAMAGE_BASE = 35.0
INJURY_THRESHOLD = 8.0
OPENING_BONUS = 1.2
STANCE_BONUS = 1.1
BARE_HANDS = 0.5
BEAST_WEAPONS = 0.8
LIMB_PENALTY = 0.85
BROKEN = 85.0
MAX_HARM = 100.0
CONDITION_BANDS = ((15.0, "fresh"), (35.0, "bruised"), (60.0, "hurt"), (85.0, "badly hurt"))
CONDITION_ORDER = ("fresh", "bruised", "hurt", "badly hurt", "broken")
CONDITION_MULT = {"fresh": 1.0, "bruised": 0.95, "hurt": 0.85, "badly hurt": 0.7, "broken": 0.5}
ARMS = ("left arm", "right arm")
LEGS = ("left leg", "right leg")
FORM_LIMBS = {"footwork": LEGS}  # every other form fights with the arms
FORM_STATS_EXTRA = {"bare": ("strength",), "claws": ("strength", "agility")}
FORM_WOUND = {
    "sword": "cut", "saber": "cut", "spear": "cut", "claws": "cut", "staff": "bruise", "fist": "bruise",
    "bare": "bruise", "footwork": "bruise", "palm": "internal", "finger": "meridian",
}
BLUNT_TARGETS = ("head", "torso", "left arm", "right arm")
FORM_TARGETS = {
    "footwork": ("left leg", "right leg", "torso"), "palm": ("torso",),
    "fist": BLUNT_TARGETS, "bare": BLUNT_TARGETS, "staff": BLUNT_TARGETS,
}
# (A's intent, B's intent) -> effects, seen from A:
#   ("hit", target, multiplier) | ("opening", side) | ("reveal", learner) | ("recover", side)
TABLE = {
    ("strike", "strike"): [("hit", "b", 0.7), ("hit", "a", 0.7)],
    ("strike", "feint"): [("hit", "b", 1.0)],
    ("strike", "guard"): [("hit", "a", 0.5), ("opening", "b")],  # the guard turns the blow and counters
    ("strike", "probe"): [("hit", "b", 1.0)],
    ("feint", "feint"): [],
    ("feint", "guard"): [("hit", "b", 0.8)],
    ("feint", "probe"): [("hit", "a", 0.6), ("reveal", "b")],
    ("guard", "guard"): [("recover", "a"), ("recover", "b")],
    ("guard", "probe"): [("reveal", "b")],
    ("probe", "probe"): [("reveal", "a"), ("reveal", "b")],
}
SWAP = {"a": "b", "b": "a"}


@dataclass(frozen=True)
class Fighter:
    name: str
    realm_mult: float
    stage: int                 # 0..3: early, middle, late, peak
    technique: str | None      # the art's name, or None
    form: str                  # an art form, "bare" or "claws"
    grade_mult: float
    mastery: float
    compat: float
    body_fit: float            # 0.8 + 0.4 * governing stat / 20
    limb_injuries: int         # unhealed injuries on the limbs this form uses
    leg_injuries: int
    agility: int
    qi: float
    traits: tuple[str, ...] = ()
    beast: bool = False
    stance_favours: str | None = None
    weapon_mult: float = 1.0          # what they hold, for a weapon art (phase 5a)
    weapon_grade: int | None = None   # the blade that meets the other's, for breakage
    armour: float = 0.0               # the share armour takes off a wound


@dataclass(frozen=True)
class Blow:
    target: str
    damage: float


@dataclass(frozen=True)
class Resolution:
    blows: tuple[Blow, ...]
    openings: tuple[str, ...]
    reveals: tuple[str, ...]
    recover: tuple[str, ...]


def condition_of(harm: float) -> str:
    for limit, name in CONDITION_BANDS:
        if harm < limit:
            return name
    return "broken"


def limbs_for(form: str) -> tuple[str, ...]:
    return FORM_LIMBS.get(form, ARMS)


def technique_power(f: Fighter) -> float:
    if f.beast:
        return BEAST_WEAPONS
    if f.technique is None:
        return BARE_HANDS
    return f.grade_mult * (0.5 + f.mastery) * f.compat * f.weapon_mult


def affordable(output: str, qi: float) -> str:
    index = QI_OUTPUTS.index(output)
    while index > 0 and QI_COST[QI_OUTPUTS[index]] > qi:
        index -= 1
    return QI_OUTPUTS[index]


def power(f: Fighter, intent: str, output: str, harm: float, opening: bool) -> float:
    value = (f.realm_mult * (1 + 0.1 * f.stage) * technique_power(f) * QI_MULT[output]
             * CONDITION_MULT[condition_of(harm)] * f.body_fit * LIMB_PENALTY ** f.limb_injuries)
    if opening:
        value *= OPENING_BONUS
    if f.stance_favours == intent:
        value *= STANCE_BONUS
    return value


def effects(a_intent: str, b_intent: str) -> list[tuple]:
    if (a_intent, b_intent) in TABLE:
        return TABLE[(a_intent, b_intent)]
    return [(e[0], SWAP[e[1]], *e[2:]) for e in TABLE[(b_intent, a_intent)]]


def resolve(a_intent: str, b_intent: str, a_power: float, b_power: float, rng, scale: float = 1.0) -> Resolution:
    blows, openings, reveals, recover = [], [], [], []
    for effect in effects(a_intent, b_intent):
        kind, side = effect[0], effect[1]
        if kind == "hit":
            hitter, target = (a_power, b_power) if side == "b" else (b_power, a_power)
            damage = DAMAGE_BASE * (hitter / max(target, 1e-6)) ** 0.8 * effect[2] * rng.uniform(0.8, 1.2) * scale
            blows.append(Blow(side, round(damage, 2)))
        elif kind == "opening":
            openings.append(side)
        elif kind == "reveal":
            reveals.append(side)
        else:
            recover.append(side)
    return Resolution(tuple(blows), tuple(openings), tuple(reveals), tuple(recover))


def wound(form: str, damage: float, rng, spar: bool = False) -> tuple[str, str, int] | None:
    """(location, kind, severity) for a blow, or None if it only bruised the fight, not the body."""
    if damage < INJURY_THRESHOLD:
        return None
    severity = min(5, 1 + int(damage // 12))
    kind = FORM_WOUND.get(form, "bruise")
    if spar:
        severity = min(2, severity)
        if kind == "meridian":
            kind = "bruise"
    if kind == "meridian":
        return (rng.choice(REGULAR), "meridian", severity)
    if kind == "bruise" and severity >= 4:
        kind = "fracture"
    return (rng.choice(FORM_TARGETS.get(form, BODY_PARTS)), kind, severity)


def flee_chance(runner: Fighter, chaser: Fighter, runner_harm: float) -> float:
    x = ((runner.agility - chaser.agility) / 4 - 0.5 * runner.leg_injuries
         - 0.5 * CONDITION_ORDER.index(condition_of(runner_harm)))
    return 1 / (1 + math.exp(-x))
