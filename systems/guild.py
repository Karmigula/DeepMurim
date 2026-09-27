"""The Alchemists' Guild (phase 5c spec 3): ranks 1-9 won by examination at its branch in every city.

The Guild is no faction of the roster (ruling 1): it is a branch in each city and a rank on each alchemist,
`guild_rank` on the person (0 once joined, None before). An examination for the next rank asks a known recipe of
the grade the rank needs, a fee, and one refining roll; it may be sat once a season. A rank passed is a fact
(`guild_rank`) that spreads like any other: who has heard it thinks better of the alchemist, and the herbalist
sells cheaper to the Guild's own. NPC alchemists (herbalists by trade and the sects' pill masters) carry a
seeded rank until something first writes one.
"""

import math

import systems.alchemy as A
import systems.lives as lives
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import Event, effect, listen
from world.seed import rng_for

MAX_RANK = 9
EXAM_FEE = 50              # silver per rank sat
HERB_DISCOUNT = 0.03       # off the herbalist's price, per rank
RESPECT = 0.05             # attitude per rank, from anyone who knows it
NPC_RANKS = (1, 4)         # a seeded NPC alchemist's rank
ORDINALS = ("", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth")
ALCHEMIST_JOBS = frozenset({"herbalist"})


def recipe_grade(key: str) -> int:
    """How hard a recipe is: its pills' grade from the Guild's herbs (ruling 2)."""
    base = A.recipe_base(key)
    if "grade" in base:
        return base["grade"]
    return 1 if base["potency"] <= 4 else 2 if base["potency"] <= 6 else 3


def needed_grade(rank: int) -> int:
    """The grade of recipe an examination for this rank asks (ruling 2: the base recipes top out at 3)."""
    return min(3, math.ceil(rank / 2))


def title(rank: int) -> str:
    return f"a {ORDINALS[rank]}-rank alchemist" if rank else "an unranked member of the Guild"


def branch_here(world, place) -> bool:
    entity = world.entity(place) if place is not None else None
    return entity is not None and entity.kind == "town" and entity.data.get("kind") == "city"


def rank_of(world, person: int) -> int | None:
    """A person's Guild rank: written once joined or examined, else seeded for an NPC alchemist, else None."""
    entity = world.entity(person)
    if "guild_rank" in entity.data:
        return entity.data["guild_rank"]
    if entity.data.get("is_player") or not is_alchemist(world, person):
        return None
    return rng_for(world.world_seed, f"guild:{lives.key(entity)}").randint(*NPC_RANKS)


def is_pill_master(world, person: int) -> bool:
    """The keeper of a sect's pill hall, standing at its seat (spec 3)."""
    from systems.pill_hall import keeps_hall
    here = world.targets(person, "located_in")
    for fid, _, data in F.memberships(world, person):
        if data.get("role") == "keeper" and data.get("status", "member") == "member" and keeps_hall(world, fid) \
                and here == [world.entity(fid).data.get("seat")]:
            return True
    return False


def is_alchemist(world, person: int) -> bool:
    entity = world.entity(person)
    if entity is None or entity.kind != "person" or entity.data.get("beast"):
        return False
    return entity.data.get("occupation") in ALCHEMIST_JOBS or is_pill_master(world, person)


def discount(world, person: int | None) -> float:
    rank = world.entity(person).data.get("guild_rank") if person is not None else None
    return 1.0 - HERB_DISCOUNT * (rank or 0)


# --- joining ------------------------------------------------------------------------------------------------

def join_block(world, person: int, place) -> str | None:
    if not branch_here(world, place):
        return "The Guild keeps its branches in the cities."
    if world.entity(person).data.get("guild_rank") is not None:
        return "You are one of the Guild already."
    return None


def join_events(world, person: int, place) -> list[Event]:
    return [Event("guild_joined", (person,), place, {})]


@effect("guild_joined")
def _joined(world, event) -> None:
    world.update_data(event.actors[0], guild_rank=0)


# --- examinations ------------------------------------------------------------------------------------------

def exam_recipe(world, person: int, rank: int) -> int | None:
    """The recipe the candidate would refine for this rank: the one they know best of the grade it asks."""
    fit = [(m, r) for r, m in A.known_recipes(world, person)
           if recipe_grade(world.entity(r).data["key"]) >= needed_grade(rank)]
    return max(fit)[1] if fit else None


def exam_block(world, person: int, place) -> str | None:
    rank = world.entity(person).data.get("guild_rank")
    if not branch_here(world, place):
        return "The Guild keeps its branches in the cities."
    if rank is None:
        return "Join the Guild first."
    if rank >= MAX_RANK:
        return "There is no higher rank."
    if world.entity(person).data.get("guild_exam_season") == lives.current_season(world):
        return "The examiners sit once a season."
    if exam_recipe(world, person, rank + 1) is None:
        return f"The {ORDINALS[rank + 1]} rank asks a recipe of grade {needed_grade(rank + 1)}."
    if silver_of(world, person) < EXAM_FEE * (rank + 1):
        return f"The fee is {EXAM_FEE * (rank + 1)} silver."
    return None


def exam_events(world, person: int, place) -> list[Event]:
    rank = world.entity(person).data["guild_rank"] + 1
    recipe = exam_recipe(world, person, rank)
    season = lives.current_season(world)
    passed = rng_for(world.world_seed, f"guild_exam:{person}:{season}").random() < A.refine_chance(world, person, recipe)
    return [Event("guild_exam", (person,), place, {"rank": rank, "recipe": recipe, "passed": passed,
                                                   "fee": EXAM_FEE * rank, "season": season})]


@effect("guild_exam")
def _exam(world, event) -> None:
    person, d = event.actors[0], event.data
    changes = {"silver": silver_of(world, person) - d["fee"], "guild_exam_season": d["season"]}
    if d["passed"]:
        changes["guild_rank"] = d["rank"]
    world.update_data(person, **changes)


@listen("guild_exam")
def _ranked_news(world, event, event_id: int) -> None:
    if not event.data["passed"]:
        return
    person, rank = event.actors[0], event.data["rank"]
    variant = make_variant("guild_rank", person, None, place=place_name(world, event.place))
    variant.update(rank=rank)
    record_fact(world, person, "guild_rank", None, place=event.place, source_event=event_id, weight=1.0 + 0.2 * rank,
                variant=variant)


def known_rank(world, knower: int, subject: int) -> int | None:
    """The highest Guild rank this knower has heard of for the subject, or None (spec 8)."""
    from systems.beliefs import knowledge_of
    heard = [b.variant.get("rank", 0) for b, f in knowledge_of(world, knower)
             if f.predicate == "guild_rank" and b.variant.get("actor") == subject]
    return max(heard) if heard else None
