# Phase 5e: The Dao Heart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The player's heart is shaped by what they do and weighs on how far they go: a steadiness and a lean moved by deeds; heart demons that rise at a breakthrough; epiphanies that open the daos of forms and elements, one completed being the return to the origin; oaths kept and broken; blades that wake a spirit or thirst from their making; and masters in the world who go mad with their demons or are enlightened.

**Architecture:**
- **The heart is person data** (`heart = {steady, lean, demons, daos, oaths}`), not the body. NPCs have none until something writes it; `heart.heart_of` reads a seeded one from their traits.
- **Deeds are listeners on events the world already makes,** from one table (`systems/data/heart_deeds.toml`) and a duel's verdict. Nothing already written is re-registered.
- **What the heart does is read where the rule lives:** a breakthrough's chance and deviation (2a), a fighter's blows (2b), a verdict (2b), the challengers in town (3b).
- **The world's side is 5c's and 5d's:** madness a lives agenda of one hash, the heart read only when it falls.

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-28-phase5e-dao-heart-design.md`

## Global Constraints

- **Save format:** no save-format version change. New state lives in:
  - person data `heart` and `mad_until`;
  - gear data `kills`, `fed_at` and `spirit`.
- **Knowledge vs truth:**
  - the player's own heart is told in words, never numbers; their demons by kind and whom;
  - NPC hearts are hidden; madness and oaths are facts that spread;
  - a blade's spirit is known after a season in hand, or when a smith of skill 3 reads it.
- **Reads never write:** pages, choices and blocks never write a heart; a seeded heart is read, not stored.
- **One effect per event kind:** new modules `@listen` or register hooks; no handler name is reused.
- **Seeded rolls stay where they were:** new rolls use their own seeded streams (`heart:`, `heart_trial:`, `stir:`, `epiphany:`, `curse:`, `madness:`, `mad_end:`), never the life clock's shared season stream.
- **A heart at rest changes nothing** (ruling 2): every older balance holds for a player who never meets 5e.
- **Speed (CPU time, averaged after `gc.collect()`):**
  - a season of 200 NPCs with the heart agenda stays within +10% of 5d's season;
  - `fighter_for` with a dao and a spirited blade stays within +10%;
  - the heart page and the oath menu are each under 20 ms;
  - the 500-year soak keeps its limits.
- **Commits:** every commit message ends with the session's Co-Authored-By attribution line.

## Review Focus

1. **A heart at rest changes no older balance:** the breakthrough and deviation effects pivot at 60, the heart's rest. Task 1 pins it with `test_a_steady_heart_breaks_through_more_easily_and_deviates_less`, and the whole suite's cultivation and phenomena tests hold unchanged.
2. **A fighter reads their gear at most twice an exchange** (5a's minors): the spirit reads the wielded item directly (ruling 16). Task 5's full suite pins it with `test_a_fighter_looks_at_their_gear_once_per_exchange`.
3. **The breakthrough keeps its roll:** a failed heart trial fails it without skipping the seeded draw, and a buried demon only shifts it. Task 2 pins it with `test_a_demon_faced_is_laid_to_rest_and_one_that_wins_fails_the_breakthrough`.
4. **The heart agenda stays cheap:** within +10% of 5d's season, measured on the same people rolled back. Task 8 pins it with `test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5ds`.
5. **Random play through oaths, demons, breakthroughs and a hungry blade:** no crash, no rule broken. Task 8 pins it with `test_a_troubled_heart`.

## Plan-time rulings (deviations from the spec, argued)

1. **The heart is person data, not part of the body,** so an NPC has none until written and a player's old save needs nothing. *Cost if wrong:* none.
2. **The heart's effects pivot at its rest (60), not at 50:** a breakthrough's chance moves `0.002 x (steady - 60)` (+0.08 to -0.12) and deviation `x (1 + (60 - steady) / 100)` (0.6 to 1.6). With the requirement unmet the shift is a tenth, as the chance is. A heart at rest then changes no older balance. *Cost if wrong:* the extremes are a little lopsided.
3. **Killing a foe broken in a fair duel moves nothing; killing one who yielded is ruthless and a guilt.** *Cost if wrong:* none.
4. **Only the player gathers demons from events;** an NPC's heart is its seeded steadiness, which is all madness reads. *Cost if wrong:* NPC demons are not named.
5. **Guilt for a desertion names the sect deserted.** *Cost if wrong:* none.
6. **Grief is eased where the dead lie:** 4b buries the dead where they fell (`buried_at`); three years ease it too. *Cost if wrong:* none.
7. **Amends are 100 silver to one of the dead one's kin,** easing that guilt a weight at a time; healing anyone eases the heaviest guilt by one. *Cost if wrong:* none.
8. **The heart trial is a scene before the roll,** only with a bottleneck to Second-rate or beyond; turning back costs nothing. *Cost if wrong:* none.
9. **Yin and yang are daos too,** since an art's element may be either; a neutral art and a heart method's inner form open none. *Cost if wrong:* none.
10. **A dao resonance is read as the place's `practice` factor above 1,** 4d's only modifier of practice. *Cost if wrong:* a later practice boost would count.
11. **A life-and-death fight's form is read from the duel's own start event** (its technique). *Cost if wrong:* none.
12. **Vengeance is kept by any hand; protection is broken only by a death at another's hand; abstinence by any kill of the player's.** *Cost if wrong:* none.
13. **Oaths are offered for grudges (vengeance), living kin (protection) and always abstinence.** *Cost if wrong:* a companion who is not kin cannot be protected by oath.
14. **A loyal spirit binds to the hand that woke it; its strength multiplies the blade's own, and only with the blade's form.** *Cost if wrong:* none.
15. **A cursed blade is read from its seed until its spirit is felt or read, then written with `cursed`.** *Cost if wrong:* none.
16. **A spirit reads the wielded item directly** (`gear.item_in`), not 5a's carried gear: 5a's minors hold a fighter to two looks at their gear an exchange, and the full suite found it. *Cost if wrong:* none.
17. **The mad are hateful:** they never spare, through the existing hateful path (3a's leaving for dead, 4b's killing). *Cost if wrong:* none.
18. **A master enlightened in a resonance opens the dao of their first art's form,** made if they had none yet. *Cost if wrong:* none.
19. **Amends and a blade's reading fold into one "Of the heart..." talk submenu,** and `tests/test_game.py`'s conversation test gains the verb. *Cost if wrong:* none.
20. **The breakthrough handler is `Game`'s own, not a mixin's,** so it asks the mixin's `_heart_trial` first. *Cost if wrong:* none.
21. **The duel's speed is measured on `fighter_for` with a dao and a spirit** (every exchange); the deed listeners run once a duel. *Cost if wrong:* none.

## Files

| File | Responsibility |
|---|---|
| `systems/data/heart_deeds.toml`, `systems/heart.py` | The heart: steadiness, lean, deeds, their effects and words. |
| `systems/demons.py` | Demons gathered, laid to rest, respects and amends; the heart trial. |
| `systems/daos.py` | Epiphanies, daos, their effects; the return to the origin. |
| `systems/oaths.py` | Oaths sworn, kept and broken; their news. |
| `systems/blade_spirits.py` | Kills, spirits waking, cursed blades, hunger, a smith's reading. |
| `systems/heart_world.py` | Madness and recovery; the enlightened. |
| `engine/heart.py`, `engine/heart_page.py` | `HeartMixin`: choices, menus, handlers, the trial; the heart page and the sheet's lines. |
| `narrate/heart_text.py`, `narrate/grammar/heart.toml` | Outcomes, journal lines, rumours. |

Existing files touched: `systems/cultivation.py`, `systems/duel.py`, `systems/events/dao_resonance.py`, `systems/world_clock.py`, `debug/invariants.py`, `engine/game.py`, `engine/commands.py`, `engine/sheet.py`, `narrate/outcomes.py`, `docs/world-events.md`, and the test `tests/test_game.py`.

**How each task is laid out:**
1. The tests, as whole new files.
2. The new modules, as whole files.
3. The run that shows what the edits must still do.
4. One patch script, `.patches/5e_taskN.py`, holding the task's edits to existing files (including files made by earlier tasks). Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: The heart

A person's heart is person data: `steady` 0-100 (at rest 60) and `lean` -100 (ruthless) to 100 (righteous). An NPC's is read from their seed and traits until something writes it. Deeds move it: the rows of `systems/data/heart_deeds.toml` and a duel's verdict. A deed that goes the way one leans steadies the heart; one against it makes it doubt twice as much. The heart weighs on a breakthrough and on deviation, pivoting at its rest (ruling 2); meditation brings it back. `check_heart` joins the rules.

**Files:**
- Create: `systems/data/heart_deeds.toml`
- Create: `systems/heart.py`
- Create: `tests/test_heart.py`
- Modify (by `.patches/5e_task1.py`): `systems/cultivation.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: 2a's `breakthrough_events`, `meditate_events`, `practise_events`; 2b's `duel_ended` verdicts; 4a's `lives.key`; the deeds of 3b, 4d, 4h, 5a, 5b and 5c named in the table.
- Produces:
  - `HT` (systems/heart.py): `DEEDS`, `START_STEADY`, `BOUNDS`, `LEAN_BOUND`, `LEAN_STEP`, `LEANING`, `DOUBT`, `SHAKEN`, `BREAKTHROUGH_STEP`, `REST_PER_WEEK`, `TRAIT_LEAN`, `TRAIT_STEADY`, `DUEL`, `KILL_YIELDED`, `STEADY_WORDS`, `LEAN_WORDS`; `seeded(world, person)`, `heart_of(world, person)`, `write(world, person)`, `steady(world, person)`, `lean(world, person)`, `shaken(world, person)`, `shift_steady(world, person, amount)`, `deed(world, person, way, weight)`, `breakthrough_shift(world, person)`, `deviation_factor(world, person)`, `steady_words(value)`, `lean_words(value)`.
  - `debug.invariants.check_heart(world)`; the heart's shift in 2a's breakthrough and deviation.

- [ ] **Step 1: Write the tests**

`tests/test_heart.py`:
```python
import pytest

import systems.encounters as encounters
import systems.heart as HT
from debug.invariants import check_heart
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.cultivation import breakthrough_events, meditate_events
from world.events import EFFECTS, LISTENERS, Event, commit


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


def someone(game, tag, traits):
    pid = game.world.add_entity("person", f"Someone {tag}", {"occupation": "tea seller", "traits": traits,
                                                              "realm": "mortal", "age": 40}, seed_path=f"test:heart:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_a_fresh_heart_is_steady_and_unaligned_and_reading_it_writes_nothing(game):
    world, me = game.world, game.player.id
    assert HT.heart_of(world, me) == {"steady": 60.0, "lean": 0.0, "demons": [], "daos": {}, "oaths": []}
    assert world.entity(me).data.get("heart") is None
    assert (HT.steady_words(60.0), HT.lean_words(0.0)) == ("steady", "unaligned")


def test_an_npc_heart_is_read_from_their_traits(game):
    world = game.world
    kind = someone(game, "kind", ["kind", "honest"])
    sly = someone(game, "sly", ["cunning", "greedy"])
    assert HT.lean(world, kind) >= 25 and HT.lean(world, sly) <= -25
    assert HT.heart_of(world, kind) == HT.heart_of(world, kind) and world.entity(kind).data.get("heart") is None
    temper = [HT.steady(world, someone(game, f"t{i}", ["hot-tempered", "proud"])) for i in range(6)]
    assert all(s <= 55 for s in temper)


def test_a_deed_moves_the_lean_and_steadies_or_shakes_a_leaning_heart(game):
    world, me = game.world, game.player.id
    HT.deed(world, me, 1, 2)
    assert HT.heart_of(world, me)["lean"] == 10.0 and HT.steady(world, me) == 60.0  # an unaligned heart: no doubt
    HT.write(world, me, lean=40.0)
    HT.deed(world, me, 1, 2)
    assert (HT.lean(world, me), HT.steady(world, me)) == (50.0, 62.0)
    HT.deed(world, me, -1, 3)
    assert (HT.lean(world, me), HT.steady(world, me)) == (35.0, 56.0)


def test_a_duels_verdict_is_a_deed(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe", ["proud"])
    for verdict, reason in (("spare", "yielded"), ("kill", "broken"), ("kill", "yielded"), ("rob", "broken")):
        HT._verdict(world, Event("duel_ended", (me, foe), game.place.id,
                                 {"result": "won", "by": "player", "verdict": verdict, "reason": reason}), 0)
    assert HT.lean(world, me) == 10.0 - 15.0 - 5.0


def test_every_deed_of_the_table_is_an_event_the_world_makes():
    for kind, row in HT.DEEDS.items():
        assert kind in EFFECTS or len(LISTENERS.get(kind, [])) > 1, kind
        assert row["actor"] >= 0 and row["lean"] in (1, -1) and 1 <= row["weight"] <= 3, kind


def test_meditation_brings_the_heart_back_to_rest(game):
    world, me = game.world, game.player.id
    HT.write(world, me, steady=40.0)
    commit(world, meditate_events(world, me, game.place.id, 14))
    assert HT.steady(world, me) == 42.0


def test_a_steady_heart_breaks_through_more_easily_and_deviates_less(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.bottleneck = True
    body.flags.append("sensed_qi")  # the way to Third-rate is open: the heart weighs in full
    save_body(world, me, body)
    HT.write(world, me, steady=100.0)
    high = breakthrough_events(world, me, game.place.id)[0].data["chance"]
    HT.write(world, me, steady=0.0)
    low = breakthrough_events(world, me, game.place.id)[0].data["chance"]
    assert high == pytest.approx(low + 0.2, abs=0.001)
    assert (HT.deviation_factor(world, me), HT.breakthrough_shift(world, me)) == (1.6, -0.12)
    HT.write(world, me, steady=60.0)
    assert (HT.deviation_factor(world, me), HT.breakthrough_shift(world, me)) == (1.0, 0.0)  # a heart at rest


def test_check_heart_flags_a_malformed_heart(game):
    world, me = game.world, game.player.id
    HT.write(world, me, steady=50.0)
    assert check_heart(world) == []
    HT.write(world, me, steady=140.0, lean=-300.0)
    assert "steadiness" in " | ".join(check_heart(world))
```

- [ ] **Step 2: Write the new modules**

`systems/data/heart_deeds.toml`:
```toml
# Deeds that move the dao heart (phase 5e spec 2). Each row is a kind of event: the actor whose heart it moves
# (an index into the event's actors), the way it leans (1 righteous, -1 ruthless) and how much it weighs (1-3).
# Duels are read in systems/heart.py: sparing, robbing, crippling and killing the yielded depend on the verdict.

[healed]            # treating the sick and hurt (5b)
actor = 0
lean = 1
weight = 1

[worms_killed]      # freeing one bound by a control pill (5c)
actor = 0
lean = 1
weight = 2

[debt_paid]         # a debt paid off for a debtor (3b)
actor = 0
lean = 1
weight = 1

[heirloom_returned] # a clan's heirloom handed home (5a)
actor = 0
lean = 1
weight = 2

[bounty_paid]       # a town kept from the beasts (4d)
actor = 0
lean = 1
weight = 1

[contract_poisoned] # poisoning for pay (5b)
actor = 0
lean = -1
weight = 3

[poison_slipped]    # poison slipped into a leader's cup (4h)
actor = 0
lean = -1
weight = 3

[hall_theft]        # a sect's pill hall robbed (5c)
actor = 0
lean = -1
weight = 2

[false_accusation]  # an innocent accused (4h)
actor = 0
lean = -1
weight = 2

[control_forced]    # a control pill forced down another's throat (5c)
actor = 0
lean = -1
weight = 3

[secret_sold]       # a sect's secret sold to its rival (5c)
actor = 0
lean = -1
weight = 1
```

`systems/heart.py`:
```python
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
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_heart.py`
Expected: `1 error`: collection stops: the tests import `check_heart`, which Step 4 adds.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5e_task1.py`:
```python
"""Phase 5e, Task 1: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/cultivation.py', r'''    if body.breakthrough_aid:  # a breakthrough pill's help (phase 5b)
        chance = min(0.95, round(chance + body.breakthrough_aid, 3))
''', r'''    if body.breakthrough_aid:  # a breakthrough pill's help (phase 5b)
        chance = min(0.95, round(chance + body.breakthrough_aid, 3))
    from systems.heart import breakthrough_shift  # phase 5e: a steady heart cuts through doubt (a tenth, unmet)
    shift = breakthrough_shift(world, pid) * (1.0 if met else 0.1)
    if shift:
        chance = max(0.0, min(max(chance, 0.95), round(chance + shift, 3)))
''')
edit('systems/cultivation.py', r'''    deviation = round(_deviation_from(body, heart_data, days) * deviation_factor(world, pid, place), 3) \
        if heart_data else 0.0''', r'''    from systems.heart import deviation_factor as heart_factor  # phase 5e: a troubled heart deviates more
    deviation = round(_deviation_from(body, heart_data, days) * deviation_factor(world, pid, place)
                      * heart_factor(world, pid), 3) if heart_data else 0.0''')
edit('systems/cultivation.py', r'''    deviation = _deviation_from(body, art, days) + (days * 1.5 if at_cap else 0.0)''', r'''    from systems.heart import deviation_factor as heart_factor  # phase 5e: a troubled heart deviates more
    deviation = (_deviation_from(body, art, days) + (days * 1.5 if at_cap else 0.0)) * heart_factor(world, pid)''')
edit('systems/world_clock.py', r'''import systems.meet  # noqa: E402,F401  phase 5d: the Meet of Hammer and Furnace
''', r'''import systems.meet  # noqa: E402,F401  phase 5d: the Meet of Hammer and Furnace
import systems.heart  # noqa: E402,F401  phase 5e: the dao heart, and the deeds that move it
''')
edit('debug/invariants.py', r'''    problems += check_crafts(world)
''', r'''    problems += check_crafts(world)
    problems += check_heart(world)
''')
edit('debug/invariants.py', r'''def check_toxins(world) -> list[str]:''', r'''def check_heart(world) -> list[str]:
    """Hearts in their bounds (phase 5e)."""
    out = []
    for person in world.entities_after("person", "heart.steady", -1):
        heart = person.data["heart"]
        if not 0 <= heart["steady"] <= 100 or not -100 <= heart["lean"] <= 100:
            out.append(f"{person.name} (#{person.id}) has a heart out of bounds: steadiness {heart['steady']}, "
                       f"lean {heart['lean']}")
    return out


def check_toxins(world) -> list[str]:''')
print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5e_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_heart.py`
Expected: `8 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1459 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the dao heart - a steadiness and a lean moved by deeds, weighing on breakthroughs and deviation"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 2: Heart demons and the heart trial

Guilt, grudges, fear and grief are gathered from duels, deaths, desertions and tribulations, at most five, and laid to rest by deeds: a grudge when its foe is beaten or dies, fear by a life-and-death fight won, grief at the grave (ruling 6) or with the years, guilt by amends and healing (ruling 7). At a breakthrough to Second-rate or beyond the heaviest rises (ruling 8): faced, it is laid to rest or fails the breakthrough; buried, it grows and weighs on it; turned back from, nothing is lost. A shaken heart stirs its worst demon in meditation.

**Files:**
- Create: `systems/demons.py`
- Create: `tests/test_demons.py`
- Modify (by `.patches/5e_task2.py`): `systems/cultivation.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Task 1's `heart`; 2b's `duel_ended`; 4b's `kin_of` and `buried_at`; 3b's `deserted`, `spy_exposed`; 4d's `tribulation`; 5b's `healed`.
- Produces:
  - `D` (systems/demons.py): `KINDS`, `MAX_DEMONS`, `MAX_WEIGHT`, `TRIAL_REALM`, `FACE_BASE`, `FACE_BOUNDS`, `FACED_STEADY`, `FACED_INSIGHT`, `FAILED_DEVIATION`, `BURIED_STEADY`, `BURIED_SHIFT`, `GRIEF_YEARS`, `AMENDS`, `STIR_CHANCE`, `STIR_DEVIATION`, `GRIEF_WEIGHT`, `CHOICES`; `demons(world, person)`, `add_demon(world, person, kind, whom, weight)`, `ease(world, person, kind, whom, by, every)`, `heaviest(world, person)`, `grief_passes(world, person)`, `season_hook(world, n)`, `respects_block(world, person, dead, place)`, `respects_events(world, person, dead, place)`, `amends_block(world, person, kin)`, `amends_events(world, person, kin, place)`, `rising(world, person)`, `face_chance(world, person, demon)`, `trial_events(world, person, place, choice)`; events `amends_made`, `demon_stirred`, `heart_trial`, `paid_respects`.
  - `cultivation.breakthrough_events(world, pid, place, fail=False, shift=0.0)`; demons in `check_heart`.

- [ ] **Step 1: Write the tests**

`tests/test_demons.py`:
```python
import pytest

import systems.demons as D
import systems.encounters as encounters
import systems.heart as HT
import systems.lives as lives
import systems.travel as travel
from debug.invariants import check_heart
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.cultivation import breakthrough_events, meditate_events
from systems.purse import silver_of
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=1000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def someone(game, tag):
    pid = game.world.add_entity("person", f"Someone {tag}", {"occupation": "tea seller", "traits": ["proud"],
                                                              "realm": "mortal", "age": 40}, seed_path=f"test:demon:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def duel(game, foe, **data):
    D._from_duel(game.world, Event("duel_ended", (game.player.id, foe), game.place.id, data), 0)


def at_the_gate(game):
    """A Third-rate body at its bottleneck, the way to Second-rate open."""
    body = load_body(game.world, game.player.id)
    body.realm, body.bottleneck, body.energy_years = 1, True, 5.0
    body.flags.append("sensed_qi")
    body.meridians["Governing"].state = "open"
    save_body(game.world, game.player.id, body)


def kinds(game):
    return sorted((d["kind"], d["weight"]) for d in D.demons(game.world, game.player.id))


def test_a_demon_for_the_same_cause_grows_and_the_lightest_goes_past_five(game):
    world, me = game.world, game.player.id
    D.add_demon(world, me, "grudge", 7, 1)
    D.add_demon(world, me, "grudge", 7, 1)
    assert kinds(game) == [("grudge", 2)]
    for whom in range(8, 13):
        D.add_demon(world, me, "guilt", whom, 3)
    assert len(D.demons(world, me)) == 5 and ("grudge", 2) not in kinds(game)


def test_a_beating_leaves_a_grudge_and_the_edge_of_death_a_fear_both_spent_by_winning(game):
    foe = someone(game, "foe")
    duel(game, foe, result="lost", by="opponent", verdict="rob")
    assert kinds(game) == [("grudge", 1)]
    duel(game, foe, result="lost", by="opponent", verdict="leave_for_dead", left_for_dead=True)
    assert kinds(game) == [("fear", 2), ("grudge", 3)]
    duel(game, foe, result="won", by="player", verdict="spare", reason="broken", life_and_death=True)
    assert kinds(game) == []


def test_killing_the_yielded_weighs_as_guilt_eased_by_amends_and_healing(game):
    world, me = game.world, game.player.id
    foe, widow = someone(game, "foe"), someone(game, "widow")
    world.relate(widow, foe, "kin_of", data={"role": "spouse"})
    duel(game, foe, result="won", by="player", verdict="kill", reason="yielded")
    assert kinds(game) == [("guilt", 2)]
    assert D.amends_block(world, me, someone(game, "stranger")) == "You owe them nothing."
    commit(world, D.amends_events(world, me, widow, game.place.id))
    assert kinds(game) == [("guilt", 1)] and silver_of(world, me) == 900 and silver_of(world, widow) >= 100
    D._from_healing(world, Event("healed", (me, widow), game.place.id, {}), 0)
    assert kinds(game) == []


def test_grief_for_the_dead_close_to_you_is_eased_at_their_grave_or_by_the_years(game):
    world, me, here = game.world, game.player.id, game.place.id
    wife, brother = someone(game, "wife"), someone(game, "brother")
    world.relate(me, wife, "kin_of", data={"role": "spouse"})
    world.relate(me, brother, "kin_of", data={"role": "sworn_sibling"})
    commit(world, [Event("died", (wife, wife), here, {"cause": "illness", "world": True}),
                   Event("died", (brother, brother), here, {"cause": "illness", "world": True})])
    assert kinds(game) == [("grief", 2), ("grief", 3)]
    elsewhere = next(r.dest for r in travel.routes_from(world, game.place))
    assert D.respects_block(world, me, wife, elsewhere) == "They do not lie here."  # the dead lie where they fell
    commit(world, D.respects_events(world, me, wife, here))
    assert kinds(game) == [("grief", 2)]
    world.set_time(world.time + D.GRIEF_YEARS * 4 * lives.SEASON)
    D.season_hook(world, 0)
    assert kinds(game) == []


def test_deserting_a_sect_weighs_as_guilt(game):
    world, me = game.world, game.player.id
    D._from_betrayal(world, Event("deserted", (me,), game.place.id, {"faction": 5, "status": "deserter"}), 0)
    assert D.demons(world, me)[0] | {"since": 0} == {"kind": "guilt", "whom": 5, "weight": 2, "since": 0}


def test_the_heaviest_demon_rises_only_at_the_gate_of_second_rate_or_beyond(game):
    world, me = game.world, game.player.id
    D.add_demon(world, me, "fear", None, 1)
    D.add_demon(world, me, "grudge", 7, 2)
    assert D.rising(world, me) is None
    at_the_gate(game)
    assert D.rising(world, me)["kind"] == "grudge"


def test_a_demon_faced_is_laid_to_rest_and_one_that_wins_fails_the_breakthrough(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    at_the_gate(game)
    D.add_demon(world, me, "grudge", 7, 2)
    D.add_demon(world, me, "fear", None, 1)
    monkeypatch.setattr(D, "FACE_BOUNDS", (1.0, 1.0))
    events = D.trial_events(world, me, here, "face")
    assert [e.kind for e in events] == ["heart_trial", "breakthrough"] and events[0].data["success"]
    insight = load_body(world, me).insight
    commit(world, events[:1])
    assert kinds(game) == [("fear", 1)] and HT.steady(world, me) == 70.0
    assert load_body(world, me).insight == insight + 10
    monkeypatch.setattr(D, "FACE_BOUNDS", (0.0, 0.0))
    events = D.trial_events(world, me, here, "face")
    assert not events[0].data["success"] and not events[1].data["success"]
    deviation = load_body(world, me).deviation
    commit(world, events[:1])
    assert load_body(world, me).deviation == pytest.approx(min(100.0, deviation + 20))


def test_a_buried_demon_grows_and_weighs_on_the_breakthrough_and_turning_back_costs_nothing(game):
    world, me, here = game.world, game.player.id, game.place.id
    at_the_gate(game)
    D.add_demon(world, me, "guilt", 7, 1)
    plain = breakthrough_events(world, me, here)[0].data["chance"]
    events = D.trial_events(world, me, here, "bury")
    assert events[1].data["chance"] == pytest.approx(max(0.0, plain - 0.1))
    commit(world, events[:1])
    assert kinds(game) == [("guilt", 2)] and HT.steady(world, me) == 55.0
    assert [e.kind for e in D.trial_events(world, me, here, "turn_back")] == ["heart_trial"]


def test_a_shaken_heart_stirs_its_demon_at_meditation(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    monkeypatch.setattr(D, "STIR_CHANCE", 1.0)
    HT.write(world, me, steady=10.0)
    D.add_demon(world, me, "grief", 3, 1)
    before = load_body(world, me).deviation
    commit(world, meditate_events(world, me, here, 7))
    assert any(e.kind == "demon_stirred" for e in world.chronicle_about(me, limit=5))
    assert load_body(world, me).deviation >= before + 10 - 1


def test_check_heart_flags_too_many_demons_or_a_stranger(game):
    world, me = game.world, game.player.id
    D.add_demon(world, me, "grief", 3, 1)
    assert check_heart(world) == []
    HT.write(world, me, demons=[{"kind": "envy", "whom": None, "weight": 4, "since": 0}] * 6)
    assert "demon" in " | ".join(check_heart(world))
```

- [ ] **Step 2: Write the new modules**

`systems/demons.py`:
```python
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
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_demons.py`
Expected: `3 failed, 7 passed`: the tests that need Step 4's breakthrough (`fail`, `shift`) fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5e_task2.py`:
```python
"""Phase 5e, Task 2: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/cultivation.py', r'''def breakthrough_events(world, pid: int, place: int) -> list[Event]:''', r'''def breakthrough_events(world, pid: int, place: int, fail: bool = False, shift: float = 0.0) -> list[Event]:
    """A breakthrough; a demon that won the heart trial fails it, a buried one weighs on it (phase 5e)."""''')
edit('systems/cultivation.py', r'''    shift = breakthrough_shift(world, pid) * (1.0 if met else 0.1)
    if shift:
        chance = max(0.0, min(max(chance, 0.95), round(chance + shift, 3)))
    success = rng.random() < chance''', r'''    shift += breakthrough_shift(world, pid) * (1.0 if met else 0.1)
    if shift:
        chance = max(0.0, min(max(chance, 0.95), round(chance + shift, 3)))
    success = rng.random() < chance and not fail''')
edit('systems/world_clock.py', r'''import systems.heart  # noqa: E402,F401  phase 5e: the dao heart, and the deeds that move it
''', r'''import systems.heart  # noqa: E402,F401  phase 5e: the dao heart, and the deeds that move it
import systems.demons  # noqa: E402,F401  phase 5e: heart demons, gathered, laid to rest, faced at a breakthrough
''')
edit('debug/invariants.py', r'''            out.append(f"{person.name} (#{person.id}) has a heart out of bounds: steadiness {heart['steady']}, "
                       f"lean {heart['lean']}")
''', r'''            out.append(f"{person.name} (#{person.id}) has a heart out of bounds: steadiness {heart['steady']}, "
                       f"lean {heart['lean']}")
        from systems.demons import KINDS, MAX_DEMONS, MAX_WEIGHT
        demons = heart.get("demons") or []
        if len(demons) > MAX_DEMONS or any(d.get("kind") not in KINDS or not 1 <= d.get("weight", 0) <= MAX_WEIGHT
                                           for d in demons):
            out.append(f"{person.name} (#{person.id}) carries a malformed demon or too many: {demons}")
''')
print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5e_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_demons.py`
Expected: `10 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1469 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: heart demons - guilt, grudges, fear and grief, laid to rest by deeds or faced at the gate"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 3: Epiphanies and daos

A dao of each martial form and each element, yin and yang among them (ruling 9), opens in epiphanies: practice in a dao resonance (ruling 10), an art brought to Great Completion, a life-and-death fight won (ruling 11), a bout watched, and meditation with a heart leaning hard. A shaken heart sees nothing. A dao speeds its arts' practice and sharpens their blows; one completed sets 2a's `returned_to_origin`, and Life-and-Death, unreachable until now, can be reached.

**Files:**
- Create: `systems/daos.py`
- Create: `tests/test_daos.py`
- Modify (by `.patches/5e_task3.py`): `systems/cultivation.py`, `systems/duel.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Task 1's `heart`; 2a's `practised`, `cultivated` and `realms.requirement`; 2b's `fighter_for` and duel start events; 4d's `world_events.factor`; 4e's `watched`.
- Produces:
  - `DA` (systems/daos.py): `DAOS`, `GAIN_BASE`, `GAIN_STEP`, `GAIN_BOUNDS`, `RESONANCE_CHANCE`, `DEATH_FIGHT_CHANCE`, `WATCH_CHANCE`, `LEANING_CHANCE`, `LEANING_AT`, `FIGHT_STEP`, `ORIGIN`; `daos(world, person)`, `dao(world, person, name)`, `gain(world, person)`, `epiphany_events(world, person, place, name, why)`, `practice_factor(world, person, form, element)`, `fight_factor(world, person, form)`; events `epiphany`.
  - `duel.dao_factor(world, person, form)`; the practice factor in 2a's practice; daos in `check_heart`.

- [ ] **Step 1: Write the tests**

`tests/test_daos.py`:
```python
from types import SimpleNamespace

import pytest

import systems.daos as DA
import systems.encounters as encounters
import systems.heart as HT
import systems.world_events as W
from debug.invariants import check_heart
from engine.game import Game
from systems import realms
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.cultivation import meditate_events, practise_events
from systems.duel import fighter_for
from systems.techniques import heart_method, known_arts, martial_arts
from world.events import Event, commit


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


def spear(game):
    return martial_arts(game.world, game.player.id)[0]  # the hunter's Hidden Crane Spear Art: spear, yang


def test_an_epiphany_opens_a_dao_by_comprehension_and_a_shaken_heart_sees_none(game):
    world, me, here = game.world, game.player.id, game.place.id
    [event] = DA.epiphany_events(world, me, here, "spear", "resonance")
    assert event.data["after"] == DA.gain(world, me) and GAIN_OK(DA.gain(world, me))
    commit(world, [event])
    assert DA.dao(world, me, "spear") == event.data["after"]
    HT.write(world, me, steady=10.0)
    assert DA.epiphany_events(world, me, here, "spear", "resonance") == []
    assert DA.epiphany_events(world, me, here, "neutral", "resonance") == []


def GAIN_OK(value):
    return DA.GAIN_BOUNDS[0] <= value <= DA.GAIN_BOUNDS[1]


def test_a_dao_completed_is_the_return_to_the_origin(game):
    world, me, here = game.world, game.player.id, game.place.id
    HT.write(world, me, daos={"sword": 0.99})
    commit(world, DA.epiphany_events(world, me, here, "sword", "fight"))
    body = load_body(world, me)
    assert DA.dao(world, me, "sword") == 1.0 and DA.ORIGIN in body.flags
    body.realm = 6
    assert realms.requirement(body, known_arts(world, me))[0]


def test_great_completion_opens_both_its_daos(game):
    world, me, here = game.world, game.player.id, game.place.id
    art = spear(game)
    DA._from_practice(world, Event("practised", (me,), here, {"technique_id": art.technique.id, "days": 7,
                                                             "mastered": True}), 1)
    assert set(DA.daos(world, me)) == {"spear", "yang"}


def test_practice_in_a_dao_resonance_brings_an_epiphany(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    monkeypatch.setattr(DA, "RESONANCE_CHANCE", 1.0)
    commit(world, practise_events(world, me, here, spear(game).technique.id))
    assert DA.daos(world, me) == {}
    monkeypatch.setattr(W, "factor", lambda world, place, key, at=None: 2.0 if key == "practice" else 1.0)
    commit(world, practise_events(world, me, here, spear(game).technique.id))
    assert "spear" in DA.daos(world, me)


def test_a_life_and_death_fight_won_and_a_bout_watched_bring_epiphanies_of_the_form(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    monkeypatch.setattr(DA, "DEATH_FIGHT_CHANCE", 1.0)
    monkeypatch.setattr(DA, "WATCH_CHANCE", 1.0)
    tech = spear(game).technique.id
    monkeypatch.setattr(world, "chronicle_entry", lambda i: SimpleNamespace(data={"technique": tech}))
    DA._from_fight(world, Event("duel_ended", (me, 99), here, {"result": "won", "by": "player", "duel": 5,
                                                               "life_and_death": True}), 1)
    assert "spear" in DA.daos(world, me)
    sword = world.add_entity("technique", "a sword art", {"form": "sword", "element": "metal"})
    occurrence = world.add_entity("sky", "a bout", {"data": {"arts": {"77": sword}}})
    DA._from_watching(world, Event("watched", (me, 77, 78), here, {"occurrence": occurrence, "winner": 77}), 2)
    assert "sword" in DA.daos(world, me)


def test_a_heart_leaning_hard_finds_its_element_in_meditation(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    monkeypatch.setattr(DA, "LEANING_CHANCE", 1.0)
    commit(world, meditate_events(world, me, here, 7))
    assert DA.daos(world, me) == {}
    HT.write(world, me, lean=-80.0)
    commit(world, meditate_events(world, me, here, 7))
    assert list(DA.daos(world, me)) == [heart_method(world, me).technique.data["element"]]


def test_a_dao_speeds_practice_and_sharpens_blows(game):
    world, me, here = game.world, game.player.id, game.place.id
    art = spear(game).technique.id
    plain = practise_events(world, me, here, art)[0].data
    plain_fighter = fighter_for(world, me, art)
    HT.write(world, me, daos={"yang": 0.5, "spear": 0.2})
    quick = practise_events(world, me, here, art)[0].data
    gained = lambda d: d["mastery_after"] - d["mastery_before"]
    assert gained(quick) == pytest.approx(gained(plain) * 1.5, rel=0.01)
    assert fighter_for(world, me, art).realm_mult == pytest.approx(plain_fighter.realm_mult * 1.02)


def test_check_heart_flags_a_dao_out_of_bounds(game):
    world, me = game.world, game.player.id
    HT.write(world, me, daos={"spear": 0.4})
    assert check_heart(world) == []
    HT.write(world, me, daos={"spear": 1.4, "moon": 0.1})
    assert "dao" in " | ".join(check_heart(world))
```

- [ ] **Step 2: Write the new modules**

`systems/daos.py`:
```python
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
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_daos.py`
Expected: `2 failed, 6 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5e_task3.py`:
```python
"""Phase 5e, Task 3: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/cultivation.py', r'''    gain *= W.factor(world, place, "practice")  # a dao resonance (phase 4d)
''', r'''    gain *= W.factor(world, place, "practice")  # a dao resonance (phase 4d)
    from systems.daos import practice_factor  # phase 5e: a dao of the art's form or element
    gain *= practice_factor(world, pid, art["form"], art["element"])
''')
edit('systems/duel.py', r'''        name=person.name, realm_mult=REALMS[body.realm].multiplier * _dark_boost(world, person_id)
        * fight_factor(world, person_id),  # phase 5d: the arrays where they stand''', r'''        name=person.name, realm_mult=REALMS[body.realm].multiplier * _dark_boost(world, person_id)
        * fight_factor(world, person_id)  # phase 5d: the arrays where they stand
        * dao_factor(world, person_id, form),  # phase 5e: the dao of the form they fight with''')
edit('systems/duel.py', r'''def fighter_for(world, person_id: int, technique_id: int | None) -> Fighter:''', r'''def dao_factor(world, person_id: int, form: str) -> float:
    from systems.daos import fight_factor as factor  # the daos come after the duel in the import graph
    return factor(world, person_id, form)


def fighter_for(world, person_id: int, technique_id: int | None) -> Fighter:''')
edit('systems/world_clock.py', r'''import systems.demons  # noqa: E402,F401  phase 5e: heart demons, gathered, laid to rest, faced at a breakthrough
''', r'''import systems.demons  # noqa: E402,F401  phase 5e: heart demons, gathered, laid to rest, faced at a breakthrough
import systems.daos  # noqa: E402,F401  phase 5e: epiphanies and the daos of forms and elements
''')
edit('debug/invariants.py', r'''            out.append(f"{person.name} (#{person.id}) carries a malformed demon or too many: {demons}")
''', r'''            out.append(f"{person.name} (#{person.id}) carries a malformed demon or too many: {demons}")
        from systems.daos import DAOS
        if any(name not in DAOS or not 0 <= value <= 1 for name, value in (heart.get("daos") or {}).items()):
            out.append(f"{person.name} (#{person.id}) has a dao out of bounds: {heart['daos']}")
''')
print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5e_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_daos.py`
Expected: `8 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1477 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: epiphanies and daos - forms and elements comprehended, and the return to the origin"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 4: Oaths on the heart

Vengeance on one the player holds a grudge against (three years), protection of kin (a year), abstinence from killing (a season), at most three open. Deaths decide most of them (ruling 12) and the seasons the rest. Kept, an oath steadies the heart; broken, it cracks it and leaves a heavy guilt. Each is a fact that spreads, and a broken oath is dishonour in the towns' eyes.

**Files:**
- Create: `systems/oaths.py`
- Create: `tests/test_oaths.py`
- Modify (by `.patches/5e_task4.py`): `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Tasks 1-2's `heart` and `demons`; 2c's `reputation.PATH_VALUE`; 3a's `record_fact`.
- Produces:
  - `O` (systems/oaths.py): `KINDS`, `MAX_OPEN`, `SWORN_STEADY`, `KEPT_STEADY`, `BROKEN_STEADY`, `KEPT_LEAN`, `BROKEN_GUILT`; `oaths(world, person)`, `grudges(world, person)`, `swear_block(world, person, kind, whom)`, `swear_events(world, person, kind, whom, place)`, `season_hook(world, n)`; events `oath_kept`, `oath_sworn`.
  - oaths in `check_heart`.

- [ ] **Step 1: Write the tests**

`tests/test_oaths.py`:
```python
import pytest

import systems.demons as D
import systems.encounters as encounters
import systems.heart as HT
import systems.oaths as O
import systems.reputation as reputation
from debug.invariants import check_heart
from engine.game import Game
from systems.creation import CreationChoice
from world.events import Event, commit


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


def someone(game, tag):
    pid = game.world.add_entity("person", f"Someone {tag}", {"occupation": "tea seller", "traits": ["proud"],
                                                              "realm": "mortal", "age": 40}, seed_path=f"test:oath:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def swear(game, kind, whom=None):
    commit(game.world, O.swear_events(game.world, game.player.id, kind, whom, game.place.id))


def dies(game, victim, killer=None):
    commit(game.world, [Event("died", (killer or victim, victim), game.place.id, {"cause": "killed", "world": True})])


def test_what_may_be_sworn(game):
    world, me = game.world, game.player.id
    foe, friend = someone(game, "foe"), someone(game, "friend")
    assert O.swear_block(world, me, "vengeance", foe) == "You bear them no grudge to avenge."
    D.add_demon(world, me, "grudge", foe, 2)
    assert O.swear_block(world, me, "vengeance", foe) is None
    assert O.swear_block(world, me, "protection", me) == "There is no one living to swear it for."
    assert O.swear_block(world, me, "abstinence", friend) == "Abstinence is sworn for no one."
    for kind, whom in (("vengeance", foe), ("protection", friend), ("abstinence", None)):
        swear(game, kind, whom)
    assert O.swear_block(world, me, "protection", foe) == "Three oaths already weigh on your heart."


def test_an_oath_sworn_steadies_the_heart_and_is_told(game):
    world, me = game.world, game.player.id
    swear(game, "abstinence")
    [oath] = O.oaths(world, me)
    assert oath["kind"] == "abstinence" and oath["until"] == world.time + O.KINDS["abstinence"]
    assert HT.steady(world, me) == 65.0 and world.facts("oath_sworn", subject=me)


def test_vengeance_is_kept_by_any_hand(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    D.add_demon(world, me, "grudge", foe, 2)
    swear(game, "vengeance", foe)
    dies(game, foe, someone(game, "stranger"))
    assert O.oaths(world, me) == [] and HT.steady(world, me) == 80.0 and world.facts("oath_kept", subject=me)


def test_a_protected_one_slain_or_an_abstinent_kill_breaks_the_oath(game):
    world, me = game.world, game.player.id
    friend, foe = someone(game, "friend"), someone(game, "foe")
    swear(game, "protection", friend)
    dies(game, friend, someone(game, "killer"))
    assert O.oaths(world, me) == [] and HT.steady(world, me) == 35.0
    assert any(d["kind"] == "guilt" and d["weight"] == 3 for d in D.demons(world, me))
    swear(game, "abstinence")
    dies(game, foe, me)
    assert O.oaths(world, me) == [] and len(world.facts("oath_broken", subject=me)) == 2


def test_the_seasons_settle_oaths_whose_time_ran_out(game):
    world, me = game.world, game.player.id
    foe, friend = someone(game, "foe"), someone(game, "friend")
    D.add_demon(world, me, "grudge", foe, 2)
    swear(game, "vengeance", foe)
    swear(game, "protection", friend)
    world.set_time(world.time + O.KINDS["protection"])
    commit(world, O.season_hook(world, 0))
    assert [o["kind"] for o in O.oaths(world, me)] == ["vengeance"] and HT.lean(world, me) == 10.0
    world.set_time(world.time + O.KINDS["vengeance"])
    commit(world, O.season_hook(world, 0))
    assert O.oaths(world, me) == [] and world.facts("oath_broken", subject=me)


def test_a_broken_oath_is_dishonour():
    assert reputation.PATH_VALUE["oath_broken"] < 0 < reputation.PATH_VALUE["oath_kept"]


def test_check_heart_flags_a_malformed_oath(game):
    world, me = game.world, game.player.id
    swear(game, "abstinence")
    assert check_heart(world) == []
    HT.write(world, me, oaths=[{"kind": "silence", "whom": None, "until": 0, "sworn_at": 0}] * 4)
    assert "oath" in " | ".join(check_heart(world))
```

- [ ] **Step 2: Write the new modules**

`systems/oaths.py`:
```python
"""Oaths sworn on the dao heart (phase 5e spec 5): vengeance, protection and abstinence, kept or broken.

An oath is `{kind, whom, until, sworn_at}` in the heart's `oaths`, at most three open. Deaths decide most of them
(a listener); the season settles the rest when their time runs out. Swearing, keeping and breaking are facts that
spread, and a broken oath is dishonour in the towns' eyes (2c's path values).
"""

import systems.demons as D
import systems.heart as HT
import systems.lives as lives
import systems.reputation as reputation
import systems.world_clock as world_clock
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, commit, effect, listen

KINDS = {"vengeance": 3 * 4 * lives.SEASON, "protection": 4 * lives.SEASON, "abstinence": lives.SEASON}
MAX_OPEN = 3
SWORN_STEADY, KEPT_STEADY, BROKEN_STEADY = 5.0, 15.0, -30.0
KEPT_LEAN = {"protection": 10.0}
BROKEN_GUILT = 3
reputation.PATH_VALUE.update({"oath_broken": -0.6, "oath_kept": 0.4})


def oaths(world, person: int) -> list[dict]:
    return list(HT.heart_of(world, person)["oaths"])


def grudges(world, person: int) -> list[int]:
    return [d["whom"] for d in D.demons(world, person) if d["kind"] == "grudge" and isinstance(d["whom"], int)]


def swear_block(world, person: int, kind: str, whom) -> str | None:
    if kind not in KINDS:
        return "There is no such oath."
    open_ = oaths(world, person)
    if len(open_) >= MAX_OPEN:
        return "Three oaths already weigh on your heart."
    if any(o["kind"] == kind and o["whom"] == whom for o in open_):
        return "You have sworn that already."
    if kind == "abstinence":
        return None if whom is None else "Abstinence is sworn for no one."
    target = world.entity(whom) if isinstance(whom, int) else None
    if target is None or target.kind != "person" or target.data.get("dead") or whom == person:
        return "There is no one living to swear it for."
    if kind == "vengeance" and whom not in grudges(world, person):
        return "You bear them no grudge to avenge."
    return None


def swear_events(world, person: int, kind: str, whom, place) -> list[Event]:
    return [Event("oath_sworn", (person,) + ((whom,) if whom is not None else ()), place,
                  {"kind": kind, "whom": whom, "until": world.time + KINDS[kind]})]


@effect("oath_sworn")
def _sworn(world, event) -> None:
    person, d = event.actors[0], event.data
    HT.write(world, person, oaths=oaths(world, person) + [{"kind": d["kind"], "whom": d["whom"], "until": d["until"],
                                                           "sworn_at": world.time}])
    HT.shift_steady(world, person, SWORN_STEADY)


def _end(world, person: int, oath: dict, kept: bool, place) -> Event:
    return Event("oath_kept" if kept else "oath_broken", (person,) + ((oath["whom"],) if oath["whom"] else ()),
                 place, {"kind": oath["kind"], "whom": oath["whom"], "sworn_at": oath["sworn_at"]})


def _close(world, event) -> None:
    person, d = event.actors[0], event.data
    HT.write(world, person, oaths=[o for o in oaths(world, person)
                                   if not (o["kind"] == d["kind"] and o["whom"] == d["whom"])])


@effect("oath_kept")
def _kept(world, event) -> None:
    person = event.actors[0]
    _close(world, event)
    HT.shift_steady(world, person, KEPT_STEADY)
    if event.data["kind"] in KEPT_LEAN:
        HT.write(world, person, lean=min(HT.LEAN_BOUND, HT.lean(world, person) + KEPT_LEAN[event.data["kind"]]))


@effect("oath_broken")
def _broken(world, event) -> None:
    person = event.actors[0]
    _close(world, event)
    HT.shift_steady(world, person, BROKEN_STEADY)
    D.add_demon(world, person, "guilt", event.data["whom"], BROKEN_GUILT)


@listen("died")
def _decided_by_death(world, event, event_id: int) -> None:
    """Vengeance done by any hand; a protected one slain; an abstinent hand that kills."""
    killer, victim = event.actors[0], event.actors[-1]
    player = world.get_meta("player_id")
    if player is None or player == victim or world.entity(player) is None:
        return
    ends = []
    for oath in oaths(world, player):
        if oath["kind"] == "vengeance" and oath["whom"] == victim:
            ends.append(_end(world, player, oath, True, event.place))
        elif oath["kind"] == "protection" and oath["whom"] == victim and killer != victim:
            ends.append(_end(world, player, oath, False, event.place))
        elif oath["kind"] == "abstinence" and killer == player:
            ends.append(_end(world, player, oath, False, event.place))
    commit(world, ends)


def season_hook(world, n: int) -> list[Event]:
    """Oaths whose time has run out: vengeance undone is broken, protection and abstinence kept."""
    player = world.get_meta("player_id")
    if player is None or world.entity(player) is None or not world.entity(player).data.get("heart"):
        return []
    here = next(iter(world.targets(player, "located_in")), None)
    return [_end(world, player, o, o["kind"] != "vengeance", here) for o in oaths(world, player)
            if o["until"] <= world.time]


world_clock.SEASON_HOOKS.append(season_hook)


# --- the news -----------------------------------------------------------------------------------------------------

@listen("oath_sworn")
@listen("oath_kept")
@listen("oath_broken")
def _news(world, event, event_id: int) -> None:
    person, d = event.actors[0], event.data
    variant = make_variant(event.kind, person, d["whom"], place=place_name(world, event.place))
    variant["oath"] = d["kind"]
    record_fact(world, person, event.kind, d["whom"], place=event.place, source_event=event_id,
                weight=1.5 if event.kind == "oath_broken" else 1.0, variant=variant)
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_oaths.py`
Expected: `1 failed, 6 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5e_task4.py`:
```python
"""Phase 5e, Task 4: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.daos  # noqa: E402,F401  phase 5e: epiphanies and the daos of forms and elements
''', r'''import systems.daos  # noqa: E402,F401  phase 5e: epiphanies and the daos of forms and elements
import systems.oaths  # noqa: E402,F401  phase 5e: oaths sworn on the heart, kept and broken
''')
edit('debug/invariants.py', r'''            out.append(f"{person.name} (#{person.id}) has a dao out of bounds: {heart['daos']}")
''', r'''            out.append(f"{person.name} (#{person.id}) has a dao out of bounds: {heart['daos']}")
        from systems.oaths import KINDS as OATHS, MAX_OPEN
        oaths = heart.get("oaths") or []
        if len(oaths) > MAX_OPEN or any(o.get("kind") not in OATHS for o in oaths):
            out.append(f"{person.name} (#{person.id}) holds a malformed oath or too many: {oaths}")
''')
print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5e_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_oaths.py`
Expected: `7 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1484 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: oaths on the dao heart - vengeance, protection and abstinence, kept or broken"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 5: Weapon spirits and cursed blades

A blade counts its kills; at twelve (a named masterwork at six, grade 2 or more) a spirit wakes, loyal or bloodthirsty as its wielder's heart leans. A loyal spirit binds to that hand (ruling 14); a bloodthirsty one lends anyone strength, whispers when unfed a season, and in a troubled hand will not spare. One famous blade in five is cursed from its making (ruling 15). A season in hand tells the spirit; so does a smith of skill 3 or more.

**Files:**
- Create: `systems/blade_spirits.py`
- Create: `tests/test_blade_spirits.py`
- Modify (by `.patches/5e_task5.py`): `systems/duel.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Task 1's `heart`; 5a's `gear.item_in`, `famous_weapons`; 2b's `fighter_for` and `verdict_events`; 5d's `craft_world.crafter` and `skill`.
- Produces:
  - `BS` (systems/blade_spirits.py): `WAKE_KILLS`, `MASTERWORK_KILLS`, `WAKE_GRADE`, `NATURES`, `BLOODTHIRSTY_LEAN`, `LOYAL_STEP`, `BOND_STEP`, `THIRST`, `CURSED_SHARE`, `HUNGER_STEADY`, `DRY_STEADY`, `TELLING_SKILL`; `cursed(world, item)`, `spirit_of(world, item_id)`, `wielded(world, person)`, `blade_factor(world, person, form)`, `refuses_spare(world, person)`, `known(world, person, item_id)`, `season_hook(world, n)`, `tell_block(world, person, smith, item_id)`, `tell_events(world, person, smith, item_id, place)`; events `blade_read`, `blade_whispered`, `spirit_felt`, `spirit_woke`.
  - `duel.blade_factor(world, person, form)`; the refused mercy in `verdict_events`; `debug.invariants.check_spirits(world)`.

- [ ] **Step 1: Write the tests**

`tests/test_blade_spirits.py`:
```python
import pytest

import systems.blade_spirits as BS
import systems.encounters as encounters
import systems.gear as gear
import systems.heart as HT
import systems.lives as lives
from debug.invariants import check_spirits
from engine.game import Game
from systems.creation import CreationChoice
from systems.duel import Duel, fighter_for, verdict_events
from systems.famous import famous_weapons, make_famous
from systems.techniques import martial_arts
from world.events import Event, commit


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


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["proud"], "realm": "mortal", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:spirit:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def spear(game, grade=2, **extra):
    item = gear.make_item(game.world, "weapon", "spear", grade, game.player.id, "bought", **extra)
    commit(game.world, gear.wield_events(game.world, game.player.id, item, game.place.id))
    return item


def kill(game, n, tag="v"):
    for i in range(n):
        victim = someone(game, f"{tag}{i}")
        commit(game.world, [Event("died", (game.player.id, victim), game.place.id, {"cause": "killed"})])


def test_a_blade_counts_its_kills_and_a_spirit_wakes_at_twelve(game):
    world = game.world
    item = spear(game)
    kill(game, 11)
    assert world.entity(item).data["kills"] == 11 and BS.spirit_of(world, item) is None
    kill(game, 1, "w")
    spirit = BS.spirit_of(world, item)
    assert spirit["nature"] == "loyal" and spirit["master"] == game.player.id and spirit["bond"] == 0.0


def test_a_named_masterwork_wakes_at_six_and_a_poor_blade_never(game):
    world, me = game.world, game.player.id
    poor = spear(game, grade=1)
    kill(game, 13, "p")
    assert BS.spirit_of(world, poor) is None
    named = spear(game, grade=3, forged_by=me, famous=True)
    kill(game, 6, "n")
    assert BS.spirit_of(world, named) is not None


def test_a_ruthless_hand_wakes_a_bloodthirsty_spirit(game):
    world, me = game.world, game.player.id
    HT.write(world, me, lean=-40.0)
    item = spear(game)
    kill(game, 12)
    assert BS.spirit_of(world, item)["nature"] == "bloodthirsty"


def test_a_loyal_spirit_binds_to_its_master_and_lends_them_strength(game):
    world, me = game.world, game.player.id
    item = spear(game)
    kill(game, 12)
    art = martial_arts(world, me)[0].technique.id  # the hunter's spear art
    plain = BS.blade_factor(world, me, "spear")
    kill(game, 5, "b")
    assert BS.spirit_of(world, item)["bond"] == 0.5 and plain == 1.0
    assert BS.blade_factor(world, me, "spear") == 1.05 and BS.blade_factor(world, me, "sword") == 1.0
    before = fighter_for(world, me, art).weapon_mult
    world.update_data(item, spirit={**BS.spirit_of(world, item), "master": 999})
    assert fighter_for(world, me, art).weapon_mult == pytest.approx(before / 1.05)


def test_a_bloodthirsty_blade_will_not_be_sheathed_dry_in_a_troubled_hand(game):
    world, me = game.world, game.player.id
    HT.write(world, me, lean=-40.0)
    spear(game)
    kill(game, 12)
    foe = someone(game, "foe")
    duel = Duel(1, me, foe, game.place.id, "duel", stage="verdict", harm={"player": 0.0, "opponent": 90.0})
    assert BS.blade_factor(world, me, "spear") == BS.THIRST and verdict_events(world, duel, "spare")
    HT.write(world, me, steady=20.0)
    assert BS.refuses_spare(world, me) and verdict_events(world, duel, "spare") == []
    assert verdict_events(world, duel, "kill")


def test_a_cursed_famous_blade_hungers_from_its_making(game):
    world = game.world
    keeper = someone(game, "keeper")
    for n in range(15):
        make_famous(world, f"test:curse:{n}", "sword", keeper, "made", "a test", game.place.id)
    cursed = [i for i in famous_weapons(world) if BS.cursed(world, world.entity(i))]
    assert cursed and len(cursed) < len(famous_weapons(world))
    assert BS.spirit_of(world, cursed[0]) | {"known_by": []} == {
        "nature": "bloodthirsty", "bond": 0.0, "master": None, "known_by": [], "cursed": True}


def test_a_season_in_hand_makes_the_spirit_felt_and_an_unfed_thirst_whispers(game):
    world, me = game.world, game.player.id
    HT.write(world, me, lean=-40.0)
    item = spear(game)
    kill(game, 12)
    assert not BS.known(world, me, item)
    world.set_time(world.time + lives.SEASON + 1)
    events = BS.season_hook(world, 0)
    assert [e.kind for e in events] == ["spirit_felt", "blade_whispered"]
    commit(world, events)
    assert BS.known(world, me, item) and HT.steady(world, me) == 55.0


def test_a_skilled_smith_reads_a_blade(game):
    world, me, here = game.world, game.player.id, game.place.id
    item = spear(game)
    kill(game, 12)
    novice = someone(game, "novice", occupation="blacksmith", craft_skill=2)
    master = someone(game, "master", occupation="blacksmith", craft_skill=4)
    assert BS.tell_block(world, me, novice, item) == "They cannot read a blade's heart."
    assert BS.tell_block(world, me, master, item) is None
    commit(world, BS.tell_events(world, me, master, item, here))
    assert BS.known(world, me, item)


def test_a_broken_blade_loses_its_spirit(game):
    world = game.world
    item = spear(game)
    kill(game, 12)
    world.update_data(item, broken=True)
    assert BS.spirit_of(world, item) is None


def test_check_spirits_flags_a_malformed_spirit(game):
    world = game.world
    item = spear(game)
    kill(game, 12)
    assert check_spirits(world) == []
    world.update_data(item, spirit={"nature": "sleepy", "bond": 2.0, "master": None, "known_by": []})
    assert "spirit" in " | ".join(check_spirits(world))
```

- [ ] **Step 2: Write the new modules**

`systems/blade_spirits.py`:
```python
"""Weapon spirits and cursed blades (phase 5e spec 6): a blade that has killed enough wakes a spirit, loyal or
bloodthirsty as its wielder's heart then leaned; a cursed famous blade hungers from its making.

A weapon counts its `kills`; a woken `spirit` is `{nature, bond, master, known_by}`. A loyal spirit lends its
master strength as the bond grows; a bloodthirsty one lends anyone strength, whispers when unfed a season, and
refuses to be sheathed dry in a troubled hand. A spirit is felt after a season in hand, or told by a smith.
"""

import systems.gear as gear
import systems.heart as HT
import systems.lives as lives
import systems.world_clock as world_clock
from systems.famous import famous_weapons
from world.events import Event, commit, effect, listen
from world.seed import seed_for

WAKE_KILLS, MASTERWORK_KILLS, WAKE_GRADE = 12, 6, 2
NATURES = ("loyal", "bloodthirsty")
BLOODTHIRSTY_LEAN = -30.0
LOYAL_STEP, BOND_STEP = 0.1, 0.1   # a loyal spirit's master fights x (1 + 0.1 x bond); a kill binds 0.1 more
THIRST = 1.15
CURSED_SHARE = 0.2                  # one famous blade in five
HUNGER_STEADY = -5.0
DRY_STEADY = 30.0                   # under this, a bloodthirsty blade will not spare
TELLING_SKILL = 3                   # a smith of this skill reads a blade


def cursed(world, item) -> bool:
    return item.id in famous_weapons(world) and seed_for(world.world_seed, f"curse:{item.id}") / 2 ** 64 < CURSED_SHARE


def spirit_of(world, item_id) -> dict | None:
    """A blade's spirit: woken, or a cursed blade's hunger; none in a broken blade."""
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item.kind != "gear" or item.data.get("broken"):
        return None
    if item.data.get("spirit"):
        return item.data["spirit"]
    if cursed(world, item):
        return {"nature": "bloodthirsty", "bond": 0.0, "master": None, "known_by": [], "cursed": True}
    return None


def wielded(world, person: int):
    """The blade in hand, if it is an item (a carried grade has no spirit): one lookup, no carried gear read."""
    return gear.item_in(world, person, "weapon")


def blade_factor(world, person: int, form: str) -> float:
    """What the spirit in the blade one fights with lends (spec 6)."""
    item = wielded(world, person)
    spirit = spirit_of(world, item.id) if item is not None and item.data["form"] == form else None
    if spirit is None:
        return 1.0
    if spirit["nature"] == "bloodthirsty":
        return THIRST
    return round(1 + LOYAL_STEP * spirit["bond"], 3) if spirit["master"] == person else 1.0


def refuses_spare(world, person: int) -> bool:
    item = wielded(world, person)
    spirit = spirit_of(world, item.id) if item is not None else None
    return spirit is not None and spirit["nature"] == "bloodthirsty" and HT.steady(world, person) < DRY_STEADY


def known(world, person: int, item_id) -> bool:
    spirit = spirit_of(world, item_id)
    return spirit is not None and person in spirit["known_by"]


def _write(world, item, spirit: dict) -> None:
    world.update_data(item.id, spirit=dict(spirit))


# --- kills and waking ------------------------------------------------------------------------------------------------

@listen("died")
def _killed(world, event, event_id: int) -> None:
    killer, victim = event.actors[0], event.actors[-1]
    if killer == victim or world.entity(killer) is None or world.entity(killer).data.get("dead"):
        return
    item = wielded(world, killer)
    if item is None or item.data.get("broken"):
        return
    kills = item.data.get("kills", 0) + 1
    world.update_data(item.id, kills=kills, fed_at=world.time)
    spirit = spirit_of(world, item.id)
    if spirit is not None:
        if spirit["nature"] == "loyal" and spirit["master"] == killer:
            _write(world, item, {**spirit, "bond": round(min(1.0, spirit["bond"] + BOND_STEP), 3)})
        return
    named = item.data.get("forged_by") is not None and item.data.get("famous")
    if item.data["grade"] >= WAKE_GRADE and kills >= (MASTERWORK_KILLS if named else WAKE_KILLS):
        nature = "bloodthirsty" if HT.lean(world, killer) < BLOODTHIRSTY_LEAN else "loyal"
        commit(world, [Event("spirit_woke", (killer, item.id), event.place, {"nature": nature})])


@effect("spirit_woke")
def _woke(world, event) -> None:
    killer, item = event.actors
    world.update_data(item, spirit={"nature": event.data["nature"], "bond": 0.0, "master": killer, "known_by": []})


# --- hunger and feeling it -------------------------------------------------------------------------------------------

def season_hook(world, n: int) -> list[Event]:
    """In the player's hand for a season: its spirit is felt; a bloodthirsty one unfed whispers."""
    player = world.get_meta("player_id")
    item = wielded(world, player) if player is not None and world.entity(player) is not None else None
    spirit = spirit_of(world, item.id) if item is not None else None
    if spirit is None:
        return []
    here = next(iter(world.targets(player, "located_in")), None)
    events = []
    if player not in spirit["known_by"]:
        events.append(Event("spirit_felt", (player, item.id), here, {"nature": spirit["nature"],
                                                                      "cursed": bool(spirit.get("cursed"))}))
    if spirit["nature"] == "bloodthirsty" and item.data.get("fed_at", -1) < world.time - lives.SEASON:
        events.append(Event("blade_whispered", (player, item.id), here, {"steady": HUNGER_STEADY}))
    return events


world_clock.SEASON_HOOKS.append(season_hook)


def _knows(world, person: int, item_id: int) -> None:
    item = world.entity(item_id)
    spirit = spirit_of(world, item_id)
    if spirit is not None and person not in spirit["known_by"]:
        _write(world, item, {**spirit, "known_by": spirit["known_by"] + [person]})


@effect("spirit_felt")
def _felt(world, event) -> None:
    _knows(world, *event.actors)


@effect("blade_whispered")
def _whispered(world, event) -> None:
    HT.shift_steady(world, event.actors[0], event.data["steady"])


def tell_block(world, person: int, smith: int, item_id) -> str | None:
    from systems.craft_world import crafter, skill  # the smiths come after the heart in the import graph
    if crafter(world, smith) != "smith" or skill(world, smith) < TELLING_SKILL:
        return "They cannot read a blade's heart."
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item.kind != "gear" or item_id not in world.targets(person, "owns"):
        return "You have no such blade."
    return None


def tell_events(world, person: int, smith: int, item_id: int, place) -> list[Event]:
    spirit = spirit_of(world, item_id)
    return [Event("blade_read", (person, smith, item_id), place,
                  {"nature": spirit["nature"] if spirit else None, "cursed": bool(spirit and spirit.get("cursed"))})]


@effect("blade_read")
def _read(world, event) -> None:
    _knows(world, event.actors[0], event.actors[2])
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_blade_spirits.py`
Expected: `1 error`: collection stops: the tests import `check_spirits`, which Step 4 adds.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5e_task5.py`:
```python
"""Phase 5e, Task 5: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/duel.py', r'''        weapon_mult=weapon_mult if art else 1.0, weapon_grade=weapon_grade if art else None, armour=armour,''', r'''        weapon_mult=weapon_mult * blade_factor(world, person_id, form) if art else 1.0,  # phase 5e: its spirit
        weapon_grade=weapon_grade if art else None, armour=armour,''')
edit('systems/duel.py', r'''def fighter_for(world, person_id: int, technique_id: int | None) -> Fighter:''', r'''def blade_factor(world, person_id: int, form: str) -> float:
    from systems.blade_spirits import blade_factor as factor  # the spirits come after the duel in the import graph
    return factor(world, person_id, form)


def fighter_for(world, person_id: int, technique_id: int | None) -> Fighter:''')
edit('systems/duel.py', r'''    if d.stage != "verdict" or choice not in (BEAST_VERDICTS if beast else VERDICTS):
        return []''', r'''    if d.stage != "verdict" or choice not in (BEAST_VERDICTS if beast else VERDICTS):
        return []
    from systems.blade_spirits import refuses_spare  # phase 5e: a bloodthirsty blade in a troubled hand
    if choice == "spare" and refuses_spare(world, d.player):
        return []''')
edit('systems/world_clock.py', r'''import systems.oaths  # noqa: E402,F401  phase 5e: oaths sworn on the heart, kept and broken
''', r'''import systems.oaths  # noqa: E402,F401  phase 5e: oaths sworn on the heart, kept and broken
import systems.blade_spirits  # noqa: E402,F401  phase 5e: weapon spirits and cursed blades
''')
edit('debug/invariants.py', r'''def check_toxins(world) -> list[str]:''', r'''def check_spirits(world) -> list[str]:
    """Weapon spirits (phase 5e)."""
    from systems.blade_spirits import NATURES
    out = []
    for item in world.entities_after("gear", "kills", 0):
        spirit = item.data.get("spirit")
        if spirit is not None and (spirit.get("nature") not in NATURES or not 0 <= spirit.get("bond", -1) <= 1):
            out.append(f"{item.name} (#{item.id}) holds a malformed spirit: {spirit}")
    return out


def check_toxins(world) -> list[str]:''')
edit('debug/invariants.py', r'''    problems += check_heart(world)
''', r'''    problems += check_heart(world)
    problems += check_spirits(world)
''')
print("task 5 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5e_task5.py`
Expected: `task 5 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_blade_spirits.py`
Expected: `10 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1494 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: weapon spirits and cursed blades - loyal and bloodthirsty, felt in the hand and read by smiths"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 6: The world's hearts

A lives agenda of one hash: a troubled master of Second-rate or more goes mad one season in a hundred. The mad call the player out as avengers do, fight harder, and never spare (ruling 17); after a year they come back to themselves, or it kills them. A master enlightened in a dao resonance opens the dao of their art (ruling 18).

**Files:**
- Create: `systems/heart_world.py`
- Create: `tests/test_heart_world.py`
- Modify (by `.patches/5e_task6.py`): `systems/duel.py`, `systems/events/dao_resonance.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Tasks 1 and 3's `heart` and `daos`; 4a's lives agendas; 3b's `HUNTER_HOOKS`; 2b's hateful verdicts; 4d's dao resonance.
- Produces:
  - `HW` (systems/heart_world.py): `MAD_REALM`, `MAD_CHANCE`, `MAD_STEADY`, `MAD_YEARS`, `RECOVERY`, `MAD_FIGHT`, `ENLIGHTENED_DAO`; `mad(world, person)`, `season_events(world, person, n, rng)`, `hunting(world, player)`, `fight_factor(world, person)`, `enlighten(world, master)`; events `heart_madness`, `madness_passed`.
  - madness in `duel.fight_factor` and the hateful verdict; the mad in `check_heart`.

- [ ] **Step 1: Write the tests**

`tests/test_heart_world.py`:
```python
import pytest

import systems.daos as DA
import systems.encounters as encounters
import systems.heart as HT
import systems.heart_world as HW
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_heart
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.duel import Duel, fighter_for, yield_events
from tests.test_world_events import begin
from world.events import commit
from world.seed import rng_for


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


def master(game, tag, realm="second-rate", steady=10.0):
    pid = founding.make_person(game.world, f"test:mad:{tag}", game.place.id, occupation="monk", age=50, realm=realm)
    HT.write(game.world, pid, steady=steady)
    return pid


def test_a_troubled_master_goes_mad_and_it_is_news(game, monkeypatch):
    world = game.world
    monkeypatch.setattr(HW, "MAD_CHANCE", 1.0)
    low, calm_one, troubled = master(game, "low", "third-rate"), master(game, "calm", steady=70.0), master(game, "t")
    assert HW.season_events(world, low, 0, None) == [] and HW.season_events(world, calm_one, 0, None) == []
    events = HW.season_events(world, troubled, 0, None)
    assert [e.kind for e in events] == ["heart_madness"]
    commit(world, events)
    assert HW.mad(world, troubled) and world.facts("went_mad", subject=troubled)


def test_after_a_year_the_mad_come_back_to_themselves_or_die_of_it(game, monkeypatch):
    world = game.world
    monkeypatch.setattr(HW, "MAD_CHANCE", 1.0)
    one, two = master(game, "one"), master(game, "two")
    commit(world, HW.season_events(world, one, 0, None) + HW.season_events(world, two, 0, None))
    assert HW.season_events(world, one, 1, None) == []
    world.set_time(world.entity(one).data["mad_until"])
    monkeypatch.setattr(HW, "RECOVERY", 1.0)
    commit(world, HW.season_events(world, one, 4, None))
    assert not HW.mad(world, one) and not world.entity(one).data.get("dead")
    monkeypatch.setattr(HW, "RECOVERY", 0.0)
    [death] = HW.season_events(world, two, 4, None)
    assert death.kind == "died" and death.data["cause"] == "madness"
    commit(world, [death])
    assert world.entity(two).data.get("mad_until") is None and check_heart(world) == []


def test_the_mad_call_the_player_out_fight_harder_and_never_spare(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(HW, "MAD_CHANCE", 1.0)
    madman = master(game, "mad")
    plain = fighter_for(world, madman, None).realm_mult
    commit(world, HW.season_events(world, madman, 0, None))
    assert HW.hunting(world, me) == [madman]
    assert fighter_for(world, madman, None).realm_mult == pytest.approx(plain * HW.MAD_FIGHT)
    duel = Duel(1, me, madman, game.place.id, "duel")
    [end] = yield_events(world, duel)
    assert end.data["verdict"] in ("leave_for_dead", "kill")


def test_a_master_enlightened_in_a_resonance_opens_their_dao(game):
    import systems.events.dao_resonance as dao
    world, town = game.world, game.place.id
    sage = founding.make_person(world, "test:sage", town, occupation="monk", age=60, realm="first-rate")
    n = world.time // W.SEASON
    world.set_time(world.time + 1)
    begin(world, "dao_resonance", town, **dao.start_data(world, town, n, rng_for(1, "t")))
    sky.observe(world, town)
    assert list(DA.daos(world, sage).values()) == [HW.ENLIGHTENED_DAO]


def test_check_heart_flags_the_dead_still_mad(game):
    world = game.world
    madman = master(game, "m")
    world.update_data(madman, mad_until=world.time + 10, dead=True)
    assert "mad" in " | ".join(check_heart(world))
```

- [ ] **Step 2: Write the new modules**

`systems/heart_world.py`:
```python
"""The world's hearts (phase 5e spec 7): masters driven mad by their demons, and the enlightened.

A lives agenda: a master of Second-rate or more whose heart is troubled goes mad, one season in a hundred (one
hash; the heart is read only when the hash falls). A mad master calls the player out in town as an avenger does,
fights harder and never spares; after a year they come back to themselves, or it kills them. A master enlightened
in a dao resonance (4d) opens the dao of their art.
"""

import systems.craft_world  # noqa: F401  5d's agendas run before this one, whatever is imported first
import systems.daos as DA
import systems.encounters as encounters
import systems.heart as HT
import systems.lives as lives
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from world.events import Event, effect, listen
from world.gen.materialize import people_at
from world.seed import seed_for

MAD_REALM = 2              # Second-rate
MAD_CHANCE = 0.01          # a season
MAD_STEADY = 30.0          # only a heart under this goes mad
MAD_YEARS = 1
RECOVERY = 0.6
MAD_FIGHT = 1.2
ENLIGHTENED_DAO = 0.2


def mad(world, person: int) -> bool:
    entity = world.entity(person)
    return entity is not None and not entity.data.get("dead") and (entity.data.get("mad_until") or 0) > world.time


def season_events(world, person: int, n: int, rng) -> list[Event]:
    entity = world.entity(person)
    if entity.data.get("mad_until"):
        if entity.data["mad_until"] > world.time:
            return []
        place = lives.home(world, person)
        if seed_for(world.world_seed, f"mad_end:{lives.key(entity)}") / 2 ** 64 < RECOVERY:
            return [Event("madness_passed", (person,), place, {})]
        return [Event("died", (person, person), place, {"cause": "madness", "world": True})]
    if realm_index(entity.data.get("realm", "mortal")) < MAD_REALM:
        return []
    if seed_for(world.world_seed, f"madness:{lives.key(entity)}:{n}") / 2 ** 64 >= MAD_CHANCE:
        return []
    if HT.steady(world, person) >= MAD_STEADY:
        return []
    return [Event("heart_madness", (person,), lives.home(world, person),
                  {"until": world.time + MAD_YEARS * 4 * lives.SEASON, "season": n})]


lives.AGENDAS.append(season_events)


@effect("heart_madness")
def _maddened(world, event) -> None:
    world.update_data(event.actors[0], mad_until=event.data["until"])


@effect("madness_passed")
def _recovered(world, event) -> None:
    world.update_data(event.actors[0], mad_until=None)


@listen("heart_madness")
def _news(world, event, event_id: int) -> None:
    person = event.actors[0]
    variant = make_variant("went_mad", person, None, place=place_name(world, event.place),
                           realm=world.entity(person).data.get("realm", "mortal"))
    record_fact(world, person, "went_mad", None, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


def hunting(world, player: int) -> list[int]:
    """The mad in the player's town call them out, as avengers do."""
    here = next(iter(world.targets(player, "located_in")), None)
    return [p.id for p in people_at(world, here, exclude=player) if mad(world, p.id)] if here is not None else []


encounters.HUNTER_HOOKS.append(hunting)


def fight_factor(world, person: int) -> float:
    return MAD_FIGHT if mad(world, person) else 1.0


def enlighten(world, master: int) -> None:
    """A master enlightened (4d's dao resonance) opens the dao of their first art's form."""
    from systems.duel import ensure_npc_arts  # arts come after the heart in the import graph
    from systems.techniques import martial_arts
    ensure_npc_arts(world, master)
    arts = martial_arts(world, master)
    if arts:
        form = arts[0].technique.data["form"]
        daos = DA.daos(world, master)
        HT.write(world, master, daos={**daos, form: round(min(1.0, daos.get(form, 0.0) + ENLIGHTENED_DAO), 3)})


@listen("died")
def _mad_no_more(world, event, event_id: int) -> None:
    if world.entity(event.actors[-1]).data.get("mad_until"):
        world.update_data(event.actors[-1], mad_until=None)
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_heart_world.py`
Expected: `3 failed, 2 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5e_task6.py`:
```python
"""Phase 5e, Task 6: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/duel.py', r'''def fight_factor(world, person_id: int) -> float:
    from systems.arrays import fight_factor as factor  # the arrays come after the duel in the import graph
    return factor(world, person_id)''', r'''def fight_factor(world, person_id: int) -> float:
    from systems.arrays import fight_factor as factor  # the arrays come after the duel in the import graph
    from systems.heart_world import fight_factor as madness  # phase 5e: the mad fight harder
    return factor(world, person_id) * madness(world, person_id)''')
edit('systems/duel.py', r'''        hateful = any(m.feeling in HATEFUL for m in world.memories(d.opponent, about=d.player))''', r'''        from systems.heart_world import mad  # phase 5e: the mad never spare
        hateful = any(m.feeling in HATEFUL for m in world.memories(d.opponent, about=d.player)) or mad(world, d.opponent)''')
edit('systems/events/dao_resonance.py', r'''    record_fact(world, master.id, "enlightened", None, place=town, weight=1.5, variant=variant)''', r'''    record_fact(world, master.id, "enlightened", None, place=town, weight=1.5, variant=variant)
    from systems.heart_world import enlighten  # phase 5e: the enlightened open the dao of their art
    enlighten(world, master.id)''')
edit('systems/world_clock.py', r'''import systems.blade_spirits  # noqa: E402,F401  phase 5e: weapon spirits and cursed blades
''', r'''import systems.blade_spirits  # noqa: E402,F401  phase 5e: weapon spirits and cursed blades
import systems.heart_world  # noqa: E402,F401  phase 5e: masters driven mad by their demons, and the enlightened
''')
edit('debug/invariants.py', r'''    for person in world.entities_after("person", "heart.steady", -1):''', r'''    for person in world.entities_after("person", "mad_until", 0):
        if person.data.get("dead"):
            out.append(f"{person.name} (#{person.id}) is dead and mad still")
    for person in world.entities_after("person", "heart.steady", -1):''')
print("task 6 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5e_task6.py`
Expected: `task 6 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_heart_world.py`
Expected: `5 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1499 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the world's hearts - masters driven mad by their demons, and the enlightened"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 7: The player's heart

`HeartMixin` puts the heart in the player's hands: a heart page in words, oaths sworn from it, respects paid at a grave, the heart trial at the gate of a breakthrough (ruling 20), and one "Of the heart..." talk menu for amends and a smith's reading of a blade (ruling 19). Every new deed has its outcome, journal line and grammar; oaths and madness are rumours; typed words and help reach it all.

**Files:**
- Create: `engine/heart.py`
- Create: `engine/heart_page.py`
- Create: `narrate/heart_text.py`
- Create: `narrate/grammar/heart.toml`
- Create: `tests/test_heart_play.py`
- Modify (by `.patches/5e_task7.py`): `engine/game.py`, `engine/commands.py`, `engine/sheet.py`, `narrate/outcomes.py`, `tests/test_game.py`

**Interfaces:**
- Consumes: Everything above; 5d's talk menus as the model.
- Produces:
  - `engine/heart.py` (engine/heart.py): `HEART_MENUS`, `TALK_MENU`.
  - `engine/heart_page.py` (engine/heart_page.py): `WEIGHT_WORDS`, `DAO_WORDS`; `demon_words(world, demon)`, `dao_name(name)`, `dao_words(value)`, `oath_words(world, oath)`, `spirit_words(world, player, item)`, `heart_lines(world, player)`, `rising_lines(world, player)`, `sheet_heart_lines(world, player)`, `oath_choices(world, player)`.
  - `narrate/heart_text.py`: outcomes, journal lines, and the rumours `went_mad`, `oath_sworn`, `oath_kept` and `oath_broken`.

- [ ] **Step 1: Write the tests**

`tests/test_heart_play.py`:
```python
import pytest

import systems.blade_spirits as BS
import systems.daos as DA
import systems.demons as D
import systems.encounters as encounters
import systems.gear as gear
import systems.heart as HT
import systems.oaths as O
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.gossip_text import rumour_text
from narrate.outcomes import SUMMARIES
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.facts import make_variant
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=1000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "mortal", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:hplay:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def text(turn):
    return " | ".join(t for t, _ in turn.lines)


def shown(turn):
    return [c.label for c in turn.choices]


def test_the_heart_page_tells_the_heart_in_words(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    D.add_demon(world, me, "grudge", foe, 2)
    HT.write(world, me, daos={"spear": 0.3})
    page = text(game.perform(Action("heart")))
    assert "Your dao heart is steady; your way is unaligned." in page
    assert "A grudge against Someone foe (heavy)" in page and "The Dao of the Spear: grasped" in page
    assert "0.3" not in page and "60" not in page  # words, never numbers
    assert any("Dao heart steady; way unaligned; the Dao of the Spear (grasped)" in t for t, _ in sheet_lines(world, me))


def test_an_untouched_heart_keeps_off_the_sheet(game):
    assert ("Heart:", "heading") not in sheet_lines(game.world, game.player.id)  # the sheet fits a 40-row screen


def test_an_oath_is_sworn_from_the_heart_page_by_number_or_by_word(game):
    world, me = game.world, game.player.id
    turn = game.perform(Action("heart"))
    turn = game.perform(next(c.action for c in turn.choices if c.label == "Swear an oath..."))
    assert "Swear to kill no one for a season" in shown(turn)
    game.perform(next(c.action for c in turn.choices if c.label == "Swear to kill no one for a season"))
    assert [o["kind"] for o in O.oaths(world, me)] == ["abstinence"]
    foe = someone(game, "foe")
    D.add_demon(world, me, "grudge", foe, 1)
    turn = game.perform(Action("heart"))
    action = parse("swear vengeance someone foe", turn.choices, turn.extra)
    assert action == Action("swear_oath", ("vengeance", foe))
    turn = game.perform(action)
    assert "You swear on your dao heart: vengeance on Someone foe." in text(turn)


def at_the_gate(game):
    body = load_body(game.world, game.player.id)
    body.realm, body.bottleneck, body.energy_years = 1, True, 5.0
    body.flags.append("sensed_qi")
    body.meridians["Governing"].state = "open"
    save_body(game.world, game.player.id, body)


def test_a_demon_rises_at_the_breakthrough_and_is_faced(game, monkeypatch):
    world, me = game.world, game.player.id
    at_the_gate(game)
    D.add_demon(world, me, "fear", None, 2)
    turn = game.perform(Action("breakthrough"))
    assert "As your qi presses at the gate, the fear of death rises before you." in text(turn)
    assert shown(turn)[:3] == ["Face it", "Bury it and break through", "Turn back"]
    turn = game.perform(Action("heart_trial", "turn_back"))
    assert "You turn back from the gate. The fear of death waits." in text(turn) and D.demons(world, me)
    monkeypatch.setattr(D, "FACE_BOUNDS", (1.0, 1.0))
    game.perform(Action("breakthrough"))
    turn = game.perform(parse("face", [], []))
    assert "You look the fear of death in the face, and it lets you go." in text(turn)
    assert D.demons(world, me) == [] and any(e.kind == "breakthrough" for e in world.chronicle_about(me, limit=5))


def test_a_breakthrough_with_no_demon_is_as_before(game):
    at_the_gate(game)
    turn = game.perform(Action("breakthrough"))
    assert "rises before you" not in text(turn)
    assert any(e.kind == "breakthrough" for e in game.world.chronicle_about(game.player.id, limit=5))


def test_respects_are_paid_at_a_grave_from_the_scene(game):
    world, me, here = game.world, game.player.id, game.place.id
    wife = someone(game, "wife")
    world.relate(me, wife, "kin_of", data={"role": "spouse"})
    commit(world, [Event("died", (wife, wife), here, {"cause": "illness", "world": True})])
    turn = game.perform(Action("look"))
    respects = next(c for c in turn.all_choices if c.label == "Pay your respects to Someone wife")
    turn = game.perform(respects.action)
    assert "You kneel at Someone wife's grave." in text(turn) and D.demons(world, me) == []


def test_amends_and_a_blades_reading_are_asked_in_conversation(game):
    world, me, here = game.world, game.player.id, game.place.id
    foe, widow = someone(game, "foe"), someone(game, "widow", occupation="blacksmith", craft_skill=4)
    world.relate(widow, foe, "kin_of", data={"role": "spouse"})
    D.add_demon(world, me, "guilt", foe, 2)
    item = gear.make_item(world, "weapon", "spear", 2, me, "bought")
    commit(world, gear.wield_events(world, me, item, here))
    game.perform(Action("talk", widow))
    turn = game.perform(Action("heart_talk"))
    assert shown(turn)[:2] == [f"Make amends ({D.AMENDS} silver)", f"Have them look at {world.entity(item).name}"]
    turn = game.perform(Action("make_amends", widow))
    assert "It undoes nothing, but it is something." in text(turn)
    game.perform(Action("heart_talk"))
    turn = game.perform(Action("read_blade", widow))
    assert "Nothing sleeps in it." in text(turn) and BS.spirit_of(world, item) is None


def test_typed_words_and_help_reach_the_heart(game):
    turn = game.perform(Action("look"))
    for word, verb in (("heart", "heart"), ("face", "heart_trial"), ("bury", "heart_trial"),
                       ("turn back", "heart_trial"), ("respects", "pay_respects")):
        assert parse(word, turn.choices, turn.extra).verb == verb
    assert any("heart | swear" in t for t, _ in game.perform(Action("help")).lines)


def test_every_heart_deed_has_a_journal_line():
    for kind in ("heart_trial", "demon_stirred", "paid_respects", "amends_made", "epiphany", "oath_sworn", "oath_kept",
                 "oath_broken", "spirit_woke", "spirit_felt", "blade_whispered", "blade_read", "heart_madness",
                 "madness_passed"):
        assert kind in SUMMARIES, kind


def test_oaths_and_madness_are_told_as_rumours(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    v = make_variant("oath_broken", foe, me)
    v["oath"] = "protection"
    assert rumour_text(world, v, me) == "Someone foe broke an oath sworn on their dao heart to protect you."
    v = make_variant("went_mad", foe, None, place="Crimson Town")
    assert rumour_text(world, v, me) == "Someone foe went mad with their demons in Crimson Town."
    assert DA.dao(world, me, "spear") == 0.0
```

- [ ] **Step 2: Write the new modules**

`engine/heart.py`:
```python
"""The dao heart in the engine (phase 5e spec 8): the heart page, oaths, respects at a grave, the heart trial at
a breakthrough, and amends and a smith's reading of a blade in conversation."""

import systems.blade_spirits as BS
import systems.demons as D
import systems.oaths as O
from engine.actions import Action, Choice
from engine.heart_page import heart_lines, oath_choices, rising_lines

HEART_MENUS = ("heart", "oath_menu", "heart_trial")
TALK_MENU = "heart_talk"


class HeartMixin:
    # --- choices -----------------------------------------------------------------------------------------------
    def _graves_here(self) -> list[int]:
        world, me, here = self.world, self.player.id, self.place.id
        return [d["whom"] for d in D.demons(world, me)
                if d["kind"] == "grief" and D.respects_block(world, me, d["whom"], here) is None]

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        extras.append(Choice("Your heart", Action("heart")))
        extras += [Choice(f"Pay your respects to {self.world.entity(dead).name}", Action("pay_respects", dead))
                   for dead in self._graves_here()]
        return extras

    def _heart_talk(self, npc) -> list:
        world, me = self.world, self.player.id
        out = []
        if D.amends_block(world, me, npc.id) is None:
            out.append(Choice(f"Make amends ({D.AMENDS} silver)", Action("make_amends", npc.id)))
        item = BS.wielded(world, me)
        if item is not None and BS.tell_block(world, me, npc.id, item.id) is None:
            out.append(Choice(f"Have them look at {item.name}", Action("read_blade", npc.id)))
        return out

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if self._heart_talk(npc):
            extras.append(Choice("Of the heart...", Action("heart_talk")))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        world, me = self.world, self.player.id
        if self.focus is not None:
            if self.submenu == TALK_MENU:
                options[TALK_MENU] = (self._heart_talk(world.entity(self.focus)), Action("talk_menu"))
            return options
        oaths = [Choice(label, Action("swear_oath", (kind, whom))) for label, kind, whom in oath_choices(world, me)]
        if self.submenu == "heart":
            choices = [Choice("Swear an oath...", Action("oath_menu"))] if oaths else []
            choices += [Choice(f"Pay your respects to {world.entity(dead).name}", Action("pay_respects", dead))
                        for dead in self._graves_here()]
            options["heart"] = (choices, Action("back"))
            options["oath_menu"] = (oaths, Action("heart"))  # typed "swear ..." reaches them from the heart page
        elif self.submenu == "oath_menu":
            options["oath_menu"] = (oaths, Action("heart"))
        elif self.submenu == "heart_trial" and D.rising(world, me) is not None:
            options["heart_trial"] = ([Choice("Face it", Action("heart_trial", "face")),
                                       Choice("Bury it and break through", Action("heart_trial", "bury")),
                                       Choice("Turn back", Action("heart_trial", "turn_back"))], Action("cultivate"))
        return options

    # --- the breakthrough -----------------------------------------------------------------------------------------
    def _heart_trial(self):
        """A demon rises at the gate of Second-rate or beyond: the trial comes before the breakthrough (spec 3)."""
        if D.rising(self.world, self.player.id) is None:
            return None
        self.submenu = "heart_trial"
        return self._turn(rising_lines(self.world, self.player.id))

    def _do_heart_trial(self, choice):
        if busy := self._busy():
            return busy
        events = D.trial_events(self.world, self.player.id, self.place.id, choice)
        if not events:
            return self._turn([("There is nothing at the gate to face.", "system")])
        return self._cultivated(events, "")

    # --- handlers ---------------------------------------------------------------------------------------------------
    def _do_heart(self, _target):
        self.submenu = "heart"
        return self._turn(heart_lines(self.world, self.player.id))

    def _do_oath_menu(self, _target):
        self.submenu = "oath_menu"
        return self._turn([("On your dao heart, you swear...", "system")])

    def _do_swear_oath(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        kind, whom = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        self.submenu = "heart"
        if (why := O.swear_block(world, me, kind, whom)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(O.swear_events(world, me, kind, whom, here)))

    def _do_pay_respects(self, dead):
        world, me, here = self.world, self.player.id, self.place.id
        if dead is None:
            dead = next(iter(self._graves_here()), None)
        if dead is None or (why := D.respects_block(world, me, dead, here)) is not None:
            return self._turn([("There is no grave of yours to kneel at here.", "system")])
        return self._turn(self._commit(D.respects_events(world, me, dead, here)))

    def _do_heart_talk(self, _target):
        if self.focus is None or not self._heart_talk(self.world.entity(self.focus)):
            return self._turn([("There is nothing of the heart to speak of with them.", "system")])
        self.submenu = TALK_MENU
        return self._turn([("What will you ask of them?", "system")])

    def _heart_deed(self, npc, why, events):
        if self.focus != npc:
            return self._turn([("They are not the one you are speaking with.", "system")])
        if why is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(events()))

    def _do_make_amends(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        why = D.amends_block(world, me, npc) if isinstance(npc, int) else "You owe them nothing."
        return self._heart_deed(npc, why, lambda: D.amends_events(world, me, npc, here))

    def _do_read_blade(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        item = BS.wielded(world, me)
        why = "You hold no blade." if item is None else BS.tell_block(world, me, npc, item.id)
        return self._heart_deed(npc, why, lambda: BS.tell_events(world, me, npc, item.id, here))
```

`engine/heart_page.py`:
```python
"""The heart page (phase 5e spec 8-9): the dao heart in words, its demons, daos, oaths, and a blade's spirit."""

import systems.blade_spirits as BS
import systems.daos as DA
import systems.demons as D
import systems.heart as HT
import systems.oaths as O

WEIGHT_WORDS = {1: "light", 2: "heavy", 3: "crushing"}
DAO_WORDS = ((1.0, "whole: you have returned to the origin"), (0.75, "profound"), (0.5, "deep"), (0.25, "grasped"),
             (0.0, "glimpsed"))


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _name(world, whom) -> str:
    entity = world.entity(whom) if isinstance(whom, int) else None
    return entity.name if entity is not None else "someone"


def demon_words(world, demon: dict) -> str:
    kind, whom = demon["kind"], demon["whom"]
    if kind == "fear":
        return "the fear of death"
    if kind == "guilt":
        return f"guilt over {_name(world, whom)}" if whom is not None else "guilt over an oath broken"
    return f"a grudge against {_name(world, whom)}" if kind == "grudge" else f"grief for {_name(world, whom)}"


def dao_name(name: str) -> str:
    if name in ("yin", "yang"):
        return f"the Dao of {name.capitalize()}"
    if name in DA.FORMS:
        return f"the Dao of the {name.capitalize()}"
    return f"the Dao of {name.capitalize()}"


def dao_words(value: float) -> str:
    return next(word for bound, word in DAO_WORDS if value >= bound)


def oath_words(world, oath: dict) -> str:
    if oath["kind"] == "vengeance":
        return f"vengeance on {_name(world, oath['whom'])}"
    if oath["kind"] == "protection":
        return f"to protect {_name(world, oath['whom'])}"
    return "to kill no one"


def spirit_words(world, player: int, item) -> str | None:
    if not BS.known(world, player, item.id):
        return None
    spirit = BS.spirit_of(world, item.id)
    if spirit.get("cursed"):
        return f"{item.name} is cursed: it thirsts for blood."
    if spirit["nature"] == "bloodthirsty":
        return f"{item.name} holds a bloodthirsty spirit."
    bound = "it knows your hand" if spirit["master"] == player else "it knows another's hand"
    return f"{item.name} holds a loyal spirit: {bound}."


def heart_lines(world, player: int) -> list:
    heart = HT.heart_of(world, player)
    lines = [("Your heart", "heading"),
             (f"  Your dao heart is {HT.steady_words(heart['steady'])}; your way is {HT.lean_words(heart['lean'])}.",
              "dim")]
    demons = sorted(heart["demons"], key=lambda d: (-d["weight"], d["since"]))
    lines.append(("Demons you carry:" if demons else "You carry no heart demons.", "heading"))
    lines += [(f"  {_cap(demon_words(world, d))} ({WEIGHT_WORDS[d['weight']]})", "dim") for d in demons]
    daos = sorted(heart["daos"].items(), key=lambda kv: -kv[1])
    if daos:
        lines.append(("Daos you have glimpsed:", "heading"))
        lines += [(f"  {_cap(dao_name(name))}: {dao_words(value)}", "dim") for name, value in daos]
    if heart["oaths"]:
        lines.append(("Oaths on your heart:", "heading"))
        for oath in heart["oaths"]:
            days = max(1, -(-(oath["until"] - world.time) // 4))
            lines.append((f"  {_cap(oath_words(world, oath))} ({days} day(s) left)", "dim"))
    item = BS.wielded(world, player)
    told = spirit_words(world, player, item) if item is not None else None
    if told:
        lines += [("Your blade:", "heading"), (f"  {told}", "dim")]
    return lines


def rising_lines(world, player: int) -> list:
    demon = D.rising(world, player)
    return [(f"As your qi presses at the gate, {demon_words(world, demon)} rises before you.", "system"),
            ("Will you face it, bury it, or turn back?", "system")]


def sheet_heart_lines(world, player: int) -> list:
    """Nothing for a heart never touched, as 5d's crafts (the sheet fits a 40-row screen)."""
    if world.entity(player).data.get("heart") is None:
        return []
    heart = HT.heart_of(world, player)
    line = f"  Dao heart {HT.steady_words(heart['steady'])}; way {HT.lean_words(heart['lean'])}"
    if heart["daos"]:
        best, value = max(heart["daos"].items(), key=lambda kv: kv[1])
        line += f"; {dao_name(best)} ({dao_words(value).split(':')[0]})"
    return [("", "default"), ("Heart:", "heading"), (line, "default")]


def oath_choices(world, player: int) -> list[tuple[str, str, int | None]]:
    """(label, kind, whom) of the oaths one may swear now: vengeance on a grudge, protection of kin, abstinence."""
    from systems.kin import kin_of
    out = [(f"Swear vengeance on {_name(world, w)}", "vengeance", w) for w in O.grudges(world, player)]
    out += [(f"Swear to protect {_name(world, k)}", "protection", k) for k, _ in kin_of(world, player)]
    out.append(("Swear to kill no one for a season", "abstinence", None))
    return [c for c in out if O.swear_block(world, player, c[1], c[2]) is None]
```

`narrate/heart_text.py`:
```python
"""What the player is told of their heart: trials, epiphanies, oaths, graves and amends, a blade's spirit, and the
masters who go mad (phase 5e spec 8)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

from engine.heart_page import dao_name, dao_words, demon_words, oath_words


def _name(world, entity_id) -> str:
    entity = world.entity(entity_id) if isinstance(entity_id, int) else None
    return entity.name if entity else "someone"


def _demon(world, data) -> str:
    return demon_words(world, {"kind": data["kind"], "whom": data["whom"]})


# --- the heart trial ---------------------------------------------------------------------------------------------

@outcome("heart_trial", body_facts=False)
def _trial(world, event):
    d = event.data
    demon = _demon(world, d)
    if d["choice"] == "turn_back":
        return [f"You turn back from the gate. {cap(demon)} waits."], {}
    if d["choice"] == "bury":
        return [f"You push {demon} down, and step through with it still inside you."], {}
    if d["success"]:
        return [f"You look {demon} in the face, and it lets you go."], {}
    return [f"{cap(demon)} will not be faced: your qi turns on itself."], {}


@summary("heart_trial")
def _trial_line(world, entry, names, place, other):
    d = entry.data
    words = {"turn_back": "Turned back from", "bury": "Buried", "face": "Faced" if d.get("success") else "Was beaten by"}
    return f"{words[d['choice']]} {_demon(world, d)} at a breakthrough."


@outcome("demon_stirred", body_facts=False)
def _stirred(world, event):
    return [f"In the stillness, {_demon(world, event.data)} rises. Your qi stumbles."], {}


@summary("demon_stirred")
def _stirred_line(world, entry, names, place, other):
    return f"Troubled by {_demon(world, entry.data)} in meditation."


@outcome("paid_respects", body_facts=False)
def _respects(world, event):
    return [f"You kneel at {_name(world, event.actors[1])}'s grave. The grief loosens its hold."], {}


@summary("paid_respects")
def _respects_line(world, entry, names, place, other):
    return f"Paid respects at {other}'s grave."


@outcome("amends_made", body_facts=False)
def _amends(world, event):
    return [f"You press {event.data['silver']} silver on {_name(world, event.actors[1])}. "
            "It undoes nothing, but it is something."], {}


@summary("amends_made")
def _amends_line(world, entry, names, place, other):
    return f"Made amends to {other}."


# --- epiphanies ----------------------------------------------------------------------------------------------------

@outcome("epiphany", body_facts=False)
def _epiphany(world, event):
    d = event.data
    lines = [f"Understanding opens like a door: {dao_name(d['dao'])}, {dao_words(d['after'])}."]
    if d["origin"]:
        lines.append("Everything you learnt falls away, and what is left is simple. You have returned to the origin.")
    return lines, {}


@summary("epiphany")
def _epiphany_line(world, entry, names, place, other):
    return f"Glimpsed more of {dao_name(entry.data['dao'])}."


# --- oaths ------------------------------------------------------------------------------------------------------------

def _oath(world, data) -> str:
    return oath_words(world, {"kind": data["kind"], "whom": data["whom"]})


@outcome("oath_sworn", body_facts=False)
def _sworn(world, event):
    return [f"You swear on your dao heart: {_oath(world, event.data)}."], {}


@summary("oath_sworn")
def _sworn_line(world, entry, names, place, other):
    return f"Swore on the dao heart: {_oath(world, entry.data)}."


@outcome("oath_kept", body_facts=False)
def _kept(world, event):
    return [f"An oath is kept: {_oath(world, event.data)}. Your heart stands straighter."], {}


@summary("oath_kept")
def _kept_line(world, entry, names, place, other):
    return f"Kept an oath: {_oath(world, entry.data)}."


@outcome("oath_broken", body_facts=False)
def _broken(world, event):
    return [f"An oath is broken: {_oath(world, event.data)}. Something in your heart cracks."], {}


@summary("oath_broken")
def _broken_line(world, entry, names, place, other):
    return f"Broke an oath: {_oath(world, entry.data)}."


# --- blades ---------------------------------------------------------------------------------------------------------

@outcome("spirit_woke", body_facts=False)
def _woke(world, event):
    return [f"{cap(_name(world, event.actors[1]))} feels heavier in your hand."], {}


@summary("spirit_woke")
def _woke_line(world, entry, names, place, other):
    return f"Something stirred in {_name(world, entry.actors[1])}."


@outcome("spirit_felt", body_facts=False)
def _felt(world, event):
    item = _name(world, event.actors[1])
    if event.data["cursed"]:
        return [f"A season in your hand, and you know it: {item} is cursed, and it thirsts."], {}
    return [f"A season in your hand, and you know it: {item} holds a {event.data['nature']} spirit."], {}


@summary("spirit_felt")
def _felt_line(world, entry, names, place, other):
    return f"Came to know the spirit in {_name(world, entry.actors[1])}."


@outcome("blade_whispered", body_facts=False)
def _whispered(world, event):
    return [f"{cap(_name(world, event.actors[1]))} whispers of blood. Your heart wavers."], {}


@summary("blade_whispered")
def _whispered_line(world, entry, names, place, other):
    return f"{cap(_name(world, entry.actors[1]))} hungered."


@outcome("blade_read", body_facts=False)
def _read(world, event):
    smith, d = _name(world, event.actors[1]), event.data
    if d["nature"] is None:
        verdict = "Good steel. Nothing sleeps in it."
    elif d["cursed"]:
        verdict = "This one is cursed. It wants blood, and it will ask you for it."
    else:
        verdict = f"There is a spirit in this, and a {d['nature']} one."
    return [f"{smith} turns the blade in the light. \"{verdict}\""], {}


@summary("blade_read")
def _read_line(world, entry, names, place, other):
    return f"Had {other} read {_name(world, entry.actors[2])}."


# --- the world ------------------------------------------------------------------------------------------------------

@summary("heart_madness")
def _mad_line(world, entry, names, place, other):
    return f"{_name(world, entry.actors[0])} went mad with their demons."


@summary("madness_passed")
def _sane_line(world, entry, names, place, other):
    return f"{_name(world, entry.actors[0])} came back to themselves."


def _went_mad(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} went mad with their demons in {v.get('place') or 'a town'}.")


def _oath_news(world, v, viewer) -> str:
    person, target = who(world, v.get("actor"), viewer), v.get("target")
    what = {"vengeance": f"to take vengeance on {who(world, target, viewer)}",
            "protection": f"to protect {who(world, target, viewer)}",
            "abstinence": "to kill no one"}.get(v.get("oath"), "an oath")
    verb = {"oath_sworn": "swore on their dao heart", "oath_kept": "kept an oath sworn on their dao heart",
            "oath_broken": "broke an oath sworn on their dao heart"}[v.get("predicate")]
    return cap(f"{person} {verb} {what}.")


SPECIAL_PHRASES["went_mad"] = _went_mad
for _kind in ("oath_sworn", "oath_kept", "oath_broken"):
    SPECIAL_PHRASES[_kind] = _oath_news
```

`narrate/grammar/heart.toml`:
```toml
# The dao heart (phase 5e): trials, epiphanies, oaths, graves, and blades with spirits.

[symbols]
heart_air = ["Your breath slows.", "The world goes very quiet.", "Your pulse is loud in your ears.", "Something old moves in your chest.", "The light seems to hold still.", "A cold clarity settles on you."]
blade_air = ["The steel is warm to the touch.", "The edge catches the light and keeps it.", "The hilt settles into your palm.", "A faint ring hangs in the air.", "The blade seems to lean toward the living.", "Rust-red glints along the fuller."]

[heart_trial]
colour = "dim"
lines = ["#heart_air#"]

[demon_stirred]
colour = "dim"
lines = ["#heart_air#"]

[epiphany]
colour = "dim"
lines = ["#heart_air#"]

[oath_sworn]
colour = "dim"
lines = ["#heart_air#"]

[oath_kept]
colour = "dim"
lines = ["#heart_air#"]

[oath_broken]
colour = "dim"
lines = ["#heart_air#"]

[paid_respects]
colour = "dim"
lines = ["#heart_air#"]

[amends_made]
colour = "dim"
lines = ["#heart_air#"]

[spirit_woke]
colour = "dim"
lines = ["#blade_air#"]

[spirit_felt]
colour = "dim"
lines = ["#blade_air#"]

[blade_whispered]
colour = "dim"
lines = ["#blade_air#"]

[blade_read]
colour = "dim"
lines = ["#blade_air#"]
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_heart_play.py`
Expected: `8 failed, 2 passed`: the engine has no handlers for the new verbs until Step 4 puts the mixin into `Game`.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5e_task7.py`:
```python
"""Phase 5e, Task 7: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('engine/game.py', r'''from engine.crafts import CraftsMixin
''', r'''from engine.crafts import CraftsMixin
from engine.heart import HeartMixin
''')
edit('engine/game.py', r'''class Game(CraftsMixin, AlchemyWorldMixin,''', r'''class Game(HeartMixin, CraftsMixin, AlchemyWorldMixin,''')
edit('engine/game.py', r'''    ("  crafts | anvil | meet | lay <pattern> | forge <form>: forging and formations", "system"),''', r'''    ("  crafts | anvil | meet | lay <pattern> | forge <form>: forging and formations", "system"),
    ("  heart | swear <oath> | respects | face | bury | turn back: the dao heart", "system"),''')
edit('engine/game.py', r'''        events = cultivation.breakthrough_events(self.world, self.player.id, self.place.id)
        return self._cultivated(events, "Your qi has not yet reached a bottleneck.")''', r'''        trial = self._heart_trial()  # phase 5e: a demon rises at the gate first
        if trial is not None:
            return trial
        events = cultivation.breakthrough_events(self.world, self.player.id, self.place.id)
        return self._cultivated(events, "Your qi has not yet reached a bottleneck.")''')
edit('engine/commands.py', r'''    "clear anvil": Action("clear_anvil"),''', r'''    "clear anvil": Action("clear_anvil"),
    "heart": Action("heart"), "respects": Action("pay_respects"), "face": Action("heart_trial", "face"),
    "bury": Action("heart_trial", "bury"), "turn back": Action("heart_trial", "turn_back"),''')
edit('engine/commands.py', r'''    "feed": "feed_servant", "lay": "lay_formation", "forge": "forge",''', r'''    "feed": "feed_servant", "lay": "lay_formation", "forge": "forge", "swear": "swear_oath",''')
edit('engine/sheet.py', r'''    from engine.crafts_page import sheet_crafts_lines  # phase 5d
    lines += sheet_crafts_lines(world, player_id)''', r'''    from engine.crafts_page import sheet_crafts_lines  # phase 5d
    lines += sheet_crafts_lines(world, player_id)
    from engine.heart_page import sheet_heart_lines  # phase 5e
    lines += sheet_heart_lines(world, player_id)''')
edit('narrate/outcomes.py', r'''import narrate.crafts_text  # noqa: E402,F401
''', r'''import narrate.crafts_text  # noqa: E402,F401
import narrate.heart_text  # noqa: E402,F401
''')
edit('tests/test_game.py', r'''                                                                "craft_talk"}  # phase 5d: a smith or a formation master''', r'''                                                                "craft_talk",  # phase 5d: a smith or a formation master
                                                                "heart_talk"}  # phase 5e: amends, a blade read''')
print("task 7 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5e_task7.py`
Expected: `task 7 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_heart_play.py`
Expected: `10 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1509 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the player's heart - the heart page, oaths, graves, the trial at the gate, and amends"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 8: The dao heart end to end

The fork guide's section 14, the speed of a season of NPC hearts, of a fighter with a dao and a spirit, and of the new menus, and a troubled heart played at random.

**Files:**
- Create: `tests/test_heart_fuzz.py`
- Create: `tests/test_heart_season.py`
- Modify (by `.patches/5e_task8.py`): `docs/world-events.md`

**Interfaces:**
- Consumes: Everything above.
- Produces:
  - `docs/world-events.md` section 14; `tests/test_heart_fuzz.py`: `test_a_troubled_heart`.

- [ ] **Step 1: Write the tests**

`tests/test_heart_fuzz.py`:
```python
"""A troubled heart, played at random (phase 5e): a fighter who kills and spares, swears and breaks oaths, meets
their demons at the gate, and carries a hungry blade; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing

WORDS = ["heart", "swear to kill no one", "swear vengeance", "face", "bury", "turn back", "respects", "breakthrough",
         "cultivate", "meditate", "look", "rest", "journal", "challenge", "kill", "spare"]


@pytest.mark.parametrize("seed", [9, 31])
def test_a_troubled_heart(tmp_path, seed):
    import systems.demons as D
    import systems.gear as gear
    import systems.heart as HT
    from systems.bodies import load_body, save_body
    from world.events import commit
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Heart{seed}", world_seed=seed)
    world = app.game.world
    me = world.get_meta("player_id")
    here = next(iter(world.targets(me, "located_in")))
    body = load_body(world, me)
    body.realm, body.bottleneck, body.energy_years = 1, True, 5.0
    body.flags.append("sensed_qi")
    body.meridians["Governing"].state = "open"
    save_body(world, me, body)
    HT.write(world, me, steady=25.0, lean=-50.0, daos={"sword": 0.4})
    for kind, weight in (("fear", 2), ("guilt", 1)):
        D.add_demon(world, me, kind, None, weight)
    blade = gear.make_item(world, "weapon", "sword", 2, me, "bought")
    world.update_data(blade, spirit={"nature": "bloodthirsty", "bond": 0.0, "master": me, "known_by": [me]})
    commit(world, gear.wield_events(world, me, blade, here))
    app.submit("look")
    happened = set()
    for step in range(260):
        game = app.game
        if game is None:
            break
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.55 and app.choices:
            stay = [n for n, c in enumerate(app.choices, 1) if c.action.verb not in ("travel", "routes")]
            app.submit(str(rng.choice(stay or [1])))
        else:
            app.submit(rng.choice(WORDS))
        if rng.random() < 0.05:
            app.handle_key("f4", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    done = happened & {"heart_trial", "oath_sworn", "oath_kept", "oath_broken", "epiphany", "demon_stirred",
                       "blade_whispered", "spirit_felt"}
    assert len(done) >= 2, done
    app.shutdown()
```

`tests/test_heart_season.py`:
```python
import gc
import time
from pathlib import Path

import pytest

import systems.demons as D
import systems.encounters as encounters
import systems.gear as gear
import systems.heart as HT
import systems.heart_world as HW
import systems.lives as lives
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
from systems.duel import fighter_for
from systems.techniques import martial_arts
from world.events import commit


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


def average(fn, n=10) -> float:
    """CPU time per call, averaged: Windows' CPU clock ticks in 15.6 ms steps (4e ruling 19)."""
    fn()
    gc.collect()
    start = time.process_time()
    for _ in range(n):
        fn()
    return (time.process_time() - start) / n


def test_the_fork_guide_covers_the_heart():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("heart_deeds.toml", "`heart = {steady", "steady", "lean", "demons", "daos", "oaths", "returned_to_origin",
                 "kills", "spirit", "mad_until", "check_heart", "check_spirits"):
        assert word in guide, word


class _Undo(Exception):
    pass


def test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5ds(game, monkeypatch):
    """The same 200 people live the same season again and again, rolled back, with and without the heart agenda."""
    from tests.test_alchemy_world_season import crowd
    world = game.world
    everything = list(lives.AGENDAS)
    before = [a for a in everything if a is not HW.season_events]
    people = crowd(world, game.place.id, "heart")
    world.set_time(world.time + lives.SEASON)

    def season(agendas) -> float:
        monkeypatch.setattr(lives, "AGENDAS", agendas)
        gc.collect()
        start = time.process_time()
        try:
            with world.transaction():
                for person in people:
                    lives.catch_up(world, person)
                spent = time.process_time() - start
                raise _Undo
        except _Undo:
            return spent

    timings = {"5d": [], "5e": []}
    for n in range(12):
        which = "5d" if n % 2 == 0 else "5e"
        timings[which].append(season(before if which == "5d" else everything))
    total = {k: sum(sorted(v)[:-1]) for k, v in timings.items()}
    assert total["5e"] <= 1.10 * total["5d"] + 0.016, timings


def test_a_fighter_with_a_dao_and_a_spirit_is_quick_to_weigh(game):
    world, me, here = game.world, game.player.id, game.place.id
    art = martial_arts(world, me)[0].technique.id
    plain = average(lambda: fighter_for(world, me, art), n=50)
    HT.write(world, me, daos={"spear": 0.6})
    blade = gear.make_item(world, "weapon", "spear", 2, me, "bought")
    world.update_data(blade, spirit={"nature": "loyal", "bond": 0.5, "master": me, "known_by": [me]})
    commit(world, gear.wield_events(world, me, blade, here))
    assert average(lambda: fighter_for(world, me, art), n=50) <= 1.10 * plain + 0.0003


def test_the_heart_page_and_the_oath_menu_are_quick(game):
    world, me = game.world, game.player.id
    for n in range(5):
        D.add_demon(world, me, "grudge", n + 100, 2)
    HT.write(world, me, daos={"spear": 0.5, "fire": 0.2, "yang": 0.9})
    for verb in ("heart", "oath_menu"):
        assert average(lambda: game.perform(Action(verb))) < 0.02, verb
```

- [ ] **Step 2: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_heart_fuzz.py tests/test_heart_season.py`
Expected: `1 failed, 5 passed`: the fork guide has no section 14 yet; the speed tests and the fuzz already pass.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5e_task8.py`:
```python
"""Phase 5e, Task 8: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('docs/world-events.md', r'''**The rules:** `check_crafts` in `debug/invariants.py` holds materials to the table, masteries within 0-1, flags to at
least one, formations laid to a pattern and a person, craft skills within 1-5, a named masterwork to the famous index,
and the Meet to a town and a span.
''', r'''**The rules:** `check_crafts` in `debug/invariants.py` holds materials to the table, masteries within 0-1, flags to at
least one, formations laid to a pattern and a person, craft skills within 1-5, a named masterwork to the famous index,
and the Meet to a town and a span.

## 14. The dao heart (phase 5e)

**The heart** is person data `heart = {steady, lean, demons, daos, oaths}`: `steady` 0-100 (at rest 60), `lean` -100
(ruthless) to 100 (righteous). An NPC has none until something writes it; `heart.heart_of` reads a seeded one from
their traits. Deeds move it: the rows of `systems/data/heart_deeds.toml` (an event kind, the actor it moves, its way
and weight) and a duel's verdict. Its effects pivot at 60, so a heart at rest changes no older balance.

**Demons** (`{kind, whom, weight, since}`, at most five: guilt, grudge, fear, grief) are gathered and laid to rest by
listeners in `systems/demons.py`; the heaviest rises at a breakthrough to Second-rate or beyond (`demons.rising`,
`trial_events`), and `cultivation.breakthrough_events` takes `fail` and `shift` for what the trial left.

**Daos** (`daos`: `{form or element: 0-1}`) grow by epiphanies (`systems/daos.py`); one completed sets 2a's
`returned_to_origin`, the way to Life-and-Death. **Oaths** (`oaths`: `{kind, whom, until, sworn_at}`, at most three)
are settled by deaths and the seasons (`systems/oaths.py`), and are facts that spread.

**Blades** count `kills`; a woken `spirit` (`{nature, bond, master, known_by}`) lives on the item
(`systems/blade_spirits.py`); a cursed famous blade's is read from its seed until written. **Madness** is a lives
agenda (`systems/heart_world.py`): a mad NPC carries `mad_until` and hunts the player through 3b's `HUNTER_HOOKS`.

**The rules:** `check_heart` in `debug/invariants.py` holds hearts, demons, daos and oaths to their bounds, and the
mad to the living; `check_spirits` holds a spirit to a nature and a bond within 0-1.
''')
print("task 8 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5e_task8.py`
Expected: `task 8 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_heart_fuzz.py tests/test_heart_season.py`
Expected: `6 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1515 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Run the 500-year soak**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: the dao heart end to end - the fork guide, speed, and a troubled heart's fuzz"
```

The message ends with the session's Co-Authored-By attribution line.

---

## Self-review

- **Spec coverage:**
  - §2 the heart (Task 1; rulings 1-3); §3 demons and the heart trial (Task 2; rulings 4-8);
  - §4 epiphanies and daos (Task 3; rulings 9-11); §5 oaths (Task 4; rulings 12-13);
  - §6 weapon spirits and cursed blades (Task 5; rulings 14-16); §7 the world (Task 6; rulings 17-18);
  - §8 the player (Task 7; rulings 19-20); §9 knowledge (Tasks 5, 7); §10 `check_heart` and `check_spirits` (Tasks 1-6);
  - §11 level of detail and speed (Task 8; ruling 21); §12 testing (every task; the fuzz and speed in Task 8).
- **Dry run:**
  - every task was applied in order to a copy of master at 78e2f25: its new files, the run of Step 3 as it says, its edits, then the green run;
  - the whole suite passed after every task, and the 500-year soak passed at the end, but for two runs:
    - after Task 7 of the first pass, `tests/test_sheet.py::test_f4_toggles_the_sheet` found the sheet's heart lines pushing the arts off a 40-row screen; the sheet now shows the heart only once it has been written, and `test_an_untouched_heart_keeps_off_the_sheet` pins it. Tasks 7 and 8 were replayed with their suites and the soak;
    - after Task 7 of the second pass, 5c's `test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5bs` took over its tenth once. It fails 2 runs in 15 on master as well, so it is older than 5e; the season speed tests of 5c, 5d and 5e are made steadier in 5e's minors.
