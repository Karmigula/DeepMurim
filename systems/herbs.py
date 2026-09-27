"""Herbs (phase 5b spec 2): named plants of fixed properties, known by tasting, gathered, bought and won.

A herb is an entity (`kind = "herb"`): its table `name` and a `grade` of age (a year, ten, a hundred, a thousand).
Its properties belong to the name (`systems/data/herbs.toml`). The player sees them only once known: their
`herb_lore` lists the names they have tasted or used.
"""

import tomllib
from pathlib import Path

import systems.lives as lives
import systems.toxins as toxins
from systems.market import drift, event_factor
from systems.purse import silver_of
from world.events import Event, effect
from world.gen.materialize import region_of
from world.seed import rng_for

HERBS = tomllib.loads((Path(__file__).parent / "data" / "herbs.toml").read_text(encoding="utf-8"))
AGES = ("a year", "ten years", "a hundred years", "a thousand years")
AGE_PRICE = (1, 4, 20, 200)
TASTE_POISON_AT = 3        # toxicity at which tasting poisons
GATHER_BASE, GATHER_TRIES = 0.35, 2
GATHER_GRADES = (0.70, 0.25, 0.05)
GUARD_CHANCE = 0.5
GATHER_WATCHES = 2
STOCK = (4, 8)
LACKED = 1.5               # a herb that does not grow in the region costs this much more
FURNACE_PRICE, FURNACE_RENT = 200, 20


def props(name: str) -> dict:
    return HERBS[name]


def herb_name(name: str, grade: int) -> str:
    return f"{name} ({AGES[grade]})"


def make_herb(world, name: str, grade: int, owner: int | None, how: str = "found") -> int:
    item = world.add_entity("herb", herb_name(name, grade), {"herb": name, "grade": grade, "how": how})
    if owner is not None:
        world.relate(owner, item, "owns")
    return item


def herb_info(item) -> tuple[str, int] | None:
    """(name, grade) of a herb of the table: a gathered or bought herb, or a treasure race's herb (spec 2.3)."""
    if item is None or item.data.get("used"):
        return None
    if item.kind == "herb":
        return item.data["herb"], item.data["grade"]
    if item.kind == "treasure" and item.data.get("kind") == "herb":
        return prize_herb(item.name)
    return None


def herbs_of(world, person: int) -> list:
    return [e for e in (world.entity(i) for i in world.targets(person, "owns")) if herb_info(e) is not None]


def known(world, person: int, name: str) -> bool:
    return name in (world.entity(person).data.get("herb_lore") or [])


def learn(world, person: int, names) -> None:
    lore = list(world.entity(person).data.get("herb_lore") or [])
    new = [n for n in names if n not in lore]
    if new:
        world.update_data(person, herb_lore=lore + new)


def spend(world, person: int, items) -> None:
    for item in items:
        world.unrelate(person, "owns", item)
        world.update_data(item, used=True)


# --- tasting ---------------------------------------------------------------------------------------------

def taste_block(world, person: int, item_id: int) -> str | None:
    if herb_info(world.entity(item_id)) is None or item_id not in world.targets(person, "owns"):
        return "You have no such herb."
    return None


def taste_events(world, person: int, item_id: int, place) -> list[Event]:
    name = herb_info(world.entity(item_id))[0]
    return [Event("herb_tasted", (person,), place, {"item": item_id, "herb": name,
                                                     "toxicity": props(name)["toxicity"]})]


@effect("herb_tasted")
def _tasted(world, event) -> None:
    person, d = event.actors[0], event.data
    learn(world, person, [d["herb"]])
    spend(world, person, [d["item"]])
    if d["toxicity"] >= TASTE_POISON_AT:
        toxins.poison(world, person, d["toxicity"], d["toxicity"] * 2, f"tasting {d['herb']}")


# --- gathering -------------------------------------------------------------------------------------------

def growing(terrain: str) -> list[str]:
    return sorted(n for n, h in HERBS.items() if terrain in h["terrains"])


def gather_block(world, person: int, place: int) -> str | None:
    if world.entity(place).kind != "town":
        return "There is nothing to gather here."
    return None


def gather_events(world, person: int, place: int) -> list[Event]:
    """Half a day in the town's surroundings: 0-2 herbs of the land, one perhaps guarded (spec 2.3)."""
    from systems.bodies import load_body
    rng = rng_for(world.world_seed, f"gather:{person}:{world.time}")
    terrain = region_of(world, place).data["terrain"]
    insight = load_body(world, person).insight
    found = []
    for _ in range(GATHER_TRIES):
        if rng.random() < GATHER_BASE + min(0.3, insight / 200):
            roll = rng.random()
            grade = 0 if roll < GATHER_GRADES[0] else 1 if roll < GATHER_GRADES[0] + GATHER_GRADES[1] else 2
            found.append({"herb": rng.choice(growing(terrain)), "grade": grade})
    guarded = any(f["grade"] == 2 for f in found) and rng.random() < GUARD_CHANCE
    return [Event("herbs_gathered", (person,), place, {"found": found, "guarded": guarded,
                                                       "watches": GATHER_WATCHES})]


@effect("herbs_gathered")
def _gathered(world, event) -> None:
    for f in event.data["found"]:
        make_herb(world, f["herb"], f["grade"], event.actors[0], "gathered")
    from systems.time import advance
    advance(world, event.data["watches"])


# --- the herbalist ----------------------------------------------------------------------------------------

def stock(world, town: int) -> list[dict]:
    """This season's herbs at the herbalist's: {key, herb, grade}, less what was bought."""
    season = lives.current_season(world)
    rng = rng_for(world.world_seed, f"herbalist:{town}:{season}")
    terrain = region_of(world, town).data["terrain"]
    local, others = growing(terrain), sorted(set(HERBS) - set(growing(terrain)))
    out = []
    for n in range(rng.randint(*STOCK)):
        pool = local if rng.random() < 0.75 else others
        out.append({"key": f"h{n}", "herb": rng.choice(pool), "grade": 1 if rng.random() < 0.2 else 0})
    sold = (world.entity(town).data.get("herbs_sold") or {}).get(str(season), [])
    return [o for o in out if o["key"] not in sold]


def price(world, town: int, name: str, grade: int) -> int:
    terrain = region_of(world, town).data["terrain"]
    factor = 1.0 if terrain in props(name)["terrains"] else LACKED
    return max(1, round(props(name)["price"] * AGE_PRICE[grade] * factor * event_factor(world, town, "herbs")
                        * drift(world, town, "herbs")))


def buy_block(world, person: int, town: int, key: str) -> str | None:
    offer = next((o for o in stock(world, town) if o["key"] == key), None)
    if offer is None:
        return "The herbalist has nothing like that now."
    if silver_of(world, person) < price(world, town, offer["herb"], offer["grade"]):
        return "You cannot pay for it."
    return None


def buy_events(world, person: int, town: int, key: str) -> list[Event]:
    offer = next(o for o in stock(world, town) if o["key"] == key)
    return [Event("herb_bought", (person,), town, {**offer, "season": lives.current_season(world),
                                                    "price": price(world, town, offer["herb"], offer["grade"])})]


@effect("herb_bought")
def _bought(world, event) -> None:
    person, town, d = event.actors[0], event.place, event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    sold = world.entity(town).data.get("herbs_sold") or {}
    season = str(d["season"])
    world.update_data(town, herbs_sold={season: sold.get(season, []) + [d["key"]]})
    make_herb(world, d["herb"], d["grade"], person, "bought")


def furnace_of(world, person: int) -> int | None:
    return next((i for i in world.targets(person, "owns") if world.entity(i).kind == "furnace"
                 and not world.entity(i).data.get("cracked")), None)


def furnace_block(world, person: int) -> str | None:
    if furnace_of(world, person) is not None:
        return "You have a furnace already."
    if silver_of(world, person) < FURNACE_PRICE:
        return f"A furnace costs {FURNACE_PRICE} silver."
    return None


def furnace_events(world, person: int, town: int) -> list[Event]:
    return [Event("furnace_bought", (person,), town, {"price": FURNACE_PRICE})]


@effect("furnace_bought")
def _furnace(world, event) -> None:
    person = event.actors[0]
    world.update_data(person, silver=silver_of(world, person) - event.data["price"])
    item = world.add_entity("furnace", "a bronze furnace", {"cracked": False})
    world.relate(person, item, "owns")


# --- legendary herbs ---------------------------------------------------------------------------------------

def prize_herb(prize_name: str) -> tuple[str, int]:
    """A treasure race's herb as a herb of the table (spec 2.3): a thousand years old, or a hundred."""
    name = prize_name.removeprefix("a ").removeprefix("an ")
    grade = 3 if name.startswith("thousand-year ") else 2
    name = name.removeprefix("thousand-year ")
    return (name if name in HERBS else "ginseng"), grade
