"""The Grand Martial Assembly (phase 4e spec 3): every three years a famous city fills with the Murim's best."""

import systems.tournaments as T
from systems.founding import make_person

SIZE, ROUND_DAYS = 32, (1, 3, 5, 7, 8)
MIN_REALM = 2  # Second-rate
BOND = 100


def places(world, n: int, rng) -> list[int]:
    return [T.host_city(world, rng)]


def start_data(world, town: int, n: int, rng) -> dict:
    edition = T.edition(world, "grand_assembly")
    return T.start_data("grand_assembly", SIZE, ROUND_DAYS, rng.randint(300, 800),
                        f"Champion of the {T.ordinal(edition)} Grand Martial Assembly", edition)


def qualifies(world, person: int) -> bool:
    return T.realm_of(world, person) >= MIN_REALM


def _wanderer(world, occurrence, i: int, rng) -> int:
    return make_person(world, f"tournament:{occurrence.id}:wanderer:{i}", occurrence.data["place"],
                       occupation="wandering swordsman", age=rng.randint(25, 60),
                       realm=rng.choice(("second-rate", "second-rate", "first-rate")))


def invite(world, occurrence) -> list[int]:
    return T.pool(world, occurrence, lambda p: qualifies(world, p), SIZE, _wanderer)


def on_stage(world, occurrence, stage: str) -> list:
    return T.on_stage(world, occurrence, stage, invite)


def on_observe(world, occurrence) -> list:
    return T.on_observe(world, occurrence)
