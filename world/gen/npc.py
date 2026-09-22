from dataclasses import dataclass

from world.gen.names import person_name
from world.seed import rng_for

OCCUPATIONS = (
    "innkeeper", "herbalist", "blacksmith", "merchant", "wandering swordsman", "beggar",
    "scholar", "hunter", "constable", "tea seller", "monk", "fortune teller",
)
TRAITS = (
    "proud", "kind", "greedy", "cautious", "hot-tempered", "curious",
    "honest", "cunning", "lazy", "loyal", "secretive", "cheerful",
)
REALMS = ("mortal", "mortal", "mortal", "third-rate", "third-rate", "second-rate", "first-rate")
PORTRAIT_PARTS = {"hair": 4, "face": 4, "robe": 4}


@dataclass(frozen=True)
class NpcSpec:
    surname: str
    given: str
    gender: str
    age: int
    occupation: str
    traits: tuple[str, str]
    realm: str
    portrait: tuple[tuple[str, int], ...]

    @property
    def name(self) -> str:
        return f"{self.surname} {self.given}"


def npc_path(town_path: str, i: int) -> str:
    return f"{town_path}/npc:{i}"


def npc_spec(world_seed: int, town_path: str, i: int) -> NpcSpec:
    rng = rng_for(world_seed, npc_path(town_path, i))
    surname, given = person_name(rng)
    return NpcSpec(
        surname=surname,
        given=given,
        gender=rng.choice(("man", "woman")),
        age=rng.randint(16, 70),
        occupation=rng.choice(OCCUPATIONS),
        traits=tuple(rng.sample(TRAITS, 2)),
        realm=rng.choice(REALMS),
        portrait=tuple((part, rng.randrange(count)) for part, count in PORTRAIT_PARTS.items()),
    )
