"""A sect's pill hall and herb garden (phase 5c spec 2): drawn from for merit, restocked, grown and harvested.

The hall is a table of pills by grade and effect, seeded by `pill_hall:{sect}`; a pill is made only when drawn,
and the member keeps it. A great sect stocks grades 1-3, any other 1-2; bandit forts keep no hall. Each spring
the table is its seed again. The garden is a few herbs of the seat's land, each a count that grows each season
and now and then ages a grade. Both are numbers until someone takes from them, and are read without writing:
what a season added is worked out from the seed when asked, and stored only when something is taken.
The player's own sect builds its garden and hall (3c): its hall is filled by its alchemist disciples.
"""

import math

import systems.alchemy as A
import systems.herbs as H
import systems.lives as lives
import systems.world_clock as world_clock
from systems import factions as F
from systems.membership import set_membership
from world.events import Event, effect
from world.gen.materialize import region_of
from world.seed import rng_for

SEED = {"great": {1: 6, 2: 4, 3: 2}, "other": {1: 4, 2: 2}}
EFFECTS = ("qi", "healing", "antidote", "bottleneck")
BASES = {"qi": "earth_qi", "healing": "wood_healing", "antidote": "metal_antidote", "bottleneck": "bottleneck"}
NO_HALL = frozenset({"bandit_fort"})
PURITY = 0.7
DRAW_MERIT = 20            # merit per grade
RANK_GRADE = {1: 1, 2: 2}  # rank 1 draws grade 1, rank 2 grade 2; an elder grade 3
ELDER_GRADE = 3
GARDEN_HERBS = (3, 6)
GARDEN_START = (2, 6)
GROWTH, GARDEN_CAP = 2, 12
AGE_CHANCE, TOP_AGE = 0.01, 2  # to "a hundred years" at most
LOOK_BACK = 40             # seasons of ageing weighed on a read; older ones are long settled
HARVEST_LIMIT = 2
HARVEST_MERIT = 5          # merit per grade + 1
OWN_HALL_CAP = 12          # the player's own hall holds at most this many pills of a grade
OWN_HALL_SEASONS = 12      # seasons of filling weighed on a read
ALCHEMIST_JOBS = frozenset({"herbalist"})


def _tier(world, faction: int) -> str:
    return "great" if world.entity(faction).data.get("tier") == "great" else "other"


def own(world, faction: int) -> bool:
    return world.entity(faction).data.get("type") == "player_sect"


def _built(world, faction: int, name: str) -> bool:
    import systems.sect as sect_mod
    return sect_mod.built(world, faction, name)


def keeps_hall(world, faction: int) -> bool:
    data = world.entity(faction).data
    if data.get("dissolved"):
        return False
    if own(world, faction):
        return _built(world, faction, "pill_hall")
    return data.get("type") in F.STAFFED and data.get("type") not in NO_HALL


def keeps_garden(world, faction: int) -> bool:
    data = world.entity(faction).data
    if data.get("dissolved") or data.get("seat") is None:
        return False
    if own(world, faction):
        return _built(world, faction, "herb_garden")
    return data.get("type") in F.STAFFED and data.get("type") not in NO_HALL


# --- the hall ----------------------------------------------------------------------------------------------

def _key(grade: int, kind: str) -> str:
    return f"{grade}:{kind}"


def seed_of(world, faction: int) -> dict[str, int]:
    """The hall as it stands each spring: {"grade:effect": count}."""
    if own(world, faction):
        return {}
    rng = rng_for(world.world_seed, f"pill_hall:{faction}")
    out: dict[str, int] = {}
    for grade, count in sorted(SEED[_tier(world, faction)].items()):
        for _ in range(count):
            key = _key(grade, rng.choice(EFFECTS))
            out[key] = out.get(key, 0) + 1
    return out


def alchemists(world, faction: int) -> list[int]:
    """The own sect's disciples who refine: herbalists by trade, or those with a Guild rank."""
    import systems.sect as sect_mod
    return [p for p in sect_mod.members(world, faction)
            if world.entity(p).data.get("occupation") in ALCHEMIST_JOBS or world.entity(p).data.get("guild_rank")]


def _filled(world, faction: int, stored: dict, since: int) -> dict[str, int]:
    """The own sect's hall brought forward: each alchemist adds 1-3 pills a season of grade ceil(rank / 2)."""
    now = lives.current_season(world)
    out = dict(stored)
    makers = alchemists(world, faction)
    for n in range(max(since, now - OWN_HALL_SEASONS) + 1, now + 1):
        for person in makers:
            rng = rng_for(world.world_seed, f"own_hall:{faction}:{n}:{person}")
            grade = max(1, math.ceil((world.entity(person).data.get("guild_rank") or 1) / 2))
            key = _key(min(5, grade), rng.choice(EFFECTS))
            held = sum(v for k, v in out.items() if k.startswith(f"{min(5, grade)}:"))
            out[key] = out.get(key, 0) + max(0, min(rng.randint(1, 3), OWN_HALL_CAP - held))
    return {k: v for k, v in out.items() if v > 0}


def table(world, faction: int) -> dict[str, int]:
    """What the hall holds now (read, never written)."""
    data = world.entity(faction).data
    stored = data.get("pill_hall")
    if own(world, faction):
        built = (data.get("buildings") or {}).get("pill_hall") or {}
        since = (data.get("pill_hall_at") if stored is not None else None)
        if since is None:
            since = built.get("done_at", world.time) // lives.SEASON
        return _filled(world, faction, stored or {}, since) if keeps_hall(world, faction) else {}
    return dict(stored) if stored is not None else seed_of(world, faction)


def best_grade(world, person: int, faction: int) -> int | None:
    """The highest grade this member may draw, or None."""
    found = F.membership(world, person, faction)
    if found is None:
        return None
    rank, data = found
    if data.get("status", "member") != "member":
        return None
    if data.get("role") in ("elder", "leader"):
        return ELDER_GRADE if not own(world, faction) else 5
    return RANK_GRADE.get(min(rank, 2))


def cost(world, faction: int, grade: int) -> int:
    return 0 if own(world, faction) else DRAW_MERIT * grade


def _merit(world, person: int, faction: int) -> int:
    return F.membership(world, person, faction)[1].get("merit", 0)


def offers(world, person: int, faction: int) -> list[tuple[int, str]]:
    """(grade, effect) this member could draw now, strongest first."""
    best = best_grade(world, person, faction)
    if best is None or not keeps_hall(world, faction):
        return []
    out = []
    for key, count in table(world, faction).items():
        grade, kind = key.split(":")
        if count > 0 and int(grade) <= best:
            out.append((int(grade), kind))
    return sorted(out, key=lambda o: (-o[0], o[1]))


def draw_block(world, person: int, faction: int, grade: int, kind: str, place) -> str | None:
    if world.entity(faction).data.get("seat") != place or not keeps_hall(world, faction):
        return "The pill hall is at the sect's seat."
    best = best_grade(world, person, faction)
    if best is None:
        return "Only a disciple of rank may draw from the pill hall."
    if grade > best:
        return "Your rank does not reach that grade."
    if table(world, faction).get(_key(grade, kind), 0) <= 0:
        return "The hall has none of those left."
    if _merit(world, person, faction) < cost(world, faction, grade):
        return f"That costs {cost(world, faction, grade)} merit."
    return None


def draw_events(world, person: int, faction: int, grade: int, kind: str, place) -> list[Event]:
    return [Event("pill_drawn", (person,), place, {"faction": faction, "grade": grade, "effect": kind,
                                                   "merit": cost(world, faction, grade),
                                                   "season": lives.current_season(world)})]


@effect("pill_drawn")
def _drawn(world, event) -> None:
    person, d = event.actors[0], event.data
    stocked = table(world, d["faction"])
    key = _key(d["grade"], d["effect"])
    stocked[key] = stocked.get(key, 0) - 1
    world.update_data(d["faction"], pill_hall={k: v for k, v in stocked.items() if v > 0}, pill_hall_at=d["season"])
    if d["merit"]:
        set_membership(world, person, d["faction"], merit=_merit(world, person, d["faction"]) - d["merit"])
    make_hall_pill(world, person, d["faction"], d["grade"], d["effect"], "drawn")


def make_hall_pill(world, person: int, faction: int, grade: int, kind: str, how: str) -> int:
    """A pill out of a sect's hall, made as it leaves (drawn, or stolen)."""
    pill = A.make_pill(world, person, A.recipe_entity(world, BASES[kind]), grade, PURITY)
    world.update_data(pill, maker=faction, how=how)
    return pill


def season_hook(world, n: int) -> list:
    """Each spring a drawn-from hall is its seed again (spec 2.1); the own sect's hall is filled, not restocked."""
    if n % 4:
        return []
    for faction in world.entities_after("faction", "pill_hall", 0):
        if not own(world, faction.id):
            world.update_data(faction.id, pill_hall=None)
    return []


world_clock.SEASON_HOOKS.append(season_hook)


# --- the garden ----------------------------------------------------------------------------------------------

def _terrain(world, faction: int) -> str | None:
    seat = world.entity(faction).data.get("seat")
    return region_of(world, seat).data["terrain"] if seat is not None else None


def garden_seed(world, faction: int) -> dict[str, list[int]]:
    """The garden as first planted: {herb: [count, grade]}."""
    terrain = _terrain(world, faction)
    growing = H.growing(terrain) if terrain else []
    if not growing:
        return {}
    rng = rng_for(world.world_seed, f"garden:{faction}")
    names = rng.sample(growing, min(len(growing), rng.randint(*GARDEN_HERBS)))
    return {name: [rng.randint(*GARDEN_START), 1 if rng.random() < 0.1 else 0] for name in sorted(names)}


def _planted(world, faction: int) -> int:
    """The season the garden was first planted: the own sect's when built, any other's when the sect arose."""
    entity = world.entity(faction)
    if own(world, faction):
        return ((entity.data.get("buildings") or {}).get("herb_garden") or {}).get("done_at", world.time) // lives.SEASON
    return entity.created_at // lives.SEASON


def garden(world, faction: int) -> dict[str, list[int]]:
    """What grows now: {herb: [count, grade]}, brought forward from the last harvest (read, never written)."""
    if not keeps_garden(world, faction):
        return {}
    stored = world.entity(faction).data.get("garden")
    herbs = {k: list(v) for k, v in (stored["herbs"] if stored else garden_seed(world, faction)).items()}
    since = stored["at"] if stored else _planted(world, faction)
    now = lives.current_season(world)
    seasons = max(0, now - since)
    for name, (count, grade) in herbs.items():
        for n in range(max(since, now - LOOK_BACK) + 1, now + 1):
            if grade < TOP_AGE and rng_for(world.world_seed, f"garden:{faction}:{name}:{n}").random() < AGE_CHANCE:
                grade += 1
        herbs[name] = [min(GARDEN_CAP, count + GROWTH * seasons), grade]
    return herbs


def guarded(world, faction: int) -> bool:
    """A garden holding a hundred-year herb keeps a guardian beast (spec 2.4)."""
    return any(grade >= TOP_AGE and count > 0 for count, grade in garden(world, faction).values())


def taken_this_season(world, person: int, faction: int) -> int:
    found = (world.entity(person).data.get("harvested") or {}).get(str(faction))
    return found["count"] if found and found["season"] == lives.current_season(world) else 0


def harvest_cost(world, faction: int, grade: int) -> int:
    return 0 if own(world, faction) else HARVEST_MERIT * (grade + 1)


def harvest_block(world, person: int, faction: int, herb: str, place) -> str | None:
    if world.entity(faction).data.get("seat") != place or not keeps_garden(world, faction):
        return "The herb garden is at the sect's seat."
    found = F.membership(world, person, faction)
    if found is None or found[1].get("status", "member") != "member":
        return "Only the sect's own may take from its garden."
    if taken_this_season(world, person, faction) >= HARVEST_LIMIT:
        return f"You may take only {HARVEST_LIMIT} herbs a season."
    growing = garden(world, faction).get(herb)
    if not growing or growing[0] <= 0:
        return "None of that grows there now."
    if _merit(world, person, faction) < harvest_cost(world, faction, growing[1]):
        return f"That costs {harvest_cost(world, faction, growing[1])} merit."
    return None


def harvest_events(world, person: int, faction: int, herb: str, place) -> list[Event]:
    grade = garden(world, faction)[herb][1]
    return [Event("garden_harvested", (person,), place, {"faction": faction, "herb": herb, "grade": grade,
                                                          "merit": harvest_cost(world, faction, grade),
                                                          "season": lives.current_season(world)})]


def take_from_garden(world, faction: int, herb: str, season: int) -> None:
    """One herb less, and the garden as it stands now remembered (a harvest, a theft)."""
    herbs = garden(world, faction)
    herbs[herb][0] = max(0, herbs[herb][0] - 1)
    world.update_data(faction, garden={"at": season, "herbs": herbs})


@effect("garden_harvested")
def _harvested(world, event) -> None:
    person, d = event.actors[0], event.data
    take_from_garden(world, d["faction"], d["herb"], d["season"])
    taken = dict(world.entity(person).data.get("harvested") or {})
    before = taken.get(str(d["faction"]))
    count = before["count"] if before and before["season"] == d["season"] else 0
    taken[str(d["faction"])] = {"season": d["season"], "count": count + 1}
    world.update_data(person, harvested=taken)
    if d["merit"]:
        set_membership(world, person, d["faction"], merit=_merit(world, person, d["faction"]) - d["merit"])
    H.make_herb(world, d["herb"], d["grade"], person, "harvested")
