"""Succession crises (phase 4g spec 3-4): a leader's death with the seat in doubt becomes a contest.

The faction clock asks `leaderless_events` before it promotes a new leader. With no doubt the 4a
handover stands (the named heir first); with doubt a `succession_crisis` occurrence starts at the seat
and the clock leaves the leader's post empty until the crisis is settled.

The 4d stages carry fixed names: `announced` is the mourning, `active` the canvass, and the contest is
decided when the `aftermath` begins (plan ruling 1).
"""

import systems.claimants as C
import systems.lives as lives
import systems.sky as sky
import systems.testament as T
import systems.world_events as W
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.tournaments import alive, realm_of
from systems.membership import set_membership
from systems.world_clock import _promotion
from world.events import Event, Witness, commit, effect, listen
from world.seed import rng_for

KIND = "succession_crisis"
VIOLENT = frozenset({"killed", "executed", "feud", "clash", "raid"})
PHASES = ("mourning", "canvass", "contest", "strife", "settled")


def live(world, faction: int):
    """The faction's crisis occurrence, if one is not yet settled."""
    found = world.entity(faction).data.get("crisis")
    occurrence = world.entity(found) if found is not None else None
    if occurrence is None or occurrence.data["data"].get("phase") == "settled":
        return None
    return occurrence


def crisis_of(occurrence) -> dict:
    return occurrence.data["data"]


# --- the fallen leader (spec 3.1) -------------------------------------------------------------

@listen("died")
def _fallen(world, event, event_id: int) -> None:
    """How a leader died is what later puts the seat in doubt: remembered on the faction."""
    killer, victim = event.actors[0], event.actors[-1]
    rows = F.memberships(world, victim)  # one lookup serves the fall and the testament (4g minors)
    for fid, _, data in rows:
        faction = world.entity(fid)
        if data.get("role") == "leader" and faction.data.get("type") in F.STAFFED \
                and not faction.data.get("dissolved"):
            world.update_data(fid, fallen={"leader": victim, "cause": event.data.get("cause"), "place": event.place,
                                           "killer": killer if killer != victim else None, "time": world.time})
    T.last_breath(world, event, rows)


def doubt(world, faction: int) -> str | None:
    """Why the seat is in doubt, or None (spec 3.1; the `close` rule as plan ruling 2 sets it)."""
    data = world.entity(faction).data
    fallen = data.get("fallen") or {}
    if fallen.get("cause") in VIOLENT:
        return "violence"
    if data.get("poisoned") is not None:
        return "suspicion"  # whispers of poison (phase 4h)
    if fallen and fallen.get("place") is not None and fallen.get("place") != data.get("seat"):
        return "token"
    heir = data.get("heir")
    elders = C.staff(world, faction, ("elder",))
    if isinstance(heir, int):
        if not C.fit(world, heir, faction):
            return "heir"
        if any(C.ambitious(world, e) and realm_of(world, e) > realm_of(world, heir) for e in elders):
            return "close"  # an ambitious elder stands above the chief disciple (plan ruling 2)
        return None
    ranked = sorted((realm_of(world, p) for p in elders or C.staff(world, faction, ("keeper",))), reverse=True)
    if len(ranked) >= 2 and ranked[0] - ranked[1] <= 1:
        return "close"
    return None


# --- the clock's question (spec 3.1) ----------------------------------------------------------

def near(world, faction: int) -> bool:
    """Played in full where the player can reach it (spec 2.4): the seat's region, or a faction of theirs."""
    player = world.get_meta("player_id")
    if not isinstance(player, int):
        return False
    found = F.membership(world, player, faction)
    if found and found[1].get("status", "member") == "member":
        return True
    here = world.targets(player, "located_in")
    seat = world.entity(faction).data.get("seat")
    return bool(here) and seat is not None and W.place_xy(world, here[0]) == W.place_xy(world, seat)


def leaderless_events(world, faction: int, n: int) -> list[Event] | None:
    """None: 4a promotes as it always has. A list: a crisis holds the seat (maybe starting it now)."""
    if live(world, faction) is not None:
        return []
    cause = doubt(world, faction)
    if cause is None:
        return None
    leader = (world.entity(faction).data.get("fallen") or {}).get("leader")
    claimants = C.declare(world, faction, leader)
    if len(claimants) < 2:
        return None  # one claim, or none: no contest (spec 4.1)
    return begin_events(world, faction, n, cause, claimants, leader)


def begin_events(world, faction: int, n: int, cause: str, claimants: list[dict], leader: int | None,
                 force: bool = False) -> list[Event]:
    """A crisis starts at the seat, played in full when near (or `force`d: the player's own sect), else settled in a line."""
    seat = world.entity(faction).data["seat"]
    summary = [Event("crisis_summarised", (), seat, {"faction": faction, "season": n, "cause": cause,
                                                      "leader": leader, "claimants": claimants})]
    if not force and not near(world, faction):
        return summary  # far from the player: settled in a line (spec 2.4)
    crisis = {"faction": faction, "leader": leader, "cause": cause, "claimants": claimants, "declared": {},
              "sways": {}, "champions": {}, "will": None, "token": None, "transmitted": None, "trial": None,
              "strife": None, "outcome": None, "phase": "mourning", "season": n}
    player = world.get_meta("player_id")
    if any(c["person"] == player for c in claimants):
        crisis["declared"] = {str(player): player}
    starts = max(n * W.SEASON, world.time - W.SEASON) if force else n * W.SEASON
    return sky.start_events(world, KIND, seat, starts, crisis) or summary  # long over: settled in a line


@listen("sky_started")
def _begun(world, event, event_id: int) -> None:
    if event.data["type"] != KIND:
        return
    row = next(r for r in reversed(W.index(world)) if r[W.TYPE] == KIND and r[W.PLACE] == event.data["place"])
    faction = event.data["data"]["faction"]
    plots = [p for p in [world.entity(faction).data.get("poisoned")] if p is not None]
    world.update_data(faction, crisis=row[W.ID], fallen=None, poisoned=None)
    occurrence = world.entity(row[W.ID])
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:mourning")
    world.update_data(occurrence.id, data={**T.at_mourning(world, crisis_of(occurrence), rng), "plots": plots})
    from systems.plots import crisis_begun  # phase 4h: puppets backed, and whatever else a crisis draws in
    crisis_begun(world, world.entity(occurrence.id))


# --- the stages -------------------------------------------------------------------------------

def on_stage(world, occurrence, stage: str) -> list[Event]:
    crisis = crisis_of(occurrence)
    if crisis["phase"] == "settled":
        return []
    if stage == "announced":
        return [Event("crisis_heralded", (), occurrence.data["place"], {"occurrence": occurrence.id})]
    if stage == "active":
        return [Event("crisis_phase", (), occurrence.data["place"], {"occurrence": occurrence.id, "phase": "canvass"})]
    if stage == "aftermath":
        return [Event("crisis_phase", (), occurrence.data["place"], {"occurrence": occurrence.id, "phase": "contest"})]
    if stage == "over" and (crisis.get("trial") or {}).get("pending"):
        return forfeit_events(world, occurrence)  # the days passed and the player never came to the trial
    return []


def _searched(world, occurrence, stage: str) -> None:
    """The camps turn the late master's rooms over at each stage's change (spec 4.4)."""
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:search:{stage}")
    world.update_data(occurrence.id, data=T.camps_search(world, crisis_of(occurrence), rng))


@effect("crisis_phase")
def _phase(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**crisis_of(occurrence), "phase": event.data["phase"]})
    _searched(world, world.entity(occurrence.id), event.data["phase"])


@listen("crisis_heralded")
def _heralded(world, event, event_id: int) -> None:
    """The heralds cry it: the seat is empty and these claim it (spec 5)."""
    occurrence = world.entity(event.data["occurrence"])
    crisis = crisis_of(occurrence)
    people = [c["person"] for c in crisis["claimants"]]
    variant = make_variant("crisis", people[0], crisis["faction"], place=place_name(world, event.place))
    variant.update(stage="mourning", people=people, kinds=[c["kind"] for c in crisis["claimants"]])
    record_fact(world, people[0], "crisis", crisis["faction"], place=event.place, source_event=event_id,
                weight=2.0, variant=variant, extra={"occurrence": occurrence.id})


def claimant(crisis: dict, person: int) -> dict | None:
    return next((c for c in crisis["claimants"] if c["person"] == person), None)


def standing_claimants(world, crisis: dict) -> list[dict]:
    """Claimants still able to take the seat: alive and not sealed in a realm."""
    return [c for c in crisis["claimants"] if alive(world, c["person"])
            and not world.entity(c["person"]).data.get("sealed_in")]


# --- the contest (spec 4.6, 4.9) --------------------------------------------------------------

REFUSE_CHANCE = 0.5
PROUD = frozenset({"proud", "hot-tempered"})
TRIAL_BOUNDS = (0.1, 0.9)
FAR_PROOF, FAR_REALM = 0.5, 0.3


@listen("crisis_phase")
def _contest(world, event, event_id: int) -> None:
    if event.data["phase"] == "contest":
        commit(world, decide_events(world, world.entity(event.data["occurrence"])))


def champion(world, crisis: dict, person: int, camp: list[int]) -> int:
    """Who fights for a claimant: whom they named (the player, spec 6.2), the player if the claimant,
    else the strongest of the camp."""
    named = crisis.get("champions", {}).get(str(person))
    if named is not None and alive(world, named):
        return named
    if world.entity(person).data.get("is_player"):
        return person
    fighters = [p for p in camp if not world.entity(p).data.get("is_player") and alive(world, p)] or [person]
    return max(fighters, key=lambda p: (realm_of(world, p), p == person, -p))


def trial_chance(world, a: int, b: int) -> float:
    """The first fighter's chance: realm decides, with upsets (4e plan ruling 7)."""
    low, high = TRIAL_BOUNDS
    return max(low, min(high, 0.5 + 0.15 * (realm_of(world, a) - realm_of(world, b))))


def decide_events(world, occurrence) -> list[Event]:
    """The contest: a camp with more than half of all votes takes the seat; else the two largest fight."""
    if crisis_of(occurrence)["phase"] != "contest":
        return []
    from systems.plots import contest_exposures  # phase 4h: what the knowing lay before the elders first
    contest_exposures(world, occurrence)
    occurrence = world.entity(occurrence.id)
    crisis, place = crisis_of(occurrence), occurrence.data["place"]
    standing = standing_claimants(world, crisis)
    if len(standing) <= 1:
        return settle_events(world, occurrence, standing[0]["person"] if standing else None, "unopposed")
    backing, undecided = C.camps(world, crisis)
    fallen = [c["person"] for c in crisis["claimants"] if c not in standing]
    undecided = list(undecided) + [b for p in fallen for b in backing.get(p, []) if b != p]  # no one's votes now
    tally = C.votes(world, crisis, {c["person"]: backing[c["person"]] for c in standing})
    total = sum(tally.values()) + len(undecided)
    ranked = sorted(tally, key=lambda p: (-tally[p], -realm_of(world, p), p))
    if tally[ranked[0]] * 2 > total:
        return settle_events(world, occurrence, ranked[0], "backing")
    from systems.legitimacy import arbitration_events  # phase 4h: an arbiter may rule before any trial
    ruled = arbitration_events(world, occurrence, standing, ranked)
    if ruled:
        return ruled
    a, b = ranked[:2]
    fighters = {str(a): champion(world, crisis, a, backing[a]), str(b): champion(world, crisis, b, backing[b])}
    trial = {"a": a, "b": b, "champions": fighters, "winner": None, "pending": False}
    player = world.get_meta("player_id")
    if player in fighters.values():
        waiting = a if fighters[str(a)] == player else b  # the side the player fights for (4g final review)
        return [Event("crisis_trial", (), place, {"occurrence": occurrence.id,
                                                  "trial": {**trial, "pending": True, "waiting": waiting}})]
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:trial")
    winner = a if rng.random() < trial_chance(world, fighters[str(a)], fighters[str(b)]) else b
    return trial_events(world, occurrence, trial, winner, rng)


def trial_events(world, occurrence, trial: dict, winner: int, rng) -> list[Event]:
    """The trial fought: the winner takes the seat, unless a proud loser refuses (then force of arms, Task 4)."""
    place = occurrence.data["place"]
    loser = trial["b"] if winner == trial["a"] else trial["a"]
    fighters = (trial["champions"][str(winner)], trial["champions"][str(loser)])
    events = [Event("crisis_trial", fighters, place,
                    {"occurrence": occurrence.id, "trial": {**trial, "winner": winner, "pending": False}})]
    if PROUD & set(world.entity(loser).data.get("traits", ())) and rng.random() < REFUSE_CHANCE:
        return events + [Event("crisis_refused", (loser, winner), place, {"occurrence": occurrence.id})]
    return events + settle_events(world, occurrence, winner, "trial")


def forfeit_events(world, occurrence) -> list[Event]:
    """The player's side never came to the trial: the other side wins it."""
    trial = crisis_of(occurrence)["trial"]
    waiting = trial.get("waiting", trial["a"] if trial["champions"][str(trial["a"])] == world.get_meta("player_id")
                        else trial["b"])
    other = trial["b"] if waiting == trial["a"] else trial["a"]
    foe = trial["champions"][str(other)]
    winner = waiting if not alive(world, foe) and alive(world, waiting) else other  # a dead foe cannot win it
    return trial_events(world, occurrence, trial, winner, rng_for(world.world_seed, f"crisis:{occurrence.id}:forfeit"))


@effect("crisis_trial")
def _trial(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**crisis_of(occurrence), "trial": event.data["trial"]})


@effect("crisis_refused")
def _refused(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**crisis_of(occurrence), "phase": "strife",
                                           "strife": {"a": event.actors[1], "b": event.actors[0], "seasons": 0}})


def settle_events(world, occurrence, winner, how: str) -> list[Event]:
    """The seat is filled: the winner leads, each other claimant remembers who beat them (spec 4.9)."""
    crisis, place = crisis_of(occurrence), occurrence.data["place"]
    faction = crisis["faction"]
    if winner is not None and not alive(world, winner):  # the dead take no seat: the living claimants' best
        standing = standing_claimants(world, crisis)
        winner = standing[0]["person"] if standing else None
    if winner is None:  # every claimant fell: the elders put forward one of their own
        winner = C._best(world, C.staff(world, faction, ("elder",)) or C.staff(world, faction, ("keeper",)))
        how = "chosen"
    losers = [c["person"] for c in crisis["claimants"] if c["person"] != winner and alive(world, c["person"])]
    events = [Event("crisis_settled", (winner,) if winner is not None else (), place,
                    {"occurrence": occurrence.id, "faction": faction, "winner": winner, "how": how, "losers": losers})]
    if winner is None:
        return events
    events += [Event("crisis_lost", (winner, loser), place, {"faction": faction},
                     witnesses=(Witness(loser, "wronged", 0.6),)) for loser in losers]
    events += [Event("deposed", (holder, winner), place, {"faction": faction})  # a holder who lost the seat
               for holder in C.staff(world, faction, ("leader",)) if holder != winner]
    return events + [_promotion(world, winner, faction, "leader", 4, None)]


@effect("deposed")
def _deposed(world, event) -> None:
    holder = event.actors[0]
    player = world.entity(holder).data.get("is_player")
    set_membership(world, holder, event.data["faction"], rank=3, role="member" if player else "elder",
                   regent_for=None)


@effect("crisis_settled")
def _settled(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    crisis = crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "phase": "settled",
                                           "outcome": {"leader": d["winner"], "how": d["how"], "schism": None}})
    _record(world, d["faction"], crisis["claimants"], d["winner"], d["how"])
    world.update_data(d["faction"], crisis=None)


def _record(world, faction: int, claimants: list[dict], winner, how: str, schism=None) -> None:
    data = world.entity(faction).data
    line = {"season": lives.current_season(world), "claimants": [c["person"] for c in claimants],
            "winner": winner, "how": how, "schism": schism}
    world.update_data(faction, history=list(data.get("history", [])) + [line], fallen=None)


@listen("crisis_settled")
def _settled_news(world, event, event_id: int) -> None:
    d = event.data
    crisis = crisis_of(world.entity(d["occurrence"]))
    _told(world, event.place, event_id, d["winner"], d["faction"], [c["person"] for c in crisis["claimants"]], d["how"])


def _told(world, place: int, event_id: int, winner, faction: int, people: list[int], how: str) -> None:
    if winner is None:
        return
    variant = make_variant("crisis", winner, faction, place=place_name(world, place))
    variant.update(stage="settled", people=people, how=how)
    record_fact(world, winner, "crisis", faction, place=place, source_event=event_id, weight=2.5, variant=variant)


# --- far away (spec 2.4, 4.6) -----------------------------------------------------------------

@listen("crisis_summarised")
def _summarised(world, event, event_id: int) -> None:
    """Nobody near: the crisis is settled in a line, weighed by proofs and realms."""
    d = event.data
    faction, rng = d["faction"], rng_for(world.world_seed, f"crisis:{d['faction']}:{d['season']}:far")
    crisis = T.at_mourning(world, {"faction": faction, "leader": d["leader"], "claimants": d["claimants"]}, rng,
                           far=True)
    standing = standing_claimants(world, crisis)
    if not standing:
        return
    weakest = min(realm_of(world, c["person"]) for c in standing)
    weights = [1 + FAR_PROOF * len(C.proofs(world, crisis, c)) + FAR_REALM * (realm_of(world, c["person"]) - weakest)
               for c in standing]
    winner = rng.choices([c["person"] for c in standing], weights=weights)[0]
    losers = [c["person"] for c in standing if c["person"] != winner]
    commit(world, [Event("crisis_lost", (winner, loser), event.place, {"faction": faction},
                         witnesses=(Witness(loser, "wronged", 0.6),)) for loser in losers]
           + [Event("deposed", (holder, winner), event.place, {"faction": faction})  # 4g final review
              for holder in C.staff(world, faction, ("leader",)) if holder != winner]
           + [_promotion(world, winner, faction, "leader", 4, None)])
    _record(world, faction, d["claimants"], winner, "far")
    _told(world, event.place, event_id, winner, faction, [c["person"] for c in d["claimants"]], "far")
    from systems.schism import far_strife  # a close contest far away may come to arms (Task 4)
    far_strife(world, event, crisis, standing, weights, winner, rng)
