"""The body: dantian, meridians, physique and injuries (phase 2 spec §3).

Stored as JSON under a person's data["body"]. `settle` brings a body forward to
a moment in time: injuries heal, damaged meridians recover or scar, deviation
fades and qi returns. It is pure, so reading a body at time t gives the same
answer however long ago it was last written.
"""

import copy
from dataclasses import asdict, dataclass, field

REGULAR = (
    "Lung", "Large Intestine", "Stomach", "Spleen", "Heart", "Small Intestine",
    "Bladder", "Kidney", "Pericardium", "Triple Burner", "Gallbladder", "Liver",
)
EXTRAORDINARY = (
    "Governing", "Conception", "Penetrating", "Girdle",
    "Yin Linking", "Yang Linking", "Yin Heel", "Yang Heel",
)
MERIDIANS = REGULAR + EXTRAORDINARY
STATES = ("open", "blocked", "damaged", "scarred", "severed")
BODY_PARTS = ("head", "torso", "left arm", "right arm", "left leg", "right leg")
LOCATIONS = BODY_PARTS + MERIDIANS
INJURY_KINDS = ("bruise", "cut", "fracture", "internal", "meridian")
ELEMENTS = ("metal", "wood", "water", "fire", "earth")
PHYSIQUE = ("strength", "agility", "endurance", "comprehension")
CONSTITUTIONS = (
    "Nine Yin Body", "Pure Yang Body", "Heavenly Sword Bones",
    "Myriad Poison Body", "Iron Bone Body", "Dragon Vein Body",
)
CONSTITUTION_CHANCE = 0.04
WATCHES_PER_DAY = 4
RESIDUE_FADE_PER_WEEK, PURE_FADE = 2.0, 0.8  # residue fades twice as fast in a body purer than this (5b)
LETHAL_POISON, POISONED_TO_DEATH = 4, "poisoned to death"
DEVIATION_DECAY_PER_DAY = 0.5
QI_REGEN_PER_DAY = 0.5  # fraction of max qi recovered per day
HEAL_FASTER = {"Iron Bone Body": 1.5}


@dataclass
class Meridian:
    state: str = "open"
    flow: float = 0.5
    opening: float = 0.0          # progress towards opening, while blocked
    heals_at: int | None = None   # while damaged: when it recovers


@dataclass
class Injury:
    id: int
    location: str
    kind: str
    severity: int
    permanent: bool
    since: int
    heals_at: int | None
    cause: str


@dataclass
class Body:
    energy_years: float = 0.0
    qi: float = 10.0
    purity: float = 0.5
    nature: dict = field(default_factory=dict)
    meridians: dict = field(default_factory=dict)
    physique: dict = field(default_factory=dict)
    constitution: str | None = None
    constitution_known: bool = False
    injuries: list = field(default_factory=list)
    deviation: float = 0.0
    realm: int = 0
    bottleneck: bool = False
    insight: float = 0.0
    flags: list = field(default_factory=list)
    meditated_days: float = 0.0
    settled_at: int = 0
    next_injury_id: int = 1
    residue: float = 0.0        # pill residue, 0-100 (phase 5b)
    venom: float = 0.0          # poison taken in along the poison path, 0-100
    poisons: list = field(default_factory=list)  # active poisons: {grade, strength, days, sealed_until, source}
    resist: int = 0             # poisons of this grade or less pass harmlessly (a beast's blood)
    baths: dict = field(default_factory=dict)    # physique stat -> times raised by a tempering bath
    breakthrough_aid: float = 0.0  # a breakthrough pill's help, spent on the next attempt


def max_qi(body: Body) -> float:
    return 10.0 + 10.0 * body.energy_years * body.purity


def to_dict(body: Body) -> dict:
    return asdict(body)


def from_dict(data: dict) -> Body:
    data = copy.deepcopy(data)
    data["meridians"] = {name: Meridian(**m) for name, m in data.get("meridians", {}).items()}
    data["injuries"] = [Injury(**i) for i in data.get("injuries", [])]
    return Body(**data)


def clone(body: Body) -> Body:
    return from_dict(to_dict(body))


def heal_watches(severity: int, body: Body) -> int:
    days = severity ** 2 * 5 / (body.physique.get("endurance", 10) / 10)
    days /= HEAL_FASTER.get(body.constitution, 1.0)
    return max(1, round(days * WATCHES_PER_DAY))


def add_injury(body: Body, location: str, kind: str, severity: int, now: int, cause: str,
               permanent: bool = False) -> Injury:
    if location not in LOCATIONS:
        raise ValueError(f"no such body location: {location!r}")
    severity = max(1, min(5, int(severity)))
    heals_at = None if permanent else now + heal_watches(severity, body)
    injury = Injury(body.next_injury_id, location, kind, severity, permanent, now, heals_at, cause)
    body.next_injury_id += 1
    body.injuries.append(injury)
    meridian = body.meridians.get(location)
    if meridian is not None:
        if permanent or severity >= 5:
            meridian.state, meridian.heals_at = "severed", None
        elif meridian.state == "open":
            meridian.state, meridian.heals_at = "damaged", heals_at
        elif meridian.state == "damaged":
            meridian.heals_at = max(meridian.heals_at or 0, heals_at)
    return injury


def unhealed(body: Body, now: int) -> list[Injury]:
    return [i for i in body.injuries if i.permanent or (i.heals_at is not None and i.heals_at > now)]


def settle(body: Body, now: int) -> Body:
    settled = clone(body)
    if now <= settled.settled_at:
        return settled
    days = (now - settled.settled_at) / WATCHES_PER_DAY
    settled.injuries = unhealed(settled, now)
    for meridian in settled.meridians.values():
        if meridian.state == "damaged" and meridian.heals_at is not None and meridian.heals_at <= now:
            meridian.state = "open" if meridian.flow >= 0.5 else "scarred"
            meridian.heals_at = None
    settled.deviation = max(0.0, settled.deviation - DEVIATION_DECAY_PER_DAY * days)
    fade = RESIDUE_FADE_PER_WEEK * (2 if settled.purity > PURE_FADE else 1) * days / 7
    settled.residue = max(0.0, round(settled.residue - fade, 3))
    _run_poisons(settled, now)
    settled.qi = min(max_qi(settled), settled.qi + max_qi(settled) * QI_REGEN_PER_DAY * days)
    settled.settled_at = now
    return settled


def _run_poisons(body: Body, now: int) -> None:
    """Poisons spread watch by watch while unsealed: strength ebbs, and each full day does internal harm (5b)."""
    left = []
    for p in body.poisons:
        start = max(p.get("at", body.settled_at), body.settled_at)
        active = max(0, now - max(start, min(now, p.get("sealed_until") or 0)))
        watches = min(active, p["strength"])
        days_before = p.get("days", 0.0)
        p = {**p, "strength": p["strength"] - watches, "days": days_before + watches / WATCHES_PER_DAY,
             "at": now}
        for day in range(int(days_before) + 1, int(p["days"]) + 1):
            add_injury(body, "torso", "internal", p["grade"], now, "poison")
        if p["grade"] >= LETHAL_POISON and p["days"] > body.realm + 2 and POISONED_TO_DEATH not in body.flags:
            body.flags.append(POISONED_TO_DEATH)  # it outlasted the body, even if it ran out since
        if p["strength"] > 0:
            left.append(p)
    body.poisons = left


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def roll_body(rng, bias: dict | None = None, physique: dict | None = None, flow_bonus: float = 0.0) -> Body:
    """A body from seeded dice. `bias` nudges an origin; `physique` fixes it (point-buy)."""
    bias = bias or {}
    if physique is None:
        physique = {p: int(_clamp(round(rng.gauss(10, 2.5)) + bias.get(p, 0), 1, 20)) for p in PHYSIQUE}
    else:
        physique = {p: int(physique[p]) for p in PHYSIQUE}
    meridians = {}
    for name in REGULAR:
        flow = _clamp(rng.uniform(0.4, 0.9) + flow_bonus + bias.get("flow", 0.0), 0.1, 1.0)
        meridians[name] = Meridian("open", round(flow, 2))
    for name in EXTRAORDINARY:
        meridians[name] = Meridian("blocked", 0.0)
    for name in rng.sample(REGULAR, int(bias.get("scarred", 0))):
        meridians[name].state = "scarred"
    yang = round(_clamp(rng.uniform(0.3, 0.7) + bias.get("yang", 0.0), 0.1, 0.9), 2)
    raw = [rng.random() + 0.05 for _ in ELEMENTS]
    total = sum(raw)
    nature = {"yin": round(1 - yang, 2), "yang": yang, **{e: round(w / total, 3) for e, w in zip(ELEMENTS, raw)}}
    purity = round(_clamp(rng.uniform(0.35, 0.6) + bias.get("purity", 0.0), 0.3, 1.0), 2)
    constitution = rng.choice(CONSTITUTIONS) if rng.random() < CONSTITUTION_CHANCE else None
    body = Body(purity=purity, nature=nature, meridians=meridians, physique=physique, constitution=constitution)
    body.qi = max_qi(body)
    return body


def body_of(entity) -> Body | None:
    raw = entity.data.get("body")
    return from_dict(raw) if raw else None
