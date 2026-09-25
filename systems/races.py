"""Treasure races (phase 4d spec 5): a treasure appears, the nearby sects send champions, and the strongest claims it.

A treasure light or a star fall names its prize when it starts, calls its champions when it
is announced (they are named, not moved: plan ruling 7), and, if no one has claimed it when
it ends, lets the champions fight it out. While it is active the player can come to the site
and fight the champions one by one (`seek`); win them all and the prize is theirs.
"""

import systems.world_events as W
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.combat_core import INTENTS
from systems.duel import best_art, ensure_npc_arts, fighter_for
from systems.duel_sim import simulate
from systems.facts import make_variant, place_name, record_fact
from systems.founding import make_person
from systems.items import create_manual
from systems.purse import silver_of
from systems.realms import add_energy, realm_index
from systems.techniques import create_technique, generate
from world.events import Event, effect, listen
from world.seed import rng_for

RACE_KINDS = ("treasure_light", "star_fall")
RACE_RANGE = 2
CHAMPION_REALM = 2  # Second-rate
WANDERER_CHANCE, MAX_WANDERERS = 0.3, 2
MAX_CHAMPIONS = 6  # the strongest few; an old world has dozens of sects in reach
PILLS = ("Heaven-and-Earth Pill", "Nine-Turn Golden Pill", "Marrow-Washing Pill", "Purple Cloud Pill")
HERBS = ("thousand-year ginseng", "blood lotus", "snow lingzhi", "dragon-bone moss")


def prize_for(kind: str, rng) -> dict:
    if kind == "star_fall":
        return {"kind": "star_iron", "name": "a lump of star iron", "value": rng.randint(400, 900)}
    what = rng.choice(("manual", "pill", "herb"))
    if what == "manual":
        return {"kind": "manual", "grade": rng.randint(2, 3), "completeness": round(rng.uniform(0.6, 1.0), 2)}
    if what == "pill":
        years = round(rng.uniform(1.0, 3.0), 2)
        return {"kind": "pill", "name": f"a {rng.choice(PILLS)}", "qi_years": years, "value": int(150 * years)}
    return {"kind": "herb", "name": f"a {rng.choice(HERBS)}", "value": rng.randint(200, 600)}


def race_start_data(kind: str, rng) -> dict:
    return {"prize": prize_for(kind, rng), "champions": [], "beaten": [], "out": [], "claimed": None, "item": None}


def race_stage(world, occurrence, stage: str) -> list[Event]:
    if stage == "announced":
        return [Event("race_called", (), occurrence.data["place"],
                      {"occurrence": occurrence.id, "champions": champions(world, occurrence)})]
    if stage == "over":
        return contest_events(world, occurrence)
    return []


def champions(world, occurrence) -> list[int]:
    """Each staffed faction within reach sends its strongest; wanderers may come too. Strongest first."""
    d = occurrence.data
    found = []
    for faction in world.entities("faction"):
        fd = faction.data
        if fd.get("type") not in F.STAFFED or fd.get("type") == "player_sect" or fd.get("dissolved") or "home" not in fd:
            continue
        if max(abs(fd["home"][0] - d["x"]), abs(fd["home"][1] - d["y"])) > RACE_RANGE:
            continue
        able = [world.entity(p) for p, _, d in world.relations_to(faction.id, "member_of")  # one query (4e soak)
                if d.get("status", "member") == "member" and d.get("role") not in (None, "member")]
        able = [p for p in able if p is not None and not p.data.get("dead") and not p.data.get("is_player")
                and realm_index(p.data.get("realm", "mortal")) >= CHAMPION_REALM]
        if able:
            found.append(max(able, key=lambda p: (realm_index(p.data["realm"]), -p.id)).id)
    rng = rng_for(world.world_seed, f"race:{occurrence.id}:wanderers")
    for i in range(MAX_WANDERERS):
        if rng.random() < WANDERER_CHANCE:
            found.append(make_person(world, f"race:{occurrence.id}:wanderer:{i}", d["place"],
                                     occupation="wandering swordsman", age=rng.randint(25, 55),
                                     realm=rng.choice(("second-rate", "first-rate"))))
    unique = sorted(set(found), key=lambda p: (-realm_index(world.entity(p).data.get("realm", "mortal")), p))
    return unique[:MAX_CHAMPIONS]


@effect("race_called")
def _called(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "champions": event.data["champions"]})


def _wins(world, a: int, b: int, rng) -> bool:
    for person in (a, b):
        ensure_npc_arts(world, person)
    mine, theirs = best_art(world, a), best_art(world, b)
    result, _ = simulate(fighter_for(world, a, mine.technique.id if mine else None),
                         fighter_for(world, b, theirs.technique.id if theirs else None),
                         lambda r, history: r.choice(INTENTS), rng)
    return result != "npc"  # a draw leaves the holder standing


def contest_events(world, occurrence) -> list[Event]:
    """When the light fades unclaimed, the champions fight in turn; the last one standing takes it."""
    race = occurrence.data["data"]
    if race["claimed"] is not None:
        return []
    alive = [c for c in race["champions"] if not world.entity(c).data.get("dead")]
    if not alive:
        return []
    rng = rng_for(world.world_seed, f"race:{occurrence.id}:contest")
    winner = alive[0]
    for other in alive[1:]:
        if not _wins(world, winner, other, rng):
            winner = other
    return claim_events(world, occurrence.id, winner, occurrence.data["place"])


def claim_events(world, occurrence_id: int, winner: int, place: int) -> list[Event]:
    race = world.entity(occurrence_id).data["data"]
    if race["claimed"] is not None:
        return []
    return [Event("treasure_claimed", (winner,), place, {"occurrence": occurrence_id, "prize": race["prize"]})]


def make_prize(world, owner: int, prize: dict, occurrence_id: int) -> int:
    """The prize as an item owned by `owner`: a 2b manual, or a treasure (plan ruling 11)."""
    if prize["kind"] == "manual":
        name, data = generate(rng_for(world.world_seed, f"prize:{occurrence_id}"), "martial", grade=prize["grade"])
        return create_manual(world, owner, create_technique(world, name, data), prize["completeness"], claimed=1.0)
    item = world.add_entity("treasure", prize["name"], {**{k: v for k, v in prize.items() if k != "name"}, "used": False})
    world.relate(owner, item, "owns")
    return item


@effect("treasure_claimed")
def _claimed(world, event) -> None:
    winner, d = event.actors[0], event.data
    occurrence = world.entity(d["occurrence"])
    race = occurrence.data["data"]
    if race["claimed"] is not None:
        raise ValueError(f"the prize of occurrence #{occurrence.id} was already claimed")
    item = make_prize(world, winner, d["prize"], occurrence.id)
    world.update_data(occurrence.id, data={**race, "claimed": winner, "item": item})


@listen("treasure_claimed")
def _claimed_news(world, event, event_id: int) -> None:
    winner = world.entity(event.actors[0])
    variant = make_variant("treasure", winner.id, None, place=place_name(world, event.place),
                           realm=winner.data.get("realm"))
    variant.update(prize=event.data["prize"]["kind"], age=int(winner.data.get("age", 20)))
    record_fact(world, winner.id, "treasure", None, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


# --- the player at the race ---------------------------------------------------------------

def _active_races(world) -> list[list]:
    return [row for row in W.index(world)
            if row[W.TYPE] in RACE_KINDS and row[W.ACTIVE_FROM] <= world.time < row[W.ACTIVE_TO]
            and world.entity(row[W.ID]).data["data"]["claimed"] is None]


def race_here(world, town: int) -> int | None:
    return next((row[W.ID] for row in _active_races(world) if row[W.PLACE] == town), None)


def races_near(world, town: int) -> list[tuple[int, int]]:
    """(occurrence, regions away) for every unclaimed treasure light within reach of this town."""
    here = W.place_xy(world, town)
    found = []
    for row in _active_races(world):
        distance = max(abs(row[W.X] - here[0]), abs(row[W.Y] - here[1]))
        if distance <= RACE_RANGE:
            found.append((row[W.ID], distance))
    return sorted(found, key=lambda p: (p[1], p[0]))


def next_champion(world, occurrence_id: int, player: int) -> int | None:
    """The weakest champion the player has not yet beaten (they face the lowest first)."""
    race = world.entity(occurrence_id).data["data"]
    left = [c for c in race["champions"] if c not in race["beaten"] and not world.entity(c).data.get("dead")]
    return left[-1] if left else None


@effect("race_fought")
def _fought(world, event) -> None:
    player, champion = event.actors
    occurrence = world.entity(event.data["occurrence"])
    race = dict(occurrence.data["data"])
    if event.data["won"]:
        race["beaten"] = race["beaten"] + [champion]
    else:
        race["out"] = race["out"] + [player]
    world.update_data(occurrence.id, data=race)


# --- treasures ----------------------------------------------------------------------------

def swallow_events(world, player: int, place: int, item: int) -> list[Event]:
    return [Event("swallowed", (player,), place, {"item": item, "qi_years": world.entity(item).data["qi_years"]})]


@effect("swallowed")
def _swallowed(world, event) -> None:
    player, item = event.actors[0], event.data["item"]
    body = load_body(world, player)
    add_energy(body, event.data["qi_years"])
    save_body(world, player, body)
    world.unrelate(player, "owns", item)
    world.update_data(item, used=True)


def sell_events(world, player: int, town: int, item: int) -> list[Event]:
    return [Event("sold_treasure", (player,), town, {"item": item, "silver": world.entity(item).data["value"]})]


@effect("sold_treasure")
def _sold(world, event) -> None:
    player, town, item = event.actors[0], event.place, event.data["item"]
    world.update_data(player, silver=silver_of(world, player) + event.data["silver"])
    world.unrelate(player, "owns", item)
    world.relate(town, item, "owns")
