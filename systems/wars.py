"""Clashes between hostile factions (phase 4a spec 3.2): who fights, who wins, what the loser loses."""

import systems.world_events as W
from systems import factions as F
from systems import halls
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from world.events import Event, effect, listen
from world.seed import rng_for

HOSTILE, WAR = -0.5, -0.8
CLASH_CHANCE, WAR_CHANCE = 0.2, 0.4
KILL_CHANCE, HALL_LOSS = 0.3, 0.5
POWER_LOSS, STANCE_HIT, MEND = 5, 0.05, 0.02


def clock_factions(world) -> list[int]:
    """Every faction the faction clock runs: materialized, not dissolved, not the player's own."""
    return [f.id for f in world.entities("faction")
            if not f.data.get("dissolved") and f.data.get("type") != "player_sect"]


def hall_towns(world, faction: int) -> list[int]:
    """Towns whose hall lists this faction (its seat and branches that still stand)."""
    data = world.entity(faction).data
    towns = {t for t in [data.get("seat"), *data.get("branches", [])] if t is not None}
    return sorted(t for t in towns if faction in halls.halls_here(world, t))


def stances(world, ids: list[int]) -> dict:
    """(a, b) -> stance for every stance relation among these factions, read once."""
    wanted = set(ids)
    return {(a, b): value for a in ids for b, value, _ in world.relations_from(a, "stance") if b in wanted}


def _power(world, faction: int) -> int:
    return int(world.entity(faction).data.get("power", 50))


def _where(world, a: int, b: int) -> tuple[int | None, bool]:
    shared = sorted(set(hall_towns(world, a)) & set(hall_towns(world, b)))
    if shared:
        return shared[0], False
    weaker = a if _power(world, a) <= _power(world, b) else b
    return world.entity(weaker).data.get("seat"), True


def _leader(world, person: int, faction: int) -> bool:
    return (F.membership(world, person, faction) or (0, {}))[1].get("role") == "leader"


def clash_boost(world, n: int) -> float:
    """A comet year stirs war (phase 4d). Read at the season's start: this season's own comets do not exist
    yet when its clashes are rolled, so every comet is caught by the next season's roll instead."""
    return W.factor(world, None, "clash", at=n * W.SEASON)


def clash_events(world, n: int) -> list[Event]:
    ids = clock_factions(world)
    known = stances(world, ids)
    events = []
    boost = clash_boost(world, n)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            value = known.get((a, b), 0.0)
            if value > HOSTILE:
                continue
            from systems.puppets import in_pocket  # phase 4h: a puppet's sect does not war on its patron
            if in_pocket(world, a, b):
                continue
            rng = rng_for(world.world_seed, f"world:{n}:clash:{a}:{b}")
            if rng.random() >= (WAR_CHANCE if value <= WAR else CLASH_CHANCE) * boost:
                continue
            town, abstract = _where(world, a, b)  # town is None when neither seat is settled yet: still a clash
            pa, pb = _power(world, a), _power(world, b)
            winner, loser = (a, b) if rng.random() < (pa / (pa + pb) if pa + pb else 0.5) else (b, a)
            killer = victim = None
            if town is not None and rng.random() < KILL_CHANCE:
                great = world.entity(loser).data["tier"] == "great"
                victims = sorted(p for p in halls.staff_at(world, loser, town) if not (great and _leader(world, p, loser)))
                seat = world.entity(winner).data.get("seat")
                killers = sorted(halls.staff_at(world, winner, town) or (halls.staff_at(world, winner, seat) if seat else []))
                if victims and killers:
                    victim, killer = rng.choice(victims), rng.choice(killers)
            lost = town is not None and not abstract and town != world.entity(loser).data.get("seat")                 and rng.random() < HALL_LOSS
            if victim is not None:  # the dead fall before the survivors of a lost hall are let go
                events.append(Event("died", (killer, victim), town, {"cause": "clash", "world": True}))
            events.append(Event("clash", (winner, loser), town, {"season": n, "hall_lost": lost, "abstract": abstract}))
    return events


def mend_events(world, n: int, clashed: set) -> list[Event]:
    """Pairs that did not clash drift back toward their founding stance (spec §3.2)."""
    ids = clock_factions(world)
    known = stances(world, ids)
    kinds = {f: world.entity(f).data["type"] for f in ids}
    changes = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if (a, b) in clashed:
                continue
            now = known.get((a, b), 0.0)
            base = F.base_stance(kinds[a], kinds[b])
            if abs(now - base) < 1e-9:
                continue
            step = min(MEND, abs(base - now))
            changes.append([a, b, round(now + step if base > now else now - step, 3)])
    return [Event("stances_mended", (), None, {"season": n, "changes": changes})] if changes else []


@effect("clash")
def _clash(world, event) -> None:
    winner, loser = event.actors
    world.update_data(loser, power=max(0, _power(world, loser) - POWER_LOSS))
    for x, y in ((winner, loser), (loser, winner)):
        world.relate(x, y, "stance", max(-1.0, round(F.stance(world, x, y) - STANCE_HIT, 3)))
    if event.data["hall_lost"]:
        town = event.place
        data = world.entity(town).data
        world.update_data(town, halls=[f for f in data.get("halls", []) if f != loser])
        world.update_data(loser, branches=[t for t in world.entity(loser).data.get("branches", []) if t != town])
        for person in halls.staff_at(world, loser, town):  # a lost hall's staff are let go where they stand
            set_membership(world, person, loser, status="released")


@effect("stances_mended")
def _mended(world, event) -> None:
    for a, b, value in event.data["changes"]:
        world.relate(a, b, "stance", value)
        world.relate(b, a, "stance", value)


@listen("clash")
def _clash_news(world, event, event_id: int) -> None:
    winner, loser = event.actors
    where = place_name(world, event.place)
    record_fact(world, winner, "clashed_with", loser, place=event.place, source_event=event_id, weight=1.5,
                variant=make_variant("clashed_with", winner, loser, place=where))
    if event.data["hall_lost"]:
        record_fact(world, loser, "lost_hall", winner, place=event.place, source_event=event_id, weight=2.0,
                    variant=make_variant("lost_hall", loser, winner, place=where))
