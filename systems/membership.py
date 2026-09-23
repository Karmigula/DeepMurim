"""Joining factions (phase 3b spec 4, 7): who may join, trials, joining, and leaving the rolls."""

from systems import factions as F
from systems import halls
from systems.beliefs import CONF_DECAY, apparent_to, believe
from systems.facts import apparent, make_variant, place_name, record_fact
from systems.purse import payment_events
from systems.realms import realm_index
from systems.reputation import reputation
from systems.standing import believed_factions, standing
from world.events import Event, effect, listen
from world.gen.materialize import ensure_town, people_at, region_of
from world.gen.region import region_spec
from world.seed import rng_for

TRIALS = {"orthodox_sect": "spar", "school": "spar", "demonic_cult": "blood", "unorthodox_clan": "blood",
          "martial_clan": "service", "local_clan": "service", "beggars": "ears", "merchant_guild": "escort",
          "imperial": None, "bandit_fort": "chief"}
FEE, TRIBUTE, EARS = 50, 30, 3
BLOOD_DAYS = 30
WATCHES_PER_DAY = 4
LEFT = {"expelled": ("expelled", 2.0), "deserter": ("deserted", 2.0), "spy": ("spy_exposed", 2.5),
        "released": ("released", 0.5)}


def set_membership(world, person: int, faction: int, rank: int | None = None, **changes) -> None:
    current_rank, data = F.membership(world, person, faction)
    world.relate(person, faction, "member_of", current_rank if rank is None else rank, {**data, **changes})


def open_martial(world, player: int) -> int | None:
    for fid, _, data in F.memberships(world, player):
        if data.get("status", "member") == "member" and not data.get("secret") and F.is_martial(world, fid):
            return fid
    return None


def clean_record(world, town_id: int, player: int) -> bool:
    """No dark name here (Task 9 replaces this with the town's bounty)."""
    return reputation(world, town_id, apparent_to(world, town_id, player)).path != "ruthless"


def refusal(world, player: int, faction: int, town: int) -> str | None:
    """Why this faction won't begin taking the player in now, or None."""
    data = world.entity(faction).data
    kind = data["type"]
    if kind == "alliance":
        return "The Alliance takes no members; it is a council of sects."
    found = F.membership(world, player, faction)
    if found and found[1].get("status", "member") == "member":
        return "You are already one of them."
    if found:
        return "They will not have you back."
    if world.entity(player).data.get("trial"):
        return "You are already undergoing a trial."
    known_as = apparent_to(world, town, player)
    if standing(world, faction, known_as).word in ("distrusted", "enemy"):
        return "They do not trust you."
    if data["path"] == "righteous" and reputation(world, town, known_as).path == "ruthless":
        return "Your name is too dark for them."
    first = open_martial(world, player)
    if kind in F.MARTIAL and first not in (None, faction):
        return f"You already belong to the {world.entity(first).name}."
    if kind == "imperial" and (realm_index(world.entity(player).data.get("realm", "mortal")) < 1
                               or not clean_record(world, town, player)):
        return "The Bureau takes only proven fighters with clean names."
    return None


def secret_possible(world, player: int, faction: int, town: int) -> bool:
    """A second martial faction, joined in secret, if it has not heard of the first."""
    first = open_martial(world, player)
    if not F.is_martial(world, faction) or first in (None, faction) or F.membership(world, player, faction):
        return False
    if world.entity(player).data.get("trial"):
        return False
    known_as = apparent_to(world, town, player)
    if standing(world, faction, known_as).word in ("distrusted", "enemy"):
        return False
    return first not in believed_factions(world, faction, known_as)


def _blood_target(world, player: int, faction: int) -> int:
    """Someone of the faction's home region the cult wants dead (seeded)."""
    region = region_of(world, halls.seat_of(world, faction))
    members = set(F.members_of(world, faction))
    candidates = []
    for i in range(region.data["town_count"]):
        town = ensure_town(world, region.data["x"], region.data["y"], i)
        halls.settle_town(world, town)
        candidates += [p.id for p in people_at(world, town, exclude=player)
                       if p.id not in members and not p.data.get("beast") and not p.data.get("dead")]
    return rng_for(world.world_seed, f"trial:{faction}:{player}").choice(sorted(candidates))


def _errand(world, player: int, faction: int, place: int) -> tuple[int, int]:
    """A town 1-2 regions away to be reached, and how many regions that is."""
    here = world.entity(place).data
    rng = rng_for(world.world_seed, f"trial-road:{faction}:{player}")
    dx, dy = rng.choice([(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3) if (dx, dy) != (0, 0)])
    x, y = here["x"] + dx, here["y"] + dy
    town = ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))
    return town, max(abs(dx), abs(dy))


def trial_events(world, player: int, recruiter: int, faction: int, place: int, secret: bool = False) -> list[Event]:
    kind = TRIALS[world.entity(faction).data["type"]]
    trial = {"faction": faction, "kind": kind, "recruiter": recruiter, "secret": secret,
             "since": world.last_rowid("chronicle"), "target": None, "town": None, "deadline": None}
    actors = (player, recruiter)
    events: list[Event] = []
    if kind == "blood":
        target = _blood_target(world, player, faction)
        trial.update(target=target, deadline=world.time + BLOOD_DAYS * WATCHES_PER_DAY)
        actors = (player, recruiter, target)
    elif kind in ("service", "escort"):
        town, regions = _errand(world, player, faction, place)
        trial.update(town=town, deadline=world.time + (3 * regions + 7) * WATCHES_PER_DAY)
        if kind == "escort":
            events += payment_events(player, recruiter, place, FEE, "guild fee")
    return events + [Event("trial_begun", actors, place, trial)]


@effect("trial_begun")
def _trial_begun(world, event) -> None:
    world.update_data(event.actors[0], trial=dict(event.data))


def trial_done(world, player: int):
    """True when the open trial is passed, False when it has failed, None while it goes on."""
    trial = world.entity(player).data.get("trial")
    if not trial:
        return None
    kind = trial["kind"]
    if kind == "blood":
        target = world.entity(trial["target"])
        if target is not None and target.data.get("dead"):
            by_me = any(e.kind == "died" and e.actors[0] == player for e in world.chronicle_about(target.id, limit=10))
            return by_me
    if trial.get("deadline") is not None and world.time > trial["deadline"]:
        return False
    if kind in ("service", "escort"):
        return True if trial["town"] in world.targets(player, "located_in") else None
    if kind == "ears":
        told = [e for e in world.chronicle_about(player, limit=300)
                if e.kind == "told" and e.id > trial["since"] and len(e.actors) > 1
                and e.actors[1] == trial["recruiter"] and e.data.get("accepted")]
        return True if len(told) >= EARS else None
    return None


def joined_events(world, player: int, recruiter: int, faction: int, place: int, secret: bool) -> list[Event]:
    found = F.membership(world, recruiter, faction)
    hall = found[1].get("hall") if found and found[1].get("hall") is not None \
        else rng_for(world.world_seed, f"hall:{faction}:{player}").randrange(2)
    sponsor = halls.elders(world, faction).get(hall) if world.entity(faction).data["type"] in F.STAFFED else None
    actors = (player, recruiter) + ((sponsor,) if sponsor not in (None, recruiter) else ())
    return [Event("joined", actors, place, {"faction": faction, "secret": secret, "hall": hall, "sponsor": sponsor})]


@effect("joined")
def _joined(world, event) -> None:
    d = event.data
    world.relate(event.actors[0], d["faction"], "member_of", 0, {
        "role": "member", "hall": d["hall"], "sponsor": d["sponsor"], "merit": 0, "secret": d["secret"],
        "joined_at": world.time, "status": "member", "judged": [], "stipend_at": world.time})
    world.update_data(event.actors[0], trial=None)


@listen("joined")
def _joined_fact(world, event, event_id: int) -> None:
    player, recruiter = event.actors[0], event.actors[1]
    d = event.data
    me = apparent(event, player)
    story = make_variant("member_of", me, d["faction"], place=place_name(world, event.place), masked=me != player)
    fact = record_fact(world, me, "member_of", d["faction"], place=event.place, variant=story,
                       source_event=event_id, weight=1.0, spread=not d["secret"])
    if d["secret"]:  # only the recruiter and the seat's own counsel know
        believe(world, recruiter, fact, story, player, 1.0, 0, "witness")
        seat = world.entity(d["faction"]).data.get("seat")
        if seat:
            believe(world, seat, fact, story, recruiter, CONF_DECAY, 1, "told")


def trial_failed_events(player: int, place: int, faction: int) -> list[Event]:
    return [Event("trial_failed", (player,), place, {"faction": faction})]


@effect("trial_failed")
def _trial_failed(world, event) -> None:
    world.update_data(event.actors[0], trial=None)


def left_events(world, person: int, faction: int, place: int, status: str) -> list[Event]:
    kind = LEFT[status][0]
    return [Event(kind, (person,), place, {"faction": faction, "status": status})]


def _left(world, event) -> None:
    set_membership(world, event.actors[0], event.data["faction"], status=event.data["status"])


def _left_fact(world, event, event_id: int) -> None:
    person = event.actors[0]
    me = apparent(event, person)
    kind, weight = LEFT[event.data["status"]]
    record_fact(world, me, kind, event.data["faction"], place=event.place, source_event=event_id, weight=weight,
                variant=make_variant(kind, me, event.data["faction"], place=place_name(world, event.place),
                                     masked=me != person))


for _kind, _ in LEFT.values():
    effect(_kind)(_left)
    listen(_kind)(_left_fact)
