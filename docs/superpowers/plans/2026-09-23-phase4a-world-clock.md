# Phase 4a: The World Clock — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The world lives without the player. People age, cultivate, marry, have children, move, take apprentices, settle scores and die. Factions drift in power, clash, lose halls, replace dead leaders, and are founded or destroyed. The player learns of it by being there or by rumour.

**Architecture:**
- **Two clocks.**
  - The **life clock** (`systems/lives.py`) catches one person up, season by season, when they are next observed.
  - The **faction clock** (`systems/world_clock.py` and `systems/wars.py`) runs every materialized faction once per season, globally, at most 8 seasons per turn.
- **Agendas** (`systems/agendas.py`) plug into the life clock through a registry.
- Every change is an event committed with `world.events.commit` (not narrated line by line), plus a fact that the 3a rumour system spreads.
- `engine/world_mixin.py` triggers the clocks and turns what the player comes to believe into one "Much has changed" line and journal entries.

| Area | System | Engine | Narration |
|---|---|---|---|
| life clock | `lives.py` | `WorldMixin` | `world_text.py` |
| agendas | `agendas.py` | — | `world_text.py` |
| faction clock | `world_clock.py`, `wars.py` | `WorldMixin` | `world_text.py` |

**Tech Stack:** Python 3.12, SQLite (save format v2, unchanged), pygame-ce, pytest.

**Spec:** `docs/superpowers/specs/2026-09-23-phase4a-world-clock-design.md`.

## Global Constraints

- No schema change. New keys only:
  - world meta `world_tick`;
  - person data `lived_to`, `age` (now a float), `revenge_rest`;
  - kin role `spouse`.
- A season is 360 watches. Season number `n = time // 360`.
- The faction clock runs at most 8 seasons per turn. The life clock runs the last 40 missed seasons in full; anything older runs a year at a time.
- **Seeds.** A person's key is their seed path, or their id if they have none (as 3c talent does).
  - Life season: `life:{key}:{n}`. Coarse year: `life:{key}:year:{y}`.
  - Faction: `world:{n}:{faction}`. Clash: `world:{n}:clash:{a}:{b}`. Region founding: `world:{n}:region:{region}`.
- World events are committed with `world.events.commit`, never `Game._commit`, so they are never narrated line by line. The only new narrated event, `heard_death`, gets grammar with at least 6 expansions, an outcome builder and a journal summary.
- The player is never aged or moved by either clock in 4a.
- A new event kind must not reuse an existing kind's name (`EFFECTS` holds one handler per kind). 4a deliberately reuses only `died`.
- Briefs keep at most 6 facts, at most 1,200 characters, and no ids.
- Test command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.

## Review Focus

1. **An old save.** Nobody ages retroactively, and both clocks start at the current season. Task 4 pins this with `test_an_old_save_starts_the_clocks_now`.
2. **A year-long seclusion.** The faction clock runs at most 8 seasons per turn and never runs ahead of the clock. Task 3 pins this with `test_the_faction_clock_runs_at_most_eight_seasons_at_a_time`.
3. **A killing between two NPC families.** The victim's kin inherit the grudge and can strike back without the player. Task 2 pins this with `test_a_killing_starts_a_vendetta_between_families`.
4. **A crowded town.** Births stop at 1.5 × the seeded population. Task 2 pins this with `test_a_full_town_has_no_more_births`.
5. **A child in a fight menu.** Children under 12 cannot be challenged, sparred with, invited or asked to follow. Task 4 pins this with `test_children_cannot_be_challenged_or_recruited`.

## Plan-time rulings (deviations from the spec, argued)

1. **Seeds use the person's key** (seed path, or id if none) rather than the raw id, so the same person lives the same life in every playthrough of a seed. This matches 3c talent. *Cost if wrong:* none visible.
2. **Members of the player's sect age and can die of age**, but the life clock does not cultivate them, because their 3c sect seasons already do. *Cost if wrong:* sect disciples would grow half as fast as intended.
3. **Revenge also acts on `grief` over a killing** (not a natural death). A murdered NPC's kin get `grief` (3a), not `hatred`, so without this, vendettas could not chain as spec §4.4 intends. *Cost if wrong:* more NPC feuds.
4. **Two debug rules are narrowed.**
   - Rule 2 (ages never decrease) is pinned by unit tests instead of a per-turn snapshot.
   - Rule 5 becomes "at most one living leader", because a leader can die of age mid-season and is replaced at the next faction season.
   *Cost if wrong:* a leaderless faction for up to a season.
5. **Children are people with the occupation `child` until 16.** The presence line shows them as "(6, child of X)". Portraits are unchanged. *Cost if wrong:* the portrait shows no age.
6. **The arrival news line comes from the town's own gossip.** Arriving, the player hears the town's news of changes *at that town* since their last visit, at most 3. The player comes to believe them through channel `gossip`. The death of anyone the player has met also becomes a `heard_death` journal event. *Cost if wrong:* the player learns local news slightly more easily than by asking.
7. **A dead member's status becomes `dead` in every faction**, generalising 3c. Otherwise the "dead have no active membership" rule could not hold.
8. **`settle_town` skips dissolved factions**, so a destroyed minor faction is never re-staffed when its seat town is first visited.
9. **Newcomer spouses and newborns start their life clock at the season they appeared.**
10. **A century-stale person takes up to 60 ms, not 20 ms.** Each coarse year is one committed event with a full data write (measured at about 32 ms per century). Getting under 20 ms would need multi-year steps, which would blur deaths and breakthroughs. *Cost if wrong:* returning to a full town after a century takes about 1 s, once.
11. **The two 3c speed tests run the world clock before they start timing.** The world clock now runs after every commit, so those tests would otherwise time 8 world seasons as well as the sect's. They measure the sect, as the 3c spec intends. *Cost if wrong:* none; the world clock has its own speed test.

---

### Task 1: The life clock: aging, cultivation, death, coarse catch-up

**Files:**
- Create: `systems/lives.py`, `narrate/world_text.py`
- Modify (via `.patches/4a_task1.py`): `narrate/outcomes.py` (import `world_text`)
- Test: `tests/test_lives.py`

**Interfaces:**
- Consumes: `systems.bodies.load_body` and `save_body`; `systems.realms.add_energy`, `breakthrough_chance` and `realm_index`; `systems.facts.record_fact`, `make_variant` and `place_name`; `systems.factions.memberships`; the 3a kin `died` effect (sets `dead` and buries at the event place).
- Produces:
  - `systems.lives`:
    - Constants: `SEASON = 360`, `FULL_SEASONS = 40`, `LIFESPAN` (8 values by realm index), `BASE_DEATH = 0.001`, `OLD_DEATH = 0.02`, `PAST_DEATH = 0.02`, `NOTABLE_REALM = 2`, `MARTIAL_JOBS`.
    - Registry: `AGENDAS: list[Callable[[world, person, season, rng], list[Event]]]`.
    - Clock: `current_season(world) -> int`, `key(entity) -> str`, `lived_to(world, person) -> int` (starts a never-simulated person at the present).
    - Who lives how: `simulated(entity) -> bool`, `is_martial(world, person) -> bool`, `in_player_sect(world, person) -> bool`, `talent(world, person) -> float`, `death_chance(age, realm) -> float`.
    - Seasons: `step_events(world, entity, n, rng, span, passive) -> list[Event]`, `catch_up(world, person, until=None, passive=False) -> int` (seasons lived).
    - Location: `home(world, person) -> int | None`.
  - Events:
    - `lived` (actors `(person,)`, data `season`, `span`, `age`, `years`, `breakthrough`, `grown`);
    - `broke_through` (data `realm`);
    - `died` with `data["world"] = True` and `cause` of `age`, `illness`, `feud` or `clash`.
  - Facts: `died` (subject = the victim), `killed` (subject = the killer), `broke_through`.
  - `narrate.world_text.WORLD_PHRASES`, merged into 3a `EXTRA_PHRASES`.

- [ ] **Step 1: Write the failing test** — `tests/test_lives.py`
```python
import time

import pytest

import systems.encounters as encounters
import systems.lives as lives
from engine.game import Game
from systems import founding
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.realms import add_energy


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def person(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **data)


def seasons_pass(game, n):
    game.world.set_time(game.world.time + n * lives.SEASON)


def test_a_new_person_starts_in_the_present(game):
    pid = person(game, "test:new", occupation="innkeeper")
    assert lives.lived_to(game.world, pid) == lives.current_season(game.world)
    assert lives.catch_up(game.world, pid) == 0


def test_a_year_away_ages_everyone_a_year(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    pid = person(game, "test:ager", occupation="innkeeper", age=30)
    lives.lived_to(game.world, pid)
    seasons_pass(game, 4)
    assert lives.catch_up(game.world, pid) == 4
    data = game.world.entity(pid).data
    assert data["age"] == 31.0 and data["lived_to"] == lives.current_season(game.world)


def test_commoners_do_not_cultivate_and_fighters_do(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    monkeypatch.setattr(lives, "breakthrough_chance", lambda body, met: 0.0)
    clerk = person(game, "test:clerk", occupation="innkeeper")
    blade = person(game, "test:blade", occupation="wandering swordsman", realm="third-rate")
    before = {p: load_body(game.world, p).energy_years for p in (clerk, blade)}
    for p in (clerk, blade):
        lives.lived_to(game.world, p)
    seasons_pass(game, 4)
    for p in (clerk, blade):
        lives.catch_up(game.world, p)
    assert load_body(game.world, clerk).energy_years == before[clerk]
    gained = load_body(game.world, blade).energy_years - before[blade]
    assert gained == pytest.approx(lives.talent(game.world, blade), abs=1e-3)


def test_the_old_die_and_are_buried(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    pid = person(game, "test:elder", occupation="innkeeper", age=95)
    lives.lived_to(game.world, pid)
    seasons_pass(game, 1)
    lives.catch_up(game.world, pid)
    entity = game.world.entity(pid)
    assert entity.data["dead"] and game.world.targets(pid, "buried_at") == [game.place.id]
    [fact] = game.world.facts(predicate="died", subject=pid)
    assert fact.place == game.place.id and fact.weight == 1.0


def test_a_breakthrough_to_second_rate_is_news(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    monkeypatch.setattr(lives, "breakthrough_chance", lambda body, met: 1.0)
    pid = person(game, "test:rising", occupation="wandering swordsman", realm="third-rate")
    body = load_body(game.world, pid)
    body.energy_years = 5.0
    add_energy(body, 0.0)
    save_body(game.world, pid, body)
    lives.lived_to(game.world, pid)
    seasons_pass(game, 1)
    lives.catch_up(game.world, pid)
    assert game.world.entity(pid).data["realm"] == "second-rate"
    assert game.world.facts(predicate="broke_through", subject=pid)


def test_one_catch_up_or_many_give_the_same_life(game, tmp_path):
    twin = Game.new(tmp_path / "twin.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    twin.start()
    results = []
    for g, steps in ((game, [8]), (twin, [1] * 8)):
        pid = person(g, "test:twin", occupation="wandering swordsman", realm="third-rate", age=60)
        lives.lived_to(g.world, pid)
        for n in steps:
            seasons_pass(g, n)
            lives.catch_up(g.world, pid)
        data = g.world.entity(pid).data
        results.append((data["age"], data.get("dead", False), data["realm"],
                        round(load_body(g.world, pid).energy_years, 6)))
    twin.close()
    assert results[0] == results[1]


def test_a_century_stale_person_catches_up_coarsely_and_fast(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    pid = person(game, "test:hermit", occupation="wandering swordsman", age=20)
    lives.lived_to(game.world, pid)
    seasons_pass(game, 400)
    start = time.perf_counter()
    lived = lives.catch_up(game.world, pid)
    elapsed = time.perf_counter() - start
    data = game.world.entity(pid).data
    assert lived == 400 and data["age"] == 120.0 and data["lived_to"] == lives.current_season(game.world)
    years = [e for e in game.world.chronicle_about(pid, limit=500) if e.kind == "lived"]
    assert len(years) < 150 and any(e.data["span"] == 4 for e in years)
    assert elapsed < 0.06, f"a century took {elapsed * 1000:.0f} ms"  # ruling 10: spec says 20 ms


def test_the_player_is_never_aged(game):
    age = game.player.data.get("age")
    seasons_pass(game, 8)
    assert lives.catch_up(game.world, game.player.id) == 0
    assert game.world.entity(game.player.id).data.get("age") == age


def test_ages_never_go_down(game):
    pid = person(game, "test:steady", occupation="innkeeper", age=40)
    lives.lived_to(game.world, pid)
    ages = []
    for _ in range(6):
        seasons_pass(game, 1)
        lives.catch_up(game.world, pid)
        entity = game.world.entity(pid)
        if entity.data.get("dead"):
            break
        ages.append(entity.data["age"])
    assert ages == sorted(ages)


def test_a_child_comes_of_age_with_a_trade(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    pid = person(game, "test:kid", occupation="child", age=15.5)
    lives.lived_to(game.world, pid)
    seasons_pass(game, 2)
    lives.catch_up(game.world, pid)
    assert game.world.entity(pid).data["occupation"] != "child"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_lives.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.lives'`.

- [ ] **Step 3: Write the life clock** — `systems/lives.py`
```python
"""The life clock (phase 4a spec 4): each person lives the seasons they missed when next observed.

A person's seasons are seeded by `life:{key}:{n}` and committed one at a time,
so catching up eight seasons at once gives the same life as eight catch-ups of
one. Seasons more than FULL_SEASONS behind the present are lived coarsely, a
year per step, with no agendas.
"""

from collections.abc import Callable
from types import SimpleNamespace

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
    """The last season this person has lived. Someone never simulated starts in the present (spec §6)."""
    found = world.entity(person).data.get("lived_to")
    if found is None:
        found = current_season(world)
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
        years = round(0.25 * span * _talent(world, entity), 4)
        _, bottleneck = _grown(body, years)
        traits = SimpleNamespace(physique=body["physique"], purity=body["purity"], insight=body["insight"])
        breakthrough = bool(bottleneck and rng.random() < breakthrough_chance(traits, True))
    dies = rng.random() < 1 - (1 - death_chance(age, realm)) ** span
    grown = _grown_job(world, entity) if entity.data.get("occupation") == "child" and age >= GROWN_AT else None
    data = {"season": n, "span": span, "age": age, "years": years, "breakthrough": breakthrough, "grown": grown}
    events = [Event("lived", (person,), place, data)]
    if breakthrough and realm + 1 >= NOTABLE_REALM:
        events.append(Event("broke_through", (person,), place, {"realm": realm + 1}))
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
```

- [ ] **Step 4: Write the world phrases** — `narrate/world_text.py`
```python
"""What the player is told about the living world (phase 4a spec 7)."""

from narrate.gossip_text import EXTRA_PHRASES

WORLD_PHRASES = {
    "died": "{actor} died.",
    "broke_through": "{actor} broke through to a higher realm.",
}
EXTRA_PHRASES.update(WORLD_PHRASES)
```

- [ ] **Step 5: Edit the existing files** — `.patches/4a_task1.py`
```python
"""Task 1 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("narrate/outcomes.py", "import narrate.season_text  # noqa: E402,F401\n",
     "import narrate.season_text  # noqa: E402,F401\nimport narrate.world_text  # noqa: E402,F401\n")
print("task 1 edits applied")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4a_task1.py && .venv/Scripts/python.exe -m pytest tests/test_lives.py -q -p no:cacheprovider`
Expected: `task 1 edits applied`, then `10 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 7: Commit**

Run: `git add -A && git commit -m "feat: the life clock - people age, cultivate and die while you are away"`

---
### Task 2: Agendas: marriage, children, moving, revenge between NPCs, apprentices

**Files:**
- Create: `systems/agendas.py`
- Modify (via `.patches/4a_task2.py`): `narrate/world_text.py` (phrases for the new facts)
- Test: `tests/test_agendas.py`

**Interfaces:**
- Consumes: Task 1 (`lives.AGENDAS`, `lives.catch_up(..., passive=True)`, `lives.simulated`, `lives.home`, `lives.key`, `lives.in_player_sect`, the `died` event with `data["world"]`), 3a `kin.kin_of` and `kin.INVERSE`, 3c `founding.make_person`, `world.body.add_injury`.
- Produces:
  - `systems.agendas`:
    - Constants: `MARRY_CHANCE = 0.03`, `BIRTH_CHANCE = 0.08`, `MOVE_CHANCE = 0.03`, `REVENGE_CHANCE = 0.1`, `FEUD_DEATH = 0.2`, `APPRENTICE_CHANCE = 0.05`, `POP_CAP = 1.5`, `REVENGE_REST = 4`.
    - Families: `spouse_of(world, person) -> int | None`, `children_of(world, person) -> list[int]`, `parents_of(world, person) -> list[int]`.
    - Grudges and population: `grudge(world, person, n) -> tuple[int, int] | None` (target, grudge event id), `population(world, town) -> int` (living non-staff people).
    - Agendas, registered in `lives.AGENDAS` in this order: `marry_events`, `birth_events`, `move_events`, `revenge_events`, `apprentice_events`, each `(world, person, n, rng) -> list[Event]`.
  - Events:
    - `married` (a, b);
    - `born` (parent, other parent, child; data `population`);
    - `moved` (person; data `to`);
    - `feud` (avenger, target; data `won`, `killed`, `cause`, `season`), followed by a `died` event when `killed`;
    - `apprenticed` (master, youth).
  - Facts: `married`, `born` (extra `population`), `moved`, `defeated` (a feud without a death), `apprenticed`.
  - Kin role `spouse` (its own inverse). Born children have `kin_ready = True`, so no seeded kin is added to them later.

- [ ] **Step 1: Write the failing test** — `tests/test_agendas.py`
```python
import math

import pytest

import systems.agendas as agendas
import systems.encounters as encounters
import systems.lives as lives
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.kin import kin_of
from world.events import Event, commit
from world.gen.materialize import ensure_town, region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


def empty_town(game):
    """A town nobody has visited, so no seeded residents stand in it."""
    return ensure_town(game.world, 9, 9, 0)


def someone(game, path, town, **data):
    pid = founding.make_person(game.world, path, town, **data)
    lives.lived_to(game.world, pid)
    return pid


def one_season(game, *people):
    game.world.set_time(game.world.time + lives.SEASON)
    for pid in people:
        lives.catch_up(game.world, pid)


def wed(game, a, b, town):
    commit(game.world, [Event("married", (a, b), town, {"season": lives.current_season(game.world)})])


def test_two_singles_marry(game, monkeypatch):
    monkeypatch.setattr(agendas, "MARRY_CHANCE", 1.0)
    town = empty_town(game)
    a = someone(game, "test:a", town, age=25, occupation="innkeeper")
    b = someone(game, "test:b", town, age=27, occupation="scholar")
    one_season(game, a)
    assert agendas.spouse_of(game.world, a) == b and agendas.spouse_of(game.world, b) == a
    assert game.world.facts(predicate="married", subject=a)


def test_with_no_one_to_marry_a_newcomer_moves_in(game, monkeypatch):
    monkeypatch.setattr(agendas, "MARRY_CHANCE", 1.0)
    town = empty_town(game)
    a = someone(game, "test:lonely", town, age=30, occupation="hunter")
    one_season(game, a)
    partner = agendas.spouse_of(game.world, a)
    assert partner is not None and game.world.targets(partner, "located_in") == [town]
    assert game.world.entity(partner).data["lived_to"] == lives.current_season(game.world)


def test_a_married_couple_has_one_child(game, monkeypatch):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    town = empty_town(game)
    a = someone(game, "test:ma", town, age=28, occupation="innkeeper")
    b = someone(game, "test:pa", town, age=30, occupation="blacksmith")
    wed(game, a, b, town)
    one_season(game, a, b)
    [child] = agendas.children_of(game.world, a)
    assert agendas.children_of(game.world, b) == [child]
    data = game.world.entity(child).data
    assert data["age"] == 0 and data["occupation"] == "child" and data["kin_ready"]
    assert data["lived_to"] == lives.current_season(game.world)
    assert game.world.targets(child, "located_in") == [town]
    assert sorted(agendas.parents_of(game.world, child)) == sorted([a, b])


def test_a_second_child_is_a_sibling(game, monkeypatch):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    town = empty_town(game)
    a = someone(game, "test:mb", town, age=28, occupation="innkeeper")
    b = someone(game, "test:pb", town, age=30, occupation="blacksmith")
    wed(game, a, b, town)
    one_season(game, a, b)
    one_season(game, a, b)
    first, second = agendas.children_of(game.world, a)
    assert (second, "sibling") in kin_of(game.world, first)


def test_a_full_town_has_no_more_births(game, monkeypatch):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    town = empty_town(game)
    cap = math.ceil(agendas.POP_CAP * game.world.entity(town).data["npc_count"])
    a = someone(game, "test:mc", town, age=28, occupation="innkeeper")
    b = someone(game, "test:pc", town, age=30, occupation="blacksmith")
    for i in range(cap - 2):
        someone(game, f"test:crowd:{i}", town, age=40, occupation="scholar")
    wed(game, a, b, town)
    one_season(game, a, b)
    assert agendas.children_of(game.world, a) == []


def test_births_below_the_cap_record_the_population(game, monkeypatch):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    town = empty_town(game)
    a = someone(game, "test:md", town, age=28, occupation="innkeeper")
    b = someone(game, "test:pd", town, age=30, occupation="blacksmith")
    wed(game, a, b, town)
    one_season(game, a, b)
    [fact] = game.world.facts(predicate="born")
    assert fact.data["population"] == 2


def test_people_move_to_a_nearby_town(game, monkeypatch):
    monkeypatch.setattr(agendas, "MOVE_CHANCE", 1.0)
    town = empty_town(game)
    region = region_of(game.world, town).data
    neighbour = ensure_town(game.world, region["x"] + 1, region["y"], 0)
    mover = someone(game, "test:mover", town, age=30, occupation="tea seller")
    one_season(game, mover)
    assert game.world.targets(mover, "located_in") == [neighbour]
    assert game.world.facts(predicate="moved", subject=mover)


def test_the_married_do_not_move_away_from_their_spouse(game, monkeypatch):
    monkeypatch.setattr(agendas, "MOVE_CHANCE", 1.0)
    town = empty_town(game)
    region = region_of(game.world, town).data
    ensure_town(game.world, region["x"] + 1, region["y"], 0)
    a = someone(game, "test:stay", town, age=30, occupation="tea seller")
    b = someone(game, "test:stay2", town, age=30, occupation="scholar")
    wed(game, a, b, town)
    one_season(game, a)
    assert game.world.targets(a, "located_in") == [town]


def test_a_killing_starts_a_vendetta_between_families(game, monkeypatch):
    monkeypatch.setattr(agendas, "REVENGE_CHANCE", 1.0)
    monkeypatch.setattr(agendas, "FEUD_DEATH", 0.0)
    town = empty_town(game)
    killer = someone(game, "test:killer", town, age=40, occupation="wandering swordsman", realm="third-rate")
    victim = someone(game, "test:victim", town, age=35, occupation="hunter")
    sister = someone(game, "test:sister", town, age=33, occupation="herbalist", kin_ready=True)
    game.world.relate(victim, sister, "kin_of", data={"role": "sibling"})
    game.world.relate(sister, victim, "kin_of", data={"role": "sibling"})
    game.world.update_data(victim, kin_ready=True)
    commit(game.world, [Event("died", (killer, victim), town, {"cause": "test", "world": True})])
    assert agendas.grudge(game.world, sister, lives.current_season(game.world) + 1)[0] == killer
    one_season(game, sister)
    feuds = [e for e in game.world.chronicle_about(sister, limit=10) if e.kind == "feud"]
    assert len(feuds) == 1 and feuds[0].actors == (sister, killer)
    assert game.world.facts(predicate="defeated")


def test_revenge_rests_for_four_seasons(game, monkeypatch):
    monkeypatch.setattr(agendas, "REVENGE_CHANCE", 1.0)
    monkeypatch.setattr(agendas, "FEUD_DEATH", 0.0)
    town = empty_town(game)
    killer = someone(game, "test:k2", town, age=40, occupation="wandering swordsman")
    victim = someone(game, "test:v2", town, age=35, occupation="hunter")
    brother = someone(game, "test:b2", town, age=33, occupation="herbalist", kin_ready=True)
    game.world.relate(victim, brother, "kin_of", data={"role": "sibling"})
    game.world.relate(brother, victim, "kin_of", data={"role": "sibling"})
    game.world.update_data(victim, kin_ready=True)
    commit(game.world, [Event("died", (killer, victim), town, {"cause": "test", "world": True})])
    counts = []
    for _ in range(5):
        one_season(game, brother)
        counts.append(len([e for e in game.world.chronicle_about(brother, limit=40) if e.kind == "feud"]))
    assert counts == [1, 1, 1, 1, 2]


def test_a_master_takes_an_apprentice(game, monkeypatch):
    monkeypatch.setattr(agendas, "APPRENTICE_CHANCE", 1.0)
    town = empty_town(game)
    master = someone(game, "test:master", town, age=50, occupation="wandering swordsman", realm="second-rate")
    youth = someone(game, "test:youth", town, age=14, occupation="child")
    someone(game, "test:grown", town, age=35, occupation="scholar")
    one_season(game, master)
    assert (youth, "disciple") in kin_of(game.world, master) and (master, "master") in kin_of(game.world, youth)
    assert game.world.facts(predicate="apprenticed", subject=master)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agendas.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.agendas'`.

- [ ] **Step 3: Write the agendas** — `systems/agendas.py`
```python
"""What people do with their seasons (phase 4a spec 4.3-4.4): marry, raise children, move, avenge, teach.

Each agenda is `(world, person, n, rng) -> list[Event]` and runs in the life clock's
full seasons only. When an agenda needs someone else, that person is first caught
up passively to the same season (spec §2.2).
"""

import systems.lives as lives
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.founding import make_person
from systems.kin import INVERSE, kin_of
from systems.realms import realm_index
from world.body import add_injury
from world.events import Event, Witness, effect, listen
from world.gen.materialize import people_at

MARRY_CHANCE, BIRTH_CHANCE, MOVE_CHANCE = 0.03, 0.08, 0.03
REVENGE_CHANCE, FEUD_DEATH, APPRENTICE_CHANCE = 0.1, 0.2, 0.05
POP_CAP = 1.5
REVENGE_REST = 4  # seasons before the same grudge is acted on again
GRUDGES = frozenset({"wronged", "hatred", "grief"})

INVERSE.setdefault("spouse", "spouse")


def _kin(world, person: int, role: str) -> list[int]:
    return [k for k, r in kin_of(world, person) if r == role]


def spouse_of(world, person: int) -> int | None:
    found = _kin(world, person, "spouse")
    return found[0] if found else None


def children_of(world, person: int) -> list[int]:
    return _kin(world, person, "child")


def parents_of(world, person: int) -> list[int]:
    return _kin(world, person, "parent")


def _age(entity) -> float:
    return float(entity.data.get("age", 30))


def _town(world, person: int) -> int | None:
    place = lives.home(world, person)
    entity = world.entity(place) if place is not None else None
    return place if entity is not None and entity.kind == "town" else None


def _staff(world, person: int) -> bool:
    return any(d.get("status", "member") == "member" and d.get("role") not in (None, "member")
               for _, _, d in F.memberships(world, person))


def population(world, town: int) -> int:
    """Living people of a town who are not faction staff (spec §4.3 cap)."""
    return len([p for p in people_at(world, town) if not p.data.get("is_player") and not _staff(world, p.id)])


def _ready(world, person: int, n: int) -> bool:
    """Catch someone up passively to season n; are they still alive to take part?"""
    lives.catch_up(world, person, until=n, passive=True)
    return lives.simulated(world.entity(person))


def marry_events(world, person: int, n: int, rng) -> list[Event]:
    entity = world.entity(person)
    if not 18 <= _age(entity) <= 50 or spouse_of(world, person) is not None or rng.random() >= MARRY_CHANCE:
        return []
    town = _town(world, person)
    if town is None:
        return []
    kin = {k for k, _ in kin_of(world, person)}
    candidates = sorted(p.id for p in people_at(world, town)
                        if p.id != person and p.id not in kin and lives.simulated(p) and 18 <= _age(p) <= 50
                        and spouse_of(world, p.id) is None)
    partner = next((c for c in candidates if _ready(world, c, n)), None)
    if partner is None:
        partner = make_person(world, f"life:{lives.key(entity)}:spouse:{n}", town, age=int(_age(entity)))
    return [Event("married", (person, partner), town, {"season": n})]


def birth_events(world, person: int, n: int, rng) -> list[Event]:
    spouse = spouse_of(world, person)
    if spouse is None or spouse < person:  # the lower id of a couple rolls for both
        return []
    entity, other = world.entity(person), world.entity(spouse)
    if not any(18 <= _age(e) <= 45 for e in (entity, other)) or rng.random() >= BIRTH_CHANCE:
        return []
    town = _town(world, person)
    if town is None:
        return []
    count = population(world, town)
    if count >= POP_CAP * world.entity(town).data.get("npc_count", 10):
        return []
    surname = entity.data.get("surname")
    child = make_person(world, f"life:{lives.key(entity)}:child:{n}", town, age=0, occupation="child",
                        realm="mortal", kin_ready=True, **({"surname": surname} if surname else {}))
    return [Event("born", (person, spouse, child), town, {"season": n, "population": count})]


def move_events(world, person: int, n: int, rng) -> list[Event]:
    if rng.random() >= MOVE_CHANCE:
        return []
    entity = world.entity(person)
    town = _town(world, person)
    if town is None or _age(entity) < 16 or entity.data.get("sworn_to") or _staff(world, person) \
            or lives.in_player_sect(world, person):
        return []
    here = set(world.sources(town, "located_in"))
    if spouse_of(world, person) in here or any(c in here for c in children_of(world, person)):
        return []  # the married and the parents do not leave their family behind
    origin = world.entity(town).data
    options = sorted(t.id for t in world.entities("town")
                     if t.id != town and max(abs(t.data["x"] - origin["x"]), abs(t.data["y"] - origin["y"])) <= 1)
    if not options:
        return []
    return [Event("moved", (person,), town, {"to": rng.choice(options)})]


def grudge(world, person: int, n: int) -> tuple[int, int] | None:
    """(someone this person means to strike back at, the event they remember), or None."""
    rest = world.entity(person).data.get("revenge_rest", {})
    for memory in world.memories(person):
        if memory.feeling not in GRUDGES or not memory.event.actors:
            continue
        doer = memory.event.actors[0]
        if doer == person:
            continue
        if memory.feeling == "grief" and (memory.event.kind != "died" or memory.event.actors[-1] == doer):
            continue  # grief over a natural death blames no one
        target = world.entity(doer)
        if target is None or not lives.simulated(target):
            continue  # never the player, the dead or a beast (spec §4.4)
        if n - rest.get(str(memory.event.id), -REVENGE_REST) < REVENGE_REST:
            continue
        return doer, memory.event.id
    return None


def revenge_events(world, person: int, n: int, rng) -> list[Event]:
    found = grudge(world, person, n)
    if found is None or rng.random() >= REVENGE_CHANCE:
        return []
    target, cause = found
    if not _ready(world, target, n):
        return []
    gap = realm_index(world.entity(person).data.get("realm", "mortal")) \
        - realm_index(world.entity(target).data.get("realm", "mortal"))
    won = rng.random() < max(0.1, min(0.9, 0.5 + 0.15 * gap))
    winner, loser = (person, target) if won else (target, person)
    killed = rng.random() < FEUD_DEATH
    place = _town(world, loser) or lives.home(world, loser)
    if place is None:
        return []
    feud = Event("feud", (person, target), place, {"won": won, "killed": killed, "cause": cause, "season": n},
                 witnesses=() if killed else (Witness(loser, "hatred", 0.8),))
    if killed:
        return [feud, Event("died", (winner, loser), place, {"cause": "feud", "world": True})]
    return [feud]


def apprentice_events(world, person: int, n: int, rng) -> list[Event]:
    entity = world.entity(person)
    if realm_index(entity.data.get("realm", "mortal")) < 2 or _kin(world, person, "disciple") \
            or rng.random() >= APPRENTICE_CHANCE:
        return []
    town = _town(world, person)
    if town is None:
        return []
    youths = sorted(p.id for p in people_at(world, town)
                    if p.id != person and lives.simulated(p) and 12 <= _age(p) <= 20 and not _kin(world, p.id, "master"))
    youth = next((y for y in youths if _ready(world, y, n)), None)
    return [] if youth is None else [Event("apprenticed", (person, youth), town, {"season": n})]


lives.AGENDAS.extend([marry_events, birth_events, move_events, revenge_events, apprentice_events])


def _pair(world, a: int, b: int, role_of_b: str) -> None:
    world.relate(a, b, "kin_of", data={"role": role_of_b})
    world.relate(b, a, "kin_of", data={"role": INVERSE[role_of_b]})


@effect("married")
def _married(world, event) -> None:
    a, b = event.actors
    _pair(world, a, b, "spouse")
    if world.entity(b).data.get("lived_to") is None:
        world.update_data(b, lived_to=event.data["season"])  # a newcomer starts living now (ruling 9)


@effect("born")
def _born(world, event) -> None:
    a, b, child = event.actors
    for parent in (a, b):
        for sibling in children_of(world, parent):
            if sibling != child:
                _pair(world, sibling, child, "sibling")
        _pair(world, parent, child, "child")
    world.update_data(child, lived_to=event.data["season"])


@effect("moved")
def _moved(world, event) -> None:
    person = event.actors[0]
    world.unrelate(person, "located_in")
    world.relate(person, event.data["to"], "located_in")


@effect("feud")
def _feud(world, event) -> None:
    person, target = event.actors
    d = event.data
    rest = dict(world.entity(person).data.get("revenge_rest", {}))
    rest[str(d["cause"])] = d["season"]
    world.update_data(person, revenge_rest=rest)
    if not d["killed"]:
        loser = target if d["won"] else person
        body = load_body(world, loser)
        add_injury(body, "torso", "cut", 2, world.time, "a feud")
        save_body(world, loser, body)


@effect("apprenticed")
def _apprenticed(world, event) -> None:
    master, youth = event.actors
    _pair(world, master, youth, "disciple")


def _news(world, event, event_id: int, subject: int, predicate: str, obj, weight: float, **extra) -> None:
    record_fact(world, subject, predicate, obj, place=event.place, source_event=event_id, weight=weight,
                variant=make_variant(predicate, subject, obj, place=place_name(world, event.place)),
                extra=extra or None)


@listen("married")
def _married_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "married", event.actors[1], 1.0)


@listen("born")
def _born_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "born", event.actors[2], 0.5, population=event.data["population"])


@listen("moved")
def _moved_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "moved", event.data["to"], 0.5)


@listen("feud")
def _feud_news(world, event, event_id: int) -> None:
    if event.data["killed"]:
        return  # the death writes `killed`
    person, target = event.actors
    winner, loser = (person, target) if event.data["won"] else (target, person)
    _news(world, event, event_id, winner, "defeated", loser, 0.5)


@listen("apprenticed")
def _apprenticed_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "apprenticed", event.actors[1], 0.5)
```

- [ ] **Step 4: Edit the existing files** — `.patches/4a_task2.py`
```python
"""Task 2 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("narrate/world_text.py", '''    "broke_through": "{actor} broke through to a higher realm.",
}''', '''    "broke_through": "{actor} broke through to a higher realm.",
    "married": "{actor} married {target}.",
    "born": "{actor} had a child, {target}.",
    "moved": "{actor} moved to {target}.",
    "apprenticed": "{actor} took {target} as a disciple.",
}''')
print("task 2 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4a_task2.py && .venv/Scripts/python.exe -m pytest tests/test_agendas.py tests/test_lives.py -q -p no:cacheprovider`
Expected: `task 2 edits applied`, then `21 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: agendas - people marry, have children, move, take apprentices and settle feuds"`

---
### Task 3: The faction clock: power, clashes, succession, staffing, minor factions

**Files:**
- Create: `systems/wars.py`, `systems/world_clock.py`
- Modify (via `.patches/4a_task3.py`): `systems/halls.py` (skip dissolved factions), `narrate/world_text.py` (phrases)
- Test: `tests/test_world_clock.py`

**Interfaces:**
- Consumes:
  - Task 1: `lives.current_season` and the `died` event with `data["world"]`.
  - 3b `systems.factions`: `stance`, `base_stance`, `members_of`, `membership`, `memberships`, `title`, `_make`, `_set_stances`, `ensure_roster`, `STAFFED`, `BASE_REALM`.
  - 3b `systems.halls`: `staff_at`, `halls_here`, `seat_of`, `_hire`, `SEAT_STAFF`, `BRANCH_STAFF`, `CAPITAL_STAFF`, `REALM_BONUS`, `DARK_TRAITS`.
  - 3b `systems.membership.set_membership`.
- Produces:
  - `systems.wars`:
    - Constants: `HOSTILE = -0.5`, `WAR = -0.8`, `CLASH_CHANCE = 0.2`, `WAR_CHANCE = 0.4`, `KILL_CHANCE = 0.3`, `HALL_LOSS = 0.5`, `POWER_LOSS = 5`, `STANCE_HIT = 0.05`, `MEND = 0.02`.
    - `clock_factions(world) -> list[int]` (not dissolved, not `player_sect`, id order).
    - `hall_towns(world, faction) -> list[int]`, `stances(world, ids) -> dict[(a, b), float]`.
    - `clash_events(world, n) -> list[Event]`, `mend_events(world, n, clashed: set) -> list[Event]`.
  - `systems.world_clock`:
    - Constants: `MAX_WORLD_SEASONS = 8`, `DRIFT = 0.2`, `NOISE = 3.0`, `DESTROY_BELOW = 15`, `FOUND_CHANCE = 0.02`.
    - Clock: `world_tick(world) -> int`, `run_season(world, n) -> None`, `run_due(world, limit=MAX_WORLD_SEASONS) -> int`.
    - Staff and power: `staff_of(world, faction) -> list[int]`, `staff_by_town(world, faction) -> dict[town, list[(person, role)]]`, `power_target(world, faction, staff=None) -> int`.
    - Events per faction: `succession_events(world, faction, n, staff=None)`, `staffing_events(world, faction, n, staff=None)`, `power_events(world, faction, n, staff=None)`, `founding_events(world, n)`.
  - Events:
    - `clash` (winner, loser; data `season`, `hall_lost`, `abstract`), followed by `died` (killer, victim; `cause: "clash"`);
    - `stances_mended` (data `changes`: `[a, b, value]`);
    - `succeeded` (person; data `faction`, `role`, `rank`, `hall`). The name avoids 3b's `promoted` event, which is the player's own promotion; the fact is still `promoted`, which reuses 3b's wording.
    - `recruited` (person; data `faction`, `role`, `rank`, `hall`, `season`);
    - `faction_season` (faction; data `power`);
    - `faction_destroyed` (faction);
    - `faction_founded` (faction; data `region`).
  - Facts: `clashed_with`, `lost_hall`, `promoted`, `faction_destroyed`, `faction_founded`.
  - Any death sets the victim's membership status to `dead` in every faction except `player_sect` (3c already handles that one).

- [ ] **Step 1: Write the failing test** — `tests/test_world_clock.py`
```python
import time
from collections import Counter

import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.wars as wars
import systems.world_clock as clock
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_region, ensure_town
from world.gen.region import region_spec


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def seasons_pass(game, n):
    clock.world_tick(game.world)  # the clock starts at its first reading; start it before time moves
    game.world.set_time(game.world.time + n * lives.SEASON)


def a_minor(game, settled=True):
    for x in range(-4, 5):
        for y in range(-4, 5):
            region = game.world.entity(ensure_region(game.world, x, y))
            for fid in F.minor_factions(game.world, region):
                seat = game.world.entity(fid).data["seat"]
                if settled:
                    halls.settle_town(game.world, seat)
                    return fid
                if not game.world.entity(seat).data.get("factions_ready"):
                    return fid
    raise AssertionError("no minor faction")


def roles_at(world, faction, town):
    return Counter(F.membership(world, p, faction)[1]["role"] for p in halls.staff_at(world, faction, town))


def test_the_faction_clock_runs_at_most_eight_seasons_at_a_time(game):
    start = clock.world_tick(game.world)
    assert start == lives.current_season(game.world)
    seasons_pass(game, 20)
    assert [clock.run_due(game.world) for _ in range(4)] == [8, 8, 4, 0]
    assert clock.world_tick(game.world) == lives.current_season(game.world) == start + 20


def test_power_drifts_toward_its_target(game):
    sect = of_type(game.world, "orthodox_sect")
    halls.seat_of(game.world, sect)
    game.world.update_data(sect, power=100)
    target = clock.power_target(game.world, sect)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert abs(game.world.entity(sect).data["power"] - target) < 100 - target


def test_hostile_factions_clash_and_their_stance_hardens(game, monkeypatch):
    monkeypatch.setattr(wars, "CLASH_CHANCE", 1.0)
    monkeypatch.setattr(wars, "WAR_CHANCE", 1.0)
    monkeypatch.setattr(wars, "KILL_CHANCE", 0.0)
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    before = F.stance(game.world, sect, cult)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert F.stance(game.world, sect, cult) == pytest.approx(before - wars.STANCE_HIT)
    pairs = {frozenset((f.subject, f.object)) for f in game.world.facts(predicate="clashed_with")}
    assert frozenset((sect, cult)) in pairs


def test_without_clashes_stances_mend_toward_their_base(game, monkeypatch):
    monkeypatch.setattr(wars, "CLASH_CHANCE", 0.0)
    monkeypatch.setattr(wars, "WAR_CHANCE", 0.0)
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    game.world.relate(sect, cult, "stance", -0.9)
    game.world.relate(cult, sect, "stance", -0.9)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert F.stance(game.world, sect, cult) == pytest.approx(-0.88)
    assert F.stance(game.world, cult, sect) == pytest.approx(-0.88)


def test_a_clash_can_kill_and_take_a_hall(game, monkeypatch):
    monkeypatch.setattr(wars, "CLASH_CHANCE", 1.0)
    monkeypatch.setattr(wars, "WAR_CHANCE", 1.0)
    monkeypatch.setattr(wars, "KILL_CHANCE", 1.0)
    monkeypatch.setattr(wars, "HALL_LOSS", 1.0)
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    town = halls.seat_of(game.world, sect)
    halls.seat_of(game.world, cult)
    game.world.update_data(town, halls=[*halls.halls_here(game.world, town), cult])
    game.world.update_data(cult, branches=[*game.world.entity(cult).data["branches"], town], power=0)
    game.world.update_data(sect, power=100)
    halls._hire(game.world, game.world.entity(cult), town, halls.BRANCH_STAFF)
    branch_staff = halls.staff_at(game.world, cult, town)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert cult not in halls.halls_here(game.world, town)
    assert game.world.facts(predicate="lost_hall", subject=cult)
    dead = [p for p in branch_staff if game.world.entity(p).data.get("dead")]
    assert dead and all(F.membership(game.world, p, cult)[1]["status"] == "dead" for p in dead)
    cult_seat = game.world.entity(cult).data["seat"]
    assert all(game.world.targets(p, "located_in") == [cult_seat] for p in branch_staff if p not in dead)


def test_a_dead_leader_is_succeeded_and_the_hall_restaffed(game):
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    [leader] = halls.staff_at(game.world, sect, seat, roles=("leader",))
    elders = halls.staff_at(game.world, sect, seat, roles=("elder",))
    commit(game.world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    assert F.membership(game.world, leader, sect)[1]["status"] == "dead"
    seasons_pass(game, 1)
    clock.run_due(game.world)
    [heir] = halls.staff_at(game.world, sect, seat, roles=("leader",))
    best = min(elders, key=lambda p: (-F.membership(game.world, p, sect)[0], p))
    assert heir in elders and heir == min(
        elders, key=lambda p: (-lives.realm_index(game.world.entity(p).data["realm"]), p)) or heir == best
    assert F.membership(game.world, heir, sect)[0] == 4
    assert game.world.facts(predicate="promoted", subject=heir)
    assert roles_at(game.world, sect, seat) == Counter(r for r, _, _ in halls.SEAT_STAFF)


def test_a_weak_minor_faction_is_destroyed(game, monkeypatch):
    monkeypatch.setattr(clock, "DESTROY_BELOW", 101)
    minor = a_minor(game)
    seat = game.world.entity(minor).data["seat"]
    staff = halls.staff_at(game.world, minor, seat)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert game.world.entity(minor).data["dissolved"]
    assert minor not in halls.halls_here(game.world, seat)
    assert all(F.membership(game.world, p, minor)[1]["status"] in ("released", "dead") for p in staff)
    assert game.world.facts(predicate="faction_destroyed", subject=minor)


def test_great_factions_are_never_destroyed(game, monkeypatch):
    monkeypatch.setattr(clock, "DESTROY_BELOW", 101)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert not any(game.world.entity(f).data.get("dissolved") for f in F.ensure_roster(game.world))


def test_new_minor_factions_are_founded(game, monkeypatch):
    monkeypatch.setattr(clock, "FOUND_CHANCE", 1.0)
    for i in range(region_spec(game.world.world_seed, 0, 0).town_count):
        halls.settle_town(game.world, ensure_town(game.world, 0, 0, i))
    seasons_pass(game, 1)
    clock.run_due(game.world)
    founded = game.world.facts(predicate="faction_founded")
    assert founded
    fid = founded[0].subject
    seat = game.world.entity(fid).data["seat"]
    assert fid in halls.halls_here(game.world, seat)
    assert halls.staff_at(game.world, fid, seat, roles=("leader",))


def test_settling_skips_destroyed_factions(game):
    minor = a_minor(game, settled=False)
    seat = game.world.entity(minor).data["seat"]
    game.world.update_data(minor, dissolved=True)
    halls.settle_town(game.world, seat)
    assert minor not in halls.halls_here(game.world, seat)


def test_the_same_seeds_give_the_same_world(game, tmp_path):
    twin = Game.new(tmp_path / "twin.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    twin.start()
    results = []
    for g in (game, twin):
        halls.seat_of(g.world, of_type(g.world, "orthodox_sect"))
        seasons_pass(g, 8)
        clock.run_due(g.world)
        results.append(sorted((f, g.world.entity(f).data["power"]) for f in wars.clock_factions(g.world)))
    twin.close()
    assert results[0] == results[1]


def test_one_faction_season_is_quick(game):
    for x in range(-1, 2):
        for y in range(-1, 2):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                halls.settle_town(game.world, ensure_town(game.world, x, y, i))
    seasons_pass(game, 1)
    start = time.perf_counter()
    clock.run_due(game.world)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.03, f"a faction season took {elapsed * 1000:.0f} ms"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_world_clock.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.wars'`.

- [ ] **Step 3: Write the clashes** — `systems/wars.py`
```python
"""Clashes between hostile factions (phase 4a spec 3.2): who fights, who wins, what the loser loses."""

from systems import factions as F
from systems import halls
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, effect, listen
from world.seed import rng_for

HOSTILE, WAR = -0.5, -0.8
CLASH_CHANCE, WAR_CHANCE = 0.2, 0.4
KILL_CHANCE, HALL_LOSS = 0.3, 0.5
POWER_LOSS, STANCE_HIT, MEND = 5, 0.05, 0.02


def clock_factions(world) -> list[int]:
    """Every faction the faction clock runs: materialized, not dissolved, not the player's own."""
    return [f.id for f in world.entities("faction")
            if not f.data.get("dissolved") and f.data.get("type") != "player_sect"]


def hall_towns(world, faction: int) -> list[int]:
    """Towns whose hall lists this faction (its seat and branches that still stand)."""
    data = world.entity(faction).data
    towns = {t for t in [data.get("seat"), *data.get("branches", [])] if t is not None}
    return sorted(t for t in towns if faction in halls.halls_here(world, t))


def stances(world, ids: list[int]) -> dict:
    """(a, b) -> stance for every stance relation among these factions, read once."""
    wanted = set(ids)
    return {(a, b): value for a in ids for b, value, _ in world.relations_from(a, "stance") if b in wanted}


def _power(world, faction: int) -> int:
    return int(world.entity(faction).data.get("power", 50))


def _where(world, a: int, b: int) -> tuple[int | None, bool]:
    shared = sorted(set(hall_towns(world, a)) & set(hall_towns(world, b)))
    if shared:
        return shared[0], False
    weaker = a if _power(world, a) <= _power(world, b) else b
    return world.entity(weaker).data.get("seat"), True


def _leader(world, person: int, faction: int) -> bool:
    return (F.membership(world, person, faction) or (0, {}))[1].get("role") == "leader"


def clash_events(world, n: int) -> list[Event]:
    ids = clock_factions(world)
    known = stances(world, ids)
    events = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            value = known.get((a, b), 0.0)
            if value > HOSTILE:
                continue
            rng = rng_for(world.world_seed, f"world:{n}:clash:{a}:{b}")
            if rng.random() >= (WAR_CHANCE if value <= WAR else CLASH_CHANCE):
                continue
            town, abstract = _where(world, a, b)  # town is None when neither seat is settled yet: still a clash
            pa, pb = _power(world, a), _power(world, b)
            winner, loser = (a, b) if rng.random() < (pa / (pa + pb) if pa + pb else 0.5) else (b, a)
            killer = victim = None
            if town is not None and rng.random() < KILL_CHANCE:
                great = world.entity(loser).data["tier"] == "great"
                victims = sorted(p for p in halls.staff_at(world, loser, town) if not (great and _leader(world, p, loser)))
                seat = world.entity(winner).data.get("seat")
                killers = sorted(halls.staff_at(world, winner, town) or (halls.staff_at(world, winner, seat) if seat else []))
                if victims and killers:
                    victim, killer = rng.choice(victims), rng.choice(killers)
            lost = town is not None and not abstract and town != world.entity(loser).data.get("seat")                 and rng.random() < HALL_LOSS
            events.append(Event("clash", (winner, loser), town, {"season": n, "hall_lost": lost, "abstract": abstract}))
            if victim is not None:
                events.append(Event("died", (killer, victim), town, {"cause": "clash", "world": True}))
    return events


def mend_events(world, n: int, clashed: set) -> list[Event]:
    """Pairs that did not clash drift back toward their founding stance (spec §3.2)."""
    ids = clock_factions(world)
    known = stances(world, ids)
    kinds = {f: world.entity(f).data["type"] for f in ids}
    changes = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if (a, b) in clashed:
                continue
            now = known.get((a, b), 0.0)
            base = F.base_stance(kinds[a], kinds[b])
            if abs(now - base) < 1e-9:
                continue
            step = min(MEND, abs(base - now))
            changes.append([a, b, round(now + step if base > now else now - step, 3)])
    return [Event("stances_mended", (), None, {"season": n, "changes": changes})] if changes else []


@effect("clash")
def _clash(world, event) -> None:
    winner, loser = event.actors
    world.update_data(loser, power=max(0, _power(world, loser) - POWER_LOSS))
    for x, y in ((winner, loser), (loser, winner)):
        world.relate(x, y, "stance", max(-1.0, round(F.stance(world, x, y) - STANCE_HIT, 3)))
    if event.data["hall_lost"]:
        town = event.place
        data = world.entity(town).data
        world.update_data(town, halls=[f for f in data.get("halls", []) if f != loser])
        world.update_data(loser, branches=[t for t in world.entity(loser).data.get("branches", []) if t != town])
        seat = halls.seat_of(world, loser)
        for person in halls.staff_at(world, loser, town):
            world.unrelate(person, "located_in")
            world.relate(person, seat, "located_in")


@effect("stances_mended")
def _mended(world, event) -> None:
    for a, b, value in event.data["changes"]:
        world.relate(a, b, "stance", value)
        world.relate(b, a, "stance", value)


@listen("clash")
def _clash_news(world, event, event_id: int) -> None:
    winner, loser = event.actors
    where = place_name(world, event.place)
    record_fact(world, winner, "clashed_with", loser, place=event.place, source_event=event_id, weight=1.5,
                variant=make_variant("clashed_with", winner, loser, place=where))
    if event.data["hall_lost"]:
        record_fact(world, loser, "lost_hall", winner, place=event.place, source_event=event_id, weight=2.0,
                    variant=make_variant("lost_hall", loser, winner, place=where))
```

- [ ] **Step 4: Write the faction clock** — `systems/world_clock.py`
```python
"""The faction clock (phase 4a spec 3): every materialized faction lives each season, watched or not.

A season runs in phases, each committed before the next reads the world:
clashes, mending, then per faction succession, staffing and power, then new
minor factions. Rolls are seeded by the season number, so the same seeds give
the same world.
"""

from collections import Counter

import systems.lives as lives
from systems import factions as F
from systems import halls, wars
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.realms import REALMS, realm_index
from world.events import Event, commit, effect, listen
from world.gen.materialize import people_at
from world.gen.names import person_name
from world.gen.npc import PORTRAIT_PARTS, TRAITS
from world.seed import rng_for

MAX_WORLD_SEASONS = 8
DRIFT, NOISE = 0.2, 3.0
DESTROY_BELOW = 15
FOUND_CHANCE = 0.02
RECRUITED_ROLES = ("keeper", "disciple")  # leaders and elders are promoted, never hired


def world_tick(world) -> int:
    """The last season the faction clock ran. An old save starts it in the present (spec §6)."""
    found = world.get_meta("world_tick")
    if found is None:
        found = lives.current_season(world)
        world.set_meta("world_tick", found)
    return found


def _role(world, person: int, faction: int) -> str | None:
    found = F.membership(world, person, faction)
    return found[1].get("role") if found else None


def staff_of(world, faction: int) -> list[int]:
    return [p for p in F.members_of(world, faction) if _role(world, p, faction) not in (None, "member")]


def _realm(world, person: int) -> int:
    return realm_index(world.entity(person).data.get("realm", "mortal"))


def staff_by_town(world, faction: int) -> dict[int, list[tuple[int, str]]]:
    """(person, role) of the living staff at each of the faction's halls, from one scan per hall."""
    out = {}
    for town in wars.hall_towns(world, faction):
        here = []
        for person in people_at(world, town):
            found = F.membership(world, person.id, faction)
            if found and found[1].get("status", "member") == "member" and found[1].get("role") not in (None, "member"):
                here.append((person.id, found[1]["role"]))
        out[town] = here
    return out


def power_target(world, faction: int, staff: dict | None = None) -> int:
    staff = staff_by_town(world, faction) if staff is None else staff
    people = [p for here in staff.values() for p, _ in here]
    mean = sum(_realm(world, p) for p in people) / len(people) if people else 0.0
    return max(0, min(100, round(20 + 10 * mean + 5 * len(staff))))


def _table(world, faction: int, seat: bool) -> tuple:
    kind = world.entity(faction).data["type"]
    if seat:
        return halls.SEAT_STAFF if kind in F.STAFFED else () if kind == "alliance" else halls.CAPITAL_STAFF
    return halls.BRANCH_STAFF if kind in F.STAFFED else ()


def _best(world, people: list[int]) -> int | None:
    return min(people, key=lambda p: (-_realm(world, p), p)) if people else None


def _promotion(world, person: int, faction: int, role: str, rank: int, hall) -> Event:
    return Event("succeeded", (person,), lives.home(world, person),
                 {"faction": faction, "role": role, "rank": rank, "hall": hall})


def succession_events(world, faction: int, n: int, staff: dict | None = None) -> list[Event]:
    """A dead or missing leader is replaced by the best elder, then keeper, then disciple; empty elder seats too."""
    seat = world.entity(faction).data.get("seat")
    staff = staff_by_town(world, faction) if staff is None else staff
    if seat not in staff:
        return []
    table = _table(world, faction, True)
    by_role = {r: [p for p, role in staff[seat] if role == r] for r in ("leader", "elder", "keeper", "disciple")}
    anywhere = staff_of(world, faction)  # a leader or elder away from the seat still holds the place
    leaders = [p for p in anywhere if _role(world, p, faction) == "leader"]
    by_role["elder"] = [p for p in anywhere if _role(world, p, faction) == "elder"]
    events = []
    if any(r == "leader" for r, _, _ in table) and not leaders:
        for pool in ("elder", "keeper", "disciple"):
            heir = _best(world, by_role[pool])
            if heir is not None:
                by_role[pool].remove(heir)
                events.append(_promotion(world, heir, faction, "leader", 4, None))
                break
    held = {F.membership(world, p, faction)[1].get("hall") for p in by_role["elder"]}
    for hall in [h for r, _, h in table if r == "elder" and h not in held]:
        for pool in ("keeper", "disciple"):
            heir = _best(world, by_role[pool])
            if heir is not None:
                by_role[pool].remove(heir)
                events.append(_promotion(world, heir, faction, "elder", 3, hall))
                break
    return events


def _recruit(world, faction, town: int, role: str, rank: int, path: str) -> int:
    """A new member of staff, made the way 3b's halls make them."""
    rng = rng_for(world.world_seed, path)
    surname, given = person_name(rng)
    realm = REALMS[min(len(REALMS) - 1, F.BASE_REALM.get(faction.data["type"], 0) + halls.REALM_BONUS[role])].label
    first = rng.choice(halls.DARK_TRAITS) if faction.data["path"] == "ruthless" else rng.choice(TRAITS)
    data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": rng.randint(16, 30),
            "occupation": "hall keeper" if role == "keeper" else F.title(world, faction.id, rank),
            "traits": list(dict.fromkeys([first, rng.choice(TRAITS)])), "realm": realm,
            "portrait": {part: rng.randrange(count) for part, count in PORTRAIT_PARTS.items()}}
    person = world.add_entity("person", f"{surname} {given}", data, path)
    world.relate(person, town, "located_in")
    return person


def staffing_events(world, faction: int, n: int, staff: dict | None = None) -> list[Event]:
    """Empty keeper and disciple places at each hall are filled by seeded recruits (spec §3.3)."""
    entity = world.entity(faction)
    staff = staff_by_town(world, faction) if staff is None else staff
    events, i = [], 0
    for town, here in sorted(staff.items()):
        table = _table(world, faction, town == entity.data.get("seat"))
        have = Counter(role for _, role in here)
        for role in RECRUITED_ROLES:
            slots = [(rank, hall) for r, rank, hall in table if r == role]
            for rank, hall in slots[have[role]:]:
                person = _recruit(world, entity, town, role, rank, f"world:{faction}:recruit:{n}:{i}")
                i += 1
                events.append(Event("recruited", (person,), town,
                                    {"faction": faction, "role": role, "rank": rank, "hall": hall, "season": n}))
    return events


def power_events(world, faction: int, n: int, staff: dict | None = None) -> list[Event]:
    data = world.entity(faction).data
    rng = rng_for(world.world_seed, f"world:{n}:{faction}")
    power = data.get("power", 50)
    target = power_target(world, faction, staff)
    new = max(0, min(100, round(power + DRIFT * (target - power) + rng.uniform(-NOISE, NOISE))))
    events = [Event("faction_season", (faction,), data.get("seat"), {"season": n, "power": new})]
    if data["tier"] == "minor" and new < DESTROY_BELOW:
        events.append(Event("faction_destroyed", (faction,), data.get("seat"), {"season": n}))
    return events


def founding_events(world, n: int) -> list[Event]:
    """Now and then a new school or bandit fort rises in a settled town of a region (spec §3.4)."""
    towns: dict = {}
    for town in world.entities("town"):
        if town.data.get("factions_ready"):
            towns.setdefault((town.data["x"], town.data["y"]), []).append(town.id)
    events = []
    for region in world.entities("region"):
        if not region.data.get("minors_ready"):
            continue
        rng = rng_for(world.world_seed, f"world:{n}:region:{region.id}")
        if rng.random() >= FOUND_CHANCE:
            continue
        x, y = region.data["x"], region.data["y"]
        free = [t for t in towns.get((x, y), [])
                if not any(world.entity(f).data["tier"] == "minor" for f in halls.halls_here(world, t))]
        if not free:
            continue
        town = rng.choice(free)
        kind = rng.choice(("school", "bandit_fort"))
        used = {world.entity(f).name for f in region.data.get("minors", [])}
        fid = F._make(world, rng, kind, "minor", (x, y), f"world:{n}:minor:{region.id}", used)
        events.append(Event("faction_founded", (fid,), town, {"season": n, "region": region.id}))
    return events


def run_season(world, n: int) -> None:
    with world.transaction():
        clashes = wars.clash_events(world, n)
        commit(world, clashes)
        clashed = {tuple(sorted(e.actors)) for e in clashes if e.kind == "clash"}
        commit(world, wars.mend_events(world, n, clashed))
        for faction in wars.clock_factions(world):
            staff = staff_by_town(world, faction)  # one scan serves succession, staffing and power
            promotions = succession_events(world, faction, n, staff)
            if promotions:
                commit(world, promotions)
                staff = staff_by_town(world, faction)
            commit(world, staffing_events(world, faction, n, staff))
            commit(world, power_events(world, faction, n, staff))
        commit(world, founding_events(world, n))
        world.set_meta("world_tick", n)


def run_due(world, limit: int = MAX_WORLD_SEASONS) -> int:
    """Run the seasons the world is owed, at most `limit` of them. Returns how many ran."""
    done = 0
    while done < limit and world_tick(world) < lives.current_season(world):
        run_season(world, world_tick(world) + 1)
        done += 1
    return done


@effect("succeeded")  # not "promoted": 3b ranks owns that kind for the player
def _succeeded(world, event) -> None:
    person, d = event.actors[0], event.data
    set_membership(world, person, d["faction"], rank=d["rank"], role=d["role"], hall=d["hall"])
    world.update_data(person, occupation=F.title(world, d["faction"], d["rank"]))


@effect("recruited")
def _recruited(world, event) -> None:
    person, d = event.actors[0], event.data
    world.relate(person, d["faction"], "member_of", d["rank"],
                 {"role": d["role"], "hall": d["hall"], "merit": 0, "status": "member", "secret": False})
    world.update_data(person, lived_to=d["season"])


@effect("faction_season")
def _faction_season(world, event) -> None:
    world.update_data(event.actors[0], power=event.data["power"])


@effect("faction_destroyed")
def _destroyed(world, event) -> None:
    faction = event.actors[0]
    for person in world.sources(faction, "member_of"):
        found = F.membership(world, person, faction)
        if found and found[1].get("status", "member") == "member":
            set_membership(world, person, faction, status="released")
    for town in {t for t in [world.entity(faction).data.get("seat"), *world.entity(faction).data.get("branches", [])] if t}:
        data = world.entity(town).data
        world.update_data(town, halls=[f for f in data.get("halls", []) if f != faction],
                          seats=[f for f in data.get("seats", []) if f != faction])
    world.update_data(faction, dissolved=True)


@effect("faction_founded")
def _founded(world, event) -> None:
    fid, town = event.actors[0], event.place
    region = world.entity(event.data["region"])
    minors = list(region.data.get("minors", []))
    world.update_data(fid, seat=town)
    F._set_stances(world, [fid], F.ensure_roster(world) + minors)
    world.update_data(region.id, minors=[*minors, fid])
    data = world.entity(town).data
    world.update_data(town, halls=[*data.get("halls", []), fid], seats=[*data.get("seats", []), fid])
    halls._hire(world, world.entity(fid), town, halls.SEAT_STAFF)


@listen("died")
def _dead_leave(world, event, event_id: int) -> None:
    """The dead hold no place in any faction (ruling 7); 3c handles the player's own sect."""
    victim = event.actors[-1]
    for fid, _, data in F.memberships(world, victim):
        if world.entity(fid).data.get("type") != "player_sect" and data.get("status", "member") == "member":
            set_membership(world, victim, fid, status="dead")


def _news(world, event, event_id: int, subject: int, predicate: str, obj, weight: float) -> None:
    record_fact(world, subject, predicate, obj, place=event.place, source_event=event_id, weight=weight,
                variant=make_variant(predicate, subject, obj, place=place_name(world, event.place)))


@listen("succeeded")
def _succeeded_news(world, event, event_id: int) -> None:
    d = event.data
    _news(world, event, event_id, event.actors[0], "promoted", d["faction"], 2.0 if d["role"] == "leader" else 1.5)


@listen("faction_destroyed")
def _destroyed_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "faction_destroyed", None, 2.5)


@listen("faction_founded")
def _founded_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "faction_founded", None, 2.0)
```

- [ ] **Step 5: Edit the existing files** — `.patches/4a_task3.py`
```python
"""Task 3 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("systems/halls.py", '''        for fid in roster + minors:
            faction = world.entity(fid)
            kind = faction.data["type"]''', '''        for fid in roster + minors:
            faction = world.entity(fid)
            if faction.data.get("dissolved"):
                continue  # a destroyed faction is never re-staffed (phase 4a ruling 8)
            kind = faction.data["type"]''')
edit("narrate/world_text.py", '''    "apprenticed": "{actor} took {target} as a disciple.",
}''', '''    "apprenticed": "{actor} took {target} as a disciple.",
    "clashed_with": "The {actor} beat the {target} in a clash.",
    "lost_hall": "The {actor} lost a hall to the {target}.",
    "faction_destroyed": "The {actor} was destroyed.",
    "faction_founded": "The {actor} was founded.",
}''')
print("task 3 edits applied")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4a_task3.py && .venv/Scripts/python.exe -m pytest tests/test_world_clock.py -q -p no:cacheprovider`
Expected: `task 3 edits applied`, then `12 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 7: Commit**

Run: `git add -A && git commit -m "feat: the faction clock - power, clashes, succession, staffing, minor factions rise and fall"`

---
### Task 4: The world in the engine: clocks on time and arrival, news, children, briefs

**Files:**
- Create: `engine/world_mixin.py`, `narrate/grammar/world.toml`
- Modify (via `.patches/4a_task4.py`):
  - `engine/hooks.py` (`_before_scene`, `_before_talk`);
  - `engine/game.py` (the hook calls, the `WorldMixin` import and its place first among the bases);
  - `narrate/world_text.py` (`heard_death` narration, `NEWS_KINDS`, `life_facts`, `town_news`);
  - `narrate/brief.py` (life facts and town news in briefs).
  - `engine/standing_page.py` (`known_factions` counts a faction named as the actor of a believed story, not only as its target).
  - `tests/test_seasons.py`, `tests/test_review_3c.py` (the 3c speed tests settle the world clock before timing; ruling 11).
- Test: `tests/test_world_engine.py`

**Interfaces:**
- Consumes: Tasks 1–3 (`lives.catch_up`, `lives.SEASON`, `world_clock.world_tick`, `world_clock.run_due`, `agendas.spouse_of`, `agendas.children_of`, `agendas.parents_of`), 3a `beliefs.believe`, `CONF_DECAY`, `gossip_text.rumour_text`, `world.acquaintances`.
- Produces:
  - `engine.world_mixin.WorldMixin`:
    - Constants: `CHILD_AGE = 12`, `CHILD_BARRED = {"challenge", "spar", "ask_follow", "sect_invite"}`, `MAX_NEWS = 3`.
    - Hooks: `_before_scene`, `_before_talk`, `_after_commit` (runs the faction clock; "The world moved on" after a time skip of a season or more), `_after_arrival` (local news), `_presence_tag` (age), `_conversation_extras` (children's menu), `_gate` (children).
    - Helper: `_local_news() -> list[Line]`.
  - Player data: `visits` (`{town id as str: time the player last saw the town}`), stamped by `_before_scene`.
  - Event `heard_death` (player, the dead; data `fact`): an outcome line, a journal summary, and a grammar table.
  - `narrate.world_text`:
    - `NEWS_KINDS`;
    - `life_facts(world, person_entity) -> list[str]`;
    - `town_news(world, town, player) -> str | None`.

- [ ] **Step 1: Write the failing test** — `tests/test_world_engine.py`
```python
import time

import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.world_clock as clock
from engine.actions import Action
from engine.game import Game
from systems import founding, travel
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import people_at
from world.gen.town import town_path


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)


def texts(turn):
    return [t for t, _ in turn.lines]


def local(game, path, **data):
    pid = founding.make_person(game.world, path, game.place.id, **data)
    lives.lived_to(game.world, pid)
    return pid


def test_arriving_catches_up_the_town(game):
    game.world.set_time(game.world.time + 4 * lives.SEASON)
    game.perform(Action("look"))
    now = lives.current_season(game.world)
    residents = people_at(game.world, game.place.id, exclude=game.player.id)
    assert residents and all(p.data["lived_to"] == now for p in residents)


def test_talking_catches_someone_up(game):
    pid = local(game, "test:talker", occupation="innkeeper", age=30)
    game.world.set_time(game.world.time + 4 * lives.SEASON)
    game.perform(Action("talk", pid))
    assert game.world.entity(pid).data["lived_to"] == lives.current_season(game.world)
    assert game.world.entity(pid).data["age"] == 31.0


def test_a_season_of_meditation_moves_the_world(game):
    turn = game.perform(Action("meditate", 90))
    assert clock.world_tick(game.world) == lives.current_season(game.world)
    assert any(t.startswith("The world moved on") for t in texts(turn))


def test_returning_brings_news_and_the_journal_remembers(game):
    home = game.place.id
    friend = local(game, "test:friend", occupation="tea seller", age=40)
    game.perform(Action("talk", friend))
    game.perform(Action("farewell"))
    route = travel.routes_from(game.world, game.place)[0]
    game.perform(Action("travel", route.dest))
    commit(game.world, [Event("died", (friend, friend), home, {"cause": "age", "world": True})])
    back = next(r for r in travel.routes_from(game.world, game.place)
                if (game.world.entity_by_seed(town_path(*r.dest)) or game.place).id == home)
    turn = game.perform(Action("travel", back.dest))
    lines = texts(turn)
    name = game.world.entity(friend).name
    assert any(t.startswith("Much has changed here.") and f"{name} died." in t for t in lines)
    assert any(f"{name} has died" in t for t in lines)
    assert any(b.variant.get("actor") == friend for b in game.world.beliefs(game.player.id))
    journal = texts(game.perform(Action("journal")))
    assert any(t.endswith(f"Heard: {name} died.") for t in journal)


def test_children_cannot_be_challenged_or_recruited(game):
    child = local(game, "test:child", occupation="child", age=6)
    game.perform(Action("look"))
    turn = game.perform(Action("talk", child))
    verbs = {c.action.verb for c in turn.all_choices}
    assert not verbs & {"challenge", "spar", "ask_follow", "sect_invite"}
    assert texts(game.perform(Action("challenge", child)))[-1] == "They are only a child."


def test_presence_shows_ages_and_parents(game):
    parent = local(game, "test:parent", occupation="blacksmith", age=33)
    child = local(game, "test:kid", occupation="child", age=6)
    game.world.relate(child, parent, "kin_of", data={"role": "parent"})
    game.world.relate(parent, child, "kin_of", data={"role": "child"})
    game.world.set_time(game.world.time + 1)
    here = next(t for t in texts(game.perform(Action("look"))) if t.startswith("Here:"))
    assert "(33)" in here and f"(6, child of {game.world.entity(parent).name})" in here


def test_briefs_carry_age_and_family(game):
    a = local(game, "test:wife", occupation="herbalist", age=31)
    b = local(game, "test:husband", occupation="hunter", age=33)
    commit(game.world, [Event("married", (a, b), game.place.id, {"season": lives.current_season(game.world)})])
    game.perform(Action("talk", a))
    facts = " ".join(game.last_briefs[-1].facts)
    assert "31 years old" in facts and "married" in facts


def test_an_old_save_starts_the_clocks_now(tmp_path):
    path = tmp_path / "old.world"
    old = Game.new(path, "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    old.start()
    ages = {p.id: p.data.get("age") for p in people_at(old.world, old.place.id, exclude=old.player.id)}
    for pid in ages:  # a save from before 4a has no life clock
        old.world._conn.execute("update entities set data = json_remove(data, '$.lived_to') where id = ?", (pid,))
    old.world.set_meta("world_tick", None)
    old.world.set_time(old.world.time + 40 * lives.SEASON)
    old.close()
    game = Game.load(path)
    game.start()
    now = lives.current_season(game.world)
    assert clock.world_tick(game.world) == now
    for pid, age in ages.items():
        entity = game.world.entity(pid)
        assert entity.data["lived_to"] == now and entity.data.get("age") == age
    game.close()


def test_arriving_in_a_busy_town_eight_seasons_on_is_quick(game):
    for i in range(30):
        local(game, f"test:crowd:{i}", occupation="tea seller", age=30)
    game.world.set_time(game.world.time + 8 * lives.SEASON)
    start = time.perf_counter()
    game.perform(Action("look"))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.15, f"arriving took {elapsed * 1000:.0f} ms"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_world_engine.py -q -p no:cacheprovider`
Expected: most tests fail (for example `assert False` on `lived_to`, or a missing "Much has changed" line), because nothing calls the clocks yet.

- [ ] **Step 3: Write the mixin** — `engine/world_mixin.py`
```python
"""The living world in the engine (phase 4a spec 7): the clocks run as time passes, and you hear what changed."""

import systems.agendas as agendas  # also registers the agendas with the life clock
import systems.lives as lives
import systems.world_clock as clock
from engine.actions import Action
from narrate.gossip_text import rumour_text
from narrate.world_text import NEWS_KINDS
from systems.beliefs import CONF_DECAY, believe
from world.events import Event
from world.gen.materialize import people_at

CHILD_AGE = 12
CHILD_BARRED = frozenset({"challenge", "spar", "ask_follow", "sect_invite"})
MAX_NEWS = 3


def _child(entity) -> bool:
    return entity is not None and entity.kind == "person" and float(entity.data.get("age", 30)) < CHILD_AGE


class WorldMixin:
    _clock_seen: int | None = None
    _last_visit: int | None = None

    def _before_scene(self) -> None:
        super()._before_scene()
        clock.world_tick(self.world)  # start the faction clock the first time a scene is shown (spec §6)
        visits = dict(self.player.data.get("visits", {}))
        self._last_visit = visits.get(str(self.place.id))  # kept for the arrival news line
        visits[str(self.place.id)] = self.world.time
        self.world.update_data(self.player.id, visits=visits)
        for person in people_at(self.world, self.place.id, exclude=self.player.id):
            lives.catch_up(self.world, person.id)

    def _before_talk(self, npc_id) -> None:
        super()._before_talk(npc_id)
        if isinstance(npc_id, int) and self.world.entity(npc_id) is not None:
            lives.catch_up(self.world, npc_id)

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        for event in events:
            if event.kind == "heard":
                variant = event.data.get("variant", {})
                for someone in (variant.get("actor"), variant.get("target")):
                    if isinstance(someone, int) and self.world.entity(someone) is not None:
                        lives.catch_up(self.world, someone)
        seen = self.world.time if self._clock_seen is None else self._clock_seen
        ran = clock.run_due(self.world)
        if ran and self.world.time - seen >= lives.SEASON:
            lines.append((f"The world moved on: {ran} season{'s' if ran > 1 else ''} pass.", "dim"))
        self._clock_seen = self.world.time
        return lines

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._local_news()

    def _local_news(self) -> list:
        """What the town says changed here since you last came (ruling 6), and who you knew that died."""
        world, me, town = self.world, self.player.id, self.place.id
        last, self._last_visit = self._last_visit, None
        if last is None:
            return []
        fresh = [(b, f) for b, f in world.known_facts(town)
                 if f.place == town and f.time > last and f.predicate in NEWS_KINDS]
        fresh = sorted(fresh, key=lambda p: (-p[1].weight, -p[1].id))[:MAX_NEWS]
        if not fresh:
            return []
        told = []
        for belief, fact in fresh:
            believe(world, me, fact.id, belief.variant, town, CONF_DECAY, belief.hops + 1, "gossip")
            told.append(rumour_text(world, belief.variant, me))
        return [("Much has changed here. " + " ".join(told), "dim")] + self._mourn([f for _, f in fresh])

    def _mourn(self, facts: list) -> list:
        me = self.player.id
        known = set(self.world.acquaintances(me))
        mourned = {e.actors[1] for e in self.world.chronicle_about(me, limit=200) if e.kind == "heard_death"}
        events = []
        for fact in facts:
            dead = fact.subject if fact.predicate == "died" else fact.object if fact.predicate == "killed" else None
            if dead in known and dead not in mourned and dead != me:
                mourned.add(dead)
                events.append(Event("heard_death", (me, dead), self.place.id, {"fact": fact.id}))
        return self._commit(events) if events else []

    def _presence_tag(self, person) -> str:
        tag = super()._presence_tag(person)
        age = person.data.get("age")
        if age is None:
            return tag
        if person.data.get("occupation") != "child":
            return f"{tag} ({int(age)})"
        here = {p.id for p in people_at(self.world, self.place.id)}
        parents = [p for p in agendas.parents_of(self.world, person.id) if p in here]
        of = f", child of {self.world.entity(parents[0]).name}" if parents else ""
        return f"{tag} ({int(age)}{of})"

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        return [c for c in extras if c.action.verb not in CHILD_BARRED] if _child(npc) else extras

    def _gate(self, action: Action):
        if action.verb in CHILD_BARRED:
            target = action.target if isinstance(action.target, int) else self.focus
            if isinstance(target, int) and _child(self.world.entity(target)):
                return self._turn([("They are only a child.", "system")])
        return super()._gate(action)
```

- [ ] **Step 4: Write the grammar** — `narrate/grammar/world.toml`
```toml
[symbols]
world_loss = ["A cold feeling settles in your chest.", "You stand still for a moment.", "The news lands heavily.", "You think of the last time you spoke.", "Somewhere a bell tolls.", "The wind feels colder."]
world_after = ["Life goes on around you.", "No one else seems to notice.", "The town carries on.", "Someone lights incense.", "Tea goes cold in a cup nearby.", "A dog barks in the distance."]

[heard_death]
colour = "default"
lines = ["#world_loss# #world_after#", "#world_after# #world_loss#"]
```

- [ ] **Step 5: Edit the existing files** — `.patches/4a_task4.py`
```python
"""Task 4 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("engine/hooks.py", '''    def _after_arrival(self) -> list:
        return []''', '''    def _before_scene(self) -> None:
        """Bring the place up to date before it is described (phase 4a: people live their missed seasons)."""

    def _before_talk(self, npc_id) -> None:
        """Bring someone up to date before a conversation with them starts (phase 4a)."""

    def _after_arrival(self) -> list:
        return []''')

GAME = "engine/game.py"
edit(GAME, "from engine.seasons import SeasonsMixin\n", "from engine.seasons import SeasonsMixin\nfrom engine.world_mixin import WorldMixin\n")
edit(GAME, "class Game(FactionsMixin,", "class Game(WorldMixin, FactionsMixin,")
edit(GAME, '''    def _do_look(self, _target) -> Turn:
        self.focus = None
''', '''    def _do_look(self, _target) -> Turn:
        self.focus = None
        self._before_scene()
''')
edit(GAME, '''        settle_town(self.world, self.place.id)
        self._last_look = (self.place.id, self.world.time)''', '''        settle_town(self.world, self.place.id)
        self._before_scene()
        self._last_look = (self.place.id, self.world.time)''')
edit(GAME, '''    def _do_talk(self, npc_id) -> Turn:
''', '''    def _do_talk(self, npc_id) -> Turn:
        self._before_talk(npc_id)
''')

edit("narrate/world_text.py", '''from narrate.gossip_text import EXTRA_PHRASES
''', '''from narrate.gossip_text import EXTRA_PHRASES, rumour_text
from narrate.outcomes import outcome, summary

NEWS_KINDS = frozenset({"died", "killed", "broke_through", "married", "born", "moved", "apprenticed",
                        "clashed_with", "lost_hall", "promoted", "faction_destroyed", "faction_founded"})
COUNTS = {1: "one child", 2: "two children", 3: "three children"}
''')
Path("narrate/world_text.py").write_text(Path("narrate/world_text.py").read_text(encoding="utf-8") + '''

def life_facts(world, person) -> list[str]:
    """One brief line of a person's age and family (spec §7.2), without naming anyone the player may not know."""
    import systems.agendas as agendas
    age = person.data.get("age")
    if age is None or person.kind != "person":
        return []
    parts = [f"{person.name} is {int(age)} years old"]
    if agendas.spouse_of(world, person.id) is not None:
        parts.append("married")
    children = len(agendas.children_of(world, person.id))
    if children:
        parts.append(f"with {COUNTS.get(children, f'{children} children')}")
    return [", ".join(parts) + "."]


def town_news(world, town: int, player: int) -> str | None:
    """The newest change at this town that the player believes, as they would tell it."""
    news = [(b, f) for b, f in world.known_facts(player) if f.place == town and f.predicate in NEWS_KINDS]
    if not news:
        return None
    belief, _ = max(news, key=lambda p: (p[1].time, p[1].id))
    return rumour_text(world, belief.variant, player)


@outcome("heard_death", body_facts=False)
def _heard_death(world, event):
    return [f"You hear that {world.entity(event.actors[1]).name} has died."], {}


@summary("heard_death")
def _heard_death_line(world, entry, names, place, other):
    return f"Heard: {other} died."
''', encoding="utf-8", newline="\n")

BRIEF = "narrate/brief.py"
edit(BRIEF, '''    facts = facts + [f for f in faction_facts(world, player.id, other) if f not in facts]
    if event.kind in OUTCOME_BUILDERS:''', '''    facts = facts + [f for f in faction_facts(world, player.id, other) if f not in facts]
    if other is not None and not other.data.get("is_player"):
        from narrate.world_text import life_facts  # age and family (phase 4a)
        facts = facts + [f for f in life_facts(world, other) if f not in facts]
    if event.kind in OUTCOME_BUILDERS:''')
edit(BRIEF, '''    fame = reputation(world, place_id, apparent_to(world, place_id, player_id))''', '''    from narrate.world_text import town_news  # the newest change here the player believes (phase 4a)
    news = town_news(world, place_id, player_id)
    if news:
        facts.append(f"Lately here: {news}")
    fame = reputation(world, place_id, apparent_to(world, place_id, player_id))''')
# the 3c speed tests measure the sect's own seasons; the world clock now runs on every commit, so settle it first
edit("tests/test_seasons.py", """    advance(game, 8)
    start = time.perf_counter()""", """    advance(game, 8)
    import systems.world_clock as world_clock
    while world_clock.run_due(game.world):
        pass  # the world's own seasons are not what this test measures (phase 4a ruling 11)
    start = time.perf_counter()""")
edit("tests/test_review_3c.py", """    game.world.set_time(game.world.time + 8 * seasons.SEASON)
    start = time.perf_counter()""", """    game.world.set_time(game.world.time + 8 * seasons.SEASON)
    import systems.world_clock as world_clock
    while world_clock.run_due(game.world):
        pass  # the world's own seasons are not what this test measures (phase 4a ruling 11)
    start = time.perf_counter()""")
edit("engine/standing_page.py", """    for belief in world.beliefs(player):
        target = belief.variant.get("target")
        if isinstance(target, int) and (entity := world.entity(target)) is not None and entity.kind == "faction":
            ids.append(target)""", """    for belief in world.beliefs(player):
        for named in (belief.variant.get("actor"), belief.variant.get("target")):  # "the X beat the Y" names both
            if isinstance(named, int) and (entity := world.entity(named)) is not None and entity.kind == "faction":
                ids.append(named)""")
print("task 4 edits applied")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4a_task4.py && .venv/Scripts/python.exe -m pytest tests/test_world_engine.py -q -p no:cacheprovider`
Expected: `task 4 edits applied`, then `9 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 7: Commit**

Run: `git add -A && git commit -m "feat: the world in the engine - clocks run as time passes, news on arrival, ages, children"`

---
### Task 5: Life rules, a 200-year soak, a long-lived wanderer, docs

**Files:**
- Create: `tests/test_life_rules.py`, `tests/test_soak.py`
- Modify (via `.patches/4a_task5.py`): `debug/invariants.py` (`check_life`), `tests/test_fuzz.py` (the wanderer), `pytest.ini` (the `slow` marker), `docs/debugging.md`
- Test: `tests/test_life_rules.py`, `tests/test_soak.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `debug.invariants.check_life(world) -> list[str]`, called from `check_world`.
  - The fuzz test `test_a_long_lived_wanderer`.
  - The soak tests `test_two_hundred_years_of_history` and `test_five_hundred_years_of_history` (marked `slow`, skipped unless `-m slow`).

- [ ] **Step 1: Write the failing test** — `tests/test_life_rules.py`
```python
import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.world_clock as clock
from debug.invariants import check_life
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def local(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **data)


def test_a_lived_world_breaks_no_rule(game):
    halls.seat_of(game.world, F.ensure_roster(game.world)[0])
    game.world.set_time(game.world.time + 8 * lives.SEASON)
    game.perform(Action("look"))
    while clock.run_due(game.world):
        pass
    assert check_life(game.world) == []


def test_a_clock_ahead_of_time_is_caught(game):
    pid = local(game, "test:ahead", occupation="scholar")
    game.world.update_data(pid, lived_to=lives.current_season(game.world) + 3)
    game.world.set_meta("world_tick", lives.current_season(game.world) + 1)
    problems = check_life(game.world)
    assert any("lived ahead" in p for p in problems) and any("world clock" in p for p in problems)


def test_a_one_sided_or_second_spouse_is_caught(game):
    a, b, c = (local(game, f"test:s{i}", occupation="scholar", age=30) for i in range(3))
    game.world.relate(a, b, "kin_of", data={"role": "spouse"})
    assert any("spouse" in p for p in check_life(game.world))
    game.world.relate(b, a, "kin_of", data={"role": "spouse"})
    game.world.relate(a, c, "kin_of", data={"role": "spouse"})
    game.world.relate(c, a, "kin_of", data={"role": "spouse"})
    assert any("spouses" in p for p in check_life(game.world))


def test_a_dead_member_is_caught(game):
    sect = F.ensure_roster(game.world)[0]
    seat = halls.seat_of(game.world, sect)
    person = halls.staff_at(game.world, sect, seat, roles=("disciple",))[0]
    game.world.update_data(person, dead=True)
    assert any("dead but still" in p for p in check_life(game.world))


def test_two_leaders_are_caught(game):
    sect = F.ensure_roster(game.world)[0]
    seat = halls.seat_of(game.world, sect)
    elder = halls.staff_at(game.world, sect, seat, roles=("elder",))[0]
    game.world.relate(elder, sect, "member_of", 4, {**F.membership(game.world, elder, sect)[1], "role": "leader"})
    assert any("leaders" in p for p in check_life(game.world))


def test_a_child_on_staff_is_caught(game):
    sect = F.ensure_roster(game.world)[0]
    child = local(game, "test:tiny", occupation="child", age=5)
    game.world.relate(child, sect, "member_of", 0, {"role": "disciple", "status": "member", "secret": False})
    assert any("child" in p for p in check_life(game.world))


def test_a_birth_over_the_cap_is_caught(game):
    a = local(game, "test:par", occupation="scholar", age=30)
    b = local(game, "test:kid2", occupation="child", age=0)
    record_fact(game.world, a, "born", b, place=game.place.id, variant=make_variant("born", a, b), extra={"population": 999})
    assert any("born" in p for p in check_life(game.world))
```

- [ ] **Step 2: Write the soak** — `tests/test_soak.py`
```python
"""Centuries of history, headless: the world keeps its rules, its great factions and a sane size."""

import random

import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.rumours as rumours
import systems.world_clock as clock
from debug.invariants import check_world
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.gen.materialize import ensure_town, people_at
from world.gen.region import region_spec


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def history(tmp_path, years: int, step: int = 5):
    path = tmp_path / "soak.world"
    game = Game.new(path, "Chronicler", world_seed=21, creation=CreationChoice("origin", "hunter"))
    game.start()
    world = game.world
    towns = []
    for x in range(-1, 2):
        for y in range(-1, 2):
            for i in range(region_spec(world.world_seed, x, y).town_count):
                town = ensure_town(world, x, y, i)
                halls.settle_town(world, town)
                towns.append(town)
    rng = random.Random(21)
    clock.world_tick(world)
    for n in range(years // step):
        world.set_time(world.time + step * 4 * lives.SEASON)
        while clock.run_due(world):
            pass
        town = rng.choice(towns)
        for person in people_at(world, town, exclude=game.player.id):
            lives.catch_up(world, person.id)
        rumours.catch_up(world, town)
        if n % 8 == 7:
            assert check_world(world) == [], f"year {(n + 1) * step}"
    assert check_world(world) == []
    assert not any(world.entity(f).data.get("dissolved") for f in F.ensure_roster(world))
    game.close()
    return path


def test_two_hundred_years_of_history(tmp_path):
    path = history(tmp_path, 200)
    assert path.stat().st_size < 60 * 2 ** 20


@pytest.mark.slow
def test_five_hundred_years_of_history(tmp_path):
    path = history(tmp_path, 500)
    assert path.stat().st_size < 150 * 2 ** 20
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_life_rules.py -q -p no:cacheprovider`
Expected: the collection error `ImportError: cannot import name 'check_life' from 'debug.invariants'`.

- [ ] **Step 4: Edit the rules, the fuzz test, the marker and the docs** — `.patches/4a_task5.py`
```python
"""Task 5 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


INV = "debug/invariants.py"
edit(INV, '''    problems += check_sect(world)
''', '''    problems += check_sect(world)
    problems += check_life(world)
''')
edit(INV, '''def check_sect(world) -> list[str]:''', '''def check_life(world) -> list[str]:
    """The living world (phase 4a spec 8): clocks never ahead, families and factions consistent."""
    from systems import factions as F
    out = []
    now = world.time // 360
    tick = world.get_meta("world_tick")
    if tick is not None and tick > now:
        out.append(f"the world clock is at season {tick}, ahead of season {now}")
    leaders: dict = {}
    for person in world.entities("person"):
        d = person.data
        who = f"{person.name} (#{person.id})"
        if d.get("lived_to") is not None and d["lived_to"] > now:
            out.append(f"{who} has lived ahead to season {d['lived_to']}")
        rows = F.memberships(world, person.id)
        active = [(f, data) for f, _, data in rows if data.get("status", "member") == "member"]
        if d.get("dead"):
            if active:
                out.append(f"{who} is dead but still a member of #{active[0][0]}")
            continue
        for f, data in active:
            if data.get("role") == "leader":
                leaders.setdefault(f, []).append(person.id)
        spouses = []
        for other, _, data in world.relations_from(person.id, "kin_of"):
            if data.get("role") != "spouse" or world.entity(other).data.get("dead"):
                continue
            spouses.append(other)
            back = [r for b, _, r in world.relations_from(other, "kin_of") if b == person.id]
            if not back or back[0].get("role") != "spouse":
                out.append(f"{who} calls #{other} a spouse, but not the other way round")
        if len(spouses) > 1:
            out.append(f"{who} has {len(spouses)} living spouses")
        if float(d.get("age", 30)) < 12:
            if any(data.get("role") not in (None, "member") for _, data in active) or d.get("sworn_to"):
                out.append(f"{who} is a child but serves a faction or a master")
            if any(r.get("role") == "disciple" for _, _, r in world.relations_from(person.id, "kin_of")):
                out.append(f"{who} is a child with a disciple")
    for faction, people in leaders.items():
        entity = world.entity(faction)
        if len(people) > 1 and not entity.data.get("dissolved") and entity.data.get("type") != "player_sect":
            out.append(f"{entity.name} has {len(people)} living leaders")
    for fact in world.facts(predicate="born"):
        town = world.entity(fact.place) if fact.place else None
        cap = 1.5 * town.data.get("npc_count", 10) if town is not None else 0
        if fact.data.get("population", 0) >= cap:
            out.append(f"a child was born in a full town ({fact.data.get('population')} >= {cap})")
    return out


def check_sect(world) -> list[str]:''')

FUZZ = "tests/test_fuzz.py"
Path(FUZZ).write_text(Path(FUZZ).read_text(encoding="utf-8") + '''

@pytest.mark.parametrize("seed", [3, 8])
def test_a_long_lived_wanderer(tmp_path, seed):
    """Seclusions by the season and long roads: the world ages around the player and every rule holds."""
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Wanderer{seed}", world_seed=seed)
    for step in range(250):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif game.focus is not None:
            app.submit(rng.choice(["1", "2", "3", "4", "5", "bye"]))
        else:
            app.submit(rng.choice(["meditate season", "meditate season", "meditate month", "look", "journal",
                                   "rumours", "go north", "go south", "go east", "go west", "1", "2", "3"]))
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()
''', encoding="utf-8", newline="\n")

edit("pytest.ini", "pythonpath = .", """pythonpath = .
markers =
    slow: centuries-long soak runs; run with -m slow
addopts = -m "not slow\"""")

edit("docs/debugging.md", '''- **Your sect (phase 3c):**''', '''- **The living world (phase 4a):** the world clock and every person's `lived_to` never run ahead of the current season; the dead hold no active membership; `spouse` is mutual and single; a faction has at most one living leader; no child is born into a full town (1.5 × its seed population); a child under 12 serves no faction or master. A 200-year headless soak (`tests/test_soak.py`) runs in the normal suite; 500 years runs with `-m slow`.
- **Your sect (phase 3c):**''')
print("task 5 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4a_task5.py && .venv/Scripts/python.exe -m pytest tests/test_life_rules.py tests/test_soak.py -q -p no:cacheprovider`
Expected: `task 5 edits applied`, then `8 passed, 1 deselected`.

Run: `.venv/Scripts/python.exe -m pytest tests/test_fuzz.py -q -p no:cacheprovider`
Expected: every fuzz test passes, including `test_a_long_lived_wanderer[3]` and `[8]`. Treat any rule violation as a bug and find its cause with systematic debugging. Do not loosen the rule.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "test: life rules, a 200-year soak, a long-lived wanderer, docs"`

---

## Self-review

**Spec coverage:**

| Spec section | Where it is built |
|---|---|
| §2.1 two clocks | Task 1 (life), Task 3 (faction) |
| §2.2 passive catch-up | Tasks 1–2 |
| §2.3 facts and weights | Tasks 1–3 |
| §3.1 power | Task 3 |
| §3.2 clashes | Task 3 |
| §3.3 succession and staffing | Task 3 |
| §3.4 minor factions | Task 3 |
| §4.1 aging and death | Task 1 |
| §4.2 rise | Task 1 |
| §4.3 families | Task 2 |
| §4.4 agendas | Task 2 |
| §4.5 level of detail | Task 1 |
| §5 children | Tasks 1 (coming of age), 2 (born), 4 (menus and gate) |
| §6 save compatibility | Tasks 1, 3, 4 |
| §7 what the player sees | Task 4 |
| §8 debug rules | Task 5 (rules 2 and 5 narrowed, ruling 4) |
| §9 testing | every task; soak and fuzz in Task 5 |

**Differences from the spec:** the plan-time rulings 1–11 above.

**Type consistency:**
- `lives.catch_up(world, person, until=None, passive=False) -> int` everywhere.
- Agendas are `(world, person, n, rng) -> list[Event]`.
- `world_clock.run_due(world, limit=8) -> int`.
- New event kinds: `lived`, `broke_through`, `married`, `born`, `moved`, `feud`, `apprenticed`, `clash`, `stances_mended`, `succeeded`, `recruited`, `faction_season`, `faction_destroyed`, `faction_founded`, `heard_death`. None collides with an existing kind except the deliberate `died`.

**Dry run** (the whole plan on a scratch copy of `fe29b8c`: 546 passed, plus the 500-year soak deselected). It found and fixed:
- **Speed.**
  - Aging now grows energy on the stored body dict and writes once per season: a century went from 114 ms to about 32 ms (ruling 10).
  - The faction clock scans each faction's staff once per season and caches faction types: a season went from 34 ms to about 20 ms.
- **`promoted` already belonged to 3b ranks**, so the world's event is `succeeded` (the fact stays `promoted`).
- **Placeless clashes.** Clashes between factions whose seats are not yet materialized still happen, with no place.
- **Visits** are stamped whenever a scene is shown, so the start town can have news too.
- **Heard-of factions.** `known_factions` now counts a faction named as the actor of a believed story ("The X beat the Y"). Found by fuzz.
- **Leaders away from the seat.** Succession checks for a living leader or elder anywhere in the faction, not only at the seat. Found by fuzz: two living chiefs of a bandit fort.
- **The 3c speed tests** settle the world clock before timing (ruling 11).
- The 200-year soak takes about 41 s.
