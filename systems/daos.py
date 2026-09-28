"""Epiphanies and daos (phase 5e spec 4): a dao of each martial form and each element, comprehended in flashes of
insight, that speeds an art's practice and sharpens its blows; a dao completed is the return to the origin.

Comprehension lives in the heart's `daos` {name: 0-1}. An epiphany is an event; its occasions are listeners on
practice (in a dao resonance, or an art brought to Great Completion), a life-and-death fight won, a tournament
bout watched, and meditation with a heart leaning hard one way. A shaken heart sees nothing.
"""

import systems.heart as HT
import systems.world_events as W
from systems.bodies import load_body, save_body
from systems.techniques import FORMS, heart_method
from world.body import ELEMENTS
from world.events import Event, commit, effect, listen
from world.seed import rng_for

DAOS = FORMS + ELEMENTS + ("yin", "yang")  # an art's element may be yin or yang; a neutral one opens no dao
GAIN_BASE, GAIN_STEP, GAIN_BOUNDS = 0.05, 0.02, (0.02, 0.15)
RESONANCE_CHANCE = 0.2     # a week's practice in a dao resonance
DEATH_FIGHT_CHANCE = 0.3   # a life-and-death fight won
WATCH_CHANCE = 0.05        # a bout watched
LEANING_CHANCE, LEANING_AT = 0.02, 60.0  # a week's meditation with the heart leaning past 60 either way
FIGHT_STEP = 0.1           # a blow of a comprehended form, x (1 + 0.1 x dao)
ORIGIN = "returned_to_origin"  # 2a's flag for Life-and-Death, set by a dao completed


def daos(world, person: int) -> dict:
    return dict(HT.heart_of(world, person)["daos"])


def dao(world, person: int, name: str | None) -> float:
    return daos(world, person).get(name, 0.0) if name else 0.0


def gain(world, person: int) -> float:
    comprehension = load_body(world, person).physique["comprehension"]
    return round(max(GAIN_BOUNDS[0], min(GAIN_BOUNDS[1], GAIN_BASE + GAIN_STEP * (comprehension - 10))), 3)


def epiphany_events(world, person: int, place, name: str, why: str) -> list[Event]:
    if name not in DAOS or HT.shaken(world, person):
        return []
    before = dao(world, person, name)
    after = round(min(1.0, before + gain(world, person)), 3)
    if after == before:
        return []
    return [Event("epiphany", (person,), place, {"dao": name, "before": before, "after": after, "why": why,
                                                  "origin": after >= 1.0 > before})]


@effect("epiphany")
def _epiphany(world, event) -> None:
    person, d = event.actors[0], event.data
    HT.write(world, person, daos={**daos(world, person), d["dao"]: d["after"]})
    if d["origin"]:
        body = load_body(world, person)
        if ORIGIN not in body.flags:
            body.flags.append(ORIGIN)
            save_body(world, person, body)


def practice_factor(world, person: int, form: str, element: str) -> float:
    """Practice of an art x (1 + the better of its form's and its element's dao)."""
    return round(1 + max(dao(world, person, form), dao(world, person, element)), 3)


def fight_factor(world, person: int, form: str) -> float:
    return round(1 + FIGHT_STEP * dao(world, person, form), 3)


def _roll(world, key: str, chance: float, times: int = 1) -> bool:
    rng = rng_for(world.world_seed, key)
    return any(rng.random() < chance for _ in range(times))


def _form_of(world, technique_id) -> str | None:
    technique = world.entity(technique_id) if technique_id is not None else None
    return technique.data.get("form") if technique is not None else None


# --- the occasions ------------------------------------------------------------------------------------------------

@listen("practised")
def _from_practice(world, event, event_id: int) -> None:
    person, d = event.actors[0], event.data
    technique = world.entity(d["technique_id"])
    events = []
    if d.get("mastered"):  # Great Completion: both its daos open a little
        events += epiphany_events(world, person, event.place, technique.data["form"], "completion")
        events += epiphany_events(world, person, event.place, technique.data["element"], "completion")
    elif W.factor(world, event.place, "practice") > 1 \
            and _roll(world, f"epiphany:practice:{event_id}", RESONANCE_CHANCE, max(1, d["days"] // 7)):
        events += epiphany_events(world, person, event.place, technique.data["form"], "resonance")
    commit(world, events)


@listen("duel_ended")
def _from_fight(world, event, event_id: int) -> None:
    d = event.data
    if d.get("result") != "won" or d.get("by") != "player" or not d.get("life_and_death"):
        return
    start = world.chronicle_entry(d["duel"]) if d.get("duel") else None
    form = _form_of(world, start.data.get("technique")) if start is not None else None
    if form and _roll(world, f"epiphany:fight:{event_id}", DEATH_FIGHT_CHANCE):
        commit(world, epiphany_events(world, event.actors[0], event.place, form, "fight"))


@listen("watched")
def _from_watching(world, event, event_id: int) -> None:
    occurrence = world.entity(event.data["occurrence"])
    arts = (occurrence.data.get("data") or {}).get("arts") or {} if occurrence is not None else {}
    form = _form_of(world, arts.get(str(event.data["winner"])))
    if form and _roll(world, f"epiphany:watch:{event_id}", WATCH_CHANCE):
        commit(world, epiphany_events(world, event.actors[0], event.place, form, "watching"))


@listen("cultivated")
def _from_meditation(world, event, event_id: int) -> None:
    person = event.actors[0]
    if not world.entity(person).data.get("is_player") or abs(HT.lean(world, person)) < LEANING_AT:
        return
    method = heart_method(world, person)
    if method is not None and _roll(world, f"epiphany:heart:{event_id}", LEANING_CHANCE,
                                    max(1, int(event.data["days"] // 7))):
        commit(world, epiphany_events(world, person, event.place, method.technique.data["element"], "meditation"))
