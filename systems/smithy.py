"""The smith's stall (phase 5a spec 4.1): seasonal stock capped by the town's size, bought and sold for silver.

A stall's stock is only a seeded list (`stock`) until something is bought: then that offer becomes an item made
by the town's smith. Gear sells back at half its price; a famous weapon only to a rich buyer in a city.
"""

import systems.gear as gear
import systems.lives as lives
from systems import factions as F
from systems.market import drift, event_factor
from systems.purse import silver_of
from world.events import Event, effect
from world.gen.materialize import people_at
from world.seed import rng_for

BASE = (20, 60, 250, 1000, 4000)  # silver by grade: iron, fine, spirit (and what a buyer pays for more)
ARMOUR_PRICE = 0.8
CAPS = {"village": 0, "town": 1, "city": 2}
SELL_SHARE = 0.5
FAMOUS_PRICE = 20
WEAPONS, ARMOURS = (3, 6), (1, 3)
SMITH_NAMES = ("Iron-Arm", "Old", "Red-Faced", "One-Eyed", "Quiet", "Hammer")


def cap(world, town: int) -> int:
    from systems.craft_world import stall_lift  # phase 5d: a master smith lifts the stall a grade
    return min(4, CAPS.get(world.entity(town).data.get("kind"), 0) + stall_lift(world, town))


def _forms(world, town: int) -> list[str]:
    """The weapon forms of the factions nearest this town, else every form."""
    here = world.entity(town).data
    near = sorted(F.ensure_roster(world), key=lambda f: (F.gap(world.entity(f).data["home"], (here["x"], here["y"])), f))
    forms = [f for fid in near[:3] for f in F.FAVOURED.get(world.entity(fid).data["type"], ()) if f in gear.WEAPON_FORMS]
    return sorted(set(forms)) or list(gear.WEAPON_FORMS)


def stock(world, town: int) -> list[dict]:
    """This season's offers: {key, slot, form, grade}, less what has been bought."""
    season = lives.current_season(world)
    rng = rng_for(world.world_seed, f"smith:{town}:{season}")
    top, forms, out = cap(world, town), _forms(world, town), []
    for n in range(rng.randint(*WEAPONS)):
        out.append({"key": f"w{n}", "slot": "weapon", "form": rng.choice(forms), "grade": rng.randint(0, top)})
    for n in range(rng.randint(*ARMOURS)):
        out.append({"key": f"a{n}", "slot": "armour", "form": rng.choice(gear.ARMOURS), "grade": rng.randint(0, top)})
    sold = (world.entity(town).data.get("smith_sold") or {}).get(str(season), [])
    return [o for o in out if o["key"] not in sold]


def price(world, town: int, slot: str, grade: int) -> int:
    base = BASE[grade] * (ARMOUR_PRICE if slot == "armour" else 1.0)
    return max(1, round(base * event_factor(world, town, "iron") * drift(world, town, "gear")))  # iron's dearness


def buy_block(world, player: int, town: int, key: str) -> str | None:
    offer = next((o for o in stock(world, town) if o["key"] == key), None)
    if offer is None:
        return "The smith has nothing like that now."
    if silver_of(world, player) < price(world, town, offer["slot"], offer["grade"]):
        return "You cannot pay for it."
    return None


def buy_events(world, player: int, town: int, key: str) -> list[Event]:
    offer = next(o for o in stock(world, town) if o["key"] == key)
    return [Event("gear_bought", (player,), town, {**offer, "season": lives.current_season(world),
                                                    "price": price(world, town, offer["slot"], offer["grade"])})]


def smith_name(world, town: int) -> str:
    rng = rng_for(world.world_seed, f"smith:{town}:name")
    return f"{rng.choice(SMITH_NAMES)} smith of {world.entity(town).name}"


@effect("gear_bought")
def _bought(world, event) -> None:
    player, town, d = event.actors[0], event.place, event.data
    world.update_data(player, silver=silver_of(world, player) - d["price"])
    sold = dict(world.entity(town).data.get("smith_sold") or {})
    season = str(d["season"])
    sold = {season: sold.get(season, []) + [d["key"]]}  # only this season's list is kept
    world.update_data(town, smith_sold=sold)
    gear.make_item(world, d["slot"], d["form"], d["grade"], player, "bought", maker=smith_name(world, town))


def sell_price(world, town: int, item_id: int) -> int:
    item = world.entity(item_id)
    base = price(world, town, item.data["slot"], item.data["grade"])
    if item.data.get("famous"):
        return base * FAMOUS_PRICE
    return max(1, int(base * SELL_SHARE * (0.2 if item.data.get("broken") else 1.0)))


def buyer_for(world, town: int, player: int) -> int | None:
    """Who in a city can pay for a famous blade: its merchants."""
    if world.entity(town).data.get("kind") != "city":
        return None
    here = [p for p in people_at(world, town) if not p.data.get("is_player")]
    rich = [p.id for p in here if p.data.get("occupation") == "merchant"]
    return min(rich) if rich else None


def sell_block(world, player: int, town: int, item_id: int) -> str | None:
    item = world.entity(item_id)
    if item is None or item.kind != "gear" or item_id not in world.targets(player, "owns"):
        return "You do not have that."
    if item.data.get("armoury") is not None:
        return "That belongs to your sect's armoury."
    if item.data.get("famous") and buyer_for(world, town, player) is None:
        return "No one here could pay what it is worth. Try a city's merchants."
    return None


def sell_events(world, player: int, town: int, item_id: int) -> list[Event]:
    famous = world.entity(item_id).data.get("famous")
    buyer = buyer_for(world, town, player) if famous else None
    amount = sell_price(world, town, item_id)
    return gear.pass_events(world, player, buyer, item_id, town, "sold") + [
        Event("gear_sold", (player,) + ((buyer,) if buyer else ()), town, {"item": item_id, "price": amount})]


@effect("gear_sold")
def _sold(world, event) -> None:
    player = event.actors[0]
    world.update_data(player, silver=silver_of(world, player) + event.data["price"])
