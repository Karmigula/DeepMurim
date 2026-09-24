"""The life clock (phase 4a spec 4): each person lives the seasons they missed when next observed.

A person's seasons are seeded by `life:{key}:{n}` and committed one at a time,
so catching up eight seasons at once gives the same life as eight catch-ups of
one. Seasons more than FULL_SEASONS behind the present are lived coarsely, a
year per step, with no agendas.
"""

from collections.abc import Callable
from types import SimpleNamespace

import systems.world_events as W
from systems import factions as F
from systems.bodies import load_body
from systems.facts import make_variant, place_name, record_fact
from systems.realms import EPS, REALMS, breakthrough_chance, next_threshold, realm_index
from world.body import to_dict
from world.events import Event, commit, effect, listen
from world.gen.npc import OCCUPATIONS
from world.seed import rng_for

SEASON = 360
FULL_SEASONS = 40
LIFESPAN = (70, 80, 95, 120, 150, 200, 300, 500)
BASE_DEATH, OLD_DEATH, PAST_DEATH = 0.001, 0.02, 0.02
NOTABLE_REALM = 2  # Second-rate: a breakthrough worth talking about
MARTIAL_JOBS = frozenset({"wandering swordsman", "constable", "monk"})
GROWN_AT = 16
AGENDAS: list[Callable] = []  # (world, person, season, rng) -> list[Event]; agendas.py registers here


def current_season(world) -> int:
    return world.time // SEASON


def key(entity) -> str:
    return entity.seed_path or str(entity.id)


def simulated(entity) -> bool:
    d = entity.data
    return entity.kind == "person" and not d.get("is_player") and not d.get("dead") and not d.get("beast")


def lived_to(world, person: int) -> int:
    """The last season this person has lived.

    Someone never stamped starts at the season they came into the world (spec §2.1);
    an old save's people were all stamped when its world clock first started (spec §6).
    """
    entity = world.entity(person)
    found = entity.data.get("lived_to")
    if found is None:
        found = min(entity.created_at // SEASON, current_season(world))
        world.update_data(person, lived_to=found)
    return found


def home(world, person: int) -> int | None:
    return next(iter(world.targets(person, "located_in")), None)


def _talent(world, entity) -> float:
    found = entity.data.get("talent")
    return found if found else round(rng_for(world.world_seed, f"talent:{key(entity)}").uniform(0.5, 1.5), 2)


def talent(world, person: int) -> float:
    return _talent(world, world.entity(person))


def _ways(world, entity) -> tuple[bool, bool]:
    """(martial, in the player's sect) from one read of the person's memberships."""
    rows = [(f, d) for f, _, d in F.memberships(world, entity.id) if d.get("status", "member") == "member"]
    sect = any(d.get("role") in ("disciple", "elder") and world.entity(f).data.get("type") == "player_sect"
               for f, d in rows)
    martial = (realm_index(entity.data.get("realm", "mortal")) > 0 or entity.data.get("occupation") in MARTIAL_JOBS
               or any(d.get("role") not in (None, "member") for _, d in rows))
    return martial, sect


def is_martial(world, person: int) -> bool:
    return _ways(world, world.entity(person))[0]


def in_player_sect(world, person: int) -> bool:
    return _ways(world, world.entity(person))[1]


def death_chance(age: float, realm: int) -> float:
    life = LIFESPAN[realm]
    chance = BASE_DEATH
    if age >= life - 10:
        chance += OLD_DEATH
    if age > life:
        chance += PAST_DEATH * (age - life)
    return min(1.0, chance)


def _grown_job(world, entity) -> str:
    """A child's trade at sixteen: a parent's with even odds, otherwise their own seeded one."""
    rng = rng_for(world.world_seed, f"life:{key(entity)}:grown")
    parents = [k for k, _, d in world.relations_from(entity.id, "kin_of") if d.get("role") == "parent"]
    jobs = [world.entity(p).data.get("occupation") for p in parents]
    jobs = [j for j in jobs if j and j != "child"]
    if jobs and rng.random() < 0.5:
        return jobs[0]
    return rng.choice(OCCUPATIONS)


def _grown(body: dict, years: float) -> tuple[float, bool]:
    """Energy after `years` more, capped at the bottleneck, and whether the bottleneck is reached.

    Works on the stored body dict: a person's seasons never need the whole Body object.
    """
    high = next_threshold(body["realm"])
    energy = body["energy_years"] + years
    if high is not None:
        energy = min(high, energy)
    return energy, high is not None and energy >= high - EPS


def _sky(world, place: int | None, n: int) -> dict:
    """The sky's boosts over season n, the season being lived (phase 4d): its own sky, not today's."""
    at = n * SEASON + SEASON // 2
    return {key: W.factor(world, place, key, at=at) for key in ("cultivation", "breakthrough")}


def step_events(world, entity, n: int, rng, span: int, passive: bool) -> list[Event]:
    """`span` seasons (1, or 4 in coarse mode) of aging, growth and the death roll, ending at season n."""
    person = entity.id
    place = home(world, person)
    realm = realm_index(entity.data.get("realm", "mortal"))
    age = round(float(entity.data.get("age", 30)) + 0.25 * span, 2)
    years, breakthrough = 0.0, False
    martial, sect = _ways(world, entity)
    if martial and not sect:
        body = entity.data.get("body") or to_dict(load_body(world, person))
        sky = _sky(world, place, n) if span == 1 else {}  # coarse years are too long ago to matter
        years = round(0.25 * span * _talent(world, entity) * sky.get("cultivation", 1.0), 4)
        _, bottleneck = _grown(body, years)
        traits = SimpleNamespace(physique=body["physique"], purity=body["purity"], insight=body["insight"])
        breakthrough = bool(bottleneck and rng.random() < breakthrough_chance(traits, True) * sky.get("breakthrough", 1.0))
    dies = rng.random() < 1 - (1 - death_chance(age, realm)) ** span
    grown = _grown_job(world, entity) if entity.data.get("occupation") == "child" and age >= GROWN_AT else None
    data = {"season": n, "span": span, "age": age, "years": years, "breakthrough": breakthrough, "grown": grown}
    events = [Event("lived", (person,), place, data)]
    if breakthrough and realm + 1 >= NOTABLE_REALM:
        events.append(Event("broke_through", (person,), place, {"realm": realm + 1, "season": n}))
    if dies and place is not None:
        cause = "age" if age >= LIFESPAN[realm] - 10 else "illness"
        return events + [Event("died", (person, person), place, {"cause": cause, "world": True})]
    if not passive and span == 1:
        for agenda in AGENDAS:
            events += agenda(world, person, n, rng)
    return events


def catch_up(world, person: int, until: int | None = None, passive: bool = False) -> int:
    """Live this person's missed seasons up to `until` (default: now). Returns how many seasons passed.

    Passive catch-up (someone else's agenda needs this person) ages, grows and
    rolls death, but runs no agendas, so it never reaches further (spec §2.2).
    """
    entity = world.entity(person)
    if entity is None or not simulated(entity):
        return 0
    now = current_season(world)
    until = now if until is None else min(until, now)
    start = lived_to(world, person)
    with world.transaction():
        while True:
            entity = world.entity(person)
            done = entity.data["lived_to"]
            if not simulated(entity) or done >= until:
                break
            if until - done > FULL_SEASONS + 3:
                n = done + 4
                rng = rng_for(world.world_seed, f"life:{key(entity)}:year:{n // 4}")
                commit(world, step_events(world, entity, n, rng, 4, True))
            else:
                n = done + 1
                rng = rng_for(world.world_seed, f"life:{key(entity)}:{n}")
                commit(world, step_events(world, entity, n, rng, 1, passive))
    return world.entity(person).data.get("lived_to", start) - start


@effect("lived")
def _lived(world, event) -> None:
    person, d = event.actors[0], event.data
    changes = {"age": d["age"], "lived_to": d["season"]}
    if d.get("grown"):
        changes["occupation"] = d["grown"]
    if d["years"]:
        body = dict(world.entity(person).data.get("body") or to_dict(load_body(world, person)))
        body["energy_years"], body["bottleneck"] = _grown(body, d["years"])
        if d["breakthrough"] and body["bottleneck"]:
            body["realm"] += 1
            body["bottleneck"] = False
        changes.update(body=body, realm=REALMS[body["realm"]].label)
    world.update_data(person, **changes)  # one write per season


def _is_staff(world, person: int) -> bool:
    return any(d.get("role") not in (None, "member") for _, _, d in F.memberships(world, person))


@listen("died")
def _death_news(world, event, event_id: int) -> None:
    """A death in the living world becomes news: `died` for age and illness, `killed` for a killing."""
    if not event.data.get("world"):
        return
    killer, victim = event.actors
    where = place_name(world, event.place)
    if killer == victim:
        notable = realm_index(world.entity(victim).data.get("realm", "mortal")) >= NOTABLE_REALM or _is_staff(world, victim)
        record_fact(world, victim, "died", None, place=event.place, source_event=event_id,
                    weight=2.0 if notable else 1.0, variant=make_variant("died", victim, None, place=where))
    else:
        record_fact(world, killer, "killed", victim, place=event.place, source_event=event_id, weight=2.0,
                    variant=make_variant("killed", killer, victim, place=where,
                                         realm=world.entity(killer).data.get("realm")))


@listen("broke_through")
def _breakthrough_news(world, event, event_id: int) -> None:
    person, realm = event.actors[0], event.data["realm"]
    record_fact(world, person, "broke_through", None, place=event.place, source_event=event_id,
                weight=1.0 + 0.5 * (realm - NOTABLE_REALM),
                variant=make_variant("broke_through", person, None, place=place_name(world, event.place),
                                     realm=REALMS[realm].label))
