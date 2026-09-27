"""Recipes as lore (phase 5c spec 4): scrolls bought, given, taught, stolen, read and sold.

A scroll is an item (`kind = "scroll"`) naming a recipe and where it came from (`guild`, `sect`, `master` or
`stolen`; a sect's secret scroll also names its sect). Reading one teaches the recipe; the scroll is kept. The
Guild sells its base recipes up to the reader's rank and buys any scroll back at half; each sect's hall keeps one
or two secret recipes for its ranked members; an NPC alchemist who likes you teaches one of theirs; a sect's secret
sold to its rival fetches triple, and the sect hates the seller once it hears of it.
"""

import systems.alchemy as A
import systems.guild as G
from systems import factions as F
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.purse import silver_of
from world.events import Event, effect, listen
from world.seed import rng_for

PRICE = 100                # silver x grade squared, at the Guild
SELL_SHARE, RIVAL_SHARE = 0.5, 3  # half at the Guild; triple from a sect's rival
SECRET_MERIT = 50          # merit x grade, for a sect's secret scroll
SECRET_RANK = 2
SECRETS = (1, 2)
TEACH_ATTITUDE = 0.5
NPC_RECIPES = (1, 3)
SOURCES = ("guild", "sect", "master", "stolen")


def price(key: str) -> int:
    return PRICE * G.recipe_grade(key) ** 2


def make_scroll(world, owner: int, key: str, source: str, faction: int | None = None) -> int:
    recipe = A.recipe_entity(world, key)
    item = world.add_entity("scroll", f"a scroll of the {world.entity(recipe).name}",
                            {"recipe": recipe, "key": key, "source": source, "faction": faction})
    world.relate(owner, item, "owns")
    return item


def scrolls_of(world, person: int) -> list:
    return [e for e in (world.entity(i) for i in world.targets(person, "owns")) if e is not None and e.kind == "scroll"]


def _owned_scroll(world, person: int, item_id) -> bool:
    item = world.entity(item_id) if isinstance(item_id, int) else None
    return item is not None and item.kind == "scroll" and item_id in world.targets(person, "owns")


# --- reading ------------------------------------------------------------------------------------------------

def read_block(world, person: int, item_id) -> str | None:
    if not _owned_scroll(world, person, item_id):
        return "You have no such scroll."
    if A.mastery(world, person, world.entity(item_id).data["recipe"]) is not None:
        return "You know that recipe already."
    return None


def read_events(world, person: int, item_id: int, place) -> list[Event]:
    return [Event("scroll_read", (person,), place, {"item": item_id, "recipe": world.entity(item_id).data["recipe"]})]


@effect("scroll_read")
def _read(world, event) -> None:
    person, recipe = event.actors[0], event.data["recipe"]
    if A.mastery(world, person, recipe) is None:
        world.relate(person, recipe, "knows_recipe", A.DISCOVERED_MASTERY)


# --- the Guild's scrolls ---------------------------------------------------------------------------------------

def guild_offers(world, person: int) -> list[str]:
    """The base recipes the Guild will sell this member: of a grade their rank reaches, not yet known."""
    rank = world.entity(person).data.get("guild_rank")
    if rank is None:
        return []
    top = G.needed_grade(rank) if rank else 0
    known = {world.entity(r).data["key"] for r, _ in A.known_recipes(world, person)}
    return [k for k in sorted(A.RECIPES) if G.recipe_grade(k) <= top and k not in known]


def buy_block(world, person: int, key: str, place) -> str | None:
    if not G.branch_here(world, place):
        return "The Guild keeps its branches in the cities."
    if key not in guild_offers(world, person):
        return "The Guild will not sell you that."
    if silver_of(world, person) < price(key):
        return f"That scroll costs {price(key)} silver."
    return None


def buy_events(world, person: int, key: str, place) -> list[Event]:
    return [Event("scroll_bought", (person,), place, {"key": key, "price": price(key)})]


@effect("scroll_bought")
def _bought(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    make_scroll(world, person, d["key"], "guild")


def sell_price(world, item_id: int) -> int:
    return max(1, int(price(world.entity(item_id).data["key"]) * SELL_SHARE))


def sell_block(world, person: int, item_id, place) -> str | None:
    if not _owned_scroll(world, person, item_id):
        return "You have no such scroll."
    if not G.branch_here(world, place):
        return "The Guild keeps its branches in the cities."
    return None


def sell_events(world, person: int, item_id: int, place) -> list[Event]:
    return [Event("scroll_sold", (person,), place, {"item": item_id, "price": sell_price(world, item_id)})]


@effect("scroll_sold")
def _sold(world, event) -> None:
    person, d = event.actors[0], event.data
    world.unrelate(person, "owns", d["item"])
    world.update_data(person, silver=silver_of(world, person) + d["price"])
    world.update_data(d["item"], sold_to="guild")


# --- a sect's secret recipes -------------------------------------------------------------------------------------

def secret_recipes(world, faction: int) -> list[str]:
    """The one or two recipes this sect's hall keeps to itself, seeded from the base recipes."""
    rng = rng_for(world.world_seed, f"secret:{faction}")
    return sorted(rng.sample(sorted(A.RECIPES), rng.randint(*SECRETS)))


def secret_cost(key: str) -> int:
    return SECRET_MERIT * G.recipe_grade(key)


def secret_block(world, person: int, faction: int, key: str, place) -> str | None:
    from systems.pill_hall import keeps_hall
    if world.entity(faction).data.get("seat") != place or not keeps_hall(world, faction):
        return "The sect's secrets are kept in its pill hall."
    found = F.membership(world, person, faction)
    if found is None or found[1].get("status", "member") != "member" or found[0] < SECRET_RANK:
        return "Only a disciple of the second rank or higher is trusted with them."
    if key not in secret_recipes(world, faction):
        return "The hall keeps no such recipe."
    if any(s.data["key"] == key and s.data.get("faction") == faction for s in scrolls_of(world, person)):
        return "You hold that scroll already."
    if found[1].get("merit", 0) < secret_cost(key):
        return f"That scroll costs {secret_cost(key)} merit."
    return None


def secret_events(world, person: int, faction: int, key: str, place) -> list[Event]:
    return [Event("secret_scroll_given", (person,), place, {"faction": faction, "key": key,
                                                             "merit": secret_cost(key)})]


@effect("secret_scroll_given")
def _given(world, event) -> None:
    person, d = event.actors[0], event.data
    merit = F.membership(world, person, d["faction"])[1].get("merit", 0)
    set_membership(world, person, d["faction"], merit=merit - d["merit"])
    make_scroll(world, person, d["key"], "sect", d["faction"])


# --- a master's teaching -----------------------------------------------------------------------------------------

def npc_recipes(world, person: int) -> list[str]:
    """What an NPC alchemist knows, seeded from their rank."""
    rank = G.rank_of(world, person)
    if rank is None:
        return []
    top = max(1, G.needed_grade(rank))
    pool = sorted(k for k in A.RECIPES if G.recipe_grade(k) <= top)
    rng = rng_for(world.world_seed, f"npc_recipes:{person}")
    return sorted(rng.sample(pool, min(len(pool), rng.randint(*NPC_RECIPES))))


def teach_offers(world, person: int, npc: int) -> list[str]:
    known = {world.entity(r).data["key"] for r, _ in A.known_recipes(world, person)}
    return [k for k in npc_recipes(world, npc) if k not in known]


def teach_block(world, person: int, npc: int, key: str) -> str | None:
    if not G.is_alchemist(world, npc):
        return "They are no alchemist."
    if attitude(world, npc, apparent_to(world, npc, person)).score < TEACH_ATTITUDE:
        return "They do not know you well enough to teach you."
    if key not in teach_offers(world, person, npc):
        return "They teach nothing like that."
    if silver_of(world, person) < price(key):
        return f"They ask {price(key)} silver."
    return None


def teach_events(world, person: int, npc: int, key: str, place) -> list[Event]:
    return [Event("recipe_taught", (person, npc), place, {"key": key, "price": price(key)})]


@effect("recipe_taught")
def _taught(world, event) -> None:
    person, npc = event.actors
    d = event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    world.update_data(npc, silver=silver_of(world, npc) + d["price"])
    make_scroll(world, person, d["key"], "master")


# --- selling a sect's secret to its rival --------------------------------------------------------------------------

def rivals_of(world, faction: int) -> list[int]:
    return [f for f in F.ensure_roster(world) if f != faction and F.stance(world, f, faction) <= F.HOSTILE]


def secret_sale_block(world, person: int, item_id, buyer: int, place) -> str | None:
    if not _owned_scroll(world, person, item_id):
        return "You have no such scroll."
    sect = world.entity(item_id).data.get("faction")
    if sect is None:
        return "No sect would pay for that."
    if buyer not in rivals_of(world, sect):
        return "They are no enemy of that sect."
    if world.entity(buyer).data.get("seat") != place:
        return "Sell it at their seat."
    return None


def secret_sale_events(world, person: int, item_id: int, buyer: int, place) -> list[Event]:
    sect = world.entity(item_id).data["faction"]
    return [Event("secret_sold", (person,), place, {"item": item_id, "sect": sect, "buyer": buyer,
                                                    "price": price(world.entity(item_id).data["key"]) * RIVAL_SHARE})]


@effect("secret_sold")
def _secret_sold(world, event) -> None:
    person, d = event.actors[0], event.data
    world.unrelate(person, "owns", d["item"])
    world.update_data(person, silver=silver_of(world, person) + d["price"])
    world.update_data(d["item"], sold_to=d["buyer"])


@listen("secret_sold")
def _betrayal(world, event, event_id: int) -> None:
    person, sect = event.actors[0], event.data["sect"]
    record_fact(world, person, "sold_secret", sect, place=event.place, source_event=event_id, weight=2.0,
                variant=make_variant("sold_secret", person, sect, place=place_name(world, event.place)))
