"""The Dragon-Phoenix Meet (phase 4e spec 3): every two years the young talents of the Murim meet."""

import systems.tournaments as T
from systems import factions as F
from systems.founding import make_person
from world.events import Event, effect

SIZE, ROUND_DAYS = 16, (1, 2, 3, 5)
MAX_AGE = 30
BOND = 30
HONOUR = 5  # the winner's sect's power


def places(world, n: int, rng) -> list[int]:
    return [T.host_city(world, rng)]


def start_data(world, town: int, n: int, rng) -> dict:
    year = n // 4 + 1
    return T.start_data("dragon_phoenix", SIZE, ROUND_DAYS, rng.randint(100, 300), f"Dragon-Phoenix of year {year}",
                        T.edition(world, "dragon_phoenix"))


def qualifies(world, occurrence, person: int, slack: int = 0) -> bool:
    return float(world.entity(person).data.get("age", 30)) <= MAX_AGE + slack


def _wanderer(world, occurrence, i: int, rng) -> int:
    return make_person(world, f"tournament:{occurrence.id}:wanderer:{i}", occurrence.data["place"],
                       occupation="wandering swordsman", age=rng.randint(16, MAX_AGE),
                       realm=rng.choice(("third-rate", "second-rate")))


def invite(world, occurrence) -> list[int]:
    return T.pool(world, occurrence, lambda p: qualifies(world, occurrence, p), SIZE, _wanderer)


def rewards(world, occurrence, champion) -> list[Event]:
    """The winner's sect stands taller (spec §3)."""
    if champion is None:
        return []
    sects = sorted(f for f, _, d in F.memberships(world, champion)
                   if d.get("status", "member") == "member" and world.entity(f).data.get("type") in F.STAFFED)
    return [Event("sect_honoured", (sects[0],), occurrence.data["place"], {"power": HONOUR})] if sects else []


@effect("sect_honoured")
def _honoured(world, event) -> None:
    faction = world.entity(event.actors[0])
    world.update_data(faction.id, power=min(100, faction.data.get("power", 50) + event.data["power"]))


def on_stage(world, occurrence, stage: str) -> list:
    return T.on_stage(world, occurrence, stage, invite)


def on_observe(world, occurrence) -> list:
    return T.on_observe(world, occurrence)
