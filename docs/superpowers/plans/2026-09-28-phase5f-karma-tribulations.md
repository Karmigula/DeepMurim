# Phase 5f: Karma and Tribulations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Heaven keeps its own account and it comes due at the gate of each realm: a hidden ledger of merit and sin, karmic threads that bring the saved and the wronged back across the player's road, tribulations weighed by karma and played wave by wave (with pills and a tribulation array to shelter under), minor tribulations, and a world where heaven strikes the wicked and temples take alms. And phase 5 closes: 5c's absent masters, 5d's commission lost with a smith.

**Architecture:**
- **Karma is person data** (`karma = {merit, sin, threads}`), apart from 5e's heart: the heart is how one sees oneself, karma is heaven's count. NPCs have none until written; `karma.karma_of` reads a seeded one.
- **Deeds are listeners** on events the world already makes, from one table (`systems/data/karma_deeds.toml`), a duel's verdict and killings.
- **A tribulation is a pending record on the player,** played one wave at a time through the engine's special choices, as a road encounter is.
- **The world's side is 5c-5e's:** retribution a lives agenda of one hash, the karma read only when it falls.

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-28-phase5f-karma-tribulations-design.md`

## Global Constraints

- **Save format:** no save-format version change. New state lives in:
  - person data `karma`, `tribulation`, `noticed_at` and `alms_merit`;
  - a formation record's `sheltered` count; a commission's `price`.
- **Knowledge vs truth:**
  - karma is never shown as a number; a fortune teller reads it in words and names the heaviest threads;
  - one met on the road by fate is known (saved, wronged, or their kin);
  - heaven's strikes and deaths in the lightning are facts that spread.
- **Reads never write:** pages, choices and blocks never write karma; a seeded ledger is read, not stored.
- **One effect per event kind:** new modules `@listen` or register hooks; no handler name is reused.
- **Seeded rolls stay where they were:** new rolls use their own seeded streams (`karma:`, `fated:`, `tribulation_fate:`, `wave:`, `struck:`, `misfortune:`), never the road's or the life clock's shared streams (ruling 6).
- **Speed (CPU time, averaged after `gc.collect()`):**
  - a season of 200 NPCs with the karma agenda stays within +10% of 5e's season;
  - a road journey weighing twelve threads stays within +10%;
  - the tribulation scene and the temple are each under 20 ms;
  - the 500-year soak keeps its limits.
- **Commits:** every commit message ends with the session's Co-Authored-By attribution line.

## Review Focus

1. **4d's tribulation still reads as 4d's:** the lightning, its witnesses and its news at a great breakthrough; no lightning at a lesser one. Task 4 keeps `tests/test_tribulations.py` whole and pins the waves with `test_a_breakthrough_to_first_rate_brings_the_waves_and_holds_the_player`.
2. **The road's own seeded draw is untouched** by the threads hook (ruling 6). Task 2 pins the meetings with `test_one_who_owes_you_repays_you_on_the_road`; the whole suite's road tests hold.
3. **Nothing else happens while heaven's waves hang over the player** (ruling 14). Task 4 pins it.
4. **The karma agenda stays cheap:** within +10% of 5e's season, measured on the same people rolled back. Task 8 pins it with `test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5es`.
5. **Random play through the waves, the temple, a fortune and the threads:** no crash, no rule broken. Task 8 pins it with `test_a_heavy_karma`.

## Plan-time rulings (deviations from the spec, argued)

1. **Karma is its own person data, apart from 5e's heart,** with its own table of deeds: heaven counts the harm done, the heart how one sees oneself, and the two weigh a deed differently. *Cost if wrong:* none.
2. **Only the player's killings are counted;** an NPC's karma is its seed. *Cost if wrong:* NPC killers are not judged.
3. **"A mortal who does not fight" is read as a mortal realm, and one who yielded from the duel that ended in the killing.** *Cost if wrong:* none.
4. **A killing ties the player to up to two of the dead one's kin** (4b brings the kin into the world at a death). *Cost if wrong:* none.
5. **Threads end with either one's death;** the player's heir starts with none. *Cost if wrong:* none.
6. **A fated meeting draws on its own seeded stream (`fated:`),** so a 2b road hook leaves the road's own draw untouched. *Cost if wrong:* none.
7. **A repayment is silver only;** a pill from an alchemist or physician is left for later. *Cost if wrong:* none.
8. **The wronged are a new road-encounter kind (`wronged`), paid with the road's own "pay" choice ("Make amends"),** and their line names the wrong. *Cost if wrong:* none.
9. **A minor tribulation is the player's own event, not 4d's `tribulation`:** 4d's test holds that a lesser breakthrough brings no lightning. *Cost if wrong:* none.
10. **A great tribulation's 4d event comes at its start with no outcome** (its lightning, witnesses and news); the waves tell how it went, and 4d's journal line for it reads "Heaven's lightning gathered". *Cost if wrong:* none.
11. **Heavenly fire alternates with lightning from Transcendent; the demon wave comes mid-way when the player carries a demon, once.** *Cost if wrong:* none.
12. **A tribulation array shelters `round(3 x strength)` waves,** rather than losing a third of the wave's strength: an array's strength is 0-1 and a wave's reaches 6 and more. *Cost if wrong:* none.
13. **Death takes a heavy sinner (net sin 200) who fails the last of six waves or more, and never at a demon wave** (its harm is 5e's). *Cost if wrong:* none.
14. **While a tribulation hangs over the player, only its waves, help and the journal are allowed,** as with a road encounter. *Cost if wrong:* none.
15. **Heaven strikes an NPC whose balance is under -50, not -100:** a seeded sin tops out at 80. *Cost if wrong:* the strike is rarer than the spec meant.
16. **A misfortune is a fifth of the purse or a fractured leg.** *Cost if wrong:* none.
17. **Alms earn at most 30 merit a season.** *Cost if wrong:* none.
18. **A fortune reading costs 50 silver and is its own conversation verb,** which `tests/test_game.py`'s conversation test allows. *Cost if wrong:* none.
19. **Heaven's notice, a misfortune and an estate's refund are told as they come** (a pass after each commit, as 5e's reactions); a breakthrough's own gathering is told by the engine. *Cost if wrong:* none.
20. **An absent master is one whose home town is not the bound's:** NPCs do move, and 5c's ruling 19 had held they never wander. *Cost if wrong:* none.
21. **A smith's estate returns the commission's price,** stored from now on; an older save's commission is returned at twice the stall's price of its grade. *Cost if wrong:* none.
22. **5d's spec marks both deferred rules done.** *Cost if wrong:* none.

## Files

| File | Responsibility |
|---|---|
| `systems/data/karma_deeds.toml`, `systems/karma.py` | Heaven's ledger: merit and sin, deeds, killings, words. |
| `systems/threads.py` | Karmic threads and fated meetings on the road. |
| `systems/tribulations.py` | A tribulation's weight; minor ones; heaven's notice; NPC fates in the lightning. |
| `systems/tribulation_waves.py` | Waves played: endure, a pill, the array, the demon; the end. |
| `systems/karma_world.py` | Retribution, a sinner's misfortune, temples, the fortune's fee. |
| `engine/tribulation.py`, `engine/karma.py` | `TribulationMixin` and `KarmaMixin`: the waves, the temple, a fortune, reactions told. |
| `narrate/tribulation_text.py`, `narrate/karma_text.py`, `narrate/grammar/tribulation5f.toml`, `narrate/grammar/karma.toml` | Outcomes, journal lines, rumours. |

Existing files touched: `systems/world_clock.py`, `systems/events/tribulation.py`, `systems/data/formations.toml`, `systems/control.py`, `systems/craft_world.py`, `debug/invariants.py`, `engine/game.py`, `engine/commands.py`, `engine/roads.py`, `engine/sky.py`, `narrate/outcomes.py`, `narrate/road_text.py`, `narrate/sky_text.py`, `docs/world-events.md`, the 5d spec, and the tests `tests/test_crafts_review.py` and `tests/test_game.py`.

**How each task is laid out:**
1. The tests, as whole new files.
2. The new modules, as whole files.
3. The run that shows what the edits must still do.
4. One patch script, `.patches/5f_taskN.py`, holding the task's edits to existing files (including files made by earlier tasks). Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: Heaven's ledger

A person's karma is person data: merit and sin, heaven's own count, apart from 5e's heart (ruling 1). An NPC's is read from their seed, trade and traits until something writes it. Deeds count through the rows of `systems/data/karma_deeds.toml` and a duel's verdict; a killing by the player is sin, heavier for one who yielded or a mortal (ruling 3), and merit when the dead were wicked. Karma is told only in words. `check_karma` joins the rules.

**Files:**
- Create: `systems/data/karma_deeds.toml`
- Create: `systems/karma.py`
- Create: `tests/test_karma.py`
- Modify (by `.patches/5f_task1.py`): `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: 2b's `duel_ended` verdicts and `died`; 4a's `lives.key`; the deeds of 3b, 4d, 4h, 5a, 5b and 5c named in the table.
- Produces:
  - `K` (systems/karma.py): `DEEDS`, `VERDICTS`, `KILL_SIN`, `KILL_INNOCENT_SIN`, `KILL_WICKED_MERIT`, `WICKED`, `SINFUL`, `VIRTUOUS`, `BALANCE_WORDS`; `seeded(world, person)`, `karma_of(world, person)`, `write(world, person)`, `balance(world, person)`, `add(world, person, merit, sin)`, `words(value)`.
  - `debug.invariants.check_karma(world)`.

- [ ] **Step 1: Write the tests**

`tests/test_karma.py`:
```python
import pytest

import systems.encounters as encounters
import systems.karma as K
from debug.invariants import check_karma
from engine.game import Game
from systems.creation import CreationChoice
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


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "lazy"], "realm": "second-rate", "age": 40}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:karma:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_a_fresh_ledger_is_empty_and_reading_it_writes_nothing(game):
    world, me = game.world, game.player.id
    assert K.karma_of(world, me) == {"merit": 0.0, "sin": 0.0, "threads": []}
    assert world.entity(me).data.get("karma") is None and K.balance(world, me) == 0.0


def test_an_npc_ledger_is_read_from_their_trade_and_traits(game):
    world = game.world
    bandit = someone(game, "bandit", occupation="bandit", traits=["cunning", "greedy"])
    monk = someone(game, "monk", occupation="monk", traits=["kind", "honest"])
    assert K.karma_of(world, bandit)["sin"] >= 20 and K.karma_of(world, monk)["merit"] >= 20
    assert K.karma_of(world, bandit) == K.karma_of(world, bandit) and world.entity(bandit).data.get("karma") is None


def test_every_deed_of_the_table_is_an_event_the_world_makes():
    for kind, row in K.DEEDS.items():
        assert kind in EFFECTS or len(LISTENERS.get(kind, [])) > 2, kind
        assert row["actor"] >= 0 and (row.get("merit", 0) > 0) != (row.get("sin", 0) > 0), kind


def test_a_duels_verdict_counts(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    for verdict in ("spare", "rob", "cripple"):
        K._verdict(world, Event("duel_ended", (me, foe), game.place.id,
                                {"result": "won", "by": "player", "verdict": verdict}), 0)
    assert K.karma_of(world, me)["merit"] == 5 and K.karma_of(world, me)["sin"] == 20


def kill(game, victim):
    commit(game.world, [Event("died", (game.player.id, victim), game.place.id, {"cause": "killed"})])


def test_killing_weighs_on_who_was_killed(game):
    world, me = game.world, game.player.id
    kill(game, someone(game, "fighter"))
    assert K.karma_of(world, me)["sin"] == K.KILL_SIN
    kill(game, someone(game, "mortal", realm="mortal"))
    assert K.karma_of(world, me)["sin"] == K.KILL_SIN + K.KILL_INNOCENT_SIN
    wicked = someone(game, "wicked")
    K.write(world, wicked, sin=200.0)
    kill(game, wicked)
    assert K.karma_of(world, me)["merit"] == K.KILL_WICKED_MERIT
    wolf = someone(game, "wolf", beast=True, occupation="grey wolf")
    kill(game, wolf)
    assert K.balance(world, me) == K.KILL_WICKED_MERIT - K.KILL_SIN - K.KILL_INNOCENT_SIN


def test_killing_one_who_yielded_is_the_heaviest(game):
    world, me, here = game.world, game.player.id, game.place.id
    import systems.duel as duel
    foe = someone(game, "yielded")
    [started] = commit(world, duel.start_events(world, me, foe, here, "duel"))
    d = duel.Duel.from_event(started, world.chronicle_entry(started))
    d.stage, d.harm = "verdict", {"player": 0.0, "opponent": 10.0}  # not broken: they yielded
    commit(world, duel.verdict_events(world, d, "kill"))
    assert K.karma_of(world, me)["sin"] == K.KILL_INNOCENT_SIN


def test_karma_is_told_in_words():
    assert [K.words(v) for v in (150, 50, 0, -50, -200)] == [
        "heaven smiles on you", "your merit outweighs your sins", "your merit and your sins stand even",
        "your sins outweigh your merit", "heaven's patience with you is thin"]


def test_check_karma_flags_a_malformed_ledger(game):
    world, me = game.world, game.player.id
    K.add(world, me, merit=5)
    assert check_karma(world) == []
    K.write(world, me, sin=-3.0)
    assert "karma" in " | ".join(check_karma(world))
```

- [ ] **Step 2: Write the new modules**

`systems/data/karma_deeds.toml`:
```toml
# Deeds heaven counts (phase 5f spec 2). Each row is a kind of event: the actor it counts for (an index into the
# event's actors) and the merit or sin it weighs. Duels and killings are read in systems/karma.py.

[healed]            # treating the sick and hurt (5b)
actor = 0
merit = 5

[worms_killed]      # freeing one bound by a control pill (5c)
actor = 0
merit = 25

[debt_paid]         # a debt paid off for a debtor (3b)
actor = 0
merit = 5

[heirloom_returned] # a clan's heirloom handed home (5a)
actor = 0
merit = 15

[bounty_paid]       # a town kept from the beasts (4d)
actor = 0
merit = 15

[contract_poisoned] # poisoning for pay (5b)
actor = 0
sin = 30

[poison_slipped]    # poison slipped into a leader's cup (4h)
actor = 0
sin = 30

[control_forced]    # a control pill forced down another's throat (5c)
actor = 0
sin = 30

[hall_theft]        # a sect's pill hall robbed (5c)
actor = 0
sin = 15

[false_accusation]  # an innocent accused (4h)
actor = 0
sin = 20

[secret_sold]       # a sect's secret sold to its rival (5c)
actor = 0
sin = 10
```

`systems/karma.py`:
```python
"""Karma (phase 5f spec 2): heaven's own ledger of merit and sin, kept apart from the heart's view of itself.

A person's karma is person data `karma = {merit, sin, threads}` (threads: systems/threads.py). NPCs have none until
something writes it; until then it is read from their seed, occupation and traits. Deeds count (a table,
`systems/data/karma_deeds.toml`, a duel's verdict, and killing). Karma is never shown as a number: a fortune teller
reads it in words.
"""

import tomllib
from pathlib import Path

import systems.lives as lives
from world.events import listen
from world.seed import rng_for

DEEDS = tomllib.loads((Path(__file__).parent / "data" / "karma_deeds.toml").read_text(encoding="utf-8"))
VERDICTS = {"spare": ("merit", 5), "rob": ("sin", 5), "cripple": ("sin", 15)}
KILL_SIN, KILL_INNOCENT_SIN, KILL_WICKED_MERIT = 10, 40, 15
WICKED = -50               # a balance under this: killing them is merit
SINFUL = {"bandit"}, {"cunning", "greedy"}
VIRTUOUS = {"monk", "herbalist", "physician"}, {"kind", "honest"}
BALANCE_WORDS = ((100, "heaven smiles on you"), (30, "your merit outweighs your sins"),
                 (-30, "your merit and your sins stand even"), (-100, "your sins outweigh your merit"),
                 (-1e9, "heaven's patience with you is thin"))


def seeded(world, person: int) -> dict:
    """An NPC's karma before anything writes it: from their seed, trade and traits (spec 2)."""
    entity = world.entity(person)
    rng = rng_for(world.world_seed, f"karma:{lives.key(entity)}")
    occupation, traits = entity.data.get("occupation"), set(entity.data.get("traits") or [])
    sinful = occupation in SINFUL[0] or bool(traits & SINFUL[1])
    virtuous = occupation in VIRTUOUS[0] or bool(traits & VIRTUOUS[1])
    merit = rng.uniform(20, 80) if virtuous else rng.uniform(0, 30)
    sin = rng.uniform(20, 80) if sinful else rng.uniform(0, 30)
    return {"merit": round(merit, 1), "sin": round(sin, 1), "threads": []}


def karma_of(world, person: int) -> dict:
    entity = world.entity(person)
    if entity.data.get("karma") is not None:
        return entity.data["karma"]
    if entity.data.get("is_player"):
        return {"merit": 0.0, "sin": 0.0, "threads": []}
    return seeded(world, person)


def write(world, person: int, **changes) -> dict:
    karma = {**karma_of(world, person), **changes}
    world.update_data(person, karma=karma)
    return karma


def balance(world, person: int) -> float:
    k = karma_of(world, person)
    return round(k["merit"] - k["sin"], 1)


def add(world, person: int, merit: float = 0.0, sin: float = 0.0) -> None:
    k = karma_of(world, person)
    write(world, person, merit=round(k["merit"] + merit, 1), sin=round(k["sin"] + sin, 1))


def words(value: float) -> str:
    return next(word for bound, word in BALANCE_WORDS if value >= bound)


# --- deeds -----------------------------------------------------------------------------------------------------

def _counter(row: dict):
    def counted(world, event, event_id: int) -> None:
        if len(event.actors) > row["actor"] and world.entity(event.actors[row["actor"]]) is not None:
            add(world, event.actors[row["actor"]], merit=row.get("merit", 0), sin=row.get("sin", 0))
    return counted


for _kind, _row in DEEDS.items():
    listen(_kind)(_counter(_row))


@listen("duel_ended")
def _verdict(world, event, event_id: int) -> None:
    d = event.data
    if d.get("result") == "won" and d.get("by") == "player" and d.get("verdict") in VERDICTS \
            and not world.entity(event.actors[1]).data.get("beast"):
        side, amount = VERDICTS[d["verdict"]]
        add(world, event.actors[0], **{side: amount})


def _yielded(world, killer: int, victim: int) -> bool:
    """Whether the victim had yielded: the duel that ended in this killing ended on a yield."""
    return any(e.kind == "duel_ended" and e.actors[:2] == (killer, victim) and e.data.get("reason") == "yielded"
               for e in world.chronicle_about(victim, limit=3))


@listen("died")
def _killing(world, event, event_id: int) -> None:
    killer, victim = event.actors[0], event.actors[-1]
    if killer == victim or not world.entity(killer).data.get("is_player"):
        return
    dead = world.entity(victim)
    if dead.data.get("beast"):
        return
    if balance(world, victim) < WICKED:
        add(world, killer, merit=KILL_WICKED_MERIT)
    elif _yielded(world, killer, victim) or dead.data.get("realm", "mortal") == "mortal":
        add(world, killer, sin=KILL_INNOCENT_SIN)
    else:
        add(world, killer, sin=KILL_SIN)
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_karma.py`
Expected: `1 error`: collection stops: the tests import `check_karma`, which Step 4 adds.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5f_task1.py`:
```python
"""Phase 5f, Task 1: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.heart_world  # noqa: E402,F401  phase 5e: masters driven mad by their demons, and the enlightened
''', r'''import systems.heart_world  # noqa: E402,F401  phase 5e: masters driven mad by their demons, and the enlightened
import systems.karma  # noqa: E402,F401  phase 5f: heaven's ledger of merit and sin
''')
edit('debug/invariants.py', r'''    problems += check_spirits(world)
''', r'''    problems += check_spirits(world)
    problems += check_karma(world)
''')
edit('debug/invariants.py', r'''def check_spirits(world) -> list[str]:''', r'''def check_karma(world) -> list[str]:
    """Heaven's ledger (phase 5f)."""
    out = []
    for person in world.entities_after("person", "karma.merit", -1e9):
        k = person.data["karma"]
        if k["merit"] < 0 or k["sin"] < 0:
            out.append(f"{person.name} (#{person.id}) has a karma out of bounds: merit {k['merit']}, sin {k['sin']}")
    return out


def check_spirits(world) -> list[str]:''')
print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5f_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_karma.py`
Expected: `8 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1529 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: heaven's ledger - merit and sin from deeds and killings, apart from the heart"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 2: Karmic threads and fated meetings

A verdict, a healing, a freeing, an accusation and a killing tie the player to people (ruling 4), at most twelve threads, each ended by a death (ruling 5). On the road the heaviest within reach may come back, on a draw of its own (ruling 6): one owed repays in silver (ruling 7), one wronged stands in the road as a new kind of encounter and takes amends through the road's own "pay" (ruling 8).

**Files:**
- Create: `systems/threads.py`
- Create: `tests/test_threads.py`
- Modify (by `.patches/5f_task2.py`): `systems/world_clock.py`, `narrate/road_text.py`, `engine/roads.py`

**Interfaces:**
- Consumes: Task 1's `karma`; 2b's `ROAD_HOOKS`, `encounter_events`, `encounter_resolved`; 4b's `kin_of`; 3a's `beliefs.home_of`.
- Produces:
  - `TH` (systems/threads.py): `OWED_TO_YOU`, `OWED_BY_YOU`, `MAX_THREADS`, `MAX_WEIGHT`, `FATE_RANGE`, `FATE_CHANCE`, `REPAY`, `AMENDS`, `AMENDS_MERIT`, `BEREAVED_KIN`; `threads(world, person)`, `add_thread(world, person, whom, kind, weight)`, `cut(world, person, whom, kind)`, `owed(thread)`, `fated_events(world, player, town, rng)`; events `fated_repaid`.
  - the `wronged` encounter's line, and amends paid through 2b's road "pay".

- [ ] **Step 1: Write the tests**

`tests/test_threads.py`:
```python
import pytest

import systems.encounters as encounters
import systems.karma as K
import systems.threads as TH
import systems.travel as travel
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit
from world.gen.materialize import ensure_town


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


def someone(game, tag, town=None, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "third-rate", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:thread:{tag}")
    game.world.relate(pid, town or game.place.id, "located_in")
    return pid


def elsewhere(game):
    return ensure_town(game.world, *travel.routes_from(game.world, game.place)[0].dest)


def kinds(game):
    return sorted((t["kind"], t["weight"]) for t in TH.threads(game.world, game.player.id))


def test_a_verdict_a_healing_a_freeing_and_an_accusation_tie_threads(game):
    world, me, here = game.world, game.player.id, game.place.id
    a, b, c, d = (someone(game, t) for t in "abcd")
    for verdict, foe in (("spare", a), ("cripple", b)):
        TH._from_duel(world, Event("duel_ended", (me, foe), here, {"result": "won", "by": "player",
                                                                  "verdict": verdict}), 0)
    TH._from_healing(world, Event("healed", (me, c), here, {}), 0)
    TH._from_freeing(world, Event("worms_killed", (me, c), here, {}), 0)
    TH._from_accusing(world, Event("false_accusation", (me, d), here, {}), 0)
    assert kinds(game) == [("accused", 2), ("crippled", 2), ("freed", 3), ("healed", 1), ("spared", 2)]
    TH.add_thread(world, me, a, "spared")
    assert ("spared", 3) in kinds(game)


def test_at_most_twelve_threads_the_lightest_going(game):
    world, me = game.world, game.player.id
    TH.add_thread(world, me, 900, "healed")
    for n in range(12):
        TH.add_thread(world, me, 1000 + n, "bereaved")
    assert len(TH.threads(world, me)) == 12 and ("healed", 1) not in kinds(game)


def test_a_killing_ties_the_player_to_the_dead_ones_kin_and_a_death_ends_its_threads(game):
    world, me, here = game.world, game.player.id, game.place.id
    victim, brother = someone(game, "victim"), someone(game, "brother")
    world.relate(victim, brother, "kin_of", data={"role": "sibling"})
    TH.add_thread(world, me, victim, "robbed")
    commit(world, [Event("died", (me, victim), here, {"cause": "killed"})])
    tied = [t["whom"] for t in TH.threads(world, me)]  # 4b brings the dead one's kin into the world
    assert brother in tied and len(tied) == TH.BEREAVED_KIN and set(k for k, _ in kinds(game)) == {"bereaved"}
    commit(world, [Event("died", (brother, brother), here, {"cause": "illness", "world": True})])
    assert brother not in [t["whom"] for t in TH.threads(world, me)] and len(TH.threads(world, me)) == 1


def test_one_who_owes_you_repays_you_on_the_road(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TH, "FATE_CHANCE", 1.0)
    friend = someone(game, "friend", town=elsewhere(game))
    TH.add_thread(world, me, friend, "spared")
    assert TH.fated_events(world, me, world.entity(elsewhere(game)), None) is None  # at their own home: no road
    [event] = TH.fated_events(world, me, game.place, None)
    assert event.kind == "fated_repaid" and event.data["silver"] == TH.REPAY * 2 * 2
    commit(world, [event])
    assert silver_of(world, me) == 1000 + TH.REPAY * 4 and kinds(game) == []


def test_one_you_wronged_stands_in_the_road_and_takes_amends(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TH, "FATE_CHANCE", 1.0)
    victim = someone(game, "victim", town=elsewhere(game))
    TH.add_thread(world, me, victim, "crippled")
    events = TH.fated_events(world, me, game.place, None)
    assert events[-1].kind == "encounter" and events[-1].data == {"kind": "wronged", "toll": 100, "thread": "crippled"}
    commit(world, events)
    game.encounter = encounters.encounter_state(events[-1])
    turn = game._turn([])
    assert "Make amends (100 silver)" in [c.label for c in turn.choices]
    game.perform(Action("road", "pay"))
    assert kinds(game) == [] and K.karma_of(world, me)["merit"] == TH.AMENDS_MERIT and silver_of(world, me) == 900


def test_the_wronged_say_why_they_stand_there(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TH, "FATE_CHANCE", 1.0)
    victim = someone(game, "victim", town=elsewhere(game))
    TH.add_thread(world, me, victim, "robbed")
    lines = game._commit(TH.fated_events(world, me, game.place, None))
    assert any("You took my silver" in t for t, _ in lines)
```

- [ ] **Step 2: Write the new modules**

`systems/threads.py`:
```python
"""Karmic threads (phase 5f spec 3): the people a life is tied to, saved or wronged, and the road that brings them
back across it.

A thread is `{whom, kind, weight, since}` in the karma's `threads`, at most twelve. Those owed to the player repay
them when fate brings them onto the road; those the player wronged stand in it, to be paid amends or fought. A
thread ends when either one dies.
"""

import systems.encounters as encounters
import systems.karma as K
from systems.beliefs import home_of
from systems.kin import kin_of
from systems.realms import realm_index
from world.events import Event, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

OWED_TO_YOU = {"spared": 2, "healed": 1, "freed": 3}
OWED_BY_YOU = {"robbed": 1, "crippled": 2, "bereaved": 3, "accused": 2}
MAX_THREADS, MAX_WEIGHT = 12, 3
FATE_RANGE, FATE_CHANCE = 3, 0.05   # regions from their home; a journey's chance per weight
REPAY = 20                          # silver x weight x (realm + 1)
AMENDS, AMENDS_MERIT = 50, 5        # silver x weight; the merit of amends paid
BEREAVED_KIN = 2                    # the kin of the one killed who take up the thread


def threads(world, person: int) -> list[dict]:
    return list(K.karma_of(world, person)["threads"])


def add_thread(world, person: int, whom: int, kind: str, weight: int | None = None) -> None:
    found = threads(world, person)
    weight = weight or {**OWED_TO_YOU, **OWED_BY_YOU}[kind]
    same = next((t for t in found if t["whom"] == whom and t["kind"] == kind), None)
    if same is not None:
        same["weight"] = min(MAX_WEIGHT, same["weight"] + weight)
    else:
        found.append({"whom": whom, "kind": kind, "weight": min(MAX_WEIGHT, weight), "since": world.time})
        if len(found) > MAX_THREADS:
            found.remove(min(found, key=lambda t: (t["weight"], -t["since"])))
    K.write(world, person, threads=found)


def cut(world, person: int, whom: int, kind: str | None = None) -> None:
    K.write(world, person, threads=[t for t in threads(world, person)
                                    if not (t["whom"] == whom and (kind is None or t["kind"] == kind))])


def owed(thread: dict) -> bool:
    """Whether the other one owes the player (else the player owes them)."""
    return thread["kind"] in OWED_TO_YOU


def _player(world) -> int | None:
    return world.get_meta("player_id")


# --- gathered ---------------------------------------------------------------------------------------------------

@listen("duel_ended")
def _from_duel(world, event, event_id: int) -> None:
    d, (player, foe) = event.data, event.actors
    if d.get("result") != "won" or d.get("by") != "player" or world.entity(foe).data.get("beast"):
        return
    kind = {"spare": "spared", "rob": "robbed", "cripple": "crippled"}.get(d.get("verdict"))
    if kind is not None:
        add_thread(world, player, foe, kind)


@listen("healed")
def _from_healing(world, event, event_id: int) -> None:
    if event.actors[0] == _player(world) and len(event.actors) > 1:
        add_thread(world, event.actors[0], event.actors[1], "healed")


@listen("worms_killed")
def _from_freeing(world, event, event_id: int) -> None:
    if event.actors[0] == _player(world):
        add_thread(world, event.actors[0], event.actors[1], "freed")


@listen("false_accusation")
def _from_accusing(world, event, event_id: int) -> None:
    if event.actors[0] == _player(world):
        add_thread(world, event.actors[0], event.actors[1], "accused")


@listen("died")
def _from_death(world, event, event_id: int) -> None:
    """A thread ends with the one it ties to; a killing ties the player to the dead one's kin."""
    killer, victim, player = event.actors[0], event.actors[-1], _player(world)
    if player is None or victim == player or world.entity(player) is None:
        return
    if any(t["whom"] == victim for t in threads(world, player)):
        cut(world, player, victim)
    if killer == player and not world.entity(victim).data.get("beast"):
        for kin, _ in kin_of(world, victim)[:BEREAVED_KIN]:
            if kin != player:
                add_thread(world, player, kin, "bereaved")


# --- fated meetings on the road ---------------------------------------------------------------------------------

def fated_events(world, player: int, town, rng) -> list[Event] | None:
    """The heaviest thread within reach may cross the road (a 2b road hook; its own seeded draw)."""
    found = sorted(threads(world, player), key=lambda t: (-t["weight"], t["since"]))
    if not found:
        return None
    here = region_of(world, town.id).data
    draw = rng_for(world.world_seed, f"fated:{player}:{world.time}")
    for thread in found:
        other = world.entity(thread["whom"])
        home = home_of(world, thread["whom"]) if other is not None and not other.data.get("dead") else None
        if home is None or home == town.id:
            continue
        there = region_of(world, home).data
        if max(abs(there["x"] - here["x"]), abs(there["y"] - here["y"])) > FATE_RANGE:
            continue
        if draw.random() >= FATE_CHANCE * thread["weight"]:
            return None
        if owed(thread):
            realm = realm_index(other.data.get("realm", "mortal"))
            return [Event("fated_repaid", (player, thread["whom"]), town.id,
                          {"kind": thread["kind"], "weight": thread["weight"],
                           "silver": REPAY * thread["weight"] * (realm + 1)})]
        return encounters.encounter_events(player, thread["whom"], town.id, "wronged", AMENDS * thread["weight"],
                                           {"thread": thread["kind"]})
    return None


encounters.ROAD_HOOKS.append(fated_events)


@effect("fated_repaid")
def _repaid(world, event) -> None:
    player, whom = event.actors
    world.update_data(player, silver=world.entity(player).data.get("silver", 0) + event.data["silver"])
    cut(world, player, whom, event.data["kind"])


@listen("encounter_resolved")
def _amends(world, event, event_id: int) -> None:
    """Amends paid to one the player wronged spend the thread, and heaven counts it."""
    if event.data.get("kind") != "wronged" or event.data.get("how") != "paid":
        return
    player, whom = event.actors
    for t in [t for t in threads(world, player) if t["whom"] == whom and not owed(t)]:
        cut(world, player, whom, t["kind"])
    K.add(world, player, merit=AMENDS_MERIT)
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_threads.py`
Expected: `2 failed, 4 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5f_task2.py`:
```python
"""Phase 5f, Task 2: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.karma  # noqa: E402,F401  phase 5f: heaven's ledger of merit and sin
''', r'''import systems.karma  # noqa: E402,F401  phase 5f: heaven's ledger of merit and sin
import systems.threads  # noqa: E402,F401  phase 5f: karmic threads, and fated meetings on the road
''')
edit('narrate/road_text.py', r'''        "bounty_hunter": f"{cap(name)}, a bounty hunter, blocks the road. There is a price on your head.",
    }[d["kind"]]''', r'''        "bounty_hunter": f"{cap(name)}, a bounty hunter, blocks the road. There is a price on your head.",
        "wronged": f'{cap(name)} stands in the road. "{WRONGS.get(d.get("thread"), "You owe me.")}"',  # phase 5f
    }[d["kind"]]''')
edit('narrate/road_text.py', r'''@outcome("encounter")''', r'''WRONGS = {"robbed": "You took my silver, and you owe me.", "crippled": "You left me like this.",
          "bereaved": "You killed my kin.", "accused": "You named me a traitor, and they believed you."}


@outcome("encounter")''')
edit('engine/roads.py', r'''        if e["kind"] == "bandit":
            choices.append(Choice(f"Pay the toll ({e['toll']} silver)", Action("road", "pay")))''', r'''        if e["kind"] == "wronged":  # phase 5f: one you wronged, owed amends
            choices.append(Choice(f"Make amends ({e['toll']} silver)", Action("road", "pay")))
        if e["kind"] == "bandit":
            choices.append(Choice(f"Pay the toll ({e['toll']} silver)", Action("road", "pay")))''')
edit('engine/roads.py', r'''            if e["kind"] != "bandit":
                return self._turn([("There is no toll to pay.", "system")])
            if silver_of(self.world, me) < e["toll"]:
                return self._turn([(f"You don't have {e['toll']} silver.", "system")])
            lines = self._commit(payment_events(me, person, place, e["toll"], "toll"))''', r'''            if e["kind"] not in ("bandit", "wronged"):
                return self._turn([("There is no toll to pay.", "system")])
            if silver_of(self.world, me) < e["toll"]:
                return self._turn([(f"You don't have {e['toll']} silver.", "system")])
            reason = "amends" if e["kind"] == "wronged" else "toll"
            lines = self._commit(payment_events(me, person, place, e["toll"], reason))''')
print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5f_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_threads.py`
Expected: `6 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1535 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: karmic threads - the saved and the wronged, and fated meetings on the road"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 3: Tribulations weighed by karma

A tribulation's waves and their strength grow with the realm and with net sin, and lighten with merit; heavenly fire comes from Transcendent and the heart's demon once, mid-way (ruling 11). A gathering tribulation waits over the player. Heaven takes notice of a heavy sinner once a year. 4d's lightning over an NPC now weighs their karma, and can kill: news.

**Files:**
- Create: `systems/tribulations.py`
- Create: `tests/test_tribulations_5f.py`
- Modify (by `.patches/5f_task3.py`): `systems/world_clock.py`, `systems/events/tribulation.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Task 1's `karma`; 5e's `demons`; 4d's `_npc_tribulation`; 3a's `record_fact`.
- Produces:
  - `TR` (systems/tribulations.py): `WAVE_KINDS`, `GREAT_REALM`, `MINOR_REALM`, `FIRE_REALM`, `MAX_WAVES`, `SIN_WAVE`, `SIN_STRENGTH`, `MERIT_STRENGTH`, `NOTICE_SIN`, `NPC_DEATH`, `NPC_DEATH_STEP`, `NPC_DEATH_MAX`; `plan(world, person, realm, minor)`, `pending(world, person)`, `gather_events(world, person, place, realm, minor, why)`, `season_hook(world, n)`, `npc_death_chance(world, person)`, `npc_fate_events(world, person, place, season)`; events `tribulation_gathers`.
  - an NPC's fate in 4d's `_npc_tribulation`; a gathering tribulation in `check_karma`.

- [ ] **Step 1: Write the tests**

`tests/test_tribulations_5f.py`:
```python
import pytest

import systems.demons as D
import systems.encounters as encounters
import systems.karma as K
import systems.lives as lives
import systems.tribulations as TR
from debug.invariants import check_karma
from engine.game import Game
from systems import founding
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


def test_a_great_tribulation_grows_with_the_realm_and_a_minor_one_is_one_wave(game):
    world, me = game.world, game.player.id
    assert TR.plan(world, me, 3, False) == {"realm": 3, "minor": False, "strength": 3.0, "waves": ["lightning"] * 2}
    assert TR.plan(world, me, 7, False)["waves"] == ["lightning", "fire"] * 3
    assert TR.plan(world, me, 2, True)["waves"] == ["lightning"]


def test_sin_adds_waves_and_weight_and_merit_lightens_them(game):
    world, me = game.world, game.player.id
    K.write(world, me, sin=250.0)
    heavy = TR.plan(world, me, 3, False)
    assert len(heavy["waves"]) == 4 and heavy["strength"] == 8.0
    K.write(world, me, sin=0.0, merit=150.0)
    assert TR.plan(world, me, 3, False)["strength"] == 1.5


def test_a_carried_demon_comes_as_a_wave(game):
    world, me = game.world, game.player.id
    D.add_demon(world, me, "grief", 5, 2)
    assert TR.plan(world, me, 4, False)["waves"] == ["lightning", "demon", "lightning", "lightning"]


def test_a_gathering_tribulation_waits_over_the_player(game):
    world, me = game.world, game.player.id
    commit(world, TR.gather_events(world, me, game.place.id, 3, False, "breakthrough"))
    assert TR.pending(world, me) == {"realm": 3, "minor": False, "strength": 3.0, "waves": ["lightning"] * 2,
                                     "wave": 0, "failed": []}
    assert check_karma(world) == []


def test_heaven_takes_notice_of_heavy_sin_once_a_year(game):
    world, me = game.world, game.player.id
    assert TR.season_hook(world, 0) == []
    K.write(world, me, sin=200.0)
    [event] = TR.season_hook(world, 0)
    assert event.kind == "tribulation_gathers" and event.data["minor"] and event.data["why"] == "notice"
    world.set_time(world.time + lives.SEASON)
    assert TR.season_hook(world, 1) == []
    world.set_time(world.time + 4 * lives.SEASON)
    assert TR.season_hook(world, 5)


def test_the_lightning_can_kill_the_wicked_and_it_is_news(game):
    world, town = game.world, game.place.id
    n = world.time // lives.SEASON
    fiends = []
    for i in range(30):
        fiend = founding.make_person(world, f"test:fiend:{i}", town, occupation="monk", age=50, realm="second-rate")
        K.write(world, fiend, sin=600.0, merit=0.0)
        fiends.append(fiend)
    assert TR.npc_death_chance(world, fiends[0]) == TR.NPC_DEATH_MAX
    for fiend in fiends:
        commit(world, [Event("broke_through", (fiend,), town, {"realm": 3, "season": n})])
    dead = [f for f in fiends if world.entity(f).data.get("dead")]
    assert 5 <= len(dead) <= 25 and world.facts(predicate="fell_to_tribulation", subject=dead[0])


def test_check_karma_flags_a_malformed_tribulation(game):
    world, me = game.world, game.player.id
    world.update_data(me, tribulation={"realm": 3, "minor": False, "strength": 0.2, "waves": ["hail"], "wave": 0,
                                       "failed": []})
    assert "tribulation" in " | ".join(check_karma(world))
```

- [ ] **Step 2: Write the new modules**

`systems/tribulations.py`:
```python
"""Tribulations weighed by karma (phase 5f spec 4): how many waves heaven sends, how hard, and of what, and the
minor tribulations of a lesser breakthrough and of a sin grown too heavy; an NPC's fate in the lightning.

A tribulation gathering over the player is person data `tribulation = {realm, minor, strength, waves, wave,
failed}`, played wave by wave (systems/tribulation_waves.py). A great tribulation is still 4d's: its lightning, its
witnesses, its news. A minor one is the player's own.
"""

import systems.demons as D
import systems.karma as K
import systems.lives as lives
import systems.world_clock as world_clock
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, effect, listen
from world.seed import seed_for

WAVE_KINDS = ("lightning", "fire", "demon")
GREAT_REALM, MINOR_REALM, FIRE_REALM = 3, 2, 5
MAX_WAVES = 6
SIN_WAVE = 100             # one wave more for each full 100 of net sin
SIN_STRENGTH, MERIT_STRENGTH = 50, 100
NOTICE_SIN = 150           # net sin at which heaven takes notice, once a year
NPC_DEATH, NPC_DEATH_STEP, NPC_DEATH_MAX = 0.02, 0.001, 0.5


def plan(world, person: int, realm: int, minor: bool) -> dict:
    """The tribulation heaven sends: its waves in order and their strength (spec 4)."""
    bal = K.balance(world, person)
    count = 1 if minor else min(MAX_WAVES, realm - 1)
    count += int(max(0.0, -bal) // SIN_WAVE)
    strength = realm + max(0.0, -bal) / SIN_STRENGTH - (bal / MERIT_STRENGTH if bal > 0 else 0.0)
    waves = ["fire" if realm >= FIRE_REALM and i % 2 else "lightning" for i in range(count)]
    if D.demons(world, person):
        waves.insert(len(waves) // 2, "demon")
    return {"realm": realm, "minor": minor, "strength": round(max(1.0, strength), 2), "waves": waves}


def pending(world, person: int) -> dict | None:
    return world.entity(person).data.get("tribulation")


def gather_events(world, person: int, place, realm: int, minor: bool, why: str) -> list[Event]:
    return [Event("tribulation_gathers", (person,), place, {**plan(world, person, realm, minor), "why": why})]


@effect("tribulation_gathers")
def _gathers(world, event) -> None:
    d = event.data
    world.update_data(event.actors[0], tribulation={"realm": d["realm"], "minor": d["minor"],
                                                    "strength": d["strength"], "waves": d["waves"], "wave": 0,
                                                    "failed": []})


# --- heaven takes notice ------------------------------------------------------------------------------------------

def season_hook(world, n: int) -> list[Event]:
    """A player whose sin outweighs their merit by 150 draws a minor tribulation, at most once a year."""
    player = world.get_meta("player_id")
    entity = world.entity(player) if player is not None else None
    if entity is None or entity.data.get("dead") or entity.data.get("tribulation"):
        return []
    if -K.balance(world, player) < NOTICE_SIN or world.time - entity.data.get("noticed_at", -10 ** 9) < 4 * lives.SEASON:
        return []
    world.update_data(player, noticed_at=world.time)
    from systems.bodies import load_body  # the body comes after the karma in the import graph
    here = next(iter(world.targets(player, "located_in")), None)
    return gather_events(world, player, here, load_body(world, player).realm, True, "notice")


world_clock.SEASON_HOOKS.append(season_hook)


# --- NPCs in the lightning ------------------------------------------------------------------------------------------

def npc_death_chance(world, person: int) -> float:
    return round(min(NPC_DEATH_MAX, NPC_DEATH + NPC_DEATH_STEP * max(0.0, -K.balance(world, person))), 3)


def npc_fate_events(world, person: int, place, season: int | None) -> list[Event]:
    """Whether 4d's lightning over an NPC kills them (one hash of their own)."""
    entity = world.entity(person)
    if entity is None or entity.data.get("dead") or entity.data.get("is_player") or place is None:
        return []
    roll = seed_for(world.world_seed, f"tribulation_fate:{lives.key(entity)}:{season}") / 2 ** 64
    if roll >= npc_death_chance(world, person):
        return []
    return [Event("died", (person, person), place, {"cause": "tribulation", "world": True})]


@listen("died")
def _fell(world, event, event_id: int) -> None:
    if event.data.get("cause") != "tribulation":
        return
    person = event.actors[-1]
    variant = make_variant("fell_to_tribulation", person, None, place=place_name(world, event.place),
                           realm=world.entity(person).data.get("realm", "mortal"))
    record_fact(world, person, "fell_to_tribulation", None, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_tribulations_5f.py`
Expected: `2 failed, 5 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5f_task3.py`:
```python
"""Phase 5f, Task 3: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.threads  # noqa: E402,F401  phase 5f: karmic threads, and fated meetings on the road
''', r'''import systems.threads  # noqa: E402,F401  phase 5f: karmic threads, and fated meetings on the road
import systems.tribulations  # noqa: E402,F401  phase 5f: tribulations weighed by karma, minor ones, NPC fates
''')
edit('systems/events/tribulation.py', r'''    if realm >= TRIBULATION_REALM and event.place is not None:
        commit(world, trigger_events(world, event.actors[0], event.place, realm, season=event.data.get("season")))''', r'''    if realm >= TRIBULATION_REALM and event.place is not None:
        from systems.tribulations import npc_fate_events  # phase 5f: karma weighs the lightning
        commit(world, trigger_events(world, event.actors[0], event.place, realm, season=event.data.get("season"))
               + npc_fate_events(world, event.actors[0], event.place, event.data.get("season")))''')
edit('debug/invariants.py', r'''            out.append(f"{person.name} (#{person.id}) has a karma out of bounds: merit {k['merit']}, sin {k['sin']}")
''', r'''            out.append(f"{person.name} (#{person.id}) has a karma out of bounds: merit {k['merit']}, sin {k['sin']}")
    from systems.tribulations import WAVE_KINDS
    for person in world.entities_after("person", "tribulation.strength", -1):
        t = person.data["tribulation"]
        if t["strength"] < 1 or any(w not in WAVE_KINDS for w in t["waves"]) or not 0 <= t["wave"] <= len(t["waves"]):
            out.append(f"{person.name} (#{person.id}) awaits a malformed tribulation: {t}")
''')
print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5f_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_tribulations_5f.py`
Expected: `7 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1542 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: tribulations weighed by karma - waves and weight, heaven's notice, and the fallen"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 4: Waves played through, and the tribulation array

The player meets each wave in turn (ruling 14): endure it, swallow a strong enough pill, shelter under a tribulation array (a new pattern of 5d's table, ruling 12), or face or bury the demon. A failed lightning wave scars, heavenly fire cripples a meridian; the heaviest sinner can die (ruling 13). A great tribulation keeps 4d's event at its start (ruling 10); a minor one comes at Second-rate (ruling 9).

**Files:**
- Create: `systems/tribulation_waves.py`
- Create: `engine/tribulation.py`
- Create: `narrate/tribulation_text.py`
- Create: `narrate/grammar/tribulation5f.toml`
- Create: `tests/test_tribulation_waves.py`
- Modify (by `.patches/5f_task4.py`): `systems/data/formations.toml`, `systems/world_clock.py`, `engine/sky.py`, `engine/game.py`, `engine/commands.py`, `narrate/outcomes.py`, `narrate/sky_text.py`, `tests/test_crafts_review.py`

**Interfaces:**
- Consumes: Task 3's `tribulations`; 5b's `pills`; 5d's `formations`; 5e's `demons` and `heart_trial`; 4d's `trigger_events`.
- Produces:
  - `TW` (systems/tribulation_waves.py): `ENDURE`, `BOUNDS`, `ARRAY`, `SHELTER_WAVES`, `DEADLY_WAVES`, `DEADLY_SIN`, `CLEAN_INSIGHT`, `CLEAN_MERIT`, `CHOICES`; `current(world, person)`, `endure_chance(world, person, strength)`, `pills_for(world, person, strength)`, `shelter_of(world, person, place)`, `wave_block(world, person, place, choice, item)`, `wave_events(world, person, place, choice, item)`; events `heart_trial`, `tribulation_passed`, `tribulation_wave`.
  - `engine/tribulation.py` (engine/tribulation.py): `WAVE_VERBS`, `NTH`.
  - the `tribulation` pattern; the waves in 4d's `SkyMixin`; `TribulationMixin` in `Game`.

- [ ] **Step 1: Write the tests**

`tests/test_tribulation_waves.py`:
```python
import pytest

import systems.demons as D
import systems.encounters as encounters
import systems.formations as FM
import systems.karma as K
import systems.realms as realms
import systems.tribulation_waves as TW
import systems.tribulations as TR
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
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


def text(turn):
    return " | ".join(t for t, _ in turn.lines)


def gather(game, realm=3, minor=False):
    commit(game.world, TR.gather_events(game.world, game.player.id, game.place.id, realm, minor, "breakthrough"))


def at_the_bottleneck(game, realm):
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years, body.bottleneck = realm, realms.REALMS[realm + 1].threshold, True
    save_body(game.world, game.player.id, body)


def pill(game, grade):
    item = game.world.add_entity("pill", f"a grade-{grade} pill", {"effect": "qi", "grade": grade, "purity": 0.5})
    game.world.relate(game.player.id, item, "owns")
    return item


def test_a_breakthrough_to_first_rate_brings_the_waves_and_holds_the_player(game, monkeypatch):
    monkeypatch.setattr(realms, "breakthrough_chance", lambda body, met: 1.0)
    at_the_bottleneck(game, 2)
    turn = game.perform(Action("breakthrough"))
    assert "Clouds gather" in text(turn) and "The first wave of 2: heaven's lightning gathers." in text(turn)
    assert [c.label for c in turn.choices] == ["Endure it"]
    assert "Heaven's tribulation is upon you." in text(game.perform(Action("look")))


def test_a_breakthrough_to_second_rate_brings_a_minor_one(game, monkeypatch):
    monkeypatch.setattr(realms, "breakthrough_chance", lambda body, met: 1.0)
    at_the_bottleneck(game, 1)
    body = load_body(game.world, game.player.id)
    body.meridians["Governing"].state = "open"
    save_body(game.world, game.player.id, body)
    turn = game.perform(Action("breakthrough"))
    assert TR.pending(game.world, game.player.id)["minor"] and "Even this gate is watched." in text(turn)
    assert game.world.facts(predicate="tribulation") == []


def test_enduring_every_wave_comes_through_clean_with_insight_and_merit(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TW, "BOUNDS", (1.0, 1.0))
    body = load_body(world, me)
    body.realm = 3
    save_body(world, me, body)
    gather(game)
    insight = load_body(world, me).insight
    game.perform(Action("wave", "endure"))
    turn = game.perform(parse("endure", [], []))
    assert "You come through heaven's tribulation whole." in text(turn) and TR.pending(world, me) is None
    assert load_body(world, me).insight == insight + 30 and K.karma_of(world, me)["merit"] == TW.CLEAN_MERIT


def test_a_failed_lightning_wave_scars_and_heavenly_fire_cripples(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TW, "BOUNDS", (0.0, 0.0))
    body = load_body(world, me)
    body.realm, body.meridians["Lung"].state = 5, "open"
    save_body(world, me, body)
    gather(game, realm=5)
    for _ in range(4):
        turn = game.perform(Action("wave", "endure"))
    assert "heaven has taken something with it" in text(turn)
    body = load_body(world, me)
    assert any(i.kind == "internal" for i in body.injuries) and body.meridians["Lung"].state == "damaged"


def test_a_strong_enough_pill_turns_a_wave_aside(game):
    world, me = game.world, game.player.id
    gather(game)
    weak, strong = pill(game, 1), pill(game, 2)
    turn = game._turn([])
    assert [c.label for c in turn.choices] == ["Endure it", "Swallow a grade-2 pill against it"]
    turn = game.perform(Action("wave", ("spend", strong)))
    assert "breaks around you like water on stone" in text(turn) and world.entity(strong).data.get("used")
    assert TW.wave_block(world, me, game.place.id, "spend", weak) == "You have no pill strong enough."


def test_a_tribulation_array_shelters_three_waves_at_full_strength(game):
    world, me, here = game.world, game.player.id, game.place.id
    body = load_body(world, me)
    body.realm = 5
    save_body(world, me, body)
    FM.place_formation(world, here, TW.ARRAY, me, 1.0)
    gather(game, realm=5)  # four waves: the array takes three
    for _ in range(3):
        turn = game.perform(Action("wave", "shelter"))
    assert "Shelter under the tribulation array" not in [c.label for c in turn.choices]
    assert TW.wave_block(world, me, here, "shelter") == "No tribulation array shelters you here."


def test_the_demon_comes_as_a_wave_and_is_faced(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(D, "FACE_BOUNDS", (1.0, 1.0))
    monkeypatch.setattr(TW, "BOUNDS", (1.0, 1.0))
    D.add_demon(world, me, "fear", None, 2)
    gather(game)
    game.perform(Action("wave", "endure"))
    turn = game._turn([])
    assert [c.label for c in turn.choices] == ["Face it", "Bury it"]
    turn = game.perform(parse("face", [], []))
    assert "You look the fear of death in the face" in text(turn) and D.demons(world, me) == []


def test_the_heaviest_sinner_can_die_in_the_last_wave(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TW, "BOUNDS", (0.0, 0.0))
    K.write(world, me, sin=450.0)
    body = load_body(world, me)
    body.realm = 3
    save_body(world, me, body)
    gather(game, realm=3)
    t = TR.pending(world, me)
    assert len(t["waves"]) == 6
    for _ in range(6):
        events = TW.wave_events(world, me, game.place.id, "endure")
        commit(world, events)
    assert events[-1].kind == "died" and events[-2].data["died"]
```

- [ ] **Step 2: Write the new modules**

`systems/tribulation_waves.py`:
```python
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
```

`engine/tribulation.py`:
```python
"""A tribulation in the engine (phase 5f spec 5, 7): heaven's waves one at a time, and nothing else until they pass."""

import systems.tribulation_waves as TW
import systems.tribulations as TR
from engine.actions import Action, Choice
from engine.heart_page import demon_words
import systems.demons as D

WAVE_VERBS = frozenset({"wave", "heart_trial", "help", "journal", "unknown", "ambiguous"})
NTH = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth")


class TribulationMixin:
    def _gate(self, action):
        if TR.pending(self.world, self.player.id) is not None and action.verb not in WAVE_VERBS:
            return self._turn([("Heaven's tribulation is upon you. There is nothing else now.", "system")]
                              + self._wave_lines())
        return super()._gate(action)

    def _special_choices(self):
        now = TW.current(self.world, self.player.id)
        if now is None:
            return super()._special_choices()
        world, me, here = self.world, self.player.id, self.place.id
        kind, strength = now
        if kind == "demon":
            return [Choice("Face it", Action("wave", "face")), Choice("Bury it", Action("wave", "bury"))], []
        choices = [Choice("Endure it", Action("wave", "endure"))]
        choices += [Choice(f"Swallow {p.name} against it", Action("wave", ("spend", p.id)))
                    for p in TW.pills_for(world, me, strength)[:5]]
        if TW.shelter_of(world, me, here) is not None:
            choices.append(Choice("Shelter under the tribulation array", Action("wave", "shelter")))
        return choices, []

    def _wave_lines(self) -> list:
        """The wave to come, told."""
        t = TR.pending(self.world, self.player.id)
        now = TW.current(self.world, self.player.id)
        if now is None:
            return []
        kind, _ = now
        nth = NTH[t["wave"]] if t["wave"] < len(NTH) else "next"
        what = {"lightning": "heaven's lightning gathers", "fire": "heavenly fire pours down"}.get(kind)
        if kind == "demon":
            demon = D.heaviest(self.world, self.player.id)
            what = f"{demon_words(self.world, demon)} rises in the storm" if demon else "your heart is tried"
        return [(f"The {nth} wave of {len(t['waves'])}: {what}.", "system")]

    def _do_wave(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        choice, item = target if isinstance(target, tuple) and len(target) == 2 else (target, None)
        if (why := TW.wave_block(world, me, here, choice, item)) is not None:
            return self._turn([(why, "system")] + self._wave_lines())
        return self._turn(self._commit(TW.wave_events(world, me, here, choice, item)) + self._wave_lines())

    def _do_heart_trial(self, choice):
        if TR.pending(self.world, self.player.id) is not None:  # a demon wave is faced as the heart's trial is
            return self._do_wave(choice)
        return super()._do_heart_trial(choice)

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        if any(e.kind == "tribulation_gathers" for e in events):
            lines += self._wave_lines()
        return lines
```

`narrate/tribulation_text.py`:
```python
"""What the player is told of a tribulation: the gathering, each wave, and what heaven leaves (phase 5f spec 5)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

KIND_WORDS = {"lightning": "the lightning", "fire": "the heavenly fire", "demon": "the demon"}


@outcome("tribulation_gathers", body_facts=False)
def _gathers(world, event):
    d = event.data
    if d["why"] == "notice":
        return ["The sky darkens over you alone. Heaven has taken notice of what you have done."], {}
    if d["minor"]:
        return ["A small, hard cloud gathers overhead. Even this gate is watched."], {}
    return [f"Heaven answers with {len(d['waves'])} waves."], {}


@summary("tribulation_gathers")
def _gathers_line(world, entry, names, place, other):
    if entry.data["minor"]:
        return "A minor tribulation came down." if entry.data["why"] != "notice" else "Heaven took notice of you."
    return f"Heaven sent {len(entry.data['waves'])} waves."


@outcome("tribulation_wave", body_facts=False)
def _wave(world, event):
    d = event.data
    if d["kind"] == "demon":
        return [], {}
    if d["choice"] == "spend":
        return [f"The pill burns in you, and {KIND_WORDS[d['kind']]} breaks around you like water on stone."], {}
    if d["choice"] == "shelter":
        return [f"The array's flags blaze and take {KIND_WORDS[d['kind']]} into the earth."], {}
    if d["success"]:
        return [f"You stand in {KIND_WORDS[d['kind']]} and it passes through you."], {}
    return [f"{cap(KIND_WORDS[d['kind']])} tears through you."], {}


@summary("tribulation_wave")
def _wave_line(world, entry, names, place, other):
    d = entry.data
    return f"{'Weathered' if d['success'] else 'Was struck by'} {KIND_WORDS[d['kind']]} of a tribulation."


@outcome("tribulation_passed", body_facts=False)
def _passed(world, event):
    d = event.data
    if d["died"]:
        return ["The last wave finds nothing left to hold it back."], {}
    return [{"clean": "The clouds break. You come through heaven's tribulation whole.",
             "scarred": "The clouds break. You come through, scarred.",
             "crippled": "The clouds break. You come through, but heaven has taken something with it."}[d["outcome"]]], {}


@summary("tribulation_passed")
def _passed_line(world, entry, names, place, other):
    d = entry.data
    return "Died in heaven's tribulation." if d["died"] else f"Came through a tribulation {d['outcome']}."


def _fell(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} fell to the heavenly tribulation in {v.get('place') or 'a town'}.")


SPECIAL_PHRASES["fell_to_tribulation"] = _fell
```

`narrate/grammar/tribulation5f.toml`:
```toml
# Tribulations played wave by wave (phase 5f).

[symbols]
storm_air = ["Thunder walks across the sky.", "The clouds turn slowly, like a millstone.", "The air smells of iron.", "Every hair on your arms stands up.", "The ground under you trembles.", "Light flickers inside the clouds."]

[tribulation_gathers]
colour = "dim"
lines = ["#storm_air#"]

[tribulation_wave]
colour = "dim"
lines = ["#storm_air#"]

[tribulation_passed]
colour = "dim"
lines = ["#storm_air#"]
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_tribulation_waves.py`
Expected: `7 failed, 1 passed`: the engine holds no waves until Step 4 puts the mixin into `Game` and the gathering into the sky.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5f_task4.py`:
```python
"""Phase 5f, Task 4: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/data/formations.toml', r'''[seclusion]
name = "the Seclusion ward"
use = "ward"
flags = 3
difficulty = 1
days = 90
''', r'''[seclusion]
name = "the Seclusion ward"
use = "ward"
flags = 3
difficulty = 1
days = 90

[tribulation]       # phase 5f: shelters its layer from heaven's waves, three at strength 1
name = "the Tribulation-Splitting array"
use = "ward"
flags = 8
difficulty = 3
days = 7
''')
edit('systems/world_clock.py', r'''import systems.tribulations  # noqa: E402,F401  phase 5f: tribulations weighed by karma, minor ones, NPC fates
''', r'''import systems.tribulations  # noqa: E402,F401  phase 5f: tribulations weighed by karma, minor ones, NPC fates
import systems.tribulation_waves  # noqa: E402,F401  phase 5f: a tribulation played wave by wave
''')
edit('engine/sky.py', r'''            if event.kind == "breakthrough" and event.actors[0] == self.player.id and event.data.get("success") \
                    and event.data["realm_after"] >= tribulation.TRIBULATION_REALM:
                outcome = tribulation.player_roll(self.world, self.player.id)
                lines += self._commit_sky(tribulation.trigger_events(
                    self.world, self.player.id, self.place.id, event.data["realm_after"], outcome=outcome))''', r'''            if event.kind == "breakthrough" and event.actors[0] == self.player.id and event.data.get("success") \
                    and event.data["realm_after"] >= tribulations.MINOR_REALM:
                realm = event.data["realm_after"]  # phase 5f: heaven's waves, played; 4d's lightning seen and told
                great = realm >= tribulation.TRIBULATION_REALM
                if great:
                    lines += self._commit_sky(tribulation.trigger_events(self.world, self.player.id, self.place.id,
                                                                         realm))
                lines += self._commit(tribulations.gather_events(self.world, self.player.id, self.place.id, realm,
                                                                 not great, "breakthrough"))''')
edit('engine/sky.py', r'''class SkyMixin:''', r'''import systems.tribulations as tribulations  # noqa: E402  phase 5f


class SkyMixin:''')
edit('engine/game.py', r'''from engine.heart import HeartMixin
''', r'''from engine.heart import HeartMixin
from engine.tribulation import TribulationMixin
''')
edit('engine/game.py', r'''class Game(HeartMixin,''', r'''class Game(TribulationMixin, HeartMixin,''')
edit('engine/commands.py', r'''    "bury": Action("heart_trial", "bury"), "turn back": Action("heart_trial", "turn_back"),''', r'''    "bury": Action("heart_trial", "bury"), "turn back": Action("heart_trial", "turn_back"),
    "endure": Action("wave", "endure"), "shelter": Action("wave", "shelter"),''')
edit('engine/game.py', r'''    ("  heart | swear <oath> | respects | face | bury | turn back: the dao heart", "system"),''', r'''    ("  heart | swear <oath> | respects | face | bury | turn back: the dao heart", "system"),
    ("  endure | shelter | face | bury: heaven's tribulation, wave by wave", "system"),''')
edit('narrate/outcomes.py', r'''import narrate.heart_text  # noqa: E402,F401
''', r'''import narrate.heart_text  # noqa: E402,F401
import narrate.tribulation_text  # noqa: E402,F401
''')
edit('tests/test_crafts_review.py', r'''    assert len([c for c in manuals.choices if c.action.verb == "buy_manual"]) == len(CW.teaches(world, master)) == 7''', r'''    assert len([c for c in manuals.choices if c.action.verb == "buy_manual"]) == len(CW.teaches(world, master)) == 8''')
edit('narrate/sky_text.py', r'''    return f"Faced the heavenly tribulation in {place}: {entry.data.get('outcome') or 'witnessed'}."''', r'''    if entry.data.get("outcome") is None:  # phase 5f: the waves that follow tell how it went
        return f"Heaven's lightning gathered over {place}."
    return f"Faced the heavenly tribulation in {place}: {entry.data['outcome']}."''')
print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5f_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_tribulation_waves.py`
Expected: `8 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1550 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: tribulations played wave by wave - endure, a pill, the array, the demon, and the end"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 5: The world's karma

A lives agenda of one hash strikes the wicked (ruling 15), and it is news. A heavy sinner's luck turns: a cut purse or a fall (ruling 16). A town with a monk has a temple that takes alms for merit, to a cap a season (ruling 17).

**Files:**
- Create: `systems/karma_world.py`
- Create: `tests/test_karma_world.py`
- Modify (by `.patches/5f_task5.py`): `systems/world_clock.py`

**Interfaces:**
- Consumes: Task 1's `karma`; 4a's lives agendas; 2a's injuries.
- Produces:
  - `KW` (systems/karma_world.py): `STRUCK_CHANCE`, `STRUCK_BALANCE`, `MISFORTUNE_CHANCE`, `MISFORTUNE_BALANCE`, `PURSE_SHARE`, `ALMS_MIN`, `ALMS_PER_MERIT`, `ALMS_CAP`; `season_events(world, person, n, rng)`, `season_hook(world, n)`, `has_temple(world, town)`, `alms_block(world, person, town, silver)`, `alms_events(world, person, town, silver)`, `incense_events(world, person, town)`; events `alms_given`, `incense_burned`, `misfortune`.
  - the fortune teller's fee (`fortune_read`), used by Task 7.

- [ ] **Step 1: Write the tests**

`tests/test_karma_world.py`:
```python
import pytest

import systems.encounters as encounters
import systems.karma as K
import systems.karma_world as KW
from engine.game import Game
from systems import founding
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit


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


def person(game, tag, **data):
    return founding.make_person(game.world, f"test:kw:{tag}", game.place.id, **{"occupation": "bandit", "age": 40,
                                                                               **data})


def test_heaven_strikes_down_the_wicked_and_it_is_news(game, monkeypatch):
    world = game.world
    monkeypatch.setattr(KW, "STRUCK_CHANCE", 1.0)
    wicked, decent = person(game, "wicked"), person(game, "decent", occupation="monk")
    K.write(world, wicked, sin=120.0, merit=0.0)
    K.write(world, decent, sin=0.0, merit=40.0)
    assert KW.season_events(world, decent, 0, None) == []
    events = KW.season_events(world, wicked, 0, None)
    assert [e.data["cause"] for e in events] == ["heaven"]
    commit(world, events)
    assert world.entity(wicked).data.get("dead") and world.facts(predicate="struck_down", subject=wicked)


def test_a_heavy_sinners_luck_turns(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(KW, "MISFORTUNE_CHANCE", 1.0)
    assert KW.season_hook(world, 0) == []
    K.write(world, me, sin=300.0)
    whats = set()
    for n in range(20):
        events = KW.season_hook(world, n)
        commit(world, events)
        whats |= {e.data["what"] for e in events}
    assert whats == {"purse", "injury"} and silver_of(world, me) < 1000
    assert any(i.cause == "a fall no one saw coming" for i in load_body(world, me).injuries)


def test_a_temple_takes_alms_for_merit_up_to_a_season_cap(game):
    world, me, here = game.world, game.player.id, game.place.id
    if not KW.has_temple(world, here):
        person(game, "abbot", occupation="monk")
    assert KW.alms_block(world, me, here, 5) == "Alms are 10 silver or more, from what you carry."
    commit(world, KW.alms_events(world, me, here, 200))
    assert K.karma_of(world, me)["merit"] == 20 and silver_of(world, me) == 800
    commit(world, KW.alms_events(world, me, here, 200))
    assert K.karma_of(world, me)["merit"] == KW.ALMS_CAP and silver_of(world, me) == 600


def test_no_monk_no_temple(game):
    world = game.world
    town = world.add_entity("town", "Empty Town", {"x": 99, "y": 99, "index": 0, "kind": "village"})
    assert not KW.has_temple(world, town)
    assert KW.alms_block(world, game.player.id, town, 50) == "There is no temple here."
```

- [ ] **Step 2: Write the new modules**

`systems/karma_world.py`:
```python
"""The world's karma (phase 5f spec 6): heaven strikes the wicked now and then, a heavy sinner's luck turns, and
temples take alms.

Retribution is a lives agenda of one hash (the karma is read only when it falls). The player's misfortune is a
season hook. A town with a monk has a temple.
"""

import systems.heart_world  # noqa: F401  5e's agenda runs before this one, whatever is imported first
import systems.karma as K
import systems.lives as lives
import systems.world_clock as world_clock
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.body import add_injury
from world.events import Event, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for, seed_for

STRUCK_CHANCE, STRUCK_BALANCE = 0.01, -50.0
MISFORTUNE_CHANCE, MISFORTUNE_BALANCE, PURSE_SHARE = 0.1, -150.0, 0.2
ALMS_MIN, ALMS_PER_MERIT, ALMS_CAP = 10, 10, 30   # merit = silver / 10, at most 30 a season


def season_events(world, person: int, n: int, rng) -> list[Event]:
    """The wicked struck down by heaven, one season in a hundred."""
    entity = world.entity(person)
    if seed_for(world.world_seed, f"struck:{lives.key(entity)}:{n}") / 2 ** 64 >= STRUCK_CHANCE:
        return []
    if K.balance(world, person) >= STRUCK_BALANCE:
        return []
    return [Event("died", (person, person), lives.home(world, person), {"cause": "heaven", "world": True})]


lives.AGENDAS.append(season_events)


@listen("died")
def _struck_news(world, event, event_id: int) -> None:
    if event.data.get("cause") != "heaven":
        return
    person = event.actors[-1]
    variant = make_variant("struck_down", person, None, place=place_name(world, event.place))
    record_fact(world, person, "struck_down", None, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


# --- the player's luck ------------------------------------------------------------------------------------------------

def season_hook(world, n: int) -> list[Event]:
    player = world.get_meta("player_id")
    entity = world.entity(player) if player is not None else None
    if entity is None or entity.data.get("dead") or K.balance(world, player) >= MISFORTUNE_BALANCE:
        return []
    rng = rng_for(world.world_seed, f"misfortune:{player}:{n}")
    if rng.random() >= MISFORTUNE_CHANCE:
        return []
    here = next(iter(world.targets(player, "located_in")), None)
    silver = silver_of(world, player)
    if silver and rng.random() < 0.5:
        return [Event("misfortune", (player,), here, {"what": "purse", "silver": int(silver * PURSE_SHARE)})]
    return [Event("misfortune", (player,), here, {"what": "injury", "silver": 0})]


world_clock.SEASON_HOOKS.append(season_hook)


@effect("misfortune")
def _misfortune(world, event) -> None:
    person, d = event.actors[0], event.data
    if d["what"] == "purse":
        world.update_data(person, silver=max(0, silver_of(world, person) - d["silver"]))
    else:
        body = load_body(world, person)
        add_injury(body, "left leg", "fracture", 2, world.time, "a fall no one saw coming")
        save_body(world, person, body)


# --- temples -----------------------------------------------------------------------------------------------------

def has_temple(world, town) -> bool:
    return world.entity(town).kind == "town" and any(p.data.get("occupation") == "monk" for p in people_at(world, town))


def alms_block(world, person: int, town, silver: int) -> str | None:
    if not has_temple(world, town):
        return "There is no temple here."
    if silver < ALMS_MIN or silver_of(world, person) < silver:
        return f"Alms are {ALMS_MIN} silver or more, from what you carry."
    return None


def alms_events(world, person: int, town, silver: int) -> list[Event]:
    season = lives.current_season(world)
    given = (world.entity(person).data.get("alms_merit") or {}).get(str(season), 0)
    merit = max(0, min(ALMS_CAP - given, silver // ALMS_PER_MERIT))
    return [Event("alms_given", (person,), town, {"silver": silver, "merit": merit, "season": season})]


@effect("alms_given")
def _alms(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["silver"],
                      alms_merit={str(d["season"]): (world.entity(person).data.get("alms_merit") or {})
                                  .get(str(d["season"]), 0) + d["merit"]})
    K.add(world, person, merit=d["merit"])


def incense_events(world, person: int, town) -> list[Event]:
    return [Event("incense_burned", (person,), town, {})]


@effect("fortune_read")
def _fortune_paid(world, event) -> None:
    person, teller = event.actors
    world.update_data(person, silver=silver_of(world, person) - event.data["silver"])
    world.update_data(teller, silver=silver_of(world, teller) + event.data["silver"])
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_karma_world.py`
Expected: `4 passed`: the tests pass already: the edit only wires the module into the clock for games that do not import it.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5f_task5.py`:
```python
"""Phase 5f, Task 5: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.tribulation_waves  # noqa: E402,F401  phase 5f: a tribulation played wave by wave
''', r'''import systems.tribulation_waves  # noqa: E402,F401  phase 5f: a tribulation played wave by wave
import systems.karma_world  # noqa: E402,F401  phase 5f: heaven's retribution, a sinner's luck, temples
''')
print("task 5 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5f_task5.py`
Expected: `task 5 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_karma_world.py`
Expected: `4 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1554 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the world's karma - heaven strikes the wicked, a sinner's luck turns, and temples"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 6: The close of phase 5

5c's absent masters: an NPC master whose home is not the bound's does not feed them (ruling 20). 5d's commission lost with a smith: their estate returns it (ruling 21). The 5d spec marks both done.

**Files:**
- Create: `tests/test_phase5_close.py`
- Modify (by `.patches/5f_task6.py`): `systems/control.py`, `systems/craft_world.py`, `docs/superpowers/specs/2026-09-28-phase5d-forging-formations-design.md`

**Interfaces:**
- Consumes: 5c's `control` season hook; 5d's `craft_world` commissions; 5a's `smithy.price`.
- Produces:
  - `control.fed(world, master, person=None)`; `commission_refunded`.

- [ ] **Step 1: Write the tests**

`tests/test_phase5_close.py`:
```python
"""The close of phase 5 (phase 5f spec 8): 5c's absent masters and 5d's commission lost with a smith."""

import pytest

import systems.control as C
import systems.craft_world as CW
import systems.encounters as encounters
import systems.travel as travel
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=5000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def test_a_master_in_another_town_does_not_feed_their_bound(game, monkeypatch):
    world, here = game.world, game.place.id
    monkeypatch.setattr(C, "CURE_SEEK", 0.0)
    elsewhere = ensure_town(world, *travel.routes_from(world, game.place)[0].dest)
    master = founding.make_person(world, "test:close:master", here, occupation="monk", age=50, realm="first-rate")
    near, far = (founding.make_person(world, f"test:close:{t}", here, occupation="tea seller", age=30)
                 for t in ("near", "far"))
    for bound in (near, far):
        C.bind(world, bound, master)
    world.unrelate(far, "located_in")
    world.relate(far, elsewhere, "located_in")
    assert C.fed(world, master, near) and not C.fed(world, master, far)
    before = C.bound(world, far)["fed_until"]
    world.set_time(world.time + 4 * C.MONTH)
    commit(world, C.season_hook(world, 1))
    assert C.bound(world, near)["fed_until"] > world.time and C.bound(world, far)["fed_until"] == before
    assert C.days_starved(world, far) > 0


def test_a_smiths_estate_returns_a_commission_unforged(game):
    world, me, here = game.world, game.player.id, game.place.id
    smith = founding.make_person(world, "test:close:smith", here, occupation="blacksmith", age=50)
    world.update_data(smith, craft_skill=3)
    commit(world, CW.commission_forge_events(world, me, smith, "weapon", "sword", here))
    paid = 5000 - silver_of(world, me)
    assert paid > 0 and CW.pending(world, me)[0]["price"] == paid
    commit(world, [Event("died", (smith, smith), here, {"cause": "illness", "world": True})])
    assert silver_of(world, me) == 5000 and CW.pending(world, me) == []
    assert any(e.kind == "commission_refunded" for e in world.chronicle_about(me, limit=5))


def test_an_older_commission_without_a_price_is_returned_at_the_stall_price(game):
    world, me, here = game.world, game.player.id, game.place.id
    smith = founding.make_person(world, "test:close:old", here, occupation="blacksmith", age=50)
    world.update_data(me, commissions=[{"smith": smith, "slot": "weapon", "form": "saber", "grade": 1,
                                        "ready_at": world.time + 40}])
    commit(world, [Event("died", (smith, smith), here, {"cause": "illness", "world": True})])
    assert silver_of(world, me) > 5000 and CW.pending(world, me) == []
```

- [ ] **Step 2: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_phase5_close.py`
Expected: `3 failed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5f_task6.py`:
```python
"""Phase 5f, Task 6: its edits to files that exist before it (the close of phase 5)."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/control.py', r'''def fed(world, master: int) -> bool:
    """An NPC master feeds their bound always, while alive (spec 6)."""
    entity = world.entity(master)
    return entity is not None and not entity.data.get("dead") and not entity.data.get("is_player")''', r'''def fed(world, master: int, person: int | None = None) -> bool:
    """An NPC master feeds their bound while alive and at hand: one living in another town does not (spec 6;
    phase 5f closes 5c's ruling 19, since NPCs do move)."""
    entity = world.entity(master)
    if entity is None or entity.data.get("dead") or entity.data.get("is_player"):
        return False
    return person is None or lives.home(world, master) == lives.home(world, person)''')
edit('systems/control.py', r'''        if fed(world, b["master"]):''', r'''        if fed(world, b["master"], person):''')
edit('systems/craft_world.py', r'''    world.update_data(person, commissions=pending(world, person) + [
        {"smith": smith, "slot": d["slot"], "form": d["form"], "grade": d["grade"], "ready_at": d["ready_at"]}])''', r'''    world.update_data(person, commissions=pending(world, person) + [
        {"smith": smith, "slot": d["slot"], "form": d["form"], "grade": d["grade"], "ready_at": d["ready_at"],
         "price": d["price"]}])


@listen("died")
def _smith_dies(world, event, event_id: int) -> None:
    """A smith who dies with a commission unforged: their estate returns the silver (phase 5f closes 5d's)."""
    smith, player = event.actors[-1], world.get_meta("player_id")
    if player is None or world.entity(player) is None:
        return
    from systems.smithy import price  # the smith's stall comes after the crafts in the import graph
    from world.events import commit
    for c in [c for c in pending(world, player) if c["smith"] == smith]:
        paid = c.get("price") or FORGE_SHARE * price(world, event.place, c["slot"], c["grade"])  # older saves
        commit(world, [Event("commission_refunded", (player, smith), event.place,
                             {"slot": c["slot"], "form": c["form"], "grade": c["grade"], "silver": paid})])


@effect("commission_refunded")
def _refunded(world, event) -> None:
    person, smith = event.actors
    world.update_data(person, silver=silver_of(world, person) + event.data["silver"],
                      commissions=[c for c in pending(world, person) if c["smith"] != smith])''')
edit('systems/craft_world.py', r'''from world.events import Event, effect
''', r'''from world.events import Event, effect, listen
''')
edit('docs/superpowers/specs/2026-09-28-phase5d-forging-formations-design.md', r'''- **A smith who dies with a commission unforged:** the silver paid is lost with them (found in review). Taken up with the absent masters at the end of phase 5.''', r'''- **A smith who dies with a commission unforged:** the silver paid is lost with them (found in review). Taken up with the absent masters at the end of phase 5: done in 5f (the estate returns it).''')
edit('docs/superpowers/specs/2026-09-28-phase5d-forging-formations-design.md', r'''- **5c's absent masters:** an NPC master away from their bound for a season lets them starve. Deferred to the end of phase 5, by decision (2026-09-28).''', r'''- **5c's absent masters:** an NPC master away from their bound for a season lets them starve. Deferred to the end of phase 5, by decision (2026-09-28): done in 5f.''')
print("task 6 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5f_task6.py`
Expected: `task 6 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_phase5_close.py`
Expected: `3 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1557 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the close of phase 5 - absent masters let their bound starve, and a smith's estate pays back"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 7: The player's karma

`KarmaMixin` gives the temple (alms and incense), a fortune teller's reading (ruling 18), and heaven's doings told as they come (ruling 19). Every new deed has its outcome, journal line and grammar; heaven's strikes are rumours; typed words and help reach it all.

**Files:**
- Create: `engine/karma.py`
- Create: `narrate/karma_text.py`
- Create: `narrate/grammar/karma.toml`
- Create: `tests/test_karma_play.py`
- Modify (by `.patches/5f_task7.py`): `engine/game.py`, `engine/commands.py`, `narrate/outcomes.py`, `tests/test_game.py`

**Interfaces:**
- Consumes: Everything above; 5e's reactions as the model.
- Produces:
  - `engine/karma.py` (engine/karma.py): `ALMS`, `FORTUNE_PRICE`, `FORTUNE_TELLER`, `REACTIONS`; events `fortune_read`.
  - `narrate/karma_text.py`: outcomes, journal lines, and the rumour `struck_down`.

- [ ] **Step 1: Write the tests**

`tests/test_karma_play.py`:
```python
import pytest

import systems.encounters as encounters
import systems.karma as K
import systems.karma_world as KW
import systems.threads as TH
import systems.tribulations as TR
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from narrate.gossip_text import rumour_text
from narrate.outcomes import SUMMARIES
from systems.creation import CreationChoice
from systems.facts import make_variant
from systems.purse import silver_of
from world.events import commit


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
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:kplay:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def text(turn):
    return " | ".join(t for t, _ in turn.lines)


def test_the_temple_takes_alms_and_incense(game):
    world, me = game.world, game.player.id
    someone(game, "abbot", occupation="monk")
    turn = game.perform(Action("look"))
    assert "Visit the temple" in [c.label for c in turn.all_choices]
    turn = game.perform(Action("temple"))
    assert [c.label for c in turn.choices][:4] == ["Give 10 silver in alms", "Give 50 silver in alms",
                                                   "Give 200 silver in alms", "Burn incense"]
    turn = game.perform(parse("alms", [], []))
    assert "You give 50 silver in alms." in text(turn) and K.karma_of(world, me)["merit"] == 5
    assert "watch the smoke climb" in text(game.perform(Action("incense")))


def test_a_fortune_teller_reads_karma_in_words_and_names_the_threads(game):
    world, me = game.world, game.player.id
    teller, friend = someone(game, "teller", occupation="fortune teller"), someone(game, "friend")
    K.write(world, me, merit=60.0, sin=10.0)
    TH.add_thread(world, me, friend, "spared")
    game.perform(Action("talk", teller))
    turn = game.perform(Action("fortune", teller))
    assert "Your merit outweighs your sins." in text(turn)
    assert "A thread runs to Someone friend: you spared them." in text(turn)
    assert silver_of(world, me) == 950 and "60" not in text(turn)


def test_heaven_taking_notice_is_told_as_it_comes(game):
    world, me = game.world, game.player.id
    K.write(world, me, sin=300.0)
    world.set_time(world.time + 400)
    turn = game.perform(Action("rest"))
    assert "Heaven has taken notice of what you have done." in text(turn)
    assert "The first wave of" in text(turn) and TR.pending(world, me)["minor"]


def test_a_misfortune_is_told_as_it_comes(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(KW, "MISFORTUNE_CHANCE", 1.0)
    monkeypatch.setattr(TR, "NOTICE_SIN", 10 ** 6)
    K.write(world, me, sin=300.0)
    world.set_time(world.time + 400)  # into the next season
    turn = game.perform(Action("rest"))
    assert "and you never felt the hand" in text(turn) or "Your leg takes the fall" in text(turn)


def test_typed_words_and_help_reach_karma(game):
    turn = game.perform(Action("look"))
    for word, verb in (("temple", "temple"), ("alms", "alms"), ("incense", "incense"), ("fortune", "fortune"),
                       ("endure", "wave"), ("shelter", "wave")):
        assert parse(word, turn.choices, turn.extra).verb == verb
    assert any("temple | alms" in t for t, _ in game.perform(Action("help")).lines)


def test_every_karmic_deed_has_a_journal_line():
    for kind in ("fated_repaid", "fortune_read", "alms_given", "incense_burned", "misfortune", "commission_refunded",
                 "tribulation_gathers", "tribulation_wave", "tribulation_passed"):
        assert kind in SUMMARIES, kind


def test_the_struck_down_and_the_fallen_are_told_as_rumours(game):
    world, me = game.world, game.player.id
    fiend = someone(game, "fiend")
    v = make_variant("struck_down", fiend, None, place="Crimson Town")
    assert rumour_text(world, v, me) == "Someone fiend was struck down by heaven in Crimson Town."
    v = make_variant("fell_to_tribulation", fiend, None, place="Crimson Town")
    assert rumour_text(world, v, me) == "Someone fiend fell to the heavenly tribulation in Crimson Town."
```

- [ ] **Step 2: Write the new modules**

`engine/karma.py`:
```python
"""Karma in the engine (phase 5f spec 7): the temple, a fortune teller's reading, and heaven's doings told as they
come (a sinner's misfortune, heaven taking notice, a smith's estate paying back)."""

import systems.karma as K
import systems.karma_world as KW
from engine.actions import Action, Choice
from narrate.brief import event_brief
from systems.purse import silver_of
from world.events import Event

ALMS = (10, 50, 200)
FORTUNE_PRICE = 50
FORTUNE_TELLER = "fortune teller"
REACTIONS = frozenset({"misfortune", "commission_refunded", "tribulation_gathers"})  # the clock's and listeners'


class KarmaMixin:
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        if KW.has_temple(self.world, self.place.id):
            extras.append(Choice("Visit the temple", Action("temple")))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if npc.data.get("occupation") == FORTUNE_TELLER:
            extras.append(Choice(f"Have your fortune read ({FORTUNE_PRICE} silver)", Action("fortune", npc.id)))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is None and self.submenu == "temple":
            options["temple"] = ([Choice(f"Give {n} silver in alms", Action("alms", n)) for n in ALMS]
                                 + [Choice("Burn incense", Action("incense"))], Action("back"))
        return options

    def _do_temple(self, _target):
        if not KW.has_temple(self.world, self.place.id):
            return self._turn([("There is no temple here.", "system")])
        self.submenu = "temple"
        return self._turn([("Incense smoke drifts under the eaves. A monk sweeps the steps.", "dim")])

    def _do_alms(self, silver):
        world, me, here = self.world, self.player.id, self.place.id
        silver = silver if isinstance(silver, int) else ALMS[1]
        self.submenu = "temple"
        if (why := KW.alms_block(world, me, here, silver)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(KW.alms_events(world, me, here, silver)))

    def _do_incense(self, _target):
        self.submenu = "temple"
        if not KW.has_temple(self.world, self.place.id):
            return self._turn([("There is no temple here.", "system")])
        return self._turn(self._commit(KW.incense_events(self.world, self.player.id, self.place.id)))

    def _do_fortune(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        npc = npc if npc is not None else self.focus
        teller = world.entity(npc) if isinstance(npc, int) else None
        if teller is None or teller.data.get("occupation") != FORTUNE_TELLER or self.focus != npc:
            return self._turn([("There is no fortune teller before you.", "system")])
        if silver_of(world, me) < FORTUNE_PRICE:
            return self._turn([(f"A reading costs {FORTUNE_PRICE} silver.", "system")])
        return self._turn(self._commit([Event("fortune_read", (me, npc), here, {"silver": FORTUNE_PRICE,
                                                                                "balance": K.balance(world, me)})]))

    def _after_commit(self, ids: list, events: list) -> list:
        """Heaven's doings in the clock and in listeners, told as they come."""
        lines = super()._after_commit(ids, events)
        if not ids:
            return lines
        me, done = self.player.id, set(ids)
        for entry in reversed(self.world.chronicle_about(me, limit=12)):
            if entry.id > min(ids) and entry.id not in done and entry.kind in REACTIONS and entry.actors[0] == me \
                    and entry.data.get("why") != "breakthrough":  # a breakthrough's is the engine's own, told already
                lines += self.narrator.narrate(event_brief(self.world, entry.id, entry))
                if entry.kind == "tribulation_gathers":
                    lines += self._wave_lines()
        return lines
```

`narrate/karma_text.py`:
```python
"""What the player is told of karma: fated meetings, a fortune read, the temple, misfortune, and a smith's estate
paying back (phase 5f spec 7)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

import systems.gear as gear
import systems.karma as K
import systems.threads as TH

THREAD_WORDS = {"spared": "you spared them", "healed": "you healed them", "freed": "you freed them from the worms",
                "robbed": "you robbed them", "crippled": "you crippled them", "bereaved": "you killed their kin",
                "accused": "you falsely accused them"}
OWED_WORDS = {"spared": "You spared me", "healed": "You healed me", "freed": "You freed me from the worms"}


def _name(world, entity_id) -> str:
    entity = world.entity(entity_id) if isinstance(entity_id, int) else None
    return entity.name if entity else "someone"


@outcome("fated_repaid", body_facts=False)
def _repaid(world, event):
    d = event.data
    return [f"{cap(_name(world, event.actors[1]))} is on the road, and knows you. \"{OWED_WORDS[d['kind']]}. "
            f"I have not forgotten.\" They press {d['silver']} silver on you."], {}


@summary("fated_repaid")
def _repaid_line(world, entry, names, place, other):
    return f"Was repaid by {other} on the road."


@outcome("fortune_read", body_facts=False)
def _fortune(world, event):
    me = event.actors[0]
    teller = _name(world, event.actors[1])
    lines = [f"{cap(teller)} spreads the sticks and reads them twice. \"{cap(K.words(event.data['balance']))}.\""]
    threads = sorted(TH.threads(world, me), key=lambda t: (-t["weight"], t["since"]))[:3]
    for t in threads:
        lines.append(f"\"A thread runs to {_name(world, t['whom'])}: {THREAD_WORDS[t['kind']]}.\"")
    if not threads:
        lines.append("\"No thread of fate pulls hard at you yet.\"")
    return lines, {}


@summary("fortune_read")
def _fortune_line(world, entry, names, place, other):
    return f"Had {other} read your fortune."


@outcome("alms_given", body_facts=False)
def _alms(world, event):
    return [f"You give {event.data['silver']} silver in alms. The monk bows without a word."], {}


@summary("alms_given")
def _alms_line(world, entry, names, place, other):
    return f"Gave {entry.data['silver']} silver in alms at {place}."


@outcome("incense_burned", body_facts=False)
def _incense(world, event):
    return ["You light a stick of incense and watch the smoke climb."], {}


@summary("incense_burned")
def _incense_line(world, entry, names, place, other):
    return f"Burned incense at {place}."


@outcome("misfortune", body_facts=False)
def _misfortune(world, event):
    d = event.data
    if d["what"] == "purse":
        return [f"Your purse is lighter by {d['silver']} silver, and you never felt the hand."], {}
    return ["A stair gives way under you. Your leg takes the fall."], {}


@summary("misfortune")
def _misfortune_line(world, entry, names, place, other):
    return "Lost silver to a cutpurse." if entry.data["what"] == "purse" else "Hurt in a fall."


@outcome("commission_refunded", body_facts=False)
def _refunded(world, event):
    d = event.data
    what = gear.ARMOUR_WORDS.get(d["form"], d["form"])
    return [f"{cap(_name(world, event.actors[1]))} died before the {what} was forged; their estate returns your "
            f"{d['silver']} silver."], {}


@summary("commission_refunded")
def _refunded_line(world, entry, names, place, other):
    return f"Had {entry.data['silver']} silver back from {other}'s estate."


def _struck(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} was struck down by heaven in {v.get('place') or 'a town'}.")


SPECIAL_PHRASES["struck_down"] = _struck
```

`narrate/grammar/karma.toml`:
```toml
# Karma (phase 5f): fated meetings, the temple, a fortune read.

[symbols]
temple_air = ["A bell sounds once.", "Incense smoke curls under the eaves.", "Old prayers flutter on strings.", "The courtyard is swept clean.", "A monk murmurs a sutra.", "Pigeons settle on the roof ridge."]
fate_air = ["Some meetings are not chance.", "The road narrows.", "You know the face before the name.", "The wind drops.", "A crow watches from a post.", "The dust settles slowly."]

[alms_given]
colour = "dim"
lines = ["#temple_air#"]

[incense_burned]
colour = "dim"
lines = ["#temple_air#"]

[fortune_read]
colour = "dim"
lines = ["#fate_air#"]

[fated_repaid]
colour = "dim"
lines = ["#fate_air#"]

["encounter.wronged"]
colour = "default"
lines = ["#fate_air#"]
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_karma_play.py`
Expected: `7 failed`: the engine has no handlers for the new verbs until Step 4 puts the mixin into `Game`.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5f_task7.py`:
```python
"""Phase 5f, Task 7: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('engine/game.py', r'''from engine.tribulation import TribulationMixin
''', r'''from engine.tribulation import TribulationMixin
from engine.karma import KarmaMixin
''')
edit('engine/game.py', r'''class Game(TribulationMixin,''', r'''class Game(KarmaMixin, TribulationMixin,''')
edit('engine/game.py', r'''    ("  endure | shelter | face | bury: heaven's tribulation, wave by wave", "system"),''', r'''    ("  endure | shelter | face | bury: heaven's tribulation, wave by wave", "system"),
    ("  temple | alms | incense | fortune: karma, and heaven's patience", "system"),''')
edit('engine/commands.py', r'''    "endure": Action("wave", "endure"), "shelter": Action("wave", "shelter"),''', r'''    "endure": Action("wave", "endure"), "shelter": Action("wave", "shelter"),
    "temple": Action("temple"), "alms": Action("alms", 50), "incense": Action("incense"),
    "fortune": Action("fortune"),''')
edit('narrate/outcomes.py', r'''import narrate.tribulation_text  # noqa: E402,F401
''', r'''import narrate.tribulation_text  # noqa: E402,F401
import narrate.karma_text  # noqa: E402,F401
''')
edit('tests/test_game.py', r'''                                                                "heart_talk"}  # phase 5e: amends, a blade read''', r'''                                                                "heart_talk",  # phase 5e: amends, a blade read
                                                                "fortune"}  # phase 5f: a fortune teller''')
print("task 7 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5f_task7.py`
Expected: `task 7 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_karma_play.py`
Expected: `7 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1564 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the player's karma - the temple, a fortune read, and heaven's doings told"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 8: Karma and tribulations end to end

The fork guide's section 15, the speed of a season of NPC karma, of a journey weighing twelve threads and of the new scenes, and a heavy karma played at random.

**Files:**
- Create: `tests/test_karma_fuzz.py`
- Create: `tests/test_karma_season.py`
- Modify (by `.patches/5f_task8.py`): `docs/world-events.md`

**Interfaces:**
- Consumes: Everything above.
- Produces:
  - `docs/world-events.md` section 15; `tests/test_karma_fuzz.py`: `test_a_heavy_karma`.

- [ ] **Step 1: Write the tests**

`tests/test_karma_fuzz.py`:
```python
"""A heavy karma, played at random (phase 5f): a fighter who kills and spares, gives alms, breaks through into
heaven's waves and meets their threads on the road; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing

WORDS = ["endure", "shelter", "face", "bury", "breakthrough", "temple", "alms", "incense", "fortune", "look", "rest",
         "journal", "challenge", "kill", "spare", "rob", "meditate", "heart"]


@pytest.mark.parametrize("seed", [9, 31])
def test_a_heavy_karma(tmp_path, seed):
    import systems.karma as K
    import systems.threads as TH
    import systems.tribulations as TR
    from systems.bodies import load_body, save_body
    from world.events import commit
    from world.gen.materialize import people_at
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Karma{seed}", world_seed=seed)
    world = app.game.world
    me = world.get_meta("player_id")
    here = next(iter(world.targets(me, "located_in")))
    world.update_data(me, silver=3000)
    body = load_body(world, me)
    body.realm, body.bottleneck, body.energy_years = 2, True, 20.0
    body.flags.append("sensed_qi")
    save_body(world, me, body)
    K.write(world, me, sin=260.0, merit=20.0)
    for person in people_at(world, here, exclude=me)[:4]:
        TH.add_thread(world, me, person.id, rng.choice(["spared", "robbed", "crippled", "healed"]))
    commit(world, TR.gather_events(world, me, here, 3, False, "breakthrough"))
    app.submit("look")
    happened = set()
    for step in range(260):
        game = app.game
        if game is None:
            break
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.55 and app.choices:
            app.submit(str(rng.randrange(1, len(app.choices) + 1)))
        else:
            app.submit(rng.choice(WORDS))
        if rng.random() < 0.05:
            app.handle_key("f4", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    done = happened & {"tribulation_wave", "tribulation_passed", "alms_given", "fortune_read", "fated_repaid",
                       "misfortune", "incense_burned", "encounter"}
    assert len(done) >= 2, done
    app.shutdown()
```

`tests/test_karma_season.py`:
```python
import gc
import time
from pathlib import Path

import pytest

import systems.encounters as encounters
import systems.karma_world as KW
import systems.lives as lives
import systems.threads as TH
import systems.tribulations as TR
from engine.actions import Action
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


def average(fn, n=10) -> float:
    """CPU time per call, averaged: Windows' CPU clock ticks in 15.6 ms steps (4e ruling 19)."""
    fn()
    gc.collect()
    start = time.process_time()
    for _ in range(n):
        fn()
    return (time.process_time() - start) / n


def test_the_fork_guide_covers_karma():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("karma_deeds.toml", "`karma = {merit", "threads", "ROAD_HOOKS", "`tribulation = {",
                 "tribulation_waves", "tribulation\"", "struck_down", "alms", "check_karma"):
        assert word in guide, word


class _Undo(Exception):
    pass


def test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5es(game, monkeypatch):
    """The same 200 people live the same season again and again, rolled back, with and without the karma agenda."""
    from tests.test_alchemy_world_season import crowd
    world = game.world
    everything = list(lives.AGENDAS)
    before = [a for a in everything if a is not KW.season_events]
    people = crowd(world, game.place.id, "karma")
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

    timings = {"5e": [], "5f": []}
    for n in range(20):  # ten a side: one side's cost sits near the bar, and the machine is noisy (5e minors)
        which = "5e" if n % 2 == 0 else "5f"
        timings[which].append(season(before if which == "5e" else everything))
    total = {k: sum(sorted(v)[:5]) for k, v in timings.items()}  # the fastest five of ten: load only slows
    assert total["5f"] <= 1.10 * total["5e"] + 0.016, timings


def test_a_journey_with_twelve_threads_is_quick(game, monkeypatch):
    world, me = game.world, game.player.id
    from world.gen.materialize import ensure_town
    import systems.travel as travel
    town = world.entity(ensure_town(world, *travel.routes_from(world, game.place)[0].dest))
    plain = average(lambda: encounters.road_encounter_events(world, me, town), n=50)
    for n in range(12):
        pid = world.add_entity("person", f"Thread {n}", {"occupation": "tea seller", "realm": "mortal", "age": 30})
        world.relate(pid, game.place.id, "located_in")
        TH.add_thread(world, me, pid, "robbed")
    monkeypatch.setattr(TH, "FATE_CHANCE", 0.0)  # every thread weighed, none met
    assert average(lambda: encounters.road_encounter_events(world, me, town), n=50) <= 1.10 * plain + 0.0003


def test_the_tribulation_scene_and_the_temple_are_quick(game):
    world, me = game.world, game.player.id
    commit(world, TR.gather_events(world, me, game.place.id, 6, False, "breakthrough"))
    assert average(lambda: game.perform(Action("look"))) < 0.02
    commit(world, [Event("tribulation_passed", (me,), game.place.id,
                         {"realm": 6, "minor": False, "outcome": "scarred", "died": False})])
    assert average(lambda: game.perform(Action("temple"))) < 0.02
```

- [ ] **Step 2: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_karma_fuzz.py tests/test_karma_season.py`
Expected: `1 failed, 5 passed`: the fork guide has no section 15 yet; the speed tests and the fuzz already pass.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5f_task8.py`:
```python
"""Phase 5f, Task 8: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('docs/world-events.md', r'''**The rules:** `check_heart` in `debug/invariants.py` holds hearts, demons, daos and oaths to their bounds, and the
mad to the living; `check_spirits` holds a spirit to a nature and a bond within 0-1.
''', r'''**The rules:** `check_heart` in `debug/invariants.py` holds hearts, demons, daos and oaths to their bounds, and the
mad to the living; `check_spirits` holds a spirit to a nature and a bond within 0-1.

## 15. Karma and tribulations (phase 5f)

**Karma** is person data `karma = {merit, sin, threads}`: heaven's ledger, apart from 5e's heart. An NPC has none until
something writes it; `karma.karma_of` reads a seeded one from their trade and traits. Deeds count through the rows of
`systems/data/karma_deeds.toml` (an event kind, the actor it counts for, its merit or sin), a duel's verdict, and a
`died` listener for killing.

**Threads** (`{whom, kind, weight, since}`, at most twelve) tie the player to people saved or wronged
(`systems/threads.py`); a 2b road hook (`encounters.ROAD_HOOKS`) brings the heaviest within reach back: a repayment,
or a `wronged` encounter that takes amends.

**Tribulations:** `systems/tribulations.py` weighs one by karma (`plan`) and keeps it gathering over the player as
person data `tribulation = {realm, minor, strength, waves, wave, failed}`; `systems/tribulation_waves.py` plays it
wave by wave (endure, a pill, a `tribulation` array of 5d's table, the heart's demon). A great tribulation is still
4d's `"tribulation"` event at its start, with its lightning and its news; a minor one is the player's own.
4d's lightning over an NPC now rolls their fate by their karma.

**The world** (`systems/karma_world.py`): a lives agenda strikes the wicked (`struck_down`); a season hook turns a
heavy sinner's luck; a town with a monk has a temple that takes alms.

**The rules:** `check_karma` in `debug/invariants.py` holds merit and sin to at least 0 and a gathering tribulation to
its wave kinds and a strength of at least 1.
''')
print("task 8 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5f_task8.py`
Expected: `task 8 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_karma_fuzz.py tests/test_karma_season.py`
Expected: `6 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1570 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Run the 500-year soak**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: karma and tribulations end to end - the fork guide, speed, and a heavy karma's fuzz"
```

The message ends with the session's Co-Authored-By attribution line.

---

## Self-review

- **Spec coverage:**
  - §2 the ledger (Task 1; rulings 1-3); §3 threads and fated meetings (Task 2; rulings 4-8);
  - §4 tribulations weighed by karma, minor ones, NPC fates (Task 3; ruling 11); §5 waves and the array (Task 4; rulings 9, 10, 12-14);
  - §6 the world (Task 5; rulings 15-17); §7 the player (Tasks 4, 7; rulings 18, 19); §8 the close of phase 5 (Task 6; rulings 20-22);
  - §9 knowledge (Tasks 1, 2, 7); §10 `check_karma` (Tasks 1, 3); §11 level of detail and speed (Task 8); §12 testing (every task; the fuzz and speed in Task 8).
- **Dry run:** every task was applied in order to a copy of master at d61881d (the spec on cf45716): its new files, the run of Step 3 as it says, its edits, then the green run. The whole suite passed after every task, and the 500-year soak passed at the end.
