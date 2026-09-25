"""Succession crises (phase 4g spec 3-4): a leader's death with the seat in doubt becomes a contest.

The faction clock asks `leaderless_events` before it promotes a new leader. With no doubt the 4a
handover stands (the named heir first); with doubt a `succession_crisis` occurrence starts at the seat
and the clock leaves the leader's post empty until the crisis is settled.

The 4d stages carry fixed names: `announced` is the mourning, `active` the canvass, and the contest is
decided when the `aftermath` begins (plan ruling 1).
"""

import systems.claimants as C
import systems.sky as sky
import systems.world_events as W
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.tournaments import alive, realm_of
from world.events import Event, effect, listen

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
    for fid, _, data in F.memberships(world, victim):
        faction = world.entity(fid)
        if data.get("role") == "leader" and faction.data.get("type") in F.STAFFED \
                and not faction.data.get("dissolved"):
            world.update_data(fid, fallen={"leader": victim, "cause": event.data.get("cause"), "place": event.place,
                                           "killer": killer if killer != victim else None, "time": world.time})


def doubt(world, faction: int) -> str | None:
    """Why the seat is in doubt, or None (spec 3.1; the `close` rule as plan ruling 2 sets it)."""
    data = world.entity(faction).data
    fallen = data.get("fallen") or {}
    if fallen.get("cause") in VIOLENT:
        return "violence"
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
                 force: bool = False) -> list[Event] | None:
    """A crisis starts at the seat, played in full when near (or `force`d: the player's own sect), else settled in a line."""
    seat = world.entity(faction).data["seat"]
    if not force and not near(world, faction):
        return None  # far from the player: 4a's handover, until Task 3 settles it in a line
    crisis = {"faction": faction, "leader": leader, "cause": cause, "claimants": claimants, "declared": {},
              "sways": {}, "champions": {}, "will": None, "token": None, "transmitted": None, "trial": None,
              "strife": None, "outcome": None, "phase": "mourning", "season": n}
    player = world.get_meta("player_id")
    if any(c["person"] == player for c in claimants):
        crisis["declared"] = {str(player): player}
    starts = max(n * W.SEASON, world.time - W.SEASON) if force else n * W.SEASON
    return sky.start_events(world, KIND, seat, starts, crisis) or None  # long over: 4a's handover after all


@listen("sky_started")
def _begun(world, event, event_id: int) -> None:
    if event.data["type"] != KIND:
        return
    row = next(r for r in reversed(W.index(world)) if r[W.TYPE] == KIND and r[W.PLACE] == event.data["place"])
    faction = event.data["data"]["faction"]
    world.update_data(faction, crisis=row[W.ID], fallen=None)


# --- the stages -------------------------------------------------------------------------------

def on_stage(world, occurrence, stage: str) -> list[Event]:
    crisis = crisis_of(occurrence)
    if crisis["phase"] == "settled":
        return []
    if stage == "announced":
        return [Event("crisis_heralded", (), occurrence.data["place"], {"occurrence": occurrence.id})]
    if stage == "active":
        return [Event("crisis_phase", (), occurrence.data["place"], {"occurrence": occurrence.id, "phase": "canvass"})]
    return []


@effect("crisis_phase")
def _phase(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**crisis_of(occurrence), "phase": event.data["phase"]})


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
