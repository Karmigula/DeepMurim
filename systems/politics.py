"""Politics inside a faction (phase 3b spec 6): the rival, framing, taboos, summons and judgement.

A taboo is judged from what the faction has heard (its towns' gossip), never
from the truth: a framed member is summoned exactly like a guilty one.
"""

from systems import factions as F
from systems import halls
from systems.attitude import attitude, is_bandit
from systems.beliefs import apparent_to
from systems.duties import _hostile_member
from systems.facts import make_variant, place_name, record_fact
from systems.membership import left_events, set_membership
from systems.realms import realm_index
from systems.standing import knowledge, seen_ids
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

FRAME_CHANCE = 0.15
PUNISH_MERIT = 30
DENY_BASE = 0.4
HARMFUL = frozenset({"killed", "crippled", "robbed", "left_for_dead", "defeated"})
RIGHTEOUS_TYPES = frozenset({"orthodox_sect", "school", "alliance"})


def rival_of(world, player: int, faction: int) -> int | None:
    return (world.entity(player).data.get("rivals") or {}).get(str(faction))


@listen("joined")
def _pick_rival(world, event, event_id: int) -> None:
    player, faction = event.actors[0], event.data["faction"]
    data = world.entity(faction).data
    if data["tier"] != "great" or data["type"] not in F.STAFFED or rival_of(world, player, faction):
        return
    disciples = halls.staff_at(world, faction, halls.seat_of(world, faction), roles=("disciple",))
    if not disciples:
        return
    rival = rng_for(world.world_seed, f"rival:{faction}:{player}").choice(sorted(disciples))
    traits = world.entity(rival).data.get("traits", [])
    world.update_data(rival, traits=list(dict.fromkeys(["proud", *traits]))[:2])
    world.add_memory(rival, event_id, "annoyed", 0.5, ignore_existing=True)
    rivals = dict(world.entity(player).data.get("rivals") or {})
    rivals[str(faction)] = rival
    world.update_data(player, rivals=rivals)


def taboo_broken(world, faction: int, predicate: str, target) -> bool:
    kind = world.entity(faction).data["type"]
    victim = world.entity(target) if isinstance(target, int) else None
    theirs = [fid for fid, _, d in F.memberships(world, target) if d.get("status", "member") == "member"] if victim else []
    innocent = victim is not None and victim.kind == "person" and not is_bandit(victim) \
        and not victim.data.get("beast") and realm_index(victim.data.get("realm", "mortal")) == 0
    dark = victim is not None and victim.kind == "faction" and victim.data["type"] in F.DARK
    if kind in RIGHTEOUS_TYPES or kind == "imperial":
        if predicate in ("killed", "robbed") and innocent:
            return True
        if predicate == "member_of" and dark:
            return True
        return kind == "imperial" and predicate == "crippled"
    if kind in F.DARK:
        return predicate == "spared" and any(F.stance(world, faction, g) <= F.HOSTILE for g in theirs)
    if kind in ("martial_clan", "local_clan"):
        return predicate in HARMFUL and faction in theirs
    if kind == "beggars":
        return predicate in HARMFUL and victim is not None and victim.data.get("occupation") == "beggar"
    if kind == "merchant_guild":
        return predicate == "robbed" and victim is not None and victim.data.get("occupation") == "merchant"
    return False


def breaches(world, player: int, faction: int) -> list:
    """Taboos the faction has heard the player broke since joining, not yet judged."""
    found = F.membership(world, player, faction)
    if not found or found[1].get("status", "member") != "member":
        return []
    data = found[1]
    judged = set(data.get("judged", []))
    know = knowledge(world, faction)
    seen = seen_ids(world, faction, player, know)
    out = []
    for belief, fact in know:
        if fact.id in judged or belief.variant.get("actor") not in seen or fact.time < data.get("joined_at", 0):
            continue
        if taboo_broken(world, faction, fact.predicate, belief.variant.get("target")):
            out.append(fact)
    return sorted(out, key=lambda f: f.id)


def accuser(world, player: int, faction: int) -> int | None:
    """The elder of the other hall, else the leader, else a hall keeper."""
    hall = F.membership(world, player, faction)[1].get("hall")
    elders = halls.elders(world, faction) if world.entity(faction).data["type"] in F.STAFFED else {}
    other = elders.get(1 - hall) if isinstance(hall, int) else None
    if other:
        return other
    seat = halls.seat_of(world, faction)
    leaders = halls.staff_at(world, faction, seat, roles=("leader",))
    return leaders[0] if leaders else halls.keeper_at(world, faction, seat)


def summons_events(world, player: int, town: int) -> list[Event]:
    """Being in a hall town of a faction that has heard of an unjudged breach: be summoned."""
    if world.entity(player).data.get("summons"):
        return []
    for fid in halls.halls_here(world, town):
        found = F.membership(world, player, fid)
        if not found or found[1].get("status", "member") != "member":
            continue
        pending = breaches(world, player, fid)
        judge = accuser(world, player, fid)
        if pending and judge:
            fact = pending[0]
            return [Event("summoned", (player, judge), town,
                          {"faction": fid, "fact": fact.id, "predicate": fact.predicate, "accuser": judge})]
    return []


@effect("summoned")
def _summoned(world, event) -> None:
    d = event.data
    world.update_data(event.actors[0], summons={"faction": d["faction"], "fact": d["fact"], "accuser": d["accuser"]})


def _contradicted(world, player: int, fact, town: int) -> bool:
    """Someone here who would know first-hand it did not happen: the named victim, with no memory of it."""
    target = fact.variant.get("target")
    if not isinstance(target, int) or target not in {p.id for p in people_at(world, town)}:
        return False
    return not any(m.event.kind in ("duel_ended", "exchange") for m in world.memories(target, about=player))


def deny_chance(world, player: int, summons: dict, town: int) -> float:
    faction = summons["faction"]
    sponsor = F.membership(world, player, faction)[1].get("sponsor")
    favour = attitude(world, sponsor, apparent_to(world, sponsor, player)).score if sponsor else 0.0
    hostility = attitude(world, summons["accuser"], apparent_to(world, summons["accuser"], player)).score
    witness = 0.4 if _contradicted(world, player, world.fact(summons["fact"]), town) else 0.0
    return max(0.0, min(1.0, DENY_BASE + 0.25 * favour - 0.25 * hostility + witness))


def judged_events(world, player: int, place: int, outcome: str, demote: bool = False) -> list[Event]:
    summons = world.entity(player).data["summons"]
    events = [Event("judged", (player, summons["accuser"]), place, {**summons, "outcome": outcome, "demote": demote})]
    if outcome == "expelled":
        events += left_events(world, player, summons["faction"], place, "expelled")
    return events


@effect("judged")
def _judged(world, event) -> None:
    player, d = event.actors[0], event.data
    rank, data = F.membership(world, player, d["faction"])
    changes = {"judged": [*data.get("judged", []), d["fact"]]}
    if d["outcome"] == "punished":
        merit = data.get("merit", 0)
        demote = merit < PUNISH_MERIT and rank > 0  # can't pay the full price in merit: pay in rank
        set_membership(world, player, d["faction"], rank=rank - 1 if demote else rank,
                       merit=max(0, merit - PUNISH_MERIT), **changes)
    else:
        set_membership(world, player, d["faction"], **changes)
    exposable = None
    if d["outcome"] == "cleared":
        fact = world.fact(d["fact"])
        liar = fact.data.get("liar") if fact is not None else None
        if liar and liar == rival_of(world, player, d["faction"]):  # the elder knows who told them
            exposable = {"faction": d["faction"], "fact": d["fact"], "rival": liar}
    world.update_data(player, summons=None, exposable=exposable)


@listen("duty_done")
def _maybe_framed(world, event, event_id: int) -> None:
    player, faction = event.actors[0], event.data["faction"]
    if rng_for(world.world_seed, f"frame:{event.data['duty']}").random() < FRAME_CHANCE:
        frame(world, player, faction, event.data["duty"])


def frame(world, player: int, faction: int, duty_id: int) -> bool:
    """The rival tells the other hall's elder an invented breach (an unnarrated, offstage lie)."""
    rival = rival_of(world, player, faction)
    if rival is None or world.entity(rival).data.get("dead"):
        return False
    judge = accuser(world, player, faction)
    seat = halls.seat_of(world, faction)
    rng = rng_for(world.world_seed, f"frame-target:{duty_id}")
    if world.entity(faction).data["path"] == "ruthless":
        predicate, target = "spared", _hostile_member(world, rng, faction)
    else:
        pool = sorted(p.id for p in people_at(world, seat) if not F.memberships(world, p.id) and not p.data.get("is_player"))
        predicate, target = "robbed", (rng.choice(pool) if pool else None)
    if judge is None or target is None:
        return False
    story = make_variant(predicate, player, target, place=place_name(world, seat))
    commit(world, [Event("told", (rival, judge), seat,
                         {"fact": None, "variant": story, "invented": True, "accepted": True, "speaker": rival},
                         witnesses=(Witness(judge, "engaged", 0.1),))])
    return True


def exposed_events(world, player: int, place: int) -> list[Event]:
    ex = world.entity(player).data["exposable"]
    return [Event("rival_exposed", (player, ex["rival"]), place, ex, witnesses=(Witness(ex["rival"], "wronged", 0.8),))]


@effect("rival_exposed")
def _exposed(world, event) -> None:
    player, rival, d = event.actors[0], event.actors[1], event.data
    set_membership(world, rival, d["faction"], status="expelled")
    _, data = F.membership(world, player, d["faction"])
    set_membership(world, player, d["faction"], merit=data.get("merit", 0) + 20)
    world.update_data(player, exposable=None)


@listen("rival_exposed")
def _exposed_fact(world, event, event_id: int) -> None:
    player, rival = event.actors
    record_fact(world, rival, "lied_about", player, place=event.place, source_event=event_id,
                variant=make_variant("lied_about", rival, player, place=place_name(world, event.place)))
