"""Heart demons (phase 5e spec 3): guilt, grudges, fear and grief, gathered from what befalls the heart, laid to
rest by deeds, and risen at a breakthrough to be faced, buried, or turned back from.

A demon is `{kind, whom, weight, since}` in the heart's `demons`, at most five. Only the player gathers demons
from events; an NPC's are read in their seeded heart (systems/heart_world.py).
"""

import systems.heart as HT
import systems.lives as lives
import systems.world_clock as world_clock
from systems.bodies import load_body, save_body
from systems.purse import silver_of
from world.events import Event, commit, effect, listen
from world.seed import rng_for

KINDS = ("guilt", "grudge", "fear", "grief")
MAX_DEMONS, MAX_WEIGHT = 5, 3
TRIAL_REALM = 2            # a breakthrough to Second-rate or beyond calls the heaviest demon up
FACE_BASE, FACE_BOUNDS = 0.3, (0.1, 0.9)
FACED_STEADY, FACED_INSIGHT, FAILED_DEVIATION = 10.0, 10.0, 20.0
BURIED_STEADY, BURIED_SHIFT = -5.0, -0.1
GRIEF_YEARS = 3
AMENDS = 100               # silver to the dead one's kin, a weight of guilt eased
STIR_CHANCE, STIR_DEVIATION = 0.05, 10.0  # a shaken heart's worst demon stirs at meditation, a week at a time
GRIEF_WEIGHT = {"child": 3, "spouse": 3, "parent": 3, "master": 2, "disciple": 2, "sworn_sibling": 2}
CHOICES = ("face", "bury", "turn_back")


def demons(world, person: int) -> list[dict]:
    return list(HT.heart_of(world, person)["demons"])


def add_demon(world, person: int, kind: str, whom, weight: int) -> None:
    """A demon gathered; one already carried for the same cause grows instead. The lightest goes past five."""
    found = demons(world, person)
    same = next((d for d in found if d["kind"] == kind and d["whom"] == whom), None)
    if same is not None:
        same["weight"] = min(MAX_WEIGHT, same["weight"] + weight)
    else:
        found.append({"kind": kind, "whom": whom, "weight": min(MAX_WEIGHT, weight), "since": world.time})
        if len(found) > MAX_DEMONS:
            found.remove(min(found, key=lambda d: (d["weight"], -d["since"])))
    HT.write(world, person, demons=found)


def ease(world, person: int, kind: str, whom=None, by: int = MAX_WEIGHT, every: bool = False) -> bool:
    """Lighten a demon (the heaviest of the kind, or the one for `whom`); at no weight it is laid to rest."""
    found = demons(world, person)
    matches = [d for d in found if d["kind"] == kind and (whom is None or d["whom"] == whom)]
    if not matches:
        return False
    for d in (matches if every else [max(matches, key=lambda d: (d["weight"], -d["since"]))]):
        d["weight"] -= by
        if d["weight"] <= 0:
            found.remove(d)
    HT.write(world, person, demons=found)
    return True


def heaviest(world, person: int) -> dict | None:
    found = demons(world, person)
    return max(found, key=lambda d: (d["weight"], -d["since"])) if found else None


def _player(world) -> int | None:
    return world.get_meta("player_id")


# --- gathered and laid to rest ---------------------------------------------------------------------------------

@listen("duel_ended")
def _from_duel(world, event, event_id: int) -> None:
    d, (player, foe) = event.data, event.actors
    if world.entity(foe).data.get("beast"):
        return
    if d.get("result") == "won" and d.get("by") == "player":
        ease(world, player, "grudge", foe)  # beaten: the grudge is spent
        if d.get("life_and_death"):
            ease(world, player, "fear", every=True)
        if d.get("verdict") == "kill" and d.get("reason") == "yielded":
            add_demon(world, player, "guilt", foe, 2)
    elif d.get("result") == "lost" and d.get("by") == "opponent" and not d.get("player_killed"):
        weight = 3 if d.get("left_for_dead") else 2 if d.get("crippled") else 1 if d.get("verdict") == "rob" else 0
        if weight:
            add_demon(world, player, "grudge", foe, weight)
        if d.get("left_for_dead"):
            add_demon(world, player, "fear", None, 2)


@listen("died")
def _from_death(world, event, event_id: int) -> None:
    player, victim = _player(world), event.actors[-1]
    if player is None or victim == player or world.entity(player).data.get("dead"):
        return
    ease(world, player, "grudge", victim)  # the one you hated is gone
    for kin, _, data in world.relations_from(player, "kin_of"):
        if kin == victim:
            add_demon(world, player, "grief", victim, GRIEF_WEIGHT.get(data.get("role"), 1))


@listen("deserted")
@listen("spy_exposed")
def _from_betrayal(world, event, event_id: int) -> None:
    if event.actors[0] == _player(world):
        add_demon(world, event.actors[0], "guilt", event.data["faction"], 2)


@listen("tribulation")
def _from_tribulation(world, event, event_id: int) -> None:
    if event.actors[0] == _player(world) and event.data.get("outcome") == "crippled":
        add_demon(world, event.actors[0], "fear", None, 2)


@listen("healed")
def _from_healing(world, event, event_id: int) -> None:
    if event.actors[0] == _player(world):
        ease(world, event.actors[0], "guilt", by=1)


def grief_passes(world, person: int) -> None:
    """Three years ease any grief (each season, for the player)."""
    for d in demons(world, person):
        if d["kind"] == "grief" and world.time - d["since"] >= GRIEF_YEARS * 4 * lives.SEASON:
            ease(world, person, "grief", d["whom"])


def season_hook(world, n: int) -> list[Event]:
    player = _player(world)
    if player is not None and world.entity(player) is not None and world.entity(player).data.get("heart"):
        grief_passes(world, player)
    return []


world_clock.SEASON_HOOKS.append(season_hook)


# --- respects and amends ---------------------------------------------------------------------------------------

def respects_block(world, person: int, dead: int, place) -> str | None:
    if not any(d["kind"] == "grief" and d["whom"] == dead for d in demons(world, person)):
        return "You carry no grief for them."
    if place not in world.targets(dead, "buried_at"):
        return "They do not lie here."
    return None


def respects_events(world, person: int, dead: int, place) -> list[Event]:
    return [Event("paid_respects", (person, dead), place, {})]


@effect("paid_respects")
def _respects(world, event) -> None:
    ease(world, event.actors[0], "grief", event.actors[1])


def amends_block(world, person: int, kin: int) -> str | None:
    wronged = {d["whom"] for d in demons(world, person) if d["kind"] == "guilt"}
    if not any(k in wronged for k, _, _ in world.relations_from(kin, "kin_of")):
        return "You owe them nothing."
    if silver_of(world, person) < AMENDS:
        return f"Amends of {AMENDS} silver are more than you carry."
    return None


def amends_events(world, person: int, kin: int, place) -> list[Event]:
    wronged = {d["whom"] for d in demons(world, person) if d["kind"] == "guilt"}
    dead = next(k for k, _, _ in world.relations_from(kin, "kin_of") if k in wronged)
    return [Event("amends_made", (person, kin), place, {"for": dead, "silver": AMENDS})]


@effect("amends_made")
def _amends(world, event) -> None:
    person, kin = event.actors
    world.update_data(person, silver=silver_of(world, person) - event.data["silver"])
    world.update_data(kin, silver=silver_of(world, kin) + event.data["silver"])
    ease(world, person, "guilt", event.data["for"], by=1)


# --- the heart trial at a breakthrough ----------------------------------------------------------------------------

def rising(world, person: int) -> dict | None:
    """The demon that rises at this breakthrough, if any (spec 3)."""
    body = load_body(world, person)
    if not body.bottleneck or body.realm + 1 < TRIAL_REALM:
        return None
    return heaviest(world, person)


def face_chance(world, person: int, demon: dict) -> float:
    comprehension = load_body(world, person).physique["comprehension"]
    chance = FACE_BASE + HT.steady(world, person) / 200 + 0.03 * (comprehension - 10) - 0.1 * demon["weight"]
    return round(max(FACE_BOUNDS[0], min(FACE_BOUNDS[1], chance)), 3)


def trial_events(world, person: int, place, choice: str) -> list[Event]:
    """Face the demon, bury it, or turn back; the breakthrough follows as the choice allows."""
    from systems.cultivation import breakthrough_events  # the breakthrough comes after the heart
    demon = rising(world, person)
    if demon is None or choice not in CHOICES:
        return []
    data = {"choice": choice, "kind": demon["kind"], "whom": demon["whom"], "weight": demon["weight"]}
    if choice == "turn_back":
        return [Event("heart_trial", (person,), place, data)]
    if choice == "bury":
        return [Event("heart_trial", (person,), place, data)] + breakthrough_events(world, person, place,
                                                                                   shift=BURIED_SHIFT)
    chance = face_chance(world, person, demon)
    success = rng_for(world.world_seed, f"heart_trial:{person}:{world.time}").random() < chance
    data.update(chance=chance, success=success)
    return [Event("heart_trial", (person,), place, data)] + breakthrough_events(world, person, place,
                                                                               fail=not success)


@effect("heart_trial")
def _trial(world, event) -> None:
    person, d = event.actors[0], event.data
    if d["choice"] == "bury":
        HT.shift_steady(world, person, BURIED_STEADY)
        add_demon(world, person, d["kind"], d["whom"], 1)
    elif d["choice"] == "face":
        body = load_body(world, person)
        if d["success"]:
            ease(world, person, d["kind"], d["whom"])
            HT.shift_steady(world, person, FACED_STEADY)
            body.insight += FACED_INSIGHT
        else:
            body.deviation = min(100.0, body.deviation + FAILED_DEVIATION)
        save_body(world, person, body)


# --- a shaken heart ------------------------------------------------------------------------------------------------

@listen("cultivated")
def _stir(world, event, event_id: int) -> None:
    person = event.actors[0]
    if person != _player(world) or not HT.shaken(world, person):
        return
    worst = heaviest(world, person)
    weeks = int(event.data["days"] // 7)
    rng = rng_for(world.world_seed, f"stir:{event_id}")
    if worst is not None and any(rng.random() < STIR_CHANCE for _ in range(weeks)):
        commit(world, [Event("demon_stirred", (person,), event.place,
                             {"kind": worst["kind"], "whom": worst["whom"], "deviation": STIR_DEVIATION})])


@effect("demon_stirred")
def _stirred(world, event) -> None:
    body = load_body(world, event.actors[0])
    body.deviation = min(100.0, body.deviation + event.data["deviation"])
    save_body(world, event.actors[0], body)
