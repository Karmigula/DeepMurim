"""The player in a crisis (phase 4g spec 6.2, 6.3): declaring, swaying, claiming, championing, searching,
and the leader's token and the will changing hands.

Each rule is a `*_block` (why not, or None) and each deed a `*_events` list, as in 3b and 4e.
"""

import systems.claimants as C
import systems.duties as duties
import systems.succession_crisis as SC
import systems.testament as T
from systems import factions as F
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from systems.tournaments import alive, realm_of
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

OPEN = ("mourning", "canvass")  # the phases in which camps are still being made
SWAY = {"speak": 0.15, "gift": 0.2, "threat": 0.25, "favour": 0.3}
SPEAK_BASE, SPEAK_PER_ATTITUDE, SPEAK_BOUNDS = 0.4, 0.5, (0.1, 0.9)
GIFT_PER_RANK = 20
CLAIM_RANK = 2


def mine_here(world, player: int, town: int):
    """The live crisis of a faction the player belongs to, whose seat is this town."""
    for fid, _, data in F.memberships(world, player):
        if data.get("status", "member") != "member":
            continue
        occurrence = SC.live(world, fid)
        if occurrence is not None and occurrence.data["place"] == town:
            return occurrence
    return None


def camp_of(crisis: dict, player: int) -> int | None:
    return crisis.get("declared", {}).get(str(player))


# --- declaring and claiming -------------------------------------------------------------------

def declare_block(world, occurrence, player: int, claimant: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "The camps are made; it is too late to choose one."
    if SC.claimant(crisis, claimant) is None or not alive(world, claimant) or claimant == player:
        return "They do not claim the seat."
    if SC.claimant(crisis, player) is not None:
        return "You claim the seat yourself."
    if camp_of(crisis, player) == claimant:
        return "You already stand with them."
    if camp_of(crisis, player) is not None and str(player) in crisis.get("switched", {}):
        return "You have changed camps once; a second time and no one would trust you."
    return None


def declare_events(world, occurrence, player: int, claimant: int) -> list[Event]:
    left = camp_of(SC.crisis_of(occurrence), player)
    witnesses = (Witness(left, "wronged", 0.4),) if left is not None else ()
    return [Event("crisis_declared", (player, claimant), occurrence.data["place"],
                  {"occurrence": occurrence.id, "claimant": claimant, "left": left}, witnesses=witnesses)]


@effect("crisis_declared")
def _declared(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    player = event.actors[0]
    switched = dict(crisis.get("switched", {}))
    if event.data["left"] is not None:
        switched[str(player)] = event.data["left"]
    world.update_data(occurrence.id, data={**crisis, "declared": {**crisis.get("declared", {}),
                                                                  str(player): event.data["claimant"]},
                                           "switched": switched})


def claim_block(world, occurrence, player: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] != "mourning":
        return "Claims are made in the days of mourning; that time has passed."
    if SC.claimant(crisis, player) is not None:
        return "You already claim the seat."
    rank, _ = F.membership(world, player, crisis["faction"])
    if rank < CLAIM_RANK and world.entity(crisis["faction"]).data.get("heir") != player:
        return "Only a core disciple or better, or the named heir, may claim the seat."
    return None


def claim_events(world, occurrence, player: int) -> list[Event]:
    return [Event("crisis_claimed", (player,), occurrence.data["place"],
                  {"occurrence": occurrence.id, "faction": SC.crisis_of(occurrence)["faction"]})]


@effect("crisis_claimed")
def _claimed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    player = event.actors[0]
    world.update_data(occurrence.id, data={**crisis, "claimants": crisis["claimants"] + [{"person": player,
                                                                                          "kind": "player"}],
                                           "declared": {**crisis.get("declared", {}), str(player): player}})


@listen("crisis_claimed")
def _claimed_news(world, event, event_id: int) -> None:
    variant = make_variant("claimed_seat", event.actors[0], event.data["faction"], place=place_name(world, event.place))
    record_fact(world, event.actors[0], "claimed_seat", event.data["faction"], place=event.place,
                source_event=event_id, weight=1.5, variant=variant)


# --- swaying a voter (spec 6.2) ---------------------------------------------------------------

def sway_for(world, occurrence, player: int) -> int | None:
    """Whom the player sways for: themself if claiming, else their declared camp."""
    crisis = SC.crisis_of(occurrence)
    return player if SC.claimant(crisis, player) is not None else camp_of(crisis, player)


def sway_block(world, occurrence, player: int, voter: int, way: str) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "The camps are made; words will not move anyone now."
    if sway_for(world, occurrence, player) is None:
        return "Declare for a claimant first."
    if voter not in C.voters(world, crisis["faction"]) or SC.claimant(crisis, voter) is not None or voter == player:
        return "Their voice is not one to win."
    if crisis.get("swayed", {}).get(str(voter)) == crisis["phase"]:
        return "You have already worked on them; give it time."
    if way == "gift" and silver_of(world, player) < gift_price(world, crisis, voter):
        return f"A gift worthy of them costs {gift_price(world, crisis, voter)} silver."
    if way == "threat" and realm_of(world, voter) >= realm_of(world, player):
        return "They do not fear you."
    if way == "favour" and duties.open_duty(world, player) is not None:
        return "Finish the duty you already carry first."
    return None


def gift_price(world, crisis: dict, voter: int) -> int:
    return GIFT_PER_RANK * max(1, F.membership(world, voter, crisis["faction"])[0])


def speak_chance(world, voter: int, player: int) -> float:
    low, high = SPEAK_BOUNDS
    warmth = attitude(world, voter, apparent_to(world, voter, player)).score
    return max(low, min(high, SPEAK_BASE + SPEAK_PER_ATTITUDE * warmth))


def sway_events(world, occurrence, player: int, voter: int, way: str) -> list[Event]:
    crisis, place = SC.crisis_of(occurrence), occurrence.data["place"]
    toward = sway_for(world, occurrence, player)
    faction = world.entity(crisis["faction"])
    data = {"occurrence": occurrence.id, "voter": voter, "claimant": toward, "way": way, "delta": 0.0, "silver": 0}
    witnesses = ()
    traits = set(world.entity(voter).data.get("traits", ()))
    if way == "speak":
        rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:speak:{voter}:{crisis['phase']}")
        data["delta"] = SWAY["speak"] if rng.random() < speak_chance(world, voter, player) else 0.0
    elif way == "gift":
        data["silver"] = gift_price(world, crisis, voter)
        if "loyal" in traits and faction.data.get("path") == "righteous":
            data["silver"], witnesses = 0, (Witness(voter, "annoyed", 0.25),)  # refused, and taken amiss
        else:
            data["delta"] = SWAY["gift"] * (2 if "greedy" in traits or faction.data.get("path") == "ruthless" else 1)
    elif way == "threat":
        data["delta"], witnesses = SWAY["threat"], (Witness(voter, "wronged", 0.5),)
    elif way == "favour":
        events = duties.issue_events(world, player, crisis["faction"], voter, place, kind="deliver")
        events[0].data["favour"] = {"occurrence": occurrence.id, "voter": voter, "claimant": toward}
        return events + [Event("crisis_swayed", (player, voter), place, {**data, "delta": 0.0})]
    return [Event("crisis_swayed", (player, voter), place, data, witnesses=witnesses)]


@effect("crisis_swayed")
def _swayed(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    crisis = SC.crisis_of(occurrence)
    sways = {k: dict(v) for k, v in crisis.get("sways", {}).items()}
    mine = sways.setdefault(str(d["voter"]), {})
    mine[str(d["claimant"])] = round(mine.get(str(d["claimant"]), 0.0) + d["delta"], 3)
    swayed = {**crisis.get("swayed", {}), str(d["voter"]): crisis["phase"]}
    world.update_data(occurrence.id, data={**crisis, "sways": sways, "swayed": swayed})
    if d["silver"]:
        player = event.actors[0]
        world.update_data(player, silver=silver_of(world, player) - d["silver"])
        world.update_data(d["voter"], silver=silver_of(world, d["voter"]) + d["silver"])


@listen("duty_done")
def _favour_done(world, event, event_id: int) -> None:
    """A favour done within the canvass wins the voter's lean (spec 6.2)."""
    favour = world.entity(event.data["duty"]).data.get("favour")
    if not favour:
        return
    occurrence = world.entity(favour["occurrence"])
    if occurrence is None or SC.crisis_of(occurrence)["phase"] not in OPEN:
        return
    commit(world, [Event("crisis_swayed", (event.actors[0], favour["voter"]), occurrence.data["place"],
                         {"occurrence": occurrence.id, "voter": favour["voter"], "claimant": favour["claimant"],
                          "way": "favour_done", "delta": SWAY["favour"], "silver": 0})])


# --- champions, the trial, the chambers -------------------------------------------------------

def champion_block(world, occurrence, player: int, claimant: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "The contest is already upon them."
    if camp_of(crisis, player) != claimant or claimant == player:
        return "Stand with them first."
    if crisis.get("champions", {}).get(str(claimant)) == player:
        return "You are already their champion."
    return None


def champion_events(world, occurrence, player: int, claimant: int) -> list[Event]:
    return [Event("crisis_champion", (player, claimant), occurrence.data["place"],
                  {"occurrence": occurrence.id, "claimant": claimant},
                  witnesses=(Witness(claimant, "respect", 0.4),))]


@effect("crisis_champion")
def _champion(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "champions": {**crisis.get("champions", {}),
                                                                  str(event.data["claimant"]): event.actors[0]}})


def my_trial(world, occurrence, player: int) -> tuple[int, int] | None:
    """(the player's side, the opposing champion) if a pending trial waits for the player."""
    trial = SC.crisis_of(occurrence).get("trial") or {}
    if not trial.get("pending"):
        return None
    for side, other in ((trial["a"], trial["b"]), (trial["b"], trial["a"])):
        if trial["champions"][str(side)] == player:
            return side, trial["champions"][str(other)]
    return None


def trial_result_events(world, occurrence, player: int, won: bool) -> list[Event]:
    side, _ = my_trial(world, occurrence, player)
    trial = SC.crisis_of(occurrence)["trial"]
    other = trial["b"] if side == trial["a"] else trial["a"]
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:trial:played")
    return SC.trial_events(world, occurrence, trial, side if won else other, rng)


def search_block(world, occurrence, player: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] != "canvass":
        return "The late master's rooms are sealed but in the canvass."
    if crisis.get("searched", {}).get(str(player)) == SC.lives.current_season(world):
        return "You searched them this season."
    return None


def search_events(world, occurrence, player: int) -> list[Event]:
    crisis = SC.crisis_of(occurrence)
    season = SC.lives.current_season(world)
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:chambers:{player}:{season}")
    found = (crisis.get("will") or {}).get("state") == "hidden" and rng.random() < T.search_chance(world, player)
    return [Event("chambers_searched", (player,), occurrence.data["place"],
                  {"occurrence": occurrence.id, "found": found, "season": season})]


@effect("chambers_searched")
def _searched(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    player = event.actors[0]
    will = crisis.get("will") or {}
    if event.data["found"]:
        will = {**will, "state": "held", "holder": player}  # the player keeps it until they choose
    world.update_data(occurrence.id, data={**crisis, "will": will,
                                           "searched": {**crisis.get("searched", {}),
                                                        str(player): event.data["season"]}})


def will_events(world, occurrence, player: int, burn: bool) -> list[Event]:
    will = SC.crisis_of(occurrence).get("will") or {}
    if will.get("holder") != player or will.get("state") != "held":
        return []
    return [Event("will_burned" if burn else "will_revealed", (player,), occurrence.data["place"],
                  {"occurrence": occurrence.id, "names": will.get("names")})]


@effect("will_revealed")
def _revealed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "will": {**crisis["will"], "state": "read", "holder": None}})


@effect("will_burned")
def _burned(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "will": {**crisis["will"], "state": "burned", "holder": None}})


@listen("will_burned")
def _burned_news(world, event, event_id: int) -> None:
    """Burned where others saw it, it is a tale (spec 4.4)."""
    if len(people_at(world, event.place, exclude=event.actors[0])) == 0:
        return
    faction = SC.crisis_of(world.entity(event.data["occurrence"]))["faction"]
    variant = make_variant("will_burned", event.actors[0], faction, place=place_name(world, event.place))
    record_fact(world, event.actors[0], "will_burned", faction, place=event.place, source_event=event_id,
                weight=2.0, variant=variant)


def will_duel_result_events(world, occurrence, player: int, won: bool) -> list[Event]:
    if not won:
        return []
    return [Event("will_taken", (player,), occurrence.data["place"], {"occurrence": occurrence.id})]


@effect("will_taken")
def _will_taken(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "will": {**crisis["will"], "state": "held",
                                                              "holder": event.actors[0]}})


# --- the leader's token, anywhere (spec 4.5, 6.3) ---------------------------------------------

def token_price(world, token: int) -> int:
    faction = world.entity(world.entity(token).data["faction"])
    return T.TOKEN_PRICE * int(faction.data.get("power", 50))


def claimant_in(world, person: int, faction: int) -> bool:
    occurrence = SC.live(world, faction)
    return occurrence is not None and SC.claimant(SC.crisis_of(occurrence), person) is not None


def buy_block(world, token: int, player: int, holder: int) -> str | None:
    if T.holder(world, token) != holder or holder == player:
        return "They do not hold it."
    if claimant_in(world, holder, world.entity(token).data["faction"]):
        return "A claimant will not part with it at any price."
    if silver_of(world, player) < token_price(world, token):
        return f"They want {token_price(world, token)} silver for it."
    return None


def token_events(world, token: int, player: int, place: int, how: str, other: int | None = None) -> list[Event]:
    """`how`: bought from `other`, taken where it lies, won from `other` in a duel, handed to claimant `other`."""
    price = token_price(world, token)
    kind = {"bought": "sect_token_bought", "taken": "sect_token_taken", "won": "sect_token_won",
            "handed": "sect_token_handed"}[how]
    actors = (player,) if other is None else (player, other)
    silver = price if how == "bought" else (price if how == "handed" and silver_of(world, other) >= price else 0)
    witnesses = (Witness(other, "grateful", 0.8, True),) if how == "handed" else ()
    return [Event(kind, actors, place, {"token": token, "silver": silver}, witnesses=witnesses)]


def _moved(world, event, to: int) -> None:
    T.put(world, event.data["token"], owner=to)


@effect("sect_token_bought")
def _bought(world, event) -> None:
    player, holder = event.actors
    _moved(world, event, player)
    world.update_data(player, silver=silver_of(world, player) - event.data["silver"])
    world.update_data(holder, silver=silver_of(world, holder) + event.data["silver"])


@effect("sect_token_taken")
def _taken(world, event) -> None:
    _moved(world, event, event.actors[0])


@effect("sect_token_won")
def _won(world, event) -> None:
    _moved(world, event, event.actors[0])


@effect("sect_token_handed")
def _handed(world, event) -> None:
    player, claimant = event.actors
    _moved(world, event, claimant)
    if event.data["silver"]:
        world.update_data(claimant, silver=silver_of(world, claimant) - event.data["silver"])
        world.update_data(player, silver=silver_of(world, player) + event.data["silver"])


def tokens_lying_at(world, town: int) -> list[int]:
    return [t for t in world.sources(town, "located_in") if world.entity(t).kind == "treasure"
            and world.entity(t).data.get("kind") == "sect_token"]


def tokens_held_by(world, person: int) -> list[int]:
    return [t for t in world.targets(person, "owns") if world.entity(t).kind == "treasure"
            and world.entity(t).data.get("kind") == "sect_token"]
