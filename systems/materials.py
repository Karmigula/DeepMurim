"""Materials and the forge (phase 5d spec 2): what gear is forged from, where it is had, and where it is worked.

A material is an item (`kind = "material"`): a `material` name of the table (`systems/data/materials.toml`) and its
`grade`. 4d's star iron counts as a material of grade 3 and stays a treasure (it still sells as one). A smith sells
iron and steel by the season, as 5a's stall sells gear; a slain beast gives its bones and, if strong, its core. Gear
is forged at one's own forge, at a smith's rented for the day, or at one's own sect's forge.
"""

import tomllib
from pathlib import Path

import systems.lives as lives
from systems.market import drift, event_factor
from systems.purse import silver_of
from systems.realms import realm_index
from world.events import Event, effect
from world.seed import rng_for

MATERIALS = tomllib.loads((Path(__file__).parent / "data" / "materials.toml").read_text(encoding="utf-8"))
STOCK = {"iron ingot": (3, 6), "black steel": (1, 3), "spirit iron": (0, 1)}
FORGE_PRICE, FORGE_RENT = 300, 30
CORE_REALM = 2
PARTS = ("bone", "core")


def make_material(world, name: str, owner: int | None, how: str = "found") -> int:
    item = world.add_entity("material", name, {"material": name, "grade": MATERIALS[name]["grade"], "how": how})
    if owner is not None:
        world.relate(owner, item, "owns")
    return item


def material_info(item) -> tuple[str, int] | None:
    """(name, grade) of a material: a forge's own, or 4d's star iron (spec 2)."""
    if item is None or item.data.get("used"):
        return None
    if item.kind == "material":
        return item.data["material"], item.data["grade"]
    if item.kind == "treasure" and item.data.get("kind") == "star_iron":
        return "star iron", MATERIALS["star iron"]["grade"]
    return None


def materials_of(world, person: int) -> list:
    return [e for e in (world.entity(i) for i in world.targets(person, "owns")) if material_info(e) is not None]


def spend(world, person: int, items) -> None:
    for item in items:
        world.unrelate(person, "owns", item)
        world.update_data(item, used=True)


# --- the smith's ore --------------------------------------------------------------------------------------

def stock(world, town: int) -> list[dict]:
    """This season's materials at the smith's: {key, material}, less what was bought."""
    kind = world.entity(town).data.get("kind")
    season = lives.current_season(world)
    rng = rng_for(world.world_seed, f"ore:{town}:{season}")
    out = []
    for name in sorted(STOCK):
        if kind not in MATERIALS[name]["sold"]:
            continue
        for n in range(rng.randint(*STOCK[name])):
            out.append({"key": f"{name}:{n}", "material": name})
    sold = (world.entity(town).data.get("ore_sold") or {}).get(str(season), [])
    return [o for o in out if o["key"] not in sold]


def price(world, town: int, name: str) -> int:
    return max(1, round(MATERIALS[name]["price"] * event_factor(world, town, "iron") * drift(world, town, "gear")))


def buy_block(world, person: int, town: int, key: str) -> str | None:
    offer = next((o for o in stock(world, town) if o["key"] == key), None)
    if offer is None:
        return "The smith has none of that now."
    if silver_of(world, person) < price(world, town, offer["material"]):
        return "You cannot pay for it."
    return None


def buy_events(world, person: int, town: int, key: str) -> list[Event]:
    offer = next(o for o in stock(world, town) if o["key"] == key)
    return [Event("material_bought", (person,), town, {**offer, "season": lives.current_season(world),
                                                        "price": price(world, town, offer["material"])})]


@effect("material_bought")
def _bought(world, event) -> None:
    person, town, d = event.actors[0], event.place, event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    sold = world.entity(town).data.get("ore_sold") or {}
    season = str(d["season"])
    world.update_data(town, ore_sold={season: sold.get(season, []) + [d["key"]]})  # only this season's list is kept
    make_material(world, d["material"], person, "bought")


# --- a slain beast ----------------------------------------------------------------------------------------

def parts_block(world, person: int, beast: int, part: str, place) -> str | None:
    entity = world.entity(beast) if isinstance(beast, int) else None
    if entity is None or not entity.data.get("beast") or not entity.data.get("dead") or part not in PARTS:
        return "There is nothing to take."
    if place not in world.targets(beast, "buried_at") + world.targets(beast, "located_in"):
        return "It is not here."
    if part in (entity.data.get("parts_taken") or []):
        return "That has been taken already."
    if part == "core" and realm_index(entity.data.get("realm", "mortal")) < CORE_REALM:
        return "It was too weak a beast to carry a core."
    return None


def parts_events(world, person: int, beast: int, part: str, place) -> list[Event]:
    return [Event("beast_parts_taken", (person, beast), place, {"part": part})]


@effect("beast_parts_taken")
def _parts(world, event) -> None:
    person, beast = event.actors
    part = event.data["part"]
    world.update_data(beast, parts_taken=(world.entity(beast).data.get("parts_taken") or []) + [part])
    make_material(world, f"beast {part}", person, "butchered")


# --- the forge --------------------------------------------------------------------------------------------

def forge_of(world, person: int) -> int | None:
    return next((i for i in world.targets(person, "owns") if world.entity(i).kind == "forge"
                 and not world.entity(i).data.get("cracked")), None)


def sect_forge(world, person: int, place) -> bool:
    """The player's own sect's forge, at its seat (3c's buildings)."""
    import systems.sect as sect_mod
    from systems.founding import my_sect
    sect = my_sect(world, person)
    return sect is not None and world.entity(sect).data.get("seat") == place and sect_mod.built(world, sect, "forge")


def rent(world, person: int, place) -> int:
    return 0 if forge_of(world, person) is not None or sect_forge(world, person, place) else FORGE_RENT


def forge_block(world, person: int, place) -> str | None:
    """One's own forge, one's own sect's, or a town smith's to rent."""
    if forge_of(world, person) is not None or sect_forge(world, person, place):
        return None
    if world.entity(place).kind != "town":
        return "You need a forge, or a town's smith to rent one."
    if silver_of(world, person) < FORGE_RENT:
        return f"The smith's forge costs {FORGE_RENT} silver for the day."
    return None


def buy_forge_block(world, person: int) -> str | None:
    if forge_of(world, person) is not None:
        return "You have a forge already."
    if silver_of(world, person) < FORGE_PRICE:
        return f"An anvil and a forge cost {FORGE_PRICE} silver."
    return None


def buy_forge_events(world, person: int, town: int) -> list[Event]:
    return [Event("forge_bought", (person,), town, {"price": FORGE_PRICE})]


@effect("forge_bought")
def _forge(world, event) -> None:
    person = event.actors[0]
    world.update_data(person, silver=silver_of(world, person) - event.data["price"])
    world.relate(person, world.add_entity("forge", "an anvil and a travelling forge", {"cracked": False}), "owns")
