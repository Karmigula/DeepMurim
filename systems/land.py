"""Land (phase 3c spec 3): bought from a magistrate, claimed from ruins, or seized from a minor faction."""

from systems import factions as F
from systems import halls
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.purse import payment_events
from world.events import Event, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

PRICES = {"village": 150, "town": 400, "city": 900}
RUIN_CHANCE = 0.3


def owner_of(world, town: int) -> int | None:
    return world.entity(town).data.get("owner")


def land_price(world, town: int) -> int:
    return PRICES.get(world.entity(town).data.get("kind"), 400)


def _great_home(world, town: int) -> bool:
    data = world.entity(town).data
    return any(tuple(world.entity(f).data["home"]) == (data["x"], data["y"]) for f in F.ensure_roster(world))


def magistrate_of(world, town: int) -> int | None:
    """Who registers land here: whoever keeps the imperial office's hall."""
    bureau = next(f for f in F.ensure_roster(world) if world.entity(f).data["type"] == "imperial")
    return halls.keeper_at(world, bureau, town)


def buy_block(world, player: int, town: int) -> str | None:
    owner = owner_of(world, town)
    if owner == player:
        return "This land is already yours."
    if owner is not None or world.entity(town).data.get("seats") or _great_home(world, town):
        return "This land is not for sale."
    return None


def buy_events(world, player: int, magistrate: int, town: int) -> list[Event]:
    price = land_price(world, town)
    return payment_events(player, magistrate, town, price, "land") + [
        Event("land_bought", (player, magistrate), town, {"price": price})]


def is_ruin(world, town: int) -> bool:
    """An old hall stands in one seeded town of some regions that no great faction calls home."""
    entity = world.entity(town)
    if entity.data.get("owner") is not None or _great_home(world, town):
        return False
    region = region_of(world, town)
    rng = rng_for(world.world_seed, f"{region.seed_path}/ruin")
    return rng.random() < RUIN_CHANCE and rng.randrange(region.data["town_count"]) == entity.data["index"]


def contester(world, town: int) -> int | None:
    """The leader of the region's first minor faction contests a claim, if there is one."""
    for fid in F.minor_factions(world, region_of(world, town)):
        faction = world.entity(fid)
        if faction.data.get("dissolved"):
            continue
        halls.settle_town(world, faction.data["seat"])
        leaders = halls.staff_at(world, fid, faction.data["seat"], roles=("leader",))
        if leaders:
            return leaders[0]
    return None


def claim_events(player: int, town: int) -> list[Event]:
    return [Event("land_claimed", (player,), town, {})]


def _own(world, event) -> None:
    player, town = event.actors[0], event.place
    world.relate(player, town, "owns_land")
    world.update_data(town, owner=player)


effect("land_bought")(_own)
effect("land_claimed")(_own)


def seizable(world, npc: int, town: int) -> int | None:
    """The minor faction this person leads from a seat in this town."""
    for fid, _, data in F.memberships(world, npc):
        faction = world.entity(fid)
        if data.get("role") == "leader" and data.get("status", "member") == "member" \
                and faction.data["tier"] == "minor" and faction.data.get("seat") == town \
                and not faction.data.get("dissolved"):
            return fid
    return None


def seized_events(world, player: int, faction: int, town: int) -> list[Event]:
    return [Event("seized", (player,), town, {"faction": faction})]


@effect("seized")
def _seized(world, event) -> None:
    faction, town = event.data["faction"], event.place
    for person in world.sources(faction, "member_of"):
        set_membership(world, person, faction, status="expelled")
    world.update_data(faction, dissolved=True)
    data = world.entity(town).data
    world.update_data(town, halls=[f for f in data.get("halls", []) if f != faction],
                      seats=[f for f in data.get("seats", []) if f != faction])
    _own(world, event)


@listen("seized")
def _seized_fact(world, event, event_id: int) -> None:
    player, faction = event.actors[0], event.data["faction"]
    for person in world.sources(faction, "member_of"):
        if not world.entity(person).data.get("dead"):
            world.add_memory(person, event_id, "wronged", 0.8, ignore_existing=True)
    record_fact(world, player, "seized", faction, place=event.place, source_event=event_id, weight=2.5,
                variant=make_variant("seized", player, faction, place=place_name(world, event.place)))
