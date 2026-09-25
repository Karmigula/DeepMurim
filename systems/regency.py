"""A sect the player leads (phase 4g spec 6.4), and regents (6.5).

A sect the player leads is one they founded (3c) or an NPC seat they won. It can be lost three ways: on
their death (the heir must hold it), while they are gone (a regent, then a usurper), and when they step
down. A founded sect that passes to someone not of the player's line becomes a school of the world, run
by the faction clock (plan ruling 10).
"""

import systems.claimants as C
import systems.lives as lives
import systems.succession_crisis as SC
import systems.world_clock as world_clock
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.tournaments import alive, realm_of
from world.events import Event, commit, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

ABSENCE = 8  # seasons away from the seat before a regency, and again before a usurpation
REFUSE_HANDOVER = 0.5  # an ambitious regent's chance to refuse a child come of age
SUCCESSORS = 3  # how many members are offered when the player steps down


def led_by(world, person: int) -> list[int]:
    """The factions whose seat this person holds (and has not lost)."""
    return [fid for fid, _, d in F.memberships(world, person)
            if d.get("role") == "leader" and d.get("status", "member") == "member"
            and not world.entity(fid).data.get("dissolved")]


def world_type(world, sect: int) -> str:
    return "unorthodox_clan" if world.entity(sect).data.get("path") == "ruthless" else "school"


def release(world, sect: int) -> None:
    """A founded sect passes out of the player's line: a minor faction of the world from now on (plan ruling 10)."""
    data = world.entity(sect).data
    if data.get("type") != "player_sect":
        return
    kind = world_type(world, sect)
    world.update_data(sect, type=kind, ranks=list(F.LADDERS[kind]), founder=None, tier="minor",
                      base_power=data.get("power", 20))
    region = region_of(world, data["seat"])
    world.update_data(region.id, minors=[*region.data.get("minors", []), sect])
    for person, _, _ in world.relations_to(sect, "member_of"):
        if world.entity(person).data.get("sect") == sect:
            world.update_data(person, sect=None)


@listen("succeeded")
def _passes_on(world, event, event_id: int) -> None:
    d = event.data
    if d["role"] == "leader" and world.entity(d["faction"]).data.get("type") == "player_sect" \
            and not world.entity(event.actors[0]).data.get("is_player"):
        release(world, d["faction"])


# --- the player's death (spec 6.4.1) ----------------------------------------------------------

def heir_doubt(world, faction: int, heir: int, was_member: bool) -> str | None:
    if not was_member or C.age_of(world, heir) < C.ADULT:
        return "heir"
    rivals = [e for e in C.staff(world, faction, ("elder",)) if e != heir]
    if any(realm_of(world, e) >= realm_of(world, heir) - 1 for e in rivals):
        return "close"
    return None


@listen("succession")
def _heir_holds(world, event, event_id: int) -> None:
    """The heir keeps the seats their forebear held, unless the elders doubt them: then a crisis, played in full."""
    old, heir = event.actors
    n = lives.current_season(world)
    for fid, was_member in event.data.get("led", []):
        if world.entity(fid).data.get("dissolved"):
            continue
        cause = heir_doubt(world, fid, heir, was_member)
        if cause is None:
            if world.entity(fid).data.get("type") != "player_sect":  # 4b already made them the founder's heir
                commit(world, [world_clock._promotion(world, heir, fid, "leader", 4, None)])
            continue
        rivals = [{"person": e, "kind": "elder"} for e in C.staff(world, fid, ("elder",))
                  if e != heir and (C.ambitious(world, e) or realm_of(world, e) >= realm_of(world, heir) - 1)]
        claimants = [{"person": heir, "kind": "player"}] + rivals[:C.MAX_CLAIMANTS]
        if len(claimants) < 2:
            if world.entity(fid).data.get("type") != "player_sect":
                commit(world, [world_clock._promotion(world, heir, fid, "leader", 4, None)])
            continue
        commit(world, SC.begin_events(world, fid, n, cause, claimants, old, force=True))


# --- absence: a regency, then a usurpation (spec 6.4.2) ---------------------------------------

def absence_events(world, n: int) -> list[Event]:
    """Each season: a sect whose master has been gone too long gets a regent; an ambitious regent, in time, the seat."""
    player = world.get_meta("player_id")
    if not isinstance(player, int):
        return []
    events = []
    for fid in led_by(world, player):
        data = world.entity(fid).data
        if SC.live(world, fid) is not None:
            continue
        regent = data.get("regent")
        visited = data.get("visited", n)
        if regent is None and n - visited >= ABSENCE:
            elders = [e for e in C.staff(world, fid, ("elder",)) if e != player]
            senior = C._best(world, elders)
            if senior is not None:
                events.append(Event("regency_declared", (senior, player), data["seat"], {"faction": fid, "season": n}))
        elif regent is not None and alive(world, regent["person"]) and n - regent["since"] >= ABSENCE \
                and C.ambitious(world, regent["person"]):
            events.append(Event("usurped", (regent["person"], player), data["seat"], {"faction": fid, "season": n}))
    return events


@effect("regency_declared")
def _regency(world, event) -> None:
    world.update_data(event.data["faction"], regent={"person": event.actors[0], "since": event.data["season"]})


@effect("usurped")
def _usurped(world, event) -> None:
    usurper, player = event.actors
    faction = event.data["faction"]
    set_membership(world, player, faction, rank=3, role="member")
    set_membership(world, usurper, faction, rank=4, role="leader")
    world.update_data(usurper, occupation=F.title(world, faction, 4))
    world.update_data(faction, regent=None, usurped_from=player)
    release(world, faction)


def _news(world, event, event_id: int, predicate: str) -> None:
    actor, player = event.actors
    faction = event.data["faction"]
    variant = make_variant(predicate, actor, faction, place=place_name(world, event.place))
    variant.update(people=[player])
    record_fact(world, actor, predicate, faction, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


@listen("regency_declared")
def _regency_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, "regency")


@listen("usurped")
def _usurped_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, "usurped")


def return_events(world, player: int, faction: int) -> list[Event]:
    """Back at the seat during a regency: the regent hands it back, or (ambitious) contests it."""
    data = world.entity(faction).data
    regent = (data.get("regent") or {}).get("person")
    if regent is None:
        return []
    if alive(world, regent) and C.ambitious(world, regent) and SC.live(world, faction) is None:
        claimants = [{"person": player, "kind": "player"}, {"person": regent, "kind": "regent"}]
        return [Event("regency_ended", (regent, player), data["seat"], {"faction": faction, "contested": True})] \
            + SC.begin_events(world, faction, lives.current_season(world), "regency", claimants, None, force=True)
    return [Event("regency_ended", (regent, player), data["seat"], {"faction": faction, "contested": False})]


@effect("regency_ended")
def _regency_ended(world, event) -> None:
    world.update_data(event.data["faction"], regent=None)


def reclaim_block(world, player: int, faction: int) -> str | None:
    data = world.entity(faction).data
    if data.get("usurped_from") != player:
        return "The seat was never yours."
    if SC.live(world, faction) is not None:
        return "The seat is already contested."
    return None


def reclaim_events(world, player: int, faction: int) -> list[Event]:
    holder = C.staff(world, faction, ("leader",))
    claimants = [{"person": player, "kind": "player"}] + [{"person": h, "kind": "elder"} for h in holder]
    return SC.begin_events(world, faction, lives.current_season(world), "usurped", claimants, None, force=True)


def visit(world, player: int, town: int) -> list[int]:
    """The player stands at the seat of sects they lead: the season is noted (a write only once a season)."""
    n = lives.current_season(world)
    found = []
    for fid in led_by(world, player):
        data = world.entity(fid).data
        if data.get("seat") == town:
            if data.get("visited") != n:
                world.update_data(fid, visited=n)
            found.append(fid)
    return found


# --- stepping down (spec 6.4.3) ---------------------------------------------------------------

def successors(world, player: int, faction: int) -> list[int]:
    """Members of rank 2 or more who could take the seat, the strongest first."""
    able = [p for p, rank, d in world.relations_to(faction, "member_of")
            if d.get("status", "member") == "member" and int(rank) >= 2 and p != player and alive(world, p)
            and d.get("role") not in ("grand_elder", "retired")]
    return sorted(able, key=lambda p: (-realm_of(world, p), p))[:SUCCESSORS]


def step_down_events(world, player: int, faction: int, successor: int) -> list[Event]:
    seat = world.entity(faction).data["seat"]
    rivals = [{"person": e, "kind": "elder"} for e in C.staff(world, faction, ("elder",))
              if e != successor and (C.ambitious(world, e) or realm_of(world, e) >= realm_of(world, successor))]
    claimants = [{"person": successor, "kind": "chief"}] + rivals[:C.MAX_CLAIMANTS - 1]
    probe = {"faction": faction, "claimants": claimants, "declared": {str(player): successor}}
    backing, undecided = C.camps(world, probe)
    tally = C.votes(world, probe, backing)
    clean = len(claimants) == 1 or tally[successor] * 2 > sum(tally.values()) + len(undecided)
    events = [Event("stepped_down", (player, successor), seat, {"faction": faction, "clean": clean})]
    if clean:
        return events + [world_clock._promotion(world, successor, faction, "leader", 4, None)]
    return events + SC.begin_events(world, faction, lives.current_season(world), "stepped_down", claimants, player,
                                    force=True)


@effect("stepped_down")
def _stepped_down(world, event) -> None:
    player = event.actors[0]
    set_membership(world, player, event.data["faction"], rank=3, role="retired")


@listen("stepped_down")
def _stepped_down_news(world, event, event_id: int) -> None:
    player, successor = event.actors
    variant = make_variant("stepped_down", player, event.data["faction"], place=place_name(world, event.place))
    variant.update(people=[successor])
    record_fact(world, player, "stepped_down", event.data["faction"], place=event.place, source_event=event_id,
                weight=2.0, variant=variant)


# --- regents for a child heir (spec 6.5) ------------------------------------------------------

@listen("crisis_settled")
def _regent_rules(world, event, event_id: int) -> None:
    """A regent who won rules for the child they claimed for."""
    crisis = SC.crisis_of(world.entity(event.data["occurrence"]))
    winner = event.data["winner"]
    won = SC.claimant(crisis, winner) if winner is not None else None
    if won is None or won["kind"] != "regent":
        return
    child = next((c["person"] for c in crisis["claimants"] if c["kind"] in ("chief", "blood")), None)
    if child is not None and C.age_of(world, child) < C.ADULT:  # a grown ward beaten: no regency (4g final review)
        world.update_data(event.data["faction"], regency_for=child)
        world.update_data(winner, regent_of=event.data["faction"])


def regency_events(world, n: int) -> list[Event]:
    """Each season: a regent whose ward has come of age hands the seat over, or (ambitious) fights to keep it."""
    events = []
    for faction in world.entities_after("faction", "regency_for", 0):  # asked of the save, not every faction
        child = faction.data.get("regency_for")
        if child is None or faction.data.get("dissolved") or SC.live(world, faction.id) is not None:
            continue
        leaders = C.staff(world, faction.id, ("leader",))
        regent = leaders[0] if leaders else None
        if regent is None or not alive(world, child) or C.role_in(world, child, faction.id) is None:
            events.append(Event("regency_over", (), faction.data["seat"], {"faction": faction.id}))
            continue
        if C.age_of(world, child) < C.ADULT:
            continue
        rng = rng_for(world.world_seed, f"regency:{faction.id}:{n}")
        if C.ambitious(world, regent) and rng.random() < REFUSE_HANDOVER:
            claimants = [{"person": child, "kind": "chief"}, {"person": regent, "kind": "regent"}]
            events += [Event("regency_over", (), faction.data["seat"], {"faction": faction.id})]
            events += SC.begin_events(world, faction.id, n, "regency", claimants, None)
        else:
            events += [Event("regency_over", (), faction.data["seat"], {"faction": faction.id}),
                       Event("deposed", (regent, child), faction.data["seat"], {"faction": faction.id}),
                       world_clock._promotion(world, child, faction.id, "leader", 4, None)]
    return events


@effect("regency_over")
def _regency_over(world, event) -> None:
    world.update_data(event.data["faction"], regency_for=None)


world_clock.SEASON_HOOKS.extend([absence_events, regency_events])
