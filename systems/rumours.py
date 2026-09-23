"""How news travels (phase 3a spec §5): witnesses, town gossip, kin, distance and telling.

Channels 1-2 react to new facts (kin is channel 3, in systems/kin.py). Channel 4
(distance) runs lazily: a town catches up on what has reached it when the player
arrives or asks. Every retelling may change the story, seeded so a world always
tells it the same way.
"""

from systems.beliefs import CONF_DECAY, believe, confidence_for, identities, knowledge_of, true_identity
from systems.facts import on_fact
from systems.realms import REALMS, realm_index
from world.events import Event, Witness, effect
from world.seed import rng_for

BASE_MUTATION = 0.25
HOP_WATCHES = 8        # two days per region crossed
REACH_FACTOR = 1.5     # a fact of weight w travels floor(1.5 * w) regions
NEWS_HALF_LIFE = 360   # watches; older news is less worth telling
LOUD = frozenset({"cheerful", "cunning"})
CAREFUL = frozenset({"honest", "secretive"})


# --- channels 1 and 2 ------------------------------------------------------------------

@on_fact
def _witnesses(world, fact) -> None:
    """Channel 1: everyone who took part in or saw the deed knows it first-hand."""
    if fact.source_event is None:
        return
    entry = world.chronicle_entry(fact.source_event)
    people = set(world.witnesses_of(fact.source_event)) | set(entry.actors if entry else ())
    for person_id in sorted(people):
        person = world.entity(person_id)
        if person is None or person.kind != "person" or person.data.get("dead") or person.data.get("beast"):
            continue
        believe(world, person_id, fact.id, fact.variant, None, 1.0, 0, "witness")


@on_fact
def _town_gossip(world, fact) -> None:
    """Channel 2: the town where it happened talks about it at once."""
    town = world.entity(fact.place) if fact.place else None
    if town is None or town.kind != "town":
        return
    believe(world, town.id, fact.id, fact.variant, None, CONF_DECAY, 1, "gossip")


# --- retelling --------------------------------------------------------------------------

def mutation_chance(traits=()) -> float:
    traits = set(traits)
    chance = BASE_MUTATION
    if LOUD & traits:
        chance *= 1.5
    if CAREFUL & traits:
        chance *= 0.5
    return chance


def mutate(variant: dict, rng, hops: int) -> dict:
    """One change to a story. Never the deed's family, never who was harmed, never truth into lie."""
    story = dict(variant)
    if story.get("predicate") == "is":
        return story
    options = ["exaggerate", "blur_place", "blur_art"]
    if story.get("masked") and story.get("actor") is not None and hops >= 2:
        options.append("misattribute")
    if story.get("predicate") == "killed" and not story.get("soft"):
        options.append("soften")
    choice = rng.choice(options)
    if choice == "exaggerate":
        if story.get("count", 1) == 1 and story.get("target") is not None:
            story["count"] = rng.choice((2, 3))
        elif story.get("realm") and realm_index(story["realm"]) < len(REALMS) - 1:
            story["realm"] = REALMS[realm_index(story["realm"]) + 1].label
    elif choice == "blur_place":
        story["place"] = None
    elif choice == "blur_art":
        story["art"], story["form"] = None, None
    elif choice == "misattribute":
        story["actor"] = None
    else:
        story["soft"] = True
    return story


def retell(variant: dict, fact_id: int, knower: int, world_seed: int, first_hop: int, last_hop: int,
           traits=()) -> dict:
    """The story after retellings first_hop..last_hop on its way to `knower`."""
    story = dict(variant)
    chance = mutation_chance(traits)
    for hop in range(first_hop, last_hop + 1):
        rng = rng_for(world_seed, f"rumour:{fact_id}:{knower}:{hop}")
        if rng.random() < chance:
            story = mutate(story, rng, hop)
    return story


# --- channel 4: distance --------------------------------------------------------------------

def region_distance(town_a, town_b) -> int:
    return max(abs(town_a.data["x"] - town_b.data["x"]), abs(town_a.data["y"] - town_b.data["y"]))


def reach(weight: float) -> int:
    return int(weight * REACH_FACTOR)


def catch_up(world, town_id: int, now: int | None = None) -> list[int]:
    """Let this town hear every fact that has had time to travel here. Returns the facts that arrived."""
    town = world.entity(town_id)
    if town is None or town.kind != "town":
        return []
    now = world.time if now is None else now
    origins: dict = {}
    added = []
    with world.transaction():
        for fact in world.facts_unknown_to(town_id, until=now - HOP_WATCHES):
            if fact.place is None or fact.place == town_id or fact.data.get("spread") is False:
                continue
            if fact.place not in origins:
                origins[fact.place] = world.entity(fact.place)
            origin = origins[fact.place]
            if origin is None or origin.kind != "town":
                continue
            distance = region_distance(origin, town)
            if distance > reach(fact.weight) or now < fact.time + distance * HOP_WATCHES:
                continue
            hops = distance + 1
            story = retell(fact.variant, fact.id, town_id, world.world_seed, 1, hops)
            believe(world, town_id, fact.id, story, origin.id, confidence_for(hops), hops, "distance")
            added.append(fact.id)
    return added


# --- telling the player ------------------------------------------------------------------------

def pick_news(world, npc_id: int, player_id: int):
    """The story this person would pass on now: heaviest and newest, about others before the player."""
    now = world.time
    mine = world.beliefs(player_id)
    held = {(b.fact_id, b.variant_key) for b in mine}
    told_me = {b.fact_id for b in mine if b.source == npc_id}
    me = identities(world, player_id, player_id)
    fresh = [(b, f) for b, f in knowledge_of(world, npc_id)
             if (b.fact_id, b.variant_key) not in held and f.id not in told_me and f.data.get("liar") != player_id]
    others = [(b, f) for b, f in fresh if f.subject not in me and f.object not in me]
    pool = others or fresh
    if not pool:
        return None
    return max(pool, key=lambda p: (p[1].weight * 0.5 ** (max(0, now - p[1].time) / NEWS_HALF_LIFE),
                                    p[1].id, p[0].variant_key))


def news_about(world, npc_id: int, subject_id: int):
    """This person's surest story about someone, or None if they have never heard of them."""
    true_id = true_identity(world, subject_id)
    ids = identities(world, npc_id, true_id) if subject_id == true_id else {subject_id}
    found = [(b, f) for b, f in knowledge_of(world, npc_id)
             if b.variant.get("actor") in ids or b.variant.get("target") in ids]
    if not found:
        return None
    return max(found, key=lambda p: (p[0].confidence * p[1].weight, p[1].id, p[0].variant_key))


def heard_events(world, player: int, npc: int, place: int, belief, fact) -> list[Event]:
    teller = world.entity(npc)
    traits = teller.data.get("traits", ())
    hops = belief.hops + 1
    story = retell(belief.variant, fact.id, player, world.world_seed, hops, hops, traits)
    trust = 0.9 if "cunning" in traits else 1.0
    data = {"fact": fact.id, "variant": story, "confidence": confidence_for(hops, trust), "hops": hops}
    return [Event("heard", (player, npc), place, data, witnesses=(Witness(npc, "engaged", 0.1),))]


def no_news_events(player: int, npc: int, place: int, about: str | None = None) -> list[Event]:
    return [Event("no_news", (player, npc), place, {"about": about})]


@effect("heard")
def _heard(world, event) -> None:
    d = event.data
    believe(world, event.actors[0], d["fact"], d["variant"], event.actors[1], d["confidence"], d["hops"], "told")
