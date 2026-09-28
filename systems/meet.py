"""The Meet of Hammer and Furnace (phase 5d spec 6): once a year, in a host city, smiths show a blade and
alchemists a pill.

It opens each spring for 30 days in a city (4e's host). Seven seeded masters stand in each craft; the player may
show one piece in each. A blade scores `10 x grade + 10 x the smith's mastery of its form`, a pill
`10 x grade + 10 x purity`. When the Meet closes the best of each craft is named: the player, if they won, takes
500 silver and a title. The Meet is one meta row (`meet`), decided in the season after it closes.
"""

import systems.forging as FG
import systems.lives as lives
import systems.world_clock as world_clock
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import Event, commit, effect, listen
from world.gen.names import person_name
from world.seed import rng_for

CRAFTS = ("forging", "refining")
DAYS, FIELD, PRIZE = 30, 7, 500
MASTER_SCORES = (20.0, 55.0)
WORDS = {"forging": "the anvil", "refining": "the furnace"}


def current(world) -> dict | None:
    return world.get_meta("meet")


def is_open(world, place=None) -> bool:
    m = current(world)
    return m is not None and not m["decided"] and m["start"] <= world.time < m["end"] \
        and (place is None or m["town"] == place)


def masters(world, year: int, craft: str) -> list[tuple[str, float]]:
    """The seven masters of a craft at this year's Meet, and their scores (seeded)."""
    rng = rng_for(world.world_seed, f"meet:{year}:{craft}")
    out = []
    for _ in range(FIELD):
        surname, given = person_name(rng)
        out.append((f"{surname} {given}", round(rng.uniform(*MASTER_SCORES), 1)))
    return out


def score(world, person: int, craft: str, item_id: int) -> float:
    item = world.entity(item_id)
    if craft == "forging":
        return round(10 * item.data["grade"] + 10 * (FG.mastery(world, person, item.data["form"]) or 0.0), 1)
    return round(10 * item.data["grade"] + 10 * item.data.get("purity", 0.0), 1)


def fits(world, person: int, craft: str, item_id) -> bool:
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item_id not in world.targets(person, "owns") or item.data.get("used"):
        return False
    if craft == "forging":
        return item.kind == "gear" and item.data.get("forged_by") == person and not item.data.get("broken")
    return item.kind == "pill" and item.data.get("maker") == person


def enter_block(world, person: int, craft: str, item_id, place) -> str | None:
    if not is_open(world, place):
        return "The Meet is not held here now."
    if str(person) in current(world)["entries"].get(craft, {}):
        return "You have shown a piece in that craft already."
    if not fits(world, person, craft, item_id):
        return "Only a blade of your own forging, or a pill of your own refining, is shown."
    return None


def enter_events(world, person: int, craft: str, item_id: int, place) -> list[Event]:
    return [Event("meet_entered", (person,), place, {"craft": craft, "item": item_id,
                                                     "score": score(world, person, craft, item_id)})]


@effect("meet_entered")
def _entered(world, event) -> None:
    m = dict(current(world))
    entries = {k: dict(v) for k, v in m["entries"].items()}
    entries.setdefault(event.data["craft"], {})[str(event.actors[0])] = event.data["score"]
    world.set_meta("meet", {**m, "entries": entries})


def standings(world, craft: str) -> list[tuple[str, float, int | None]]:
    """(name, score, person or None) for the craft, best first."""
    m = current(world)
    rows = [(name, s, None) for name, s in masters(world, m["year"], craft)]
    rows += [(world.entity(int(p)).name, s, int(p)) for p, s in m["entries"].get(craft, {}).items()]
    return sorted(rows, key=lambda r: (-r[1], r[0]))


def decide_events(world) -> list[Event]:
    m = current(world)
    if m is None or m["decided"] or world.time < m["end"]:
        return []
    events = []
    for craft in CRAFTS:
        name, best, person = standings(world, craft)[0]
        events.append(Event("meet_decided", (person,) if person is not None else (), m["town"],
                            {"year": m["year"], "craft": craft, "name": name, "score": best,
                             "prize": PRIZE if person is not None else 0,
                             "title": f"champion of {WORDS[craft]} at the Meet of Hammer and Furnace, year {m['year']}"}))
    return events


@effect("meet_decided")
def _decided(world, event) -> None:
    d = event.data
    m = current(world)
    world.set_meta("meet", {**m, "decided": m["decided"] or d["craft"] == CRAFTS[-1]})
    if event.actors:
        champion = event.actors[0]
        world.update_data(champion, silver=silver_of(world, champion) + d["prize"],
                          titles=list(world.entity(champion).data.get("titles", [])) + [d["title"]])


@listen("meet_decided")
def _news(world, event, event_id: int) -> None:
    d = event.data
    subject = event.actors[0] if event.actors else event.place
    variant = make_variant("meet_won", event.actors[0] if event.actors else None, None,
                           place=place_name(world, event.place))
    variant.update(name=d["name"], craft=d["craft"], year=d["year"])
    record_fact(world, subject, "meet_won", None, place=event.place, source_event=event_id, weight=1.5, variant=variant)


def open_events(world, n: int) -> list[Event]:
    from systems.tournaments import host_city
    year = n // 4 + 1
    town = host_city(world, rng_for(world.world_seed, f"meet_host:{year}"))
    return [Event("meet_opened", (), town, {"year": year, "start": n * lives.SEASON,
                                            "end": n * lives.SEASON + DAYS * 4})]


@effect("meet_opened")
def _opened(world, event) -> None:
    d = event.data
    world.set_meta("meet", {"year": d["year"], "town": event.place, "start": d["start"], "end": d["end"],
                            "entries": {}, "decided": False})


def season_hook(world, n: int) -> list[Event]:
    """Each season the Meet that has closed is decided; each spring a new one opens."""
    commit(world, decide_events(world))
    return open_events(world, n) if n % 4 == 0 else []


world_clock.SEASON_HOOKS.append(season_hook)
