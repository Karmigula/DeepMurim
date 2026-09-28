"""The dao heart (phase 5e spec 2): how steady a cultivator's heart is, and which way it leans.

A person's heart is person data `heart = {steady, lean, demons, daos, oaths}`: `steady` 0-100, `lean` -100
(ruthless) to 100 (righteous). NPCs have none until something writes it; until then it is read from their seed
and traits. Deeds move it (a table, `systems/data/heart_deeds.toml`, and a duel's verdict): a deed that goes the
way one leans steadies the heart, one against it makes it doubt. A steady heart breaks through more easily and
deviates less; a shaken one sees no epiphany.
"""

import tomllib
from pathlib import Path

import systems.lives as lives
from world.events import listen
from world.seed import rng_for

DEEDS = tomllib.loads((Path(__file__).parent / "data" / "heart_deeds.toml").read_text(encoding="utf-8"))
START_STEADY, BOUNDS = 60.0, (0.0, 100.0)
LEAN_BOUND, LEAN_STEP, LEANING = 100.0, 5.0, 20.0  # a deed moves the lean 5 x its weight; |lean| 20 is a leaning
DOUBT = 2                  # a deed against one's lean shakes the heart twice its weight
SHAKEN = 20.0              # under this, no epiphany comes and demons stir
BREAKTHROUGH_STEP = 0.002  # a breakthrough's chance per point of steadiness over its rest (60): +0.08 to -0.12
REST_PER_WEEK = 1.0        # meditation brings the heart back toward START_STEADY
TRAIT_LEAN = {"kind": 20, "honest": 20, "loyal": 10, "cunning": -20, "greedy": -20, "hot-tempered": -10}
TRAIT_STEADY = {"hot-tempered": -15, "proud": -10, "cautious": 5, "loyal": 5}
DUEL = {"spare": (1, 2), "rob": (-1, 1), "cripple": (-1, 2)}  # a won duel's verdict: (lean, weight)
KILL_YIELDED = (-1, 3)     # killing one who yielded; a foe killed broken in a fair fight moves nothing
STEADY_WORDS = ((85, "unshaken"), (70, "firm"), (50, "steady"), (35, "wavering"), (20, "troubled"), (0, "shaken"))
LEAN_WORDS = ((60, "righteous"), (20, "upright"), (-20, "unaligned"), (-60, "hard"), (-101, "ruthless"))


def _clamp(value: float, low: float, high: float) -> float:
    return round(max(low, min(high, value)), 3)


def seeded(world, person: int) -> dict:
    """An NPC's heart before anything writes it: from their seed and their traits (spec 2)."""
    entity = world.entity(person)
    rng = rng_for(world.world_seed, f"heart:{lives.key(entity)}")
    traits = entity.data.get("traits") or []
    lean = sum(TRAIT_LEAN.get(t, 0) for t in traits) + rng.uniform(-15, 15)
    steady = rng.uniform(40, 80) + sum(TRAIT_STEADY.get(t, 0) for t in traits)
    return {"steady": _clamp(steady, *BOUNDS), "lean": _clamp(lean, -LEAN_BOUND, LEAN_BOUND),
            "demons": [], "daos": {}, "oaths": []}


def heart_of(world, person: int) -> dict:
    """The heart as it stands: written, or the player's fresh one, or an NPC's seeded one."""
    entity = world.entity(person)
    if entity.data.get("heart") is not None:
        return entity.data["heart"]
    if entity.data.get("is_player"):
        return {"steady": START_STEADY, "lean": 0.0, "demons": [], "daos": {}, "oaths": []}
    return seeded(world, person)


def write(world, person: int, **changes) -> dict:
    heart = {**heart_of(world, person), **changes}
    world.update_data(person, heart=heart)
    return heart


def steady(world, person: int) -> float:
    return heart_of(world, person)["steady"]


def lean(world, person: int) -> float:
    return heart_of(world, person)["lean"]


def shaken(world, person: int) -> bool:
    return steady(world, person) < SHAKEN


def shift_steady(world, person: int, amount: float) -> None:
    write(world, person, steady=_clamp(steady(world, person) + amount, *BOUNDS))


def deed(world, person: int, way: int, weight: int) -> None:
    """A deed leaning `way` (1 righteous, -1 ruthless) of `weight`: the lean moves, and the heart holds or doubts."""
    heart = heart_of(world, person)
    before = heart["lean"]
    change = 0.0
    if abs(before) >= LEANING:
        change = weight if (before > 0) == (way > 0) else -DOUBT * weight
    write(world, person, lean=_clamp(before + way * LEAN_STEP * weight, -LEAN_BOUND, LEAN_BOUND),
          steady=_clamp(heart["steady"] + change, *BOUNDS))


# --- what the heart weighs --------------------------------------------------------------------------------------

def breakthrough_shift(world, person: int) -> float:
    return round(BREAKTHROUGH_STEP * (steady(world, person) - START_STEADY), 3)


def deviation_factor(world, person: int) -> float:
    """Deviation gained x 0.6 for an unshaken heart to x 1.6 for a shaken one; a heart at rest changes nothing."""
    return round(1 + (START_STEADY - steady(world, person)) / 100, 3)


def steady_words(value: float) -> str:
    return next(word for bound, word in STEADY_WORDS if value >= bound)


def lean_words(value: float) -> str:
    return next(word for bound, word in LEAN_WORDS if value >= bound)


# --- deeds -----------------------------------------------------------------------------------------------------

def _mover(row: dict):
    def moved(world, event, event_id: int) -> None:
        if len(event.actors) > row["actor"] and world.entity(event.actors[row["actor"]]) is not None:
            deed(world, event.actors[row["actor"]], row["lean"], row["weight"])
    return moved


for _kind, _row in DEEDS.items():
    listen(_kind)(_mover(_row))


@listen("duel_ended")
def _verdict(world, event, event_id: int) -> None:
    d = event.data
    if d.get("result") != "won" or d.get("by") != "player" or world.entity(event.actors[1]).data.get("beast"):
        return
    if d.get("verdict") == "kill":
        if d.get("reason") == "yielded":
            deed(world, event.actors[0], *KILL_YIELDED)
        return
    if d.get("verdict") in DUEL:
        deed(world, event.actors[0], *DUEL[d["verdict"]])


@listen("cultivated")
def _rest(world, event, event_id: int) -> None:
    """Meditation brings a heart back toward its rest, a point a week."""
    person = event.actors[0]
    entity = world.entity(person)
    if entity.data.get("heart") is None and not entity.data.get("is_player"):
        return
    now = steady(world, person)
    step = min(abs(START_STEADY - now), REST_PER_WEEK * event.data["days"] / 7)
    if step:
        shift_steady(world, person, step if now < START_STEADY else -step)
