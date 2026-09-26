"""What a weapon has done, and who knows it (phase 5a spec 3.1-3.2).

A weapon wielded in a notable deed remembers it: an item keeps its twelve weightiest deeds, a carried grade keeps
them until it is made real. The deeds of a famous weapon, or of any of treasure grade or better, are told as
facts about the weapon (`wielded_in`), and spread like any rumour. Whoever believes one knows the weapon on
sight: a proud or greedy fighter may challenge its bearer for it, the kin of those it killed hate its bearer, and
the faction it was taken from demands it back.
"""

import systems.gear as gear
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.kin import kin_of
from systems.realms import realm_index
from world.events import Event, Witness, effect, listen
from world.seed import rng_for

LEGEND_GRADE = 3  # treasure grade or better is told of
KILL_WEIGHT, LEADER_WEIGHT, BESTED_WEIGHT, TITLE_WEIGHT = 3.0, 4.0, 2.0, 2.5
NOTABLE_RANK, NOTABLE_REALM = 3, 2
COVET_CHANCE, COVETOUS = 0.2, frozenset({"proud", "greedy"})
KIN_HATRED = 0.6
DEED_HOOKS: list = []  # (world, item entity, deed) -> None: a famous weapon's epithet (Task 3)


# --- deeds ----------------------------------------------------------------------------------------------

def notable(world, person: int) -> str | None:
    """Why this person's fall is worth remembering: a leader, a ranked member, a strong fighter; or None."""
    data = world.entity(person).data
    rows = F.memberships(world, person)
    if any(d.get("role") == "leader" and d.get("status", "member") == "member" for _, _, d in rows):
        return "leader"
    if any(rank >= NOTABLE_RANK and d.get("status", "member") == "member" for _, rank, d in rows) \
            or realm_index(data.get("realm", "mortal")) >= NOTABLE_REALM:
        return "notable"
    return None


def _keep(deeds: list, deed: dict) -> list:
    return sorted(deeds + [deed], key=lambda d: (-d["weight"], d["event"]))[:gear.MAX_DEEDS]


def remember(world, person: int, deed: dict, place) -> None:
    """The weapon this person struck with remembers the deed; a great one's is told (spec 3.1-3.2)."""
    w = gear.weapon_of(world, person)
    if w is None or w["broken"]:
        return  # bare hands leave no legend
    if w["item"] is None and w["grade"] >= LEGEND_GRADE and not world.entity(person).data.get("is_player"):
        gear.materialize(world, person, "weapon")  # a treasure is worth a name of its own
        w = gear.weapon_of(world, person)
    if w["item"] is None:
        carried = dict(gear.carried(world, person))
        carried["deeds"] = _keep(list(carried.get("deeds", [])), deed)
        world.update_data(person, gear=carried)
        return
    item = world.entity(w["item"])
    world.update_data(item.id, deeds=_keep(list(item.data["deeds"]), deed))
    if item.data.get("famous") or item.data["grade"] >= LEGEND_GRADE:
        variant = make_variant("wielded_in", item.id, deed.get("whom"), place=place_name(world, place))
        variant.update(wielder=person, deed=deed["kind"])
        record_fact(world, item.id, "wielded_in", deed.get("whom"), place=place, source_event=deed["event"],
                    weight=deed["weight"], variant=variant)
    for hook in DEED_HOOKS:
        hook(world, world.entity(item.id), deed)


@listen("died")
def _killed_with(world, event, event_id: int) -> None:
    killer, victim = event.actors[0], event.actors[-1]
    if killer == victim or world.entity(killer) is None or world.entity(killer).data.get("dead"):
        return
    why = notable(world, victim)
    if why is not None:
        remember(world, killer, {"event": event_id, "kind": "killed", "whom": victim,
                                 "weight": LEADER_WEIGHT if why == "leader" else KILL_WEIGHT}, event.place)


def ranked(world, person: int) -> bool:
    from systems.rankings import pavilion, rank_of  # the Pavilion comes after the duel in the import graph
    pav = pavilion(world)
    return pav is not None and rank_of(world.entity(pav).data.get("lists") or {}, person) is not None


@listen("duel_ended")
def _bested_with(world, event, event_id: int) -> None:
    d = event.data
    if d.get("killed") or d.get("player_killed"):
        return  # the death tells it
    player, opponent = event.actors
    if d["result"] == "won" and ranked(world, opponent):
        remember(world, player, {"event": event_id, "kind": "bested", "whom": opponent, "weight": BESTED_WEIGHT},
                 event.place)
    elif d["result"] == "lost" and d.get("by") == "opponent" and ranked(world, player):
        remember(world, opponent, {"event": event_id, "kind": "bested", "whom": player, "weight": BESTED_WEIGHT},
                 event.place)


@listen("tournament_won")
def _title_with(world, event, event_id: int) -> None:
    champion = event.data.get("champion")
    if champion is not None and world.entity(champion) is not None and not world.entity(champion).data.get("dead"):
        remember(world, champion, {"event": event_id, "kind": "won_tournament", "whom": None,
                                   "weight": TITLE_WEIGHT}, event.place)


# --- knowing a weapon on sight ----------------------------------------------------------------------------

def recognizers(world, item_id: int, people) -> set[int]:
    """Who among these believes any tale of this weapon (one query, the beliefs' actor index)."""
    return {belief.knower for belief, _ in world.known_facts_about(people, actors=[item_id], predicate="wielded_in")}


def known_blades(world, viewer: int, people) -> list[tuple[int, int]]:
    """(person, item) for each of these who wields a weapon the viewer knows by its tales."""
    held = [(p, world.targets(p, "wields")) for p in people if p != viewer]
    held = [(p, found[0]) for p, found in held if found]
    if not held:
        return []
    known = {fact.subject for _, fact in world.known_facts_about([viewer], actors=[i for _, i in held],
                                                                 predicate="wielded_in")}
    return [(p, i) for p, i in held if i in known]


def killed_by(world, item) -> list[int]:
    return [d["whom"] for d in item.data["deeds"] if d["kind"] == "killed" and d.get("whom") is not None]


def reactions(world, bearer: int, place: int, present: list[int]) -> dict:
    """What the people here make of the weapon the bearer carries: {covets, hates, demands} (spec 3.2)."""
    item = gear.item_in(world, bearer, "weapon")
    out = {"covets": None, "hates": [], "demands": None}
    if item is None:
        return out
    knowing = sorted(recognizers(world, item.id, [p for p in present if p != bearer]))
    if not knowing:
        return out
    grief = {k for victim in killed_by(world, item) for k, _ in kin_of(world, victim)}
    mine = realm_index(world.entity(bearer).data.get("realm", "mortal"))
    claimed = item.data.get("claimed_by")
    for person in knowing:
        data = world.entity(person).data
        if person in grief and not any(m.feeling == "hatred" for m in world.memories(person, about=bearer)):
            out["hates"].append(person)
        if claimed is not None and out["demands"] is None and any(
                f == claimed and d.get("status", "member") == "member" for f, _, d in F.memberships(world, person)):
            out["demands"] = person
        rng = rng_for(world.world_seed, f"covet:{person}:{item.id}:{world.time}")
        if out["covets"] is None and COVETOUS & set(data.get("traits", ())) \
                and abs(realm_index(data.get("realm", "mortal")) - mine) <= 1 and rng.random() < COVET_CHANCE:
            out["covets"] = person
    return out


def hatred_events(world, bearer: int, haters: list[int], place: int, item: int) -> list[Event]:
    return [Event("blade_known", (h, bearer), place, {"item": item},
                  witnesses=(Witness(h, "hatred", KIN_HATRED),)) for h in haters]


def demand_events(world, bearer: int, demander: int, item_id: int, place: int, hand_over: bool) -> list[Event]:
    """Hand it over (the sect thinks better of you) or refuse (worse), spec 3.2."""
    faction = world.entity(item_id).data["claimed_by"]
    events = [Event("blade_demanded", (bearer, demander), place,
                    {"item": item_id, "faction": faction, "handed": hand_over})]
    if hand_over:
        events += gear.pass_events(world, bearer, demander, item_id, place, "given")
    return events


@listen("blade_demanded")
def _demanded(world, event, event_id: int) -> None:
    bearer, d = event.actors[0], event.data
    predicate = "returned_gear" if d["handed"] else "kept_gear"
    variant = make_variant(predicate, bearer, d["faction"], place=place_name(world, event.place))
    record_fact(world, bearer, predicate, d["faction"], place=event.place, source_event=event_id,
                weight=0.5 if d["handed"] else 1.0, variant=variant)


@effect("blade_known")
def _known(world, event) -> None:
    pass  # the hatred is the witness's memory
