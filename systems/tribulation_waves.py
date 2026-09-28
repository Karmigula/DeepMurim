"""A tribulation played wave by wave (phase 5f spec 5): endure it, turn it aside with a pill, shelter under a
tribulation array, or face the heart's demon; and what heaven leaves when it is done.

Each wave is one `tribulation_wave` event; the last is followed by `tribulation_passed` (clean, scarred or
crippled, as 4d's) and, for the heaviest sinner who fails the last of six waves or more, a death.
"""

import systems.demons as D
import systems.formations as FM
import systems.karma as K
import systems.pills as P
import systems.tribulations as TR
from systems.bodies import load_body, save_body
from world.body import REGULAR, add_injury
from world.events import Event, effect
from world.seed import rng_for

ENDURE = (0.45, 0.3, 0.02, 0.05, 0.06)  # base, x purity, x (endurance - 10), x realm, - x strength
BOUNDS = (0.05, 0.95)
ARRAY = "tribulation"
SHELTER_WAVES = 3          # an array of strength 1 takes three waves
DEADLY_WAVES, DEADLY_SIN = 6, 200
CLEAN_INSIGHT, CLEAN_MERIT = 10.0, 10.0
CHOICES = {"lightning": ("endure", "spend", "shelter"), "fire": ("endure", "spend", "shelter"),
           "demon": ("face", "bury")}


def current(world, person: int) -> tuple[str, float] | None:
    t = TR.pending(world, person)
    return (t["waves"][t["wave"]], t["strength"]) if t and t["wave"] < len(t["waves"]) else None


def endure_chance(world, person: int, strength: float) -> float:
    body = load_body(world, person)
    base, pure, tough, realm, hard = ENDURE
    chance = base + pure * body.purity + tough * (body.physique["endurance"] - 10) + realm * body.realm \
        - hard * strength
    return round(max(BOUNDS[0], min(BOUNDS[1], chance)), 3)


def pills_for(world, person: int, strength: float) -> list:
    """Pills strong enough to turn a wave aside: grade at least half its strength."""
    return [p for p in P.pills_of(world, person) if P.grade_of(p) >= strength / 2]


def shelter_of(world, person: int, place) -> dict | None:
    """A tribulation array laid here with shelter left in it."""
    return next((f for f in FM.laid(world, place, ARRAY)
                 if f.get("sheltered", 0) < round(SHELTER_WAVES * f["strength"])), None)


def wave_block(world, person: int, place, choice: str, item=None) -> str | None:
    now = current(world, person)
    if now is None:
        return "No tribulation hangs over you."
    kind, strength = now
    if choice not in CHOICES[kind]:
        return "That will not help against this."
    if choice == "spend" and not any(p.id == item for p in pills_for(world, person, strength)):
        return "You have no pill strong enough."
    if choice == "shelter" and shelter_of(world, person, place) is None:
        return "No tribulation array shelters you here."
    if kind == "demon" and D.heaviest(world, person) is None:
        return None  # the demon is gone already: the wave passes
    return None


def wave_events(world, person: int, place, choice: str, item=None) -> list[Event]:
    kind, strength = current(world, person)
    t = TR.pending(world, person)
    data = {"kind": kind, "choice": choice, "strength": strength, "item": item, "wave": t["wave"],
            "of": len(t["waves"])}
    events = []
    if kind == "demon":
        demon = D.heaviest(world, person)
        success = True
        if demon is not None:
            trial = {"choice": choice, "kind": demon["kind"], "whom": demon["whom"], "weight": demon["weight"]}
            if choice == "face":
                chance = D.face_chance(world, person, demon)
                success = rng_for(world.world_seed, f"wave:{person}:{world.time}:{t['wave']}").random() < chance
                trial.update(chance=chance, success=success)
            events.append(Event("heart_trial", (person,), place, trial))
        data["success"] = success
    elif choice == "endure":
        data["success"] = rng_for(world.world_seed, f"wave:{person}:{world.time}:{t['wave']}").random() \
            < endure_chance(world, person, strength)
    else:
        data["success"] = True
    events.insert(0, Event("tribulation_wave", (person,), place, data))
    if t["wave"] + 1 == len(t["waves"]):
        events += _passed_events(world, person, place, t["failed"] + ([kind] if not data["success"] else []),
                                 last_failed=not data["success"] and kind != "demon")
    return events


def _passed_events(world, person: int, place, failed: list[str], last_failed: bool) -> list[Event]:
    """The end: clean, scarred or crippled; death for a heavy sinner who fails the last of six waves or more."""
    t = TR.pending(world, person)
    outcome = "clean" if not failed else "crippled" if "fire" in failed else "scarred"
    dies = last_failed and len(t["waves"]) >= DEADLY_WAVES and -K.balance(world, person) >= DEADLY_SIN
    events = [Event("tribulation_passed", (person,), place, {"realm": t["realm"], "minor": t["minor"],
                                                             "outcome": outcome, "died": dies})]
    if dies:
        events.append(Event("died", (person, person), place, {"cause": "tribulation"}))
    return events


@effect("tribulation_wave")
def _wave(world, event) -> None:
    person, d, place = event.actors[0], event.data, event.place
    t = dict(TR.pending(world, person))
    t["wave"] += 1
    if not d["success"]:
        t["failed"] = t["failed"] + [d["kind"]]
    world.update_data(person, tribulation=t)
    if d["choice"] == "spend":
        world.update_data(d["item"], used=True)
        world.unrelate(person, "owns", d["item"])
    elif d["choice"] == "shelter":
        shelter = shelter_of(world, person, place)
        same = lambda f: all(f.get(k) == shelter.get(k) for k in ("pattern", "owner", "until"))  # noqa: E731
        world.update_data(place, formations=[{**f, "sheltered": f.get("sheltered", 0) + 1} if same(f) else f
                                             for f in FM.laid(world, place)])
    if d["success"] or d["kind"] == "demon":
        return  # a demon's harm is the heart trial's own
    body = load_body(world, person)
    if d["kind"] == "lightning":
        add_injury(body, "torso", "internal", 2, world.time, "the heavenly tribulation")
    else:
        opened = [m for m in REGULAR if body.meridians[m].state == "open"]
        if opened:
            body.meridians[opened[0]].state = "damaged"
            add_injury(body, opened[0], "meridian", 3, world.time, "the heavenly fire")
    save_body(world, person, body)


@effect("tribulation_passed")
def _passed(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, tribulation=None)
    if d["outcome"] == "clean" and not d["minor"]:
        body = load_body(world, person)
        body.insight += CLEAN_INSIGHT * d["realm"]
        save_body(world, person, body)
        K.add(world, person, merit=CLEAN_MERIT)
