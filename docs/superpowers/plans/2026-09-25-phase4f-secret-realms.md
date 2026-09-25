# Phase 4f: Secret Realms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Secret realms are sealed pocket worlds that open for a few days.
- The player delves them floor by floor, against guardians, trials and rival sect bands, for an ancient master's inheritance.
- If the gate closes on them, they are sealed in until it opens again.

**Architecture:**
- **A realm** is a lasting `secret_realm` entity: its master, entry rule and period, its floors of chambers, and its history. Everyone inside is `located_in` it.
- **Each opening** is a 4d world-event occurrence: `realm_opening` on the realm's own period, or `realm_awakening` when a treasure light cracks a new realm open.
- **Level of detail:** far from the player an opening is settled in one event when it closes. Once the player enters, the sects' bands are placed inside and take a step for each of the player's.
- **The engine:** a delve mode (`DelveMixin` and its siblings) replaces the town scene while the player is inside.

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-25-phase4f-secret-realms-design.md`

## Global Constraints

- **Save format:** no save-format version change.
  - New state lives in entities (`secret_realm`, and `person` realm spirits), entity data (`sealed_in`, `delve`, `delve_at`, `realms_seen`, `realm_heralds`), the occurrence's `data["data"]`, and the meta row `secret_realms`.
- **Knowledge vs truth:**
  - what happens inside is recorded where it happened (the realm), and reaches the world only with those who come out;
  - pages and briefs read beliefs and what the player saw.
- **Reads never write:** a look or a page never creates realms (`SR.realms`). The season clock seeds them (`SR.ensure_realms`).
- **The entity cache (4e):** all realm, chamber and delve state is written through `update_data`, never by editing `.data` in place.
- **Speed (CPU time, `time.process_time`):**
  - a delve step with three bands inside: under 40 ms;
  - a summarised closing with 12 delvers: under 10 ms;
  - the realms page: under 30 ms;
  - the 200-year soak keeps its 100 ms season budget, and the 500-year soak its 200 ms.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The gate closes between two of the player's steps, or during a fight inside.**
   - The player is sealed at once and cannot walk out of a shut gate.
   - Task 6 pins this with `test_the_gate_closes_between_two_steps_and_no_one_walks_out`.
2. **The player dies inside.**
   - The heir carries on at home; the body and what it carried stay where it fell, for later delvers.
   - Task 6 pins this with `test_letting_your_heir_carry_on_ends_your_tale`, and Task 4 with `test_what_the_dead_carried_lies_where_they_fell`.
3. **A save reloaded while inside a realm.**
   - The delve resumes: the header, the chamber and its choices.
   - Task 7 pins this with `test_a_save_reloaded_inside_a_realm_resumes_the_delve`.
4. **A token realm and a player with no token.**
   - A token can be bought from whoever holds one.
   - Task 3 pins this with `test_a_token_can_be_bought_from_its_holder`.
5. **A long catch-up (years meditated, a long sealing) passes a realm's opening season.**
   - The opening rolls on to its next turn; it is never lost.
   - Task 1 pins this with `test_a_missed_opening_rolls_on_to_its_next_turn`.

## Plan-time rulings (deviations from the spec, argued)

1. **Realms are seeded by the season clock, never by a read.**
   - A look or a page lists only realms already made (`SR.realms`). The dry run found a first look seeding realms, which changed saves that must not change and shifted the ids other seeded tests rely on.
   - An old save gains its realms at its next season, with their first openings still ahead.
   - *Cost if wrong:* none.
2. **An opening's gate stands open a fixed 8 days,** not 6–12 per realm: the TOML's stages belong to the type. *Cost if wrong:* less variety.
3. **An opening a long catch-up passed rolls on to the realm's next turn** (`SR.due`). *Cost if wrong:* none.
4. **The master's shade always stands one realm above whoever challenges it, for the NPCs far away too.**
   - The spec's formula then gives a summarised closing a 0.1 chance of the inheritance.
   - The dry run found the floor-count shade made the inheritance unwinnable under a Second-rate ceiling.
   - *Cost if wrong:* the legacy falls a little more often far away.
5. **Jade tokens:**
   - half go to the near sects' strongest, the rest to wanderers at the gate; none is hidden in another realm or made a Meet prize;
   - the player buys one from its holder, at three times its value.
   - *Cost if wrong:* fewer ways to a token.
6. **A caught sneak records a `trespassed` deed** at the gate town. The righteous hold it against you (−0.5 of doctrine), not a flat −1 with every sect there. *Cost if wrong:* a softer penalty with the ruthless.
7. **Sealed NPCs are frozen in time,** and their years are applied when they walk out: they age half the seasons and gain ×3 cultivation (level of detail). *Cost if wrong:* none visible.
8. **A sect leader who walks out after the sect filled the post returns an elder.** The dry run's fuzz found two living leaders. *Cost if wrong:* none.
9. **Bands step on the player's steps** (moving, taking, resting, trials, slipping past), not during fights. A band travelling with you follows you; it does not share fights. *Cost if wrong:* fights inside run without the bands moving.
10. **Guardians, reflections and a master's remnant are realm spirits:** `person` entities flagged `realm_spirit`, off the life clock, whose arts are given and never seeded. *Cost if wrong:* none.
11. **The dead master is a person, dead and buried in the realm,** bonded to the heir as `master`; the lineage page names them. *Cost if wrong:* none.
12. **Inside a realm, the place of any event or rumour is the gate's land** (`region_of`, the brief's `_place`). The dry run found briefs and the kin channel asking a realm for its region. *Cost if wrong:* none.
13. **A look asks `_special_look` first** (a new hook): the `Game` class defines `_do_look` itself, so a mixin cannot override it. *Cost if wrong:* none.
14. **Scalar meta values (the clock, the seed, the player) are kept in memory.**
    - The dry run measured a season reading `time` 523 times and `world_seed` 415 times.
    - The 200-year soak's season went from 109 ms to under 100 ms with realms in.
    - `entities(kind)` also serves decoded entities from the 4e entity cache. The dry run's 500-year soak spent 253 of its check's 484 ms decoding the same 2,500 people eleven times.
    - *Cost if wrong:* none; lists and dicts are never kept.
15. **The chamber's description is dim status, not prose.** It is shown after every step, and the rule against repeated narration caught it. *Cost if wrong:* none.
16. **One leaves only through an open gate, and each step checks the gate's clock.** The dry run's fuzz found the gate closing between steps with the player still free to walk out. *Cost if wrong:* none.
17. **Letting your heir carry on ends the sealed character's tale** as a death "sealed in a secret realm."
    - 4b's rules hold that every ancestor is dead and buried, so the sealed one does not walk out later as an NPC elder.
    - *Cost if wrong:* a story the spec wanted.
18. **Slipping past a guardian marks it passed for everyone this opening:** chamber state is shared. *Cost if wrong:* a later band slips by too.
19. **Two realms' gates cannot stand open in one town at once:** 4d allows one live occurrence per type and place. *Cost if wrong:* none.
20. **The Assembly round's timing test collects garbage first** (as 4e ruling 19 did for the rumour catch-up). It measures 16–31 ms alone and spiked to 62.5 ms inside the longer suite. *Cost if wrong:* none; the budget is unchanged.

21. **Wanderers and wandering token-holders are made only when the player is in the gate's region.**
    - Far away, only the near sects' members delve and hold tokens.
    - The dry run's 500-year soak grew by every far opening's new people, until the per-turn debug check took 344 ms against its 300 ms budget.
    - *Cost if wrong:* far openings are sect affairs only.

22. **At most 12 go in (the spec's limit), nearest sects first, and a sect's leader and elders stay home.**
    - The young generation goes in, as in the genre.
    - The dry run's 500-year save grew from 112 MB to 152 MB: every opening near a busy gate took 20 or more, heads among them, and the sects spent the centuries replacing them (2,023 recruits against 861 people).
    - *Cost if wrong:* no sect head is ever lost in a realm.

23. **A founder's sect seasons are settled before the scene names anyone.**
    - The realm fuzz found a 3c ordering bug: coming home, the scene listed who was there, then the sect's catch-up sent one of them away, and the knowledge rule caught a name on screen of someone no longer present.
    - The season's report now comes before the scene.
    - *Cost if wrong:* none.

24. **The rule on Young Dragons judges a list by the ages the Pavilion believed when it published it.**
    - The realm fuzz found a 4d rule re-run a year after the list (a newcomer reopens the world, clearing the rule's once-a-list mark), when the believed age had ticked from 30 to 31.
    - *Cost if wrong:* none.

**A known flake, not this phase's:** `tests/test_world_engine.py::test_arriving_in_a_busy_town_eight_seasons_on_is_quick`. With the 4e entity cache it now measures 47–78 ms against 150 ms, so it should no longer fail; if it does, re-run it alone and record the result.

---

### Task 1: Realms and their openings

**Files:**
- Create: `systems/secret_realms.py`, `systems/events/realm_opening.py`
- Modify (via `.patches/4f_task1.py`):
  - `systems/data/world_events.toml`: the `realm_opening` and `realm_awakening` types;
  - `systems/events/treasure_light.py`: a light may crack a realm open;
  - `systems/races.py`: a cracked light runs no race.
  - `world/db.py`: scalar meta values (the clock, the seed, the player) are kept in memory (a season read `time` 523 times), and `entities(kind)` serves decoded entities from the 4e entity cache;
- Test: `tests/test_secret_realms.py`, `tests/test_meta_cache.py`

**Interfaces:**
- Consumes:
  - `sky.start_events`, `sky.season_events`, `sky.observe`;
  - `W.index`, `W.SEASON`, `W.TYPES`;
  - `races.prize_for`, `races.race_start_data`;
  - `techniques.generate`, `create_technique`;
  - `world.gen.materialize.ensure_town`, `world.gen.region.region_spec`.
- Produces:
  - **`systems.secret_realms` (SR):**
    - constants: `ANCIENT = 3`, `CRACK_CHANCE = 0.25`, `OPENINGS = ("realm_opening", "realm_awakening")`, `GUARDIANS`, `TRIALS`;
    - `realms(world) -> list[int]` (the realms made so far; never writes);
    - `ensure_realms(world) -> list[int]` (every realm, ancient first; seeds the ancient ones on first call: the season clock's `places` hook and tests call it);
    - `make_realm(world, gate, path, ancient, n) -> int`;
    - `layout(rng, floors) -> list[list[dict]]`, `chamber(rng, kind, floor) -> dict`, `prize_at(rng, floor) -> dict`;
    - `due(world, n) -> list[int]`;
    - `opening_data(realm) -> dict`;
    - `opening_of(world, realm) -> int | None` (the live opening occurrence), `stage_of(world, occurrence) -> str`;
    - `on_stage(world, occurrence, stage) -> list[Event]`, `on_observe(world, occurrence) -> list[Event]`: hook points, empty in this task.
  - **Realm data:**
    - `gate`, `ancient`;
    - `master` (`name`, `art`, `weapon`);
    - `rule` (`kind`, `value`), `period`, `next_opening`;
    - `floors` (a list of floors, each a list of `{"kind", "state", "contents"}`);
    - `history`, `inheritance_claimed_by`, `sealed`.
  - **Opening data** (`occurrence.data["data"]`): `realm`, `delvers`, `teams`, `tokens`, `entered`, `closed`.
  - **Meta:** `secret_realms`, the list of realm ids.

- [ ] **Step 1: Write the failing test** — `tests/test_secret_realms.py`
```python
import pytest

import systems.encounters as encounters
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from engine.game import Game
from systems.creation import CreationChoice
from world.events import commit
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


def test_every_world_has_three_ancient_realms(game):
    world = game.world
    realms = [world.entity(r) for r in SR.ensure_realms(world)]
    assert len(realms) == SR.ANCIENT and all(r.kind == "secret_realm" and r.data["ancient"] for r in realms)
    for realm in realms:
        floors = realm.data["floors"]
        assert 3 <= len(floors) <= 6 and all(2 <= len(f) <= 4 for f in floors)
        assert all(f[-1]["kind"] == "stair" for f in floors[:-1]) and floors[-1][-1]["kind"] == "inheritance"
        assert realm.data["rule"]["kind"] in ("ceiling", "token", "quota")
        assert realm.data["next_opening"] > world.time // W.SEASON and 12 <= realm.data["period"] <= 40
        assert world.entity(realm.data["master"]["art"]).kind == "technique"
    assert SR.ensure_realms(world) == SR.realms(world) == [r.id for r in realms]  # seeded once


def test_a_look_makes_no_realms(game):
    game.perform(__import__("engine.actions", fromlist=["Action"]).Action("look"))
    assert SR.realms(game.world) == []  # the season clock seeds them; a read never writes


def test_a_realms_layout_is_the_same_for_the_same_world(tmp_path):
    def layouts(name):
        g = Game.new(tmp_path / f"{name}.world", "Hero", world_seed=7, creation=CreationChoice("origin", "hunter"))
        found = [(g.world.entity(r).name, g.world.entity(r).data["floors"], g.world.entity(r).data["rule"])
                 for r in SR.ensure_realms(g.world)]
        g.close()
        return found
    assert layouts("a") == layouts("b")


def test_an_old_save_gets_its_realms_with_openings_still_ahead(tmp_path):
    from world.db import World
    world = World.create(tmp_path / "old.world", 11)  # a world from before 4f: nothing has asked for realms yet
    world.set_time(40 * W.SEASON)
    assert all(world.entity(r).data["next_opening"] > 40 for r in SR.ensure_realms(world))
    world.close()


def test_a_missed_opening_rolls_on_to_its_next_turn(game):
    world = game.world
    realm = SR.ensure_realms(world)[0]
    period = world.entity(realm).data["period"]
    world.update_data(realm, next_opening=5)
    assert realm not in SR.due(world, 5 + period + 1)
    assert world.entity(realm).data["next_opening"] == 5 + 2 * period


def test_a_realm_opens_on_its_own_period(game):
    world = game.world
    realm = SR.ensure_realms(world)[0]
    n = world.time // W.SEASON + 1
    world.update_data(realm, next_opening=n)
    events = [e for e in sky.season_events(world, n) if e.kind == "sky_started" and e.data["type"] == "realm_opening"]
    assert [e.place for e in events] == [world.entity(realm).data["gate"]]
    assert events[0].data["data"] == SR.opening_data(realm)
    commit(world, events)
    assert world.entity(realm).data["next_opening"] == n + world.entity(realm).data["period"]
    assert SR.opening_of(world, realm) == W.index(world)[-1][W.ID]


def test_a_treasure_light_may_crack_a_newborn_realm_open(game, monkeypatch):
    import systems.events.treasure_light as tl
    monkeypatch.setattr(SR, "CRACK_CHANCE", 1.0)
    world, town = game.world, game.place.id
    before = SR.ensure_realms(world)
    commit(world, sky.start_events(world, "treasure_light", town, world.time,
                                   tl.start_data(world, town, 10, rng_for(1, "t"))))
    newborn = [r for r in SR.ensure_realms(world) if r not in before]
    assert len(newborn) == 1
    realm = world.entity(newborn[0])
    assert not realm.data["ancient"] and realm.data["gate"] == town and realm.data["rule"]["kind"] in ("open", "token")
    assert 3 <= len(realm.data["floors"]) <= 4
    assert SR.opening_of(world, realm.id) is not None  # its first opening begins at once
    world.set_time(world.time + 4 * 4)
    ids = sky.observe(world, town)
    assert not any(world.chronicle_entry(i).kind == "race_called" for i in ids)  # the light's treasure is the realm


def test_a_one_off_realm_opens_once(game, monkeypatch):
    import systems.events.treasure_light as tl
    monkeypatch.setattr(SR, "CRACK_CHANCE", 1.0)
    monkeypatch.setattr(SR, "ONE_OFF_CHANCE", 1.0)
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "treasure_light", town, world.time,
                                   tl.start_data(world, town, 10, rng_for(1, "t"))))
    realm = SR.ensure_realms(world)[-1]
    assert world.entity(realm).data["period"] is None and world.entity(realm).data["next_opening"] is None
    assert all(realm not in SR.due(world, n) for n in range(10, 80))
```

- [ ] **Step 1b: Write the failing test** — `tests/test_meta_cache.py`
```python
import pytest

from world.db import World


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "m.world", 5)
    yield w
    w.close()


def test_the_clock_is_read_from_memory_after_the_first_time(world, monkeypatch):
    world.set_time(40)
    reads = []
    real = world._conn

    class Counting:
        def execute(self, sql, *args):
            reads.append(sql)
            return real.execute(sql, *args)
    monkeypatch.setattr(world, "_conn", Counting())
    assert world.time == 40 and world.time == 40 and world.world_seed == 5
    assert not any("from meta" in sql for sql in reads)
    monkeypatch.setattr(world, "_conn", real)


def test_a_rolled_back_clock_is_forgotten(world):
    world.set_time(40)
    with pytest.raises(RuntimeError):
        with world.transaction():
            world.set_time(99)
            raise RuntimeError("the turn fails")
    assert world.time == 40


def test_a_listing_by_kind_is_served_from_memory(world):
    ids = [world.add_entity("thing", f"Jar {i}", {"n": i}) for i in range(3)]
    first = world.entities("thing")
    again = world.entities("thing")
    assert [e.id for e in again] == ids and all(a is b for a, b in zip(first, again))  # decoded once
    world.update_data(ids[1], n=9)
    assert [e.data["n"] for e in world.entities("thing")] == [0, 9, 2]


def test_a_list_is_never_kept_in_memory(world):
    world.set_meta("index", [[1, 2]])
    world.get_meta("index")[0].append(3)  # a caller that edits what it got back
    assert world.get_meta("index") == [[1, 2]]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_secret_realms.py tests/test_meta_cache.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.secret_realms'`, and `test_the_clock_is_read_from_memory_after_the_first_time` failing (each read of the clock queries the meta table).

- [ ] **Step 3: Write the realms** — `systems/secret_realms.py`
```python
"""Secret realms (phase 4f spec 2): sealed pocket worlds that open for a few days.

A realm is a lasting `secret_realm` entity at a gate town: its master and their art, its entry
rule, its period, its floors of chambers, and its history. Each opening is a 4d world-event
occurrence (`realm_opening`; `realm_awakening` for a newborn realm's first). Three ancient realms
are seeded into every world the first time anything asks (old saves too, never backdated); newborn
realms are cracked open by treasure lights.
"""

import systems.world_events as W
from systems.techniques import create_technique, generate
from world.events import Event, commit, listen
from world.gen.materialize import ensure_town
from world.gen.region import region_spec
from world.seed import rng_for

ANCIENT = 3
ANCIENT_PERIOD = (12, 40)
NEWBORN_PERIOD = (8, 20)
ONE_OFF_CHANCE = 0.6
CRACK_CHANCE = 0.25
GATE_RADIUS = 6
OPENINGS = ("realm_opening", "realm_awakening")
PLACES = ("Sunken Palace", "Cloud-Veiled Cave", "Nine Dragon Tomb", "Jade Valley", "Bronze Pagoda", "Frozen Abyss",
          "Moonlit Garden", "Thousand-Sword Mound")
EPITHETS = ("Azure Sage", "Crimson Emperor", "White Crane Immortal", "Iron-Blood Tyrant", "Silent Moon Nun",
            "Nine-Fingered Demon", "Wandering Sword Saint", "Jade Maiden")
WEAPONS = ("sword", "saber", "spear", "staff", "fan", "pair of gauntlets")
GUARDIANS = ("bronze puppet", "stone lion", "jade serpent", "iron-feathered roc", "ghost-fire wolf")
TRIALS = ("formation", "pressure", "mirror")
RULES_ANCIENT = (("ceiling", 0.5), ("token", 0.3), ("quota", 0.2))
RULES_NEWBORN = (("open", 0.6), ("token", 0.4))
CHAMBER_WEIGHTS = (("treasure", 3), ("guardian", 3), ("trial", 2), ("rivals", 2))


def _pick(rng, table) -> str:
    roll, total = rng.random(), 0.0
    for name, chance in table:
        total += chance
        if roll < total:
            return name
    return table[-1][0]


# --- the layout ---------------------------------------------------------------------------------

def prize_at(rng, floor: int) -> dict:
    """A treasure for a chamber on this floor (1 is the first): 4d's prizes, richer the deeper (spec §3.2)."""
    from systems.races import prize_for
    prize = prize_for(rng.choice(("treasure_light", "treasure_light", "star_fall")), rng)
    scale = 1 + 0.5 * floor
    if "value" in prize:
        prize["value"] = int(prize["value"] * scale)
    if "qi_years" in prize:
        prize["qi_years"] = round(prize["qi_years"] * scale, 2)
    if prize["kind"] == "manual":
        prize["grade"] = min(4, prize["grade"] + floor // 2)
        prize["completeness"] = round(min(1.0, prize["completeness"] + 0.05 * floor), 2)
    return prize


def chamber(rng, kind: str, floor: int) -> dict:
    contents: dict = {}
    if kind == "treasure":
        contents = {"prize": prize_at(rng, floor)}
    elif kind == "guardian":
        contents = {"species": rng.choice(GUARDIANS), "realm": min(4, floor + 1), "guardian": None}
    elif kind == "trial":
        contents = {"trial": rng.choice(TRIALS)}
    return {"kind": kind, "state": "untouched", "contents": contents}


def layout(rng, floors: int) -> list[list[dict]]:
    """Floors of 2-4 chambers: each ends in its stair down, the last in the inheritance."""
    out = []
    kinds = [k for k, _ in CHAMBER_WEIGHTS]
    weights = [w for _, w in CHAMBER_WEIGHTS]
    for f in range(1, floors + 1):
        chambers = [chamber(rng, rng.choices(kinds, weights=weights)[0], f) for _ in range(rng.randint(1, 3))]
        chambers.append(chamber(rng, "inheritance" if f == floors else "stair", f))
        out.append(chambers)
    return out


# --- making realms ----------------------------------------------------------------------------------

def make_realm(world, gate: int, path: str, ancient: bool, n: int) -> int:
    rng = rng_for(world.world_seed, path)
    epithet = rng.choice(EPITHETS)
    art_name, art = generate(rng, "martial", grade=4 if ancient else 3)
    art_id = create_technique(world, art_name, art)
    floors = rng.randint(3, 6) if ancient else rng.randint(3, 4)
    rule = _pick(rng, RULES_ANCIENT if ancient else RULES_NEWBORN)
    value = rng.choice(("second-rate", "first-rate")) if rule == "ceiling" else None
    if ancient:
        period = rng.randint(*ANCIENT_PERIOD)
        next_opening = n + rng.randint(2, period)  # ahead, never backdated (an old save's too)
    else:
        period = None if rng.random() < ONE_OFF_CHANCE else rng.randint(*NEWBORN_PERIOD)
        next_opening = None  # its first opening is the awakening
    data = {"gate": gate, "ancient": ancient,
            "master": {"name": f"the {epithet}", "art": art_id, "weapon": f"the {epithet}'s {rng.choice(WEAPONS)}"},
            "rule": {"kind": rule, "value": value}, "period": period, "next_opening": next_opening,
            "floors": layout(rng, floors), "history": [], "inheritance_claimed_by": None, "sealed": []}
    return world.add_entity("secret_realm", f"the {rng.choice(PLACES)} of the {epithet}", data, path)


def realms(world) -> list[int]:
    """The realms made so far, without making any: a read (a look, a page) must never write."""
    return list(world.get_meta("secret_realms") or [])


def ensure_realms(world) -> list[int]:
    """Every realm, ancient first; the three ancient ones are seeded the first time anyone asks."""
    found = world.get_meta("secret_realms")
    if found is not None:
        return list(found)
    n = world.time // W.SEASON
    rng = rng_for(world.world_seed, "realms:ancient")
    made = []
    for k in range(ANCIENT):
        x, y = rng.randint(-GATE_RADIUS, GATE_RADIUS), rng.randint(-GATE_RADIUS, GATE_RADIUS)
        gate = ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))
        made.append(make_realm(world, gate, f"realm:ancient:{k}", True, n))
    world.set_meta("secret_realms", made)
    return made


# --- openings ------------------------------------------------------------------------------------

def due(world, n: int) -> list[int]:
    """Realms opening in season `n`. An opening missed (a long catch-up passed it) rolls on to its next turn."""
    found = []
    for realm in ensure_realms(world):
        data = world.entity(realm).data
        nxt, period = data["next_opening"], data["period"]
        if nxt is not None and nxt < n:
            nxt = nxt + period * ((n - nxt + period - 1) // period) if period else None
            world.update_data(realm, next_opening=nxt)
        if nxt == n:
            found.append(realm)
    return found


def opening_data(realm: int) -> dict:
    return {"realm": realm, "delvers": [], "teams": [], "tokens": [], "entered": [], "closed": False}


def stage_of(world, occurrence: int) -> str:
    return W.stage_at(world.entity(occurrence).data, world.time)


def opening_of(world, realm: int) -> int | None:
    """The live opening of this realm, if one is under way."""
    for row in W.index(world):
        if row[W.TYPE] in OPENINGS and not row[W.DONE] and world.entity(row[W.ID]).data["data"]["realm"] == realm:
            return row[W.ID]
    return None


def on_stage(world, occurrence, stage: str) -> list[Event]:
    return []


def on_observe(world, occurrence) -> list[Event]:
    return []


@listen("sky_started")
def _started(world, event, event_id: int) -> None:
    """An opening moves its realm's clock on; a treasure light that cracks a realm open makes it (spec §4.6)."""
    import systems.sky as sky
    d = event.data
    n = d["starts"] // W.SEASON
    if d["type"] in OPENINGS:
        realm = world.entity(d["data"]["realm"])
        period = realm.data["period"]
        world.update_data(realm.id, next_opening=n + period if period else None)
    elif d["type"] == "treasure_light" and d["data"].get("cracked"):
        realms = ensure_realms(world)
        realm = make_realm(world, d["place"], f"realm:newborn:{event_id}", False, n)
        world.set_meta("secret_realms", realms + [realm])
        commit(world, sky.start_events(world, "realm_awakening", d["place"], d["starts"], opening_data(realm)))
```

- [ ] **Step 4: Write the event type** — `systems/events/realm_opening.py`
```python
"""An opening of a secret realm (phase 4f spec 2.4): heralded, then the gate stands open for eight days.

`realm_opening` comes round on each realm's own period (`every = 1`, with `places` naming the gates
due this season); `realm_awakening` is a newborn realm's first opening, started by its treasure light.
"""

import systems.secret_realms as SR


def places(world, n: int, rng) -> list[int]:
    return sorted({world.entity(r).data["gate"] for r in SR.due(world, n)})


def start_data(world, gate: int, n: int, rng) -> dict | None:
    realms = [r for r in SR.due(world, n) if world.entity(r).data["gate"] == gate]
    return SR.opening_data(realms[0]) if realms else None


def on_stage(world, occurrence, stage: str) -> list:
    return SR.on_stage(world, occurrence, stage)


def on_observe(world, occurrence) -> list:
    return SR.on_observe(world, occurrence)
```

- [ ] **Step 5: Edit the existing files** — `.patches/4f_task1.py`
```python
"""Task 1 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    Path(path).write_text(Path(path).read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


append("systems/data/world_events.toml", '''
[realm_opening]
module = "systems.events.realm_opening"
scope = "town"
cycle = "every"
every = 1
sky = false
stages = { foretold = 30, announced = 10, active = 8, aftermath = 20 }
news = { predicate = "phenomenon", weight = 2.0, stages = ["foretold", "announced"] }

[realm_awakening]
module = "systems.events.realm_opening"
scope = "town"
cycle = "trigger"
sky = false
stages = { announced = 3, active = 8, aftermath = 20 }
''')

edit("systems/events/treasure_light.py", '''def start_data(world, site: int, n: int, rng) -> dict:
    return race_start_data("treasure_light", rng)''', '''def start_data(world, site: int, n: int, rng) -> dict:
    import systems.secret_realms as SR  # a light may mark a realm's gate, not a treasure (phase 4f spec 4.6)
    cracked = rng_for(world.world_seed, f"crack:{site}:{n}").random() < SR.CRACK_CHANCE
    return {**race_start_data("treasure_light", rng), "cracked": cracked}''')
edit("systems/events/treasure_light.py", '''from systems.races import race_stage, race_start_data
''', '''from systems.races import race_stage, race_start_data
from world.seed import rng_for
''')

RACES = "systems/races.py"
edit(RACES, '''def race_stage(world, occurrence, stage: str) -> list[Event]:
''', '''def race_stage(world, occurrence, stage: str) -> list[Event]:
    if occurrence.data["data"].get("cracked"):
        return []  # the light opened a secret realm: there is no treasure to race for (4f)
''')
edit(RACES, '''            and world.entity(row[W.ID]).data["data"]["claimed"] is None]''',
     '''            and world.entity(row[W.ID]).data["data"]["claimed"] is None
            and not world.entity(row[W.ID]).data["data"].get("cracked")]''')
DB = "world/db.py"
edit(DB, '''        self._entities: dict[int, Entity] = {}''', '''        self._entities: dict[int, Entity] = {}
        self._meta: dict = {}  # scalar meta values (the clock, the seed): a season reads `time` hundreds of times''')
edit(DB, '''    def get_meta(self, key: str, default=None):
        row = self._conn.execute("select value from meta where key = ?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    def set_meta(self, key: str, value) -> None:
        self._conn.execute(
            "insert into meta(key, value) values(?, ?) on conflict(key) do update set value = excluded.value",
            (key, json.dumps(value)),
        )''', '''    def get_meta(self, key: str, default=None):
        if key in self._meta:
            return self._meta[key]
        row = self._conn.execute("select value from meta where key = ?", (key,)).fetchone()
        if row is None:
            return default
        value = json.loads(row[0])
        if isinstance(value, (int, float, str, bool)):  # never a list or dict: a caller may edit what it gets back
            self._meta[key] = value
        return value

    def set_meta(self, key: str, value) -> None:
        self._conn.execute(
            "insert into meta(key, value) values(?, ?) on conflict(key) do update set value = excluded.value",
            (key, json.dumps(value)),
        )
        if isinstance(value, (int, float, str, bool)):
            self._meta[key] = value
        else:
            self._meta.pop(key, None)''')
edit(DB, '''    def entities(self, kind: str) -> list[Entity]:
        rows = self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities where kind = ? order by id", (kind,)
        )
        return [_entity(row) for row in rows]''', '''    def entities(self, kind: str) -> list[Entity]:
        """Every entity of a kind, decoded once: a 500-year world's rules list 2,500 people each turn."""
        found = []
        for row in self._conn.execute(
                "select id, kind, name, seed_path, created_at, data from entities where kind = ? order by id", (kind,)):
            entity = self._entities.get(row[0])
            if entity is None:
                entity = _entity(row)
                self._remember(entity)
            found.append(entity)
        return found''')
edit(DB, '''                self._entities.clear()  # what the transaction wrote is gone''', '''                self._entities.clear()  # what the transaction wrote is gone
                self._meta.clear()''')
print("task 1 edits applied")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4f_task1.py && .venv/Scripts/python.exe -m pytest tests/test_secret_realms.py tests/test_meta_cache.py -q -p no:cacheprovider`
Expected: `task 1 edits applied`, then `12 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 7: Commit**

Run: `git add -A && git commit -m "feat: secret realms - three ancient realms in every world, seeded layouts, openings on their own periods, and realms cracked open by treasure lights"`

---
### Task 2: The gate: who may enter, jade tokens, who the sects send, and openings far away

**Files:**
- Create: `systems/realm_gates.py`, `narrate/realm_text.py`
- Modify (via `.patches/4f_task2.py`):
  - `systems/secret_realms.py`: `on_stage` hands the gate its stages;
  - `systems/lives.py`: the sealed are frozen in time;
  - `debug/invariants.py`: `check_realms` (spec §7 rules 2 and 4);
  - `narrate/outcomes.py`: imports `narrate.realm_text`.
- Test: `tests/test_realm_gates.py`

**Interfaces:**
- Consumes (Task 1):
  - `SR.ensure_realms`, `SR.opening_data`, `SR.opening_of`, `SR.prize_at`, `SR.OPENINGS`;
  - `T.realm_of`, `T.alive` (4e);
  - `races.make_prize`;
  - `founding.make_person`, `membership.set_membership`;
  - `realms.add_energy`, `bodies.load_body`, `save_body`, `lives.current_season`.
- Produces:
  - **`systems.realm_gates` (G):**
    - constants: `RANGE = 3`, `TOKENS = (3, 8)`, `PER_SECT = 3`, `PER_SECT_TOKEN = 2`, `MAX_DELVERS = 12`, `HEADS = {"leader", "elder"}`, `WANDERER_CHANCE = 0.3`, `MAX_WANDERERS = 3`, `OUT_BASE = 0.6`, `OUT_PER_FLOOR = 0.05`, `DEAD_CHANCE = 0.25`, `LOOT_CHANCE = 0.5`, `INHERIT_PER_MARGIN = 0.1`, `SEALED_GROWTH = 3.0`;
    - `ceiling_of(world, realm) -> int | None`, `tokens_of(world, person, realm) -> list[int]`, `near_sects(world, gate) -> list[int]`;
    - `admits(world, realm, person) -> str | None`: why the gate refuses; the quota's sponsor and sneaking are the engine's (Task 3);
    - `token_events`, `delver_events`, `walk_out_events`, `closing_events(world, occurrence) -> list[Event]`;
    - `seal(world, person, realm) -> None`;
    - `inherit(world, person, realm) -> None`: the art (complete), the weapon, the title; Task 4 adds the player's master bond;
    - `shade_realm(world, challenger) -> int`: one realm above the challenger.
  - **Events:**
    - `tokens_made` (`occurrence`, `realm`, `holders`);
    - `delvers_chosen` (`occurrence`, `teams` = `[{"faction", "members"}]`);
    - `walked_out` (actors: the sealed; `realm`);
    - `realm_closed` (`occurrence`, `realm`, `fates` = `{str(person): "out" | "dead" | "sealed"}`, `loot` = `{str(person): prize}`, `inherited`).
  - **Person data:** `sealed_in` = `{"realm", "season"}`. **Items:** `treasure` entities of kind `token` (`realm`, `used`, `value`) and kind `weapon`.
  - **Facts:** `delved` (variant `realm_name`), `took` (variant `prize`), `inherited` (weight 3.0), `sealed` (weight 1.5).
  - `debug.invariants.check_realms(world) -> list[str]`.

- [ ] **Step 1: Write the failing test** — `tests/test_realm_gates.py`
```python
import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_realms
from engine.game import Game
from systems import factions as F
from systems import founding
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_town


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


def opening(game, kind="ceiling", value="second-rate"):
    """The first ancient realm, its gate moved to the player's town (the sects are near), opening now."""
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": kind, "value": value})
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    return realm, W.index(world)[-1][W.ID]


def at(game, occurrence, when):
    """Move to a stage of the opening and let the gate town see it."""
    d = game.world.entity(occurrence).data
    game.world.set_time({"announced": d["ends"]["foretold"], "active": d["active"][0], "closed": d["active"][1]}[when])
    sky.observe(game.world, d["place"])


def away(game):
    world, me = game.world, game.player.id
    world.unrelate(me, "located_in")
    world.relate(me, ensure_town(world, 5, 5, 0), "located_in")


def test_the_ceiling_refuses_the_strong(game):
    world, town = game.world, game.place.id
    realm, _ = opening(game)
    strong = founding.make_person(world, "test:strong", town, occupation="monk", age=50, realm="first-rate")
    weak = founding.make_person(world, "test:weak", town, occupation="monk", age=20, realm="third-rate")
    assert "will not admit" in G.admits(world, realm, strong) and G.admits(world, realm, weak) is None


def test_a_token_realm_hands_out_tokens_and_spends_them_at_the_gate(game):
    world = game.world
    realm, occurrence = opening(game, "token", None)
    at(game, occurrence, "announced")
    tokens = world.entity(occurrence).data["data"]["tokens"]
    assert G.TOKENS[0] <= len(tokens) <= G.TOKENS[1]
    assert all(len(world.sources(t, "owns")) == 1 for t in tokens)
    at(game, occurrence, "active")
    delvers = world.entity(occurrence).data["data"]["delvers"]
    assert delvers and all(world.entity(t).data["used"] for t in tokens if not world.sources(t, "owns"))
    assert all(not G.tokens_of(world, p, realm) for p in delvers)  # each spent theirs to pass


def test_the_near_sects_send_their_strongest_under_the_ceiling(game):
    world = game.world
    realm, occurrence = opening(game)
    at(game, occurrence, "active")
    t = world.entity(occurrence).data["data"]
    assert t["delvers"] and all(T.realm_of(world, p) <= G.ceiling_of(world, realm) for p in t["delvers"])
    for team in t["teams"]:
        assert len(team["members"]) <= (G.PER_SECT if team["faction"] is not None else 1)
    assert len(t["delvers"]) <= G.MAX_DELVERS
    assert not any(d.get("role") in G.HEADS for p in t["delvers"] for _, _, d in F.memberships(world, p))


def test_a_closing_far_away_settles_every_fate_and_moves_only_the_sealed(game):
    world = game.world
    realm, occurrence = opening(game)
    at(game, occurrence, "active")
    away(game)
    at(game, occurrence, "closed")
    t = world.entity(occurrence).data["data"]
    [closed] = [e for e in world.chronicle_of_kind("realm_closed") if e.data["occurrence"] == occurrence]
    fates = closed.data["fates"]
    assert set(fates) == {str(p) for p in t["delvers"]} and t["closed"]
    for person, fate in fates.items():
        p = int(person)
        inside = world.targets(p, "located_in") == [realm]
        assert inside == (fate == "sealed")
        assert (fate == "dead") == bool(world.entity(p).data.get("dead"))
        if fate == "sealed":
            assert p in world.entity(realm).data["sealed"]
            assert all(d.get("status") == "missing" for _, _, d in F.memberships(world, p))
    assert world.entity(realm).data["history"][-1]["entered"] == len(t["delvers"])
    assert check_realms(world) == []


def test_survivors_carry_the_story_out(game, monkeypatch):
    monkeypatch.setattr(G, "OUT_BASE", 1.0)
    world = game.world
    realm, occurrence = opening(game)
    at(game, occurrence, "active")
    away(game)
    at(game, occurrence, "closed")
    delvers = world.entity(occurrence).data["data"]["delvers"]
    heard = {f.subject for _, f in world.known_facts(world.entity(occurrence).data["place"]) if f.predicate == "delved"}
    assert heard == set(delvers)


def test_the_sealed_walk_out_at_the_next_opening(game, monkeypatch):
    monkeypatch.setattr(G, "OUT_BASE", 0.0)
    monkeypatch.setattr(G, "DEAD_CHANCE", 0.0)
    world, town = game.world, game.place.id
    realm, occurrence = opening(game)
    at(game, occurrence, "active")
    away(game)
    at(game, occurrence, "closed")
    sealed = list(world.entity(realm).data["sealed"])
    ages = {p: float(world.entity(p).data.get("age", 30)) for p in sealed}
    assert sealed and all(not lives.simulated(world.entity(p)) for p in sealed)  # frozen while sealed
    world.set_time(world.time + 8 * W.SEASON)
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    at(game, W.index(world)[-1][W.ID], "active")
    assert world.entity(realm).data["sealed"] == []
    for p in sealed:
        person = world.entity(p)
        assert world.targets(p, "located_in") == [town] and not person.data.get("sealed_in")
        assert float(person.data["age"]) == pytest.approx(ages[p] + 1.0, abs=0.3)  # eight seasons at half pace
        assert person.data["lived_to"] == lives.current_season(world)
        assert all(d.get("status") == "member" for _, _, d in F.memberships(world, p))


def test_a_sealed_leader_whose_post_was_filled_walks_out_an_elder(game):
    world, town = game.world, game.place.id
    realm, occurrence = opening(game)
    faction = next(f for f in G.near_sects(world, town))
    old = founding.make_person(world, "test:old leader", town, occupation="monk", age=50, realm="second-rate")
    new = founding.make_person(world, "test:new leader", town, occupation="monk", age=40, realm="second-rate")
    for person, status in ((old, "member"), (new, "member")):
        world.relate(person, faction, "member_of", 4, {"role": "leader", "hall": None, "merit": 0, "status": status,
                                                        "secret": False})
    G.seal(world, old, realm)  # gone: the sect's other leader holds the seat
    commit(world, [Event("walked_out", (old,), town, {"realm": realm})])
    assert F.membership(world, old, faction)[1]["role"] == "elder"


def test_an_inheritance_is_claimed_once(game, monkeypatch):
    monkeypatch.setattr(G, "OUT_BASE", 1.0)
    monkeypatch.setattr(G, "INHERIT_PER_MARGIN", 10.0)
    world = game.world
    realm, occurrence = opening(game)
    at(game, occurrence, "active")
    away(game)
    at(game, occurrence, "closed")
    heir = world.entity(realm).data["inheritance_claimed_by"]
    assert heir is not None and world.entity(heir).data["titles"][-1].startswith("Last Disciple of")
    art = world.entity(realm).data["master"]["art"]
    assert any(t == art for t, _, _ in world.relations_from(heir, "knows"))
    world.set_time(world.time + 8 * W.SEASON)  # the next opening: the legacy is gone
    commit(world, sky.start_events(world, "realm_opening", game.place.id, world.time, SR.opening_data(realm)))
    again = W.index(world)[-1][W.ID]
    at(game, again, "active")
    at(game, again, "closed")
    assert sum(1 for e in world.chronicle_of_kind("realm_closed") if e.data["inherited"]) == 1
    assert world.entity(realm).data["inheritance_claimed_by"] == heir and check_realms(world) == []


def test_an_opening_far_away_makes_no_one_new(game):
    world = game.world
    away(game)
    realm = SR.ensure_realms(world)[0]
    gate = world.entity(realm).data["gate"]
    world.update_data(realm, rule={"kind": "token", "value": None})
    people = len(world.entities("person"))
    commit(world, sky.start_events(world, "realm_opening", gate, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    for when in ("announced", "active", "closed"):
        at(game, occurrence, when)
    assert len(world.entities("person")) == people  # the far wanderers and token-holders are never made


def test_the_rules_catch_someone_inside_a_realm_who_should_not_be(game):
    world, town = game.world, game.place.id
    realm, _ = opening(game)
    stray = founding.make_person(world, "test:stray", town, occupation="monk", age=30)
    world.unrelate(stray, "located_in")
    world.relate(stray, realm, "located_in")
    assert any("is inside" in p for p in check_realms(world))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_realm_gates.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.realm_gates'`.

- [ ] **Step 3: Write the gate** — `systems/realm_gates.py`
```python
"""The gate of a secret realm (phase 4f spec 4): who may enter, the jade tokens, who the sects send,
and what becomes of them when the gate closes far from the player. The sealed walk out at the next opening.

Level of detail (spec §2.5): the delvers are chosen when the gate opens and nobody moves. If the
player never enters, one `realm_closed` event settles every fate when the gate closes; only the
sealed leave their towns. (When the player is inside, Task 6 closes the gate instead.)
"""

import systems.lives as lives
import systems.secret_realms as SR
import systems.world_events as W
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.founding import make_person
from systems.membership import set_membership
from systems.realms import REALMS, add_energy, realm_index
from systems.tournaments import alive, realm_of
from world.events import Event, effect, listen
from world.seed import rng_for

RANGE = 3
TOKENS = (3, 8)
PER_SECT, PER_SECT_TOKEN = 3, 2
MAX_DELVERS = 12  # spec §4.2: four to twelve go in
HEADS = frozenset({"leader", "elder"})  # a sect's heads stay home: the young generation goes in
WANDERER_CHANCE, MAX_WANDERERS = 0.3, 3
OUT_BASE, OUT_PER_FLOOR, DEAD_CHANCE = 0.6, 0.05, 0.25
LOOT_CHANCE = 0.5
INHERIT_PER_MARGIN = 0.1
SEALED_GROWTH = 3.0  # the dense qi of a realm: three times the cultivation
WEAPON_VALUE = 1500


# --- who may enter -----------------------------------------------------------------------------

def ceiling_of(world, realm: int) -> int | None:
    rule = world.entity(realm).data["rule"]
    return realm_index(rule["value"]) if rule["kind"] == "ceiling" else None


def tokens_of(world, person: int, realm: int) -> list[int]:
    found = []
    for item in world.targets(person, "owns"):
        entity = world.entity(item)
        if entity is not None and entity.kind == "treasure" and entity.data.get("kind") == "token" \
                and entity.data.get("realm") == realm and not entity.data.get("used"):
            found.append(item)
    return found


def near_sects(world, gate: int) -> list[int]:
    """Staffed factions with a home within RANGE regions of the gate, as 4d's races count them; nearest first."""
    xy = W.place_xy(world, gate)
    found = []
    for faction in world.entities("faction"):
        fd = faction.data
        if fd.get("type") not in F.STAFFED or fd.get("type") == "player_sect" or fd.get("dissolved") or "home" not in fd:
            continue
        if xy is not None and max(abs(fd["home"][0] - xy[0]), abs(fd["home"][1] - xy[1])) <= RANGE:
            found.append((max(abs(fd["home"][0] - xy[0]), abs(fd["home"][1] - xy[1])), faction.id))
    return [f for _, f in sorted(found)]


def _member_of_near(world, person: int, gate: int) -> bool:
    near = set(near_sects(world, gate))
    return any(f in near and d.get("status", "member") == "member" for f, _, d in F.memberships(world, person))


def admits(world, realm: int, person: int) -> str | None:
    """Why the gate refuses this person, or None. (A quota's sponsor and sneaking in are the engine's.)"""
    rule = world.entity(realm).data["rule"]
    cap = ceiling_of(world, realm)
    if cap is not None and realm_of(world, person) > cap:
        return f"The seal presses you back; it will not admit a {REALMS[realm_of(world, person)].name}."
    if rule["kind"] == "token" and not tokens_of(world, person, realm):
        return "The gate will not open without a jade token of this realm."
    if rule["kind"] == "quota" and not _member_of_near(world, person, world.entity(realm).data["gate"]):
        return "No sect near this gate has given you one of its places."
    return None


def _near_player(world, gate: int) -> bool:
    """Whether the player is in the gate's region: only there are wanderers made (level of detail, plan ruling 21)."""
    player = world.get_meta("player_id")
    here = world.targets(player, "located_in") if player is not None else []
    return bool(here) and W.place_xy(world, here[0]) == W.place_xy(world, gate)


def _strongest(world, faction: int, cap: int | None, count: int) -> list[int]:
    able = [p for p, _, d in world.relations_to(faction, "member_of")  # one query; below the sect's heads
            if d.get("status", "member") == "member" and d.get("role") not in HEADS and alive(world, p)
            and not world.entity(p).data.get("is_player") and not world.entity(p).data.get("sealed_in")]
    able = [p for p in able if cap is None or realm_of(world, p) <= cap]
    return sorted(able, key=lambda p: (-realm_of(world, p), p))[:count]


# --- the stages -------------------------------------------------------------------------------------

def token_events(world, occurrence) -> list[Event]:
    """At `announced`: 3-8 jade tokens, half to the near sects' strongest, the rest to wanderers at the gate."""
    t = occurrence.data["data"]
    realm = world.entity(t["realm"])
    if realm.data["rule"]["kind"] != "token" or t["tokens"]:
        return []
    gate = occurrence.data["place"]
    rng = rng_for(world.world_seed, f"realm:{occurrence.id}:tokens")
    count = rng.randint(*TOKENS)
    holders = []
    for faction in near_sects(world, gate):
        if len(holders) >= (count + 1) // 2:
            break
        holders += [p for p in _strongest(world, faction, None, 1) if p not in holders]
    i = 0
    while len(holders) < count and _near_player(world, gate):  # far away, only the sects hold tokens
        holders.append(make_person(world, f"realm:{occurrence.id}:holder:{i}", gate, occupation="wandering swordsman",
                                   age=rng.randint(18, 40), realm=rng.choice(("third-rate", "second-rate"))))
        i += 1
    return [Event("tokens_made", (), gate, {"occurrence": occurrence.id, "realm": realm.id, "holders": holders})]


@effect("tokens_made")
def _tokens_made(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    name = world.entity(d["realm"]).name
    tokens = []
    for holder in d["holders"]:
        token = world.add_entity("treasure", f"a jade token of {name}",
                                 {"kind": "token", "realm": d["realm"], "used": False, "value": 120})
        world.relate(holder, token, "owns")
        tokens.append(token)
    world.update_data(occurrence.id, data={**occurrence.data["data"], "tokens": tokens})


def delver_events(world, occurrence) -> list[Event]:
    """When the gate opens: the near sects send their strongest who pass the rule; wanderers may come too."""
    t = occurrence.data["data"]
    if t["delvers"]:
        return []
    realm, gate = t["realm"], occurrence.data["place"]
    rule = world.entity(realm).data["rule"]["kind"]
    cap = ceiling_of(world, realm)
    teams = []
    if rule == "token":
        holders = [p for token in t["tokens"] for p in world.sources(token, "owns")
                   if alive(world, p) and not world.entity(p).data.get("is_player")]
        by_sect: dict = {}
        for p in sorted(set(holders)):
            sect = next((f for f, _, d in F.memberships(world, p) if d.get("status", "member") == "member"
                         and world.entity(f).data.get("type") in F.STAFFED), None)
            by_sect.setdefault(sect, []).append(p)
        for sect, members in sorted(by_sect.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
            teams += [{"faction": sect, "members": members[:PER_SECT_TOKEN]}] if sect is not None \
                else [{"faction": None, "members": [p]} for p in members]
    else:
        for faction in near_sects(world, gate):
            room = MAX_DELVERS - sum(len(team["members"]) for team in teams)
            members = _strongest(world, faction, cap, min(PER_SECT, room))
            if members:
                teams.append({"faction": faction, "members": members})
        rng = rng_for(world.world_seed, f"realm:{occurrence.id}:wanderers")
        realms = [r for r in ("third-rate", "second-rate", "first-rate") if cap is None or realm_index(r) <= cap]
        for i in range(MAX_WANDERERS if _near_player(world, gate) else 0):  # nobody made far from the player
            if rng.random() < WANDERER_CHANCE and sum(len(team["members"]) for team in teams) < MAX_DELVERS:
                wanderer = make_person(world, f"realm:{occurrence.id}:wanderer:{i}", gate,
                                       occupation="wandering swordsman", age=rng.randint(18, 45),
                                       realm=rng.choice(realms))
                teams.append({"faction": None, "members": [wanderer]})
    return [Event("delvers_chosen", (), gate, {"occurrence": occurrence.id, "teams": teams})]


@effect("delvers_chosen")
def _delvers_chosen(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    delvers = [p for team in d["teams"] for p in team["members"]]
    for person in delvers:  # a token passes one through the gate and is gone
        for token in tokens_of(world, person, t["realm"])[:1]:
            world.unrelate(person, "owns", token)
            world.update_data(token, used=True)
    world.update_data(occurrence.id, data={**t, "teams": d["teams"], "delvers": delvers})


def walk_out_events(world, occurrence) -> list[Event]:
    """When the gate opens again, those sealed at the last closing walk out (spec §4.4)."""
    realm = world.entity(occurrence.data["data"]["realm"])
    sealed = [p for p in realm.data["sealed"] if alive(world, p) and not world.entity(p).data.get("is_player")]
    if not sealed:
        return []
    return [Event("walked_out", tuple(sealed), occurrence.data["place"], {"realm": realm.id})]


@effect("walked_out")
def _walked_out(world, event) -> None:
    realm = world.entity(event.data["realm"])
    now = lives.current_season(world)
    for person in event.actors:
        entity = world.entity(person)
        seasons = max(0, now - entity.data["sealed_in"]["season"])
        body = load_body(world, person)  # the dense qi, and time at half pace (spec §4.4)
        add_energy(body, seasons / 4 * SEALED_GROWTH * 0.5)
        save_body(world, person, body)
        world.update_data(person, sealed_in=None, lived_to=now,
                          age=round(float(entity.data.get("age", 30)) + seasons / 8, 2))
        world.unrelate(person, "located_in")
        world.relate(person, event.place, "located_in")
        for faction, _, data in F.memberships(world, person):
            if data.get("status") == "missing":
                taken = data.get("role") == "leader" and any(  # the sect chose another while they were gone
                    d.get("role") == "leader" and d.get("status", "member") == "member" and alive(world, p)
                    for p, _, d in world.relations_to(faction, "member_of") if p != person)
                set_membership(world, person, faction, status="member", **({"role": "elder"} if taken else {}))
    world.update_data(realm.id, sealed=[p for p in realm.data["sealed"] if p not in event.actors])


# --- the gate closes far from the player ----------------------------------------------------------

def shade_realm(world, challenger: int) -> int:
    """The master's remnant always stands one realm above whoever challenges it (spec §3.2; plan ruling 4)."""
    return min(len(REALMS) - 1, realm_of(world, challenger) + 1)


def closing_events(world, occurrence) -> list[Event]:
    t = occurrence.data["data"]
    if t["closed"]:
        return []
    realm = world.entity(t["realm"])
    floors = len(realm.data["floors"])
    rng = rng_for(world.world_seed, f"realm:{occurrence.id}:close")
    fates, loot = {}, {}
    for person in t["delvers"]:
        if not alive(world, person):
            continue
        depth = min(floors, max(1, realm_of(world, person)))
        roll, out = rng.random(), OUT_BASE - OUT_PER_FLOOR * max(0, depth - 2)
        fate = "out" if roll < out else "dead" if roll < out + DEAD_CHANCE else "sealed"
        fates[str(person)] = fate
        if fate == "out" and rng.random() < LOOT_CHANCE:
            loot[str(person)] = SR.prize_at(rng, depth)
    inherited = None
    survivors = [int(p) for p, f in fates.items() if f == "out"]
    if realm.data["inheritance_claimed_by"] is None and survivors:
        best = max(survivors, key=lambda p: (realm_of(world, p), -p))
        margin = realm_of(world, best) - shade_realm(world, best) + 2  # 1: a chance of 0.1 each opening
        if rng.random() < INHERIT_PER_MARGIN * max(0, margin):
            inherited = best
    gate = occurrence.data["place"]
    events = [Event("realm_closed", (), gate, {"occurrence": occurrence.id, "realm": realm.id, "fates": fates,
                                               "loot": loot, "inherited": inherited})]
    events += [Event("died", (int(p), int(p)), gate, {"cause": "realm", "world": True})
               for p, f in fates.items() if f == "dead"]
    return events


def seal(world, person: int, realm: int) -> None:
    """Shut in until the next opening: out of the world, their sect counting them missing (spec §4.4)."""
    world.update_data(person, sealed_in={"realm": realm, "season": lives.current_season(world)})
    world.unrelate(person, "located_in")
    world.relate(person, realm, "located_in")
    for faction, _, data in F.memberships(world, person):
        if data.get("status", "member") == "member":
            set_membership(world, person, faction, status="missing")
    entity = world.entity(realm)
    if person not in entity.data["sealed"]:
        world.update_data(realm, sealed=entity.data["sealed"] + [person])


def inherit(world, person: int, realm: int) -> None:
    """The master's legacy: their art complete, their weapon, and the title of their last disciple."""
    from systems.techniques import teach
    entity = world.entity(realm)
    master = entity.data["master"]
    teach(world, person, master["art"], completeness=1.0, known_completeness=1.0, source="inheritance")
    weapon = world.add_entity("treasure", master["weapon"], {"kind": "weapon", "used": False, "value": WEAPON_VALUE})
    world.relate(person, weapon, "owns")
    titles = list(world.entity(person).data.get("titles", []))
    world.update_data(person, titles=titles + [f"Last Disciple of {master['name']}"])
    world.update_data(realm, inheritance_claimed_by=person, claims=entity.data.get("claims", 0) + 1)


@effect("realm_closed")
def _closed(world, event) -> None:
    from systems.races import make_prize
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "closed": True})
    for person, prize in d["loot"].items():
        make_prize(world, int(person), prize, f"{occurrence.id}:{person}")
    for person, fate in d["fates"].items():
        if fate == "sealed":
            seal(world, int(person), d["realm"])
    if d["inherited"] is not None:
        inherit(world, d["inherited"], d["realm"])
    realm = world.entity(d["realm"])
    fates = list(d["fates"].values())
    line = {"season": lives.current_season(world), "entered": len(t["delvers"]), "died": fates.count("dead"),
            "sealed": fates.count("sealed"), "took": len(d["loot"]), "inherited": d["inherited"]}
    world.update_data(realm.id, history=realm.data["history"] + [line])


@listen("realm_closed")
def _closed_news(world, event, event_id: int) -> None:
    """Only those who came out can tell it (spec §5)."""
    d = event.data
    realm = world.entity(d["realm"])
    where = place_name(world, event.place)
    for person, fate in d["fates"].items():
        p = int(person)
        if fate == "out":
            variant = make_variant("delved", p, None, place=where)
            variant["realm_name"] = realm.name
            record_fact(world, p, "delved", None, place=event.place, source_event=event_id, weight=1.0,
                        variant=variant)
        elif fate == "sealed":
            variant = make_variant("sealed", p, None, place=where)
            variant["realm_name"] = realm.name
            record_fact(world, p, "sealed", None, place=event.place, source_event=event_id, weight=1.5,
                        variant=variant)
    for person, prize in d["loot"].items():
        variant = make_variant("took", int(person), None, place=where)
        variant.update(realm_name=realm.name, prize=prize["kind"])
        record_fact(world, int(person), "took", None, place=event.place, source_event=event_id, weight=1.0,
                    variant=variant)
    if d["inherited"] is not None:
        variant = make_variant("inherited", d["inherited"], None, place=where)
        variant.update(realm_name=realm.name, master=realm.data["master"]["name"])
        record_fact(world, d["inherited"], "inherited", None, place=event.place, source_event=event_id, weight=3.0,
                    variant=variant)


def stage_events(world, occurrence, stage: str) -> list[Event]:
    if stage == "announced":
        return token_events(world, occurrence)
    if stage == "active":
        return walk_out_events(world, occurrence) + delver_events(world, occurrence)
    if stage == "aftermath":
        player = world.get_meta("player_id")
        if player not in occurrence.data["data"]["entered"]:
            return closing_events(world, occurrence)
    return []
```

- [ ] **Step 4: Write the words** — `narrate/realm_text.py`
```python
"""What the player is told about secret realms (phase 4f)."""

from narrate.outcomes import cap  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who


def _delved_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} went into {variant.get('realm_name') or 'a secret realm'} "
               f"and came out alive.")


def _took_story(world, variant, viewer) -> str:
    what = {"manual": "a martial manual", "pill": "a precious pill", "herb": "a spirit herb",
            "star_iron": "star iron"}.get(variant.get("prize"), "a treasure")
    return cap(f"{who(world, variant.get('actor'), viewer)} came out of {variant.get('realm_name') or 'a secret realm'} "
               f"with {what}.")


def _inherited_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} won the inheritance of {variant.get('master') or 'an ancient master'} "
               f"in {variant.get('realm_name') or 'a secret realm'}.")


def _sealed_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} did not come out of {variant.get('realm_name') or 'a secret realm'} "
               f"before the gate closed.")


SPECIAL_PHRASES.update({"delved": _delved_story, "took": _took_story, "inherited": _inherited_story,
                        "sealed": _sealed_story})
```

- [ ] **Step 5: Edit the existing files** — `.patches/4f_task2.py`
```python
"""Task 2 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("systems/secret_realms.py", '''def on_stage(world, occurrence, stage: str) -> list[Event]:
    return []''', '''def on_stage(world, occurrence, stage: str) -> list[Event]:
    from systems.realm_gates import stage_events
    return stage_events(world, occurrence, stage)''')
edit("systems/lives.py", '''    return entity.kind == "person" and not d.get("is_player") and not d.get("dead") and not d.get("beast")''',
     '''    return entity.kind == "person" and not d.get("is_player") and not d.get("dead") and not d.get("beast") \\
        and not d.get("sealed_in")  # a secret realm's sealed live when they walk out (4f spec 4.4)''')
edit("narrate/outcomes.py", '''import narrate.tournament_text  # noqa: E402,F401
''', '''import narrate.tournament_text  # noqa: E402,F401
import narrate.realm_text  # noqa: E402,F401
''')

INV = "debug/invariants.py"
edit(INV, '''    problems += check_tournaments(world)
''', '''    problems += check_tournaments(world)
    problems += check_realms(world)
''')
Path(INV).write_text(Path(INV).read_text(encoding="utf-8") + '''

def check_realms(world) -> list[str]:
    """Phase 4f spec 7, rules 1, 2 and 4: one inheritance, no one inside who should not be, the ceiling holds."""
    import systems.realm_gates as G
    import systems.secret_realms as SR
    import systems.tournaments as T
    import systems.world_events as W
    out = []
    realms = world.get_meta("secret_realms") or []
    live = {}  # realm -> its live opening, from one pass over the sky index
    for row in W.index(world):
        if row[W.TYPE] in SR.OPENINGS and not row[W.DONE]:
            occurrence = world.entity(row[W.ID])
            live[occurrence.data["data"]["realm"]] = occurrence
    for realm in realms:
        entity = world.entity(realm)
        claims = entity.data.get("claims", 0)
        if claims > 1 or (claims == 1) != (entity.data["inheritance_claimed_by"] is not None):
            out.append(f"{entity.name}'s inheritance was claimed {claims} times")
        inside = world.sources(realm, "located_in")
        if not inside:
            continue
        occurrence = live.get(realm)
        t = occurrence.data["data"] if occurrence is not None else {}
        open_ = occurrence is not None and W.stage_at(occurrence.data, world.time) == "active"
        cap = G.ceiling_of(world, realm)
        for person in inside:
            p = world.entity(person)
            if p is None or p.kind != "person" or p.data.get("realm_spirit"):
                continue
            sealed = person in entity.data["sealed"]
            if not sealed and person not in t.get("entered", []):  # entered this opening: sealed when it closes
                out.append(f"{p.name} (#{person}) is inside {entity.name} but neither entered it nor is sealed there")
            if not sealed and open_ and cap is not None and T.realm_of(world, person) > cap:
                out.append(f"{p.name} (#{person}) is inside {entity.name} above its ceiling")
    return out
''', encoding="utf-8", newline="\n")
print("task 2 edits applied")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4f_task2.py && .venv/Scripts/python.exe -m pytest tests/test_realm_gates.py -q -p no:cacheprovider`
Expected: `task 2 edits applied`, then `10 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 7: Commit**

Run: `git add -A && git commit -m "feat: the realm gate - ceilings, jade tokens and quotas, the sects' delvers, closings far away settled in a line, the sealed and their walking out"`

---
### Task 3: The delve: entering, moving, treasure, and the engine's delve mode

**Files:**
- Create: `systems/delve.py`, `engine/delve.py`, `narrate/grammar/realm.toml`
- Modify (via `.patches/4f_task3.py`):
  - `engine/game.py`: `DelveMixin` joins the `Game` bases; a look asks `_special_look` first; a step and a rest stay out of the journal;
  - `engine/hooks.py`: the `_special_look` hook;
  - `narrate/brief.py`: an event inside a realm is set in its gate's land (every event's brief names a town);
  - `world/gen/materialize.py`: `region_of` a realm is its gate's region (kin, rumours and briefs ask it of any place);
  - `engine/commands.py`: `enter`, `deeper`, `up`, `leave realm`;
  - `systems/reputation.py`: a `trespassed` deed counts against you with the righteous;
  - `debug/invariants.py`: `check_realms` checks the player's delve position (spec §7 rule 5);
  - `narrate/realm_text.py`: outcomes and journal lines.
- Test: `tests/test_delve.py`

**Interfaces:**
- Consumes:
  - Task 1: `SR.ensure_realms`, `SR.opening_of`, `SR.stage_of`, `SR.opening_data`;
  - Task 2: `G.admits`, `G.tokens_of`, `G.near_sects`;
  - `T.sponsor_of` (4e), `races.make_prize`, `time.advance`, `world.body.max_qi`, `sky.observe`.
- Produces:
  - **`systems.delve` (D):**
    - constants: `STEP = 2`, `STAIR = 1`, `REST = 1` (watches), `SNEAK_BASE = 0.2`, `SNEAK_PER_AGILITY = 0.03`, `SNEAK_BOUNDS = (0.05, 0.6)`, `BLOCKING = {"guardian", "rivals"}`;
    - `position(world, person) -> dict | None`, `here(world, person) -> tuple[Entity, int, int, dict] | None` (realm, floor, chamber, the chamber's dict);
    - `set_chamber(world, realm, floor, chamber, **changes)`;
    - `gate_open(world, realm) -> int | None` (the opening if its gate stands open now), `days_left(world, occurrence) -> int`, `realms_at(world, town) -> list[int]`;
    - `entry(world, realm, player) -> tuple[str | None, str]`: the refusal or None, and how the player would pass (`rule`, `token`, `sponsor` or `sneak`);
    - `enter_events`, `sneak_events`, `move_events(world, player, where)` (`where` in `on`, `back`), `moves(world, player) -> dict[str, bool]`, `leave_events`, `take_events`, `rest_events`;
    - `TOKEN_PRICE = 3`, `token_offer(world, holder, player) -> int | None`, `buy_events(world, player, holder)`.
  - **Events:**
    - `realm_entered` (`realm`, `occurrence`, `how`);
    - `sneak_caught` (`realm`);
    - `delve_moved` (`realm`, `floor`, `chamber`, `watches`);
    - `realm_left` (`realm`, `occurrence`);
    - `chamber_looted` (`realm`, `floor`, `chamber`, `prize`);
    - `delve_rested`;
    - `token_bought` (`token`, `silver`).
  - **Player data:** `delve` = `{"realm", "floor", "chamber"}` (floor from 1, chamber from 0).
  - **`engine.delve.DelveMixin`:**
    - `_chamber_choices(realm, floor, chamber, room) -> list[Choice]`, which later tasks extend;
    - `_delve_lines() -> list[Line]`;
    - `INSIDE_VERBS`, the verbs allowed inside.
  - **Verbs:** `enter_realm`, `sneak_realm`, `delve_on`, `delve_back`, `leave_realm`, `take_treasure`, `delve_rest`, `buy_token`.
  - **Fact:** `trespassed` (a caught sneak).

- [ ] **Step 1: Write the failing test** — `tests/test_delve.py`
```python
import pytest

import systems.delve as D
import systems.encounters as encounters
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_realms
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
from world.events import commit


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
    monkeypatch.setattr(G, "near_sects", lambda world, gate: [])  # an empty realm: no rival bands (Task 5 has those)
    monkeypatch.setattr(G, "WANDERER_CHANCE", 0.0)


def room(kind, **contents):
    return {"kind": kind, "state": "untouched", "contents": contents}


def open_realm(game, rule=("open", None), floors=None):
    """The first ancient realm with its gate in the player's town, standing open now."""
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    changes = {"gate": town, "rule": {"kind": rule[0], "value": rule[1]}}
    if floors is not None:
        changes["floors"] = floors
    world.update_data(realm, **changes)
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    sky.observe(world, town)
    return realm, occurrence


def actions(turn):
    return [c.action for c in turn.all_choices]


def texts(turn):
    return [t for t, _ in turn.lines]


def test_you_enter_at_the_gate_while_it_stands_open(game):
    world, me = game.world, game.player.id
    realm, occurrence = open_realm(game)
    assert Action("enter_realm", realm) in actions(game.perform(Action("look")))
    turn = game.perform(Action("enter_realm", realm))
    assert world.targets(me, "located_in") == [realm] and D.position(world, me) == {"realm": realm, "floor": 1, "chamber": 0}
    assert me in world.entity(occurrence).data["data"]["entered"]
    header = texts(game.perform(Action("look")))[0]
    assert world.entity(realm).name.lower() in header.lower() and "floor 1 of" in header and "the gate closes in" in header
    assert check_realms(world) == []


def test_the_gate_explains_what_its_rule_refuses(game):
    world, me = game.world, game.player.id
    realm, _ = open_realm(game, ("token", None))
    turn = game.perform(Action("enter_realm", realm))
    assert any("jade token" in t for t in texts(turn)) and world.targets(me, "located_in") != [realm]


def test_a_token_is_spent_to_enter(game):
    world, me = game.world, game.player.id
    realm, _ = open_realm(game, ("token", None))
    token = world.add_entity("treasure", "a jade token", {"kind": "token", "realm": realm, "used": False, "value": 120})
    world.relate(me, token, "owns")
    game.perform(Action("enter_realm", realm))
    assert world.targets(me, "located_in") == [realm]
    assert world.entity(token).data["used"] and not world.sources(token, "owns")


def test_a_token_can_be_bought_from_its_holder(game):
    from systems import founding
    from systems.purse import silver_of
    world, me, town = game.world, game.player.id, game.place.id
    realm, _ = open_realm(game, ("token", None))
    holder = founding.make_person(world, "test:holder", town, occupation="wandering swordsman", age=30)
    token = world.add_entity("treasure", "a jade token", {"kind": "token", "realm": realm, "used": False, "value": 120})
    world.relate(holder, token, "owns")
    world.update_data(me, silver=500)
    turn = game.perform(Action("talk", holder))
    assert Action("buy_token", holder) in actions(turn)
    game.perform(Action("buy_token", holder))
    assert world.sources(token, "owns") == [me] and silver_of(world, me) == 500 - D.TOKEN_PRICE * 120
    game.perform(Action("farewell"))
    game.perform(Action("enter_realm", realm))
    assert world.targets(me, "located_in") == [realm]


def test_a_quota_realm_lets_the_unsponsored_try_to_slip_in(game, monkeypatch):
    world, me = game.world, game.player.id
    realm, _ = open_realm(game, ("quota", None))
    monkeypatch.setattr("systems.tournaments.sponsor_of", lambda world, player: None)
    assert Action("sneak_realm", realm) in actions(game.perform(Action("look")))
    monkeypatch.setattr(D, "SNEAK_BOUNDS", (0.0, 0.0))
    game.perform(Action("sneak_realm", realm))
    assert world.targets(me, "located_in") != [realm]
    assert [f for f in world.facts(predicate="trespassed") if f.subject == me]
    monkeypatch.setattr(D, "SNEAK_BOUNDS", (1.0, 1.0))
    game.perform(Action("sneak_realm", realm))
    assert world.targets(me, "located_in") == [realm]


def test_moving_on_costs_time_and_a_guardian_bars_the_way(game):
    world, me = game.world, game.player.id
    floors = [[room("treasure", prize={"kind": "herb", "name": "a blood lotus", "value": 300}),
               room("guardian", species="stone lion", realm=2, guardian=None), room("stair")],
              [room("inheritance")]]
    realm, _ = open_realm(game, floors=floors)
    game.perform(Action("enter_realm", realm))
    before = world.time
    turn = game.perform(Action("take_treasure"))
    herb = [i for i in world.targets(me, "owns") if world.entity(i).name == "a blood lotus"]
    assert herb and world.time == before + D.STEP and world.entity(realm).data["floors"][0][0]["state"] == "looted"
    game.perform(Action("delve_on"))
    assert D.position(world, me)["chamber"] == 1
    found = actions(game.perform(Action("look")))
    assert Action("delve_on") not in found and Action("delve_back") in found  # the lion bars the way on


def test_stairs_lead_down_and_up_and_you_leave_only_from_the_first_floor(game):
    world, me, town = game.world, game.player.id, game.place.id
    realm, _ = open_realm(game, floors=[[room("stair")], [room("trial", trial="formation"), room("stair")],
                                        [room("inheritance")]])
    game.perform(Action("enter_realm", realm))
    assert Action("leave_realm") in actions(game.perform(Action("look")))
    game.perform(Action("delve_on"))  # the stair down
    assert D.position(world, me) == {"realm": realm, "floor": 2, "chamber": 0}
    assert Action("leave_realm") not in actions(game.perform(Action("look")))
    game.perform(Action("delve_back"))  # back up to the stair on floor 1
    assert D.position(world, me) == {"realm": realm, "floor": 1, "chamber": 0}
    game.perform(Action("leave_realm"))
    assert world.targets(me, "located_in") == [town] and D.position(world, me) is None
    assert [f for f in world.facts(predicate="delved") if f.subject == me]


def test_inside_only_the_delve_and_its_pages_answer(game):
    world = game.world
    realm, _ = open_realm(game)
    game.perform(Action("enter_realm", realm))
    turn = game.perform(Action("market"))
    assert any("inside" in t for t in texts(turn))
    assert any("Last Disciple" not in t for t in texts(game.perform(Action("journal"))))


def test_the_rules_check_your_delve_position(game):
    world, me = game.world, game.player.id
    realm, _ = open_realm(game)
    game.perform(Action("enter_realm", realm))
    world.update_data(me, delve={"realm": realm, "floor": 9, "chamber": 0})
    assert any("delve" in p for p in check_realms(world))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_delve.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.delve'`.

- [ ] **Step 3: Write the delve** — `systems/delve.py`
```python
"""The delve (phase 4f spec 3): the player's steps through a secret realm, chamber by chamber.

The player's place inside is `delve = {"realm", "floor", "chamber"}` (floors from 1, chambers from 0);
they are `located_in` the realm itself. A floor's chambers lie in a line ending at its stair (or,
on the last floor, the inheritance). A guardian or a band of rivals bars the way on until dealt
with; everything else may be left behind. One leaves only from the first floor.
"""

import systems.realm_gates as G
import systems.secret_realms as SR
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.time import advance
from world.body import max_qi
from world.events import Event, effect, listen
from world.seed import rng_for

STEP, STAIR, REST = 2, 1, 1  # watches
SNEAK_BASE, SNEAK_PER_AGILITY, SNEAK_BOUNDS = 0.2, 0.03, (0.05, 0.6)
BLOCKING = frozenset({"guardian", "rivals"})


# --- where the player is -------------------------------------------------------------------------

def position(world, person: int) -> dict | None:
    return world.entity(person).data.get("delve")


def here(world, person: int):
    """(realm entity, floor, chamber index, the chamber) for someone inside, or None."""
    pos = position(world, person)
    if not pos:
        return None
    realm = world.entity(pos["realm"])
    return realm, pos["floor"], pos["chamber"], realm.data["floors"][pos["floor"] - 1][pos["chamber"]]


def set_chamber(world, realm: int, floor: int, chamber: int, **changes) -> None:
    floors = [list(f) for f in world.entity(realm).data["floors"]]
    floors[floor - 1][chamber] = {**floors[floor - 1][chamber], **changes}
    world.update_data(realm, floors=floors)


def gate_open(world, realm: int) -> int | None:
    occurrence = SR.opening_of(world, realm)
    return occurrence if occurrence is not None and SR.stage_of(world, occurrence) == "active" else None


def days_left(world, occurrence: int) -> int:
    return max(0, (world.entity(occurrence).data["active"][1] - world.time + 3) // 4)


def realms_at(world, town: int) -> list[int]:
    """Realms whose gate stands open in this town now."""
    return [r for r in SR.realms(world) if world.entity(r).data["gate"] == town and gate_open(world, r)]


# --- entering and leaving ----------------------------------------------------------------------------

def entry(world, realm: int, player: int) -> tuple[str | None, str]:
    """(why the gate refuses, or None; and how the player would pass: rule, token, sponsor or sneak)."""
    from systems.tournaments import sponsor_of
    if gate_open(world, realm) is None:
        return "The gate is shut.", ""
    if world.entity(realm).data["gate"] not in world.targets(player, "located_in"):
        return "The gate is not here.", ""
    rule = world.entity(realm).data["rule"]["kind"]
    why = G.admits(world, realm, player)
    if why is None:
        return None, "token" if rule == "token" else "rule"
    if rule == "quota" and G.ceiling_of(world, realm) is None:
        if sponsor_of(world, player) is not None:
            return None, "sponsor"  # a sect that welcomes you lends you a place (4e sponsor)
        return why, "sneak"
    return why, ""


def enter_events(world, realm: int, player: int, how: str) -> list[Event]:
    return [Event("realm_entered", (player,), world.entity(realm).data["gate"],
                  {"realm": realm, "occurrence": gate_open(world, realm), "how": how})]


def sneak_events(world, realm: int, player: int) -> list[Event]:
    """Past the sects' guards: a chance from agility (spec §4.1); caught, the sects hear of it."""
    agility = load_body(world, player).physique["agility"]
    low, high = SNEAK_BOUNDS
    chance = min(high, max(low, SNEAK_BASE + SNEAK_PER_AGILITY * (agility - 10)))
    occurrence = gate_open(world, realm)
    if rng_for(world.world_seed, f"sneak:{occurrence}:{player}:{world.time}").random() < chance:
        return enter_events(world, realm, player, "sneak")
    return [Event("sneak_caught", (player,), world.entity(realm).data["gate"], {"realm": realm})]


@effect("realm_entered")
def _entered(world, event) -> None:
    player, d = event.actors[0], event.data
    if d["how"] == "token":
        token = G.tokens_of(world, player, d["realm"])[0]
        world.unrelate(player, "owns", token)
        world.update_data(token, used=True)
    world.unrelate(player, "located_in")
    world.relate(player, d["realm"], "located_in")
    world.update_data(player, delve={"realm": d["realm"], "floor": 1, "chamber": 0})
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "entered": t["entered"] + [player]})


@listen("sneak_caught")
def _caught(world, event, event_id: int) -> None:
    player = event.actors[0]
    variant = make_variant("trespassed", player, None, place=place_name(world, event.place))
    variant["realm_name"] = world.entity(event.data["realm"]).name
    record_fact(world, player, "trespassed", None, place=event.place, source_event=event_id, weight=1.0,
                variant=variant)


def leave_events(world, player: int) -> list[Event]:
    pos = position(world, player)
    if not pos or pos["floor"] != 1:
        return []
    realm = pos["realm"]
    return [Event("realm_left", (player,), world.entity(realm).data["gate"],
                  {"realm": realm, "occurrence": SR.opening_of(world, realm)})]


@effect("realm_left")
def _left(world, event) -> None:
    player = event.actors[0]
    world.unrelate(player, "located_in")
    world.relate(player, event.place, "located_in")
    world.update_data(player, delve=None)


@listen("realm_left")
def _came_out(world, event, event_id: int) -> None:
    player = event.actors[0]
    variant = make_variant("delved", player, None, place=place_name(world, event.place))
    variant["realm_name"] = world.entity(event.data["realm"]).name
    record_fact(world, player, "delved", None, place=event.place, source_event=event_id, weight=1.0, variant=variant)


# --- moving ------------------------------------------------------------------------------------------

def moves(world, player: int) -> dict[str, bool]:
    found = here(world, player)
    if found is None:
        return {}
    realm, floor, c, room = found
    floors = realm.data["floors"]
    last = c == len(floors[floor - 1]) - 1
    barred = room["kind"] in BLOCKING and room["state"] == "untouched"
    return {"on": not barred and (not last or (room["kind"] == "stair" and floor < len(floors))),
            "back": c > 0 or floor > 1,
            "leave": floor == 1}


def move_events(world, player: int, where: str) -> list[Event]:
    if not moves(world, player).get(where):
        return []
    realm, floor, c, room = here(world, player)
    floors = realm.data["floors"]
    if where == "on" and room["kind"] == "stair" and c == len(floors[floor - 1]) - 1:
        target, watches = (floor + 1, 0), STAIR
    elif where == "on":
        target, watches = (floor, c + 1), STEP
    elif c > 0:
        target, watches = (floor, c - 1), STEP
    else:
        target, watches = (floor - 1, len(floors[floor - 2]) - 1), STAIR  # back up the stair you came down
    return [Event("delve_moved", (player,), realm.id,
                  {"realm": realm.id, "floor": target[0], "chamber": target[1], "watches": watches})]


@effect("delve_moved")
def _moved(world, event) -> None:
    d = event.data
    world.update_data(event.actors[0], delve={"realm": d["realm"], "floor": d["floor"], "chamber": d["chamber"]})
    advance(world, d["watches"])


# --- treasure and rest ------------------------------------------------------------------------------

def take_events(world, player: int) -> list[Event]:
    found = here(world, player)
    if found is None:
        return []
    realm, floor, c, room = found
    if room["kind"] != "treasure" or room["state"] != "untouched":
        return []
    return [Event("chamber_looted", (player,), realm.id,
                  {"realm": realm.id, "floor": floor, "chamber": c, "prize": room["contents"]["prize"]})]


@effect("chamber_looted")
def _looted(world, event) -> None:
    from systems.races import make_prize
    d = event.data
    make_prize(world, event.actors[0], d["prize"], f"realm:{d['realm']}:{d['floor']}:{d['chamber']}:{world.time}")
    set_chamber(world, d["realm"], d["floor"], d["chamber"], state="looted")
    advance(world, STEP)


@listen("chamber_looted")
def _took(world, event, event_id: int) -> None:
    """Known to whoever was there; it leaves the realm only with a survivor (spec §5)."""
    player, d = event.actors[0], event.data
    variant = make_variant("took", player, None, place=world.entity(d["realm"]).name)
    variant.update(realm_name=world.entity(d["realm"]).name, prize=d["prize"]["kind"])
    record_fact(world, player, "took", None, place=d["realm"], source_event=event_id, weight=1.0, variant=variant)


TOKEN_PRICE = 3  # times a token's value: its holder gives up a place inside


def token_offer(world, holder: int, player: int) -> int | None:
    """A jade token this person holds and would part with (spec §4.1: tokens are bought, stolen or robbed)."""
    if holder == player:
        return None
    for item in world.targets(holder, "owns"):
        entity = world.entity(item)
        if entity is not None and entity.kind == "treasure" and entity.data.get("kind") == "token" \
                and not entity.data.get("used"):
            return item
    return None


def buy_events(world, player: int, holder: int) -> list[Event]:
    from systems.purse import silver_of
    token = token_offer(world, holder, player)
    if token is None:
        return []
    price = TOKEN_PRICE * world.entity(token).data["value"]
    if silver_of(world, player) < price:
        return []
    place = world.targets(player, "located_in")[0]
    return [Event("token_bought", (player, holder), place, {"token": token, "silver": price})]


@effect("token_bought")
def _bought(world, event) -> None:
    from systems.purse import silver_of
    player, holder = event.actors
    d = event.data
    world.unrelate(holder, "owns", d["token"])
    world.relate(player, d["token"], "owns")
    world.update_data(player, silver=silver_of(world, player) - d["silver"])
    world.update_data(holder, silver=silver_of(world, holder) + d["silver"])


def rest_events(world, player: int) -> list[Event]:
    pos = position(world, player)
    return [Event("delve_rested", (player,), pos["realm"], {})] if pos else []


@effect("delve_rested")
def _rested(world, event) -> None:
    body = load_body(world, event.actors[0])
    body.qi = min(max_qi(body), body.qi + 0.1 * max_qi(body))
    save_body(world, event.actors[0], body)
    advance(world, REST)
```

- [ ] **Step 4: Write the engine's delve mode** — `engine/delve.py`
```python
"""The delve in the engine (phase 4f spec 3, 6): the gate's choices outside, and inside, a menu of the chamber."""

import systems.delve as D
import systems.sky as sky
from engine.actions import Action, Choice
from narrate.realm_text import chamber_line
from systems.realms import realm_title
from systems.time import format_date
from world.gen.materialize import people_at

INSIDE_VERBS = frozenset({
    "look", "journal", "help", "unknown", "ambiguous", "buy_token", "back", "more_menu", "people", "talk", "farewell", "ask",
    "ask_about", "news", "rumours", "tell_menu", "standing", "ledger", "lineage", "rankings", "tournaments", "realms",
    "intent", "flee", "yield_duel", "verdict", "use_menu", "use", "challenge", "spar",
    "delve_on", "delve_back", "leave_realm", "take_treasure", "delve_rest",
})


class DelveMixin:
    def _inside(self) -> dict | None:
        return D.position(self.world, self.player.id)

    # --- outside: the gate ---------------------------------------------------------------------
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me = self.world, self.player.id
        if self._inside():
            return extras
        for realm in D.realms_at(world, self.place.id):
            name = world.entity(realm).name
            days = D.days_left(world, D.gate_open(world, realm))
            why, how = D.entry(world, realm, me)
            extras.append(Choice(f"Enter {name} (the gate closes in {days} days)", Action("enter_realm", realm)))
            if why and how == "sneak":
                extras.append(Choice(f"Slip into {name} past the sects' guards", Action("sneak_realm", realm)))
        return extras

    def _do_enter_realm(self, realm):
        if realm is None:  # typed: the realm whose gate stands open here
            realm = next(iter(D.realms_at(self.world, self.place.id)), None)
        if realm is None:
            return self._turn([("No gate stands open here.", "system")])
        why, how = D.entry(self.world, realm, self.player.id)
        if why:
            return self._turn([(why, "system")])
        self._commit(D.enter_events(self.world, realm, self.player.id, how))
        return self._do_look(None)

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        token = D.token_offer(self.world, npc.id, self.player.id)
        if token is not None:
            price = D.TOKEN_PRICE * self.world.entity(token).data["value"]
            extras.append(Choice(f"Buy their jade token ({price} silver)", Action("buy_token", npc.id)))
        return extras

    def _do_buy_token(self, holder):
        events = D.buy_events(self.world, self.player.id, holder) if isinstance(holder, int) else []
        if not events:
            return self._turn([("You cannot buy that token.", "system")])
        return self._turn(self._commit(events))

    def _do_sneak_realm(self, realm):
        why, how = D.entry(self.world, realm, self.player.id) if isinstance(realm, int) else ("", "")
        if how != "sneak":
            return self._turn([("There is no slipping past anyone here.", "system")])
        lines = self._commit(D.sneak_events(self.world, realm, self.player.id))
        return self._do_look(None) if self._inside() else self._turn(lines)

    # --- inside ----------------------------------------------------------------------------------
    def _gate(self, action):
        if self._inside() and self.combat is None and action.verb not in INSIDE_VERBS:
            realm = self.world.entity(self._inside()["realm"])
            return self._turn([(f"You are inside {realm.name}; that must wait until you are out.", "system")])
        return super()._gate(action)

    def _before_scene(self) -> None:
        super()._before_scene()
        pos = self._inside()
        if pos:  # the gate's clock runs in the world outside
            sky.observe(self.world, self.world.entity(pos["realm"]).data["gate"])

    def _delve_lines(self) -> list:
        found = D.here(self.world, self.player.id)
        realm, floor, c, room = found
        floors = realm.data["floors"]
        occurrence = D.gate_open(self.world, realm.id)
        gate = f"the gate closes in {D.days_left(self.world, occurrence)} days" if occurrence else "the gate is shut"
        lines = [(f"{realm.name[0].upper()}{realm.name[1:]}, floor {floor} of {len(floors)}, "
                  f"chamber {c + 1} of {len(floors[floor - 1])} ({gate})", "heading"),
                 (chamber_line(self.world, realm, floor, c, room), "dim")]  # shown after every step: status, not prose
        others = [p.name for p in people_at(self.world, realm.id, exclude=self.player.id)
                  if (p.data.get("delve_at") or [None])[:2] == [floor, c]]  # placed by Task 5
        if others:
            lines.append(("Here: " + ", ".join(others) + ".", "dim"))
        return lines

    def _special_look(self):
        if not self._inside():  # outside, or the gate closed on the scene (Task 6)
            return super()._special_look()
        return self._delve_lines()

    def _chamber_choices(self, realm, floor: int, c: int, room: dict) -> list:
        if room["kind"] == "treasure" and room["state"] == "untouched":
            return [Choice(f"Take {chamber_prize(room)}", Action("take_treasure"))]
        return []

    def _special_choices(self):
        pos = self._inside()
        if not pos or self.combat is not None or self.encounter is not None or self.challenger is not None \
                or self.focus is not None or self.player.data.get("dying"):
            return super()._special_choices()
        realm, floor, c, room = D.here(self.world, self.player.id)
        choices = self._chamber_choices(realm, floor, c, room)
        can = D.moves(self.world, self.player.id)
        floors = realm.data["floors"]
        if can.get("on"):
            down = room["kind"] == "stair" and c == len(floors[floor - 1]) - 1
            choices.append(Choice("Take the stair down" if down else "Go on to the next chamber", Action("delve_on")))
        if can.get("back"):
            choices.append(Choice("Go back" if c > 0 else "Climb back up the stair", Action("delve_back")))
        if can.get("leave"):
            choices.append(Choice("Leave the realm", Action("leave_realm")))
        choices.append(Choice("Catch your breath (a watch)", Action("delve_rest")))
        choices += [Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]
        return choices[:9], choices[9:]

    def _special_status(self):
        pos = self._inside()
        if not pos:
            return super()._special_status()
        realm = self.world.entity(pos["realm"])
        return f"{self.player.name} | {realm_title(self.body())} | {format_date(self.world.time)} | {realm.name}, floor {pos['floor']}"

    def _special_art(self):
        pos = self._inside()
        if not pos or self.focus is not None:
            return super()._special_art()
        gate = self.world.entity(self.world.entity(pos["realm"]).data["gate"])
        return {"type": "scene", "terrain": gate.data["terrain"], "settlement": gate.data["kind"],
                "watch": self.world.time % 4, "hall": None}

    def _step(self, events: list, refusal: str):
        if not events:
            return self._turn([(refusal, "system")])
        lines = self._commit(events)
        return self._turn(lines + (self._delve_lines() if self._inside() else []))

    def _do_delve_on(self, _target):
        return self._step(D.move_events(self.world, self.player.id, "on"), "The way on is barred.")

    def _do_delve_back(self, _target):
        return self._step(D.move_events(self.world, self.player.id, "back"), "There is no way back from here.")

    def _do_take_treasure(self, _target):
        return self._step(D.take_events(self.world, self.player.id), "There is nothing here to take.")

    def _do_delve_rest(self, _target):
        return self._step(D.rest_events(self.world, self.player.id), "You are not inside a realm.")

    def _do_leave_realm(self, _target):
        events = D.leave_events(self.world, self.player.id)
        if not events:
            return self._turn([("You can only leave from the first floor.", "system")])
        self._commit(events)
        return self._do_look(None)


def chamber_prize(room: dict) -> str:
    prize = room["contents"]["prize"]
    return prize.get("name") or {"manual": "a martial manual", "star_iron": "a lump of star iron"}.get(prize["kind"], "the treasure")
```

- [ ] **Step 5: Write the words** — `narrate/grammar/realm.toml`
```toml
[symbols]
realm_air = ["The air is thick with old qi.", "Dust hangs in the lamplight of no lamp.", "Somewhere water drips on stone.", "The walls are carved with forms no one has practised in a thousand years.", "Your breath comes slow in the dense air.", "Far off, something vast shifts in its sleep."]

[realm_entered]
colour = "default"
lines = ["#realm_air#", "#realm_air# #realm_air#"]

[sneak_caught]
colour = "default"
lines = ["#realm_air#"]

[delve_moved]
colour = "dim"
lines = ["#realm_air#"]

[realm_left]
colour = "default"
lines = ["#realm_air#"]

[chamber_looted]
colour = "gold"
lines = ["#realm_air#"]

[delve_rested]
colour = "dim"
lines = ["#realm_air#"]

[token_bought]
colour = "default"
lines = ["#realm_air#"]
```

- [ ] **Step 6: Edit the existing files** — `.patches/4f_task3.py`
```python
"""Task 3 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    Path(path).write_text(Path(path).read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


edit("world/gen/materialize.py", '''def region_of(world: World, town_id: int) -> Entity:
    return world.entity(world.targets(town_id, "located_in")[0])''', '''def region_of(world: World, town_id: int) -> Entity:
    place = world.entity(town_id)
    if place is not None and place.kind == "secret_realm":  # inside a realm: its gate's region (4f)
        town_id = place.data["gate"]
    return world.entity(world.targets(town_id, "located_in")[0])''')
edit("narrate/brief.py", '''def _place(world: World, place_id: int) -> PlaceBrief:
    town = world.entity(place_id)
    return PlaceBrief(
        town.name, town.data["kind"], region_of(world, town.id).name, town.data["terrain"],
        season_of(world.time), WATCH_NAMES[world.time % 4],
    )''', '''def _place(world: World, place_id: int) -> PlaceBrief:
    place = world.entity(place_id)
    town = world.entity(place.data["gate"]) if place.kind == "secret_realm" else place  # inside: the gate's land (4f)
    return PlaceBrief(
        place.name, town.data["kind"], region_of(world, town.id).name, town.data["terrain"],
        season_of(world.time), WATCH_NAMES[world.time % 4],
    )''')

GAME = "engine/game.py"
edit(GAME, '''        self.focus = None
        self._before_scene()
        here = (self.place.id, self.world.time)''', '''        self.focus = None
        self._before_scene()
        special = self._special_look()  # a scene of another kind: inside a secret realm (4f)
        if special is not None:
            return self._turn(special)
        here = (self.place.id, self.world.time)''')
edit("engine/hooks.py", '''    def _special_art(self):
        return None''', '''    def _special_art(self):
        return None

    def _special_look(self):
        """Lines that replace the town scene on a look (inside a secret realm), or None."""
        return None''')
edit(GAME, '''QUIET_KINDS = frozenset({"exchange", "player_aged"})''',
     '''QUIET_KINDS = frozenset({"exchange", "player_aged", "delve_moved", "delve_rested"})''')
edit(GAME, '''class Game(LineageMixin,''', '''class Game(DelveMixin, LineageMixin,''')
edit(GAME, '''from engine.actions import''', '''from engine.delve import DelveMixin
from engine.actions import''')

edit("engine/commands.py", '''    "rankings": Action("rankings"), "lists": Action("rankings"),
''', '''    "rankings": Action("rankings"), "lists": Action("rankings"),
    "enter": Action("enter_realm"), "enter realm": Action("enter_realm"), "deeper": Action("delve_on"),
    "on": Action("delve_on"), "up": Action("delve_back"), "leave realm": Action("leave_realm"),
''')

edit("systems/reputation.py", '''"paid_off": -0.1, "left_for_dead": -0.8, "owns_manual": 0.0, "seized": -0.8}''',
     '''"paid_off": -0.1, "left_for_dead": -0.8, "owns_manual": 0.0, "seized": -0.8,
              "trespassed": -0.5}  # 4f: caught slipping past the sects' guards at a realm's gate''')

edit("debug/invariants.py", '''            if not sealed and open_ and cap is not None and T.realm_of(world, person) > cap:
                out.append(f"{p.name} (#{person}) is inside {entity.name} above its ceiling")
    return out''', '''            if not sealed and open_ and cap is not None and T.realm_of(world, person) > cap:
                out.append(f"{p.name} (#{person}) is inside {entity.name} above its ceiling")
    player = world.get_meta("player_id")
    if player is not None and world.entity(player) is not None:
        pos = world.entity(player).data.get("delve")
        inside = [r for r in world.targets(player, "located_in") if r in realms]
        if pos is None and inside and player not in world.entity(inside[0]).data["sealed"]:
            out.append("the player is inside a realm with no delve position")
        if pos is not None:
            floors = world.entity(pos["realm"]).data["floors"] if pos["realm"] in realms else []
            if inside != [pos["realm"]] or not 1 <= pos["floor"] <= len(floors) \\
                    or not 0 <= pos["chamber"] < len(floors[pos["floor"] - 1]):
                out.append(f"the player's delve position {pos} does not fit the realm they are in")
    return out''')

append("narrate/realm_text.py", '''


CHAMBERS = {
    "treasure": ("Something glints on an altar of black stone.", "An empty altar; someone was here before you."),
    "guardian": ("A {species} stands between you and the way on, and its eyes open.", "The {species} lies broken."),
    "trial": ("A trial chamber: {trial_words}", "The trial here has been passed."),
    "rivals": ("Voices ahead: others have come this way.", "Nobody bars the way now."),
    "stair": ("A stair goes down into the dark.", "A stair goes down into the dark."),
    "inheritance": ("A throne of jade, and on it the stillness of {master}.", "An empty throne of jade."),
}
TRIAL_WORDS = {"formation": "lines of an ancient array glow in the floor.",
               "pressure": "the qi here presses like deep water.",
               "mirror": "a bronze mirror as tall as a door."}


def chamber_line(world, realm, floor: int, c: int, room: dict) -> str:
    fresh, spent = CHAMBERS[room["kind"]]
    text = fresh if room["state"] == "untouched" else spent
    return text.format(species=room["contents"].get("species", "guardian"),
                       trial_words=TRIAL_WORDS.get(room["contents"].get("trial"), ""),
                       master=realm.data["master"]["name"])


def _trespassed_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} was caught slipping into "
               f"{variant.get('realm_name') or 'a secret realm'} past the sects' guards.")


SPECIAL_PHRASES["trespassed"] = _trespassed_story


@outcome("realm_entered", body_facts=False)
def _entered(world, event):
    realm = world.entity(event.data["realm"]).name
    how = {"token": "The jade token grows warm and crumbles as the gate lets you through.",
           "sponsor": "A sect's elder vouches for you, and the guards stand aside.",
           "sneak": "You slip past the guards while their eyes are elsewhere."}.get(event.data["how"], "")
    return [line for line in (how, f"You step through the gate into {realm}.") if line], {}


@summary("realm_entered")
def _entered_line(world, entry, names, place, other):
    return f"Entered {world.entity(entry.data['realm']).name} at {place}."


@outcome("sneak_caught", body_facts=False)
def _caught(world, event):
    return ["A sect guard catches your sleeve: \\"Not without a place, friend.\\" Word of it will spread."], {}


@summary("sneak_caught")
def _caught_line(world, entry, names, place, other):
    return f"Was caught slipping into {world.entity(entry.data['realm']).name}."


@outcome("delve_moved", body_facts=False)
def _moved(world, event):
    return [], {}


@outcome("realm_left", body_facts=False)
def _left(world, event):
    return [f"You come out of {world.entity(event.data['realm']).name} into daylight."], {}


@summary("realm_left")
def _left_line(world, entry, names, place, other):
    return f"Came out of {world.entity(entry.data['realm']).name} alive."


@outcome("chamber_looted", body_facts=False)
def _looted(world, event):
    prize = event.data["prize"]
    what = prize.get("name") or {"manual": "a martial manual", "star_iron": "a lump of star iron"}.get(prize["kind"], "a treasure")
    return [f"You take {what}."], {}


@summary("chamber_looted")
def _looted_line(world, entry, names, place, other):
    return f"Took a treasure in {world.entity(entry.data['realm']).name}."


@outcome("token_bought", body_facts=False)
def _bought(world, event):
    return [f"{world.entity(event.actors[1]).name} counts your {event.data['silver']} silver and hands over the jade token."], {}


@summary("token_bought")
def _bought_line(world, entry, names, place, other):
    return f"Bought a jade token from {other} in {place}."


@outcome("delve_rested", body_facts=False)
def _rested(world, event):
    return ["You sit against the cold wall and let your qi settle."], {}
''')
edit("narrate/realm_text.py", '''from narrate.outcomes import cap  # first: outcomes loads gossip_text, which needs it loaded''',
     '''from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded''')
print("task 3 edits applied")
```

- [ ] **Step 7: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4f_task3.py && .venv/Scripts/python.exe -m pytest tests/test_delve.py -q -p no:cacheprovider`
Expected: `task 3 edits applied`, then `9 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 8: Commit**

Run: `git add -A && git commit -m "feat: the delve - enter at the gate by the realm's rule, a sponsor or a sneak; floors, stairs, treasure and time; leave from the first floor"`

---
### Task 4: Guardians, trials, the inheritance, and what the dead leave

**Files:**
- Create: `systems/chambers.py`
- Modify (via `.patches/4f_task4.py`):
  - `engine/delve.py`: the chambers' choices, and `ChamberMixin` (their verbs, and what a fight inside settles);
  - `engine/game.py`: `ChamberMixin` joins the `Game` bases;
  - `systems/realm_gates.py`: each opening renews its chambers;
  - `engine/lineage_page.py`: a dead master is named;
  - `narrate/realm_text.py`, `narrate/grammar/realm.toml`: outcomes and journal lines.
- Test: `tests/test_chambers.py`

**Interfaces:**
- Consumes:
  - Task 3: `D.here`, `D.set_chamber`, `D.position`, `D.STEP`, `DelveMixin._chamber_choices`, `INSIDE_VERBS`;
  - Task 2: `G.inherit`, `G.shade_realm`;
  - `T.realm_of`, `duel.best_art`, `techniques.teach`, `set_mastery`, `realms.add_energy`, `world.body.add_injury`, `max_qi`;
  - `agendas._pair`; `FightMixin._start_duel`, `_after_duel`.
- Produces:
  - **`systems.chambers` (C):**
    - constants: `SLIP_BASE = 0.3`, `SLIP_PER_AGILITY = 0.03`, `SLIP_PER_REALM = 0.1`, `SLIP_BOUNDS = (0.05, 0.8)`, `FORMATION_BASE = 0.2`, `FORMATION_PER_COMPREHENSION = 0.04`, `FORMATION_BOUNDS = (0.1, 0.9)`, `PRESSURE_QI = 0.4`, `MIRROR_MASTERY = 0.05`, `RESTOCK_CHANCE = 0.3`;
    - `guardian(world, realm, floor, chamber) -> int`, `mirror(world, realm, floor, chamber, player) -> int`, `shade(world, realm, player) -> int`: realm spirits, `person` entities with `realm_spirit = True` and `delve_at = [floor, chamber]`;
    - `slip_events`, `slain_events`, `trial_open(world, player) -> bool`, `trial_events`, `mirror_events(world, player, passed)`, `inheritance_open(world, player) -> bool`, `shade_events(world, player, passed)`, `remains_events(world, player, item)`, `renew_events(world, occurrence)`.
  - **Events:**
    - `guardian_slain`, `guardian_slipped` (`passed`);
    - `trial_attempted` (`trial`, `passed`, …);
    - `inheritance_claimed`, `inheritance_failed`;
    - `remains_taken` (`item`);
    - `chambers_renewed` (`realm`, `floors`).
  - **Chamber contents:** `tried` (player ids, for a trial, this opening), `failed` (the inheritance), `remains` (item ids the dead left).
  - **Verbs:** `fight_guardian`, `slip_past`, `attempt_trial`, `face_shade`, `take_remains`.

- [ ] **Step 1: Write the failing test** — `tests/test_chambers.py`
```python
import pytest

import systems.chambers as C
import systems.delve as D
import systems.encounters as encounters
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_realms
from engine.actions import Action
from engine.game import Game
from engine.lineage_page import lineage_lines
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import max_qi
from world.events import commit


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
    monkeypatch.setattr(G, "near_sects", lambda world, gate: [])  # an empty realm: no rival bands (Task 5 has those)
    monkeypatch.setattr(G, "WANDERER_CHANCE", 0.0)


def room(kind, **contents):
    return {"kind": kind, "state": "untouched", "contents": contents}


def inside(game, *first_floor):
    """Enter a realm (gate in the player's town, open rule) whose first floor is these chambers, then a stair."""
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None},
                      floors=[list(first_floor) + [room("stair")], [room("inheritance")]])
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    sky.observe(world, town)
    game.perform(Action("enter_realm", realm))
    return realm


def actions(turn):
    return [c.action for c in turn.all_choices]


def end_duel(game, result, verdict=None):
    """End the running duel with this result, the way the fight menu does after the last exchange."""
    import systems.duel as duel
    from world.seed import rng_for
    d = game.combat
    event = duel._end_event(game.world, d, result, "limit", rng_for(1, "end"), d.harm, 5, verdict)
    game._commit([event])
    return game._finish_duel(event.data)


def test_a_guardian_is_fought_and_stays_slain(game):
    world, me = game.world, game.player.id
    realm = inside(game, room("guardian", species="stone lion", realm=2, guardian=None))
    assert Action("fight_guardian") in actions(game.perform(Action("look")))
    game.perform(Action("fight_guardian"))
    lion = world.entity(realm).data["floors"][0][0]["contents"]["guardian"]
    assert game.combat is not None and game.combat.opponent == lion and world.entity(lion).data["realm_spirit"]
    end_duel(game, "won", "kill")
    assert world.entity(realm).data["floors"][0][0]["state"] == "slain"
    assert Action("delve_on") in actions(game.perform(Action("look")))


def test_slipping_past_a_guardian_or_facing_it(game, monkeypatch):
    world = game.world
    realm = inside(game, room("guardian", species="jade serpent", realm=2, guardian=None))
    monkeypatch.setattr(C, "SLIP_BOUNDS", (1.0, 1.0))
    game.perform(Action("slip_past"))
    assert world.entity(realm).data["floors"][0][0]["state"] == "passed" and game.combat is None
    world.update_data(realm, floors=[[room("guardian", species="jade serpent", realm=2, guardian=None), room("stair")],
                                     [room("inheritance")]])
    monkeypatch.setattr(C, "SLIP_BOUNDS", (0.0, 0.0))
    game.perform(Action("slip_past"))
    assert game.combat is not None  # seen: it fights


def test_a_formation_trial_grants_insight_once_an_opening(game, monkeypatch):
    world, me = game.world, game.player.id
    inside(game, room("trial", trial="formation"))
    monkeypatch.setattr(C, "FORMATION_BOUNDS", (1.0, 1.0))
    insight = load_body(world, me).insight
    game.perform(Action("attempt_trial"))
    assert load_body(world, me).insight > insight
    assert Action("attempt_trial") not in actions(game.perform(Action("look")))


def test_a_failed_formation_costs_qi_and_hurts(game, monkeypatch):
    world, me = game.world, game.player.id
    inside(game, room("trial", trial="formation"))
    monkeypatch.setattr(C, "FORMATION_BOUNDS", (0.0, 0.0))
    body = load_body(world, me)
    body.qi = max_qi(body)
    save_body(world, me, body)
    game.perform(Action("attempt_trial"))
    after = load_body(world, me)
    assert after.qi <= 0.75 * max_qi(body) and len(after.injuries) == len(body.injuries) + 1  # halved, then two watches' rest


def test_the_qi_pressure_asks_for_qi_and_gives_cultivation(game):
    world, me = game.world, game.player.id
    inside(game, room("trial", trial="pressure"))
    body = load_body(world, me)
    body.qi = max_qi(body)
    save_body(world, me, body)
    energy = body.energy_years
    game.perform(Action("attempt_trial"))
    assert load_body(world, me).energy_years > energy


def test_the_mirror_is_you_and_beating_it_sharpens_your_art(game):
    from systems.duel import best_art
    world, me = game.world, game.player.id
    mine = best_art(world, me)  # a hunter's family art
    inside(game, room("trial", trial="mirror"))
    game.perform(Action("attempt_trial"))
    reflection = game.combat.opponent
    assert world.entity(reflection).data["realm_spirit"] and best_art(world, reflection).technique.id == mine.technique.id
    end_duel(game, "spar_won")
    assert best_art(world, me).mastery == pytest.approx(mine.mastery + C.MIRROR_MASTERY)


def test_the_inheritance_is_won_once_and_names_your_master(game):
    world, me = game.world, game.player.id
    realm = inside(game)
    game.perform(Action("delve_on"))  # the stair down
    assert Action("face_shade") in actions(game.perform(Action("look")))
    game.perform(Action("face_shade"))
    shade = game.combat.opponent
    from systems.tournaments import realm_of
    assert realm_of(world, shade) == realm_of(world, me) + 1
    end_duel(game, "passed")
    master = world.entity(realm).data["master"]
    assert world.entity(realm).data["inheritance_claimed_by"] == me
    assert any(t == master["art"] for t, _, _ in world.relations_from(me, "knows"))
    assert any(d.get("role") == "master" for _, _, d in world.relations_from(me, "kin_of"))  # kin_of lists only the living
    assert any("Master" in t and master["name"] in t for t, _ in lineage_lines(world, me))
    assert Action("face_shade") not in actions(game.perform(Action("look")))
    assert check_realms(world) == []


def test_failing_the_shade_throws_you_back_for_this_opening(game):
    world, me = game.world, game.player.id
    inside(game)
    game.perform(Action("delve_on"))
    game.perform(Action("face_shade"))
    end_duel(game, "failed")
    assert D.position(world, me)["chamber"] == 0
    assert Action("face_shade") not in actions(game.perform(Action("look")))


def test_what_the_dead_carried_lies_where_they_fell(game):
    world, me = game.world, game.player.id
    realm = inside(game, room("trial", trial="formation"))
    rival = C._spirit(world, "test:fallen", realm, 1, 0, "Ma Chen", realm="second-rate")
    world.update_data(rival, realm_spirit=False, beast=False)
    herb = world.add_entity("treasure", "a blood lotus", {"kind": "herb", "value": 300, "used": False})
    world.relate(rival, herb, "owns")
    commit(world, [G_died(rival, realm)])
    assert herb in world.entity(realm).data["floors"][0][0]["contents"]["remains"]
    assert world.sources(herb, "owns") == [realm]
    game.perform(Action("take_remains", herb))
    assert world.sources(herb, "owns") == [me]


def G_died(person, realm):
    from world.events import Event
    return Event("died", (person, person), realm, {"cause": "realm", "world": True})


def test_an_opening_renews_what_was_taken_and_slain(game, monkeypatch):
    monkeypatch.setattr(C, "RESTOCK_CHANCE", 1.0)
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    spent = [{"kind": "treasure", "state": "looted", "contents": {"prize": {"kind": "herb", "name": "a herb", "value": 1}}},
             {"kind": "guardian", "state": "slain", "contents": {"species": "stone lion", "realm": 2, "guardian": 99}},
             {"kind": "stair", "state": "untouched", "contents": {}}]
    world.update_data(realm, gate=town, floors=[spent, [room("inheritance")]])
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    sky.observe(world, town)
    floor = world.entity(realm).data["floors"][0]
    assert floor[0]["state"] == "untouched" and floor[1]["state"] == "untouched" and floor[1]["contents"]["guardian"] is None
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chambers.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.chambers'`.

- [ ] **Step 3: Write the chambers** — `systems/chambers.py`
```python
"""The chambers of a secret realm (phase 4f spec 3.2-3.3): guardians, trials, the inheritance, and what the dead leave.

Guardians, reflections and the master's shade are realm spirits: `person` entities that live inside
(`realm_spirit`, `delve_at`), are not on the life clock, and are fought through the ordinary duel.
"""

import systems.delve as D
import systems.realm_gates as G
from systems.bodies import load_body, save_body
from systems.duel import best_art
from systems.facts import make_variant, record_fact
from systems.realms import REALMS, add_energy
from systems.techniques import set_mastery, teach
from systems.time import advance
from systems.tournaments import realm_of
from world.body import add_injury, max_qi
from world.events import Event, commit, effect, listen
from world.seed import rng_for

SLIP_BASE, SLIP_PER_AGILITY, SLIP_PER_REALM, SLIP_BOUNDS = 0.3, 0.03, 0.1, (0.05, 0.8)
FORMATION_BASE, FORMATION_PER_COMPREHENSION, FORMATION_BOUNDS = 0.2, 0.04, (0.1, 0.9)
PRESSURE_QI = 0.4
MIRROR_MASTERY = 0.05
RESTOCK_CHANCE = 0.3


def _clamp(value: float, bounds) -> float:
    return min(bounds[1], max(bounds[0], value))


def _spirit(world, path: str, home: int, floor: int, c: int, name: str, **data) -> int:
    """A realm spirit at this chamber of the realm `home`: made once per path, refreshed when met again.
    (`data["realm"]` is its cultivation realm, as for anyone.)"""
    found = world.entity_by_seed(path)
    if found is not None:
        world.update_data(found.id, delve_at=[floor, c], **data)
        return found.id
    spirit = world.add_entity("person", name, {"realm_spirit": True, "beast": False, "delve_at": [floor, c],
                                               "arts_ready": True,  # their arts are given, never seeded (a mirror is you)
                                               "traits": ["hot-tempered"], "silver": 0, "age": 300, **data}, path)
    world.relate(spirit, home, "located_in")
    return spirit


def guardian(world, realm: int, floor: int, c: int) -> int:
    room = world.entity(realm).data["floors"][floor - 1][c]
    if room["contents"].get("guardian"):
        return room["contents"]["guardian"]
    openings = len(world.entity(realm).data["history"])
    spirit = _spirit(world, f"realm:{realm}:guardian:{floor}:{c}:{openings}", realm, floor, c,
                     f"a {room['contents']['species']}", beast=True, occupation=room["contents"]["species"],
                     realm=REALMS[room["contents"]["realm"]].label)
    D.set_chamber(world, realm, floor, c, contents={**room["contents"], "guardian": spirit})
    return spirit


def mirror(world, realm: int, floor: int, c: int, player: int) -> int:
    """Your reflection: your own body and your best art."""
    spirit = _spirit(world, f"realm:{realm}:mirror:{floor}:{c}", realm, floor, c, "your reflection",
                     occupation="reflection", realm=REALMS[realm_of(world, player)].label)
    save_body(world, spirit, load_body(world, player))
    art = best_art(world, player)
    if art is not None and all(t != art.technique.id for t, _, _ in world.relations_from(spirit, "knows")):
        teach(world, spirit, art.technique.id, completeness=art.completeness, mastery=art.mastery)
    return spirit


def shade(world, realm: int, player: int) -> int:
    """The master's remnant: their art, one realm above whoever kneels (spec §3.2)."""
    floors = world.entity(realm).data["floors"]
    master = world.entity(realm).data["master"]
    spirit = _spirit(world, f"realm:{realm}:shade", realm, len(floors), len(floors[-1]) - 1,
                     f"the remnant of {master['name']}", occupation="remnant soul",
                     realm=REALMS[G.shade_realm(world, player)].label)
    if all(t != master["art"] for t, _, _ in world.relations_from(spirit, "knows")):
        teach(world, spirit, master["art"], completeness=1.0, mastery=0.9)
    return spirit


# --- guardians -------------------------------------------------------------------------------------

def slip_events(world, player: int) -> list[Event]:
    realm, floor, c, room = D.here(world, player)
    agility = load_body(world, player).physique["agility"]
    gap = room["contents"]["realm"] - realm_of(world, player)
    chance = _clamp(SLIP_BASE + SLIP_PER_AGILITY * (agility - 10) - SLIP_PER_REALM * gap, SLIP_BOUNDS)
    passed = rng_for(world.world_seed, f"slip:{realm.id}:{floor}:{c}:{player}:{world.time}").random() < chance
    return [Event("guardian_slipped", (player,), realm.id, {"realm": realm.id, "floor": floor, "chamber": c,
                                                            "passed": passed})]


@effect("guardian_slipped")
def _slipped(world, event) -> None:
    d = event.data
    if d["passed"]:
        D.set_chamber(world, d["realm"], d["floor"], d["chamber"], state="passed")
    advance(world, D.STEP)


def slain_events(world, player: int, purpose: dict) -> list[Event]:
    realm, floor, c = purpose["guardian"]
    return [Event("guardian_slain", (player, world.entity(realm).data["floors"][floor - 1][c]["contents"]["guardian"]),
                  realm, {"realm": realm, "floor": floor, "chamber": c})]


@effect("guardian_slain")
def _slain(world, event) -> None:
    d = event.data
    D.set_chamber(world, d["realm"], d["floor"], d["chamber"], state="slain")


# --- trials ------------------------------------------------------------------------------------------

def trial_open(world, player: int) -> bool:
    realm, floor, c, room = D.here(world, player)
    return room["kind"] == "trial" and room["state"] == "untouched" and player not in room["contents"].get("tried", [])


def trial_events(world, player: int) -> list[Event]:
    """Formation and pressure settle at once; the mirror is a spar (the engine starts it)."""
    realm, floor, c, room = D.here(world, player)
    trial = room["contents"]["trial"]
    body = load_body(world, player)
    data = {"realm": realm.id, "floor": floor, "chamber": c, "trial": trial}
    if trial == "formation":
        chance = _clamp(FORMATION_BASE + FORMATION_PER_COMPREHENSION * body.physique["comprehension"], FORMATION_BOUNDS)
        passed = rng_for(world.world_seed, f"formation:{realm.id}:{floor}:{c}:{player}:{world.time}").random() < chance
        data.update(passed=passed, insight=round(0.5 + 0.2 * floor, 2) if passed else 0.0)
    elif trial == "pressure":
        passed = body.qi >= PRESSURE_QI * max_qi(body) and realm_of(world, player) >= floor - 1
        data.update(passed=passed, years=round(0.2 * floor, 2) if passed else 0.0)
    else:
        return []
    return [Event("trial_attempted", (player,), realm.id, data)]


@effect("trial_attempted")
def _attempted(world, event) -> None:
    player, d = event.actors[0], event.data
    room = world.entity(d["realm"]).data["floors"][d["floor"] - 1][d["chamber"]]
    contents = {**room["contents"], "tried": room["contents"].get("tried", []) + [player]}
    D.set_chamber(world, d["realm"], d["floor"], d["chamber"], contents=contents,
                  **({"state": "passed"} if d["passed"] else {}))
    body = load_body(world, player)
    if d["trial"] == "formation":
        if d["passed"]:
            body.insight += d["insight"]
        else:
            body.qi = body.qi / 2
            add_injury(body, "torso", "internal", 1, world.time, "an ancient array's backlash")
    elif d["trial"] == "pressure":
        if d["passed"]:
            add_energy(body, d["years"])
        else:
            body.qi = body.qi * 0.75
    save_body(world, player, body)
    advance(world, D.STEP)


def mirror_events(world, player: int, purpose: dict, passed: bool) -> list[Event]:
    realm, floor, c = purpose["mirror"]
    art = best_art(world, player)
    return [Event("trial_attempted", (player,), realm,
                  {"realm": realm, "floor": floor, "chamber": c, "trial": "mirror", "passed": passed,
                   "art": art.technique.id if art and passed else None})]


@listen("trial_attempted")
def _sharpened(world, event, event_id: int) -> None:
    d = event.data
    if d["trial"] == "mirror" and d.get("art") is not None:
        mastery = next(v for t, v, _ in world.relations_from(event.actors[0], "knows") if t == d["art"])
        set_mastery(world, event.actors[0], d["art"], min(1.0, mastery + MIRROR_MASTERY))


# --- the inheritance ------------------------------------------------------------------------------------

def inheritance_open(world, player: int) -> bool:
    realm, floor, c, room = D.here(world, player)
    return room["kind"] == "inheritance" and realm.data["inheritance_claimed_by"] is None \
        and player not in room["contents"].get("failed", [])


def shade_events(world, player: int, purpose: dict, passed: bool) -> list[Event]:
    realm = purpose["inheritance"]
    return [Event("inheritance_claimed" if passed else "inheritance_failed", (player,), realm, {"realm": realm})]


def _master_person(world, realm: int) -> int:
    """The dead master, as a person the lineage can name: dead long ago, buried in their realm."""
    master = world.entity(realm).data["master"]
    path = f"realm:{realm}:master"
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    person = world.add_entity("person", master["name"], {"dead": True, "age": 300, "realm": "profound",
                                                          "death": {"cause": "age", "age": 300, "place": realm},
                                                          "occupation": "ancient master"}, path)
    world.relate(person, realm, "buried_at")
    return person


@effect("inheritance_claimed")
def _claimed(world, event) -> None:
    from systems.agendas import _pair
    player, realm = event.actors[0], event.data["realm"]
    G.inherit(world, player, realm)
    floors = world.entity(realm).data["floors"]
    D.set_chamber(world, realm, len(floors), len(floors[-1]) - 1, state="passed")
    _pair(world, _master_person(world, realm), player, "disciple")  # their last disciple (spec §3.2)


@listen("inheritance_claimed")
def _claimed_news(world, event, event_id: int) -> None:
    player, realm = event.actors[0], world.entity(event.data["realm"])
    variant = make_variant("inherited", player, None, place=realm.name)
    variant.update(realm_name=realm.name, master=realm.data["master"]["name"])
    record_fact(world, player, "inherited", None, place=realm.id, source_event=event_id, weight=3.0, variant=variant)


@effect("inheritance_failed")
def _failed(world, event) -> None:
    player, realm = event.actors[0], event.data["realm"]
    floors = world.entity(realm).data["floors"]
    room = floors[-1][-1]
    D.set_chamber(world, realm, len(floors), len(floors[-1]) - 1,
                  contents={**room["contents"], "failed": room["contents"].get("failed", []) + [player]})
    world.update_data(player, delve={"realm": realm, "floor": len(floors), "chamber": 0})  # thrown back


# --- the dead, and what they carried -------------------------------------------------------------------------

@listen("died")
def _fell_inside(world, event, event_id: int) -> None:
    """Whoever dies in a realm leaves what they carried where they fell (spec §3.3)."""
    victim = event.actors[-1]
    person = world.entity(victim)
    where = person.data.get("delve") or ({"realm": None, "floor": person.data["delve_at"][0],
                                          "chamber": person.data["delve_at"][1]} if person.data.get("delve_at") else None)
    realms = world.get_meta("secret_realms") or []
    realm = (where or {}).get("realm") or (event.place if event.place in realms else None)
    if where is None or realm is None:
        return
    items = [i for i in world.targets(victim, "owns") if world.entity(i).kind in ("treasure", "manual")]
    if items:
        commit(world, [Event("remains_left", (victim,), realm, {"realm": realm, "floor": where["floor"],
                                                               "chamber": where["chamber"], "items": items})])
    world.update_data(victim, delve=None, delve_at=None)


@effect("remains_left")
def _remains_left(world, event) -> None:
    d = event.data
    room = world.entity(d["realm"]).data["floors"][d["floor"] - 1][d["chamber"]]
    for item in d["items"]:
        world.unrelate(event.actors[0], "owns", item)
        world.relate(d["realm"], item, "owns")
    D.set_chamber(world, d["realm"], d["floor"], d["chamber"],
                  contents={**room["contents"], "remains": room["contents"].get("remains", []) + d["items"]})


def remains_events(world, player: int, item: int) -> list[Event]:
    realm, floor, c, room = D.here(world, player)
    if item not in room["contents"].get("remains", []):
        return []
    return [Event("remains_taken", (player,), realm.id, {"realm": realm.id, "floor": floor, "chamber": c, "item": item})]


@effect("remains_taken")
def _remains_taken(world, event) -> None:
    d = event.data
    room = world.entity(d["realm"]).data["floors"][d["floor"] - 1][d["chamber"]]
    world.unrelate(d["realm"], "owns", d["item"])
    world.relate(event.actors[0], d["item"], "owns")
    D.set_chamber(world, d["realm"], d["floor"], d["chamber"],
                  contents={**room["contents"], "remains": [i for i in room["contents"]["remains"] if i != d["item"]]})


# --- each opening renews the chambers ------------------------------------------------------------------------

def renew_events(world, occurrence) -> list[Event]:
    """Slain guardians rise again, trials reset, and a looted treasure returns with chance 0.3 (spec §3.2)."""
    import systems.secret_realms as SR
    realm = world.entity(occurrence.data["data"]["realm"])
    rng = rng_for(world.world_seed, f"realm:{occurrence.id}:renew")
    floors = []
    for f, chambers in enumerate(realm.data["floors"], 1):
        renewed = []
        for room in chambers:
            if room["kind"] == "guardian" and room["state"] != "untouched":
                room = {**room, "state": "untouched", "contents": {**room["contents"], "guardian": None}}
            elif room["kind"] == "trial":
                room = {**room, "state": "untouched", "contents": {**room["contents"], "tried": []}}
            elif room["kind"] == "inheritance":
                room = {**room, "contents": {**room["contents"], "failed": []}}
            elif room["kind"] == "treasure" and room["state"] == "looted" and rng.random() < RESTOCK_CHANCE:
                room = {**room, "state": "untouched", "contents": {**room["contents"], "prize": SR.prize_at(rng, f)}}
            renewed.append(room)
        floors.append(renewed)
    return [Event("chambers_renewed", (), occurrence.data["place"], {"realm": realm.id, "floors": floors})]


@effect("chambers_renewed")
def _renewed(world, event) -> None:
    world.update_data(event.data["realm"], floors=event.data["floors"])
```

- [ ] **Step 4: Edit the existing files** — `.patches/4f_task4.py`
```python
"""Task 4 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    Path(path).write_text(Path(path).read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


ENG = "engine/delve.py"
edit(ENG, '''    "delve_on", "delve_back", "leave_realm", "take_treasure", "delve_rest",
})''', '''    "delve_on", "delve_back", "leave_realm", "take_treasure", "delve_rest",
    "fight_guardian", "slip_past", "attempt_trial", "face_shade", "take_remains",
})
TRIAL_LABELS = {"formation": "Read the ancient array", "pressure": "Walk into the pressing qi",
                "mirror": "Face the bronze mirror"}''')
edit(ENG, '''import systems.delve as D
''', '''import systems.chambers as C
import systems.delve as D
''')
edit(ENG, '''    def _chamber_choices(self, realm, floor: int, c: int, room: dict) -> list:
        if room["kind"] == "treasure" and room["state"] == "untouched":
            return [Choice(f"Take {chamber_prize(room)}", Action("take_treasure"))]
        return []''', '''    def _chamber_choices(self, realm, floor: int, c: int, room: dict) -> list:
        world, me = self.world, self.player.id
        out = []
        if room["kind"] == "treasure" and room["state"] == "untouched":
            out.append(Choice(f"Take {chamber_prize(room)}", Action("take_treasure")))
        if room["kind"] == "guardian" and room["state"] == "untouched":
            species = room["contents"]["species"]
            out += [Choice(f"Fight the {species}", Action("fight_guardian")),
                    Choice(f"Slip past the {species}", Action("slip_past"))]
        if C.trial_open(world, me):
            out.append(Choice(TRIAL_LABELS[room["contents"]["trial"]], Action("attempt_trial")))
        if C.inheritance_open(world, me):
            out.append(Choice(f"Kneel before {realm.data['master']['name']}", Action("face_shade")))
        for item in room["contents"].get("remains", []):
            out.append(Choice(f"Take {world.entity(item).name} from the fallen", Action("take_remains", item)))
        return out''')
append(ENG, '''


def _room(game):
    return D.here(game.world, game.player.id)


class ChamberMixin:
    """The chambers' verbs (Task 4): a Game base beside DelveMixin, whose steps and lines it uses."""

    def _do_fight_guardian(self, _target):
        found = _room(self)
        if found is None or found[3]["kind"] != "guardian" or found[3]["state"] != "untouched":
            return self._turn([("Nothing here bars your way.", "system")])
        realm, floor, c, room = found
        foe = C.guardian(self.world, realm.id, floor, c)
        return self._turn(self._start_duel(foe, "duel", purpose={"guardian": [realm.id, floor, c]}))

    def _do_slip_past(self, _target):
        found = _room(self)
        if found is None or found[3]["kind"] != "guardian" or found[3]["state"] != "untouched":
            return self._turn([("Nothing here bars your way.", "system")])
        realm, floor, c, room = found
        lines = self._commit(C.slip_events(self.world, self.player.id))
        if self.world.entity(realm.id).data["floors"][floor - 1][c]["state"] == "passed":
            return self._turn(lines + self._delve_lines())
        foe = C.guardian(self.world, realm.id, floor, c)  # seen: it turns on you
        return self._turn(lines + self._start_duel(foe, "duel", purpose={"guardian": [realm.id, floor, c]}))

    def _do_attempt_trial(self, _target):
        if _room(self) is None or not C.trial_open(self.world, self.player.id):
            return self._turn([("There is no trial for you here.", "system")])
        realm, floor, c, room = _room(self)
        if room["contents"]["trial"] == "mirror":
            foe = C.mirror(self.world, realm.id, floor, c, self.player.id)
            return self._turn(self._start_duel(foe, "spar", purpose={"mirror": [realm.id, floor, c]}))
        return self._step(C.trial_events(self.world, self.player.id), "There is no trial for you here.")

    def _do_face_shade(self, _target):
        if _room(self) is None or not C.inheritance_open(self.world, self.player.id):
            return self._turn([("No one waits for you here.", "system")])
        realm = _room(self)[0]
        foe = C.shade(self.world, realm.id, self.player.id)
        return self._turn(self._start_duel(foe, "test", purpose={"inheritance": realm.id}))

    def _do_take_remains(self, item):
        return self._step(C.remains_events(self.world, self.player.id, item) if isinstance(item, int) else [],
                          "There is nothing like that here.")

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        me = self.player.id
        if "guardian" in purpose and data.get("result") == "won":
            lines += self._commit(C.slain_events(self.world, me, purpose))
        elif "mirror" in purpose:
            lines += self._commit(C.mirror_events(self.world, me, purpose, data.get("result") == "spar_won"))
        elif "inheritance" in purpose:
            lines += self._commit(C.shade_events(self.world, me, purpose, data.get("result") == "passed"))
        return lines

''')

edit("engine/delve.py", '''    def _gate(self, action):
        if self._inside() and self.combat is None and action.verb not in INSIDE_VERBS:''', '''    def _gate(self, action):
        if self._inside() and self.combat is None and not self.player.data.get("dying") \\
                and action.verb not in INSIDE_VERBS:''')

edit("engine/game.py", '''class Game(DelveMixin, ''', '''class Game(ChamberMixin, DelveMixin, ''')
edit("engine/game.py", '''from engine.delve import DelveMixin''', '''from engine.delve import ChamberMixin, DelveMixin''')

edit("systems/realm_gates.py", '''    if stage == "active":
        return walk_out_events(world, occurrence) + delver_events(world, occurrence)''', '''    if stage == "active":
        from systems.chambers import renew_events  # each opening, the chambers renew (Task 4)
        return renew_events(world, occurrence) + walk_out_events(world, occurrence) + delver_events(world, occurrence)''')

edit("engine/lineage_page.py", '''    rows += [f"  Sworn follower: {_someone(world, f)}" for f in followers(world, player)]''',
     '''    rows += [f"  Sworn follower: {_someone(world, f)}" for f in followers(world, player)]
    rows += [f"  Master: {world.entity(k).name}" + (" (long dead)" if world.entity(k).data.get("dead") else "")
             for k, _, d in world.relations_from(player, "kin_of") if d.get("role") == "master"]  # a realm's last disciple (4f)''')

append("narrate/realm_text.py", '''


@outcome("guardian_slipped", body_facts=False)
def _slipped(world, event):
    return (["You keep to the shadows and slip past."] if event.data["passed"]
            else ["It sees you."]), {}


@outcome("guardian_slain", body_facts=False)
def _slain(world, event):
    return [f"{world.entity(event.actors[1]).name[0].upper()}{world.entity(event.actors[1]).name[1:]} falls and does not rise."], {}


@summary("guardian_slain")
def _slain_line(world, entry, names, place, other):
    return f"Slew a realm guardian in {place}."


TRIAL_OUTCOMES = {
    ("formation", True): "The array's lines resolve into sense; something opens in your understanding.",
    ("formation", False): "The array flares. Your qi scatters and the light burns you.",
    ("pressure", True): "You walk into the pressing qi and it pours into you.",
    ("pressure", False): "The pressure drives you back, and costs you qi.",
    ("mirror", True): "Your reflection falters first. You see where your art was weak.",
    ("mirror", False): "Your reflection outlasts you, and smiles your smile.",
}


@outcome("trial_attempted", body_facts=False)
def _trial(world, event):
    return [TRIAL_OUTCOMES[(event.data["trial"], event.data["passed"])]], {}


@summary("trial_attempted")
def _trial_line(world, entry, names, place, other):
    return f"{'Passed' if entry.data['passed'] else 'Failed'} a {entry.data['trial']} trial in {place}."


@outcome("inheritance_claimed", body_facts=False)
def _claimed(world, event):
    realm = world.entity(event.data["realm"])
    master = realm.data["master"]
    return [f"The remnant of {master['name']} bows its head. Its art flows into you, whole; {master['weapon']} is yours.",
            f"You are the last disciple of {master['name']}."], {}


@summary("inheritance_claimed")
def _claimed_line(world, entry, names, place, other):
    return f"Won the inheritance of {world.entity(entry.data['realm']).data['master']['name']}."


@outcome("inheritance_failed", body_facts=False)
def _failed(world, event):
    return ["The remnant turns its face away, and a wind throws you back across the floor."], {}


@summary("inheritance_failed")
def _failed_line(world, entry, names, place, other):
    return f"Was found wanting by the remnant in {place}."


@outcome("remains_taken", body_facts=False)
def _remains(world, event):
    return [f"You take {world.entity(event.data['item']).name} from the one who fell here."], {}


@summary("remains_taken")
def _remains_line(world, entry, names, place, other):
    return f"Took what the fallen left in {place}."
''')
append("narrate/grammar/realm.toml", '''
[guardian_slipped]
colour = "dim"
lines = ["#realm_air#"]

[guardian_slain]
colour = "default"
lines = ["#realm_air#"]

[trial_attempted]
colour = "default"
lines = ["#realm_air#", "#realm_air# #realm_air#"]

[inheritance_claimed]
colour = "gold"
lines = ["#realm_air# #realm_air#"]

[inheritance_failed]
colour = "default"
lines = ["#realm_air#"]

[remains_taken]
colour = "default"
lines = ["#realm_air#"]
''')
print("task 4 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4f_task4.py && .venv/Scripts/python.exe -m pytest tests/test_chambers.py -q -p no:cacheprovider`
Expected: `task 4 edits applied`, then `10 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: realm chambers - guardians fought or slipped past, three trials, the master's shade and inheritance, what the dead leave, and chambers renewed each opening"`

---
### Task 5: Rival delvers in full detail

**Files:**
- Create: `systems/delvers.py`
- Modify (via `.patches/4f_task5.py`):
  - `systems/delve.py`: only a guardian bars the way by its kind; a band in your chamber bars it (`delvers.blocking`);
  - `engine/delve.py`: the bands' choices, their steps after each of yours, an ambush, a routed band;
  - `engine/game.py`: `RivalMixin` joins the `Game` bases;
  - `narrate/realm_text.py`, `narrate/grammar/realm.toml`: outcomes and journal lines.
- Test: `tests/test_delvers.py`

**Interfaces:**
- Consumes:
  - Task 2: `G.RANGE` and the opening's `teams` (`{"faction", "members"}`);
  - Task 3: `D.position`, `D.here`, `D.set_chamber`, `D.gate_open`, `D.days_left`, `DelveMixin._step`, `_delve_lines`, `INSIDE_VERBS`;
  - Task 4: `G.inherit`;
  - `attitude.attitude`, `races.make_prize`, `T.realm_of`, `T.alive`, `F.stance`, `F.memberships`.
- Produces:
  - **`systems.delvers` (R):**
    - constants: `GUARDIAN_BASE = 0.5`, `GUARDIAN_PER_REALM = 0.15`, `INHERIT_BASE = 0.1`, `INHERIT_PER_REALM = 0.15`, `INHERIT_BOUNDS = (0.02, 0.6)`, `CLASH_DEATH = 0.5`, `AMBUSH_CHANCE = 0.5`, `PASS_SCORE = -0.3`, `WARM_SCORE = 1.0`;
    - `placement_events(world, occurrence) -> list[Event]`;
    - `step_events(world, player) -> list[Event]`;
    - `rivals(world, team_a, team_b) -> bool`, `here(world, player) -> list[int]` (the bands in the player's chamber), `blocking(world, player) -> bool`, `leader(world, team) -> int`;
    - `pass_events`, `rout_events`, `join_events`, `ambusher(world, player) -> int | None`.
  - **Opening data:** `placed`; each team gains `at` (`[floor, chamber]`), `let_pass` (player ids), `with` (a player, or None), `with_floor`, `left`.
  - **Member data:** `delve_at = [floor, chamber]` while inside.
  - **Events:** `delvers_placed`, `delvers_stepped` (`moves`, `clashes`), `inheritance_won`, `pass_asked` (`granted`), `band_routed`, `band_joined`.
  - **Verbs:** `ask_pass`, `fight_rival`, `join_band`.

- [ ] **Step 1: Write the failing test** — `tests/test_delvers.py`
```python
import pytest

import systems.delve as D
import systems.delvers as R
import systems.encounters as encounters
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_realms
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from world.events import commit


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
    monkeypatch.setattr(R, "AMBUSH_CHANCE", 0.0)


def room(kind, **contents):
    return {"kind": kind, "state": "untouched", "contents": contents}


def band(world, town, name, realm="second-rate", traits=("calm", "honest")):
    person = founding.make_person(world, f"test:{name}", town, occupation="wandering swordsman", age=25, realm=realm)
    world.update_data(person, traits=list(traits))
    return person


def open_with_bands(game, floors, bands):
    """A realm at the player's town, open now, with these bands chosen at the gate (one member each)."""
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None}, floors=floors)
    data = {**SR.opening_data(realm), "delvers": list(bands), "teams": [{"faction": None, "members": [b]} for b in bands]}
    commit(world, sky.start_events(world, "realm_opening", town, world.time, data))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    sky.observe(world, town)
    return realm, occurrence


def teams(world, occurrence):
    return world.entity(occurrence).data["data"]["teams"]


def put(world, occurrence, i, at):
    t = world.entity(occurrence).data["data"]
    moved = [dict(team) for team in t["teams"]]
    moved[i]["at"] = at
    world.update_data(occurrence, data={**t, "teams": moved})
    for member in moved[i]["members"]:
        world.update_data(member, delve_at=at)


def actions(turn):
    return [c.action for c in turn.all_choices]


def test_the_bands_are_placed_when_you_enter_the_strong_deeper(game):
    world, town = game.world, game.place.id
    floors = [[room("trial", trial="formation"), room("stair")], [room("trial", trial="mirror"), room("stair")],
              [room("inheritance")]]
    weak, strong = band(world, town, "weak", "third-rate"), band(world, town, "strong", "second-rate")
    realm, occurrence = open_with_bands(game, floors, [weak, strong])
    game.perform(Action("enter_realm", realm))
    placed = teams(world, occurrence)
    assert [t["at"][0] for t in placed] == [1, 2]
    for member in (weak, strong):
        assert world.targets(member, "located_in") == [realm] and world.entity(member).data["delve_at"]
    assert check_realms(world) == []


def test_bands_step_as_you_act_and_take_what_they_reach(game):
    world, town = game.world, game.place.id
    herb = {"kind": "herb", "name": "a snow lingzhi", "value": 400}
    floors = [[room("trial", trial="formation"), room("treasure", prize=herb), room("stair")], [room("inheritance")]]
    rival = band(world, town, "rival")
    realm, occurrence = open_with_bands(game, floors, [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 1])
    game.perform(Action("delve_rest"))
    assert world.entity(realm).data["floors"][0][1]["state"] == "looted"
    assert any(world.entity(i).name == "a snow lingzhi" for i in world.targets(rival, "owns"))


def test_rival_sects_clash_when_they_meet(game, monkeypatch):
    monkeypatch.setattr(R, "rivals", lambda world, a, b: True)
    monkeypatch.setattr(R, "CLASH_DEATH", 1.0)
    world, town = game.world, game.place.id
    floors = [[room("trial", trial="formation"), room("trial", trial="pressure"), room("stair")], [room("inheritance")]]
    a, b = band(world, town, "a", "first-rate"), band(world, town, "b", "third-rate")
    realm, occurrence = open_with_bands(game, floors, [a, b])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 2])
    put(world, occurrence, 1, [1, 2])
    game.perform(Action("delve_rest"))
    [stepped] = [e for e in world.chronicle_of_kind("delvers_stepped")][-1:]
    assert stepped.data["clashes"] and sum(world.entity(p).data.get("dead", False) for p in (a, b)) == 1


def test_a_band_can_win_the_inheritance_first(game, monkeypatch):
    monkeypatch.setattr(R, "INHERIT_BOUNDS", (1.0, 1.0))
    world, town = game.world, game.place.id
    rival = band(world, town, "heir")
    realm, occurrence = open_with_bands(game, [[room("stair")], [room("inheritance")]], [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [2, 0])
    game.perform(Action("delve_rest"))
    assert world.entity(realm).data["inheritance_claimed_by"] == rival


def test_a_band_in_your_chamber_bars_the_way_until_it_lets_you_pass(game):
    world, town = game.world, game.place.id
    rival = band(world, town, "gatekeeper")
    realm, occurrence = open_with_bands(game, [[room("trial", trial="formation"), room("stair")], [room("inheritance")]],
                                       [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 0])
    found = actions(game.perform(Action("look")))
    assert Action("delve_on") not in found and Action("ask_pass", 0) in found
    game.perform(Action("ask_pass", 0))
    assert Action("delve_on") in actions(game.perform(Action("look")))


def test_beating_a_band_routs_it(game):
    import systems.duel as duel
    from world.seed import rng_for
    world, town = game.world, game.place.id
    rival = band(world, town, "brawler")
    realm, occurrence = open_with_bands(game, [[room("trial", trial="formation"), room("stair")], [room("inheritance")]],
                                       [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 0])
    game.perform(Action("fight_rival", 0))
    d = game.combat
    event = duel._end_event(world, d, "won", "limit", rng_for(1, "end"), d.harm, 5, "spare")
    game._commit([event])
    game._finish_duel(event.data)
    assert not R.blocking(world, game.player.id)


def test_a_hostile_band_may_attack_first(game, monkeypatch):
    monkeypatch.setattr(R, "AMBUSH_CHANCE", 1.0)
    world, town = game.world, game.place.id
    rival = band(world, town, "proud one", "first-rate", traits=("proud", "greedy"))
    realm, occurrence = open_with_bands(game, [[room("trial", trial="formation"), room("stair")], [room("inheritance")]],
                                       [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 0])
    game.perform(Action("delve_rest"))
    assert game.combat is not None and game.combat.opponent == rival


def test_bands_make_for_the_gate_before_it_closes(game):
    world, town = game.world, game.place.id
    rival = band(world, town, "careful")
    realm, occurrence = open_with_bands(game, [[room("stair")], [room("trial", trial="formation"), room("inheritance")]],
                                       [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 0])
    world.set_time(world.entity(occurrence).data["active"][1] - 4)  # the last day
    game.perform(Action("delve_rest"))
    assert world.targets(rival, "located_in") == [town] and teams(world, occurrence)[0]["left"]
    assert [f for f in world.facts(predicate="delved") if f.subject == rival]
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_delvers.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.delvers'`.

- [ ] **Step 3: Write the delvers** — `systems/delvers.py`
```python
"""Rival delvers in full detail (phase 4f spec 4.3): the sects' bands inside with the player.

When the player enters, the bands chosen at the gate are placed inside (the strong deeper). After
each thing the player does, every band takes one step: it loots, fights a guardian, tries the
inheritance, moves on, or heads for the gate in time. Two rival bands in one chamber clash. A band
in the player's chamber bars the way until it lets them pass or is beaten; a hostile one may strike first.
"""

import systems.delve as D
import systems.realm_gates as G
import systems.secret_realms as SR
from systems import factions as F
from systems.attitude import attitude
from systems.facts import make_variant, place_name, record_fact
from systems.tournaments import alive, realm_of
from world.events import Event, commit, effect, listen
from world.seed import rng_for

GUARDIAN_BASE, GUARDIAN_PER_REALM = 0.5, 0.15
INHERIT_BASE, INHERIT_PER_REALM, INHERIT_BOUNDS = 0.1, 0.15, (0.02, 0.6)
CLASH_DEATH = 0.5
AMBUSH_CHANCE = 0.5
PASS_SCORE, WARM_SCORE = -0.3, 1.0
PROUD = frozenset({"proud", "hot-tempered"})


def _clamp(value: float, bounds) -> float:
    return min(bounds[1], max(bounds[0], value))


def _opening(world, player: int):
    pos = D.position(world, player)
    occurrence = SR.opening_of(world, pos["realm"]) if pos else None
    return world.entity(occurrence) if occurrence is not None else None


def members(world, team: dict, realm: int) -> list[int]:
    return [p for p in team["members"] if alive(world, p) and world.targets(p, "located_in") == [realm]]


def leader(world, team: dict) -> int:
    return max(team["members"], key=lambda p: (alive(world, p), realm_of(world, p), -p))


def rivals(world, team_a: dict, team_b: dict) -> bool:
    """Two bands fall on each other: sects at odds, or a proud member among them."""
    a, b = team_a["faction"], team_b["faction"]
    if a is not None and b is not None and a != b and F.stance(world, a, b) <= F.HOSTILE:
        return True
    return any(PROUD & set(world.entity(p).data.get("traits", ())) for p in team_a["members"] + team_b["members"])


# --- placing the bands ----------------------------------------------------------------------------------

def placement_events(world, occurrence) -> list[Event]:
    t = occurrence.data["data"]
    realm = world.entity(t["realm"])
    floors = realm.data["floors"]
    rng = rng_for(world.world_seed, f"realm:{occurrence.id}:placed")
    at = []
    for team in t["teams"]:
        floor = min(len(floors), max(1, max(realm_of(world, p) for p in team["members"])))
        chambers = floors[floor - 1]
        wanted = [c for c, room in enumerate(chambers) if room["kind"] == "rivals"] or list(range(len(chambers)))
        at.append([floor, rng.choice(wanted)])
    return [Event("delvers_placed", (), realm.id, {"occurrence": occurrence.id, "at": at})]


@effect("delvers_placed")
def _placed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    teams, inside = [], []
    for team, at in zip(t["teams"], event.data["at"]):
        for person in team["members"]:
            if alive(world, person):
                world.unrelate(person, "located_in")
                world.relate(person, event.place, "located_in")
                world.update_data(person, delve_at=at)
                inside.append(person)
        teams.append({**team, "at": at, "let_pass": [], "with": None, "with_floor": None, "left": False})
    world.update_data(occurrence.id, data={**t, "teams": teams, "placed": True, "entered": t["entered"] + inside})


@listen("realm_entered")
def _place_on_entry(world, event, event_id: int) -> None:
    occurrence = world.entity(event.data["occurrence"])
    if not occurrence.data["data"].get("placed") and occurrence.data["data"]["teams"]:
        commit(world, placement_events(world, occurrence))


# --- each step -----------------------------------------------------------------------------------------------

def step_events(world, player: int) -> list[Event]:
    occurrence = _opening(world, player)
    if occurrence is None or not occurrence.data["data"].get("placed"):
        return []
    t = occurrence.data["data"]
    realm = world.entity(t["realm"])
    floors = realm.data["floors"]
    pos = D.position(world, player)
    days = D.days_left(world, occurrence.id)
    rng = rng_for(world.world_seed, f"step:{occurrence.id}:{world.time}")
    moves, extra = [], []
    for i, team in enumerate(t["teams"]):
        alive_in = members(world, team, realm.id)
        if team.get("left") or not team.get("at") or not alive_in:
            continue
        f, c = team["at"]
        room = floors[f - 1][c]
        best = max(alive_in, key=lambda p: (realm_of(world, p), -p))
        step = {"team": i, "at": [f, c], "took": None, "slew": False, "left": False}
        if team.get("with") == player:
            step["at"] = [pos["floor"], pos["chamber"]]  # travelling together
        elif days <= f:  # time to make for the gate: a day a floor
            if f == 1 and c == 0:
                step["left"] = True
            else:
                step["at"] = [f, c - 1] if c > 0 else [f - 1, len(floors[f - 2]) - 1]
        elif room["kind"] == "treasure" and room["state"] == "untouched":
            step["took"] = room["contents"]["prize"]
        elif room["kind"] == "guardian" and room["state"] == "untouched":
            gap = realm_of(world, best) - room["contents"]["realm"]
            if rng.random() < _clamp(GUARDIAN_BASE + GUARDIAN_PER_REALM * gap, (0.05, 0.95)):
                step["slew"] = True
            else:
                weakest = min(alive_in, key=lambda p: (realm_of(world, p), p))
                extra.append(Event("died", (weakest, weakest), realm.id, {"cause": "realm", "world": True}))
        elif room["kind"] == "inheritance" and realm.data["inheritance_claimed_by"] is None \
                and [f, c] != [pos["floor"], pos["chamber"]]:
            shade = G.shade_realm(world, best)
            chance = _clamp(INHERIT_BASE + INHERIT_PER_REALM * (realm_of(world, best) - shade + 1), INHERIT_BOUNDS)
            if rng.random() < chance:
                extra.append(Event("inheritance_won", (best,), realm.id, {"realm": realm.id}))
        elif c < len(floors[f - 1]) - 1:
            step["at"] = [f, c + 1]
        elif room["kind"] == "stair" and f < len(floors):
            step["at"] = [f + 1, 0]
        moves.append(step)
    clashes = _clashes(world, t["teams"], moves, realm.id, rng)
    events = [Event("delvers_stepped", (), realm.id, {"occurrence": occurrence.id, "moves": moves, "clashes": clashes})]
    for clash in clashes:
        killer = leader(world, t["teams"][clash["winner"]])
        events += [Event("died", (killer, p), realm.id, {"cause": "realm", "world": True}) for p in clash["dead"]]
    return events + extra


def _clashes(world, teams: list, moves: list, realm: int, rng) -> list[dict]:
    """Two bands that end in one chamber and are at odds fight: by the realm gap, the losers die or flee."""
    where: dict = {}
    for step in moves:
        if not step["left"]:
            where.setdefault(tuple(step["at"]), []).append(step["team"])
    clashes = []
    for at, found in sorted(where.items()):
        if len(found) < 2:
            continue
        a, b = found[0], found[1]
        if not rivals(world, teams[a], teams[b]):
            continue
        ra, rb = (max(realm_of(world, p) for p in members(world, teams[i], realm)) for i in (a, b))
        winner = a if rng.random() < _clamp(0.5 + 0.15 * (ra - rb), (0.1, 0.9)) else b
        loser = b if winner == a else a
        dead = [p for p in members(world, teams[loser], realm) if rng.random() < CLASH_DEATH]
        clashes.append({"winner": winner, "loser": loser, "dead": dead, "at": list(at)})
    return clashes


@effect("delvers_stepped")
def _stepped(world, event) -> None:
    from systems.races import make_prize
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    teams = [dict(team) for team in t["teams"]]
    realm = t["realm"]
    gate = world.entity(realm).data["gate"]
    for step in d["moves"]:
        team = teams[step["team"]]
        f, c = team["at"]
        if step["took"] is not None:
            make_prize(world, leader(world, team), step["took"], f"realm:{realm}:{f}:{c}:{world.time}")
            D.set_chamber(world, realm, f, c, state="looted")
        if step["slew"]:
            D.set_chamber(world, realm, f, c, state="slain")
        team["at"] = step["at"]
        if team.get("with") is not None and team.get("with_floor") != step["at"][0]:
            team["with"], team["with_floor"] = None, None  # a floor together, and they go their own way
        if step["left"]:
            team["left"] = True
            for person in members(world, team, realm):
                world.unrelate(person, "located_in")
                world.relate(person, gate, "located_in")
                world.update_data(person, delve_at=None)
        else:
            for person in members(world, team, realm):
                world.update_data(person, delve_at=step["at"])
    for clash in d["clashes"]:
        loser = teams[clash["loser"]]
        f, c = loser["at"]
        loser["at"] = [f, c - 1] if c > 0 else ([f - 1, 0] if f > 1 else [f, c])  # the survivors flee back
        for person in members(world, loser, realm):
            if person not in clash["dead"]:
                world.update_data(person, delve_at=loser["at"])
    world.update_data(occurrence.id, data={**t, "teams": teams})


@listen("delvers_stepped")
def _came_out(world, event, event_id: int) -> None:
    """A band that reaches the gate tells of it (spec §5)."""
    d = event.data
    t = world.entity(d["occurrence"]).data["data"]
    realm = world.entity(t["realm"])
    gate = realm.data["gate"]
    for step in d["moves"]:
        if step["left"]:
            for person in t["teams"][step["team"]]["members"]:
                if alive(world, person):
                    variant = make_variant("delved", person, None, place=place_name(world, gate))
                    variant["realm_name"] = realm.name
                    record_fact(world, person, "delved", None, place=gate, weight=1.0, variant=variant)


@effect("inheritance_won")
def _won(world, event) -> None:
    realm = event.data["realm"]
    G.inherit(world, event.actors[0], realm)
    floors = world.entity(realm).data["floors"]
    D.set_chamber(world, realm, len(floors), len(floors[-1]) - 1, state="passed")


# --- the player and the bands -------------------------------------------------------------------------------

def here(world, player: int) -> list[int]:
    """The bands in the player's chamber (their indexes on the opening)."""
    occurrence = _opening(world, player)
    pos = D.position(world, player)
    if occurrence is None or not pos:
        return []
    t = occurrence.data["data"]
    return [i for i, team in enumerate(t["teams"]) if not team.get("left") and team.get("at") == [pos["floor"], pos["chamber"]]
            and members(world, team, t["realm"])]


def blocking(world, player: int) -> bool:
    occurrence = _opening(world, player)
    if occurrence is None:
        return False
    teams = occurrence.data["data"]["teams"]
    return any(player not in teams[i].get("let_pass", []) and teams[i].get("with") != player for i in here(world, player))


def _hostile_to(world, team: dict, player: int) -> bool:
    mine = [f for f, _, d in F.memberships(world, player) if d.get("status", "member") == "member"]
    return team["faction"] is not None and any(F.stance(world, team["faction"], f) <= F.HOSTILE for f in mine)


def pass_events(world, player: int, i: int) -> list[Event]:
    occurrence = _opening(world, player)
    team = occurrence.data["data"]["teams"][i]
    head = leader(world, team)
    granted = attitude(world, head, player).score > PASS_SCORE and not _hostile_to(world, team, player)
    return [Event("pass_asked", (player, head), D.position(world, player)["realm"],
                  {"occurrence": occurrence.id, "team": i, "granted": granted})]


@effect("pass_asked")
def _asked(world, event) -> None:
    d = event.data
    if d["granted"]:
        occurrence = world.entity(d["occurrence"])
        t = occurrence.data["data"]
        teams = [dict(team) for team in t["teams"]]
        teams[d["team"]]["let_pass"] = teams[d["team"]].get("let_pass", []) + [event.actors[0]]
        world.update_data(occurrence.id, data={**t, "teams": teams})


def rout_events(world, player: int, i: int) -> list[Event]:
    occurrence = _opening(world, player)
    head = leader(world, occurrence.data["data"]["teams"][i])
    return [Event("band_routed", (player, head), D.position(world, player)["realm"],
                  {"occurrence": occurrence.id, "team": i})]


@effect("band_routed")
def _routed(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    teams = [dict(team) for team in t["teams"]]
    teams[d["team"]]["let_pass"] = teams[d["team"]].get("let_pass", []) + [event.actors[0]]  # beaten, they give way
    world.update_data(occurrence.id, data={**t, "teams": teams})


def join_events(world, player: int, i: int) -> list[Event]:
    occurrence = _opening(world, player)
    team = occurrence.data["data"]["teams"][i]
    if attitude(world, leader(world, team), player).score < WARM_SCORE:
        return []
    return [Event("band_joined", (player, leader(world, team)), D.position(world, player)["realm"],
                  {"occurrence": occurrence.id, "team": i, "floor": D.position(world, player)["floor"]})]


@effect("band_joined")
def _joined(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    teams = [dict(team) for team in t["teams"]]
    teams[d["team"]].update({"with": event.actors[0], "with_floor": d["floor"]})
    world.update_data(occurrence.id, data={**t, "teams": teams})


def ambusher(world, player: int) -> int | None:
    """A band in your chamber that strikes first: hostile to you, or proud and stronger (chance 0.5)."""
    occurrence = _opening(world, player)
    if occurrence is None:
        return None
    teams = occurrence.data["data"]["teams"]
    for i in here(world, player):
        team = teams[i]
        if player in team.get("let_pass", []) or team.get("with") == player:
            continue
        head = leader(world, team)
        proud = PROUD & set(world.entity(head).data.get("traits", ())) and realm_of(world, head) > realm_of(world, player)
        if (attitude(world, head, player).score <= -1.0 or proud or _hostile_to(world, team, player)) \
                and rng_for(world.world_seed, f"ambush:{occurrence.id}:{i}:{world.time}").random() < AMBUSH_CHANCE:
            return head
    return None
```

- [ ] **Step 4: Edit the existing files** — `.patches/4f_task5.py`
```python
"""Task 5 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    Path(path).write_text(Path(path).read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


DELVE = "systems/delve.py"
edit(DELVE, '''BLOCKING = frozenset({"guardian", "rivals"})''',
     '''BLOCKING = frozenset({"guardian"})  # a band bars the way by being there, not by the chamber's kind (Task 5)''')
edit(DELVE, '''    barred = room["kind"] in BLOCKING and room["state"] == "untouched"''', '''    from systems.delvers import blocking
    barred = (room["kind"] in BLOCKING and room["state"] == "untouched") or blocking(world, player)''')

ENG = "engine/delve.py"
edit(ENG, '''    "fight_guardian", "slip_past", "attempt_trial", "face_shade", "take_remains",
})''', '''    "fight_guardian", "slip_past", "attempt_trial", "face_shade", "take_remains",
    "ask_pass", "fight_rival", "join_band",
})''')
edit(ENG, '''import systems.delve as D
''', '''import systems.delve as D
import systems.delvers as R
import systems.secret_realms as SR
from world.events import commit
''')
edit(ENG, '''    def _step(self, events: list, refusal: str):
        if not events:
            return self._turn([(refusal, "system")])
        lines = self._commit(events)
        return self._turn(lines + (self._delve_lines() if self._inside() else []))''', '''    def _step(self, events: list, refusal: str):
        if not events:
            return self._turn([(refusal, "system")])
        lines = self._commit(events)
        if self._inside():  # a band sharing your chamber may strike first; then every band takes its step (Task 5)
            foe = R.ambusher(self.world, self.player.id)
            if foe is not None:
                lines.append((f"{self.world.entity(foe).name} strikes without a word!", "red"))
                return self._turn(lines + self._start_duel(foe, "duel", purpose={"rival": R.here(self.world, self.player.id)[0]}))
            stepped = R.step_events(self.world, self.player.id)
            if stepped:
                commit(self.world, stepped)  # the world's events, not the player's: nothing to narrate
        return self._turn(lines + (self._delve_lines() if self._inside() else []))''')
edit(ENG, '''        for item in room["contents"].get("remains", []):''', '''        occurrence = SR.opening_of(world, realm.id)  # at any stage: the gate may have shut this very step
        for i in R.here(world, me):
            team = world.entity(occurrence).data["data"]["teams"][i]
            head = world.entity(R.leader(world, team))
            if me not in team.get("let_pass", []) and team.get("with") != me:
                out += [Choice(f"Ask {head.name} to let you pass", Action("ask_pass", i)),
                        Choice(f"Fight {head.name}", Action("fight_rival", i))]
            if team.get("with") is None and R.join_events(world, me, i):
                out.append(Choice(f"Travel with {head.name}'s band for a floor", Action("join_band", i)))
            out.append(Choice(f"Talk to {head.name}", Action("talk", head.id)))
        for item in room["contents"].get("remains", []):''')
append(ENG, '''


class RivalMixin:
    """The bands' verbs (Task 5): a Game base beside DelveMixin."""

    def _band(self, i):
        return isinstance(i, int) and i in R.here(self.world, self.player.id)

    def _do_ask_pass(self, i):
        if not self._band(i):
            return self._turn([("No band stands here.", "system")])
        lines = self._commit(R.pass_events(self.world, self.player.id, i))
        if R.blocking(self.world, self.player.id):
            foe = R.ambusher(self.world, self.player.id)
            if foe is not None:
                return self._turn(lines + self._start_duel(foe, "duel", purpose={"rival": i}))
        return self._turn(lines + self._delve_lines())

    def _do_fight_rival(self, i):
        if not self._band(i):
            return self._turn([("No band stands here.", "system")])
        occurrence = SR.opening_of(self.world, self._inside()["realm"])
        head = R.leader(self.world, self.world.entity(occurrence).data["data"]["teams"][i])
        return self._turn(self._start_duel(head, "duel", purpose={"rival": i}))

    def _do_join_band(self, i):
        events = R.join_events(self.world, self.player.id, i) if self._band(i) else []
        if not events:
            return self._turn([("They will not have you along.", "system")])
        return self._turn(self._commit(events) + self._delve_lines())

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        if "rival" in purpose and data.get("result") == "won" and self._inside() \\
                and purpose["rival"] in R.here(self.world, self.player.id):
            lines += self._commit(R.rout_events(self.world, self.player.id, purpose["rival"]))
        return lines
''')
edit("engine/game.py", '''class Game(ChamberMixin, DelveMixin, ''', '''class Game(RivalMixin, ChamberMixin, DelveMixin, ''')
edit("engine/game.py", '''from engine.delve import ChamberMixin, DelveMixin''', '''from engine.delve import ChamberMixin, DelveMixin, RivalMixin''')

append("narrate/realm_text.py", '''


@outcome("pass_asked", body_facts=False)
def _pass_asked(world, event):
    head = world.entity(event.actors[1]).name
    return ([f"{head} looks you over, then waves you by."] if event.data["granted"]
            else [f"{head} does not move from your path."]), {}


@summary("pass_asked")
def _pass_line(world, entry, names, place, other):
    return f"{'Was let pass by' if entry.data['granted'] else 'Was refused passage by'} {other} in {place}."


@outcome("band_routed", body_facts=False)
def _routed(world, event):
    return [f"{world.entity(event.actors[1]).name}'s band gives way before you."], {}


@summary("band_routed")
def _routed_line(world, entry, names, place, other):
    return f"Routed {other}'s band in {place}."


@outcome("band_joined", body_facts=False)
def _joined(world, event):
    return [f"You fall in with {world.entity(event.actors[1]).name}'s band."], {}


@summary("band_joined")
def _joined_line(world, entry, names, place, other):
    return f"Travelled with {other}'s band in {place}."
''')
append("narrate/grammar/realm.toml", '''
[pass_asked]
colour = "default"
lines = ["#realm_air#"]

[band_routed]
colour = "default"
lines = ["#realm_air#"]

[band_joined]
colour = "default"
lines = ["#realm_air#"]
''')
print("task 5 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4f_task5.py && .venv/Scripts/python.exe -m pytest tests/test_delvers.py -q -p no:cacheprovider`
Expected: `task 5 edits applied`, then `8 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: rival delvers - bands placed as you enter, a step for each of yours, clashes, a stolen inheritance, passage asked or fought for, ambushes"`

---
### Task 6: The gate closes on you: sealed in, the years inside, and the ways out

**Files:**
- Create: `systems/sealed.py`
- Modify (via `.patches/4f_task6.py`):
  - `systems/realm_gates.py`: an opening the player entered closes from what really happened inside; the sealed player walks on when the realm opens again; sealing leaves the player's own posts alone;
  - `systems/mortality.py`: the `sealed` cause of an ending;
  - `systems/delve.py`: one leaves only through an open gate;
  - `engine/delve.py` (`_step`): after each step the gate's clock is checked, so it closes on you when it should;
  - `engine/lineage.py`: the death screen of one lost to a realm shows its gate's land;
  - `engine/delve.py`: `SealedMixin`, the sealed player's choices;
  - `engine/game.py`: `SealedMixin` joins the `Game` bases;
  - `narrate/realm_text.py`, `narrate/grammar/realm.toml`: outcomes and journal lines.
- Test: `tests/test_sealed.py`

**Plan ruling for this task (plan ruling 17):** letting your heir carry on ends your sealed character's tale as a death "lost to the realm" (cause `sealed`), and the usual 4b succession follows. 4b's rules hold that every ancestor is dead and buried, so the sealed one does not walk out later as an NPC elder, which the spec had hoped.

**Interfaces:**
- Consumes:
  - Task 2: `G.stage_events`, `G.seal`, `G.walk_out_events`, `G.SEALED_GROWTH`, the `walked_out` and `realm_closed` events;
  - Task 3: `D.position`, `D.gate_open`, `DelveMixin`;
  - Task 5: the teams' `members`;
  - `mortality.death_events`, `bonds.candidates`, `realms.add_energy`, `time.advance`, `lives.SEASON`.
- Produces:
  - **`systems.sealed` (S):**
    - constants: `SEARCH_BASE = 0.05`, `SEARCH_PER_COMPREHENSION = 0.01`, `SEARCH_BOUNDS = (0.02, 0.4)`, `SEASON_GROWTH = 0.75` (energy-years a sealed season gives: three times a season's meditation);
    - `sealed_realm(world, player) -> int | None`;
    - `inside_closing_events(world, occurrence) -> list[Event]`;
    - `season_events`, `search_events`, `lost_events(world, player) -> list[Event]`;
    - `unseal_events(world, occurrence) -> list[Event]`.
  - **Events:**
    - `sealed_season` (`years`);
    - `exit_searched` (`found`);
    - `unsealed` (`occurrence`, `realm`).
  - **Verbs:** `sealed_cultivate`, `search_exit`, `heir_carry_on`.

- [ ] **Step 1: Write the failing test** — `tests/test_sealed.py`
```python
import pytest

import systems.delve as D
import systems.encounters as encounters
import systems.realm_gates as G
import systems.sealed as S
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_lineage, check_realms
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.bodies import load_body
from systems.creation import CreationChoice
from world.events import commit


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
    monkeypatch.setattr(G, "WANDERER_CHANCE", 0.0)
    monkeypatch.setattr(G, "near_sects", lambda world, gate: [])


def room(kind, **contents):
    return {"kind": kind, "state": "untouched", "contents": contents}


def opening(game, realm):
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    game.perform(Action("look"))
    return occurrence


def sealed_in(game, period=12, bands=()):
    """Enter a realm at the player's town (with these bands chosen at the gate), and stay until the gate closes."""
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None}, period=period,
                      floors=[[room("trial", trial="formation"), room("stair")], [room("inheritance")]])
    data = {**SR.opening_data(realm), "delvers": list(bands), "teams": [{"faction": None, "members": [b]} for b in bands]}
    commit(world, sky.start_events(world, "realm_opening", town, world.time, data))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    game.perform(Action("look"))
    game.perform(Action("enter_realm", realm))
    world.set_time(world.entity(occurrence).data["active"][1] + 1)
    game.perform(Action("look"))
    return realm, occurrence


def actions(turn):
    return [c.action for c in turn.all_choices]


def test_the_gate_closes_on_you_and_on_the_band_beside_you(game, monkeypatch):
    import systems.delvers as R
    monkeypatch.setattr(R, "step_events", lambda world, player: [])  # the band stays where it was put
    world, me, town = game.world, game.player.id, game.place.id
    rival = founding.make_person(world, "test:rival", town, occupation="wandering swordsman", age=25, realm="third-rate")
    realm, occurrence = sealed_in(game, bands=[rival])
    assert S.sealed_realm(world, me) == realm and me in world.entity(realm).data["sealed"]
    assert rival in world.entity(realm).data["sealed"] and world.entity(rival).data["sealed_in"]
    closed = [e for e in world.chronicle_of_kind("realm_closed") if e.data["occurrence"] == occurrence]
    assert closed and closed[0].data["fates"][str(me)] == "sealed"
    assert check_realms(world) == []


def test_a_sealed_season_cultivates_three_times_over(game):
    world, me = game.world, game.player.id
    realm, _ = sealed_in(game)
    assert Action("sealed_cultivate") in actions(game.perform(Action("look")))
    energy, when = load_body(world, me).energy_years, world.time
    game.perform(Action("sealed_cultivate"))
    assert world.time == when + W.SEASON and load_body(world, me).energy_years > energy


def test_the_sealed_walk_on_when_the_realm_opens_again(game):
    world, me = game.world, game.player.id
    realm, _ = sealed_in(game)
    world.set_time(world.time + 4 * W.SEASON)
    again = opening(game, realm)
    assert S.sealed_realm(world, me) is None and me in world.entity(again).data["data"]["entered"]
    assert D.position(world, me) is not None and me not in world.entity(realm).data["sealed"]
    assert check_realms(world) == []


def test_a_search_may_find_another_way_out(game, monkeypatch):
    monkeypatch.setattr(S, "SEARCH_BOUNDS", (1.0, 1.0))
    world, me, town = game.world, game.player.id, game.place.id
    realm, _ = sealed_in(game)
    game.perform(Action("search_exit"))
    assert world.targets(me, "located_in") == [town] and S.sealed_realm(world, me) is None
    assert D.position(world, me) is None and me not in world.entity(realm).data["sealed"]


def test_letting_your_heir_carry_on_ends_your_tale(game):
    from systems.agendas import _pair
    world, me, town = game.world, game.player.id, game.place.id
    pupil = founding.make_person(world, "test:pupil", town, occupation="apprentice", age=18)
    _pair(world, me, pupil, "disciple")
    realm, _ = sealed_in(game)
    game.perform(Action("heir_carry_on"))
    assert world.entity(me).data.get("dying", {}).get("cause") == "sealed"
    game.perform(Action("succeed", pupil))
    assert world.get_meta("player_id") == pupil and world.entity(me).data["dead"]
    assert world.targets(me, "buried_at") == [realm] and check_lineage(world) == []


def test_the_gate_closes_between_two_steps_and_no_one_walks_out(game):
    world, me, town = game.world, game.player.id, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None}, period=12,
                      floors=[[room("trial", trial="formation"), room("stair")], [room("inheritance")]])
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    game.perform(Action("look"))
    game.perform(Action("enter_realm", realm))
    world.set_time(world.entity(occurrence).data["active"][1] - 1)  # a watch before the gate closes
    game.perform(Action("delve_rest"))
    assert S.sealed_realm(world, me) == realm and check_realms(world) == []
    assert Action("leave_realm") not in actions(game.perform(Action("look")))


def test_a_one_off_realm_keeps_its_sealed(game):
    world, me = game.world, game.player.id
    realm, _ = sealed_in(game, period=None)
    found = actions(game.perform(Action("look")))
    assert Action("sealed_cultivate") not in found
    assert Action("search_exit") in found and Action("heir_carry_on") in found
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sealed.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.sealed'`.

- [ ] **Step 3: Write the sealed** — `systems/sealed.py`
```python
"""Sealed in (phase 4f spec 4.4): when the gate closes with the player inside.

An opening the player entered closes from what really happened: whoever is still inside is sealed,
the player too. Sealed, the player may cultivate a season at a time in the dense qi, search the
floors for another way out, or let their heir carry on (their tale ends: plan ruling 17). When the
realm opens again, the sealed player walks on through the open gate.
"""

import systems.lives as lives
import systems.realm_gates as G
from systems.bodies import load_body, save_body
from systems.factions import memberships
from systems.membership import set_membership
from systems.realms import add_energy
from systems.time import advance
from systems.tournaments import alive
from world.events import Event, effect
from world.seed import rng_for

SEARCH_BASE, SEARCH_PER_COMPREHENSION, SEARCH_BOUNDS = 0.05, 0.01, (0.02, 0.4)
SEASON_GROWTH = 0.75  # energy-years: three times a season's meditation


def sealed_realm(world, player: int) -> int | None:
    found = world.entity(player).data.get("sealed_in")
    return found["realm"] if found else None


def inside_closing_events(world, occurrence) -> list[Event]:
    """The gate closes on an opening the player entered: fates from what happened, not a roll (spec §4.4)."""
    t = occurrence.data["data"]
    if t["closed"]:
        return []
    realm = t["realm"]
    fates = {}
    for person in dict.fromkeys(t["delvers"] + t["entered"]):
        if not alive(world, person):
            fates[str(person)] = "dead"
        elif world.targets(person, "located_in") == [realm]:
            fates[str(person)] = "sealed"
    return [Event("realm_closed", (), occurrence.data["place"], {"occurrence": occurrence.id, "realm": realm,
                                                                "fates": fates, "loot": {}, "inherited": None})]


def unseal_events(world, occurrence) -> list[Event]:
    """The realm opens again: the sealed player is free to walk on (their place inside is where they left it)."""
    realm = world.entity(occurrence.data["data"]["realm"])
    player = world.get_meta("player_id")
    if player not in realm.data["sealed"] or not alive(world, player):
        return []
    return [Event("unsealed", (player,), realm.id, {"occurrence": occurrence.id, "realm": realm.id})]


def _free(world, player: int, realm: int) -> None:
    world.update_data(player, sealed_in=None)
    entity = world.entity(realm)
    world.update_data(realm, sealed=[p for p in entity.data["sealed"] if p != player])


@effect("unsealed")
def _unsealed(world, event) -> None:
    player, d = event.actors[0], event.data
    _free(world, player, d["realm"])
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "entered": t["entered"] + [player]})


def season_events(world, player: int) -> list[Event]:
    realm = sealed_realm(world, player)
    if realm is None or world.entity(realm).data["period"] is None:
        return []
    return [Event("sealed_season", (player,), realm, {"years": SEASON_GROWTH})]


@effect("sealed_season")
def _season(world, event) -> None:
    body = load_body(world, event.actors[0])
    add_energy(body, event.data["years"])
    save_body(world, event.actors[0], body)
    advance(world, lives.SEASON)


def search_events(world, player: int) -> list[Event]:
    realm = sealed_realm(world, player)
    if realm is None:
        return []
    comprehension = load_body(world, player).physique["comprehension"]
    chance = min(SEARCH_BOUNDS[1], max(SEARCH_BOUNDS[0], SEARCH_BASE + SEARCH_PER_COMPREHENSION * comprehension))
    found = rng_for(world.world_seed, f"search:{realm}:{player}:{world.time}").random() < chance
    return [Event("exit_searched", (player,), realm, {"realm": realm, "found": found})]


@effect("exit_searched")
def _searched(world, event) -> None:
    player, d = event.actors[0], event.data
    advance(world, lives.SEASON)
    if d["found"]:
        _free(world, player, d["realm"])
        world.unrelate(player, "located_in")
        world.relate(player, world.entity(d["realm"]).data["gate"], "located_in")
        world.update_data(player, delve=None)


def lost_events(world, player: int) -> list[Event]:
    """Let the heir carry on: the sealed one's tale ends here (plan ruling 17)."""
    from systems.mortality import death_events
    if sealed_realm(world, player) is None:
        return []
    return death_events(world, player, "sealed", None)
```

- [ ] **Step 4: Edit the existing files** — `.patches/4f_task6.py`
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


edit("systems/delve.py", '''            "leave": floor == 1}''', '''            "leave": floor == 1 and gate_open(world, realm.id) is not None}  # a shut gate lets no one out (Task 6)''')
edit("engine/delve.py", '''            stepped = R.step_events(self.world, self.player.id)
            if stepped:
                commit(self.world, stepped)  # the world's events, not the player's: nothing to narrate''', '''            stepped = R.step_events(self.world, self.player.id)
            if stepped:
                commit(self.world, stepped)  # the world's events, not the player's: nothing to narrate
            sky.observe(self.world, self.world.entity(self._inside()["realm"]).data["gate"])  # the gate may close now
            if self.world.entity(self.player.id).data.get("sealed_in"):
                return self._turn(lines + (self._special_look() or []))''')

GATES = "systems/realm_gates.py"
edit(GATES, '''    if stage == "aftermath":
        player = world.get_meta("player_id")
        if player not in occurrence.data["data"]["entered"]:
            return closing_events(world, occurrence)
    return []''', '''    if stage == "aftermath":
        player = world.get_meta("player_id")
        if player not in occurrence.data["data"]["entered"]:
            return closing_events(world, occurrence)
        from systems.sealed import inside_closing_events  # the player was inside: what happened, happened (Task 6)
        return inside_closing_events(world, occurrence)
    return []''')
edit(GATES, '''        return renew_events(world, occurrence) + walk_out_events(world, occurrence) + delver_events(world, occurrence)''',
     '''        from systems.sealed import unseal_events
        return (renew_events(world, occurrence) + walk_out_events(world, occurrence) + unseal_events(world, occurrence)
                + delver_events(world, occurrence))''')
edit(GATES, '''    world.relate(person, realm, "located_in")
    for faction, _, data in F.memberships(world, person):
        if data.get("status", "member") == "member":
            set_membership(world, person, faction, status="missing")''', '''    world.relate(person, realm, "located_in")
    for faction, _, data in ([] if world.entity(person).data.get("is_player") else F.memberships(world, person)):
        if data.get("status", "member") == "member":  # the player keeps their posts: their sect waits (Task 6)
            set_membership(world, person, faction, status="missing")''')

edit("engine/lineage.py", '''            town = self.world.entity(grave[0]) if grave else None
            if town is not None and town.kind == "town":''', '''            town = self.world.entity(grave[0]) if grave else None
            if town is not None and town.kind == "secret_realm":  # lost to a realm: its gate's land (4f)
                town = self.world.entity(town.data["gate"])
            if town is not None and town.kind == "town":''')
edit("systems/mortality.py", '''CAUSES = {''', '''CAUSES = {
    "sealed": "sealed in a secret realm",''')

ENG = "engine/delve.py"
edit(ENG, '''    "ask_pass", "fight_rival", "join_band",
})''', '''    "ask_pass", "fight_rival", "join_band",
    "sealed_cultivate", "search_exit", "heir_carry_on", "succeed", "new_world", "newcomer",
})''')
append(ENG, '''


class SealedMixin:
    """The sealed player's choices (Task 6): a Game base beside DelveMixin."""

    def _special_choices(self):
        import systems.sealed as S
        realm = S.sealed_realm(self.world, self.player.id)
        if realm is None or self.combat is not None or self.focus is not None or self.player.data.get("dying"):
            return super()._special_choices()
        choices = []
        if self.world.entity(realm).data["period"] is not None:
            choices.append(Choice("Cultivate a season in the dense qi", Action("sealed_cultivate")))
        choices += [Choice("Search the sealed floors for another way out (a season)", Action("search_exit")),
                    Choice("Let your heir carry on", Action("heir_carry_on")),
                    Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]
        return choices, []

    def _special_look(self):
        import systems.sealed as S
        realm = S.sealed_realm(self.world, self.player.id)
        if realm is None:
            return super()._special_look()
        entity = self.world.entity(realm)
        when = "It will open again when its season comes round." if entity.data["period"] is not None \\
            else "It will not open again."
        return [(f"You are sealed in {entity.name}. {when}", "heading")]

    def _do_sealed_cultivate(self, _target):
        import systems.sealed as S
        events = S.season_events(self.world, self.player.id)
        if not events:
            return self._turn([("There is no waiting this out.", "system")])
        lines = self._commit(events)
        return self._turn(lines + (self._special_look() or []))

    def _do_search_exit(self, _target):
        import systems.sealed as S
        events = S.search_events(self.world, self.player.id)
        if not events:
            return self._turn([("You are not sealed in anywhere.", "system")])
        self._commit(events)
        return self._do_look(None)

    def _do_heir_carry_on(self, _target):
        import systems.sealed as S
        events = S.lost_events(self.world, self.player.id)
        if not events:
            return self._turn([("You are not sealed in anywhere.", "system")])
        self._commit(events)
        return self._do_look(None)
''')
edit("engine/game.py", '''class Game(RivalMixin, ChamberMixin, DelveMixin, ''', '''class Game(SealedMixin, RivalMixin, ChamberMixin, DelveMixin, ''')
edit("engine/game.py", '''from engine.delve import ChamberMixin, DelveMixin, RivalMixin''',
     '''from engine.delve import ChamberMixin, DelveMixin, RivalMixin, SealedMixin''')

append("narrate/realm_text.py", '''


@outcome("sealed_season", body_facts=False)
def _season(world, event):
    return ["A season passes in the realm's thick qi. You grow; you grow older."], {}


@summary("sealed_season")
def _season_line(world, entry, names, place, other):
    return f"Cultivated a season sealed in {place}."


@outcome("exit_searched", body_facts=False)
def _searched(world, event):
    return (["Behind a cracked mural a draught of outside air: a way out."] if event.data["found"]
            else ["A season of searching finds only walls."]), {}


@summary("exit_searched")
def _searched_line(world, entry, names, place, other):
    return "Found a hidden way out of a sealed realm." if entry.data["found"] else "Searched a sealed realm for a way out."
''')
append("narrate/grammar/realm.toml", '''
[sealed_season]
colour = "default"
lines = ["#realm_air#"]

[exit_searched]
colour = "default"
lines = ["#realm_air#"]
''')
print("task 6 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4f_task6.py && .venv/Scripts/python.exe -m pytest tests/test_sealed.py -q -p no:cacheprovider`
Expected: `task 6 edits applied`, then `7 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: sealed in - the gate closes on who is still inside, seasons of cultivation, a hidden way out, the heir carries on, and walking on when the realm opens again"`

---
### Task 7: The screens: the realms page (F5), briefs, heralds, the sheet, the journal, help

**Files:**
- Create: `engine/realm_page.py`
- Modify (via `.patches/4f_task7.py`):
  - `engine/delve.py`: `realms`, the heralds' and the open gate's lines (each once), the realms you have seen, others heard on your floor;
  - `engine/commands.py`: `realms`; `engine/game.py`: the help line; `app.py`: F5;
  - `narrate/brief.py`: the gate town's scene facts;
  - `engine/sheet.py`: tokens and sealed status;
  - `narrate/realm_text.py`: `realm_facts`, and the last journal lines.
- Test: `tests/test_realm_screens.py`

**Interfaces:**
- Consumes:
  - Tasks 1–6: `SR.realms`, `SR.OPENINGS`, `SR.opening_of`, `SR.stage_of`, `G.tokens_of`, `D.position`, `D.gate_open`, `D.days_left`, `S.sealed_realm`;
  - `DelveMixin._delve_lines`, `_after_arrival`, `_after_look`;
  - `outcomes.SUMMARIES`.
- Produces:
  - **`engine.realm_page`:**
    - `known(world, player) -> list[int]`: realms the player has seen, entered, heard heralded, or heard tales of;
    - `realm_line(world, player, realm) -> str`, `realms_lines(world, player) -> list[Line]`, `sheet_realm_lines(world, player) -> list[Line]`.
  - **`narrate.realm_text`:** `realm_facts(world, town, player) -> list[str]`, `stage_words(world, occurrence, stage) -> str`.
  - **Player data:** `realms_seen` (realm ids), `realm_heralds` (`{str(occurrence): stage}`).
  - **Verb:** `realms` (F5).

- [ ] **Step 1: Write the failing test** — `tests/test_realm_screens.py`
```python
import time

import pytest

import systems.encounters as encounters
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from engine.realm_page import realms_lines
from engine.sheet import sheet_lines
from narrate.outcomes import SUMMARIES
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from world.events import commit


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
    monkeypatch.setattr(G, "WANDERER_CHANCE", 0.0)
    monkeypatch.setattr(G, "near_sects", lambda world, gate: [])


def texts(turn):
    return [t for t, _ in turn.lines]


def heralded(game, realm, here=True):
    """An opening of this realm, foretold; its gate in the player's town, or far away."""
    world = game.world
    town = game.place.id if here else world.entity(realm).data["gate"]
    world.update_data(realm, gate=town)
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    return W.index(world)[-1][W.ID]


def test_the_page_shows_only_the_realms_you_know(game):
    world, me = game.world, game.player.id
    far, other = SR.ensure_realms(world)[:2]
    lines = " ".join(texts(game.perform(Action("realms")))).lower()
    assert not any(world.entity(r).name.lower() in lines for r in (far, other))
    occurrence = heralded(game, far, here=False)
    gate = world.entity(far).data["gate"]
    variant = make_variant("phenomenon", gate, None, place=place_name(world, gate))
    variant.update(kind="realm_opening", stage="foretold", reading=None)
    fact = record_fact(world, gate, "phenomenon", None, place=gate, variant=variant, spread=False,
                       extra={"occurrence": occurrence, "until": world.time + 40 * 4})
    believe(world, me, fact, variant, None, 0.7, 2, "gossip")
    lines = " ".join(texts(game.perform(Action("realms")))).lower()
    assert world.entity(far).name.lower() in lines and "heralded" in lines and world.entity(other).name.lower() not in lines


def test_f5_opens_the_realms_page(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Watcher", world_seed=5)
    app.handle_key("f5", "")
    assert any("Secret realms" in t for t, _ in app.last_turn.lines)


def test_the_gate_town_hears_the_heralds_once_and_sees_the_gate_open(game):
    world = game.world
    realm = SR.ensure_realms(world)[0]
    occurrence = heralded(game, realm)
    assert any("Heralds" in t and world.entity(realm).name in t for t in texts(game.perform(Action("look"))))
    world.set_time(world.time + 1)
    assert not any("Heralds" in t for t in texts(game.perform(Action("look"))))
    world.set_time(world.entity(occurrence).data["active"][0])
    turn = game.perform(Action("look"))
    assert any("stands open" in t for t in texts(turn))
    facts = " ".join(f for b in game.last_briefs if b.kind == "scene" for f in b.facts)
    assert "stands open here" in facts and realm in game.player.data.get("realms_seen", [])


def test_the_sheet_shows_your_tokens_and_whether_you_are_sealed(game):
    world, me = game.world, game.player.id
    realm = SR.ensure_realms(world)[0]
    token = world.add_entity("treasure", "a jade token", {"kind": "token", "realm": realm, "used": False, "value": 120})
    world.relate(me, token, "owns")
    text = " ".join(t for t, _ in sheet_lines(world, me))
    assert "Jade tokens" in text and world.entity(realm).name in text and "Sealed" not in text
    world.update_data(me, sealed_in={"realm": realm, "season": 10})
    assert f"Sealed in {world.entity(realm).name}" in " ".join(t for t, _ in sheet_lines(world, me))


def test_every_realm_event_you_take_part_in_has_a_journal_line():
    for kind in ("realm_entered", "sneak_caught", "realm_left", "chamber_looted", "guardian_slipped", "guardian_slain",
                 "trial_attempted", "inheritance_claimed", "inheritance_failed", "remains_taken", "pass_asked",
                 "band_routed", "band_joined", "sealed_season", "exit_searched", "unsealed"):
        assert kind in SUMMARIES, kind


def test_a_save_reloaded_inside_a_realm_resumes_the_delve(game):
    world, me, town = game.world, game.player.id, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None})
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    world.set_time(world.entity(W.index(world)[-1][W.ID]).data["active"][0])
    game.perform(Action("look"))
    game.perform(Action("enter_realm", realm))
    path = world.path
    game.close()
    again = Game.load(path)
    try:
        turn = again.look()
        assert "floor 1 of" in texts(turn)[0] and Action("delve_rest") in [c.action for c in turn.all_choices]
    finally:
        again.close()


def test_help_names_the_realms(game):
    assert any("realms (F5)" in t for t in texts(game.perform(Action("help"))))


def test_the_realms_page_is_quick(game):
    world, me = game.world, game.player.id
    for realm in SR.ensure_realms(world):
        world.update_data(me, realms_seen=game.player.data.get("realms_seen", []) + [realm])
    for i in range(200):
        variant = make_variant("delved", me, None, place="somewhere")
        variant["realm_name"] = world.entity(SR.realms(world)[i % 3]).name
        fact = record_fact(world, me, "delved", None, place=game.place.id, variant=variant, spread=False)
        believe(world, me, fact, variant, None, 0.7, 2, "gossip")
    realms_lines(world, me)
    start = time.process_time()
    realms_lines(world, me)
    assert time.process_time() - start < 0.03
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_realm_screens.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'engine.realm_page'`.

- [ ] **Step 3: Write the page** — `engine/realm_page.py`
```python
"""The realms page (F5, phase 4f spec 6): the secret realms you know of, as far as you know them.

Built from what the player has seen (gates, the realms they entered: `realms_seen`) and believes (the
heralds' news of an opening, the tales survivors carry out), never from a realm nobody told them of.
"""

import systems.delve as D
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.world_events as W
from narrate.base import Line
from systems.facts import place_name
from world.gen.materialize import region_of

RULE_WORDS = {"ceiling": "the seal admits no one above {value}", "token": "a jade token opens the gate",
              "open": "open to anyone at the gate", "quota": "the near sects hold its places"}
TALES = frozenset({"delved", "took", "inherited", "sealed"})


def _beliefs(world, player: int):
    """(heralded realms: {realm: (occurrence, stage)}, tales: {realm name: [(predicate, actor)]}) from beliefs."""
    heralded, tales = {}, {}
    for belief, fact in world.known_facts_about([player], predicate="phenomenon"):
        occurrence = world.entity(fact.data.get("occurrence")) if fact.data.get("occurrence") else None
        if occurrence is not None and occurrence.data.get("type") in SR.OPENINGS:
            heralded[occurrence.data["data"]["realm"]] = (occurrence.id, belief.variant.get("stage"))
    for predicate in sorted(TALES):
        for belief, fact in world.known_facts_about([player], predicate=predicate):
            name = belief.variant.get("realm_name")
            if name:
                tales.setdefault(name, []).append((predicate, belief.variant.get("actor")))
    return heralded, tales


def known(world, player: int) -> list[int]:
    heralded, tales = _beliefs(world, player)
    seen = set(world.entity(player).data.get("realms_seen", []))
    return [r for r in SR.realms(world) if r in seen or r in heralded or world.entity(r).name in tales]


def realm_line(world, player: int, realm: int, heralded=None, tales=None) -> str:
    if heralded is None:
        heralded, tales = _beliefs(world, player)
    entity = world.entity(realm)
    gate = entity.data["gate"]
    rule = entity.data["rule"]
    words = RULE_WORDS[rule["kind"]].format(value=(rule["value"] or "").replace("-", " "))
    occurrence = D.gate_open(world, realm)
    if occurrence is not None and realm in world.entity(player).data.get("realms_seen", []):
        when = f"the gate stands open, closing in {D.days_left(world, occurrence)} days"
    elif realm in heralded:
        live = world.entity(heralded[realm][0])
        days = max(0, (live.data["active"][0] - world.time) // 4) if live is not None else 0
        when = f"heralded: its gate opens in about {days} days" if days else "heralded"
    else:
        when = "when it opens again, no one has told you"
    tokens = len(G.tokens_of(world, player, realm))
    told = tales.get(entity.name, [])
    heirs = [world.entity(actor).name for predicate, actor in told if predicate == "inherited" and actor is not None]
    inside = realm in world.entity(player).data.get("realms_seen", [])
    legacy = f"claimed by {heirs[0]}" if heirs else "unclaimed, as far as you know" if inside else "unknown"
    came_out = sum(1 for predicate, _ in told if predicate == "delved")
    return (f"  {entity.name[0].upper()}{entity.name[1:]}, its gate at {place_name(world, gate)} "
            f"({region_of(world, gate).name}): {words}; {when}. Inheritance: {legacy}."
            + (f" Your jade tokens: {tokens}." if tokens else "")
            + (f" You have heard of {came_out} who came out." if came_out else ""))


def realms_lines(world, player: int) -> list[Line]:
    lines: list[Line] = [("Secret realms", "heading")]
    heralded, tales = _beliefs(world, player)
    seen = set(world.entity(player).data.get("realms_seen", []))
    found = [r for r in SR.realms(world) if r in seen or r in heralded or world.entity(r).name in tales]
    if not found:
        return lines + [("  You know of no secret realm. Heralds cry their openings; survivors tell of them.", "dim")]
    return lines + [(realm_line(world, player, r, heralded, tales), "dim") for r in found]


def sheet_realm_lines(world, player: int) -> list[Line]:
    """The character sheet's jade tokens and, if it has come to that, where the player is sealed."""
    lines: list[Line] = []
    tokens = [world.entity(i) for i in world.targets(player, "owns")]
    tokens = [t for t in tokens if t is not None and t.kind == "treasure" and t.data.get("kind") == "token"
              and not t.data.get("used")]
    if tokens:
        names = ", ".join(sorted({world.entity(t.data["realm"]).name for t in tokens}))
        lines += [("", "default"), (f"Jade tokens: {len(tokens)} ({names})", "default")]
    sealed = world.entity(player).data.get("sealed_in")
    if sealed:
        lines.append((f"Sealed in {world.entity(sealed['realm']).name}", "red"))
    return lines
```

- [ ] **Step 4: Edit the existing files** — `.patches/4f_task7.py`
```python
"""Task 7 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    Path(path).write_text(Path(path).read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


TEXT = "narrate/realm_text.py"
append(TEXT, '''


def stage_words(world, occurrence, stage: str) -> str:
    """What the streets of the gate town say at an opening's stage."""
    name = world.entity(occurrence.data["data"]["realm"]).name
    if stage in ("foretold", "announced"):
        days = max(1, (occurrence.data["active"][0] - world.time + 3) // 4)
        return f"Heralds cry that the gate of {name} will open here in {days} days."
    return f"The gate of {name} stands open in this town."


def realm_facts(world, town: int, player: int) -> list[str]:
    """The scene's secret realm: a gate here, heralded or standing open (spec §6)."""
    import systems.secret_realms as SR
    import systems.world_events as W
    facts = []
    for realm in SR.realms(world):
        occurrence = SR.opening_of(world, realm)
        if occurrence is None or world.entity(realm).data["gate"] != town:
            continue
        live = world.entity(occurrence)
        stage = W.stage_at(live.data, world.time)
        if stage == "active":
            days = max(0, (live.data["active"][1] - world.time + 3) // 4)
            facts.append(f"The gate of {world.entity(realm).name} stands open here; it closes in {days} days.")
        elif stage in ("foretold", "announced"):
            facts.append(stage_words(world, live, stage))
    return facts


@summary("guardian_slipped")
def _slipped_line(world, entry, names, place, other):
    return f"{'Slipped past' if entry.data['passed'] else 'Was seen by'} a realm guardian in {place}."


@outcome("unsealed", body_facts=False)
def _unsealed(world, event):
    return [f"Light: the gate of {world.entity(event.data['realm']).name} stands open again."], {}


@summary("unsealed")
def _unsealed_line(world, entry, names, place, other):
    return f"Saw {world.entity(entry.data['realm']).name} open again after years sealed inside."
''')
append("narrate/grammar/realm.toml", '''
[unsealed]
colour = "gold"
lines = ["#realm_air#"]
''')

ENG = "engine/delve.py"
edit(ENG, '''    "delve_on", "delve_back", "leave_realm", "take_treasure", "delve_rest",
''', '''    "delve_on", "delve_back", "leave_realm", "take_treasure", "delve_rest", "realms",
''')
edit(ENG, '''        if others:
            lines.append(("Here: " + ", ".join(others) + ".", "dim"))
        return lines''', '''        if others:
            lines.append(("Here: " + ", ".join(others) + ".", "dim"))
        near = [p for p in people_at(self.world, realm.id, exclude=self.player.id)
                if not p.data.get("realm_spirit") and (p.data.get("delve_at") or [None])[0] == floor
                and p.data["delve_at"][:2] != [floor, c]]
        if near:
            lines.append(("You hear others somewhere on this floor.", "dim"))
        return lines

    def _realm_news(self) -> list:
        """The heralds of an opening here, and its gate standing open: each stage told once (spec §6)."""
        import systems.secret_realms as SR
        from narrate.realm_text import stage_words
        world, town = self.world, self.place.id
        before = dict(self.player.data.get("realm_heralds", {}))
        told, lines, seen = dict(before), [], list(self.player.data.get("realms_seen", []))
        for realm in SR.realms(world):
            occurrence = SR.opening_of(world, realm)
            if occurrence is None or world.entity(realm).data["gate"] != town:
                continue
            stage = SR.stage_of(world, occurrence)
            if stage in ("foretold", "announced", "active") and told.get(str(occurrence)) != stage:
                told[str(occurrence)] = stage
                lines.append((stage_words(world, world.entity(occurrence), stage), "dim"))
            if stage == "active" and realm not in seen:
                seen.append(realm)  # you have seen its gate: it is on your page now
        live = {str(SR.opening_of(world, r)) for r in SR.realms(world)}
        told = {k: v for k, v in told.items() if k in live}
        if told != before or seen != list(self.player.data.get("realms_seen", [])):
            world.update_data(self.player.id, realm_heralds=told, realms_seen=seen)
        return lines

    def _after_arrival(self) -> list:
        return super()._after_arrival() + ([] if self._inside() else self._realm_news())

    def _after_look(self) -> list:
        return super()._after_look() + ([] if self._inside() else self._realm_news())

    def _do_realms(self, _target):
        from engine.realm_page import realms_lines
        return self._turn(realms_lines(self.world, self.player.id))''')
edit(ENG, '''        self._commit(D.enter_events(self.world, realm, self.player.id, how))
        return self._do_look(None)''', '''        self._commit(D.enter_events(self.world, realm, self.player.id, how))
        seen = list(self.player.data.get("realms_seen", []))
        if realm not in seen:
            self.world.update_data(self.player.id, realms_seen=seen + [realm])
        return self._do_look(None)''')

edit("engine/commands.py", '''    "enter": Action("enter_realm"),''', '''    "realms": Action("realms"), "secret realms": Action("realms"), "enter": Action("enter_realm"),''')
edit("engine/game.py", '''    ("  tournaments (F11) | bracket | register | watch | odds | bet <fighter> <silver>", "system"),
''', '''    ("  tournaments (F11) | bracket | register | watch | odds | bet <fighter> <silver>", "system"),
    ("  realms (F5) | enter | deeper | up | leave realm", "system"),
''')
edit("app.py", '''        elif key == "f11":
            self.submit("tournaments")
''', '''        elif key == "f11":
            self.submit("tournaments")
        elif key == "f5":
            self.submit("realms")
''')
edit("narrate/brief.py", '''    facts += tournament_facts(world, place_id, player_id)
''', '''    facts += tournament_facts(world, place_id, player_id)
    from narrate.realm_text import realm_facts  # a secret realm's gate here (phase 4f)
    facts += realm_facts(world, place_id, player_id)
''')
edit("engine/sheet.py", '''    lines += sheet_tournament_lines(world, player_id)
''', '''    lines += sheet_tournament_lines(world, player_id)
    from engine.realm_page import sheet_realm_lines  # phase 4f
    lines += sheet_realm_lines(world, player_id)
''')
print("task 7 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4f_task7.py && .venv/Scripts/python.exe -m pytest tests/test_realm_screens.py -q -p no:cacheprovider`
Expected: `task 7 edits applied`, then `8 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: realm screens - the realms page (F5) as you know it, heralds and the open gate, briefs, tokens and sealing on the sheet, help"`

---
### Task 8: A realm season end to end: speed, the fork guide, the delver's fuzz

**Files:**
- Modify (via `.patches/4f_task8.py`):
  - `docs/world-events.md`: a section on secret realms;
  - `tests/test_tournaments.py`: the Assembly round's timing collects garbage first (plan ruling 20);
  - `tests/test_fuzz.py`: `test_a_realm_delver`;
  - `engine/seasons.py`: the founder's sect seasons are settled before the scene names anyone (plan ruling 23), with a test in `tests/test_seasons.py`;
  - `systems/rankings.py`, `debug/invariants.py`: a Young Dragon is judged by the age the Pavilion believed when it published the list (plan ruling 24).
- Test: `tests/test_realm_season.py`

**Interfaces:**
- Consumes (Tasks 1–7): `SR.ensure_realms`, `SR.due`, `SR.opening_data`, `G.closing_events`, `R.step_events`, the `delvers_placed` placement, `tests.test_fuzz.FIGHTING`, `keep_playing`.
- Produces: no new names; the fuzz and speed tests guard everything before them.

- [ ] **Step 1: Write the failing test** — `tests/test_realm_season.py`
```python
import time
from pathlib import Path

import pytest

import systems.encounters as encounters
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from world.events import commit
from world.gen.materialize import ensure_town


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


def room(kind, **contents):
    return {"kind": kind, "state": "untouched", "contents": contents}


def opening_with(game, bands, floors=None):
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    changes = {"gate": town, "rule": {"kind": "open", "value": None}}
    if floors:
        changes["floors"] = floors
    world.update_data(realm, **changes)
    teams = [{"faction": None, "members": list(b)} for b in bands]
    data = {**SR.opening_data(realm), "delvers": [p for b in bands for p in b], "teams": teams}
    commit(world, sky.start_events(world, "realm_opening", town, world.time, data))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    return realm, occurrence


def people(world, town, count, prefix):
    return [founding.make_person(world, f"test:{prefix}:{i}", town, occupation="wandering swordsman", age=25,
                                 realm="second-rate") for i in range(count)]


def test_a_delve_step_with_three_bands_inside_is_quick(game):
    world, town = game.world, game.place.id
    floors = [[room("trial", trial="formation"), room("treasure", prize={"kind": "herb", "name": "a herb", "value": 9}),
               room("guardian", species="stone lion", realm=2, guardian=None), room("stair")],
              [room("trial", trial="pressure"), room("stair")], [room("inheritance")]]
    bands = [people(world, town, 3, f"band{i}") for i in range(3)]
    realm, _ = opening_with(game, bands, floors)
    game.perform(Action("look"))
    game.perform(Action("enter_realm", realm))
    game.perform(Action("delve_rest"))
    start = time.process_time()
    game.perform(Action("delve_rest"))
    elapsed = time.process_time() - start
    assert elapsed < 0.04, f"a step took {elapsed * 1000:.0f} ms"


def test_a_closing_far_away_with_twelve_delvers_is_quick(game):
    world, town = game.world, game.place.id
    realm, occurrence = opening_with(game, [people(world, town, 3, f"sect{i}") for i in range(4)])
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, ensure_town(world, 5, 5, 0), "located_in")
    world.set_time(world.entity(occurrence).data["active"][1])
    start = time.process_time()
    commit(world, G.closing_events(world, world.entity(occurrence)))
    elapsed = time.process_time() - start
    assert world.entity(occurrence).data["data"]["closed"]
    assert elapsed < 0.01 + 0.0157, f"a closing took {elapsed * 1000:.0f} ms"  # 10 ms, and one tick of the CPU clock


def test_a_young_dragon_is_judged_by_the_age_believed_when_listed(game):
    import systems.rankings as R
    from debug.invariants import check_rankings
    from tests.test_rankings import deed, master, publish
    world, town = game.world, game.place.id
    youth = master(world, town, "test:youth", realm="second-rate", age=30)
    deed(world, youth, "tribulation", town, realm="second-rate", age=30)
    assert youth in publish(world)["lists"]["young"]
    world.set_time(world.time + R.YEAR)  # a year on, the Pavilion would think them 31; the list is last spring's
    world._rankings_checked = None
    assert check_rankings(world) == []


def test_the_fork_guide_covers_secret_realms():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("secret_realm", "realm_opening", "realm_awakening", "PLACES", "GUARDIANS", "TRIALS", "RULES_ANCIENT",
                 "CHAMBER_WEIGHTS", "check_realms", "sealed_in", "realm_spirit", "delve_at"):
        assert word in guide, word
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_realm_season.py -q -p no:cacheprovider`
Expected: 2 failed (`test_the_fork_guide_covers_secret_realms` with `AssertionError: secret_realm`, and `test_a_young_dragon_is_judged_by_the_age_believed_when_listed` with the rule's `#… is a Young Dragon but the Pavilion believes them older than 30`), 2 passed.

- [ ] **Step 3: Edit the existing files** — `.patches/4f_task8.py`
```python
"""Task 8 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    Path(path).write_text(Path(path).read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


append("docs/world-events.md", '''
## 7. Secret realms (phase 4f)

A secret realm is a lasting `secret_realm` entity (its gate town, its master and their art, its entry rule, its
period, its floors of chambers, its history). Its openings are two event types in the TOML:

- `realm_opening`: an `every = 1` type whose `places` hook names the gates of realms due this season (each realm
  keeps its own period, 12-40 seasons for the ancient ones); heralded like any phenomenon.
- `realm_awakening`: a trigger type, a newborn realm's first opening, started when a treasure light cracks a realm
  open (`secret_realms.CRACK_CHANCE`).

**The tables** in `systems/secret_realms.py`: `PLACES` and `EPITHETS` (names), `WEAPONS`, `GUARDIANS`, `TRIALS`,
`RULES_ANCIENT` and `RULES_NEWBORN` (the entry rules: ceiling, token, open, quota), and `CHAMBER_WEIGHTS` (what a
floor holds). The knobs of chance live beside the code that rolls them: `realm_gates` (tokens, who the sects send,
fates far away), `chambers` (guardians, trials), `delvers` (the bands inside) and `sealed` (the years inside).

**Saved state:**
- the meta row `secret_realms` lists every realm, ancient first;
- a person's `sealed_in` (`{"realm", "season"}`) marks them shut in until the next opening, and a sealed person is
  off the life clock until they walk out;
- the player's `delve` (`{"realm", "floor", "chamber"}`) is their place inside; a band member's `delve_at` is theirs;
- guardians, reflections and a master's remnant are `realm_spirit` persons who live inside.

**The rules:** `check_realms` in `debug/invariants.py` guards the inheritance (claimed once), who may be inside, the
ceiling, and the player's place inside.
''')

edit("tests/test_tournaments.py", '''    world.set_time(T.day_start(world.entity(occurrence), 2))
    start = time.process_time()
    T.resolve(world, occurrence)
    assert time.process_time() - start < 0.06''', '''    world.set_time(T.day_start(world.entity(occurrence), 2))
    import gc
    gc.collect()  # earlier tests' garbage is not this round's cost (4f ruling 20)
    start = time.process_time()
    T.resolve(world, occurrence)
    assert time.process_time() - start < 0.06''')

edit("engine/seasons.py", '''    def _after_look(self) -> list:
        return super()._after_look() + (self._sect_catch_up() if self._at_seat() else [])

    def _after_arrival(self) -> list:
        return super()._after_arrival() + (self._sect_catch_up() if self._at_seat() else [])''', '''    def _before_scene(self) -> None:
        super()._before_scene()
        if self._at_seat():  # settled before anyone is named: a season may send a member away (4f ruling 23)
            self._pending += self._sect_catch_up()''')
append("tests/test_seasons.py", '''


def test_the_sect_season_is_settled_before_the_scene_names_anyone(game):
    sect, town = found_sect(game)
    advance(game, 1)
    turn = game.perform(Action("look"))
    texts = [t for t, _ in turn.lines]
    [line] = [d["line"] for d in season_data(game, sect)][-1:]
    here = next(i for i, t in enumerate(texts) if t.startswith("Here:"))
    assert texts.index(line) < here  # the season (who left, who came) is told before the scene
''')

edit("systems/rankings.py", '''def believed_ages(world, pav: int) -> dict[int, int]:
    """How old the Pavilion thinks people are: the newest age it was told, plus the years since."""
    newest: dict = {}
    for belief, fact in world.known_facts(pav):
        who, age = belief.variant.get("actor"), belief.variant.get("age")
        if who is not None and age is not None and (who not in newest or fact.time > newest[who][1]):
            newest[who] = (age, fact.time)
    return {who: int(age + (world.time - t) // YEAR) for who, (age, t) in newest.items()}''', '''def believed_ages(world, pav: int, at: int | None = None) -> dict[int, int]:
    """How old the Pavilion thinks people are at `at` (default: now): the newest age it was told, plus the years since."""
    at = world.time if at is None else at
    newest: dict = {}
    for belief, fact in world.known_facts(pav):
        who, age = belief.variant.get("actor"), belief.variant.get("age")
        if who is not None and age is not None and fact.time <= at and (who not in newest or fact.time > newest[who][1]):
            newest[who] = (age, fact.time)
    return {who: int(age + (at - t) // YEAR) for who, (age, t) in newest.items()}''')
edit("debug/invariants.py", '''    ages = R.believed_ages(world, pav)
    for person in d["lists"].get("young", []):''', '''    published = world.chronicle_of_kind("rankings_published")  # judged as the Pavilion saw them then (4f ruling 24)
    ages = R.believed_ages(world, pav, published[-1].time if published else None)
    for person in d["lists"].get("young", []):''')

FUZZ = "tests/test_fuzz.py"
append(FUZZ, '''

@pytest.mark.parametrize("seed", [2, 9])
def test_a_realm_delver(tmp_path, seed, monkeypatch):
    """A secret realm opens wherever the delver stands, season after season: enter, delve, fight, leave, be sealed."""
    import systems.secret_realms as SR
    import systems.sky as sky
    import systems.world_events as W
    from world.events import commit
    monkeypatch.setitem(W.TYPES, "realm_opening", {**W.TYPES["realm_opening"],
                                                   "stages": {**W.TYPES["realm_opening"]["stages"], "foretold": 0,
                                                              "announced": 1, "active": 30, "aftermath": 3}})

    def open_here(world):
        """A realm opens where the delver stands, if none is open (the gate follows them)."""
        realm = SR.ensure_realms(world)[0]
        here = world.targets(world.get_meta("player_id"), "located_in")
        if not here or world.entity(here[0]).kind != "town" or SR.opening_of(world, realm) is not None:
            return
        world.update_data(realm, gate=here[0], rule={"kind": "open", "value": None})
        commit(world, sky.start_events(world, "realm_opening", here[0], world.time, SR.opening_data(realm)))
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Delver{seed}", world_seed=seed)
    happened = set()
    for step in range(300):
        game = app.game
        if step % 20 == 0:
            open_here(game.world)
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.5 and app.choices:
            stay = [n for n, c in enumerate(app.choices, 1) if c.action.verb not in ("travel", "routes", "leave_realm")]
            app.submit(str(rng.choice(stay or [1])))
        else:
            app.submit(rng.choice(["enter", "deeper", "deeper", "up", "realms", "look", "rest", "meditate week",
                                   "journal", "leave realm"]))
        if rng.random() < 0.05:
            app.handle_key("f5", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    assert {"realm_entered", "realm_closed"} <= happened, happened
    app.shutdown()
''')
print("task 8 edits applied")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4f_task8.py && .venv/Scripts/python.exe -m pytest tests/test_realm_season.py "tests/test_fuzz.py::test_a_realm_delver" -q -p no:cacheprovider`
Expected: `task 8 edits applied`, then `6 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: the 500-year soak passes (about 3 minutes).

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "feat: a realm season end to end - speed, the fork guide's secret realms, the delver's fuzz"`

---

## Self-review

- **Spec coverage:**
  - §2 (architecture, the realm entity, being inside, openings, level of detail): Tasks 1–3.
  - §3 (the delve: moving, the chambers, dying inside): Tasks 3–4.
  - §4 (entry rules and tokens, who the sects send, rivals in full detail, the gate closing, far away, newborn realms): Tasks 1, 2, 5 and 6.
  - §5 (knowledge vs truth): facts recorded where the deed was done (Tasks 2–5); pages and briefs from beliefs and what the player saw (Task 7).
  - §6 (screens): Tasks 3 and 7. §7 (debug rules 1–5): Tasks 2 and 3 (rule 3, tokens, is the 4d treasure rule: one owner or used).
  - §8 (testing): every task's tests, plus Task 8's speed, fuzz and guide.
- **Placeholders:** none; every step carries its code or its command.
- **Types:** each task's Interfaces block names what the tasks before it made; the dry run applied Tasks 1–8 in order on a copy of master and ran the full suite and the slow soak.
