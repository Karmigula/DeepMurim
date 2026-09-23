"""Martial arts as things in the world (phase 2 spec §5).

A technique is an entity; knowing one is a `knows` relation carrying mastery
and completeness. `completeness` is what the art truly contains;
`known_completeness` is what its knower believes. Only the belief is ever shown.
"""

import math
from dataclasses import dataclass
from statistics import mean

from world.body import ELEMENTS, REGULAR, Body
from world.db import Entity, World

FORMS = ("sword", "saber", "spear", "staff", "palm", "fist", "finger", "footwork")
GRADE_MULT = (1.0, 1.5, 2.2, 3.2, 4.5, 6.5)
INTENTS = ("strike", "feint", "guard", "probe")
ELEMENT_CHOICES = ELEMENTS + ("yin", "yang", "neutral")
ROUTE_FACTOR = {"open": 1.0, "scarred": 0.8, "damaged": 0.5, "blocked": 0.3, "severed": 0.0}
FORM_STATS = {
    "sword": ("agility",), "finger": ("agility",), "footwork": ("agility",),
    "saber": ("strength",), "fist": ("strength",),
    "spear": ("strength", "agility"), "staff": ("strength", "agility"),
    "palm": ("endurance", "comprehension"), "inner": ("endurance", "comprehension"),
}
ADJECTIVES = (
    "Pale", "Iron", "Nine Bends", "Falling Leaf", "Azure", "Blood", "Silent", "Heavenly",
    "Drunken", "Hidden", "Golden", "Frost", "Burning", "Hundred Step", "Thousand Hand",
)
NOUNS = (
    "Crane", "Tiger", "Plum", "Thunder", "Serpent", "Cloud", "Mountain", "River",
    "Wolf", "Lotus", "Dragon", "Moon", "Wind", "Stone", "Phoenix",
)
FORM_WORDS = {
    "sword": ("Sword Art", "Sword"), "saber": ("Saber", "Saber Art"), "spear": ("Spear", "Spear Art"),
    "staff": ("Staff", "Staff Art"), "palm": ("Palm",), "fist": ("Fist",), "finger": ("Finger",),
    "footwork": ("Steps", "Footwork"), "inner": ("Heart Method", "Divine Art", "Qi Manual"),
}
STANCES = {
    "strike": ("Charging Bull Stance", "Falling Hammer Stance"),
    "feint": ("Shifting Shadow Stance", "Drunken Step Stance"),
    "guard": ("Iron Gate Stance", "Rooted Pine Stance"),
    "probe": ("Listening Wind Stance", "Watching Crane Stance"),
}
MASTERY_STAGES = ((0.34, "Initial"), (0.67, "Minor Success"), (1.0, "Major Success"))


def grade_mult(grade: int) -> float:
    return GRADE_MULT[max(1, min(len(GRADE_MULT), grade)) - 1]


def technique_name(rng, form: str) -> str:
    return f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)} {rng.choice(FORM_WORDS[form])}"


def generate(rng, category: str, form: str | None = None, grade: int = 1, element: str | None = None) -> tuple[str, dict]:
    form = "inner" if category == "heart_method" else (form or rng.choice(FORMS))
    element = element or rng.choice(ELEMENT_CHOICES)
    route = rng.sample(REGULAR, min(6, rng.randint(2, 3 + grade // 2)))
    favours = rng.choice(INTENTS)
    data = {
        "category": category, "form": form,
        "stance": {"name": rng.choice(STANCES[favours]), "favours": favours},
        "route": route, "element": element, "grade": grade,
        "power": round(rng.uniform(0.7, 1.3), 2), "speed": round(rng.uniform(0.7, 1.3), 2),
        "defence": round(rng.uniform(0.7, 1.3), 2), "creator": None, "origin": "seeded",
    }
    return technique_name(rng, form), data


def create_technique(world: World, name: str, data: dict) -> int:
    return world.add_entity("technique", name, data)


@dataclass(frozen=True)
class Known:
    technique: Entity
    mastery: float
    completeness: float
    known_completeness: float
    source: str
    teacher: int | None

    @property
    def name(self) -> str:
        return self.technique.name

    @property
    def category(self) -> str:
        return self.technique.data["category"]

    @property
    def form(self) -> str:
        return self.technique.data["form"]


def teach(world: World, person_id: int, technique_id: int, completeness: float = 1.0,
          known_completeness: float = 1.0, source: str = "taught", teacher: int | None = None,
          mastery: float = 0.05) -> None:
    data = {"completeness": completeness, "known_completeness": known_completeness, "source": source, "teacher": teacher}
    world.relate(person_id, technique_id, "knows", value=mastery, data=data)


def set_mastery(world: World, person_id: int, technique_id: int, mastery: float) -> None:
    for tech_id, _, data in world.relations_from(person_id, "knows"):
        if tech_id == technique_id:
            world.relate(person_id, technique_id, "knows", value=mastery, data=data)
            return
    raise KeyError(f"#{person_id} does not know technique #{technique_id}")


def known_arts(world: World, person_id: int) -> list[Known]:
    arts = []
    for tech_id, mastery, data in world.relations_from(person_id, "knows"):
        arts.append(Known(
            world.entity(tech_id), mastery, data.get("completeness", 1.0),
            data.get("known_completeness", 1.0), data.get("source", "unknown"), data.get("teacher"),
        ))
    return arts


def heart_method(world: World, person_id: int) -> Known | None:
    return next((a for a in known_arts(world, person_id) if a.category == "heart_method"), None)


def martial_arts(world: World, person_id: int) -> list[Known]:
    return [a for a in known_arts(world, person_id) if a.category == "martial"]


def alignment(element: str, nature: dict) -> float:
    if element == "neutral":
        return 0.0
    if element in ("yin", "yang"):
        return max(-1.0, min(1.0, nature.get(element, 0.5) * 2 - 1))
    return max(-1.0, min(1.0, (nature.get(element, 0.2) - 0.2) / 0.2))


def usable(body: Body, data: dict) -> bool:
    return all(body.meridians[m].state != "severed" for m in data["route"])


def compatibility(body: Body, data: dict) -> float:
    route = math.prod(ROUTE_FACTOR[body.meridians[m].state] for m in data["route"])
    nature = max(0.6, min(1.3, 1 + 0.3 * alignment(data["element"], body.nature)))
    stat = mean(body.physique[s] for s in FORM_STATS[data["form"]])
    fit = 0.8 + 0.4 * (stat / 20)
    return round(max(0.0, min(1.3, route * nature * fit)), 3)


def compat_words(c: float) -> str:
    if c < 0.4:
        return "fights your body"
    if c < 0.7:
        return "sits awkwardly"
    if c < 1.0:
        return "suits you"
    return "made for you"


def mastery_stage(mastery: float) -> str:
    for limit, name in MASTERY_STAGES:
        if mastery < limit:
            return name
    return "Great Completion"


def practise_gain(days: float, comprehension: float, compat: float, grade: int) -> float:
    return days * 0.004 * (comprehension / 10) * compat / grade_mult(grade)


def set_known_completeness(world: World, person_id: int, technique_id: int) -> None:
    """The knower learns the truth: belief becomes the real completeness."""
    for tech_id, mastery, data in world.relations_from(person_id, "knows"):
        if tech_id == technique_id:
            truth = {**data, "known_completeness": data.get("completeness", 1.0)}
            world.relate(person_id, technique_id, "knows", value=mastery, data=truth)
            return
