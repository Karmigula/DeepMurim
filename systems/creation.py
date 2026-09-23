"""Character creation (phase 2 spec §7): an origin, pure chance, or point-buy.

Creation is generation, like materializing a town: it writes the body, purse
and starting arts directly. Every mode rolls a hidden constitution.
"""

from dataclasses import dataclass, field

from systems.techniques import FORMS, create_technique, generate, teach
from world.body import PHYSIQUE, Body, roll_body, to_dict
from world.db import World
from world.events import Event, effect
from world.seed import rng_for


@dataclass(frozen=True)
class Origin:
    key: str
    title: str
    description: str
    heart_grade: int
    heart_element: str | None
    art_forms: tuple[str, ...]
    bias: dict = field(default_factory=dict)
    silver: int = 0
    heart_completeness: float = 1.0  # below 1.0 the family method is secretly incomplete


ORIGINS = {
    "hunter": Origin("hunter", "Hunter's child", "Raised on game trails; strong legs and a steady spear.",
                     1, None, ("spear", "fist"), {"strength": 2, "endurance": 2}, 30),
    "scion": Origin("scion", "Fallen clan scion", "Born to a ruined martial clan; the family method survived the fall.",
                    2, None, ("sword",), {"comprehension": 2, "scarred": 1}, 80, 0.8),
    "temple": Origin("temple", "Temple orphan", "Raised by monks on chanting, cold water and a single palm art.",
                     1, "yang", ("palm", "staff"), {"purity": 0.1, "endurance": 2}, 10),
    "merchant": Origin("merchant", "Merchant's runaway", "Fled a counting-house with quick feet and a fat purse.",
                       1, None, ("footwork",), {"agility": 2}, 200),
    "beggar": Origin("beggar", "Beggar-sect urchin", "Grew up in the alleys among ragged, dangerous masters.",
                     1, None, ("staff", "fist"), {"agility": 2, "comprehension": 1}, 5),
}
WANDERER = Origin("wanderer", "Wanderer", "A drifter with a little training and less money.",
                  1, None, ("fist", "sword", "palm"), {}, 20)
MODES = ("random", "origin", "point_buy")
POINT_BASE, POINT_POOL, POINT_MAX, FLOW_POINT_COST = 8, 12, 16, 2


@dataclass(frozen=True)
class CreationChoice:
    mode: str = "random"
    origin: str | None = None
    physique: tuple[tuple[str, int], ...] | None = None
    flow_points: int = 0
    form: str | None = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode, "origin": self.origin,
            "physique": dict(self.physique) if self.physique else None,
            "flow_points": self.flow_points, "form": self.form,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CreationChoice":
        physique = data.get("physique")
        return cls(
            data.get("mode", "random"), data.get("origin"),
            tuple(physique.items()) if physique else None,
            data.get("flow_points", 0), data.get("form"),
        )


@dataclass
class Creation:
    origin: Origin
    body: Body
    arts: list        # [(name, data, true completeness)]
    silver: int


def points_spent(physique: dict, flow_points: int) -> int:
    return sum(physique[p] - POINT_BASE for p in PHYSIQUE) + flow_points * FLOW_POINT_COST


def point_buy_problem(physique: dict, flow_points: int) -> str | None:
    if set(physique) != set(PHYSIQUE):
        return "Every attribute needs a value."
    for name in PHYSIQUE:
        if not POINT_BASE <= physique[name] <= POINT_MAX:
            return f"{name} must be between {POINT_BASE} and {POINT_MAX}."
    if flow_points < 0:
        return "Meridian openness cannot be negative."
    spent = points_spent(physique, flow_points)
    if spent > POINT_POOL:
        return f"{spent} points spent; only {POINT_POOL} available."
    return None


def build(world_seed: int, choice: CreationChoice) -> Creation:
    rng = rng_for(world_seed, "creation")
    if choice.mode == "origin":
        origin = WANDERER if choice.origin == "wanderer" else ORIGINS.get(choice.origin)
        if origin is None:
            raise ValueError(f"unknown origin {choice.origin!r}")
        body = roll_body(rng, bias=origin.bias)
    elif choice.mode == "point_buy":
        physique = dict(choice.physique or ())
        problem = point_buy_problem(physique, choice.flow_points)
        if problem:
            raise ValueError(problem)
        if choice.form not in FORMS:
            raise ValueError(f"choose a form from {FORMS}")
        origin = Origin("self_made", "Self-made", "Shaped by will alone.", 1, None, (choice.form,), {}, 50)
        body = roll_body(rng, physique=physique, flow_bonus=0.1 * choice.flow_points)
    elif choice.mode == "random":
        origin = ORIGINS[rng.choice(sorted(ORIGINS))]
        body = roll_body(rng)
    else:
        raise ValueError(f"unknown creation mode {choice.mode!r}")
    heart_name, heart = generate(rng, "heart_method", grade=origin.heart_grade, element=origin.heart_element)
    art_name, art = generate(rng, "martial", form=rng.choice(origin.art_forms), grade=1)
    return Creation(origin, body, [(heart_name, heart, origin.heart_completeness), (art_name, art, 1.0)], origin.silver)


def apply_creation(world: World, person_id: int, creation: Creation) -> list[str]:
    """Write body, purse and starting arts onto a person. Returns the art names."""
    creation.body.settled_at = world.time
    world.update_data(
        person_id, body=to_dict(creation.body), silver=creation.silver, realm="mortal",
        origin=creation.origin.key, origin_title=creation.origin.title,
    )
    names = []
    for name, data, completeness in creation.arts:
        technique = create_technique(world, name, data)
        teach(world, person_id, technique, completeness=completeness, known_completeness=1.0, source="origin")
        names.append(name)
    return names


def wanderer_arts(world_seed: int) -> list[str]:
    return [name for name, _, _ in build(world_seed, CreationChoice("origin", "wanderer")).arts]


@effect("body_awakened")
def _awaken(world: World, event: Event) -> None:
    """A save from before bodies existed: give its hero one."""
    apply_creation(world, event.actors[0], build(world.world_seed, CreationChoice("origin", "wanderer")))
