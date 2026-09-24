# Phase 4d: World Events, Heavenly Phenomena and Rankings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A data-driven world-event framework, eight heavenly phenomena built on it, treasure races, and the Heavenly Ranking Pavilion's yearly lists, all narrated from Briefs and guarded by debug rules.

**Architecture:**
- **Framework:**
  - Event types are TOML entries (`systems/data/world_events.toml`) with optional hook modules (`systems/events/*.py`).
  - Occurrences are `world_event` entities. Their stages are computed from the time.
  - A small `sky_index` meta row lists the occurrences that still matter, so modifier lookups never scan history.
  - `systems/world_events.py` only reads. `systems/sky.py` starts occurrences, commits stage events and records news.
- **Wiring into existing systems:** each system reads one named knob through `world_events.factor`.
- **Rankings:** built from the beliefs of an `institution` entity, the Pavilion.

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-24-phase4d-world-events-design.md`

## Global Constraints

- **Save format:** no save-format version change. New entity kinds are `world_event`, `institution` and `treasure`; new meta keys are `sky_index` and `pavilion`.
- **Modifiers:** `factor()` is clamped to 0.25–4.0. Price effects go through the 4c `market.EVENT_FACTORS`, which market clamps to 0.3–4.0.
- **Dates:** an occurrence counts from its own season (`n * SEASON`), and one whose whole span ends before now is never created (the 4c catch-up lesson).
- **Uniqueness:** at most one live occurrence per type per place.
- **Knowledge vs truth:**
  - Rankings read only the Pavilion's beliefs.
  - The player sees the sky over their own place directly, and anything else only through beliefs.
  - A fact's variant `actor` equals its `subject` (the 3a knowledge rule).
- **Speed:** measured in CPU time (`time.process_time`). `factor()` under 0.2 ms; the season hook with 50 regions under 20 ms; a ranking revision under 50 ms; the rankings page under 30 ms.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A long absence** (a 40-season catch-up, or an heir waking decades later). No old comets, famines or tribulations start "now"; NPC growth in the past uses only the occurrences live at that past season. Task 1 pins this with `test_a_catch_up_starts_nothing_already_over`, and Task 2 with `test_npc_growth_reads_the_sky_of_its_own_season`.
2. **A save from before 4d.** No `sky_index` and no Pavilion: every factor is 1.0, the first season creates the Pavilion, and the first lists appear the next spring. Task 1 pins this with `test_an_old_world_has_a_quiet_sky`, and Task 5 with `test_an_old_save_gets_the_pavilion_and_publishes_in_spring`.
3. **Two phenomena on one knob.** A qi tide inside a comet year, or a blood moon over a beast tide: modifiers multiply and clamp. Task 1 pins this with `test_modifiers_multiply_and_clamp`.
4. **A player who wins the race's last duel while already holding the prize.** A prize is claimed once only, and the item has one owner. Task 4 pins this with `test_a_prize_is_never_claimed_twice`.
5. **The dead on the lists.** A dead master stays listed until the Pavilion hears of the death, and never after. Task 5 pins this with `test_the_dead_stay_listed_until_the_pavilion_hears`.

## Plan-time rulings (deviations from the spec, argued)

1. **The rankings page takes F10, not F9.** F9 is already the bug-report key (`app.py`). *Cost if wrong:* one key binding.
2. **Rankings spread as one `published` fact per revision, not one `ranked` fact per entry.**
   - 70 facts a year would flood the facts table and every town's rumour catch-up over a 500-year soak.
   - Renown and the rank epithet come from the town believing the latest `published` fact that names the person.
   - *Cost if wrong:* renown for rank is computed rather than summed from facts.
3. **Pavilion informants give each fact two chances.** A fact is considered once in the season after it happens, and once more a year later; then it is let go. The spec said "re-rolled once a year", which is unbounded over centuries. *Cost if wrong:* a distant deed is never heard after two misses.
4. **The Pavilion also surveys public figures.** Each spring it records an `assessed` fact (unspread) for every living leader and elder of a staffed faction, with their realm.
   - Without this, the world's generated masters, who have no deeds on record, would never be ranked, and the first lists would be empty.
   - Wanderers and hidden masters are still unranked until they do something.
   - *Cost if wrong:* the lists favour sect elders.
5. **Duel wins count once.** A player's won duel records both `defeated` and a verdict fact (`killed`, `spared`…); scoring counts `defeated` only. Believed age comes from facts that carry an `age` (assessed, tribulation, treasure), plus years elapsed. *Cost if wrong:* someone with no age-bearing fact cannot be a Young Dragon.
6. **`seek` fights at the site; it does not travel there.** Away from the site, `seek` tells you where the light is and how far. The spec had `seek` travel for you, but road travel already exists and stays the one way to move. *Cost if wrong:* one extra `go` step for the player.
7. **Champions are named, not moved.** At `announced`, champions are recorded on the occurrence. They stay where they live, so 4a agendas and faction staffing are undisturbed; the player's duels against them happen at the site. *Cost if wrong:* a champion can also be seen at home during the race.
8. **The beast-tide bounty lives on the occurrence, not in 3b law.** The magistrate's bounty is the occurrence's `bounty`. Three beast kills in the region while it is active pay it. 3b bounties are on criminals, a different thing. *Cost if wrong:* none.
9. **Blood-moon patrols use the 3b `HUNTER_HOOKS`.** During a blood moon, righteous-faction members in a town where you are known as ruthless call you out like avengers. *Cost if wrong:* the chance is 3b's `AVENGER_CHANCE` (0.6).
10. **Tribulation odds:**
    - clean = `0.45 + 0.3 × purity + 0.1 if rested in the 3 days before` (70% at purity 0.5 with rest);
    - crippled = 3%, only when purity is below 0.5;
    - scarred otherwise.

    An NPC's tribulation lightning is visible only if its breakthrough falls in the current season.
11. **Treasures are a small new item kind** (`treasure`: pill, herb, star iron). A pill is swallowed for qi years, and a herb or star iron is sold in any town for its value, because no consumable or sellable item exists yet. A manual prize is a normal 2b manual. *Cost if wrong:* phase 5 may reshape items.
12. **The narrator re-rolls away from the last lines of any kind, not only its own.**
    - The dry run found the app's "repeat of a recent line" rule firing: a road line from one grammar key repeated a line from another key. Qi tides changed the world's path and exposed it.
    - The narrator now keeps the last 8 lines it produced, which covers the previous turn and this one.
    - *Cost if wrong:* none.
13. **The "named on screen" rule matches people's names with their capitals.**
    - The dry run found a character named "Again" flagged inside "Until the rivers meet again".
    - Names are proper nouns and always appear capitalised; faction names keep the lowercase match.
    - *Cost if wrong:* a name shown in lowercase would slip past the rule.
14. **Rank lends renown instead of doubling it in the rival roll.** A town that believes the latest list adds rank renown (12 for Heaven, 8 for Earth, 5 for Men and for Young Dragons) and puts the rank title first in the epithet. The 3a rival roll then sees a ranked fighter as renowned with no special case. *Cost if wrong:* a Human-list fighter with no other renown stays just below the rival threshold.
15. **A main menu that still overflows folds its tail under "More...".**
    - The dry run's sect-founder and long-lived fuzz runs reached 10 choices once the sky, the lists and treasures joined the general group.
    - The engine already folds people and routes; after that, anything past the eighth entry goes under "More...".
    - *Cost if wrong:* one more key press to reach a rare entry.

---
### Task 1: The world-event framework

**Files:**
- Create: `systems/world_events.py`, `systems/sky.py`, `systems/data/world_events.toml`, `narrate/sky_text.py`, `tests/sky_fork_example.py`
- Modify (via `.patches/4d_task1.py`): `systems/world_clock.py` (imports `systems.sky`), `debug/invariants.py` (`check_sky`), `narrate/outcomes.py` (imports `narrate.sky_text`), `narrate/procedural.py` (re-rolls away from recent lines of any kind; ruling 12), `debug/invariants.py` (people's names match by their capitals; ruling 13)
- Test: `tests/test_world_events.py`

**Interfaces:**
- Consumes:
  - `world.events.Event`, `commit`, `effect`, `listen`;
  - `world._cached`, `get_meta`, `set_meta`;
  - `world_clock.SEASON_HOOKS`, `market.EVENT_FACTORS`;
  - `facts.make_variant`, `record_fact`, `place_name`;
  - `gossip_text.SPECIAL_PHRASES`.
- Produces:
  - `systems.world_events` (imported as `W`):
    - constants: `SEASON = 360`, `STAGES`, `TYPES: dict[str, dict]`, `DEFAULTS`, `FACTOR_MIN = 0.25`, `FACTOR_MAX = 4.0`, `KEEP_INDEXED`;
    - index column constants: `ID`, `TYPE`, `SCOPE`, `PLACE`, `X`, `Y`, `STARTS`, `ACTIVE_FROM`, `ACTIVE_TO`, `OVER_AT`, `DONE`;
    - types: `full_spec(spec) -> dict`, `register(name, spec)`, `load_types(path=DATA)`;
    - time: `schedule(spec, starts) -> (ends, active_from, active_to, over_at)`, `stage_at(data, t) -> str`, `stages_of(data) -> list[str]`;
    - places: `index(world) -> list[list]`, `place_xy(world, place)`, `covers(row, place, xy) -> bool`, `showing(world, place, at=None) -> list[list]`;
    - modifiers: `factor(world, place, key, at=None) -> float`, `price_factor(world, town, good) -> float`.
  - `systems.sky`:
    - hooks: `module(kind)`, `start_events(world, kind, place, starts, data=None) -> list[Event]`;
    - observing: `stage_events(world, place=None) -> list[Event]`, `observe(world, place=None) -> list[int]`;
    - news: `news_town(world, data) -> int | None`, `reading(world, kind, town) -> str | None`;
    - clock: `season_events(world, n)`, `observe_all(world, n)`.
  - Event kinds `sky_started` and `world_event_stage` (data `occurrence`, `type`, `stage`).
  - Fact predicate `phenomenon`: subject is a town; the variant carries `kind`, `stage` and `reading`; data carries `occurrence` and `until`.
  - `debug.invariants.check_sky(world) -> list[str]`.
  - `narrate.sky_text`: `NAMES: dict[str, str]`, `phenomenon_name(kind) -> str`.

- [ ] **Step 1: Write the failing test** — `tests/test_world_events.py`
```python
import json
import time

import pytest

import systems.market as market
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_sky
from engine.game import Game
from narrate.gossip_text import rumour_text
from systems.creation import CreationChoice
from world.events import commit
from world.gen.materialize import ensure_town, region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def add_type(monkeypatch, name, **spec):
    monkeypatch.setitem(W.TYPES, name, W.full_spec(spec))


def begin(world, kind, place, starts=None, **data):
    events = sky.start_events(world, kind, place, world.time if starts is None else starts, data)
    assert events, f"{kind} did not start"
    commit(world, events)
    return W.index(world)[-1][W.ID]


def stages_seen(world, occurrence):
    rows = world._conn.execute("select data from chronicle where kind = 'world_event_stage' order by id").fetchall()
    return [d["stage"] for d in map(lambda r: json.loads(r[0]), rows) if d["occurrence"] == occurrence]


OMEN = dict(scope="town", cycle="trigger", stages={"foretold": 2, "announced": 3, "active": 5, "aftermath": 4})


def test_stages_follow_the_calendar(game, monkeypatch):
    add_type(monkeypatch, "omen", **OMEN)
    world, t0 = game.world, game.world.time
    data = world.entity(begin(world, "omen", game.place.id)).data
    assert [W.stage_at(data, t0 + d * 4) for d in (0, 2, 5, 9, 10, 13, 14)] == \
        ["foretold", "announced", "active", "active", "aftermath", "aftermath", "over"]
    assert W.stage_at(data, t0 - 1) == "pending"


def test_each_stage_is_observed_once(game, monkeypatch):
    add_type(monkeypatch, "omen", **OMEN)
    world, t0 = game.world, game.world.time
    occurrence = begin(world, "omen", game.place.id)
    for day in (0, 3, 3, 11, 20, 20):
        world.set_time(t0 + day * 4)
        sky.observe(world, game.place.id)
    assert stages_seen(world, occurrence) == ["foretold", "announced", "active", "aftermath", "over"]
    assert world.entity(occurrence).data["over"] and W.index(world)[-1][W.DONE]
    assert check_sky(world) == []


def test_a_catch_up_starts_nothing_already_over(game, monkeypatch):
    add_type(monkeypatch, "tide", scope="region", chance=1.0, stages={"active": 200})
    world = game.world
    world.set_time(world.time + 20 * W.SEASON)
    now = world.time // W.SEASON
    assert [e for e in sky.season_events(world, now - 5) if e.data["type"] == "tide"] == []
    assert [e for e in sky.season_events(world, now) if e.data["type"] == "tide"]


def test_modifiers_multiply_and_clamp(game, monkeypatch):
    add_type(monkeypatch, "calm", scope="world", cycle="trigger", stages={"active": 30}, modifiers={"cultivation": 1.5})
    add_type(monkeypatch, "storm", scope="region", cycle="trigger", stages={"active": 30}, modifiers={"cultivation": 4.0})
    add_type(monkeypatch, "drain", scope="town", cycle="trigger", stages={"active": 30}, modifiers={"cultivation": 0.01})
    world, town = game.world, game.place.id
    far = ensure_town(world, 5, 5, 0)
    assert W.factor(world, town, "cultivation") == 1.0
    begin(world, "calm", None)
    assert W.factor(world, town, "cultivation") == 1.5 and W.factor(world, None, "cultivation") == 1.5
    begin(world, "storm", region_of(world, town).id)
    assert W.factor(world, town, "cultivation") == 4.0
    assert W.factor(world, far, "cultivation") == 1.5
    begin(world, "drain", town)
    assert W.factor(world, town, "cultivation") == 0.25
    assert W.factor(world, town, "breakthrough") == 1.0
    world.set_time(world.time + 31 * 4)
    assert W.factor(world, town, "cultivation") == 1.0


def test_one_live_occurrence_per_type_per_place(game, monkeypatch):
    add_type(monkeypatch, "omen", **OMEN)
    begin(game.world, "omen", game.place.id)
    assert sky.start_events(game.world, "omen", game.place.id, game.world.time) == []
    assert sky.start_events(game.world, "omen", ensure_town(game.world, 1, 0, 0), game.world.time)


def test_an_old_world_has_a_quiet_sky(game):
    assert W.index(game.world) == [] and W.factor(game.world, game.place.id, "cultivation") == 1.0
    assert check_sky(game.world) == []


def test_a_type_from_toml_runs_its_module(game, monkeypatch, tmp_path):
    import tests.sky_fork_example as fork
    monkeypatch.setattr(W, "TYPES", dict(W.TYPES))
    path = tmp_path / "fork.toml"
    path.write_text('[fork_omen]\nmodule = "tests.sky_fork_example"\nscope = "town"\ncycle = "trigger"\n'
                    'stages = { active = 3 }\n', encoding="utf-8")
    W.load_types(path)
    fork.SEEN.clear()
    world = game.world
    begin(world, "fork_omen", game.place.id)
    world.set_time(world.time + 20)
    sky.observe(world)
    assert fork.SEEN == ["active", "over"]


def test_news_carries_a_local_reading(game, monkeypatch):
    add_type(monkeypatch, "omen", scope="town", cycle="trigger", stages={"announced": 2, "active": 5},
             readings=["war", "plenty"], news={"predicate": "phenomenon", "weight": 1.2, "stages": ["announced"]})
    world, town = game.world, game.place.id
    begin(world, "omen", town)
    sky.observe(world, town)
    [fact] = world.facts(predicate="phenomenon", subject=town)
    assert fact.variant["kind"] == "omen" and fact.variant["stage"] == "announced"
    assert fact.variant["reading"] in ("war", "plenty") and fact.data["occurrence"]
    text = rumour_text(world, fact.variant, game.player.id)
    assert "omen" in text and "{" not in text


def test_prices_follow_the_sky(game, monkeypatch):
    add_type(monkeypatch, "dearth", scope="town", cycle="trigger", stages={"active": 30}, prices={"salt": 2.0})
    world, town = game.world, game.place.id
    before = market.price(world, town, "salt")
    begin(world, "dearth", town)
    assert market.price(world, town, "salt") == pytest.approx(before * 2, abs=1)


def test_the_sky_rules_catch_a_broken_calendar(game, monkeypatch):
    add_type(monkeypatch, "omen", **OMEN)
    world = game.world
    occurrence = begin(world, "omen", game.place.id)
    assert check_sky(world) == []
    world.update_data(occurrence, seen=["active", "foretold"])
    assert any("out of order" in p for p in check_sky(world))


def test_the_narrator_never_repeats_a_line_of_another_kind():
    from dataclasses import replace
    from narrate.procedural import Grammar, ProceduralNarrator
    from tests.test_narrate import brief
    narrator = ProceduralNarrator(Grammar({"a": {"lines": ["#x#"]}, "b": {"lines": ["#x#"]},
                                           "symbols": {"x": ["One.", "Two."]}}))
    [(first, _)] = narrator.narrate(brief("a"))
    [(second, _)] = narrator.narrate(replace(brief("b"), salt="t:b:1"))
    assert first != second


def test_a_name_that_is_also_a_word_is_matched_by_its_capital(game):
    from types import SimpleNamespace
    from debug.invariants import check_people
    stranger = game.world.add_entity("person", "Again", {"age": 30, "occupation": "monk"})
    game.world.relate(stranger, ensure_town(game.world, 4, 4, 0), "located_in")
    quiet = SimpleNamespace(lines=[("Until the rivers meet again.", "npc")], all_choices=[])
    loud = SimpleNamespace(lines=[("Again the monk bows.", "npc")], all_choices=[])
    assert check_people(game, quiet) == []
    assert any("Again" in p for p in check_people(game, loud))


def test_factor_is_quick(game, monkeypatch):
    add_type(monkeypatch, "storm", scope="region", cycle="trigger", stages={"active": 30}, modifiers={"cultivation": 1.1})
    world = game.world
    for x in range(20):
        begin(world, "storm", region_of(world, ensure_town(world, x, 3, 0)).id)
    town = game.place.id
    start = time.process_time()
    for _ in range(1000):
        W.factor(world, town, "cultivation")
    assert time.process_time() - start < 0.2
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_world_events.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.sky'`.

- [ ] **Step 3: Write the framework** — `systems/world_events.py`
```python
"""World events (phase 4d spec 3): typed occurrences whose stages follow the calendar, and the modifiers they lend.

A type is an entry in `systems/data/world_events.toml`, and may name a module with hooks
(systems/sky.py says when each runs):

    eligible(world, place, n) -> bool           may one start here in season n?
    start_data(world, place, n, rng) -> dict    its own data, fixed when it starts (None: do not start)
    on_stage(world, occurrence, stage) -> list  the events of a stage, the first time it is observed

A fork adds an event with one TOML entry and one module; the engine is untouched.

This module only reads. The occurrences that still matter are listed in the `sky_index` meta
row as [id, type, scope, place, x, y, starts, active_from, active_to, over_at, done], so asking
what is in the sky over a place never scans the world's history.
"""

import tomllib
from pathlib import Path

from systems.time import DAYS_PER_SEASON, WATCHES_PER_DAY

SEASON = DAYS_PER_SEASON * WATCHES_PER_DAY
STAGES = ("foretold", "announced", "active", "aftermath")
SCOPES = ("world", "region", "town", "site")
FACTOR_MIN, FACTOR_MAX = 0.25, 4.0
KEEP_INDEXED = 44 * SEASON  # the life clock replays up to 40 missed seasons in full (4a) and asks about them
DATA = Path(__file__).parent / "data" / "world_events.toml"
DEFAULTS = {"module": None, "scope": "town", "cycle": "season", "chance": 0.0, "stages": {}, "modifiers": {},
            "prices": {}, "readings": [], "news": None}
TYPES: dict[str, dict] = {}
ID, TYPE, SCOPE, PLACE, X, Y, STARTS, ACTIVE_FROM, ACTIVE_TO, OVER_AT, DONE = range(11)


def full_spec(spec: dict) -> dict:
    full = {**DEFAULTS, **spec}
    if full["scope"] not in SCOPES:
        raise ValueError(f"unknown scope {full['scope']!r}")
    full["stages"] = {stage: int(full["stages"].get(stage, 0)) for stage in STAGES}
    return full


def register(name: str, spec: dict) -> None:
    """Add or replace an event type (the TOML loader uses this; so may a fork)."""
    TYPES[name] = full_spec(spec)


def load_types(path: Path = DATA) -> None:
    with open(path, "rb") as handle:
        for name, spec in tomllib.load(handle).items():
            register(name, spec)


def schedule(spec: dict, starts: int) -> tuple[dict, int, int, int]:
    """(the end of each stage it has, when its active stage begins and ends, when it is over) from a start."""
    ends, t = {}, starts
    active_from = active_to = starts
    for stage in STAGES:
        days = spec["stages"][stage]
        if not days:
            continue
        if stage == "active":
            active_from = t
        t += days * WATCHES_PER_DAY
        ends[stage] = t
        if stage == "active":
            active_to = t
    return ends, active_from, active_to, t


def stage_at(data: dict, t: int) -> str:
    """Its stage at time t: "pending" before it starts, "over" once its last stage has ended."""
    if t < data["starts"]:
        return "pending"
    for stage in STAGES:
        end = data["ends"].get(stage)
        if end is not None and t < end:
            return stage
    return "over"


def stages_of(data: dict) -> list[str]:
    """The stages this occurrence has, in order, ending with "over"."""
    return [stage for stage in STAGES if stage in data["ends"]] + ["over"]


def index(world) -> list[list]:
    return world._cached(("sky_index",), lambda: world.get_meta("sky_index", []))


def _xy(world, place: int):
    entity = world.entity(place)
    return None if entity is None or "x" not in entity.data else (entity.data["x"], entity.data["y"])


def place_xy(world, place: int | None):
    """The region coordinates of a town or a region (a town's data carries its region's x and y)."""
    if place is None:
        return None
    return world._cached(("sky_xy", place), lambda: [_xy(world, place)])[0]


def covers(row: list, place: int | None, xy) -> bool:
    scope = row[SCOPE]
    if scope == "world":
        return True
    if place is None:
        return False
    if scope == "region":
        return xy is not None and (row[X], row[Y]) == tuple(xy)
    return row[PLACE] == place


def showing(world, place: int | None, at: int | None = None) -> list[list]:
    """Index rows over `place` that have begun and are not yet over at `at`."""
    at = world.time if at is None else at
    xy = place_xy(world, place)
    return [row for row in index(world) if row[STARTS] <= at < row[OVER_AT] and covers(row, place, xy)]


def factor(world, place: int | None, key: str, at: int | None = None) -> float:
    """The `key` modifiers of every occurrence active over `place` at `at` (None: the world-wide ones), clamped."""
    at = world.time if at is None else at
    hits = [row for row in index(world)
            if row[ACTIVE_FROM] <= at < row[ACTIVE_TO] and key in TYPES.get(row[TYPE], DEFAULTS)["modifiers"]]
    if not hits:
        return 1.0
    xy = place_xy(world, place)
    value = 1.0
    for row in hits:
        if covers(row, place, xy):
            value *= TYPES[row[TYPE]]["modifiers"][key]
    return max(FACTOR_MIN, min(FACTOR_MAX, value))


def price_factor(world, town: int, good: str) -> float:
    """The price multipliers of occurrences active over this town (4c market clamps the product)."""
    at = world.time
    hits = [row for row in index(world)
            if row[ACTIVE_FROM] <= at < row[ACTIVE_TO] and good in TYPES.get(row[TYPE], DEFAULTS)["prices"]]
    if not hits:
        return 1.0
    xy = place_xy(world, town)
    value = 1.0
    for row in hits:
        if covers(row, town, xy):
            value *= TYPES[row[TYPE]]["prices"][good]
    return value


load_types()
```

- [ ] **Step 4: Write the sky's clock** — `systems/sky.py`
```python
"""The sky's clock (phase 4d spec 3): occurrences start, their stages are observed, and towns talk.

`start_events` begins an occurrence. `observe` commits a `world_event_stage` event for each
stage reached but not yet seen, and the type's module reacts. The world clock rolls the
season-cycle types and observes everything each season; the engine observes the player's
place on every scene, so what happens in the sky happens whether or not anyone is there.
"""

import importlib

import systems.market as market
import systems.world_clock as world_clock
import systems.world_events as W
from systems.facts import make_variant, place_name, record_fact
from systems.time import DAYS_PER_SEASON, WATCHES_PER_DAY
from world.events import Event, commit, effect, listen
from world.seed import rng_for

NEWS_STAGES = ("announced", "active")
LOCAL = ("town", "site")


def module(kind: str):
    path = W.TYPES[kind]["module"]
    return importlib.import_module(path) if path else None


def _hook(kind: str, name: str):
    found = module(kind) if kind in W.TYPES else None
    return getattr(found, name, None) if found is not None else None


def start_events(world, kind: str, place: int | None, starts: int, data: dict | None = None) -> list[Event]:
    """An occurrence of `kind` over `place` from `starts`; none if one is live there or it would be long over."""
    spec = W.TYPES[kind]
    ends, active_from, active_to, over_at = W.schedule(spec, starts)
    if over_at <= world.time:
        return []
    if any(row[W.TYPE] == kind and row[W.PLACE] == place and not row[W.DONE] and row[W.OVER_AT] > starts
           for row in W.index(world)):
        return []
    x, y = W.place_xy(world, place) or (None, None)
    return [Event("sky_started", (), place if spec["scope"] in LOCAL else None, {
        "type": kind, "scope": spec["scope"], "place": place, "x": x, "y": y, "starts": starts, "ends": ends,
        "active": [active_from, active_to], "over_at": over_at, "data": data or {}})]


@effect("sky_started")
def _started(world, event) -> None:
    d = event.data
    occurrence = world.add_entity("world_event", d["type"].replace("_", " "), {**d, "seen": [], "over": False})
    keep = [row for row in W.index(world) if row[W.OVER_AT] > world.time - W.KEEP_INDEXED]
    keep.append([occurrence, d["type"], d["scope"], d["place"], d["x"], d["y"], d["starts"], d["active"][0],
                 d["active"][1], d["over_at"], False])
    world.set_meta("sky_index", keep)


def stage_events(world, place: int | None = None) -> list[Event]:
    """An event for every stage reached but not yet seen, over `place` (everywhere when None)."""
    now = world.time
    xy = W.place_xy(world, place)
    events = []
    for row in W.index(world):
        if row[W.DONE] or now < row[W.STARTS] or (place is not None and not W.covers(row, place, xy)):
            continue
        occurrence = world.entity(row[W.ID])
        d = occurrence.data
        order = W.stages_of(d)
        for stage in order[: order.index(W.stage_at(d, now)) + 1]:
            if stage not in d["seen"]:
                events.append(Event("world_event_stage", (), d["place"] if d["scope"] in LOCAL else None,
                                    {"occurrence": occurrence.id, "type": d["type"], "stage": stage}))
    return events


def observe(world, place: int | None = None) -> list[int]:
    events = stage_events(world, place)
    return commit(world, events) if events else []


@effect("world_event_stage")
def _stage(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    world.update_data(occurrence.id, seen=list(occurrence.data["seen"]) + [d["stage"]], over=d["stage"] == "over")
    if d["stage"] == "over":
        world.set_meta("sky_index", [row if row[W.ID] != occurrence.id else row[:W.DONE] + [True]
                                     for row in W.index(world)])


@listen("world_event_stage")
def _react(world, event, event_id: int) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    _news(world, occurrence, d["stage"], event_id)
    react = _hook(d["type"], "on_stage")
    if react is not None:
        events = react(world, occurrence, d["stage"])
        if events:
            commit(world, events)


def news_town(world, d: dict) -> int | None:
    """The town whose people first talk about an occurrence."""
    if d["scope"] in LOCAL:
        return d["place"]
    if d["scope"] == "region":
        towns = sorted(t for t in world.sources(d["place"], "located_in") if world.entity(t).kind == "town")
        return towns[0] if towns else None
    capital = world.get_meta("capital")
    if capital is not None:
        return capital
    towns = world.entities("town")
    return towns[0].id if towns else None


def reading(world, kind: str, town: int) -> str | None:
    """What this town makes of it: each town has its own superstition (spec §3.5)."""
    readings = W.TYPES.get(kind, W.DEFAULTS)["readings"]
    return rng_for(world.world_seed, f"reading:{kind}:{town}").choice(readings) if readings else None


def _news(world, occurrence, stage: str, event_id: int) -> None:
    d = occurrence.data
    news = W.TYPES.get(d["type"], W.DEFAULTS)["news"]
    if not news or stage not in news.get("stages", NEWS_STAGES):
        return
    town = news_town(world, d)
    if town is None:
        return
    predicate = news.get("predicate", "phenomenon")
    variant = make_variant(predicate, town, None, place=place_name(world, town))
    variant.update(kind=d["type"], stage=stage, reading=reading(world, d["type"], town))
    record_fact(world, town, predicate, None, place=town, source_event=event_id, weight=news.get("weight", 1.0),
                variant=variant, extra={"occurrence": occurrence.id, "until": d["ends"].get(stage, d["over_at"])})


def _places(world, scope: str) -> list[tuple[int | None, str]]:
    if scope == "world":
        return [(None, "world")]
    kind = "town" if scope == "town" else "region"
    return [(e.id, e.seed_path or str(e.id)) for e in world.entities(kind)]


def _site(world, region: int, rng) -> int | None:
    towns = sorted(t for t in world.sources(region, "located_in") if world.entity(t).kind == "town")
    return rng.choice(towns) if towns else None


def season_events(world, n: int) -> list[Event]:
    """Roll every season-cycle type for season n; each starts on a day of that season (spec §3.3)."""
    events = []
    for kind in sorted(W.TYPES):
        spec = W.TYPES[kind]
        if spec["cycle"] != "season" or spec["chance"] <= 0:
            continue
        for place, path in _places(world, spec["scope"]):
            rng = rng_for(world.world_seed, f"sky:{kind}:{path}:{n}")
            if rng.random() >= spec["chance"]:
                continue
            where = _site(world, place, rng) if spec["scope"] == "site" else place
            if spec["scope"] == "site" and where is None:
                continue
            starts = n * W.SEASON + rng.randrange(DAYS_PER_SEASON) * WATCHES_PER_DAY
            if W.schedule(spec, starts)[3] <= world.time:
                continue  # long over: a catch-up never starts old events now
            eligible = _hook(kind, "eligible")
            if eligible is not None and not eligible(world, where, n):
                continue
            make = _hook(kind, "start_data")
            data = make(world, where, n, rng) if make is not None else {}
            if data is not None:
                events += start_events(world, kind, where, starts, data)
    return events


def observe_all(world, n: int) -> list[Event]:
    """Every occurrence reaches its stages each season, whoever is watching."""
    observe(world)
    return []


world_clock.SEASON_HOOKS.extend([season_events, observe_all])
market.EVENT_FACTORS.append(W.price_factor)
for _kind in sorted(W.TYPES):
    module(_kind)  # a type's module may register hooks of its own (the blood moon's patrols)
```

- [ ] **Step 5: Write the first event type** — `systems/data/world_events.toml`
```toml
# World events (phase 4d spec 3-4): one entry per type. See systems/world_events.py for the fields.
# A fork adds an event here, and (if it needs hooks) a module under systems/events/.

[qi_tide]
scope = "region"
cycle = "season"
chance = 0.04
stages = { announced = 10, active = 90, aftermath = 20 }
modifiers = { cultivation = 1.5, breakthrough = 1.2 }
news = { predicate = "phenomenon", weight = 1.2, stages = ["announced", "active"] }
```

- [ ] **Step 6: Write the fork example the test loads** — `tests/sky_fork_example.py`
```python
"""A fork's event type, for tests: it only notes each stage it is shown."""

SEEN: list[str] = []


def on_stage(world, occurrence, stage):
    SEEN.append(stage)
    return []
```

- [ ] **Step 7: Write the narration** — `narrate/sky_text.py`
```python
"""What the player is told about the sky and the Murim's great events (phase 4d)."""

from narrate.gossip_text import SPECIAL_PHRASES
from narrate.outcomes import cap

NAMES = {"qi_tide": "a qi tide"}
STAGE_WORDS = {"foretold": "is foretold over", "announced": "gathers over", "active": "hangs over",
               "aftermath": "has passed over"}


def phenomenon_name(kind: str) -> str:
    return NAMES.get(kind, "a " + kind.replace("_", " "))


def _phenomenon_story(world, variant, viewer) -> str:
    where = variant.get("place") or "the land"
    text = f"{cap(phenomenon_name(variant.get('kind', 'omen')))} {STAGE_WORDS.get(variant.get('stage'), 'was seen over')} {where}."
    if variant.get("reading"):
        text += f" People say it means {variant['reading']}."
    return text


SPECIAL_PHRASES["phenomenon"] = _phenomenon_story
```

- [ ] **Step 8: Edit the existing files** — `.patches/4d_task1.py`
```python
"""Task 1 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


CLOCK = "systems/world_clock.py"
Path(CLOCK).write_text(Path(CLOCK).read_text(encoding="utf-8").rstrip("\n") + '''


import systems.sky  # noqa: E402,F401  phase 4d: the sky's season hooks
''', encoding="utf-8", newline="\n")

INV = "debug/invariants.py"
edit(INV, '''    problems += check_trade(world)
''', '''    problems += check_trade(world)
    problems += check_sky(world)
''')
edit(INV, '''def check_trade(world) -> list[str]:''', '''def check_sky(world) -> list[str]:
    """Phase 4d spec 8, rules 1-3: occurrences keep their calendar, one per type and place, modifiers in bounds."""
    import systems.world_events as W
    out, live = [], {}
    rows = W.index(world)
    for row in rows:
        occurrence = world.entity(row[W.ID])
        if occurrence is None or occurrence.kind != "world_event":
            out.append(f"the sky index names missing occurrence #{row[W.ID]}")
            continue
        d = occurrence.data
        if d["type"] not in W.TYPES:
            out.append(f"occurrence #{occurrence.id} has unknown type {d['type']!r}")
            continue
        ends = [d["ends"][s] for s in W.STAGES if s in d["ends"]]
        if ends != sorted(ends) or not ends or ends[0] <= d["starts"]:
            out.append(f"occurrence #{occurrence.id} has its stages out of order")
        if d["seen"] != W.stages_of(d)[:len(d["seen"])]:
            out.append(f"occurrence #{occurrence.id} saw its stages out of order: {d['seen']}")
        if d.get("over") and world.time < d["over_at"]:
            out.append(f"occurrence #{occurrence.id} is over before its time")
        if not row[W.DONE]:
            live.setdefault((row[W.TYPE], row[W.PLACE]), []).append(row)
        for key in W.TYPES[d["type"]]["modifiers"]:
            value = W.factor(world, None if row[W.SCOPE] == "world" else row[W.PLACE], key)
            if not W.FACTOR_MIN - 1e-9 <= value <= W.FACTOR_MAX + 1e-9:
                out.append(f"the {key} modifier over #{row[W.PLACE]} is {value}")
    for (kind, place), found in live.items():
        found.sort(key=lambda r: r[W.STARTS])
        for a, b in zip(found, found[1:]):
            if a[W.OVER_AT] > b[W.STARTS]:
                out.append(f"two {kind} occurrences overlap over #{place}")
    return out


def check_trade(world) -> list[str]:''')

PROC = "narrate/procedural.py"  # a new world path showed the same road line from two grammar keys in a row
edit(PROC, '''        self._last_salt: dict[str, tuple[str, str]] = {}
''', '''        self._last_salt: dict[str, tuple[str, str]] = {}
        self._shown: deque[str] = deque(maxlen=2 * self.RECENT)  # lines of any kind: last turn's and this one's
''')
edit(PROC, '''        for _ in range(self.REROLLS):
            if text not in recent:
                break
            text = self.grammar.expand(key, rng, context)
''', '''        fallback = None
        for _ in range(self.REROLLS):
            if text not in recent:
                if text not in self._shown:
                    break
                fallback = fallback or text  # new to its kind if not to the screen: the best a small grammar can do
            text = self.grammar.expand(key, rng, context)
        else:
            text = fallback or text
''')
edit(PROC, '''        recent.append(text)
''', '''        recent.append(text)
        self._shown.append(text)
''')

edit(INV, '''    text = "\\n".join([t for t, _ in turn.lines] + [c.label for c in turn.all_choices]).lower()
''', '''    raw = "\\n".join([t for t, _ in turn.lines] + [c.label for c in turn.all_choices])
    text = raw.lower()
''')
edit(INV, '''            if re.search(rf"(?<![\\w-]){re.escape(name)}(?![\\w-])", text):
                out.append(f"{entity.name} (#{entity.id}) is named on screen but the player never heard of them")''',
     '''            if re.search(rf"(?<![\\w-]){re.escape(entity.name)}(?![\\w-])", raw):  # a proper noun: "again" is not Again
                out.append(f"{entity.name} (#{entity.id}) is named on screen but the player never heard of them")''')

edit("narrate/outcomes.py", '''import narrate.market_text  # noqa: E402,F401
''', '''import narrate.market_text  # noqa: E402,F401
import narrate.sky_text  # noqa: E402,F401
''')
print("task 1 edits applied")
```

- [ ] **Step 9: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4d_task1.py && .venv/Scripts/python.exe -m pytest tests/test_world_events.py -q -p no:cacheprovider`
Expected: `task 1 edits applied`, then `13 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 10: Commit**

Run: `git add -A && git commit -m "feat: the world-event framework - typed occurrences, stages from the calendar, modifiers and news"`

---
### Task 2: The knobs, and the qi tide, blood moon, comet and dao resonance

**Files:**
- Create: `systems/events/__init__.py` (empty), `systems/events/blood_moon.py`, `systems/events/dao_resonance.py`
- Modify (via `.patches/4d_task2.py`):
  - `systems/cultivation.py`: the `cultivation`, `breakthrough` and `practice` knobs for the player;
  - `systems/lives.py`: `cultivation` and `breakthrough` for NPCs, read at the season being lived;
  - `systems/encounters.py`: `encounter`;
  - `systems/wars.py`: `clash`;
  - `systems/duel.py`: `demonic`;
  - `systems/data/world_events.toml`: blood moon, comet, dao resonance;
  - `narrate/sky_text.py`: their names.
- Test: `tests/test_phenomena.py`

**Interfaces:**
- Consumes (Task 1): `W.factor(world, place, key, at=None)`, `W.SEASON`, `W.TYPES`, `sky.start_events`, `sky.observe`; `tests.test_world_events.add_type` and `begin`.
- Produces:
  - Knob keys read by existing systems: `cultivation`, `breakthrough`, `practice`, `encounter`, `clash`, `demonic`, `patrol`.
  - `systems.events.blood_moon`: `patrols(world, player) -> list[int]`, registered in `encounters.HUNTER_HOOKS`.
  - `systems.events.dao_resonance`: `MASTER_REALM = 3`, and the hooks `eligible`, `start_data` and `on_stage`.
  - Fact predicate `enlightened`: subject is the master; the variant carries `realm` and `age`.
  - `lives._sky(world, place, n) -> dict`: the boosts over the season being lived.
  - `duel._dark_boost(world, person) -> float`.

- [ ] **Step 1: Write the failing test** — `tests/test_phenomena.py`
```python
import random

import pytest

import systems.cultivation as cultivation
import systems.encounters as encounters
import systems.lives as lives
import systems.market as market
import systems.sky as sky
import systems.wars as wars
import systems.world_events as W
from engine.game import Game
from systems import founding
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.duel import fighter_for
from systems.techniques import martial_arts
from tests.test_world_events import add_type, begin
from world.gen.materialize import region_of
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


def faction_of_type(world, kind):
    return next(f.id for f in world.entities("faction") if f.data["type"] == kind)


def join(world, person, faction):
    world.relate(person, faction, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                   "secret": False})


def test_a_qi_tide_speeds_the_players_cultivation_and_breakthrough(game):
    world, me, town = game.world, game.player.id, game.place.id
    body = load_body(world, me)
    body.bottleneck = True
    save_body(world, me, body)
    gained = cultivation.meditate_events(world, me, town, 7)[0].data["energy_gained"]
    chance = cultivation.breakthrough_events(world, me, town)[0].data["chance"]
    begin(world, "qi_tide", region_of(world, town).id, starts=world.time - 11 * 4)
    assert cultivation.meditate_events(world, me, town, 7)[0].data["energy_gained"] == pytest.approx(gained * 1.5, rel=0.01)
    assert cultivation.breakthrough_events(world, me, town)[0].data["chance"] == pytest.approx(min(max(chance, 0.95), chance * 1.2))


def test_npc_growth_reads_the_sky_of_its_own_season(game):
    world, town = game.world, game.place.id
    adept = world.entity(founding.make_person(world, "test:adept", town, occupation="wandering swordsman", age=30))
    n = world.time // W.SEASON
    plain = lives.step_events(world, adept, n, random.Random(1), 1, True)[0].data["years"]
    begin(world, "qi_tide", region_of(world, town).id, starts=n * W.SEASON)
    assert lives.step_events(world, adept, n, random.Random(1), 1, True)[0].data["years"] == pytest.approx(plain * 1.5, rel=0.01)
    assert lives.step_events(world, adept, n - 3, random.Random(1), 1, True)[0].data["years"] == pytest.approx(plain, rel=0.01)


def test_a_blood_moon_strengthens_dark_arts_only(game):
    world, town = game.world, game.place.id
    cultist = founding.make_person(world, "test:cultist", town, occupation="wandering swordsman", age=30)
    join(world, cultist, faction_of_type(world, "demonic_cult"))
    monk = founding.make_person(world, "test:monk", town, occupation="monk", age=30)
    join(world, monk, faction_of_type(world, "orthodox_sect"))
    dark, bright = fighter_for(world, cultist, None).realm_mult, fighter_for(world, monk, None).realm_mult
    begin(world, "blood_moon", None, starts=world.time - 6 * 4)
    assert fighter_for(world, cultist, None).realm_mult == pytest.approx(dark * 1.3)
    assert fighter_for(world, monk, None).realm_mult == pytest.approx(bright)


def test_the_encounter_knob_fills_the_roads(game, monkeypatch):
    add_type(monkeypatch, "red_sky", scope="world", cycle="trigger", stages={"active": 1000}, modifiers={"encounter": 4.0})
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.2)
    world, me, town = game.world, game.player.id, game.world.entity(game.place.id)

    def count():
        found = 0
        for t in range(400):
            world.set_time(10 * W.SEASON + 1000 + t)
            found += bool(encounters.road_encounter_events(world, me, town))
        return found
    plain = count()
    world.set_time(10 * W.SEASON + 1000)
    begin(world, "red_sky", None)
    assert count() > plain * 2


def test_the_clash_knob_stirs_war(game, monkeypatch):
    add_type(monkeypatch, "war_star", scope="world", cycle="trigger", stages={"active": 200}, modifiers={"clash": 4.0})
    monkeypatch.setattr(wars, "CLASH_CHANCE", 0.25)
    monkeypatch.setattr(wars, "WAR_CHANCE", 0.25)
    world = game.world
    n = world.time // W.SEASON
    plain = len([e for e in wars.clash_events(world, n) if e.kind == "clash"])
    begin(world, "war_star", None, starts=n * W.SEASON)
    assert len([e for e in wars.clash_events(world, n) if e.kind == "clash"]) > plain


def test_a_comet_raises_salt_and_rice(game):
    world, town = game.world, game.place.id
    salt, rice, silk = (market.price(world, town, g) for g in ("salt", "rice", "silk"))
    begin(world, "comet", None, starts=world.time - 31 * 4)
    assert market.price(world, town, "salt") == pytest.approx(salt * 1.3, abs=1)
    assert market.price(world, town, "rice") == pytest.approx(rice * 1.3, abs=1)
    assert market.price(world, town, "silk") == silk


def test_a_comet_is_read_differently_town_by_town(game):
    readings = {sky.reading(game.world, "comet", t) for t in range(1, 60)}
    assert len(readings) > 1 and readings <= set(W.TYPES["comet"]["readings"])


def test_a_dao_resonance_doubles_practice_and_names_the_master(game):
    import systems.events.dao_resonance as dao
    world, me, town = game.world, game.player.id, game.place.id
    master = founding.make_person(world, "test:master", town, occupation="monk", age=60, realm="first-rate")
    n = world.time // W.SEASON
    assert dao.eligible(world, town, n)
    art = martial_arts(world, me)[0]
    plain = cultivation.practise_events(world, me, town, art.technique.id, 2)[0].data
    world.set_time(world.time + 1)
    begin(world, "dao_resonance", town, **dao.start_data(world, town, n, rng_for(1, "t")))
    sky.observe(world, town)
    boosted = cultivation.practise_events(world, me, town, art.technique.id, 2)[0].data
    assert boosted["mastery_after"] - boosted["mastery_before"] == pytest.approx(
        2 * (plain["mastery_after"] - plain["mastery_before"]), rel=0.01)
    [fact] = world.facts(predicate="enlightened", subject=master)
    assert fact.variant["actor"] == master and fact.variant["realm"] == "first-rate"


def test_blood_moon_patrols_call_out_the_ruthless(game, monkeypatch):
    import systems.events.blood_moon as blood_moon
    from systems.reputation import Reputation
    world, me, town = game.world, game.player.id, game.place.id
    monk = founding.make_person(world, "test:monk", town, occupation="monk", age=30)
    join(world, monk, faction_of_type(world, "orthodox_sect"))
    monkeypatch.setattr(blood_moon, "reputation", lambda w, t, s: Reputation(9.0, "known", "ruthless", None))
    assert blood_moon.patrols(world, me) == []
    begin(world, "blood_moon", None, starts=world.time - 6 * 4)
    assert monk in blood_moon.patrols(world, me)
    assert blood_moon.patrols in encounters.HUNTER_HOOKS
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_phenomena.py -q -p no:cacheprovider`
Expected: failures. For example, a qi tide leaves `energy_gained` unchanged, and `KeyError: 'blood_moon'`.

- [ ] **Step 3: Write the blood moon** — `systems/events/blood_moon.py`
```python
"""The blood moon (phase 4d spec 4.3): demonic arts grow strong, the roads grow dangerous, righteous sects patrol.

Its modifiers live in the TOML; this module adds the patrols (plan ruling 9): righteous
fighters in a town where you are known as ruthless call you out, like avengers do.
"""

import systems.encounters as encounters
import systems.world_events as W
from systems import factions as F
from systems.beliefs import apparent_to
from systems.reputation import reputation
from world.gen.materialize import people_at

RIGHTEOUS = frozenset({"orthodox_sect", "school"})


def patrols(world, player: int) -> list[int]:
    """Righteous fighters here who call out someone known here as ruthless, while the blood moon is up."""
    here = world.targets(player, "located_in")
    if not here or W.factor(world, here[0], "patrol") <= 1.0:
        return []
    town = here[0]
    if reputation(world, town, apparent_to(world, town, player)).path != "ruthless":
        return []
    return [p.id for p in people_at(world, town, exclude=player)
            if any(world.entity(f).data.get("type") in RIGHTEOUS and d.get("status", "member") == "member"
                   for f, _, d in F.memberships(world, p.id))]


encounters.HUNTER_HOOKS.append(patrols)
```

- [ ] **Step 4: Write the dao resonance** — `systems/events/dao_resonance.py`
```python
"""Dao resonance (phase 4d spec 4.6): a master's enlightenment makes a town hum; practice there comes twice as fast."""

import systems.lives as lives
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from world.gen.materialize import people_at

MASTER_REALM = 3  # First-rate


def _master(world, town: int):
    found = [p for p in people_at(world, town)
             if lives.simulated(p) and realm_index(p.data.get("realm", "mortal")) >= MASTER_REALM]
    return max(found, key=lambda p: (realm_index(p.data["realm"]), -p.id), default=None)


def eligible(world, town: int, n: int) -> bool:
    return _master(world, town) is not None


def start_data(world, town: int, n: int, rng) -> dict | None:
    master = _master(world, town)
    return {"master": master.id} if master is not None else None


def on_stage(world, occurrence, stage: str) -> list:
    if stage != "active":
        return []
    d = occurrence.data
    master, town = world.entity(d["data"]["master"]), d["place"]
    variant = make_variant("enlightened", master.id, None, place=place_name(world, town),
                           realm=master.data.get("realm", "mortal"))
    variant["age"] = int(master.data.get("age", 30))
    record_fact(world, master.id, "enlightened", None, place=town, weight=1.5, variant=variant)
    return []
```

- [ ] **Step 5: Edit the existing files** — `.patches/4d_task2.py`
```python
"""Task 2 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


Path("systems/events/__init__.py").write_text("", encoding="utf-8")

CULT = "systems/cultivation.py"
edit(CULT, "from systems import realms\n", "import systems.world_events as W\nfrom systems import realms\n")
edit(CULT, '''    gained = realms.add_energy(trial, energy_rate(body, heart_data, days, world.time) * days)''',
     '''    gained = realms.add_energy(trial, energy_rate(body, heart_data, days, world.time) * days
                               * W.factor(world, place, "cultivation"))  # a qi tide (phase 4d)''')
edit(CULT, '''    chance = realms.breakthrough_chance(body, met)
''', '''    chance = realms.breakthrough_chance(body, met)
    chance = min(max(chance, 0.95), chance * W.factor(world, place, "breakthrough"))  # a qi tide (phase 4d)
''')
edit(CULT, '''    if CONSTITUTION_FORM.get(body.constitution) == art["form"]:
        gain *= 1.5
''', '''    if CONSTITUTION_FORM.get(body.constitution) == art["form"]:
        gain *= 1.5
    gain *= W.factor(world, place, "practice")  # a dao resonance (phase 4d)
''')

LIVES = "systems/lives.py"
edit(LIVES, "from systems import factions as F\nfrom systems.bodies import load_body\n",
     "import systems.world_events as W\nfrom systems import factions as F\nfrom systems.bodies import load_body\n")
edit(LIVES, '''def step_events(world, entity, n: int, rng, span: int, passive: bool) -> list[Event]:''',
     '''def _sky(world, place: int | None, n: int) -> dict:
    """The sky's boosts over season n, the season being lived (phase 4d): its own sky, not today's."""
    at = n * SEASON + SEASON // 2
    return {key: W.factor(world, place, key, at=at) for key in ("cultivation", "breakthrough")}


def step_events(world, entity, n: int, rng, span: int, passive: bool) -> list[Event]:''')
edit(LIVES, '''        years = round(0.25 * span * _talent(world, entity), 4)
        _, bottleneck = _grown(body, years)
        traits = SimpleNamespace(physique=body["physique"], purity=body["purity"], insight=body["insight"])
        breakthrough = bool(bottleneck and rng.random() < breakthrough_chance(traits, True))''',
     '''        sky = _sky(world, place, n) if span == 1 else {}  # coarse years are too long ago to matter
        years = round(0.25 * span * _talent(world, entity) * sky.get("cultivation", 1.0), 4)
        _, bottleneck = _grown(body, years)
        traits = SimpleNamespace(physique=body["physique"], purity=body["purity"], insight=body["insight"])
        breakthrough = bool(bottleneck and rng.random() < breakthrough_chance(traits, True) * sky.get("breakthrough", 1.0))''')

ENC = "systems/encounters.py"
edit(ENC, "from systems.beliefs import appears_as, apparent_to, home_of\n",
     "import systems.world_events as W\nfrom systems.beliefs import appears_as, apparent_to, home_of\n")
edit(ENC, '''    if rng.random() >= danger * ENCOUNTER_CHANCE:''',
     '''    if rng.random() >= danger * ENCOUNTER_CHANCE * W.factor(world, town.id, "encounter"):''')

WARS = "systems/wars.py"
edit(WARS, "from systems import factions as F\nfrom systems import halls\n",
     "import systems.world_events as W\nfrom systems import factions as F\nfrom systems import halls\n")
edit(WARS, '''    ids = clock_factions(world)
    known = stances(world, ids)
    events = []
''', '''    ids = clock_factions(world)
    known = stances(world, ids)
    events = []
    boost = W.factor(world, None, "clash", at=n * W.SEASON + W.SEASON // 2)  # a comet year (phase 4d)
''')
edit(WARS, '''            if rng.random() >= (WAR_CHANCE if value <= WAR else CLASH_CHANCE):''',
     '''            if rng.random() >= (WAR_CHANCE if value <= WAR else CLASH_CHANCE) * boost:''')

DUEL = "systems/duel.py"
edit(DUEL, "from systems.attitude import afraid\n", "import systems.world_events as W\nfrom systems.attitude import afraid\n")
edit(DUEL, '''def fighter_for(world, person_id: int, technique_id: int | None) -> Fighter:''',
     '''def _dark_boost(world, person_id: int) -> float:
    """A blood moon lends strength to the arts of demonic cults and unorthodox clans (phase 4d spec 4.3)."""
    if not W.index(world):
        return 1.0
    from systems import factions as F
    if not any(world.entity(f).data.get("type") in F.DARK and d.get("status", "member") == "member"
               for f, _, d in F.memberships(world, person_id)):
        return 1.0
    here = world.targets(person_id, "located_in")
    return W.factor(world, here[0] if here else None, "demonic")


def fighter_for(world, person_id: int, technique_id: int | None) -> Fighter:''')
edit(DUEL, '''        name=person.name, realm_mult=REALMS[body.realm].multiplier, stage=STAGES.index(stage_of(body)),''',
     '''        name=person.name, realm_mult=REALMS[body.realm].multiplier * _dark_boost(world, person_id),
        stage=STAGES.index(stage_of(body)),''')

TOML = "systems/data/world_events.toml"
Path(TOML).write_text(Path(TOML).read_text(encoding="utf-8") + '''
[blood_moon]
module = "systems.events.blood_moon"
scope = "world"
chance = 0.03
stages = { foretold = 5, active = 10 }
modifiers = { demonic = 1.3, encounter = 1.5, patrol = 2.0 }
readings = ["the dead walking", "a demon's birth", "blood spilled before the year is out", "a cult rising"]
news = { predicate = "phenomenon", weight = 1.5, stages = ["foretold", "active"] }

[comet]
scope = "world"
chance = 0.02
stages = { foretold = 30, active = 90 }
modifiers = { clash = 1.5 }
prices = { salt = 1.3, rice = 1.3 }
readings = ["war", "the fall of a dynasty", "the birth of a demon", "a sage descending"]
news = { predicate = "phenomenon", weight = 2.0, stages = ["foretold", "active"] }

[dao_resonance]
module = "systems.events.dao_resonance"
scope = "town"
chance = 0.01
stages = { active = 5 }
modifiers = { practice = 2.0 }
news = { predicate = "phenomenon", weight = 1.0, stages = ["active"] }
''', encoding="utf-8", newline="\n")

edit("narrate/sky_text.py", '''NAMES = {"qi_tide": "a qi tide"}''',
     '''NAMES = {"qi_tide": "a qi tide", "blood_moon": "a blood moon", "comet": "a comet",
         "dao_resonance": "a dao resonance"}''')
print("task 2 edits applied")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4d_task2.py && .venv/Scripts/python.exe -m pytest tests/test_phenomena.py -q -p no:cacheprovider`
Expected: `task 2 edits applied`, then `9 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 7: Commit**

Run: `git add -A && git commit -m "feat: the sky's knobs - qi tides, blood moons, comets and dao resonance move cultivation, roads, war, prices and practice"`

---
### Task 3: Tribulation lightning and the beast tide

**Files:**
- Create: `systems/events/tribulation.py`, `systems/events/beast_tide.py`, `engine/sky.py`, `narrate/grammar/sky.toml`
- Modify (via `.patches/4d_task3.py`):
  - `systems/lives.py`: `broke_through` carries its season;
  - `systems/encounters.py`: the `beasts` knob;
  - `systems/mortality.py`: the `beasts` cause;
  - `engine/game.py`: `SkyMixin` joins `Game`;
  - `systems/data/world_events.toml`: tribulation, beast tide;
  - `narrate/sky_text.py`: tribulation, hunt and bounty narration.
- Test: `tests/test_tribulations.py`

**Interfaces:**
- Consumes:
  - Task 1: `sky.start_events`, `sky.observe`, `W.index`, `W.covers`, `W.place_xy`.
  - Task 2: `W.factor`.
  - 4c: `price_events.shift`.
  - 2b: `duel._end_event`; the `breakthrough` event data (`success`, `realm_after`).
- Produces:
  - `systems.events.tribulation`:
    - constants: `TRIBULATION_REALM = 3`, `OUTCOMES`;
    - functions: `player_roll(world, pid) -> str`, `trigger_events(world, person, place, realm, season=None, outcome=None) -> list[Event]`.
  - Event `tribulation` (actor: the person; data `realm`, `outcome` = clean | scarred | crippled | None for NPCs), and fact `tribulation` (variant `realm`, `age`).
  - `systems.events.beast_tide`:
    - constants: `ATTACK_CHANCE = 0.3`, `KILLS_FOR_BOUNTY = 3`;
    - function: `hunt_events(world, player, place) -> list[Event]`.
  - Events `beast_hunted` (data `occurrence`, `kills`) and `bounty_paid` (data `occurrence`, `silver`).
  - `engine.sky.SkyMixin` with `_after_commit` (the player's tribulation) and `_after_duel` (beast hunts). Tasks 4 and 6 add to it.
  - Knob `beasts`.

- [ ] **Step 1: Write the failing test** — `tests/test_tribulations.py`
```python
import random

import pytest

import systems.encounters as encounters
import systems.events.beast_tide as beast_tide
import systems.events.tribulation as tribulation
import systems.market as market
import systems.realms as realms
import systems.sky as sky
import systems.world_events as W
import systems.duel as duel
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from tests.test_world_events import begin
from world.events import Event, commit
from world.gen.materialize import region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)


def texts(turn):
    return [t for t, _ in turn.lines]


def at_the_bottleneck(game, realm=2):
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years, body.bottleneck = realm, realms.REALMS[realm + 1].threshold, True
    save_body(game.world, game.player.id, body)


def test_breaking_through_to_first_rate_calls_down_the_lightning(game, monkeypatch):
    monkeypatch.setattr(realms, "breakthrough_chance", lambda body, met: 1.0)
    at_the_bottleneck(game)
    turn = game.perform(Action("breakthrough"))
    assert any("Clouds gather" in t for t in texts(turn)), texts(turn)
    world, me, town = game.world, game.player.id, game.place.id
    [fact] = world.facts(predicate="tribulation", subject=me)
    assert fact.variant["realm"] == "first-rate"
    assert any(row[W.TYPE] == "tribulation" for row in W.showing(world, town))


def test_a_lesser_breakthrough_brings_no_lightning(game, monkeypatch):
    monkeypatch.setattr(realms, "breakthrough_chance", lambda body, met: 1.0)
    at_the_bottleneck(game, realm=1)
    game.perform(Action("breakthrough"))
    assert game.world.facts(predicate="tribulation") == []


def test_purity_and_rest_steady_the_roll(game):
    world, me = game.world, game.player.id

    def outcomes(purity):
        body = load_body(world, me)
        body.purity = purity
        save_body(world, me, body)
        found = []
        for t in range(300):
            world.set_time(20 * W.SEASON + t)
            found.append(tribulation.player_roll(world, me))
        return found
    pure, rough = outcomes(0.9), outcomes(0.2)
    assert pure.count("clean") > rough.count("clean")
    assert "crippled" not in pure and "crippled" in rough


def test_scars_and_crippled_meridians_are_real(game):
    world, me, town = game.world, game.player.id, game.place.id
    commit(world, [Event("tribulation", (me,), town, {"realm": 3, "outcome": "scarred"})])
    assert any(i.kind == "internal" for i in load_body(world, me).injuries)
    commit(world, [Event("tribulation", (me,), town, {"realm": 3, "outcome": "crippled"})])
    assert any(m.state == "damaged" for m in load_body(world, me).meridians.values())


def test_an_npc_tribulation_lights_the_sky_only_if_it_is_recent(game):
    world, town = game.world, game.place.id
    n = world.time // W.SEASON
    elder = founding.make_person(world, "test:elder", town, occupation="monk", age=50, realm="second-rate")
    old = founding.make_person(world, "test:old", town, occupation="monk", age=70, realm="second-rate")
    commit(world, [Event("broke_through", (old,), town, {"realm": 3, "season": n - 5})])
    assert world.facts(predicate="tribulation", subject=old) and not W.showing(world, town)
    commit(world, [Event("broke_through", (elder,), town, {"realm": 3, "season": n})])
    assert world.facts(predicate="tribulation", subject=elder)
    assert any(row[W.TYPE] == "tribulation" for row in W.showing(world, town))
    assert any(m.feeling == "respect" for m in world.memories(game.player.id, about=elder))


def test_a_beast_tide_fills_the_roads_with_beasts(game, monkeypatch):
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.2)
    world, me, town = game.world, game.player.id, game.world.entity(game.place.id)

    def kinds():
        found = []
        for t in range(300):
            world.set_time(10 * W.SEASON + 100 + t)
            events = encounters.road_encounter_events(world, me, town)
            found += [e.data["kind"] for e in events if e.kind == "encounter"]
        return found
    plain = kinds()
    world.set_time(10 * W.SEASON + 100)
    long_tide = dict(W.TYPES["beast_tide"], stages={**W.TYPES["beast_tide"]["stages"], "active": 1000})
    monkeypatch.setitem(W.TYPES, "beast_tide", long_tide)  # the samples span more than its 15 days
    begin(world, "beast_tide", region_of(world, town.id).id, starts=world.time - 6 * 4, bounty=50, hunts={}, paid=[])
    tide = kinds()
    assert len(tide) > 1.5 * len(plain) and tide.count("beast") > 0.6 * len(tide)


def test_a_beast_tide_attacks_the_towns(game, monkeypatch):
    monkeypatch.setattr(beast_tide, "ATTACK_CHANCE", 1.0)
    world, town = game.world, game.place.id
    herbs = market.price(world, town, "herbs")
    begin(world, "beast_tide", region_of(world, town).id, starts=world.time - 6 * 4, bounty=50, hunts={}, paid=[])
    sky.observe(world, town)
    dead = world._conn.execute("select count(*) from chronicle where kind = 'died' and data like '%beasts%'").fetchone()[0]
    assert dead >= 1 and market.price(world, town, "herbs") > herbs


def test_three_beast_kills_pay_the_bounty(game):
    world, me, town = game.world, game.player.id, game.place.id
    begin(world, "beast_tide", region_of(world, town).id, starts=world.time - 6 * 4, bounty=50, hunts={}, paid=[])
    silver = silver_of(world, me)
    for _ in range(3):
        commit(world, beast_tide.hunt_events(world, me, town))
    assert silver_of(world, me) == silver + 50
    assert beast_tide.hunt_events(world, me, town) == []


def test_winning_a_fight_with_a_beast_counts_as_a_hunt(game):
    world, me, town = game.world, game.player.id, game.place.id
    occurrence = begin(world, "beast_tide", region_of(world, town).id, starts=world.time - 6 * 4,
                       bounty=50, hunts={}, paid=[])
    region = region_of(world, town)
    beast = encounters.make_roamer(world, region, "beast", 0, 0.5)
    game._start_duel(beast, "duel")
    d = game.combat
    event = duel._end_event(world, d, "won", "broken", random.Random(1), d.harm, 3, verdict="kill")
    game._commit([event])
    game._finish_duel(event.data)
    assert world.entity(occurrence).data["data"]["hunts"] == {str(me): 1}
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tribulations.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.events.beast_tide'`.

- [ ] **Step 3: Write the tribulation** — `systems/events/tribulation.py`
```python
"""Tribulation lightning (phase 4d spec 4.1): heaven's answer to a great breakthrough, seen across the region.

A breakthrough to First-rate or beyond, by anyone, calls it down. The townsfolk witness it,
a `tribulation` fact names who broke through (the Pavilion's informants listen for these),
and the player must come through it: clean, scarred, or with a meridian torn (plan ruling 10).
"""

import systems.sky as sky
import systems.world_events as W
from systems.bodies import load_body, save_body
from systems.cultivation import BREAKTHROUGH_DAYS
from systems.facts import make_variant, place_name, record_fact
from systems.realms import REALMS
from world.body import REGULAR, add_injury
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

TRIBULATION_REALM = 3  # First-rate
OUTCOMES = ("clean", "scarred", "crippled")
REST_DAYS = 3
WITNESSES = 8


def player_roll(world, pid: int) -> str:
    """How the player comes through: purity and a rested body help; only the impure can be crippled."""
    body = load_body(world, pid)
    since = world.time - (BREAKTHROUGH_DAYS + REST_DAYS) * 4
    rested = any(e.kind == "rested" and e.time >= since for e in world.chronicle_about(pid, limit=30))
    clean = 0.45 + 0.3 * body.purity + (0.1 if rested else 0.0)
    crippled = 0.03 if body.purity < 0.5 else 0.0
    roll = rng_for(world.world_seed, f"tribulation:{pid}:{world.time}").random()
    return "clean" if roll < clean else "crippled" if roll >= 1 - crippled else "scarred"


def trigger_events(world, person: int, place: int, realm: int, season: int | None = None,
                   outcome: str | None = None) -> list[Event]:
    """The lightning (if it is still to be seen) and the tribulation itself."""
    recent = season is None or season >= world.time // W.SEASON
    events = sky.start_events(world, "tribulation", place, world.time if recent else season * W.SEASON,
                              {"person": person, "realm": realm})
    witnesses = tuple(Witness(p.id, "respect", 0.4) for p in people_at(world, place, exclude=person)[:WITNESSES]) \
        if recent else ()
    return events + [Event("tribulation", (person,), place, {"realm": realm, "outcome": outcome}, witnesses=witnesses)]


@effect("tribulation")
def _tribulation(world, event) -> None:
    outcome = event.data.get("outcome")
    if outcome not in ("scarred", "crippled"):
        return
    pid = event.actors[0]
    body = load_body(world, pid)
    if outcome == "scarred":
        add_injury(body, "torso", "internal", 2, world.time, "the heavenly tribulation")
    else:
        opened = [m for m in REGULAR if body.meridians[m].state == "open"]
        if opened:
            body.meridians[opened[0]].state = "damaged"
            add_injury(body, opened[0], "meridian", 3, world.time, "the heavenly tribulation")
    save_body(world, pid, body)


@listen("tribulation")
def _news(world, event, event_id: int) -> None:
    person, realm = event.actors[0], event.data["realm"]
    variant = make_variant("tribulation", person, None, place=place_name(world, event.place), realm=REALMS[realm].label)
    variant["age"] = int(world.entity(person).data.get("age", 20))
    record_fact(world, person, "tribulation", None, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


@listen("broke_through")
def _npc_tribulation(world, event, event_id: int) -> None:
    realm = event.data["realm"]
    if realm >= TRIBULATION_REALM and event.place is not None:
        commit(world, trigger_events(world, event.actors[0], event.place, realm, season=event.data.get("season")))
```

- [ ] **Step 4: Write the beast tide** — `systems/events/beast_tide.py`
```python
"""The beast tide (phase 4d spec 4.5): beasts pour out of the wilds, towns are attacked, the magistrate pays hunters.

Only regions with beasts in them rise (the 2b `BEASTS` terrains). While it is active the
roads are thick with beasts (the `beasts` knob); each town rolls an attack once; and three
beast kills in the region, before the aftermath ends, pay the bounty (plan ruling 8).
"""

import systems.lives as lives
import systems.price_events as price_events  # a module import: price_events loads the world clock, which loads this
import systems.world_events as W
from systems.encounters import BEASTS
from systems.purse import silver_of
from world.events import Event, effect
from world.gen.materialize import people_at
from world.seed import rng_for

ATTACK_CHANCE = 0.3
KILLS_FOR_BOUNTY = 3


def eligible(world, region: int, n: int) -> bool:
    return world.entity(region).data.get("terrain") in BEASTS


def start_data(world, region: int, n: int, rng) -> dict:
    return {"bounty": rng.randint(30, 80), "hunts": {}, "paid": []}


def on_stage(world, occurrence, stage: str) -> list[Event]:
    if stage != "active":
        return []
    d, events = occurrence.data, []
    for town in sorted(t for t in world.sources(d["place"], "located_in") if world.entity(t).kind == "town"):
        rng = rng_for(world.world_seed, f"beast_tide:{occurrence.id}:{town}")
        if rng.random() >= ATTACK_CHANCE:
            continue
        folk = sorted(p.id for p in people_at(world, town) if lives.simulated(p))
        for victim in rng.sample(folk, min(len(folk), rng.randint(1, 3))):
            events.append(Event("died", (victim, victim), town, {"cause": "beasts", "world": True}))
        price_events.shift(world, "town", town, {"herbs": 1.5}, d["active"][1], "beast tide")
    return events


def _tide_over(world, place: int) -> int | None:
    """The beast tide whose hunting season covers this place now, if any."""
    xy = W.place_xy(world, place)
    for row in W.index(world):
        if row[W.TYPE] == "beast_tide" and row[W.ACTIVE_FROM] <= world.time < row[W.OVER_AT] \
                and W.covers(row, place, xy):
            return row[W.ID]
    return None


def hunt_events(world, player: int, place: int) -> list[Event]:
    """A beast the player killed while a tide was up; the third one pays the bounty."""
    occurrence = _tide_over(world, place)
    if occurrence is None:
        return []
    d = world.entity(occurrence).data["data"]
    if player in d["paid"]:
        return []
    kills = d["hunts"].get(str(player), 0) + 1
    events = [Event("beast_hunted", (player,), place, {"occurrence": occurrence, "kills": kills})]
    if kills >= KILLS_FOR_BOUNTY:
        events.append(Event("bounty_paid", (player,), place, {"occurrence": occurrence, "silver": d["bounty"]}))
    return events


@effect("beast_hunted")
def _hunted(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    d = dict(occurrence.data["data"])
    d["hunts"] = {**d["hunts"], str(event.actors[0]): event.data["kills"]}
    world.update_data(occurrence.id, data=d)


@effect("bounty_paid")
def _paid(world, event) -> None:
    player, occurrence = event.actors[0], world.entity(event.data["occurrence"])
    world.update_data(player, silver=silver_of(world, player) + event.data["silver"])
    d = dict(occurrence.data["data"])
    d["paid"] = d["paid"] + [player]
    world.update_data(occurrence.id, data=d)
```

- [ ] **Step 5: Write the engine's sky** — `engine/sky.py`
```python
"""The sky in the engine (phase 4d spec 7): the player's tribulation and the beast hunt.

Tasks 4 and 6 add the treasure race, the sky and rankings pages, and what arrival shows.
"""

import systems.events.beast_tide as beast_tide
import systems.events.tribulation as tribulation
from world.events import commit


class SkyMixin:
    def _commit_sky(self, events: list) -> list:
        """Occurrences start quietly (the scene shows the sky); the rest is narrated."""
        quiet = [e for e in events if e.kind == "sky_started"]
        if quiet:
            commit(self.world, quiet)
        loud = [e for e in events if e.kind != "sky_started"]
        return self._commit(loud) if loud else []

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        for event in events:
            if event.kind == "breakthrough" and event.actors[0] == self.player.id and event.data.get("success") \
                    and event.data["realm_after"] >= tribulation.TRIBULATION_REALM:
                outcome = tribulation.player_roll(self.world, self.player.id)
                lines += self._commit_sky(tribulation.trigger_events(
                    self.world, self.player.id, self.place.id, event.data["realm_after"], outcome=outcome))
        return lines

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is None or data.get("result") != "won" or len(entry.actors) < 2:
            return lines
        foe = self.world.entity(entry.actors[1])
        if foe is not None and foe.data.get("beast"):
            events = beast_tide.hunt_events(self.world, self.player.id, self.place.id)
            lines += self._commit(events) if events else []
        return lines
```

- [ ] **Step 6: Write the grammar** — `narrate/grammar/sky.toml`
```toml
[symbols]
sky_thunder = ["Thunder rolls on long after.", "The air smells of burnt iron.", "Somewhere a dog will not stop howling.", "The clouds break slowly, as if reluctant.", "People come out of their doors to stare.", "Rain follows, warm and heavy."]
sky_hunt = ["The carcass steams in the cold air.", "Blood darkens the grass.", "Flies are already gathering.", "The villagers will sleep easier tonight.", "Its teeth are as long as your fingers."]
sky_reward = ["The magistrate's clerk counts it out twice.", "A crowd gathers to see who hunted so well.", "The silver is heavier than you expected.", "Someone buys you a drink on the strength of it."]

[tribulation]
colour = "default"
lines = ["#sky_thunder#", "#sky_thunder# #sky_thunder#"]

[beast_hunted]
colour = "default"
lines = ["#sky_hunt#", "#sky_hunt# #sky_hunt#"]

[bounty_paid]
colour = "default"
lines = ["#sky_reward#", "#sky_reward# #sky_hunt#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/4d_task3.py`
```python
"""Task 3 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("systems/lives.py", '''        events.append(Event("broke_through", (person,), place, {"realm": realm + 1}))''',
     '''        events.append(Event("broke_through", (person,), place, {"realm": realm + 1, "season": n}))''')

ENC = "systems/encounters.py"
edit(ENC, '''    if rng.random() >= danger * ENCOUNTER_CHANCE * W.factor(world, town.id, "encounter"):''',
     '''    if rng.random() >= danger * ENCOUNTER_CHANCE * W.factor(world, town.id, "encounter") * W.factor(world, town.id, "beasts"):''')
edit(ENC, '''    kinds = ["bandit", "wanderer"] + (["beast"] if region.data["terrain"] in BEASTS else [])
    kind = rng.choice(kinds)''', '''    kinds = ["bandit", "wanderer"] + (["beast"] if region.data["terrain"] in BEASTS else [])
    tide = W.factor(world, town.id, "beasts")  # a beast tide (phase 4d): most of what comes is a beast
    kind = "beast" if "beast" in kinds and tide > 1.0 and rng.random() < 1 - 1 / tide else rng.choice(kinds)''')

edit("systems/mortality.py", '''          "killed": "at the hands of {killer}", "executed": "under the executioner's blade"}''',
     '''          "killed": "at the hands of {killer}", "executed": "under the executioner's blade",
          "beasts": "to the beasts"}''')

GAME = "engine/game.py"
edit(GAME, "from engine.market import MarketMixin\n", "from engine.market import MarketMixin\nfrom engine.sky import SkyMixin\n")
edit(GAME, "class Game(LineageMixin, MarketMixin, WorldMixin,", "class Game(LineageMixin, MarketMixin, SkyMixin, WorldMixin,")

TOML = "systems/data/world_events.toml"
Path(TOML).write_text(Path(TOML).read_text(encoding="utf-8") + '''
[tribulation]
module = "systems.events.tribulation"
scope = "town"
cycle = "trigger"
stages = { active = 1 }

[beast_tide]
module = "systems.events.beast_tide"
scope = "region"
chance = 0.03
stages = { announced = 5, active = 15, aftermath = 30 }
modifiers = { beasts = 3.0 }
readings = ["the mountain spirits' anger", "a great beast waking", "a hard winter coming"]
news = { predicate = "phenomenon", weight = 1.5, stages = ["announced", "active"] }
''', encoding="utf-8", newline="\n")

SKY = "narrate/sky_text.py"
edit(SKY, '''from narrate.gossip_text import SPECIAL_PHRASES
from narrate.outcomes import cap
''', '''from narrate.gossip_text import SPECIAL_PHRASES
from narrate.outcomes import cap, outcome, summary
from systems.realms import REALMS
''')
edit(SKY, '''         "dao_resonance": "a dao resonance"}''', '''         "dao_resonance": "a dao resonance", "tribulation": "tribulation lightning", "beast_tide": "a beast tide"}''')
Path(SKY).write_text(Path(SKY).read_text(encoding="utf-8") + '''

TRIBULATION_WORDS = {
    "clean": "You stand in the lightning and come through whole; heaven has let you pass.",
    "scarred": "The lightning finds you. You come through it scarred and shaking.",
    "crippled": "The lightning tears through your meridians. You live, but something in you is broken.",
}


def _tribulation_story(world, variant, viewer) -> str:
    who = "you" if variant.get("actor") == viewer else (world.entity(variant["actor"]).name if variant.get("actor") else "someone")
    where = variant.get("place") or "the hills"
    return cap(f"heavenly lightning fell on {who} in {where}, breaking through to {variant.get('realm') or 'a higher realm'}.")


SPECIAL_PHRASES["tribulation"] = _tribulation_story


@outcome("tribulation")
def _tribulation(world, event):
    d = event.data
    return [f"Clouds gather over you as you reach {REALMS[d['realm']].name}. {TRIBULATION_WORDS.get(d.get('outcome'), '')}".strip()], {}


@summary("tribulation")
def _tribulation_line(world, entry, names, place, other):
    return f"Faced the heavenly tribulation in {place}: {entry.data.get('outcome') or 'witnessed'}."


@outcome("beast_hunted", body_facts=False)
def _hunted(world, event):
    return [f"That is {event.data['kills']} beast{'s' if event.data['kills'] != 1 else ''} for the magistrate's bounty."], {}


@summary("beast_hunted")
def _hunted_line(world, entry, names, place, other):
    return f"Killed a beast in the beast tide near {place}."


@outcome("bounty_paid", body_facts=False)
def _paid(world, event):
    return [f"The magistrate pays you {event.data['silver']} silver for the beasts."], {}


@summary("bounty_paid")
def _paid_line(world, entry, names, place, other):
    return f"Was paid {entry.data['silver']} silver for hunting beasts near {place}."
''', encoding="utf-8", newline="\n")
print("task 3 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4d_task3.py && .venv/Scripts/python.exe -m pytest tests/test_tribulations.py -q -p no:cacheprovider`
Expected: `task 3 edits applied`, then `9 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: tribulation lightning and the beast tide - great breakthroughs light the sky, beasts flood the roads and the magistrate pays hunters"`

---
### Task 4: Treasure races, and the treasures they give

**Files:**
- Create: `systems/races.py`, `systems/events/treasure_light.py`, `systems/events/star_fall.py`
- Modify (via `.patches/4d_task4.py`):
  - `engine/sky.py`: `seek`, `swallow`, `sell_treasure`, the race duels, menu entries;
  - `engine/commands.py`: `seek` and `swallow`;
  - `debug/invariants.py`: `check_races`;
  - `systems/data/world_events.toml`: treasure light, star fall;
  - `narrate/sky_text.py` and `narrate/grammar/sky.toml`: race narration.
- Test: `tests/test_races.py`

**Interfaces:**
- Consumes:
  - Task 1: `sky.start_events`, `sky.observe`, `W.index`.
  - Task 3: `SkyMixin`, `_commit_sky`.
  - 2b: `duel.ensure_npc_arts`, `best_art`, `fighter_for`, `duel_sim.simulate`, `items.create_manual`, `techniques.generate`, `create_technique`.
  - 3c: `founding.make_person`.
- Produces:
  - `systems.races`:
    - constants: `RACE_KINDS`, `RACE_RANGE = 2`, `CHAMPION_REALM = 2`, `WANDERER_CHANCE = 0.3`, `MAX_WANDERERS = 2`, `MAX_CHAMPIONS = 6`;
    - setup: `prize_for(kind, rng) -> dict`, `race_start_data(kind, rng) -> dict`, `race_stage(world, occurrence, stage) -> list[Event]`, `champions(world, occurrence) -> list[int]`;
    - contest: `contest_events(world, occurrence) -> list[Event]`, `claim_events(world, occurrence_id, winner, place) -> list[Event]`;
    - player: `race_here(world, town) -> int | None`, `races_near(world, town) -> list[tuple[int, int]]`, `next_champion(world, occurrence_id, player) -> int | None`;
    - treasures: `make_prize(world, owner, prize, occurrence_id) -> int`, `swallow_events(...)`, `sell_events(...)`.
  - Events:
    - `race_called` (`occurrence`, `champions`);
    - `race_fought` (actors: player and champion; `occurrence`, `won`);
    - `treasure_claimed` (actor: the winner; `occurrence`, `prize`);
    - `swallowed` (`item`, `qi_years`);
    - `sold_treasure` (`item`, `silver`).
  - Fact `treasure` (subject: the winner; the variant carries `prize` and `age`).
  - Entity kind `treasure` (data `kind` = pill | herb | star_iron, `value`, optional `qi_years`, `used`).
  - Race occurrence data: `{"prize", "champions", "beaten", "out", "claimed", "item"}`.
  - `debug.invariants.check_races(world) -> list[str]`.
  - Verbs `seek`, `swallow`, `sell_treasure`.

- [ ] **Step 1: Write the failing test** — `tests/test_races.py`
```python
import random

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.mortality as mortality
import systems.races as races
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_races
from engine.actions import Action
from engine.game import Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from tests.test_world_events import begin
from world.gen.materialize import ensure_town
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(races, "WANDERER_CHANCE", 1.0)
    monkeypatch.setattr(mortality, "lethal", lambda *args: None)


def texts(turn):
    return [t for t, _ in turn.lines]


def light(game, town=None, seed="t"):
    town = game.place.id if town is None else town
    occurrence = begin(game.world, "treasure_light", town, **races.race_start_data("treasure_light", rng_for(1, seed)))
    game.world.set_time(game.world.time + 6 * 4)
    sky.observe(game.world, town)
    return occurrence


def race(world, occurrence):
    return world.entity(occurrence).data["data"]


def finish(game, result):
    d = game.combat
    event = duel._end_event(game.world, d, result, "broken", random.Random(1), d.harm, 3,
                            verdict="spare" if result == "won" else None)
    game._commit([event])
    return game._finish_duel(event.data)


def test_a_treasure_light_calls_champions_who_fight_for_it(game):
    world = game.world
    occurrence = light(game)
    champions = race(world, occurrence)["champions"]
    assert len(champions) >= 2
    world.set_time(world.time + 21 * 4)
    sky.observe(world, game.place.id)
    winner = race(world, occurrence)["claimed"]
    assert winner in champions and world.targets(winner, "owns") and race(world, occurrence)["item"]
    assert world.facts(predicate="treasure", subject=winner)
    assert check_races(world) == []


def test_only_the_strongest_few_answer(game, monkeypatch):
    monkeypatch.setattr(races, "MAX_CHAMPIONS", 1)
    occurrence = light(game)
    assert len(race(game.world, occurrence)["champions"]) == 1


def test_the_contest_is_the_same_every_time(tmp_path):
    winners = []
    for n in range(2):
        g = Game.new(tmp_path / f"g{n}.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
        g.start()
        g.world.set_time(10 * W.SEASON + 8)
        occurrence = light(g)
        g.world.set_time(g.world.time + 21 * 4)
        sky.observe(g.world, g.place.id)
        winners.append(race(g.world, occurrence)["claimed"])
        g.close()
    assert winners[0] == winners[1] is not None


def test_seek_fights_each_champion_and_claims_the_prize(game):
    world, me = game.world, game.player.id
    occurrence = light(game)
    champions = race(world, occurrence)["champions"]
    for champion in reversed(champions):  # the weakest first
        turn = game.perform(Action("seek"))
        assert game.combat is not None and game.combat.opponent == champion, texts(turn)
        lines = finish(game, "won")
    assert race(world, occurrence)["claimed"] == me
    assert race(world, occurrence)["item"] in world.targets(me, "owns")
    assert any("claim" in t.lower() for t, _ in lines)


def test_a_prize_is_never_claimed_twice(game):
    world, me = game.world, game.player.id
    occurrence = light(game)
    for _ in race(world, occurrence)["champions"]:
        game.perform(Action("seek"))
        finish(game, "won")
    assert races.claim_events(world, occurrence, me, game.place.id) == []
    world.set_time(world.time + 21 * 4)
    sky.observe(world, game.place.id)
    item = race(world, occurrence)["item"]
    assert world.sources(item, "owns") == [me] and check_races(world) == []


def test_losing_puts_you_out_of_the_race(game):
    occurrence = light(game)
    game.perform(Action("seek"))
    finish(game, "lost")
    assert game.player.id in race(game.world, occurrence)["out"]
    assert any("had your chance" in t for t in texts(game.perform(Action("seek"))))


def test_seek_far_from_the_light_points_the_way(game):
    far = ensure_town(game.world, 1, 0, 0)
    light(game, town=far)
    lines = texts(game.perform(Action("seek")))
    assert any(game.world.entity(far).name in t and "1 region" in t for t in lines), lines


def test_a_pill_is_swallowed_and_a_herb_is_sold(game):
    world, me = game.world, game.player.id
    pill = races.make_prize(world, me, {"kind": "pill", "name": "a Purple Cloud Pill", "qi_years": 0.5, "value": 75}, 0)
    herb = races.make_prize(world, me, {"kind": "herb", "name": "a blood lotus", "value": 300}, 0)
    energy, silver = load_body(world, me).energy_years, silver_of(world, me)
    choices = [c.action for c in game.perform(Action("look")).all_choices]
    assert Action("swallow", pill) in choices and Action("sell_treasure", herb) in choices
    game.perform(Action("swallow", pill))
    game.perform(Action("sell_treasure", herb))
    assert load_body(world, me).energy_years > energy and silver_of(world, me) == silver + 300
    assert world.sources(pill, "owns") == [] and world.entity(pill).data["used"]
    assert world.sources(herb, "owns") == [game.place.id]
    assert check_races(world) == []


def test_the_race_rules_catch_a_prize_with_two_owners(game):
    world, me = game.world, game.player.id
    herb = races.make_prize(world, me, {"kind": "herb", "name": "a blood lotus", "value": 300}, 0)
    world.relate(game.place.id, herb, "owns")
    assert any("owners" in p for p in check_races(world))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_races.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.races'`.

- [ ] **Step 3: Write the races** — `systems/races.py`
```python
"""Treasure races (phase 4d spec 5): a treasure appears, the nearby sects send champions, and the strongest claims it.

A treasure light or a star fall names its prize when it starts, calls its champions when it
is announced (they are named, not moved: plan ruling 7), and, if no one has claimed it when
it ends, lets the champions fight it out. While it is active the player can come to the site
and fight the champions one by one (`seek`); win them all and the prize is theirs.
"""

import systems.world_events as W
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.combat_core import INTENTS
from systems.duel import best_art, ensure_npc_arts, fighter_for
from systems.duel_sim import simulate
from systems.facts import make_variant, place_name, record_fact
from systems.founding import make_person
from systems.items import create_manual
from systems.purse import silver_of
from systems.realms import add_energy, realm_index
from systems.techniques import create_technique, generate
from world.events import Event, effect, listen
from world.seed import rng_for

RACE_KINDS = ("treasure_light", "star_fall")
RACE_RANGE = 2
CHAMPION_REALM = 2  # Second-rate
WANDERER_CHANCE, MAX_WANDERERS = 0.3, 2
MAX_CHAMPIONS = 6  # the strongest few; an old world has dozens of sects in reach
PILLS = ("Heaven-and-Earth Pill", "Nine-Turn Golden Pill", "Marrow-Washing Pill", "Purple Cloud Pill")
HERBS = ("thousand-year ginseng", "blood lotus", "snow lingzhi", "dragon-bone moss")


def prize_for(kind: str, rng) -> dict:
    if kind == "star_fall":
        return {"kind": "star_iron", "name": "a lump of star iron", "value": rng.randint(400, 900)}
    what = rng.choice(("manual", "pill", "herb"))
    if what == "manual":
        return {"kind": "manual", "grade": rng.randint(2, 3), "completeness": round(rng.uniform(0.6, 1.0), 2)}
    if what == "pill":
        years = round(rng.uniform(1.0, 3.0), 2)
        return {"kind": "pill", "name": f"a {rng.choice(PILLS)}", "qi_years": years, "value": int(150 * years)}
    return {"kind": "herb", "name": f"a {rng.choice(HERBS)}", "value": rng.randint(200, 600)}


def race_start_data(kind: str, rng) -> dict:
    return {"prize": prize_for(kind, rng), "champions": [], "beaten": [], "out": [], "claimed": None, "item": None}


def race_stage(world, occurrence, stage: str) -> list[Event]:
    if stage == "announced":
        return [Event("race_called", (), occurrence.data["place"],
                      {"occurrence": occurrence.id, "champions": champions(world, occurrence)})]
    if stage == "over":
        return contest_events(world, occurrence)
    return []


def champions(world, occurrence) -> list[int]:
    """Each staffed faction within reach sends its strongest; wanderers may come too. Strongest first."""
    d = occurrence.data
    found = []
    for faction in world.entities("faction"):
        fd = faction.data
        if fd.get("type") not in F.STAFFED or fd.get("type") == "player_sect" or fd.get("dissolved") or "home" not in fd:
            continue
        if max(abs(fd["home"][0] - d["x"]), abs(fd["home"][1] - d["y"])) > RACE_RANGE:
            continue
        able = [world.entity(p) for p in F.members_of(world, faction.id)]
        able = [p for p in able if not p.data.get("is_player") and realm_index(p.data.get("realm", "mortal")) >= CHAMPION_REALM]
        if able:
            found.append(max(able, key=lambda p: (realm_index(p.data["realm"]), -p.id)).id)
    rng = rng_for(world.world_seed, f"race:{occurrence.id}:wanderers")
    for i in range(MAX_WANDERERS):
        if rng.random() < WANDERER_CHANCE:
            found.append(make_person(world, f"race:{occurrence.id}:wanderer:{i}", d["place"],
                                     occupation="wandering swordsman", age=rng.randint(25, 55),
                                     realm=rng.choice(("second-rate", "first-rate"))))
    unique = sorted(set(found), key=lambda p: (-realm_index(world.entity(p).data.get("realm", "mortal")), p))
    return unique[:MAX_CHAMPIONS]


@effect("race_called")
def _called(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "champions": event.data["champions"]})


def _wins(world, a: int, b: int, rng) -> bool:
    for person in (a, b):
        ensure_npc_arts(world, person)
    mine, theirs = best_art(world, a), best_art(world, b)
    result, _ = simulate(fighter_for(world, a, mine.technique.id if mine else None),
                         fighter_for(world, b, theirs.technique.id if theirs else None),
                         lambda r, history: r.choice(INTENTS), rng)
    return result != "npc"  # a draw leaves the holder standing


def contest_events(world, occurrence) -> list[Event]:
    """When the light fades unclaimed, the champions fight in turn; the last one standing takes it."""
    race = occurrence.data["data"]
    if race["claimed"] is not None:
        return []
    alive = [c for c in race["champions"] if not world.entity(c).data.get("dead")]
    if not alive:
        return []
    rng = rng_for(world.world_seed, f"race:{occurrence.id}:contest")
    winner = alive[0]
    for other in alive[1:]:
        if not _wins(world, winner, other, rng):
            winner = other
    return claim_events(world, occurrence.id, winner, occurrence.data["place"])


def claim_events(world, occurrence_id: int, winner: int, place: int) -> list[Event]:
    race = world.entity(occurrence_id).data["data"]
    if race["claimed"] is not None:
        return []
    return [Event("treasure_claimed", (winner,), place, {"occurrence": occurrence_id, "prize": race["prize"]})]


def make_prize(world, owner: int, prize: dict, occurrence_id: int) -> int:
    """The prize as an item owned by `owner`: a 2b manual, or a treasure (plan ruling 11)."""
    if prize["kind"] == "manual":
        name, data = generate(rng_for(world.world_seed, f"prize:{occurrence_id}"), "martial", grade=prize["grade"])
        return create_manual(world, owner, create_technique(world, name, data), prize["completeness"], claimed=1.0)
    item = world.add_entity("treasure", prize["name"], {**{k: v for k, v in prize.items() if k != "name"}, "used": False})
    world.relate(owner, item, "owns")
    return item


@effect("treasure_claimed")
def _claimed(world, event) -> None:
    winner, d = event.actors[0], event.data
    occurrence = world.entity(d["occurrence"])
    race = occurrence.data["data"]
    if race["claimed"] is not None:
        raise ValueError(f"the prize of occurrence #{occurrence.id} was already claimed")
    item = make_prize(world, winner, d["prize"], occurrence.id)
    world.update_data(occurrence.id, data={**race, "claimed": winner, "item": item})


@listen("treasure_claimed")
def _claimed_news(world, event, event_id: int) -> None:
    winner = world.entity(event.actors[0])
    variant = make_variant("treasure", winner.id, None, place=place_name(world, event.place),
                           realm=winner.data.get("realm"))
    variant.update(prize=event.data["prize"]["kind"], age=int(winner.data.get("age", 20)))
    record_fact(world, winner.id, "treasure", None, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


# --- the player at the race ---------------------------------------------------------------

def _active_races(world) -> list[list]:
    return [row for row in W.index(world)
            if row[W.TYPE] in RACE_KINDS and row[W.ACTIVE_FROM] <= world.time < row[W.ACTIVE_TO]
            and world.entity(row[W.ID]).data["data"]["claimed"] is None]


def race_here(world, town: int) -> int | None:
    return next((row[W.ID] for row in _active_races(world) if row[W.PLACE] == town), None)


def races_near(world, town: int) -> list[tuple[int, int]]:
    """(occurrence, regions away) for every unclaimed treasure light within reach of this town."""
    here = W.place_xy(world, town)
    found = []
    for row in _active_races(world):
        distance = max(abs(row[W.X] - here[0]), abs(row[W.Y] - here[1]))
        if distance <= RACE_RANGE:
            found.append((row[W.ID], distance))
    return sorted(found, key=lambda p: (p[1], p[0]))


def next_champion(world, occurrence_id: int, player: int) -> int | None:
    """The weakest champion the player has not yet beaten (they face the lowest first)."""
    race = world.entity(occurrence_id).data["data"]
    left = [c for c in race["champions"] if c not in race["beaten"] and not world.entity(c).data.get("dead")]
    return left[-1] if left else None


@effect("race_fought")
def _fought(world, event) -> None:
    player, champion = event.actors
    occurrence = world.entity(event.data["occurrence"])
    race = dict(occurrence.data["data"])
    if event.data["won"]:
        race["beaten"] = race["beaten"] + [champion]
    else:
        race["out"] = race["out"] + [player]
    world.update_data(occurrence.id, data=race)


# --- treasures ----------------------------------------------------------------------------

def swallow_events(world, player: int, place: int, item: int) -> list[Event]:
    return [Event("swallowed", (player,), place, {"item": item, "qi_years": world.entity(item).data["qi_years"]})]


@effect("swallowed")
def _swallowed(world, event) -> None:
    player, item = event.actors[0], event.data["item"]
    body = load_body(world, player)
    add_energy(body, event.data["qi_years"])
    save_body(world, player, body)
    world.unrelate(player, "owns", item)
    world.update_data(item, used=True)


def sell_events(world, player: int, town: int, item: int) -> list[Event]:
    return [Event("sold_treasure", (player,), town, {"item": item, "silver": world.entity(item).data["value"]})]


@effect("sold_treasure")
def _sold(world, event) -> None:
    player, town, item = event.actors[0], event.place, event.data["item"]
    world.update_data(player, silver=silver_of(world, player) + event.data["silver"])
    world.unrelate(player, "owns", item)
    world.relate(town, item, "owns")
```

- [ ] **Step 4: Write the two race types** — `systems/events/treasure_light.py`
```python
"""A treasure light (phase 4d spec 5): a pillar of light marks where a treasure has been born. A race."""

from systems.races import race_stage, race_start_data


def start_data(world, site: int, n: int, rng) -> dict:
    return race_start_data("treasure_light", rng)


def on_stage(world, occurrence, stage: str) -> list:
    return race_stage(world, occurrence, stage)
```

`systems/events/star_fall.py`
```python
"""A star fall (phase 4d spec 4.8): a meteor comes down and leaves star iron for whoever gets there. A race."""

from systems.races import race_stage, race_start_data


def start_data(world, site: int, n: int, rng) -> dict:
    return race_start_data("star_fall", rng)


def on_stage(world, occurrence, stage: str) -> list:
    return race_stage(world, occurrence, stage)
```

- [ ] **Step 5: Edit the existing files** — `.patches/4d_task4.py`
```python
"""Task 4 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


SKY = "engine/sky.py"
edit(SKY, '''import systems.events.beast_tide as beast_tide
import systems.events.tribulation as tribulation
from world.events import commit
''', '''import systems.events.beast_tide as beast_tide
import systems.events.tribulation as tribulation
import systems.races as races
from engine.actions import Action, Choice
from narrate.sky_text import race_line
from world.events import Event, commit
''')
edit(SKY, '''        foe = self.world.entity(entry.actors[1])
        if foe is not None and foe.data.get("beast"):''', '''        foe = self.world.entity(entry.actors[1])
        race = (data.get("purpose") or {}).get("race")
        if race is not None:
            return lines + self._race_fought(race, foe.id, True)
        if foe is not None and foe.data.get("beast"):''')
edit(SKY, '''        if entry is None or data.get("result") != "won" or len(entry.actors) < 2:
            return lines
''', '''        if entry is None or len(entry.actors) < 2:
            return lines
        if data.get("result") != "won":
            race = (data.get("purpose") or {}).get("race")
            return lines + (self._race_fought(race, entry.actors[1], False) if race is not None else [])
''')
Path(SKY).write_text(Path(SKY).read_text(encoding="utf-8") + '''
    # --- treasure races and treasures (phase 4d spec 5) ---------------------------------------
    def _race_fought(self, race: int, champion: int, won: bool) -> list:
        me, town = self.player.id, self.place.id
        lines = self._commit([Event("race_fought", (me, champion), town, {"occurrence": race, "won": won})])
        if won and races.next_champion(self.world, race, me) is None:
            lines += self._commit(races.claim_events(self.world, race, me, town))
        return lines

    def _do_seek(self, _target):
        world, me, town = self.world, self.player.id, self.place.id
        race = races.race_here(world, town)
        if race is None:
            near = races.races_near(world, town)
            if not near:
                return self._turn([("No treasure light stands anywhere you can see.", "system")])
            return self._turn([(race_line(world, occurrence, distance), "dim") for occurrence, distance in near])
        if me in world.entity(race).data["data"]["out"]:
            return self._turn([("You have had your chance at this treasure.", "system")])
        foe = races.next_champion(world, race, me)
        if foe is None:
            return self._turn(self._commit(races.claim_events(world, race, me, town)))
        return self._turn([(f"{world.entity(foe).name} stands between you and the treasure.", "dim")]
                          + self._start_duel(foe, "duel", purpose={"race": race}))

    def _treasures(self) -> list:
        found = [self.world.entity(i) for i in self.world.targets(self.player.id, "owns")]
        return [t for t in found if t is not None and t.kind == "treasure"]

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        if races.race_here(self.world, self.place.id) is not None:
            extras.append(Choice("Seek the treasure", Action("seek")))
        for item in self._treasures():
            if item.data["kind"] == "pill":
                extras.append(Choice(f"Swallow {item.name}", Action("swallow", item.id)))
            else:
                extras.append(Choice(f"Sell {item.name} ({item.data['value']} silver)", Action("sell_treasure", item.id)))
        return extras

    def _owned_treasure(self, item, kinds):
        found = [t for t in self._treasures() if t.data["kind"] in kinds and (item is None or t.id == item)]
        return found[0] if found else None

    def _do_swallow(self, item):
        pill = self._owned_treasure(item, ("pill",))
        if pill is None:
            return self._turn([("You have no pill to swallow.", "system")])
        return self._turn(self._commit(races.swallow_events(self.world, self.player.id, self.place.id, pill.id)))

    def _do_sell_treasure(self, item):
        found = self._owned_treasure(item, ("pill", "herb", "star_iron"))
        if found is None:
            return self._turn([("You have no treasure to sell.", "system")])
        return self._turn(self._commit(races.sell_events(self.world, self.player.id, self.place.id, found.id)))
''', encoding="utf-8", newline="\n")

edit("engine/commands.py", '''"market": Action("market"), "prices": Action("prices"),''',
     '''"market": Action("market"), "prices": Action("prices"),
    "seek": Action("seek"), "swallow": Action("swallow"),''')

INV = "debug/invariants.py"
edit(INV, '''    problems += check_sky(world)
''', '''    problems += check_sky(world)
    problems += check_races(world)
''')
edit(INV, '''def check_sky(world) -> list[str]:''', '''def check_races(world) -> list[str]:
    """Phase 4d spec 8, rule 5: a prize is claimed at most once, and every treasure has one owner (or was used)."""
    import systems.races as races
    import systems.world_events as W
    out = []
    for row in W.index(world):
        if row[W.TYPE] not in races.RACE_KINDS:
            continue
        race = world.entity(row[W.ID]).data["data"]
        if race.get("claimed") is not None and world.entity(race.get("item") or -1) is None:
            out.append(f"race #{row[W.ID]} was claimed but its prize is missing")
    for item in world.entities("treasure"):
        owners = world.sources(item.id, "owns")
        if len(owners) != (0 if item.data.get("used") else 1):
            out.append(f"treasure #{item.id} has {len(owners)} owners")
    return out


def check_sky(world) -> list[str]:''')

TOML = "systems/data/world_events.toml"
Path(TOML).write_text(Path(TOML).read_text(encoding="utf-8") + '''
[treasure_light]
module = "systems.events.treasure_light"
scope = "site"
chance = 0.03
stages = { announced = 5, active = 20 }
readings = ["an immortal's cave opening", "a heavenly treasure born", "a trap for the greedy"]
news = { predicate = "phenomenon", weight = 1.5, stages = ["announced"] }

[star_fall]
module = "systems.events.star_fall"
scope = "site"
chance = 0.01
stages = { announced = 3, active = 30 }
readings = ["heaven's iron for a great blade", "a star's grief", "a hero's birth"]
news = { predicate = "phenomenon", weight = 1.5, stages = ["announced"] }
''', encoding="utf-8", newline="\n")

TEXT = "narrate/sky_text.py"
edit(TEXT, '''"tribulation": "tribulation lightning", "beast_tide": "a beast tide"}''',
     '''"tribulation": "tribulation lightning", "beast_tide": "a beast tide",
         "treasure_light": "a pillar of treasure light", "star_fall": "a falling star"}''')
Path(TEXT).write_text(Path(TEXT).read_text(encoding="utf-8") + '''

PRIZE_WORDS = {"manual": "a martial manual", "pill": "a heavenly pill", "herb": "a spirit herb", "star_iron": "star iron"}


def race_line(world, occurrence: int, distance: int) -> str:
    d = world.entity(occurrence).data
    town = world.entity(d["place"]).name
    how_far = "here" if distance == 0 else f"{distance} region{'s' if distance != 1 else ''} away"
    return f"{cap(phenomenon_name(d['type']))} stands over {town}, {how_far}."


def _treasure_story(world, variant, viewer) -> str:
    who = "you" if variant.get("actor") == viewer else (world.entity(variant["actor"]).name if variant.get("actor") else "someone")
    return cap(f"{who} claimed {PRIZE_WORDS.get(variant.get('prize'), 'a treasure')} in {variant.get('place') or 'the wilds'}.")


SPECIAL_PHRASES["treasure"] = _treasure_story


@outcome("race_fought", body_facts=False)
def _fought(world, event):
    champion = world.entity(event.actors[1]).name
    if event.data["won"]:
        return [f"{champion} falls back; the way to the treasure is a step clearer."], {}
    return [f"{champion} bars the way. Your chance at the treasure is gone."], {}


@summary("race_fought")
def _fought_line(world, entry, names, place, other):
    return f"{'Beat' if entry.data['won'] else 'Lost to'} {other} in the race for a treasure near {place}."


@outcome("treasure_claimed", body_facts=False)
def _claimed(world, event):
    prize = event.data["prize"]
    what = prize.get("name") or PRIZE_WORDS.get(prize["kind"], "the treasure")
    return [f"You claim the treasure: {what}."], {}


@summary("treasure_claimed")
def _claimed_line(world, entry, names, place, other):
    prize = entry.data["prize"]
    return f"Claimed {prize.get('name') or PRIZE_WORDS.get(prize['kind'], 'a treasure')} near {place}."


@outcome("swallowed", body_facts=True)
def _swallowed(world, event):
    return [f"You swallow it. Qi floods your meridians: {event.data['qi_years']:.1f} years of it."], {}


@summary("swallowed")
def _swallowed_line(world, entry, names, place, other):
    return f"Swallowed a pill worth {entry.data['qi_years']:.1f} years of qi."


@outcome("sold_treasure", body_facts=False)
def _sold(world, event):
    return [f"You sell {world.entity(event.data['item']).name} for {event.data['silver']} silver."], {}


@summary("sold_treasure")
def _sold_line(world, entry, names, place, other):
    return f"Sold a treasure in {place} for {entry.data['silver']} silver."
''', encoding="utf-8", newline="\n")
Path("narrate/grammar/sky.toml").write_text(Path("narrate/grammar/sky.toml").read_text(encoding="utf-8") + '''
[race_fought]
colour = "default"
lines = ["#sky_race#", "#sky_race# #sky_race#"]

[treasure_claimed]
colour = "default"
lines = ["#sky_treasure#", "#sky_treasure# #sky_race#"]

[swallowed]
colour = "default"
lines = ["#sky_pill#", "#sky_pill# #sky_pill#"]

[sold_treasure]
colour = "default"
lines = ["#sky_reward#", "#sky_reward# #sky_reward#"]
''', encoding="utf-8", newline="\n")
edit("narrate/grammar/sky.toml", '''sky_reward = [''', '''sky_race = ["The light above is almost too bright to look at.", "Other seekers watch from the rocks.", "Dust and blood; the treasure waits.", "Somewhere behind you someone is praying.", "The ground here is scorched and strange."]
sky_treasure = ["It is warm to the touch.", "Heaven and earth seem to hold their breath.", "The light fades as your hand closes on it.", "Nobody else dares come closer."]
sky_pill = ["Heat spreads from your belly to your fingertips.", "Your sweat smells of herbs.", "For a moment you can hear your own heart like a drum.", "Your dantian swells and settles."]
sky_reward = [''')
print("task 4 edits applied")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4d_task4.py && .venv/Scripts/python.exe -m pytest tests/test_races.py -q -p no:cacheprovider`
Expected: `task 4 edits applied`, then `9 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 7: Commit**

Run: `git add -A && git commit -m "feat: treasure races - lights and falling stars draw champions; seek the site, beat them all and claim the prize"`

---
### Task 5: The Heavenly Ranking Pavilion

**Files:**
- Create: `systems/rankings.py`
- Modify (via `.patches/4d_task5.py`):
  - `world/db.py`: `facts_after`;
  - `systems/reputation.py`: rank title and renown;
  - `systems/world_clock.py`: imports `systems.rankings`;
  - `debug/invariants.py`: `check_rankings`;
  - `narrate/sky_text.py`: the `published` story and the journal line;
  - `systems/beliefs.py`: people named on a list you have heard of are people you know of.
- Test: `tests/test_rankings.py`

**Interfaces:**
- Consumes:
  - 3a: `beliefs.believe`, `world.known_facts`, `record_fact`.
  - 3b: `F.members_of`, `F.membership`, `F.STAFFED`.
  - Task 1: `W.place_xy`, `W.SEASON`.
  - Facts `defeated`, `died`, `killed`, `broke_through`, `tribulation` (Task 3), `treasure` (Task 4) and `enlightened` (Task 2).
- Produces:
  - `systems.rankings`:
    - constants: `LISTS`, `YOUNG`, `YOUNG_AGE`, `TITLES`, `ORDINALS`, `RANK_RENOWN`, `YEAR`;
    - the Pavilion: `capital(world) -> int`, `pavilion(world) -> int | None`, `ensure_pavilion(world) -> int`;
    - informants: `informants(world, n) -> None`, `survey(world) -> None`;
    - scoring: `scores(world, pav) -> dict[int, float]`, `believed_ages(world, pav) -> dict[int, int]`;
    - publishing: `revision_events(world, n) -> list[Event]`, `season_hook(world, n) -> list[Event]`;
    - reading the lists: `latest(world, knower) -> dict | None` (`{"year", "lists", "time"}`), `rank_of(lists, person) -> tuple[str, int] | None`, `title(name, place) -> str`, `rank_known_in(world, town, person) -> tuple[str, float] | None`, `post_in_city(world, player, town) -> bool`.
  - Event `rankings_published`:
    - actors: the Pavilion and every entrant;
    - data: `year`, `lists` (`{"heaven": [...], "earth": [...], "human": [...], "young": [...]}`), `scores` (`{str(person): score}`).
  - Facts:
    - `published`: subject the Pavilion; the variant carries `year` and `lists`;
    - `assessed`: subject a person, object their faction; unspread; the variant carries `realm` and `age`.
  - Meta keys: `pavilion`, `capital`, `pavilion_mark`, `pavilion_retry`.
  - `World.facts_after(after_id, until, predicates) -> list[Fact]`.
  - `debug.invariants.check_rankings(world) -> list[str]`.

- [ ] **Step 1: Write the failing test** — `tests/test_rankings.py`
```python
import time

import pytest

import systems.rankings as R
import systems.world_events as W
from debug.invariants import check_rankings
from engine.game import Game
from systems import founding
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from systems.reputation import reputation
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(3 * W.SEASON + 8)
    yield g
    g.close()


def deed(world, person, predicate, town, realm=None, target=None, age=None, heard=True):
    variant = make_variant(predicate, person, target, place=place_name(world, town), realm=realm)
    if age is not None:
        variant["age"] = age
    fact = record_fact(world, person, predicate, target, place=town, variant=variant, spread=False)
    if heard:
        believe(world, R.ensure_pavilion(world), fact, variant, None, 0.9, 1, "informant")
    return fact


def master(world, town, path, realm="first-rate", age=50):
    return founding.make_person(world, path, town, occupation="wandering swordsman", age=age, realm=realm)


def publish(world, n=4):
    from world.events import commit
    commit(world, R.revision_events(world, n))
    return world.entity(R.ensure_pavilion(world)).data


def test_only_the_pavilions_beliefs_count(game):
    world, town = game.world, game.place.id
    known, unheard = master(world, town, "test:known"), master(world, town, "test:unheard")
    deed(world, known, "tribulation", town, realm="first-rate")
    deed(world, unheard, "tribulation", town, realm="peak", heard=False)
    table = R.scores(world, R.ensure_pavilion(world))
    assert table[known] == 300 and unheard not in table


def test_a_hidden_master_stays_unranked(game):
    world, town = game.world, game.place.id
    hidden = master(world, town, "test:hidden", realm="profound")
    lists = publish(world)["lists"]
    assert all(hidden not in names for names in lists.values())


def test_the_dead_stay_listed_until_the_pavilion_hears(game):
    world, town = game.world, game.place.id
    old = master(world, town, "test:old", realm="peak", age=80)
    deed(world, old, "tribulation", town, realm="peak")
    assert old in publish(world)["lists"]["heaven"]
    died = deed(world, old, "died", town, heard=False)
    assert old in publish(world, 8)["lists"]["heaven"]
    believe(world, R.ensure_pavilion(world), died, world.fact(died).variant, None, 0.9, 1, "informant")
    assert old not in publish(world, 12)["lists"]["heaven"]


def test_beating_the_seventh_takes_most_of_their_score(game):
    world, town, me = game.world, game.place.id, game.player.id
    rivals = [master(world, town, f"test:rival:{i}", realm="first-rate") for i in range(8)]
    for i, rival in enumerate(rivals):
        deed(world, rival, "tribulation", town, realm="first-rate")
        for _ in range(i):
            deed(world, rival, "treasure", town)
    seventh = publish(world)["lists"]["heaven"][6]
    before = R.scores(world, R.ensure_pavilion(world))[seventh]
    deed(world, me, "defeated", town, realm="first-rate", target=seventh)
    mine = R.scores(world, R.ensure_pavilion(world))[me]
    assert mine == pytest.approx(300 + 10 + 0.6 * before)


def test_informants_hear_near_deeds_more_than_far_ones(game):
    world = game.world
    pav = R.ensure_pavilion(world)
    near, far = R.capital(world), ensure_town(world, 9, 9, 0)
    people = {place: [master(world, place, f"test:{place}:{i}") for i in range(40)] for place in (near, far)}
    for place, folk in people.items():
        for person in folk:
            deed(world, person, "broke_through", place, realm="second-rate", heard=False)
    world.set_time(world.time + W.SEASON + 1)
    R.informants(world, world.time // W.SEASON)
    heard = {f.subject for b, f in world.known_facts(pav)}
    assert len(heard & set(people[near])) > len(heard & set(people[far]))


def test_each_fact_gets_two_chances(game, monkeypatch):
    world = game.world
    monkeypatch.setattr(R, "INFORMANT_REACH", 0.0)
    person = master(world, game.place.id, "test:unlucky")
    deed(world, person, "broke_through", game.place.id, realm="second-rate", heard=False)
    world.set_time(world.time + W.SEASON + 1)
    R.informants(world, world.time // W.SEASON)
    assert len(world.get_meta("pavilion_retry")) == 1
    world.set_time(world.time + R.YEAR)
    R.informants(world, world.time // W.SEASON)
    assert world.get_meta("pavilion_retry") == []


def test_spring_publishes_the_lists_and_they_keep_the_rules(game):
    world, town = game.world, game.place.id
    for i in range(12):
        deed(world, master(world, town, f"test:m{i}", age=20 + 3 * i), "tribulation", town, realm="first-rate",
             age=20 + 3 * i)
    assert R.season_hook(world, 5) == []
    [event] = R.season_hook(world, 8)
    assert event.kind == "rankings_published" and len(event.data["lists"]["heaven"]) == 10
    from world.events import commit
    commit(world, [event])
    assert world.facts(predicate="published") and check_rankings(world) == []


def test_young_dragons_are_young_by_the_pavilions_belief(game):
    world, town = game.world, game.place.id
    youth = master(world, town, "test:youth", age=25)
    deed(world, youth, "tribulation", town, realm="first-rate", age=25)
    assert youth in publish(world)["lists"]["young"]
    world.set_time(world.time + 10 * R.YEAR)
    assert youth not in publish(world, 44)["lists"]["young"]


def test_a_city_posts_the_new_lists(game):
    world, me = game.world, game.player.id
    deed(world, master(world, game.place.id, "test:m"), "tribulation", game.place.id, realm="first-rate")
    publish(world)
    assert R.latest(world, me) is None
    assert not R.post_in_city(world, me, game.place.id) or world.entity(game.place.id).data["kind"] == "city"
    assert R.post_in_city(world, me, R.capital(world))
    assert R.latest(world, me)["year"] == 2


def test_a_ranked_name_carries_its_title_and_renown(game):
    world, town = game.world, game.place.id
    champion = master(world, town, "test:champion", realm="peak")
    deed(world, champion, "tribulation", town, realm="peak")
    before = reputation(world, town, champion).renown
    publish(world)
    fact = world.facts(predicate="published")[-1]
    believe(world, town, fact.id, fact.variant, None, 0.9, 1, "posted")
    found = reputation(world, town, champion)
    assert found.epithet.startswith("First of Heaven") and found.renown == pytest.approx(before + R.RANK_RENOWN["heaven"])


def test_a_list_you_have_heard_names_people_you_know_of(game):
    from systems.beliefs import known_people
    world, me, town = game.world, game.player.id, game.place.id
    champion = master(world, town, "test:champion", realm="peak")
    deed(world, champion, "tribulation", town, realm="peak")
    publish(world)
    assert champion not in known_people(world, me)
    fact = world.facts(predicate="published")[-1]
    believe(world, me, fact.id, fact.variant, town, 0.8, 2, "gossip")
    assert champion in known_people(world, me)


def test_an_old_save_gets_the_pavilion_and_publishes_in_spring(game):
    world = game.world
    assert R.pavilion(world) is None
    assert R.season_hook(world, 5) == [] and R.pavilion(world) is not None
    assert R.season_hook(world, 8)


def test_the_ranking_rules_catch_an_unknown_entrant(game):
    world, town = game.world, game.place.id
    deed(world, master(world, town, "test:m"), "tribulation", town, realm="first-rate")
    publish(world)
    pav = R.ensure_pavilion(world)
    stranger = master(world, town, "test:stranger")
    lists = dict(world.entity(pav).data["lists"])
    lists["heaven"] = lists["heaven"] + [stranger]
    world.update_data(pav, lists=lists, scores={**world.entity(pav).data["scores"], str(stranger): 0.0})
    assert any("no belief" in p for p in check_rankings(world))


def test_a_revision_is_quick(game):
    world, town = game.world, game.place.id
    folk = [master(world, town, f"test:q{i}") for i in range(200)]
    for i in range(2000):
        deed(world, folk[i % 200], "defeated", town, realm="second-rate", target=folk[(i + 1) % 200])
    world.known_facts(R.ensure_pavilion(world))
    start = time.process_time()
    R.revision_events(world, 4)
    assert time.process_time() - start < 0.05
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rankings.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.rankings'`.

- [ ] **Step 3: Write the Pavilion** — `systems/rankings.py`
```python
"""The Heavenly Ranking Pavilion (phase 4d spec 6): who stands where under heaven, as far as the Pavilion has heard.

The Pavilion is an `institution` and a knower (3a). Its informants hear deeds from afar,
giving each fact two chances (plan ruling 3). Each spring it surveys the public figures of
the staffed factions (ruling 4), scores everyone it believes in, and publishes four lists as
one `published` fact (ruling 2). The lists are knowledge, not truth: the hidden stay hidden,
and the dead stay listed until the Pavilion hears of the death.
"""

import systems.world_clock as world_clock
import systems.world_events as W
from systems import factions as F
from systems.beliefs import believe
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from world.events import Event, effect, listen
from world.gen.materialize import ensure_town
from world.gen.region import region_spec
from world.gen.town import town_spec
from world.seed import rng_for

LISTS = (("heaven", 10), ("earth", 20), ("human", 30))
YOUNG, YOUNG_AGE = 10, 30
TITLES = {"heaven": "of Heaven", "earth": "of Earth", "human": "of Men", "young": "among the Young Dragons"}
ORDINALS = ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
            "Eleventh", "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth",
            "Eighteenth", "Nineteenth", "Twentieth", "Twenty-first", "Twenty-second", "Twenty-third",
            "Twenty-fourth", "Twenty-fifth", "Twenty-sixth", "Twenty-seventh", "Twenty-eighth", "Twenty-ninth",
            "Thirtieth")
RANK_RENOWN = {"heaven": 12.0, "earth": 8.0, "human": 5.0, "young": 5.0}
TIER_FACTS = frozenset({"broke_through", "tribulation", "assessed", "enlightened", "treasure"})
HEARD = TIER_FACTS | {"defeated", "died", "killed"}
INFORMANT_REACH, INFORMANT_FALL = 0.9, 0.85
WIN_POINTS, WIN_SHARE, TREASURE_POINTS, ENLIGHTENED_POINTS = 10.0, 0.6, 30.0, 20.0
DEED_FADE = 0.8
PUBLIC_ROLES = ("leader", "elder")
YEAR = 4 * W.SEASON


# --- the Pavilion ------------------------------------------------------------------------------

def capital(world) -> int:
    """The city nearest the heart of the world (region 0, 0), seeded; the Pavilion stands there."""
    found = world.get_meta("capital")
    if found is not None:
        return found
    town = None
    for radius in range(4):
        ring = [(x, y) for x in range(-radius, radius + 1) for y in range(-radius, radius + 1)
                if max(abs(x), abs(y)) == radius]
        for x, y in ring:
            for i in range(region_spec(world.world_seed, x, y).town_count):
                if town is None and town_spec(world.world_seed, x, y, i).kind == "city":
                    town = ensure_town(world, x, y, i)
        if town is not None:
            break
    town = town if town is not None else ensure_town(world, 0, 0, 0)
    world.set_meta("capital", town)
    return town


def pavilion(world) -> int | None:
    return world.get_meta("pavilion")


def ensure_pavilion(world) -> int:
    found = pavilion(world)
    if found is not None:
        return found
    town = capital(world)
    found = world.add_entity("institution", "the Heavenly Ranking Pavilion",
                             {"kind": "rankings", "town": town, "lists": None, "year": None, "scores": {},
                              "fact": None}, "institution:pavilion")
    world.set_meta("pavilion", found)
    return found


# --- what reaches the Pavilion ------------------------------------------------------------------

def _hears(world, fact, home, attempt: int) -> bool:
    origin = W.place_xy(world, fact.place) if fact.place is not None else None
    distance = 0 if origin is None or home is None else max(abs(origin[0] - home[0]), abs(origin[1] - home[1]))
    return rng_for(world.world_seed, f"pavilion:{fact.id}:{attempt}").random() < INFORMANT_REACH * INFORMANT_FALL ** distance


def informants(world, n: int) -> None:
    """Deeds at least a season old reach the Pavilion, less often from far away; each gets two chances."""
    pav = ensure_pavilion(world)
    home = W.place_xy(world, world.entity(pav).data["town"])
    mark = world.get_meta("pavilion_mark", 0)
    retry = world.get_meta("pavilion_retry", [])
    fresh = world.facts_after(mark, world.time - W.SEASON, HEARD)
    keep = [[f, due] for f, due in retry if due > world.time]
    for fact in fresh:
        if _hears(world, fact, home, 0):
            believe(world, pav, fact.id, fact.variant, None, 0.9, 1, "informant")
        else:
            keep.append([fact.id, world.time + YEAR])
    for fact_id, due in retry:
        fact = world.fact(fact_id) if due <= world.time else None
        if fact is not None and _hears(world, fact, home, 1):
            believe(world, pav, fact.id, fact.variant, None, 0.8, 2, "informant")
    world.set_meta("pavilion_mark", max([mark] + [f.id for f in fresh]))
    world.set_meta("pavilion_retry", keep)


def survey(world) -> None:
    """Each spring the Pavilion takes the measure of every sect's leaders and elders (plan ruling 4)."""
    pav = ensure_pavilion(world)
    known = {(b.variant.get("actor"), b.variant.get("realm")) for b, f in world.known_facts(pav) if f.predicate == "assessed"}
    for faction in world.entities("faction"):
        fd = faction.data
        if fd.get("type") not in F.STAFFED or fd.get("type") == "player_sect" or fd.get("dissolved"):
            continue
        for person in F.members_of(world, faction.id):
            found = F.membership(world, person, faction.id)
            entity = world.entity(person)
            realm = entity.data.get("realm", "mortal")
            if not found or found[1].get("role") not in PUBLIC_ROLES or (person, realm) in known \
                    or entity.data.get("is_player"):
                continue
            variant = make_variant("assessed", person, faction.id, place=place_name(world, fd.get("seat")), realm=realm)
            variant["age"] = int(entity.data.get("age", 30))
            fact = record_fact(world, person, "assessed", faction.id, place=fd.get("seat"), weight=1.0,
                               variant=variant, spread=False)
            believe(world, pav, fact, variant, None, 1.0, 0, "survey")


# --- scoring --------------------------------------------------------------------------------------

def scores(world, pav: int) -> dict[int, float]:
    """Everyone the Pavilion believes in, scored: realm tier x 100, plus deeds that fade year by year."""
    last = world.entity(pav).data.get("scores") or {}
    tier, deeds, dead = {}, {}, set()
    for belief, fact in world.known_facts(pav):
        v, predicate = belief.variant, fact.predicate
        if predicate == "died":
            dead.add(fact.subject)
            continue
        if predicate == "killed":
            if v.get("target") is not None:
                dead.add(v["target"])
            continue
        who = v.get("actor")
        if who is None:
            continue
        realm = realm_index(v["realm"]) if v.get("realm") else None
        if realm is not None and (predicate in TIER_FACTS or predicate == "defeated"):
            tier[who] = max(tier.get(who, 0), realm)
        fade = DEED_FADE ** max(0, (world.time - fact.time) // YEAR)
        if predicate == "defeated":
            points = WIN_POINTS + WIN_SHARE * last.get(str(v.get("target")), 0.0)
        else:
            points = {"treasure": TREASURE_POINTS, "enlightened": ENLIGHTENED_POINTS}.get(predicate, 0.0)
        if points:
            deeds[who] = deeds.get(who, 0.0) + points * fade
    out = {}
    for who in set(tier) | set(deeds):
        entity = world.entity(who)
        if who in dead or entity is None or entity.kind not in ("person", "persona"):
            continue
        out[who] = round(tier.get(who, 0) * 100 + deeds.get(who, 0.0), 2)
    return out


def believed_ages(world, pav: int) -> dict[int, int]:
    """How old the Pavilion thinks people are: the newest age it was told, plus the years since."""
    newest: dict = {}
    for belief, fact in world.known_facts(pav):
        who, age = belief.variant.get("actor"), belief.variant.get("age")
        if who is not None and age is not None and (who not in newest or fact.time > newest[who][1]):
            newest[who] = (age, fact.time)
    return {who: int(age + (world.time - t) // YEAR) for who, (age, t) in newest.items()}


# --- publishing ------------------------------------------------------------------------------------

def revision_events(world, n: int) -> list[Event]:
    pav = ensure_pavilion(world)
    table = scores(world, pav)
    order = sorted(table, key=lambda p: (-table[p], p))
    lists, start = {}, 0
    for name, size in LISTS:
        lists[name] = order[start:start + size]
        start += size
    ages = believed_ages(world, pav)
    lists["young"] = [p for p in order if ages.get(p, YOUNG_AGE + 1) <= YOUNG_AGE][:YOUNG]
    entrants = sorted({p for names in lists.values() for p in names})
    return [Event("rankings_published", (pav, *entrants), world.entity(pav).data["town"],
                  {"year": n // 4 + 1, "lists": lists, "scores": {str(p): table[p] for p in table}})]


@effect("rankings_published")
def _published(world, event) -> None:
    d = event.data
    world.update_data(event.actors[0], lists=d["lists"], year=d["year"], scores=d["scores"])


@listen("rankings_published")
def _published_news(world, event, event_id: int) -> None:
    pav, d = event.actors[0], event.data
    variant = make_variant("published", pav, None, place=place_name(world, event.place))
    variant.update(year=d["year"], lists=d["lists"])
    fact = record_fact(world, pav, "published", None, place=event.place, source_event=event_id, weight=3.0,
                       variant=variant)
    world.update_data(pav, fact=fact)


def season_hook(world, n: int) -> list[Event]:
    """Every season the informants report; every spring the lists are revised."""
    ensure_pavilion(world)
    informants(world, n)
    if n % 4:
        return []
    survey(world)
    return revision_events(world, n)


world_clock.SEASON_HOOKS.append(season_hook)


# --- reading the lists ----------------------------------------------------------------------------

def latest(world, knower: int) -> dict | None:
    """The newest lists this knower has heard of: {"year", "lists", "time"}."""
    best = None
    for belief, fact in world.known_facts(knower):
        if fact.predicate == "published" and (best is None or belief.variant.get("year", 0) > best["year"]):
            best = {"year": belief.variant.get("year", 0), "lists": belief.variant.get("lists", {}), "time": fact.time}
    return best


def rank_of(lists: dict, person: int) -> tuple[str, int] | None:
    for name in ("heaven", "earth", "human", "young"):
        names = lists.get(name, [])
        if person in names:
            return name, names.index(person) + 1
    return None


def title(name: str, place: int) -> str:
    return f"{ORDINALS[place - 1]} {TITLES[name]}"


def rank_known_in(world, town: int, person: int) -> tuple[str, float] | None:
    """(title, renown) if this town has heard lists that name this person."""
    known = latest(world, town)
    found = rank_of(known["lists"], person) if known else None
    return (title(*found), RANK_RENOWN[found[0]]) if found else None


def post_in_city(world, player: int, town: int) -> bool:
    """Cities post the Pavilion's newest lists; arriving in one teaches them (spec §6.5)."""
    pav = pavilion(world)
    fact_id = world.entity(pav).data.get("fact") if pav is not None else None
    if fact_id is None or world.entity(town).data.get("kind") != "city":
        return False
    fact = world.fact(fact_id)
    believe(world, town, fact.id, fact.variant, None, 1.0, 1, "posted")
    return believe(world, player, fact.id, fact.variant, town, 1.0, 1, "posted")
```

- [ ] **Step 4: Edit the existing files** — `.patches/4d_task5.py`
```python
"""Task 5 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("world/db.py", '''    def facts_unknown_to(self, knower: int, until: int) -> list[Fact]:''',
     '''    def facts_after(self, after_id: int, until: int, predicates) -> list[Fact]:
        """Facts newer than `after_id`, no later than `until`, of these predicates (phase 4d: the Pavilion's informants)."""
        predicates = sorted(predicates)
        rows = self._conn.execute(
            f"select {_FACT_COLUMNS} from facts f where f.id > ? and f.time <= ? "
            f"and f.predicate in ({','.join('?' * len(predicates))}) order by f.id", (after_id, until, *predicates))
        return [_fact(row) for row in rows]

    def facts_unknown_to(self, knower: int, until: int) -> list[Fact]:''')

REP = "systems/reputation.py"
edit(REP, '''def reputation(world, town_id: int, subject_id: int) -> Reputation:
    """What a town makes of someone, including half of the name they inherited (phase 4b spec 6)."""''',
     '''def _reputation(world, town_id: int, subject_id: int) -> Reputation:
    """What a town makes of someone, including half of the name they inherited (phase 4b spec 6)."""''')
edit(REP, '''    return Reputation(renown, renown_word(renown), own.path if own.renown else "hard to read", own.epithet or shadow)
''', '''    return Reputation(renown, renown_word(renown), own.path if own.renown else "hard to read", own.epithet or shadow)


def reputation(world, town_id: int, subject_id: int) -> Reputation:
    """What a town makes of someone: deeds, an inherited name, and a place on the Pavilion's lists (phase 4d)."""
    found = _reputation(world, town_id, subject_id)
    from systems.rankings import rank_known_in
    ranked = rank_known_in(world, town_id, subject_id)
    if ranked is None:
        return found
    title, bonus = ranked
    renown = round(found.renown + bonus, 3)
    return Reputation(renown, renown_word(renown), found.path, f"{title}, the {found.epithet}" if found.epithet else title)
''')

CLOCK = "systems/world_clock.py"
edit(CLOCK, '''import systems.sky  # noqa: E402,F401  phase 4d: the sky's season hooks
''', '''import systems.sky  # noqa: E402,F401  phase 4d: the sky's season hooks
import systems.rankings  # noqa: E402,F401  phase 4d: the Pavilion's informants and yearly lists
''')

INV = "debug/invariants.py"
edit(INV, '''    problems += check_races(world)
''', '''    problems += check_races(world)
    problems += check_rankings(world)
''')
edit(INV, '''def check_races(world) -> list[str]:''', '''def check_rankings(world) -> list[str]:
    """Phase 4d spec 8, rule 4: the lists name only people the Pavilion believes in, in order, once each."""
    import systems.rankings as R
    pav = R.pavilion(world)
    d = world.entity(pav).data if pav is not None else {}
    if not d.get("lists"):
        return []
    key = (str(world.path), d["year"], len(d["lists"].get("heaven", [])), sum(map(len, d["lists"].values())))
    if getattr(world, "_rankings_checked", None) == key:
        return []
    out, seen = [], set()
    believed = {b.variant.get("actor") for b, f in world.known_facts(pav)}
    for name, size in R.LISTS:
        names = d["lists"].get(name, [])
        values = [d["scores"].get(str(p), 0.0) for p in names]
        if len(names) > size or len(set(names)) != len(names) or values != sorted(values, reverse=True):
            out.append(f"the {name} list is out of order, too long or repeats someone")
        if seen & set(names):
            out.append(f"the {name} list shares a name with a higher list")
        seen |= set(names)
    for person in seen | set(d["lists"].get("young", [])):
        if person not in believed:
            out.append(f"#{person} is ranked but the Pavilion holds no belief about them")
    ages = R.believed_ages(world, pav)
    for person in d["lists"].get("young", []):
        if ages.get(person, R.YOUNG_AGE + 1) > R.YOUNG_AGE:
            out.append(f"#{person} is a Young Dragon but the Pavilion believes them older than {R.YOUNG_AGE}")
    if not out:
        world._rankings_checked = key
    return out


def check_races(world) -> list[str]:''')

TEXT = "narrate/sky_text.py"
Path(TEXT).write_text(Path(TEXT).read_text(encoding="utf-8") + '''


def _published_story(world, variant, viewer) -> str:
    from systems.rankings import title
    heaven = variant.get("lists", {}).get("heaven", [])
    if not heaven:
        return "The Heavenly Ranking Pavilion has published its lists; not one name on them is worth a rumour."
    first = "you" if heaven[0] == viewer else world.entity(heaven[0]).name
    return f"The Heavenly Ranking Pavilion has published its lists for year {variant.get('year')}: {title('heaven', 1)} is {first}."


SPECIAL_PHRASES["published"] = _published_story


@summary("rankings_published")
def _published_line(world, entry, names, place, other):
    from systems.rankings import rank_of, title
    me = world.get_meta("player_id")
    found = rank_of(entry.data["lists"], me)
    return f"The Pavilion named you {title(*found)}." if found else "The Pavilion published its lists."
''', encoding="utf-8", newline="\n")
edit("systems/beliefs.py", '''            if someone is not None and someone != player_id and someone not in seen:
                seen.append(someone)
''', '''            if someone is not None and someone != player_id and someone not in seen:
                seen.append(someone)
        for names in (belief.variant.get("lists") or {}).values():  # a list you have read names people (phase 4d)
            seen += [p for p in names if p != player_id and p not in seen]
''')

print("task 5 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4d_task5.py && .venv/Scripts/python.exe -m pytest tests/test_rankings.py -q -p no:cacheprovider`
Expected: `task 5 edits applied`, then `14 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: the Heavenly Ranking Pavilion - informants, a yearly survey, four lists from what it believes, and rank titles in every town that has heard"`

---
### Task 6: The sky and the lists on screen

**Files:**
- Create: `engine/rankings_page.py`
- Modify (via `.patches/4d_task6.py`):
  - `engine/sky.py`: observing on each scene; city posting; stage lines on arrival and look; the `sky` and `rankings` pages; menu entries; `sheet_sky_lines`;
  - `narrate/sky_text.py`: `sky_facts`, `stage_line`;
  - `narrate/brief.py`: the sky in the scene brief;
  - `engine/sheet.py`: the heavens and your rank;
  - `engine/lineage_page.py`: each ancestor's best rank;
  - `systems/rankings.py`: `best_rank`;
  - `engine/commands.py`: `sky` and `rankings`;
  - `engine/game.py`: help;
  - `app.py`: F10;
  - `engine/game.py` (again): a main menu that still overflows folds its tail under "More..." (ruling 15).
- Test: `tests/test_sky_engine.py`

**Interfaces:**
- Consumes:
  - Task 1: `W.showing`, `W.stage_at`, `W.TYPES`, `sky.observe`, `sky.reading`.
  - Task 5: `R.latest`, `R.rank_of`, `R.title`, `R.post_in_city`.
  - `narrate.sky_text.NAMES`, `STAGE_WORDS`, `phenomenon_name`.
- Produces:
  - `narrate.sky_text`: `sky_facts(world, place) -> list[str]`, `stage_line(world, data, stage, town) -> str`.
  - `engine.sky`: `sheet_sky_lines(world, player) -> list`; `SkyMixin._before_scene`, `_sky_news`, `_do_sky`, `_do_rankings`.
  - `engine.rankings_page.rankings_lines(world, player) -> list[Line]`.
  - `systems.rankings.best_rank(world, person) -> str | None`.
  - Player data `sky_seen` (`{str(occurrence): stage}`).
  - Verbs `sky`, `rankings`; the F10 key.

- [ ] **Step 1: Write the failing test** — `tests/test_sky_engine.py`
```python
import time

import pytest

import systems.encounters as encounters
import systems.rankings as R
import systems.world_events as W
from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from engine.rankings_page import rankings_lines
from engine.sheet import sheet_lines
from systems import founding
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from tests.test_rankings import deed, master, publish
from tests.test_world_events import begin
from world.events import commit
from world.gen.materialize import ensure_town, region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.perform(Action("look"))
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def texts(turn):
    return [t for t, _ in turn.lines]


def moon(game):
    return begin(game.world, "blood_moon", None, starts=game.world.time - 6 * 4)


def test_the_scene_brief_carries_the_sky(game):
    moon(game)
    game.world.set_time(game.world.time + 1)  # a look at the same moment is "nothing has changed"
    game.perform(Action("look"))
    facts = " ".join(b for brief in game.last_briefs if brief.kind == "scene" for b in brief.facts)
    assert "blood moon" in facts and "days left" in facts


def test_a_new_stage_is_told_once(game):
    moon(game)
    first = texts(game.perform(Action("look")))
    assert any("blood moon" in t.lower() for t in first)
    again = texts(game.perform(Action("look")))
    assert not any("blood moon" in t.lower() for t in again)


def test_the_sky_page_shows_what_is_overhead_and_what_you_heard(game):
    world, me = game.world, game.player.id
    moon(game)
    far = ensure_town(world, 3, 3, 0)
    occurrence = begin(world, "qi_tide", region_of(world, far).id, starts=world.time - 11 * 4)
    variant = make_variant("phenomenon", far, None, place=place_name(world, far))
    variant.update(kind="qi_tide", stage="active", reading=None)
    fact = record_fact(world, far, "phenomenon", None, place=far, variant=variant, spread=False,
                       extra={"occurrence": occurrence, "until": world.time + 40 * 4})
    believe(world, me, fact, variant, None, 0.7, 2, "gossip")
    lines = texts(game.perform(Action("sky")))
    assert any("blood moon" in t for t in lines) and any("qi tide" in t and "days left" in t for t in lines)


def test_the_rankings_page_and_f10(game, tmp_path):
    world, me, town = game.world, game.player.id, game.place.id
    deed(world, me, "tribulation", town, realm="peak", age=20)
    publish(world)
    fact = world.facts(predicate="published")[-1]
    believe(world, me, fact.id, fact.variant, None, 1.0, 1, "posted")
    lines = texts(game.perform(Action("rankings")))
    assert any("You are First of Heaven" in t for t in lines) and any(t.startswith("Heaven") for t in lines)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Watcher", world_seed=5)
    app.handle_key("f10", "")
    assert any("Pavilion" in t for t, _ in app.last_turn.lines)


def test_the_rankings_page_marks_the_dead_you_have_heard_of(game):
    world, me, town = game.world, game.player.id, game.place.id
    old = master(world, town, "test:old", realm="peak", age=80)
    deed(world, old, "tribulation", town, realm="peak")
    publish(world)
    for fact in (world.facts(predicate="published")[-1], world.fact(deed(world, old, "died", town, heard=False))):
        believe(world, me, fact.id, fact.variant, None, 1.0, 1, "gossip")
    assert any(world.entity(old).name in t and "dead" in t for t, _ in rankings_lines(world, me))


def test_a_city_posts_the_lists_when_you_arrive(game):
    world, me = game.world, game.player.id
    deed(world, master(world, game.place.id, "test:m"), "tribulation", game.place.id, realm="first-rate")
    publish(world)
    city = R.capital(world)
    world.unrelate(me, "located_in")
    world.relate(me, city, "located_in")
    game.perform(Action("look"))
    assert R.latest(world, me) is not None


def test_the_sheet_shows_the_heavens_and_your_rank(game):
    world, me, town = game.world, game.player.id, game.place.id
    begin(world, "qi_tide", region_of(world, town).id, starts=world.time - 11 * 4)
    text = " ".join(t for t, _ in sheet_lines(world, me))
    assert "Qi tide: breakthrough x1.2, cultivation x1.5" in text and "Rank: unranked" in text


def test_an_ancestors_rank_is_remembered_on_the_lineage_page(game):
    from engine.lineage_page import lineage_lines
    world, me, town = game.world, game.player.id, game.place.id
    grandmother = master(world, town, "test:grandmother", realm="peak", age=90)
    deed(world, grandmother, "tribulation", town, realm="peak")
    publish(world)
    world.update_data(grandmother, dead=True, death={"cause": "age", "age": 90, "place": town})
    world.update_data(me, ancestors=[grandmother])
    assert any("once First of Heaven" in t for t, _ in lineage_lines(world, me))


def test_a_crowded_menu_folds_its_tail_under_more(game, monkeypatch):
    from engine.actions import Choice
    extras = [Choice(f"Extra {i}", Action("look")) for i in range(10)]
    monkeypatch.setattr(type(game), "_general_extras", lambda self: extras)
    turn = game.perform(Action("look"))
    assert len(turn.choices) <= 9 and turn.choices[-1].label == "More..."
    more = game.perform(Action("more_menu"))
    assert any(c.label == "Extra 9" for c in more.choices) and more.choices[-1].label == "Back"


def test_the_rankings_page_is_quick(game):
    world, me, town = game.world, game.player.id, game.place.id
    for i in range(80):
        deed(world, master(world, town, f"test:q{i}"), "tribulation", town, realm="first-rate", age=20 + i % 30)
    publish(world)
    fact = world.facts(predicate="published")[-1]
    believe(world, me, fact.id, fact.variant, None, 1.0, 1, "posted")
    rankings_lines(world, me)
    start = time.process_time()
    rankings_lines(world, me)
    assert time.process_time() - start < 0.03
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sky_engine.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'engine.rankings_page'`.

- [ ] **Step 3: Write the rankings page** — `engine/rankings_page.py`
```python
"""The rankings page (F10, phase 4d spec 7.2): the Pavilion's lists, as far as you have seen them."""

from narrate.base import Line
from systems import rankings as R

LABELS = (("heaven", "Heaven"), ("earth", "Earth"), ("human", "Men"), ("young", "Young Dragons"))


def _dead_you_know_of(world, player: int) -> set[int]:
    dead = set()
    for belief, fact in world.known_facts(player):
        if fact.predicate == "died":
            dead.add(fact.subject)
        elif fact.predicate == "killed" and belief.variant.get("target") is not None:
            dead.add(belief.variant["target"])
    return dead


def rankings_lines(world, player: int) -> list[Line]:
    lines: list[Line] = [("The Heavenly Ranking Pavilion", "heading")]
    known = R.latest(world, player)
    if known is None:
        return lines + [("  You have not seen the Pavilion's lists. Every city posts them each spring.", "dim")]
    lines.append((f"  Your copy: the lists of year {known['year']}, {max(0, (world.time - known['time']) // 4)} days old.", "dim"))
    mine = R.rank_of(known["lists"], player)
    if mine:
        lines.append((f"  You are {R.title(*mine)}.", "dim"))
    dead = _dead_you_know_of(world, player)
    for name, label in LABELS:
        names = known["lists"].get(name, [])
        if not names:
            continue
        lines.append((f"{label}:", "heading"))
        for place, person in enumerate(names, 1):
            who = "you" if person == player else world.entity(person).name
            lines.append((f"  {place:>2}. {who}{' (dead, you have heard)' if person in dead else ''}", "dim"))
    return lines
```

- [ ] **Step 4: Edit the existing files** — `.patches/4d_task6.py`
```python
"""Task 6 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    Path(path).write_text(Path(path).read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


TEXT = "narrate/sky_text.py"
append(TEXT, '''


def _days_left(data: dict, stage: str, now: int) -> int:
    return max(1, (data["ends"].get(stage, data["over_at"]) - now + 3) // 4)


def stage_line(world, data: dict, stage: str, town: int) -> str:
    """What someone standing in `town` sees of an occurrence at this stage."""
    from systems.sky import reading
    text = f"{cap(phenomenon_name(data['type']))} {STAGE_WORDS.get(stage, 'is over')} {world.entity(town).name}."
    read = reading(world, data["type"], town)
    return text + (f" People here say it means {read}." if read and stage != "aftermath" else "")


def sky_facts(world, place: int) -> list[str]:
    """The sky over this place, for a Brief: what, which stage, how long, and what the town makes of it."""
    import systems.world_events as W
    from systems.sky import reading
    out = []
    for row in W.showing(world, place):
        data = world.entity(row[W.ID]).data
        stage = W.stage_at(data, world.time)
        if stage not in STAGE_WORDS:
            continue
        text = (f"The sky: {phenomenon_name(data['type'])} {STAGE_WORDS[stage]} {world.entity(place).name} "
                f"({_days_left(data, stage, world.time)} days left)")
        read = reading(world, data["type"], place)
        out.append(text + (f"; people here read it as {read}." if read else "."))
    return out
''')

edit("narrate/brief.py", '''    ancestors = player.data.get("ancestors") or []
    if ancestors:
        facts.append(f"You are the heir of {world.entity(ancestors[-1]).name}.")''', '''    from narrate.sky_text import sky_facts  # the sky over this place (phase 4d)
    facts += sky_facts(world, place_id)
    ancestors = player.data.get("ancestors") or []
    if ancestors:
        facts.append(f"You are the heir of {world.entity(ancestors[-1]).name}.")''')

SKY = "engine/sky.py"
edit(SKY, '''import systems.races as races
''', '''import systems.races as races
import systems.rankings as rankings
import systems.sky as sky
import systems.world_events as W
from engine.rankings_page import rankings_lines
from narrate import sky_text
from narrate.gossip_text import rumour_text
from narrate.outcomes import cap
''')
edit(SKY, '''    def _general_extras(self) -> list:
        extras = super()._general_extras()
''', '''    def _general_extras(self) -> list:
        extras = super()._general_extras()
        if W.showing(self.world, self.place.id):
            extras.append(Choice("Look at the sky", Action("sky")))
        if rankings.latest(self.world, self.player.id) is not None:
            extras.append(Choice("The Pavilion's lists", Action("rankings")))
''')
append(SKY, '''
    # --- what the player sees of the sky, and the lists (phase 4d spec 7) ----------------------
    def _before_scene(self) -> None:
        super()._before_scene()
        sky.observe(self.world, self.place.id)
        rankings.post_in_city(self.world, self.player.id, self.place.id)

    def _sky_news(self) -> list:
        """A line for each occurrence over this place whose stage the player has not yet seen."""
        world, me, town = self.world, self.player.id, self.place.id
        before = dict(self.player.data.get("sky_seen", {}))
        seen, lines = dict(before), []
        for row in W.showing(world, town):
            data = world.entity(row[W.ID]).data
            stage = W.stage_at(data, world.time)
            if stage in sky_text.STAGE_WORDS and seen.get(str(row[W.ID])) != stage:
                seen[str(row[W.ID])] = stage
                lines.append((sky_text.stage_line(world, data, stage, town), "dim"))
        live = {str(row[W.ID]) for row in W.index(world) if not row[W.DONE]}
        seen = {k: v for k, v in seen.items() if k in live}
        if seen != before:
            world.update_data(me, sky_seen=seen)
        return lines

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._sky_news()

    def _after_look(self) -> list:
        return super()._after_look() + self._sky_news()

    def _do_sky(self, _target):
        world, me, town = self.world, self.player.id, self.place.id
        overhead = sky_text.sky_facts(world, town)
        lines = [("The sky", "heading")]
        lines += [(f"  {t}", "dim") for t in overhead] or [("  Clear. Nothing strange hangs over this place.", "dim")]
        here = {row[W.ID] for row in W.showing(world, town)}
        newest: dict = {}
        for belief, fact in world.known_facts(me):
            occurrence = fact.data.get("occurrence")
            if fact.predicate == "phenomenon" and occurrence not in here and fact.data.get("until", 0) > world.time \\
                    and (occurrence not in newest or fact.time >= newest[occurrence][1].time):
                newest[occurrence] = (belief, fact)
        if newest:
            lines.append(("Heard of elsewhere:", "heading"))
            for belief, fact in newest.values():
                days = max(1, (fact.data["until"] - world.time + 3) // 4)
                lines.append((f"  {rumour_text(world, belief.variant, me)} ({days} days left)", "dim"))
        return self._turn(lines)

    def _do_rankings(self, _target):
        return self._turn(rankings_lines(self.world, self.player.id))


def sheet_sky_lines(world, player: int) -> list:
    """The character sheet's heavens: what the sky does to you here, and your place on the lists."""
    here = world.targets(player, "located_in")
    lines = [("", "default"), ("The heavens:", "heading")]
    for row in (W.showing(world, here[0]) if here else []):
        mods = W.TYPES.get(row[W.TYPE], W.DEFAULTS)["modifiers"]
        if mods and W.stage_at(world.entity(row[W.ID]).data, world.time) == "active":
            words = ", ".join(f"{k} x{v:g}" for k, v in sorted(mods.items()))
            lines.append((f"  {cap(sky_text.phenomenon_name(row[W.TYPE]).removeprefix('a '))}: {words}", "default"))
    if len(lines) == 2:
        lines.append(("  quiet", "dim"))
    known = rankings.latest(world, player)
    mine = rankings.rank_of(known["lists"], player) if known else None
    lines.append((f"Rank: {rankings.title(*mine)} (the lists of year {known['year']})" if mine else "Rank: unranked",
                  "default"))
    return lines
''')

edit("engine/sheet.py", '''                lines.append((_standing(world, town, persona.id, f"As {persona.name}"), "default"))
    return lines
''', '''                lines.append((_standing(world, town, persona.id, f"As {persona.name}"), "default"))
    from engine.sky import sheet_sky_lines  # phase 4d
    lines += sheet_sky_lines(world, player_id)
    return lines
''')

append("systems/rankings.py", '''

def best_rank(world, person: int) -> str | None:
    """The highest place this person ever held on the Pavilion's lists, as a title (the lineage page's pride)."""
    order = ("heaven", "earth", "human", "young")
    best = None
    for entry in world.chronicle_about(person, limit=400):
        found = rank_of(entry.data["lists"], person) if entry.kind == "rankings_published" else None
        if found and (best is None or (order.index(found[0]), found[1]) < (order.index(best[0]), best[1])):
            best = found
    return title(*best) if best else None
''')

edit("engine/lineage_page.py", '''    return f"  {p.name}, died {how} in {where}, aged {int(death.get('age') or p.data.get('age', 0))}"''',
     '''    from systems.rankings import best_rank  # phase 4d: a family's pride
    rank = best_rank(world, person)
    return f"  {p.name}, died {how} in {where}, aged {int(death.get('age') or p.data.get('age', 0))}" \\
        + (f", once {rank}" if rank else "")''')

edit("engine/commands.py", '''    "seek": Action("seek"), "swallow": Action("swallow"),''',
     '''    "seek": Action("seek"), "swallow": Action("swallow"), "sky": Action("sky"),
    "rankings": Action("rankings"), "lists": Action("rankings"),''')
edit("engine/game.py", '''lineage (F8) | market | prices", "system"),''',
     '''lineage (F8) | market | prices", "system"),
    ("  sky | rankings (F10) | seek | swallow", "system"),''')
GAME = "engine/game.py"
edit(GAME, '''    "use_menu", "learn_menu", "browse", "create_menu",
})''', '''    "use_menu", "learn_menu", "browse", "create_menu", "more_menu",
})''')
edit(GAME, '''    def _do_back(self, _target) -> Turn:''', '''    def _do_more_menu(self, _target) -> Turn:
        self.submenu = "more_menu"
        return self._turn([("What else?", "system")])

    def _do_back(self, _target) -> Turn:''')
edit(GAME, '''        if self.submenu in submenus:
            options, back = submenus[self.submenu]
            shown = options[: MAX_SHOWN - 1] + [Choice("Back", back)]
        else:
            shown = self._main_menu(people, routes, general)''', '''        main = self._main_menu(people, routes, general)
        submenus["more_menu"] = (self._more, Action("back"))
        if self.submenu in submenus:
            options, back = submenus[self.submenu]
            shown = options[: MAX_SHOWN - 1] + [Choice("Back", back)]
        else:
            shown = main''')
edit(GAME, '''            if len(menu()) > MAX_SHOWN and len(group) > 1:
                fold[name] = True
        return menu()''', '''            if len(menu()) > MAX_SHOWN and len(group) > 1:
                fold[name] = True
        items = menu()
        self._more = items[MAX_SHOWN - 1:] if len(items) > MAX_SHOWN else []  # a crowded day folds its tail (4d)
        return items[: MAX_SHOWN - 1] + [Choice("More...", Action("more_menu"))] if self._more else items''')

edit("app.py", '''        elif key == "f8":
            self.submit("lineage")
''', '''        elif key == "f8":
            self.submit("lineage")
        elif key == "f10":
            self.submit("rankings")
''')
print("task 6 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4d_task6.py && .venv/Scripts/python.exe -m pytest tests/test_sky_engine.py -q -p no:cacheprovider`
Expected: `task 6 edits applied`, then `10 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: the sky and the lists on screen - briefs, stage news, the sky page, the rankings page (F10), sheet and lineage"`

---
### Task 7: A sky-watcher's fuzz run, speed, soak and the fork guide

**Files:**
- Create: `tests/test_sky_speed.py`
- Modify (via `.patches/4d_task7.py`):
  - `tests/test_fuzz.py`: `test_a_sky_watcher`;
  - `tests/test_soak.py`: the sky index stays small;
  - `docs/debugging.md`: the phase 4d rules;
  - `docs/world-events.md` (new): how a fork adds an event.
- Test: `tests/test_sky_speed.py`, `tests/test_fuzz.py`

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: `test_a_sky_watcher[4]`, `[17]`; `test_the_season_hook_is_quick_with_fifty_regions`; `docs/world-events.md`.

- [ ] **Step 1: Write the failing test** — `tests/test_sky_speed.py`
```python
import time

import systems.sky as sky
import systems.world_events as W
from pathlib import Path
from world.db import World
from world.gen.materialize import ensure_town


def test_the_season_hook_is_quick_with_fifty_regions(tmp_path):
    world = World.create(tmp_path / "w.world", 7)
    for i in range(50):
        ensure_town(world, i % 10, i // 10, 0)
    n = 6
    world.set_time(n * W.SEASON)
    sky.season_events(world, n)
    start = time.process_time()
    sky.season_events(world, n + 1)
    assert time.process_time() - start < 0.02


def test_the_fork_guide_names_every_hook_and_knob():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("eligible", "start_data", "on_stage", "cultivation", "breakthrough", "practice", "encounter",
                 "beasts", "clash", "demonic", "patrol", "prices"):
        assert word in guide, word
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sky_speed.py -q -p no:cacheprovider`
Expected: `FileNotFoundError` for `docs/world-events.md` in the second test. The first test already passes, because it measures work Task 1 built; this task pins it.

- [ ] **Step 3: Edit the tests and docs** — `.patches/4d_task7.py`
```python
"""Task 7 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


FUZZ = "tests/test_fuzz.py"
Path(FUZZ).write_text(Path(FUZZ).read_text(encoding="utf-8") + '''

@pytest.mark.parametrize("seed", [4, 17])
def test_a_sky_watcher(tmp_path, seed, monkeypatch):
    """Seasons pass under a busy sky: comets, blood moons, tides, races, tribulations and the lists; every rule holds."""
    import systems.world_events as W
    for kind, spec in list(W.TYPES.items()):
        if spec["cycle"] == "season":
            monkeypatch.setitem(W.TYPES, kind, {**spec, "chance": min(1.0, spec["chance"] * 10)})
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 1.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Watcher{seed}", world_seed=seed)
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.3 and app.choices:
            app.submit(str(rng.randint(1, len(app.choices))))
        else:
            app.submit(rng.choice(["sky", "rankings", "seek", "swallow", "look", "meditate season", "meditate month",
                                   "go north", "go east", "go south", "go west", "rest", "journal"]))
        if rng.random() < 0.05:
            app.handle_key("f10", "")
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()
''', encoding="utf-8", newline="\n")

SOAK = "tests/test_soak.py"
edit(SOAK, '''    assert not any(world.entity(f).data.get("dissolved") for f in F.ensure_roster(world))
''', '''    assert not any(world.entity(f).data.get("dissolved") for f in F.ensure_roster(world))
    import systems.world_events as W
    assert len(W.index(world)) < 300, "the sky index keeps only what still matters (phase 4d)"
''')

edit("docs/debugging.md", '''- **Trade (phase 4c):**''', '''- **World events (phase 4d):** an occurrence keeps its calendar (stage ends in order, stages seen in order, over only once its time has passed); at most one live occurrence per type per place; every modifier within 0.25-4.0; a race's prize is claimed once, and every treasure has one owner (none once used); the Pavilion's lists name only people it believes in, in score order, once each, and its Young Dragons are 30 or under by its own belief. The fuzz run `test_a_sky_watcher` watches 300 turns of a busy sky.
- **Trade (phase 4c):**''')

Path("docs/world-events.md").write_text('''# World events: adding your own

DeepMurim's scheduled world events (phase 4d) are data plus a little code. A fork adds an event
without touching the engine: one entry in `systems/data/world_events.toml`, and, if it needs to
do more than lend modifiers, one module under `systems/events/`.

## 1. The TOML entry

~~~toml
[meteor_shower]
module = "systems.events.meteor_shower"   # optional
scope = "region"          # world | region | town | site (site: a town chosen in the region)
cycle = "season"          # "season": rolled each world season; "trigger": your code starts it
chance = 0.02             # per eligible place per season
stages = { foretold = 5, announced = 3, active = 10, aftermath = 10 }   # days; leave a stage out to skip it
modifiers = { cultivation = 1.2 }          # knobs, while active (see below)
prices = { iron = 0.8 }                    # 4c price multipliers, while active
readings = ["good fortune", "a hero's death"]   # what towns make of it; each town picks one
news = { predicate = "phenomenon", weight = 1.5, stages = ["announced", "active"] }
~~~

Each occurrence is a `world_event` entity. Its stage is worked out from the calendar; the first
time a stage is observed (every world season, and every time the player sees the place) a
`world_event_stage` event is committed and your module reacts.

## 2. The module's hooks (all optional)

| Hook | When | Returns |
|---|---|---|
| `eligible(world, place, n)` | after the chance roll, before it starts in season `n` | bool |
| `start_data(world, place, n, rng)` | when it starts | a dict kept on the occurrence (`None`: do not start) |
| `on_stage(world, occurrence, stage)` | the first time a stage is observed (`foretold`, `announced`, `active`, `aftermath`, `over`) | a list of events to commit |

A module can also register hooks of its own when it is imported: the blood moon adds its patrols
to `encounters.HUNTER_HOOKS`. `systems/sky.py` imports every module named in the TOML at start.

To start a `trigger` event from your own code: `systems.sky.start_events(world, kind, place, starts, data)`.

## 3. The knobs

`systems.world_events.factor(world, place, key, at=None)` multiplies the `key` modifiers of every
occurrence active over a place, clamped to 0.25-4.0. These keys are read today:

| Key | Read by |
|---|---|
| `cultivation` | meditation (player) and the life clock's growth (NPCs, at the season being lived) |
| `breakthrough` | breakthrough chance, player and NPC |
| `practice` | practising and learning arts |
| `encounter` | the road encounter chance |
| `beasts` | road encounters, and the share of them that are beasts |
| `clash` | the faction clock's clash chance (world-wide occurrences) |
| `demonic` | the combat weight of demonic-cult and unorthodox-clan members |
| `patrol` | righteous patrols calling out the ruthless |
| `prices` (a table, not a key) | 4c market prices, through `market.EVENT_FACTORS` |

A new knob is one `factor()` call in the system it should move, and a key in your TOML.

## 4. The worked examples

`systems/data/world_events.toml` holds eight: the qi tide and the comet (modifiers only), the
blood moon (a hook of its own), dao resonance (`eligible`, `start_data`, `on_stage`), tribulation
lightning (a trigger), the beast tide (attacks and a bounty), and the treasure light and star fall
(races, in `systems/races.py`). The debug rules in `debug/invariants.py` (`check_sky`,
`check_races`) guard every type, including yours.
''', encoding="utf-8", newline="\n")
print("task 7 edits applied")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4d_task7.py && .venv/Scripts/python.exe -m pytest tests/test_sky_speed.py -q -p no:cacheprovider`
Expected: `task 7 edits applied`, then `2 passed`.

Run: `.venv/Scripts/python.exe -m pytest tests/test_fuzz.py -q -p no:cacheprovider`
Expected: every fuzz test passes, including `test_a_sky_watcher[4]` and `[17]`. Treat any rule violation as a bug and find its cause with systematic debugging. Do not loosen the rule.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "test: a sky-watcher's fuzz run, season-hook speed, a bounded sky index, and the fork guide"`

---

## Self-review

**Spec coverage:**

| Spec section | Where it is built |
|---|---|
| §3.1–3.3 types, occurrences, scheduling | Task 1 |
| §3.4 modifiers and the knobs | Task 1 (`factor`), Task 2 (cultivation, breakthrough, practice, encounter, clash, demonic, patrol), Task 3 (beasts) |
| §3.5 news and readings | Task 1 |
| §4 the eight phenomena | Task 1 (qi tide), Task 2 (blood moon, comet, dao resonance), Task 3 (tribulation, beast tide), Task 4 (treasure light, star fall) |
| §5 treasure races | Task 4 |
| §6 rankings | Task 5 |
| §7 screens | Task 6 (briefs, stage lines, sky, rankings F10, sheet, journal, lineage), Tasks 3–4 (narration) |
| §8 debug rules | Task 1 (rules 1–3), Task 4 (rule 5), Task 5 (rule 4) |
| §9 testing | every task; fuzz, speed and soak in Task 7 |

**Differences from the spec:** plan-time rulings 1–15 above.

**Type consistency:**
- Index rows are always read through the `W.ID … W.DONE` column constants.
- `start_events(world, kind, place, starts, data)` is used the same way in Tasks 1, 3 and 4.
- The race data keys `prize`, `champions`, `beaten`, `out`, `claimed` and `item` are set in `race_start_data` and read in Tasks 4 and 7.
- `latest(world, knower)` returns `{"year", "lists", "time"}` everywhere it is read (Tasks 5 and 6).

**Dry run** (the whole plan on a scratch copy of master `6d721a1`: 744 passed, and the 500-year soak passes). It found and fixed:
- **An import cycle.** `price_events` loads the world clock, which loads the sky's modules. The beast tide now imports `price_events` as a module rather than importing a name from it.
- **Two old narration rules exposed by a new world path.** A road line repeated one from another grammar key (ruling 12), and a character named "Again" was flagged in "meet again" (ruling 13).
- **Soak speed.** After 500 years, a treasure light called 13 champions and one season took 123 ms. At most the 6 strongest now answer.
- **A crowded main menu.** 10 choices appeared once the sky, the lists and treasures joined the general group (ruling 15).
- **Pages as prose.** The sky and rankings pages printed rows in a prose colour, so asking twice broke the repeat rule. Their rows are now dim, like every other page.
- **A rumour that names people.** The `published` story named the first of Heaven, whom the player had never heard of. Anyone named on a list you have heard of now counts as someone you know of.
- **Tests that asked the wrong question:**
  - the player meets the weakest champion first;
  - a beast tide lasts 15 days, so the test stretches its active stage to cover its samples;
  - a second `look` at the same moment is "nothing has changed".
