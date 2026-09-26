# Phase 4h: Succession Intrigue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 4g's crises gain a hidden layer: truths the world does not yet know, which the player can uncover, expose, exploit or bury.
- A master may have been poisoned; a claimant may be a rival sect's puppet, a disciple a cult's spy, a will a forgery; a rightful heir may have been framed, and returns years later.
- New ways to the seat: the supreme art, the founder's test, marriage into the master's line, an arbiter's verdict, an outsider named heir.
- The player plots too (poison, spies, puppets, frames, forgeries), and lives with the risk of being found out.

**Architecture:**
- **A plot** is an entity (`kind = "plot"`) per hidden truth, with its clues and a secret fact (`spread = False`). The meta row `open_plots` indexes the open ones; the seasonal hooks (leak, burial, cold, each type's own) read only it.
- **`systems/plots.py`** owns the model, clues, accusation and exposure, and three registries the type modules fill: `EXPOSE_HOOKS` (each type's consequence), `SEASON_HOOKS` (a spy's year), `BEGUN_HOOKS` (a puppet backed when a crisis begins). The registries sit at the top of the module, before its imports: the faction clock's import chain loads the type modules while `plots` is still loading.
- **The type modules** (`murder`, `puppets`, `frames`, `legitimacy`) hook 4g's crisis by listeners on its events, by `SC._begun` calling `plots.crisis_begun` at its end, and by `SC.decide_events` importing `plots.contest_exposures` and `legitimacy.arbitration_events` lazily.
- **The player's part** is `IntrigueMixin` (`engine/intrigue.py`) over plain rule modules in the `*_block` / `*_events` style; the player's own schemes are `systems/scheming.py`.

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-25-phase4h-succession-intrigue-design.md`

## Global Constraints

- **Save format:** no save-format version change.
  - New state lives in plot entities, in faction data (`poisoned`, `pocket`, `supreme_art`, `art_manual`, `heir_since`, `outsider`), person data (`spy_of`, `framed`, `searched`), a crisis's `plots`, and the meta rows `open_plots` and `exiles`.
- **Knowledge vs truth:**
  - a plot's truth is known only to its plotter, its patron, and those who found it out or heard it leak;
  - the Succession block's "Found" and "Suspicions" come only from the player's own clues; a clue's words name only the person it points to.
- **Reads never write:** a look, a page or a brief never makes, finds or exposes a plot.
- **The entity cache (4e):** all plot state is written through `update_data`, never by editing `.data` in place.
- **One effect per event kind:** a new module never registers a second `@effect` for an existing kind; it uses `@listen`.
- **Speed (CPU time, `time.process_time`, averaged over 10 calls after `gc.collect()`):**
  - the plot hooks with 50 open plots: under 5 ms a season;
  - a turn at a seat with plots: under 50 ms (ruling 1);
  - the 500-year soak keeps its limits.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The player accuses an innocent the clues pointed at.**
   - A red herring leads there; the player loses 30 merit, the accused remembers, and a proud accused calls them out.
   - Task 1 pins it with `test_a_red_herring_can_make_you_accuse_an_innocent`; Task 5 with `test_a_proud_man_falsely_accused_calls_you_out`.
2. **A leader dies while the player is talking to them or fighting.**
   - The conversation and the duel end cleanly; no rule is broken (a dead conversation partner was the fuzz's find).
   - Task 8 pins it with `test_a_plotting_heir` (the harness's own leader deaths only strike between scenes; the poisonings strike anywhere).
3. **An exposed plotter far from the player.**
   - They never win the seat in a far summary, whatever the rolls.
   - Task 8 pins it with `test_far_away_an_exposed_plotter_cannot_win_and_a_puppet_is_weighed_up`.
4. **The framed player comes back.**
   - Not before 4 seasons; then a crisis with the player and the holder.
   - Task 3 pins it with `test_a_framed_player_may_come_back_to_demand_the_seat`; Task 5 with `test_a_framed_player_may_demand_the_seat_back`.
5. **Many open plots in a long world.**
   - The seasonal hooks stay cheap.
   - Task 8 pins it with `test_the_plot_hooks_stay_cheap_with_fifty_open_plots`.

## Plan-time rulings (deviations from the spec, argued)

1. **A turn at a seat with plots is held to 4g's 50 ms turn budget,** not "at most +2 ms". Windows' CPU clock ticks in 15.6 ms steps, so a 2 ms difference cannot be measured. *Cost if wrong:* a slow plot hook on a turn goes unnoticed below 50 ms.
2. **4g's tests still 4h's intrigue.** `tests/intrigue.py`'s `still(monkeypatch)` zeroes every 4h chance knob; Task 1 adds it to the calm fixtures of the ten 4g crisis test files, and each 4h test turns on only the knob it tests. An NPC's founder's test settled 4g's test crises at random. *Cost if wrong:* none; the fuzz and the soak run unstilled.
3. **A red herring:** a murder's witness and motive clues point at an innocent with a motive with chance 0.2 (`murder.RED_HERRING`), marked `false`. The spec's clues all point at the plotter, which left a false accusation (two clues) unreachable. `check_plots` exempts a clue marked false. *Cost if wrong:* the player is misled a fifth of the time.
4. **A crisis tells the plots it has begun by a direct call:** `SC._begun` calls `plots.crisis_begun` at its end, which runs `BEGUN_HOOKS` (a puppet backed, an outsider's claim). A `sky_started` listener in a new module ran before 4g's own. *Cost if wrong:* none.
5. **An NPC who fails the founder's test and lives drops a realm** through `testament.set_realm`, which keeps the realm's label and the body's stage in step. The fuzz found the label out of step; 4g's transmission (a realm gained) now goes through it too. *Cost if wrong:* none.
6. **A framed crime's fact is a lie with its liar:** recorded `is_true = False` with `extra = {"liar": framer}`, as 4e's `check_knowledge` requires of every false fact. *Cost if wrong:* none.
7. **The 4g fuzz harness kills a leader only between scenes** (no conversation, no combat). A leader killed by the harness mid-conversation left a dead partner; the 4h fuzz keeps the poisonings, which strike through the game's own events. *Cost if wrong:* none; it is a test's harness.
8. **The player's spy reports ride the spy's season hook** (`SEASON_HOOKS["spy"]`): one hook per type. *Cost if wrong:* none.
9. **An exposed scheme's bounty comes from the 3b law:** the deed facts (`poisoner`, `spymaster`, `framer`, `forger`, `puppet_master`, `murdered`) weigh `law.SCHEME_WEIGHT` (5.0), which the town's belief turns into a 100-silver bounty. *Cost if wrong:* none.
10. **A murder's witness is asked about "the night"** only while the crisis lives; afterwards the witness has nothing to add. *Cost if wrong:* a cold murder cannot be reopened by the witness.
11. **A far crisis's founder's test** (`legitimacy.far_founder`) is tried in claimant order by the ambitious of a great sect, and the first to pass wins before the weighted draw. *Cost if wrong:* none visible.
12. **Accusing needs two clues and the faction's seat, for every type, with or without a live crisis.** The spec asked a live crisis for murders, puppets and forgeries. A murder found out after its crisis still expels and names the murderer (no claim is left to strike). *Cost if wrong:* a settled seat's old murder can still be brought before the elders.

## Files

| File | Responsibility |
|---|---|
| `systems/plots.py` | The plot model and index, clues, the quarters search, suspicions, accusation, exposure, leaks, burial, the cold trail, the contest's exposures, the hook registries. |
| `systems/murder.py` | The poisoned master, motives, the body, the witness, the letters, the murder exposed. |
| `systems/puppets.py` | Puppets (silver, the lent fighter, the pocket) and cult spies (planting, theft, exposure). |
| `systems/frames.py` | The forged will, framing, exile and the return (NPC and player). |
| `systems/legitimacy.py` | The supreme art, the founder's test, marriage, arbitration, the outsider, the far founder. |
| `systems/scheming.py` | The player's poison, spy, puppet, frame and forgery, and their exposure. |
| `engine/intrigue.py` | `IntrigueMixin`: the choices, the talk asks, the handlers. |
| `narrate/intrigue_text.py`, `narrate/grammar/intrigue.toml` | Clue words, the tales, the deeds, the scene's suspicions. |
| `tests/intrigue.py` | `still(monkeypatch)`. |

Existing files touched: `systems/succession_crisis.py`, `systems/claimants.py`, `systems/world_clock.py`, `systems/wars.py`, `systems/schism.py`, `systems/testament.py`, `systems/mortality.py`, `systems/law.py`, `systems/attitude.py`, `debug/invariants.py`, `narrate/crisis_text.py`, `narrate/outcomes.py`, `narrate/brief.py`, `engine/game.py`, `engine/commands.py`, `engine/crisis_page.py`, `engine/standing_page.py`, `docs/world-events.md`, and the ten 4g crisis test files (`still`).

**How each task is laid out:**
1. The tests, as whole new files.
2. The red run.
3. The new modules, as whole files.
4. One patch script, `.patches/4h_taskN.py`, holding the task's edits to existing files. Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: Plots, clues, and the poisoned master

The plot entity and its index, clues and who found them, suspicions, accusation (true or false), exposure, and the seasonal hooks (leak, burial, the trail gone cold). The first plot type: a leader's natural death may be a poisoning by someone with a motive; the crisis that follows is in doubt (`suspicion`) and carries the plot; the body, the witness and the quarters point at the plotter (or, a fifth of the time, at an innocent: ruling 3). An NPC who knows speaks at the contest. `check_plots` joins the debug rules, and 4g's crisis tests are stilled (ruling 2).

**Files:**
- Create: `systems/murder.py`
- Create: `systems/plots.py`
- Create: `tests/intrigue.py`
- Create: `tests/test_plots.py`
- Modify (by `.patches/4h_task1.py`): `systems/succession_crisis.py`, `systems/claimants.py`, `systems/world_clock.py`, `debug/invariants.py`, `tests/test_crisis_contest.py`, `tests/test_crisis_minors.py`, `tests/test_crisis_play.py`, `tests/test_crisis_review.py`, `tests/test_crisis_screens.py`, `tests/test_crisis_season.py`, `tests/test_regency.py`, `tests/test_schism.py`, `tests/test_succession_crisis.py`, `tests/test_testament.py`, `tests/test_crisis_fuzz.py`

**Interfaces:**
- Consumes: 4g's `SC` (`begin_events`, `_begun`, `decide_events`, `doubt`, `crisis_of`, `live`, `standing_claimants`), `C` (`ambitious`, `staff`, `lean`, `PROOF_LEAN`), `world_clock.SEASON_HOOKS`; 4e's `record_fact(spread=False)`, `believe`.
- Produces:
  - `plots` (P): `EXPOSE_HOOKS`, `SEASON_HOOKS`, `BEGUN_HOOKS` (at the module's top), `TYPES`, `PREDICATES`, `LEAK_CHANCE`, `BURY_CHANCE`, `COLD_SEASONS`, `NPC_EXPOSE`, `NPC_EXPOSE_MANY`, `FALSE_MERIT`, `ACCUSE_CLUES`, `QUARTERS`, `SEARCH_CHANCE`; `open_plots(world) -> list[int]`, `plot_of(world, id)`, `plots_of(world, faction, types=TYPES)`, `clue(kind, points_to, **more) -> dict`, `made_events(world, kind, key, plotter, faction, place, target=None, patron=None, serves=None, clues=(), extra=None)`, `knows`, `learn(world, person, plot, confidence=1.0, channel='told')`, `unfound(plot, kind, finder)`, `found_events(world, plot, kind, finder, place)`, `search_block/search_events(world, person, suspect[, place])`, `found_by(world, plot, person)`, `suspicions(world, person, faction=None) -> {person: [clue kinds]}`, `proven`, `accuse_block/accuse_events(world, person, suspect, faction[, place])`, `exposed_events(world, plot, exposer, place)`, `crisis_begun(world, occurrence)`, `contest_exposures(world, occurrence)`, `season_events(world, n)`; events `plot_made`, `clue_found`, `quarters_searched`, `false_accusation`, `plot_exposed`, `plot_leaked`, `witness_lost`, `plot_closed`.
  - `murder` (M): `MURDER_CHANCE`, `RED_HERRING`, `EXAMINE_BASE`, `EXAMINE_PER_REALM`, `POISONS`, `motives(world, f) -> [(person, patron)]`, `murder_events(world, f, victim, plotter, patron, place, rng)`, `murder_of(world, occurrence)`, `examine_block/examine_chance/examine_events(world, occurrence, player)`, `witness_plot(world, player, npc)`, `night_events(world, player, npc, place)`; events `body_examined`, `murder_revealed`; faction data `poisoned`.
  - `tests/intrigue.py`: `still(monkeypatch)`. `SC`: the doubt `suspicion`; a crisis's `plots`. `debug.invariants.check_plots(world)`.

- [ ] **Step 1: Write the failing tests**

`tests/intrigue.py`:
```python
"""Stilling phase 4h's intrigue in tests of what came before it (4g's crises): no murders, puppets, spies,
forgeries, frames, founder's tests, weddings, arbiters or outsiders unless a test asks for one."""

import importlib

KNOBS = (("systems.murder", ("MURDER_CHANCE",)), ("systems.puppets", ("PUPPET_CHANCE", "SPY_CHANCE")),
         ("systems.frames", ("FORGE_CHANCE", "FRAME_CHANCE")),
         ("systems.legitimacy", ("NPC_TRY", "MARRY_CHANCE", "ARBITER_CHANCE", "OUTSIDER_CHANCE")))


def still(monkeypatch) -> None:
    for name, knobs in KNOBS:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError:
            continue  # a later task's module, not written yet
        for knob in knobs:
            if hasattr(module, knob):
                monkeypatch.setattr(module, knob, 0.0)
```

`tests/test_plots.py`:
```python
import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from debug.invariants import check_knowledge, check_plots
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.beliefs import known_people
from systems.creation import CreationChoice
from world.events import Event, commit
from tests.intrigue import still


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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(M, "MURDER_CHANCE", 1.0)
    monkeypatch.setattr(M, "RED_HERRING", 0.0)


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def poisoned_sect(game):
    """The orthodox sect's master dies 'of age', poisoned by a proud elder; the player stands at the seat."""
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["proud"])
    world.update_data(elders[1], traits=["kind"], realm="mortal")
    for keeper in staff(world, sect, seat, "keeper"):
        world.update_data(keeper, traits=["kind"])
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])  # a second claimant
    [leader] = staff(world, sect, seat, "leader")
    real = M.motives
    M.motives = lambda world, faction: [(elders[0], None)]  # the proud elder alone (a war's agent aside)
    try:
        commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    finally:
        M.motives = real
    [pid] = P.open_plots(world)
    return sect, seat, leader, elders[0], world.entity(pid)


def a_season(game):
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)


def test_a_natural_death_with_a_motive_is_a_poisoning_kept_secret(game):
    world, me = game.world, game.player.id
    sect, seat, leader, proud, plot = poisoned_sect(game)
    d = plot.data
    assert d["type"] == "murder" and d["plotter"] == proud and d["target"] == leader and d["state"] == "open"
    assert [c["kind"] for c in d["clues"]] == ["body", "witness", "motive"]
    assert d["known_by"] == [proud]
    fact = world.fact(d["fact"])
    assert fact.predicate == "poisoned" and {b.knower for b in world.believers(fact.id)} == {proud}
    assert world.entity(sect).data["poisoned"] == plot.id and SC.doubt(world, sect) == "suspicion"
    assert check_plots(world) == []


def test_the_crisis_after_a_poisoning_carries_the_plot(game):
    world = game.world
    sect, seat, leader, proud, plot = poisoned_sect(game)
    a_season(game)
    crisis = SC.crisis_of(SC.live(world, sect))
    assert crisis["cause"] == "suspicion" and crisis["plots"] == [plot.id]
    assert world.entity(sect).data.get("poisoned") is None


def test_no_motive_no_murder(game, monkeypatch):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    for person in staff(world, sect, seat, "elder") + staff(world, sect, seat, "keeper"):
        world.update_data(person, traits=["kind"])
    monkeypatch.setattr(M, "motives", lambda world, faction: [])
    [leader] = staff(world, sect, seat, "leader")
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    assert P.open_plots(world) == []


def test_examining_the_body_names_the_poison_and_points_at_the_plotter(game, monkeypatch):
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    world, me = game.world, game.player.id
    sect, seat, leader, proud, plot = poisoned_sect(game)
    a_season(game)
    occurrence = SC.live(world, sect)
    assert M.examine_block(world, occurrence, me) is None
    commit(world, M.examine_events(world, occurrence, me))
    assert P.suspicions(world, me, sect) == {proud: ["body"]}
    assert proud in known_people(world, me)  # the clue named them
    assert M.examine_block(world, SC.live(world, sect), me) is not None  # once a crisis


def test_the_witness_tells_what_they_saw_once_you_have_reason_to_ask(game):
    world, me = game.world, game.player.id
    sect, seat, leader, proud, plot = poisoned_sect(game)
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "witness")
    assert M.witness_plot(world, me, witness) is None  # no crisis yet: no whispers, no clue
    a_season(game)
    assert M.witness_plot(world, me, witness).id == plot.id  # the whispers of poison give reason
    commit(world, M.night_events(world, me, witness, seat))
    assert P.suspicions(world, me, sect) == {proud: ["witness"]}


def test_a_suspects_quarters_hold_the_motive(game, monkeypatch):
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect, seat, leader, proud, plot = poisoned_sect(game)
    assert P.search_block(world, me, proud) is not None  # no suspicion, no search
    a_season(game)
    commit(world, M.examine_events(world, SC.live(world, sect), me))
    assert P.search_block(world, me, proud) is None
    commit(world, P.search_events(world, me, proud, seat))
    assert sorted(P.suspicions(world, me, sect)[proud]) == ["body", "motive"]
    assert P.search_block(world, me, proud) == "You searched their quarters this season."


def test_two_clues_expose_the_murderer(game, monkeypatch):
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect, seat, leader, proud, plot = poisoned_sect(game)
    a_season(game)
    occurrence = SC.live(world, sect)
    assert SC.claimant(SC.crisis_of(occurrence), proud) is not None
    commit(world, M.examine_events(world, occurrence, me))
    assert P.accuse_block(world, me, proud, sect) is not None  # one clue is a suspicion, not a case
    commit(world, P.search_events(world, me, proud, seat))
    assert P.accuse_block(world, me, proud, sect) is None
    commit(world, P.accuse_events(world, me, proud, sect, seat))
    assert world.entity(plot.id).data["state"] == "exposed" and plot.id not in P.open_plots(world)
    assert SC.claimant(SC.crisis_of(SC.live(world, sect)), proud) is None  # struck from the claims
    assert F.membership(world, proud, sect)[1]["status"] == "expelled"
    assert world.facts(predicate="murdered", subject=proud)
    elders = [e for e in staff(world, sect, seat, "elder") if e != proud]
    assert all(any(m.feeling == "grateful" for m in world.memories(e, about=me)) for e in elders)
    assert check_plots(world) == []
    assert check_knowledge(world) == []  # the exposer saw it: a witness at no retellings


def test_a_red_herring_can_make_you_accuse_an_innocent(game, monkeypatch):
    monkeypatch.setattr(M, "RED_HERRING", 1.0)
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 50, "status": "member",
                                            "secret": False})
    for person in staff(world, sect, seat, "elder"):
        world.update_data(person, traits=["proud"])
    [leader] = staff(world, sect, seat, "leader")
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    [pid] = P.open_plots(world)
    plot = world.entity(pid)
    innocent = next(c["points_to"] for c in plot.data["clues"] if c.get("false"))
    assert innocent != plot.data["plotter"]
    a_season(game)
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "witness")
    commit(world, M.night_events(world, me, witness, seat))
    commit(world, P.search_events(world, me, innocent, seat))
    assert P.accuse_block(world, me, innocent, sect) is None  # two clues: the case looks sound
    commit(world, P.accuse_events(world, me, innocent, sect, seat))
    assert world.entity(pid).data["state"] == "open"
    assert F.membership(world, me, sect)[1]["merit"] == 50 - P.FALSE_MERIT
    assert any(m.feeling == "wronged" and m.indelible for m in world.memories(innocent, about=me))
    assert check_plots(world) == []


def test_a_secret_leaks_a_witness_can_be_lost_and_a_trail_goes_cold(game, monkeypatch):
    monkeypatch.setattr(P, "LEAK_CHANCE", 1.0)
    monkeypatch.setattr(P, "BURY_CHANCE", 1.0)
    world = game.world
    sect, seat, leader, proud, plot = poisoned_sect(game)
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "witness")
    n = lives.current_season(world)
    commit(world, P.season_events(world, n))
    plot = world.entity(plot.id)
    assert len(plot.data["known_by"]) == 2  # someone at the seat heard it
    assert world.entity(witness).data.get("vanished") and not world.targets(witness, "located_in")
    assert any(c["kind"] == "missing" for c in plot.data["clues"])
    assert any(c.get("lost") for c in plot.data["clues"] if c["kind"] == "witness")
    commit(world, P.season_events(world, n + P.COLD_SEASONS))
    assert world.entity(plot.id).data["state"] == "cold" and plot.id not in P.open_plots(world)
    assert check_plots(world) == []


def test_an_npc_who_knows_lays_it_before_the_elders(game, monkeypatch):
    monkeypatch.setattr(P, "NPC_EXPOSE", 1.0)
    world = game.world
    sect, seat, leader, proud, plot = poisoned_sect(game)
    a_season(game)
    occurrence = SC.live(world, sect)
    voter = next(v for v in C.voters(world, sect) if v != proud and not world.entity(v).data.get("is_player"))
    P.learn(world, voter, world.entity(plot.id))
    world.set_time(occurrence.data["ends"]["active"])
    sky.observe(world, seat)
    assert world.entity(plot.id).data["state"] == "exposed"
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert proud not in {c["person"] for c in crisis["claimants"]}
    assert check_plots(world) == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_plots.py`
Expected: `ModuleNotFoundError: No module named 'systems.murder'` (the test imports it before `systems.plots`).

- [ ] **Step 3: Write the new modules**

`systems/murder.py`:
```python
"""The poisoned master (phase 4h spec 4): a natural death that was not, its clues, and what exposure costs.

When a staffed faction's leader dies of age or illness and someone had a motive, a seeded roll makes it a
poisoning: a `murder` plot. The world sees a natural death, but whispers of poison put the seat in doubt
(4g's cause `suspicion`, read from the faction's `poisoned`).
"""

import systems.claimants as C
import systems.plots as P
import systems.succession_crisis as SC
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.kin import kin_of
from systems.membership import set_membership
from systems.tournaments import alive, realm_of
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

MURDER_CHANCE = 0.25
RED_HERRING = 0.2  # the witness and the letters point at an innocent with a motive (plan ruling 3)
NATURAL = frozenset({"age", "illness"})
WAR = -0.8
EXAMINE_BASE, EXAMINE_PER_REALM = 0.6, 0.1
POISONS = {"unorthodox_clan": "the black lotus of a poison valley", "demonic_cult": "a cult's blood-venom",
           "bandit_fort": "a crude arsenic", None: "a slow poison from the south"}


def motives(world, faction: int) -> list[tuple[int, int | None]]:
    """(plotter, patron): an ambitious elder or keeper; an agent of a faction at war; a cult's spy in its halls."""
    found = [(p, None) for p in C.staff(world, faction, ("elder", "keeper")) if C.ambitious(world, p)]
    for other, value, _ in world.relations_from(faction, "stance"):
        if value <= WAR and not world.entity(other).data.get("dissolved"):
            agents = C.staff(world, other, ("elder", "keeper", "disciple"))
            if agents:
                found.append((max(agents, key=lambda p: (realm_of(world, p), -p)), other))
    found += [(spy.data["plotter"], spy.data["patron"]) for spy in P.plots_of(world, faction, ("spy",))
              if alive(world, spy.data["plotter"])]
    return found


def poison_words(world, plotter: int, patron) -> str:
    source = patron if isinstance(patron, int) and world.entity(patron).kind == "faction" else None
    kind = world.entity(source).data["type"] if source is not None else None
    return POISONS.get(kind, POISONS[None])


def murder_events(world, faction: int, victim: int, plotter: int, patron, place: int, rng) -> list[Event]:
    """A poisoning: the plot and its three clues (the body, a witness at the seat, the plotter's quarters)."""
    present = sorted(p.id for p in people_at(world, place) if p.id not in (plotter, victim)
                     and not p.data.get("is_player") and alive(world, p.id))
    innocents = [p for p, _ in motives(world, faction) if p not in (plotter, victim)]
    blamed = rng.choice(innocents) if innocents and rng.random() < RED_HERRING else None
    points = blamed if blamed is not None else plotter
    extra = {"false": True} if blamed is not None else {}
    clues = [P.clue("body", plotter, poison=poison_words(world, plotter, patron))]
    if present:
        clues.append(P.clue("witness", points, witness=rng.choice([p for p in present if p != points] or present),
                            **extra))
    clues.append(P.clue("motive", points, at="quarters", **extra))
    return P.made_events(world, "murder", f"murder:{faction}:{victim}", plotter, faction, place, target=victim,
                         patron=patron, clues=clues)


@listen("died")
def _poisoned(world, event, event_id: int) -> None:
    """A leader's natural death: with someone to want it, a seeded roll makes it murder (spec 4)."""
    victim = event.actors[-1]
    if event.data.get("cause") not in NATURAL or event.data.get("poisoned_by") is not None:
        return
    for fid, _, data in F.memberships(world, victim):
        faction = world.entity(fid)
        if data.get("role") != "leader" or faction.data.get("type") not in F.STAFFED or faction.data.get("dissolved"):
            continue
        rng = rng_for(world.world_seed, f"murder:{fid}:{victim}")
        if rng.random() >= MURDER_CHANCE:
            continue
        choices = [m for m in motives(world, fid) if m[0] != victim]
        if not choices:
            continue
        plotter, patron = rng.choice(choices)
        place = event.place if event.place is not None else faction.data.get("seat")
        commit(world, murder_events(world, fid, victim, plotter, patron, place, rng))


@listen("plot_made")
def _whispers(world, event, event_id: int) -> None:
    """Whispers of poison: the seat is in doubt (4g's `suspicion`)."""
    if event.data["type"] == "murder":
        plot = world.entity_by_seed(f"plot:{event.data['key']}")
        world.update_data(event.data["faction"], poisoned=plot.id)


# --- the clues (spec 4) --------------------------------------------------------------------------------------

def murder_of(world, occurrence):
    """The crisis's open murder plot, if it has one."""
    for pid in SC.crisis_of(occurrence).get("plots", []):
        plot = P.plot_of(world, pid)
        if plot is not None and plot.data["type"] == "murder" and plot.data["state"] == "open":
            return plot
    return None


def examine_block(world, occurrence, player: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] != "mourning":
        return "The late master has been laid in the earth."
    if player in crisis.get("examined", []):
        return "You have looked on the late master as long as the mourners will allow."
    return None


def examine_chance(world, player: int) -> float:
    return EXAMINE_BASE + EXAMINE_PER_REALM * max(0, realm_of(world, player) - 1)


def examine_events(world, occurrence, player: int) -> list[Event]:
    place = occurrence.data["place"]
    plot = murder_of(world, occurrence)
    rng = rng_for(world.world_seed, f"murder:{occurrence.id}:examine:{player}")
    found = plot is not None and rng.random() < examine_chance(world, player)
    events = [Event("body_examined", (player,), place, {"occurrence": occurrence.id, "found": found,
                                                        "poison": _poison_of(plot) if found else None})]
    return events + (P.found_events(world, plot, "body", player, place) if found else [])


def _poison_of(plot) -> str | None:
    return next((c.get("poison") for c in plot.data["clues"] if c["kind"] == "body"), None)


@effect("body_examined")
def _examined(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "examined": crisis.get("examined", []) + [event.actors[0]]})


def witness_plot(world, player: int, npc: int):
    """The open murder plot this person witnessed, if the player has reason to ask them about it."""
    for pid in P.open_plots(world):
        plot = world.entity(pid)
        if plot.data["type"] != "murder":
            continue
        witnessed = any(c["kind"] == "witness" and c.get("witness") == npc and player not in c["found_by"]
                        and not c.get("lost") for c in plot.data["clues"])
        if not witnessed:
            continue
        occurrence = SC.live(world, plot.data["faction"])
        whispers = occurrence is not None and SC.crisis_of(occurrence)["cause"] == "suspicion"
        if P.found_by(world, plot, player) or whispers:
            return plot
    return None


def night_events(world, player: int, npc: int, place: int) -> list[Event]:
    """Asking about the night the master died: the witness tells what they saw."""
    plot = witness_plot(world, player, npc)
    return [Event("asked_night", (player, npc), place, {"told": plot is not None})] + (
        P.found_events(world, plot, "witness", player, place) if plot is not None else [])


# --- exposure (spec 4) ----------------------------------------------------------------------------------------

def _exposed(world, plot, exposer) -> list[Event]:
    victim = plot.data["target"]
    kin = tuple(Witness(k, "hatred", 0.8, True) for k, _ in kin_of(world, victim) if k != plot.data["plotter"])
    return [Event("murder_revealed", (plot.data["plotter"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "victim": victim, "faction": plot.data["faction"], "patron": plot.data["patron"]},
                  witnesses=kin)]


@effect("murder_revealed")
def _revealed(world, event) -> None:
    d = event.data
    plotter = event.actors[0]
    found = F.membership(world, plotter, d["faction"])
    if found and found[1].get("status", "member") == "member":
        set_membership(world, plotter, d["faction"], status="expelled")
    patron = d["patron"]
    if isinstance(patron, int) and world.entity(patron).kind == "faction":
        world.relate(d["faction"], patron, "stance", -1.0)
        world.relate(patron, d["faction"], "stance", -1.0)


@listen("murder_revealed")
def _revealed_news(world, event, event_id: int) -> None:
    plotter = event.actors[0]
    variant = make_variant("murdered", plotter, event.data["victim"], place=place_name(world, event.place))
    record_fact(world, plotter, "murdered", event.data["victim"], place=event.place, source_event=event_id,
                weight=3.0, variant=variant)


P.EXPOSE_HOOKS["murder"] = _exposed
```

`systems/plots.py`:
```python
"""Hidden truths (phase 4h spec 2.2-2.3, 3): a lasting plot per murder, puppet, spy, frame or forgery.

A plot is an entity (`kind = "plot"`) with its clues and a secret fact of its truth (recorded with
`spread = False`, as 4e's fixes). The meta row `open_plots` lists the plots still open; the seasonal hooks
(leaks, burial, the trail going cold, each type's own) read only that list.

Clues are found by actions the other modules name; a finder learns the name a clue points to. Two found
clues pointing at one person let the finder accuse them; a true accusation exposes the plot.
"""

# The registries come first: the modules that fill them (murder, puppets, frames) may be imported while this one
# is still loading (the faction clock's import chain), and must find them.
EXPOSE_HOOKS: dict = {}  # type -> (world, plot entity, exposer) -> list[Event]: each type's own consequence
SEASON_HOOKS: dict = {}  # type -> (world, plot entity, n, rng) -> list[Event]: each type's own season (a spy's year)
BEGUN_HOOKS: list = []  # (world, occurrence) -> None: called once a crisis has begun (a puppet backed)

import systems.claimants as C  # noqa: E402
import systems.lives as lives  # noqa: E402
import systems.succession_crisis as SC  # noqa: E402
import systems.world_clock as world_clock  # noqa: E402
from systems import factions as F  # noqa: E402
from systems.beliefs import believe  # noqa: E402
from systems.facts import make_variant, place_name, record_fact  # noqa: E402
from systems.membership import set_membership  # noqa: E402
from systems.tournaments import alive  # noqa: E402
from world.events import Event, Witness, commit, effect, listen  # noqa: E402
from world.gen.materialize import people_at  # noqa: E402
from world.seed import rng_for  # noqa: E402

TYPES = ("murder", "puppet", "spy", "frame", "forgery")
PREDICATES = {"murder": "poisoned", "puppet": "puppet_of", "spy": "spy_for", "frame": "framed", "forgery": "forged_will"}
LEAK_CHANCE, BURY_CHANCE, COLD_SEASONS = 0.1, 0.15, 40
COLD_TYPES = frozenset({"murder", "forgery"})
NPC_EXPOSE, NPC_EXPOSE_MANY = 0.5, 0.8
FALSE_MERIT = 30
ACCUSE_CLUES = 2


# --- the model and its index --------------------------------------------------------------------------

def open_plots(world) -> list[int]:
    return list(world.get_meta("open_plots", []))


def plot_of(world, plot_id: int):
    entity = world.entity(plot_id) if plot_id is not None else None
    return entity if entity is not None and entity.kind == "plot" else None


def plots_of(world, faction: int, types=TYPES) -> list:
    """The open plots bearing on a faction."""
    out = []
    for pid in open_plots(world):
        plot = world.entity(pid)
        if plot.data["faction"] == faction and plot.data["type"] in types:
            out.append(plot)
    return out


def clue(kind: str, points_to: int, **more) -> dict:
    return {"kind": kind, "points_to": points_to, "found_by": [], **more}


def made_events(world, kind: str, key: str, plotter: int, faction: int, place: int, target=None, patron=None,
                serves=None, clues=(), extra: dict | None = None) -> list[Event]:
    """A plot begins. `key` makes its seed path (one plot a key); `clues` are `clue(...)` dicts."""
    return [Event("plot_made", (plotter,), place, {
        "type": kind, "key": key, "plotter": plotter, "faction": faction, "target": target, "patron": patron,
        "serves": serves, "clues": list(clues), "extra": extra or {}})]


@effect("plot_made")
def _made(world, event) -> None:
    d = event.data
    names = {"murder": "the poisoning of {t}", "puppet": "the puppet {s}", "spy": "the spy {p}",
             "frame": "the framing of {t}", "forgery": "the forged will of {p}"}

    def name(i):
        entity = world.entity(i) if isinstance(i, int) else None
        return entity.name if entity is not None else "someone"
    title = names[d["type"]].format(t=name(d["target"]), s=name(d["serves"]), p=name(d["plotter"]))
    known = [p for p in (d["plotter"], d["patron"]) if isinstance(p, int) and world.entity(p).kind == "person"]
    data = {"type": d["type"], "plotter": d["plotter"], "patron": d["patron"], "target": d["target"],
            "faction": d["faction"], "serves": d["serves"], "made_at": world.time,
            "season": lives.current_season(world), "clues": d["clues"], "known_by": known, "state": "open",
            "fact": None, **d["extra"]}
    plot = world.add_entity("plot", title, data, f"plot:{d['key']}")
    world.set_meta("open_plots", open_plots(world) + [plot])


@listen("plot_made")
def _secret(world, event, event_id: int) -> None:
    """The truth is a fact from the start, but nobody holds it but the plotter (4e's way with a fix)."""
    d = event.data
    plot = world.entity_by_seed(f"plot:{d['key']}")
    target = d["target"] if d["type"] != "puppet" else d["patron"]
    actor = d["plotter"] if d["type"] != "puppet" else d["serves"]
    predicate = PREDICATES[d["type"]]
    variant = make_variant(predicate, actor, target if isinstance(target, int) else None,
                           place=place_name(world, event.place))
    variant["faction_of"] = d["faction"]
    fact = record_fact(world, actor, predicate, target if isinstance(target, int) else None, place=event.place,
                       source_event=event_id, weight=2.5, variant=variant, spread=False, extra={"plot": plot.id})
    world.update_data(plot.id, fact=fact)
    for knower in plot.data["known_by"]:
        believe(world, knower, fact, variant, None, 1.0, 0, "witness")


def knows(world, person: int, plot) -> bool:
    return person in plot.data["known_by"]


def learn(world, person: int, plot, confidence: float = 1.0, channel: str = "told") -> None:
    """Someone comes to know the truth of a plot."""
    if person in plot.data["known_by"]:
        return
    world.update_data(plot.id, known_by=plot.data["known_by"] + [person])
    fact = world.fact(plot.data["fact"]) if plot.data.get("fact") else None
    if fact is not None:
        believe(world, person, fact.id, fact.data["variant"], None, confidence, 0 if channel == "witness" else 1,
                channel)  # who saw it for themself heard it at no retellings


def _close(world, plot_id: int, state: str) -> None:
    world.update_data(plot_id, state=state)
    world.set_meta("open_plots", [p for p in open_plots(world) if p != plot_id])


# --- clues, suspicion, accusation (spec 3) ---------------------------------------------------------------

def unfound(plot, kind: str, finder: int) -> dict | None:
    return next((c for c in plot.data["clues"] if c["kind"] == kind and finder not in c["found_by"]
                 and not c.get("lost")), None)


def found_events(world, plot, kind: str, finder: int, place: int) -> list[Event]:
    """The finder turns up a clue of this kind (the caller has rolled for it)."""
    found = unfound(plot, kind, finder)
    if found is None:
        return []
    return [Event("clue_found", (finder, found["points_to"]), place,
                  {"plot": plot.id, "kind": kind, "points_to": found["points_to"]})]


@effect("clue_found")
def _found(world, event) -> None:
    d = event.data
    plot = world.entity(d["plot"])
    clues = [dict(c, found_by=c["found_by"] + [event.actors[0]]) if c["kind"] == d["kind"]
             and event.actors[0] not in c["found_by"] else c for c in plot.data["clues"]]
    world.update_data(plot.id, clues=clues)


@listen("clue_found")
def _clue_known(world, event, event_id: int) -> None:
    """The finder now knows a name: a private fact of their own (nobody else holds it)."""
    d = event.data
    plot = world.entity(d["plot"])
    variant = make_variant("clue", d["points_to"], plot.data["faction"], place=place_name(world, event.place))
    variant.update(kind=d["kind"], plot_type=plot.data["type"])
    fact = record_fact(world, d["points_to"], "clue", plot.data["faction"], place=event.place, source_event=event_id,
                       weight=0.5, variant=variant, spread=False, extra={"plot": plot.id})
    believe(world, event.actors[0], fact, variant, None, 0.5, 0, "witness")


QUARTERS = frozenset({"motive", "mark", "planted"})  # clues kept in someone's quarters
SEARCH_CHANCE = 0.5


def search_block(world, person: int, suspect: int) -> str | None:
    if suspect not in suspicions(world, person) and not world.entity(suspect).data.get("framed"):
        return "You have no reason to turn their quarters over."
    if world.targets(suspect, "located_in") != world.targets(person, "located_in"):
        return "Their quarters are not here."
    if (world.entity(person).data.get("searched") or {}).get(str(suspect)) == lives.current_season(world):
        return "You searched their quarters this season."
    return None


def search_events(world, person: int, suspect: int, place: int) -> list[Event]:
    """Turning a suspect's quarters over: a chance at every quarters clue pointing at them (spec 4, 5.2, 6.2)."""
    season = lives.current_season(world)
    rng = rng_for(world.world_seed, f"plots:search:{person}:{suspect}:{season}")
    found = rng.random() < SEARCH_CHANCE
    events = [Event("quarters_searched", (person, suspect), place, {"season": season, "found": found})]
    if found:
        for pid in open_plots(world):
            plot = world.entity(pid)
            for c in plot.data["clues"]:
                here = (c.get("at") == "quarters" and c["points_to"] == suspect) or \
                    (c.get("at") == "quarters_of" and c.get("owner") == suspect)  # evidence planted on another
                if c["kind"] in QUARTERS and here and person not in c["found_by"] and not c.get("lost"):
                    events += found_events(world, plot, c["kind"], person, place)
    return events


@effect("quarters_searched")
def _searched(world, event) -> None:
    person, suspect = event.actors
    searched = dict(world.entity(person).data.get("searched") or {})
    searched[str(suspect)] = event.data["season"]
    world.update_data(person, searched=searched)


def found_by(world, plot, person: int) -> list[dict]:
    return [c for c in plot.data["clues"] if person in c["found_by"]]


def suspicions(world, person: int, faction: int | None = None) -> dict[int, list[str]]:
    """{suspect: [clue kinds]} from the open plots whose clues this person has found."""
    out: dict[int, list[str]] = {}
    for pid in open_plots(world):
        plot = world.entity(pid)
        if faction is not None and plot.data["faction"] != faction:
            continue
        for c in found_by(world, plot, person):
            out.setdefault(c["points_to"], []).append(c["kind"])
    return out


def proven(world, person: int, suspect: int, faction: int):
    """The open plot of this faction whose plotter is `suspect`, if this person found two clues pointing at them."""
    for plot in plots_of(world, faction):
        if plot.data["plotter"] == suspect and sum(1 for c in found_by(world, plot, person)
                                                   if c["points_to"] == suspect) >= ACCUSE_CLUES:
            return plot
    return None


def accuse_block(world, person: int, suspect: int, faction: int) -> str | None:
    clues = [k for k in suspicions(world, person, faction).get(suspect, [])]
    if len(clues) < ACCUSE_CLUES:
        return "You need two things that point at them before the elders will hear you."
    return None


def accuse_events(world, person: int, suspect: int, faction: int, place: int) -> list[Event]:
    """Before the elders: a true accusation exposes the plot; a false one costs the accuser (spec 3)."""
    plot = proven(world, person, suspect, faction)
    if plot is not None:
        return exposed_events(world, plot, person, place)
    return [Event("false_accusation", (person, suspect), place, {"faction": faction},
                  witnesses=(Witness(suspect, "wronged", 0.8, True),))]


@effect("false_accusation")
def _false(world, event) -> None:
    person, faction = event.actors[0], event.data["faction"]
    found = F.membership(world, person, faction)
    if found and found[1].get("status", "member") == "member":
        set_membership(world, person, faction, merit=max(0, found[1].get("merit", 0) - FALSE_MERIT))


@listen("false_accusation")
def _false_news(world, event, event_id: int) -> None:
    person, suspect = event.actors
    variant = make_variant("false_accusation", person, suspect, place=place_name(world, event.place))
    record_fact(world, person, "false_accusation", suspect, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


# --- exposure (spec 3) -----------------------------------------------------------------------------------

def exposed_events(world, plot, exposer: int | None, place: int) -> list[Event]:
    elders = [e for e in C.staff(world, plot.data["faction"], ("leader", "elder")) if e != plot.data["plotter"]]
    thanks = tuple(Witness(e, "grateful", 0.5) for e in elders) if exposer is not None else ()
    actors = (exposer, plot.data["plotter"]) if exposer is not None else (plot.data["plotter"],)
    events = [Event("plot_exposed", actors, place, {"plot": plot.id, "exposer": exposer})]
    if thanks:
        events.append(Event("thanked", (exposer,), place, {"plot": plot.id}, witnesses=thanks))
    hook = EXPOSE_HOOKS.get(plot.data["type"])
    return events + (hook(world, plot, exposer) if hook is not None else [])


@effect("plot_exposed")
def _exposed(world, event) -> None:
    plot = world.entity(event.data["plot"])
    _close(world, plot.id, "exposed")
    occurrence = SC.live(world, plot.data["faction"])
    if occurrence is not None:  # the plotter is struck from any claim they hold
        crisis = SC.crisis_of(occurrence)
        who = plot.data["plotter"]
        claimants = [c for c in crisis["claimants"] if c["person"] != who]
        declared = {k: v for k, v in crisis.get("declared", {}).items() if v != who}
        world.update_data(occurrence.id, data={**crisis, "claimants": claimants, "declared": declared})


@listen("plot_exposed")
def _published(world, event, event_id: int) -> None:
    """Out in the open: the truth is told like any deed (4e's publishing), now at full weight."""
    plot = world.entity(event.data["plot"])
    secret = world.fact(plot.data["fact"]) if plot.data.get("fact") else None
    if secret is None:
        return
    record_fact(world, secret.subject, secret.predicate, secret.object, place=event.place, source_event=event_id,
                weight=2.5, variant=dict(secret.data["variant"]), extra={"plot": plot.id, "exposed": True})
    if event.data["exposer"] is not None:
        learn(world, event.data["exposer"], world.entity(plot.id), 1.0, "witness")


def crisis_begun(world, occurrence) -> None:
    """A crisis has begun (4g's `_begun` calls this last): each registered hook may draw a plot into it."""
    for hook in BEGUN_HOOKS:
        hook(world, world.entity(occurrence.id))


# --- NPCs who know speak at the contest (spec 3) ----------------------------------------------------------

def contest_exposures(world, occurrence) -> None:
    """Before the contest: an NPC claimant or voter who knows a plot's truth may lay it before the elders."""
    crisis = SC.crisis_of(occurrence)
    faction, place = crisis["faction"], occurrence.data["place"]
    speakers = {c["person"] for c in crisis["claimants"]} | set(C.voters(world, faction))
    rng = rng_for(world.world_seed, f"plots:{occurrence.id}:contest")
    for plot in plots_of(world, faction):
        knowing = [p for p in plot.data["known_by"] if p in speakers and p not in (plot.data["plotter"],
                                                                                   plot.data["patron"])
                   and alive(world, p) and not world.entity(p).data.get("is_player")]
        chance = NPC_EXPOSE_MANY if len(knowing) > 1 else NPC_EXPOSE
        if knowing and rng.random() < chance:
            commit(world, exposed_events(world, plot, knowing[0], place))



# --- the seasons (spec 2.3) ------------------------------------------------------------------------------

def season_events(world, n: int) -> list[Event]:
    """Over open plots only: leaks, burial, the trail going cold, each type's own season."""
    events = []
    for pid in open_plots(world):
        plot = world.entity(pid)
        d = plot.data
        rng = rng_for(world.world_seed, f"plots:{pid}:{n}")
        if not alive(world, d["plotter"]) and d["type"] in ("spy", "puppet"):
            events.append(Event("plot_closed", (), None, {"plot": pid, "state": "void"}))
            continue
        if d["type"] in COLD_TYPES and n - d["season"] >= COLD_SEASONS:
            events.append(Event("plot_closed", (), None, {"plot": pid, "state": "cold"}))
            continue
        seat = world.entity(d["faction"]).data.get("seat")
        if seat is not None and rng.random() < LEAK_CHANCE:
            hearers = [p.id for p in people_at(world, seat) if p.id not in d["known_by"]
                       and not p.data.get("is_player")]
            if hearers:
                events.append(Event("plot_leaked", (rng.choice(sorted(hearers)),), seat, {"plot": pid}))
        witness = next((c for c in d["clues"] if c.get("witness") is not None and not c["found_by"]
                        and not c.get("lost") and alive(world, c["witness"])), None)
        if witness is not None and alive(world, d["plotter"]) and rng.random() < BURY_CHANCE:
            events.append(Event("witness_lost", (witness["witness"],), seat, {"plot": pid, "kind": witness["kind"]}))
        hook = SEASON_HOOKS.get(d["type"])
        if hook is not None:
            events += hook(world, plot, n, rng)
    return events


@effect("plot_closed")
def _closed(world, event) -> None:
    _close(world, event.data["plot"], event.data["state"])


@effect("plot_leaked")
def _leaked(world, event) -> None:
    learn(world, event.actors[0], world.entity(event.data["plot"]), 0.7, "gossip")


@effect("witness_lost")
def _witness_lost(world, event) -> None:
    """A witness goes missing: their clue is lost, and the loss points at the plotter (spec 2.3)."""
    witness, d = event.actors[0], event.data
    plot = world.entity(d["plot"])
    world.update_data(witness, vanished={"plot": plot.id, "time": world.time})
    world.unrelate(witness, "located_in")
    for faction, _, data in F.memberships(world, witness):
        if data.get("status", "member") == "member":
            set_membership(world, witness, faction, status="missing")
    clues = [dict(c, lost=True) if c["kind"] == d["kind"] else c for c in plot.data["clues"]]
    world.update_data(plot.id, clues=clues + [clue("missing", plot.data["plotter"])])


@listen("witness_lost")
def _witness_news(world, event, event_id: int) -> None:
    variant = make_variant("vanished", event.actors[0], None, place=place_name(world, event.place))
    record_fact(world, event.actors[0], "vanished", None, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


world_clock.SEASON_HOOKS.append(season_events)
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4h_task1.py`:
```python
"""Phase 4h, Task 1: the crisis reads the plots (a poisoning's doubt, the contest's exposures, the plots a crisis draws in), check_plots, 4g's tests stilled"""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def still(path: str) -> None:
    """A 4g test's fixture stills 4h's intrigue: they test the crisis alone."""
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    anchor = '    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)\n'
    if text.count(anchor) != 1:
        raise SystemExit(f"{path}: no single calm fixture")
    text = text.replace(anchor, anchor + "    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises\n")
    i = text.index("\n\n\n@pytest.fixture")
    text = text[:i] + "\nfrom tests.intrigue import still" + text[i:]
    file.write_text(text, encoding="utf-8", newline="\n")


edit('systems/succession_crisis.py', r'''    if fallen.get("cause") in VIOLENT:
        return "violence"''', r'''    if fallen.get("cause") in VIOLENT:
        return "violence"
    if data.get("poisoned") is not None:
        return "suspicion"  # whispers of poison (phase 4h)''')
edit('systems/succession_crisis.py', r'''    crisis, place = crisis_of(occurrence), occurrence.data["place"]
    if crisis["phase"] != "contest":
        return []
    standing = standing_claimants(world, crisis)''', r'''    if crisis_of(occurrence)["phase"] != "contest":
        return []
    from systems.plots import contest_exposures  # phase 4h: what the knowing lay before the elders first
    contest_exposures(world, occurrence)
    occurrence = world.entity(occurrence.id)
    crisis, place = crisis_of(occurrence), occurrence.data["place"]
    standing = standing_claimants(world, crisis)''')
edit('systems/succession_crisis.py', r'''    world.update_data(faction, crisis=row[W.ID], fallen=None)''', r'''    plots = [p for p in [world.entity(faction).data.get("poisoned")] if p is not None]
    world.update_data(faction, crisis=row[W.ID], fallen=None, poisoned=None)''')
edit('systems/succession_crisis.py', r'''    world.update_data(occurrence.id, data=T.at_mourning(world, crisis_of(occurrence), rng))''', r'''    world.update_data(occurrence.id, data={**T.at_mourning(world, crisis_of(occurrence), rng), "plots": plots})
    from systems.plots import crisis_begun  # phase 4h: puppets backed, and whatever else a crisis draws in
    crisis_begun(world, world.entity(occurrence.id))''')
edit('systems/claimants.py', r'''    world.update_data(d["faction"], fallen=None, **({"heir": None} if data.get("heir") == event.actors[0] else {}))''', r'''    world.update_data(d["faction"], fallen=None, poisoned=None,
                      **({"heir": None} if data.get("heir") == event.actors[0] else {}))''')
edit('systems/world_clock.py', r'''import systems.regency  # noqa: E402,F401  phase 4g: regents, usurpers, and heirs who must hold the seat''', r'''import systems.regency  # noqa: E402,F401  phase 4g: regents, usurpers, and heirs who must hold the seat
import systems.murder  # noqa: E402,F401  phase 4h: plots, and the poisoned master''')
edit('debug/invariants.py', r'''    problems += check_crises(world)
    times''', r'''    problems += check_crises(world)
    problems += check_plots(world)
    times''')
append('debug/invariants.py', r'''

def check_plots(world) -> list[str]:
    """Plots (phase 4h spec 12): the index holds exactly the open ones; their people exist; clues point true."""
    import systems.plots as P
    import systems.succession_crisis as SC
    out = []
    listed = set(P.open_plots(world))
    for plot in world.entities("plot"):
        d = plot.data
        if (d["state"] == "open") != (plot.id in listed):
            out.append(f"{plot.name} (#{plot.id}) is {d['state']} but {'in' if plot.id in listed else 'not in'} the open index")
        for key in ("plotter", "target", "faction"):
            if isinstance(d.get(key), int) and world.entity(d[key]) is None:
                out.append(f"{plot.name} points at missing #{d[key]} ({key})")
        for c in d["clues"]:
            if c["points_to"] != d["plotter"] and not c.get("false"):
                out.append(f"{plot.name}'s {c['kind']} clue points at #{c['points_to']}, not its plotter")
        if d["state"] == "exposed":
            occurrence = SC.live(world, d["faction"])
            if occurrence is not None and SC.claimant(SC.crisis_of(occurrence), d["plotter"]) is not None:
                out.append(f"{plot.name}'s exposed plotter still claims the seat")
    for pid in listed:
        if world.entity(pid) is None or world.entity(pid).kind != "plot":
            out.append(f"the open index lists #{pid}, which is no plot")
    return out
''')
still('tests/test_crisis_contest.py')
still('tests/test_crisis_minors.py')
still('tests/test_crisis_play.py')
still('tests/test_crisis_review.py')
still('tests/test_crisis_screens.py')
still('tests/test_crisis_season.py')
still('tests/test_regency.py')
still('tests/test_schism.py')
still('tests/test_succession_crisis.py')
still('tests/test_testament.py')
edit('tests/test_crisis_fuzz.py', r'''        if step % 25 == 0 and game.world.get_meta("player_id") == me:''', r'''        if step % 25 == 0 and game.world.get_meta("player_id") == me and game.focus is None and game.combat is None:''')
print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4h_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_plots.py tests/test_succession_crisis.py tests/test_crisis_contest.py`
Expected: `29 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: hidden truths - the plot and its clues, accusation and exposure, leaks and burial, the poisoned master

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: Puppets and cult spies

When a crisis begins, a hostile sect within reach may back a claimant: its silver sways the voters at the mourning's end, it lends its strongest elder as champion and a fighter in strife, and a puppet who wins puts the sect in the patron's pocket (no clashes while the puppet leads). The gifted voter and the patron's envoy can be asked. Once a year a demonic cult may plant a spy among a hostile sect's keepers and disciples; a spy's year may steal an art; an exposed spy is cast out.

**Files:**
- Create: `systems/puppets.py`
- Create: `tests/test_puppets.py`
- Modify (by `.patches/4h_task2.py`): `systems/world_clock.py`, `systems/wars.py`, `systems/schism.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Task 1: `P.made_events`, `P.clue`, `P.BEGUN_HOOKS`, `P.EXPOSE_HOOKS`, `P.SEASON_HOOKS`, `P.plots_of`, `P.knows`; 4g's `crisis_phase`, `crisis_settled`, `schism` strife, `C.lean`.
- Produces:
  - `puppets` (U): `HOSTILE`, `PUPPET_CHANCE`, `PUPPET_REACH`, `GIFT`, `POCKET_STANCE`, `EXPOSED_LEAN`, `EXPOSED_STANCE`, `SPY_CHANCE`, `THEFT_CHANCE`, `SPY_STANCE`; `patrons(world, f)`, `puppet_events(world, occurrence, patron, claimant, key, plotter=None)`, `gift_plot(world, player, npc)`, `envoy_plot(world, player, npc)`, `asked_events(world, player, npc, place, what)`, `in_pocket(world, a, b) -> bool`, `spy_events(world, sect, cult, spy, key)`, `planting_events(world, n)`; events `puppet_revealed`, `spy_revealed`, `art_stolen`; faction data `pocket`; person data `spy_of`.
  - `wars` skips a pair in the pocket; `schism` counts the lent fighter.

- [ ] **Step 1: Write the failing tests**

`tests/test_puppets.py`:
```python
import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.succession_crisis as SC
import systems.testament as T
import systems.wars as wars
import systems.world_clock as clock
from debug.invariants import check_plots
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from tests.test_crisis_play import crisis_at_seat, to_stage
from world.events import Event, commit
from tests.intrigue import still


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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(M, "MURDER_CHANCE", 0.0)
    monkeypatch.setattr(U, "PUPPET_CHANCE", 0.0)


def the_sects(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    cult = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "demonic_cult")
    world.update_data(cult, home=list(world.entity(sect).data["home"]))  # within reach
    world.relate(sect, cult, "stance", -0.8)
    world.relate(cult, sect, "stance", -0.8)
    halls.seat_of(world, cult)
    return sect, cult


def a_puppet(game, monkeypatch):
    monkeypatch.setattr(U, "PUPPET_CHANCE", 1.0)
    world = game.world
    sect, cult = the_sects(world)
    found = crisis_at_seat(game)
    [plot] = P.plots_of(world, sect, ("puppet",))
    return sect, cult, found, plot


def test_a_hostile_sect_within_reach_backs_a_puppet_with_a_fighter(game, monkeypatch):
    world = game.world
    sect, cult, (_, seat, keeper, proud, other, occurrence), plot = a_puppet(game, monkeypatch)
    d = plot.data
    assert d["patron"] == cult and d["serves"] in (keeper, proud) and d["occurrence"] == occurrence.id
    envoy = d["plotter"]
    assert world.targets(envoy, "located_in") == [seat] and F.membership(world, envoy, cult) is not None
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert plot.id in crisis["plots"]
    assert crisis["champions"][str(d["serves"])] == d["lent"] and C.role_in(world, d["lent"], cult) == "elder"
    assert check_plots(world) == []


def test_the_puppets_silver_sways_the_voters_and_a_gifted_voter_can_be_asked(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, cult, (_, seat, keeper, proud, other, occurrence), plot = a_puppet(game, monkeypatch)
    to_stage(world, occurrence, seat, "announced")  # the canvass begins: the silver is spent
    plot = world.entity(plot.id)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    puppet = str(plot.data["serves"])
    assert plot.data["gifted"] and all(crisis["sways"][str(v)][puppet] >= U.GIFT for v in plot.data["gifted"])
    voter = plot.data["gifted"][0]
    commit(world, U.asked_events(world, me, voter, seat, "silver"))
    commit(world, U.asked_events(world, me, plot.data["plotter"], seat, "envoy"))
    envoy = plot.data["plotter"]
    assert sorted(P.suspicions(world, me, sect)[envoy]) == ["envoy", "silver"]
    commit(world, P.accuse_events(world, me, envoy, sect, seat))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert world.entity(plot.id).data["state"] == "exposed"
    assert all(crisis["sways"][str(v)][puppet] <= U.GIFT + U.EXPOSED_LEAN + 1e-9 for v in plot.data["gifted"])
    assert F.stance(world, sect, cult) == pytest.approx(-1.0)  # -0.8 - 0.3, bounded
    assert check_plots(world) == []


def test_a_puppet_who_wins_puts_the_sect_in_the_patrons_pocket(game, monkeypatch):
    world = game.world
    sect, cult, (_, seat, keeper, proud, other, occurrence), plot = a_puppet(game, monkeypatch)
    puppet = plot.data["serves"]
    crisis = SC.crisis_of(world.entity(occurrence.id))
    world.update_data(occurrence.id, data={**crisis, "sways": {str(v): {str(puppet): 5.0} for v in C.voters(world, sect)}})
    to_stage(world, occurrence, seat, "active")
    assert C.role_in(world, puppet, sect) == "leader"
    assert F.stance(world, sect, cult) == U.POCKET_STANCE and U.in_pocket(world, sect, cult)
    world.relate(sect, cult, "stance", -1.0)
    world.relate(cult, sect, "stance", -1.0)
    monkeypatch.setattr(wars, "WAR_CHANCE", 1.0)
    clashes = [e for e in wars.clash_events(world, 99) if e.kind == "clash" and set(e.actors) == {sect, cult}]
    assert clashes == []  # no war on the patron while its puppet leads


def spy_in(game, monkeypatch):
    monkeypatch.setattr(U, "SPY_CHANCE", 1.0)
    world = game.world
    sect, cult = the_sects(world)
    commit(world, U.planting_events(world, 4))
    [plot] = P.plots_of(world, sect, ("spy",))
    return sect, cult, plot


def test_a_cult_plants_a_spy_among_a_hostile_sects_keepers_and_disciples(game, monkeypatch):
    world = game.world
    sect, cult, plot = spy_in(game, monkeypatch)
    spy = plot.data["plotter"]
    assert world.entity(spy).data["spy_of"] == cult and C.role_in(world, spy, sect) in ("keeper", "disciple")
    assert U.planting_events(world, 5) == []  # once a year
    assert (spy, cult) in M.motives(world, sect)  # a spy is a motive for murder
    assert check_plots(world) == []


def test_a_spys_year_may_steal_an_art_for_the_cult(game, monkeypatch):
    monkeypatch.setattr(U, "THEFT_CHANCE", 1.0)
    world = game.world
    sect, cult, plot = spy_in(game, monkeypatch)
    world.update_data(sect, arts=[4242])
    commit(world, P.season_events(world, 8))
    assert 4242 in world.entity(cult).data["arts"]


def test_a_spy_exposed_is_cast_out(game, monkeypatch):
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect, cult, plot = spy_in(game, monkeypatch)
    spy = plot.data["plotter"]
    seat = world.entity(sect).data["seat"]
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "night")
    commit(world, P.found_events(world, plot, "night", me, seat))  # the witness saw them outside the walls
    world.unrelate(spy, "located_in")
    world.relate(spy, seat, "located_in")
    commit(world, P.search_events(world, me, spy, seat))
    commit(world, P.accuse_events(world, me, spy, sect, seat))
    assert F.membership(world, spy, sect)[1]["status"] == "spy_exposed" and not world.entity(spy).data.get("spy_of")
    assert F.stance(world, sect, cult) == pytest.approx(-1.0)
    assert world.facts(predicate="spy_exposed", subject=spy)
    assert witness is not None and check_plots(world) == []


def test_a_cult_spy_declares_for_the_cults_puppet(game, monkeypatch):
    world = game.world
    sect, cult, plot = spy_in(game, monkeypatch)
    spy = plot.data["plotter"]
    monkeypatch.setattr(U, "PUPPET_CHANCE", 1.0)
    monkeypatch.setattr(U, "patrons", lambda world, faction: [cult])
    _, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    [puppet_plot] = P.plots_of(world, sect, ("puppet",))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["declared"][str(spy)] == puppet_plot.data["serves"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_puppets.py`
Expected: `ModuleNotFoundError: No module named 'systems.puppets'`.

- [ ] **Step 3: Write the new modules**

`systems/puppets.py`:
```python
"""Puppets and cult spies (phase 4h spec 5).

A hostile sect may back a claimant in a crisis with silver and a fighter (a `puppet` plot, its envoy at the
seat); a winning puppet puts the sect in the patron's pocket. A demonic cult may plant a spy among an
orthodox sect's keepers and disciples (a `spy` plot): in peace they steal arts, in a crisis they are a motive
for murder and a vote for the cult's puppet.
"""

import systems.claimants as C
import systems.plots as P
import systems.succession_crisis as SC
import systems.world_clock as world_clock
from systems import factions as F
from systems import founding
from systems.attitude import attitude
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.tournaments import alive, realm_of
from world.events import Event, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

HOSTILE = -0.5
PUPPET_CHANCE, PUPPET_REACH = 0.3, 3
GIFT = 0.2
POCKET_STANCE = 0.3
EXPOSED_LEAN, EXPOSED_STANCE = -0.5, -0.3
SPY_CHANCE, THEFT_CHANCE = 0.02, 0.1
SPY_STANCE = -0.2


def _stance(world, a: int, b: int) -> float:
    return F.stance(world, a, b)


# --- puppets (spec 5.1) --------------------------------------------------------------------------------------

def patrons(world, faction: int) -> list[int]:
    """Factions hostile to this one, within reach of its seat, that could back a puppet."""
    data = world.entity(faction).data
    home = data.get("home")
    out = []
    for other, value, _ in world.relations_from(faction, "stance"):
        o = world.entity(other)
        if value <= HOSTILE and not o.data.get("dissolved") and o.data.get("home") is not None and home is not None \
                and F.gap(home, o.data["home"]) <= PUPPET_REACH and C.staff(world, other, ("leader", "elder")):
            out.append(other)
    return sorted(out)


def puppet_events(world, occurrence, patron: int, claimant: int, key: str, plotter: int | None = None) -> list[Event]:
    """A puppet plot: its envoy at the seat (made on the spot unless given) and its two clues."""
    crisis, seat = SC.crisis_of(occurrence), occurrence.data["place"]
    envoy = plotter
    if envoy is None:
        envoy = founding.make_person(world, f"envoy:{key}", seat, occupation="wandering swordsman", age=35,
                                     realm="second-rate")
        world.relate(envoy, patron, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                     "secret": False})
    fighters = C.staff(world, patron, ("elder",)) if world.entity(patron).kind == "faction" else []
    lent = max(fighters, key=lambda p: (realm_of(world, p), -p)) if fighters else None
    clues = [P.clue("silver", envoy), P.clue("envoy", envoy)]
    return P.made_events(world, "puppet", key, envoy, crisis["faction"], seat, target=crisis["faction"],
                         patron=patron, serves=claimant, clues=clues,
                         extra={"occurrence": occurrence.id, "lent": lent, "gifted": []})


def _backed(world, occurrence) -> None:
    """A crisis begins: a hostile sect within reach may back a claimant (0.3)."""
    faction = SC.crisis_of(occurrence)["faction"]
    rng = rng_for(world.world_seed, f"puppet:{occurrence.id}")
    options = patrons(world, faction)
    crisis = SC.crisis_of(occurrence)
    claimants = [c["person"] for c in crisis["claimants"] if not world.entity(c["person"]).data.get("is_player")]
    if not options or not claimants or rng.random() >= PUPPET_CHANCE:
        return
    patron = rng.choice(options)
    heads = C.staff(world, patron, ("leader",))
    if heads:
        claimant = max(claimants, key=lambda p: (attitude(world, heads[0], p).score, -p))
    else:
        claimant = min(claimants, key=lambda p: (realm_of(world, p), p))
    commit(world, puppet_events(world, occurrence, patron, claimant, f"puppet:{occurrence.id}"))


@listen("plot_made")
def _lends(world, event, event_id: int) -> None:
    """The patron's fighter stands as the puppet's champion; the cult's spies declare for the cult's puppet."""
    d = event.data
    if d["type"] != "puppet":
        return
    plot = world.entity_by_seed(f"plot:{d['key']}")
    occurrence = world.entity(plot.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    champions = dict(crisis.get("champions", {}))
    if plot.data.get("lent") is not None and str(d["serves"]) not in champions:
        champions[str(d["serves"])] = plot.data["lent"]
    declared = dict(crisis.get("declared", {}))
    for spy in P.plots_of(world, crisis["faction"], ("spy",)):
        if spy.data["patron"] == d["patron"] and alive(world, spy.data["plotter"]):
            declared[str(spy.data["plotter"])] = d["serves"]
    world.update_data(occurrence.id, data={**crisis, "champions": champions, "declared": declared,
                                           "plots": crisis.get("plots", []) + [plot.id]})


@listen("crisis_phase")
def _silver(world, event, event_id: int) -> None:
    """At the mourning's end the puppet's camp spends the patron's silver: a gift-sway to each voter of rank 2+."""
    if event.data["phase"] != "canvass":
        return
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    for plot in P.plots_of(world, crisis["faction"], ("puppet",)):
        if plot.data.get("occurrence") != occurrence.id:
            continue
        puppet = str(plot.data["serves"])
        sways = {k: dict(v) for k, v in crisis.get("sways", {}).items()}
        gifted = []
        for voter in C.voters(world, crisis["faction"]):
            found = F.membership(world, voter, crisis["faction"])
            if voter == plot.data["serves"] or world.entity(voter).data.get("is_player") or not found or found[0] < 2:
                continue
            mine = sways.setdefault(str(voter), {})
            mine[puppet] = round(mine.get(puppet, 0.0) + GIFT, 3)
            gifted.append(voter)
        crisis = {**crisis, "sways": sways}
        world.update_data(plot.id, gifted=gifted)
    world.update_data(occurrence.id, data=crisis)


def gift_plot(world, player: int, npc: int):
    """The open puppet plot this voter took silver from, at the player's town."""
    here = world.targets(player, "located_in")
    for plot in [world.entity(p) for p in P.open_plots(world)]:
        if plot.data["type"] == "puppet" and npc in plot.data.get("gifted", []) \
                and P.unfound(plot, "silver", player) is not None \
                and here == [world.entity(plot.data["faction"]).data.get("seat")]:
            return plot
    return None


def envoy_plot(world, player: int, npc: int):
    """The open puppet plot whose envoy this is, if the player has not yet found them out."""
    for plot in [world.entity(p) for p in P.open_plots(world)]:
        if plot.data["type"] == "puppet" and plot.data["plotter"] == npc and P.unfound(plot, "envoy", player):
            return plot
    return None


def asked_events(world, player: int, npc: int, place: int, what: str) -> list[Event]:
    """Asking a voter about the gift they took, or a stranger where they come from."""
    plot = gift_plot(world, player, npc) if what == "silver" else envoy_plot(world, player, npc)
    return [Event("asked_about", (player, npc), place, {"what": what, "told": plot is not None})] + (
        P.found_events(world, plot, what, player, place) if plot is not None else [])


@listen("crisis_settled")
def _pocket(world, event, event_id: int) -> None:
    """A puppet who wins puts the sect in the patron's pocket (spec 5.1)."""
    for plot in P.plots_of(world, event.data["faction"], ("puppet",)):
        if plot.data["serves"] == event.data["winner"] and world.entity(plot.data["patron"]).kind == "faction":
            a, b = event.data["faction"], plot.data["patron"]
            world.relate(a, b, "stance", POCKET_STANCE)
            world.relate(b, a, "stance", POCKET_STANCE)
            world.update_data(a, pocket={"patron": b, "puppet": event.data["winner"]})


def in_pocket(world, a: int, b: int) -> bool:
    """Whether one of these factions is in the other's pocket, its puppet still leading."""
    for x, y in ((a, b), (b, a)):
        pocket = world.entity(x).data.get("pocket")
        if pocket and pocket["patron"] == y and C.role_in(world, pocket["puppet"], x) == "leader":
            return True
    return False


def _puppet_exposed(world, plot, exposer) -> list[Event]:
    return [Event("puppet_revealed", (plot.data["serves"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "faction": plot.data["faction"], "patron": plot.data["patron"]})]


@effect("puppet_revealed")
def _revealed(world, event) -> None:
    d = event.data
    puppet = event.actors[0]
    occurrence = SC.live(world, d["faction"])
    if occurrence is not None:
        crisis = SC.crisis_of(occurrence)
        sways = {k: dict(v) for k, v in crisis.get("sways", {}).items()}
        for voter in C.voters(world, d["faction"]):
            mine = sways.setdefault(str(voter), {})
            mine[str(puppet)] = round(mine.get(str(puppet), 0.0) + EXPOSED_LEAN, 3)  # a foreign creature
        world.update_data(occurrence.id, data={**crisis, "sways": sways})
    patron = d["patron"]
    if isinstance(patron, int) and world.entity(patron).kind == "faction":
        value = max(-1.0, _stance(world, d["faction"], patron) + EXPOSED_STANCE)
        world.relate(d["faction"], patron, "stance", value)
        world.relate(patron, d["faction"], "stance", value)
    if (world.entity(d["faction"]).data.get("pocket") or {}).get("puppet") == puppet:
        world.update_data(d["faction"], pocket=None)


P.EXPOSE_HOOKS["puppet"] = _puppet_exposed


# --- cult spies (spec 5.2) -----------------------------------------------------------------------------------

def spy_events(world, sect: int, cult: int, spy: int, key: str) -> list[Event]:
    seat = world.entity(sect).data.get("seat")
    present = sorted(p.id for p in people_at(world, seat) if p.id != spy and not p.data.get("is_player")
                     and alive(world, p.id)) if seat is not None else []
    rng = rng_for(world.world_seed, f"spy:{key}")
    clues = ([P.clue("night", spy, witness=rng.choice(present))] if present else []) + [P.clue("mark", spy, at="quarters")]
    return P.made_events(world, "spy", key, spy, sect, seat, target=sect, patron=cult, clues=clues)


@listen("plot_made")
def _spy_of(world, event, event_id: int) -> None:
    if event.data["type"] == "spy":
        world.update_data(event.data["plotter"], spy_of=event.data["patron"])


def planting_events(world, n: int) -> list[Event]:
    """Once a year each demonic cult may plant a spy in each orthodox sect it is hostile to (0.02)."""
    if n % 4 != C.NAMING_SEASON:
        return []
    factions = [f for f in world.entities("faction") if not f.data.get("dissolved")]
    cults = [f.id for f in factions if f.data.get("type") == "demonic_cult"]
    sects = [f.id for f in factions if f.data.get("type") == "orthodox_sect"]
    events = []
    for cult in cults:
        for sect in sects:
            if _stance(world, cult, sect) > HOSTILE:
                continue
            rng = rng_for(world.world_seed, f"spy:{cult}:{sect}:{n}")
            if rng.random() >= SPY_CHANCE:
                continue
            able = [p for p in C.staff(world, sect, ("keeper", "disciple")) if not world.entity(p).data.get("is_player")
                    and not world.entity(p).data.get("spy_of")]
            if able:
                events += spy_events(world, sect, cult, rng.choice(sorted(able)), f"spy:{cult}:{sect}:{n}")
    return events


def _spy_year(world, plot, n: int, rng) -> list[Event]:
    """In peacetime a spy may steal one of the sect's arts for the cult (spec 5.2)."""
    if n % 4 != C.NAMING_SEASON or rng.random() >= THEFT_CHANCE:
        return []
    arts = [a for a in world.entity(plot.data["faction"]).data.get("arts", [])
            if a not in world.entity(plot.data["patron"]).data.get("arts", [])]
    if not arts or world.entity(plot.data["patron"]).kind != "faction":
        return []
    return [Event("art_stolen", (plot.data["plotter"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "cult": plot.data["patron"], "art": rng.choice(sorted(arts))})]


@effect("art_stolen")
def _stolen(world, event) -> None:
    cult = event.data["cult"]
    world.update_data(cult, arts=list(world.entity(cult).data.get("arts", [])) + [event.data["art"]])


def _spy_exposed(world, plot, exposer) -> list[Event]:
    return [Event("spy_revealed", (plot.data["plotter"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "faction": plot.data["faction"], "cult": plot.data["patron"]})]


@effect("spy_revealed")
def _spy_revealed(world, event) -> None:
    spy, d = event.actors[0], event.data
    if F.membership(world, spy, d["faction"]):
        set_membership(world, spy, d["faction"], status="spy_exposed")
    world.update_data(spy, spy_of=None)
    if isinstance(d["cult"], int) and world.entity(d["cult"]).kind == "faction":
        value = max(-1.0, _stance(world, d["faction"], d["cult"]) + SPY_STANCE)
        world.relate(d["faction"], d["cult"], "stance", value)
        world.relate(d["cult"], d["faction"], "stance", value)


@listen("spy_revealed")
def _spy_news(world, event, event_id: int) -> None:
    spy = event.actors[0]
    variant = make_variant("spy_exposed", spy, event.data["faction"], place=place_name(world, event.place))
    record_fact(world, spy, "spy_exposed", event.data["faction"], place=event.place, source_event=event_id,
                weight=2.5, variant=variant)


P.EXPOSE_HOOKS["spy"] = _spy_exposed
P.BEGUN_HOOKS.append(_backed)
P.SEASON_HOOKS["spy"] = _spy_year
world_clock.SEASON_HOOKS.append(planting_events)
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4h_task2.py`:
```python
"""Phase 4h, Task 2: puppets and spies in the clock, no war on a patron, the lent fighter in strife, the spy rule"""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def still(path: str) -> None:
    """A 4g test's fixture stills 4h's intrigue: they test the crisis alone."""
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    anchor = '    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)\n'
    if text.count(anchor) != 1:
        raise SystemExit(f"{path}: no single calm fixture")
    text = text.replace(anchor, anchor + "    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises\n")
    i = text.index("\n\n\n@pytest.fixture")
    text = text[:i] + "\nfrom tests.intrigue import still" + text[i:]
    file.write_text(text, encoding="utf-8", newline="\n")


edit('systems/world_clock.py', r'''import systems.murder  # noqa: E402,F401  phase 4h: plots, and the poisoned master''', r'''import systems.murder  # noqa: E402,F401  phase 4h: plots, and the poisoned master
import systems.puppets  # noqa: E402,F401  phase 4h: puppets and cult spies''')
edit('systems/wars.py', r'''            value = known.get((a, b), 0.0)
            if value > HOSTILE:
                continue''', r'''            value = known.get((a, b), 0.0)
            if value > HOSTILE:
                continue
            from systems.puppets import in_pocket  # phase 4h: a puppet's sect does not war on its patron
            if in_pocket(world, a, b):
                continue''')
edit('systems/schism.py', r'''    backing, _ = C.camps(world, crisis)
    gone = set(crisis["strife"].get("gone", []))
    return {side: [p for p in backing.get(side, [side]) if p not in gone and alive(world, p)]
            for side in (crisis["strife"]["a"], crisis["strife"]["b"])}''', r'''    backing, _ = C.camps(world, crisis)
    gone = set(crisis["strife"].get("gone", []))
    from systems.plots import plots_of  # phase 4h: a patron's lent fighter stands in the puppet's camp
    lent = {p.data["serves"]: p.data.get("lent") for p in plots_of(world, crisis["faction"], ("puppet",))}
    return {side: [p for p in backing.get(side, [side]) + ([lent[side]] if lent.get(side) else [])
                   if p not in gone and alive(world, p)]
            for side in (crisis["strife"]["a"], crisis["strife"]["b"])}''')
edit('debug/invariants.py', r'''    for pid in listed:
        if world.entity(pid) is None or world.entity(pid).kind != "plot":''', r'''        if d["type"] == "spy" and d["state"] == "open" and world.entity(d["plotter"]) is not None \
                and not world.entity(d["plotter"]).data.get("dead"):
            found = world.relations_from(d["plotter"], "member_of")
            if not any(f == d["faction"] and data.get("status", "member") == "member" for f, _, data in found):
                out.append(f"{plot.name}: the spy is no longer of the sect they spy on")
    for pid in listed:
        if world.entity(pid) is None or world.entity(pid).kind != "plot":''')
print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4h_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_puppets.py tests/test_plots.py tests/test_schism.py`
Expected: `22 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: puppets and spies - a hostile sect's silver and fighter, the pocket, cult spies planted, stealing, cast out

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: The forged will, the frame, exile and the return

A cunning claimant may forge the will at the mourning's end (the seal and the scribe betray it; exposed, the will is `forged` and proves nothing), or frame a rival at the canvass's start: a false crime the sect believes, the rival expelled and sent 3-6 regions away until a seeded season 12-40 on. A framed heir returns to a live crisis or starts their own (cause `return`), with `the truth` if the frame was exposed meanwhile. A framed player may come back after 4 seasons to demand the seat.

**Files:**
- Create: `systems/frames.py`
- Create: `tests/test_frames.py`
- Modify (by `.patches/4h_task3.py`): `systems/world_clock.py`, `systems/claimants.py`, `narrate/crisis_text.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Task 1: `P.made_events`, `P.clue`, `P.EXPOSE_HOOKS`, `P.found_events`, `P.QUARTERS`; 4g's `SC.begin_events`, `crisis_phase`, the will in the crisis's data, `C.PROOF_LEAN`.
- Produces:
  - `frames` (R): `FORGE_CHANCE`, `FRAME_CHANCE`, `SEAL_BASE`, `SEAL_PER_WIT`, `EXILE_REACH`, `RETURN_SEASONS`, `PLAYER_RETURN`, `CRIMES`, `TRUTH`; `exiles(world)`, `forgery_events(world, occurrence, forger, names, key)`, `examine_will_block/seal_chance/examine_will_events(world, occurrence, player)`, `frame_events(world, occurrence, framer, framed, key, rng)`, `ask_plot(world, player, npc, kind)`, `asked_events(world, player, npc, place, kind)`, `return_events(world, person, n)`, `returns_due(world, n)`, `player_return_block(world, player, town)`; events `will_examined`, `forgery_revealed`, `framed_out`, `frame_revealed`, `heir_returned`, `claim_joined`, `exile_ended`; person data `framed`; meta `exiles`.
  - `C`: the proof `truth`; `crisis_text`: the claim kind `returned` and the cause `return`.

- [ ] **Step 1: Write the failing tests**

`tests/test_frames.py`:
```python
import random

import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.frames as R
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.succession_crisis as SC
import systems.testament as T
from debug.invariants import check_plots
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems.creation import CreationChoice
from tests.test_crisis_play import crisis_at_seat, to_stage
from world.events import commit
from world.gen.materialize import region_of
from tests.intrigue import still


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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(M, "MURDER_CHANCE", 0.0)
    monkeypatch.setattr(U, "PUPPET_CHANCE", 0.0)
    monkeypatch.setattr(R, "FORGE_CHANCE", 0.0)
    monkeypatch.setattr(R, "FRAME_CHANCE", 0.0)


def cunning_crisis(game, monkeypatch, forge=0.0, frame=0.0):
    """The chief disciple against a cunning elder; at the canvass's start the elder may forge or frame."""
    monkeypatch.setattr(R, "FORGE_CHANCE", forge)
    monkeypatch.setattr(R, "FRAME_CHANCE", frame)
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(proud, traits=["cunning"])
    to_stage(world, occurrence, seat, "announced")
    return sect, seat, keeper, proud, occurrence


def test_a_cunning_claimant_forges_the_will(game, monkeypatch):
    world = game.world
    sect, seat, keeper, forger, occurrence = cunning_crisis(game, monkeypatch, forge=1.0)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    [plot] = P.plots_of(world, sect, ("forgery",))
    assert crisis["will"]["state"] == "read" and crisis["will"]["names"] == forger
    assert crisis["will"]["forged"] == plot.id and plot.id in crisis["plots"]
    assert "will" in C.proofs(world, crisis, SC.claimant(crisis, forger))
    assert check_plots(world) == []


def test_the_seal_and_the_scribe_expose_a_forgery(game, monkeypatch):
    monkeypatch.setattr(R, "seal_chance", lambda world, player: 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, forger, occurrence = cunning_crisis(game, monkeypatch, forge=1.0)
    [plot] = P.plots_of(world, sect, ("forgery",))
    occurrence = world.entity(occurrence.id)
    assert R.examine_will_block(world, occurrence, me) is None
    commit(world, R.examine_will_events(world, occurrence, me))
    assert R.examine_will_block(world, world.entity(occurrence.id), me) is not None  # once a crisis
    scribe = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "scribe")
    commit(world, R.asked_events(world, me, scribe, seat, "scribe"))
    commit(world, P.accuse_events(world, me, forger, sect, seat))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["will"]["state"] == "forged" and SC.claimant(crisis, forger) is None
    assert check_plots(world) == []


def test_a_framed_claimant_is_cast_out_and_waits_in_exile(game, monkeypatch):
    world = game.world
    sect, seat, keeper, framer, occurrence = cunning_crisis(game, monkeypatch, frame=1.0)
    [plot] = P.plots_of(world, sect, ("frame",))
    framed = plot.data["target"]
    assert framed == keeper and plot.data["plotter"] == framer
    assert F.membership(world, framed, sect)[1]["status"] == "expelled"
    assert SC.claimant(SC.crisis_of(world.entity(occurrence.id)), framed) is None
    home, there = region_of(world, seat), region_of(world, world.targets(framed, "located_in")[0])
    assert max(abs(home.data["x"] - there.data["x"]), abs(home.data["y"] - there.data["y"])) >= R.EXILE_REACH[0]
    exile = world.entity(framed).data["framed"]
    assert exile["plot"] == plot.id and exile["returns_at"] - exile["since"] >= R.RETURN_SEASONS[0]
    assert framed in R.exiles(world)
    [crime] = [f for f in world.facts(subject=framed) if f.predicate in R.CRIMES]
    assert not crime.is_true
    assert check_plots(world) == []


def test_the_false_witness_can_be_made_to_tell(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, framer, occurrence = cunning_crisis(game, monkeypatch, frame=1.0)
    [plot] = P.plots_of(world, sect, ("frame",))
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "false_witness")
    commit(world, R.asked_events(world, me, witness, seat, "false_witness"))
    assert P.suspicions(world, me, sect) == {framer: ["false_witness"]}


def test_the_framed_come_home_to_a_live_crisis_or_start_their_own(game, monkeypatch):
    world = game.world
    sect, seat, keeper, framer, occurrence = cunning_crisis(game, monkeypatch, frame=1.0)
    [plot] = P.plots_of(world, sect, ("frame",))
    n = lives.current_season(world)
    world.update_data(keeper, framed={**world.entity(keeper).data["framed"], "returns_at": n})
    commit(world, R.returns_due(world, n))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert {"person": keeper, "kind": "returned", "plot": plot.id} in crisis["claimants"]
    assert world.targets(keeper, "located_in") == [seat] and keeper not in R.exiles(world)
    plot = world.entity(plot.id)
    assert keeper in plot.data["known_by"]  # they know who framed them, and bring the planted evidence
    assert any(c["kind"] == "planted" and keeper in c["found_by"] for c in plot.data["clues"])


def test_an_heir_whose_frame_was_exposed_returns_with_the_truth(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, framer, occurrence = cunning_crisis(game, monkeypatch, frame=1.0)
    [plot] = P.plots_of(world, sect, ("frame",))
    commit(world, P.exposed_events(world, plot, me, seat))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    world.update_data(occurrence.id, data={**crisis, "sways": {str(v): {str(framer): 5.0}
                                                               for v in C.voters(world, sect)}})
    to_stage(world, occurrence, seat, "active")  # the crisis is settled while they are away
    world.set_time(world.entity(occurrence.id).data["over_at"] + lives.SEASON)  # and a season on
    n = lives.current_season(world)
    world.update_data(keeper, framed={**world.entity(keeper).data["framed"], "returns_at": n})
    commit(world, R.returns_due(world, n))
    live = SC.live(world, sect)
    assert live is not None and SC.crisis_of(live)["cause"] == "return"
    crisis = SC.crisis_of(live)
    returned = SC.claimant(crisis, keeper)
    assert returned["kind"] == "returned" and "truth" in C.proofs(world, crisis, returned)


def test_a_framed_player_may_come_back_to_demand_the_seat(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    world.update_data(proud, traits=["cunning"])
    commit(world, R.frame_events(world, world.entity(occurrence.id), proud, me, "frame:test", random.Random(1)))
    assert F.membership(world, me, sect)[1]["status"] == "expelled"
    assert world.targets(me, "located_in") == [seat]  # the player is not carried off: they walk out themselves
    assert R.player_return_block(world, me, seat) == "It is too soon: the elders' anger is fresh."
    since = world.entity(me).data["framed"]["since"]
    world.update_data(me, framed={**world.entity(me).data["framed"], "since": since - R.PLAYER_RETURN})
    assert R.player_return_block(world, me, seat) is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_frames.py`
Expected: `ModuleNotFoundError: No module named 'systems.frames'`.

- [ ] **Step 3: Write the new modules**

`systems/frames.py`:
```python
"""The forged will, the framed heir, and the return (phase 4h spec 6).

A cunning claimant may forge the late master's will, or frame a rival with a false crime: the framed are
cast out and live on in exile, and years later come back to demand the seat. Who waits in exile is kept in
the meta row `exiles`, so the season's check never reads every person.
"""

import systems.claimants as C
import systems.lives as lives
import systems.plots as P
import systems.succession_crisis as SC
import systems.world_clock as world_clock
from systems import factions as F
from systems import founding
from systems.bodies import load_body
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.tournaments import alive
from world.events import Event, commit, effect, listen
from world.gen.materialize import ensure_town
from world.gen.region import region_spec
from world.seed import rng_for

FORGE_CHANCE, FRAME_CHANCE = 0.3, 0.15
SEAL_BASE, SEAL_PER_WIT = 0.3, 0.1
EXILE_REACH = (3, 6)
RETURN_SEASONS = (12, 40)
PLAYER_RETURN = 4  # seasons before a framed player may come back to demand the seat
CRIMES = ("stole_art", "killed_disciple")
TRUTH = 0.5


def _cunning(world, person: int) -> bool:
    return "cunning" in world.entity(person).data.get("traits", ())


def exiles(world) -> list[int]:
    return list(world.get_meta("exiles", []))


# --- the forged will (spec 6.1) -------------------------------------------------------------------------------

def forgery_events(world, occurrence, forger: int, names: int, key: str) -> list[Event]:
    """A forged will read out, naming `names`; its seal and its scribe are the clues."""
    seat = occurrence.data["place"]
    scribe = founding.make_person(world, f"scribe:{key}", seat, occupation="scribe", age=50)
    clues = [P.clue("seal", forger), P.clue("scribe", forger, witness=scribe)]
    return P.made_events(world, "forgery", key, forger, SC.crisis_of(occurrence)["faction"], seat,
                         target=SC.crisis_of(occurrence)["faction"], serves=names, clues=clues,
                         extra={"occurrence": occurrence.id})


@listen("plot_made")
def _forged_will_read(world, event, event_id: int) -> None:
    d = event.data
    if d["type"] != "forgery" or d["extra"].get("occurrence") is None:
        return  # a forgery made outside a crisis's canvass reads no will out
    plot = world.entity_by_seed(f"plot:{d['key']}")
    occurrence = world.entity(plot.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "will": {"state": "read", "names": d["serves"], "holder": None,
                                                              "forged": plot.id},
                                           "plots": crisis.get("plots", []) + [plot.id]})


def examine_will_block(world, occurrence, player: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if (crisis.get("will") or {}).get("state") != "read":
        return "No will has been read out."
    if player in crisis.get("will_examined", []):
        return "You have studied the will as closely as the elders allow."
    return None


def seal_chance(world, player: int) -> float:
    wit = load_body(world, player).physique["comprehension"] if world.entity(player).data.get("is_player") else 5
    return max(0.0, SEAL_BASE + SEAL_PER_WIT * (wit - 5))


def examine_will_events(world, occurrence, player: int) -> list[Event]:
    crisis, place = SC.crisis_of(occurrence), occurrence.data["place"]
    plot = P.plot_of(world, (crisis.get("will") or {}).get("forged"))
    rng = rng_for(world.world_seed, f"frames:{occurrence.id}:seal:{player}")
    found = plot is not None and plot.data["state"] == "open" and rng.random() < seal_chance(world, player)
    return [Event("will_examined", (player,), place, {"occurrence": occurrence.id, "found": found})] + (
        P.found_events(world, plot, "seal", player, place) if found else [])


@effect("will_examined")
def _will_examined(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "will_examined": crisis.get("will_examined", []) +
                                           [event.actors[0]]})


def _forgery_exposed(world, plot, exposer) -> list[Event]:
    return [Event("forgery_revealed", (plot.data["plotter"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "occurrence": plot.data.get("occurrence")})]


@effect("forgery_revealed")
def _forgery_revealed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"]) if event.data.get("occurrence") else None
    if occurrence is not None:
        crisis = SC.crisis_of(occurrence)
        if (crisis.get("will") or {}).get("forged") == event.data["plot"]:
            world.update_data(occurrence.id, data={**crisis, "will": {"state": "forged", "names": None,
                                                                      "holder": None}})


# --- framing (spec 6.2) ----------------------------------------------------------------------------------------

def frame_events(world, occurrence, framer: int, framed: int, key: str, rng) -> list[Event]:
    """A false crime pinned on a claimant: the planted evidence (in the framed's quarters) and a false witness."""
    seat = occurrence.data["place"]
    witness = founding.make_person(world, f"witness:{key}", seat, occupation="servant", age=30)
    clues = [P.clue("planted", framer, at="quarters_of", owner=framed),
             P.clue("false_witness", framer, witness=witness)]
    return P.made_events(world, "frame", key, framer, SC.crisis_of(occurrence)["faction"], seat, target=framed,
                         clues=clues, extra={"occurrence": occurrence.id, "crime": rng.choice(CRIMES)})


@listen("plot_made")
def _cast_out(world, event, event_id: int) -> None:
    """The sect believes the crime: the framed are expelled, struck from the claims, and leave (spec 6.2)."""
    d = event.data
    if d["type"] != "frame" or d["extra"].get("failed"):
        return  # a frame that did not take casts no one out (4h spec 8)
    plot = world.entity_by_seed(f"plot:{d['key']}")
    framed, faction = d["target"], d["faction"]
    commit(world, [Event("framed_out", (framed, d["plotter"]), event.place,
                         {"plot": plot.id, "faction": faction, "crime": plot.data["crime"],
                          "occurrence": plot.data["occurrence"]})])


@effect("framed_out")
def _framed_out(world, event) -> None:
    framed, d = event.actors[0], event.data
    if F.membership(world, framed, d["faction"]):
        set_membership(world, framed, d["faction"], status="expelled")
    occurrence = world.entity(d["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "claimants": [c for c in crisis["claimants"]
                                                                   if c["person"] != framed],
                                           "plots": crisis.get("plots", []) + [d["plot"]]})
    n = lives.current_season(world)
    rng = rng_for(world.world_seed, f"frames:{d['plot']}:exile")
    if world.entity(framed).data.get("is_player"):
        world.update_data(framed, framed={"plot": d["plot"], "faction": d["faction"], "since": n})
        return
    home = world.entity(world.entity(d["faction"]).data["seat"]).data
    dx, dy = rng.randint(*EXILE_REACH) * rng.choice((-1, 1)), rng.randint(*EXILE_REACH) * rng.choice((-1, 1))
    x, y = home["x"] + dx, home["y"] + dy
    town = ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))
    world.unrelate(framed, "located_in")
    world.relate(framed, town, "located_in")
    world.update_data(framed, framed={"plot": d["plot"], "faction": d["faction"], "since": n,
                                      "returns_at": n + rng.randint(*RETURN_SEASONS)})
    world.set_meta("exiles", exiles(world) + [framed])


@listen("framed_out")
def _crime_told(world, event, event_id: int) -> None:
    """The false crime is told as any deed is: believed, and false (`is_true = False`)."""
    framed, d = event.actors[0], event.data
    variant = make_variant(d["crime"], framed, d["faction"], place=place_name(world, event.place))
    record_fact(world, framed, d["crime"], d["faction"], place=event.place, source_event=event_id, weight=2.0,
                variant=variant, is_true=False, extra={"liar": event.actors[1]})  # a lie: the framer told it


def ask_plot(world, player: int, npc: int, kind: str):
    """The open plot whose `kind` clue this person holds (a scribe, a false witness), unfound by the player."""
    for plot in [world.entity(p) for p in P.open_plots(world)]:
        for c in plot.data["clues"]:
            if c["kind"] == kind and c.get("witness") == npc and player not in c["found_by"] and not c.get("lost"):
                return plot
    return None


def asked_events(world, player: int, npc: int, place: int, kind: str) -> list[Event]:
    """Asking a scribe about the will they wrote, or a witness about the crime they swore to."""
    plot = ask_plot(world, player, npc, kind)
    return [Event("asked_about", (player, npc), place, {"what": kind, "told": plot is not None})] + (
        P.found_events(world, plot, kind, player, place) if plot is not None else [])


def _frame_exposed(world, plot, exposer) -> list[Event]:
    return [Event("frame_revealed", (plot.data["target"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "faction": plot.data["faction"], "framer": plot.data["plotter"]})]


@effect("frame_revealed")
def _frame_revealed(world, event) -> None:
    """The truth clears the framed: a player cast out is taken back; an exile will come home with it (spec 6.3)."""
    framed, d = event.actors[0], event.data
    if world.entity(framed).data.get("is_player") and F.membership(world, framed, d["faction"]):
        set_membership(world, framed, d["faction"], status="member")
        world.update_data(framed, framed=None)


@listen("frame_revealed")
def _cleared(world, event, event_id: int) -> None:
    framed = event.actors[0]
    variant = make_variant("cleared", framed, event.data["faction"], place=place_name(world, event.place))
    record_fact(world, framed, "cleared", event.data["faction"], place=event.place, source_event=event_id,
                weight=2.0, variant=variant)


# --- the crisis's canvass: forgers and framers act (spec 6.1, 6.2) ------------------------------------------

@listen("crisis_phase")
def _schemes(world, event, event_id: int) -> None:
    if event.data["phase"] != "canvass":
        return
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    rng = rng_for(world.world_seed, f"frames:{occurrence.id}:canvass")
    cunning = [c["person"] for c in SC.standing_claimants(world, crisis) if _cunning(world, c["person"])
               and not world.entity(c["person"]).data.get("is_player")]
    will = crisis.get("will") or {}
    if cunning and will.get("state") != "read" and rng.random() < FORGE_CHANCE:
        forger = cunning[0]
        commit(world, forgery_events(world, occurrence, forger, forger, f"forgery:{occurrence.id}"))
        occurrence = world.entity(occurrence.id)
        crisis = SC.crisis_of(occurrence)
    if cunning and rng.random() < FRAME_CHANCE:
        framer = cunning[-1]
        rivals = [c["person"] for c in SC.standing_claimants(world, crisis) if c["person"] != framer]
        if rivals:
            commit(world, frame_events(world, occurrence, framer, rng.choice(rivals), f"frame:{occurrence.id}", rng))


# --- the return (spec 6.3) ---------------------------------------------------------------------------------

def return_events(world, person: int, n: int) -> list[Event]:
    """The framed come back to demand the seat: a new crisis, the returned heir against whoever holds it."""
    framed = world.entity(person).data.get("framed") or {}
    faction = framed.get("faction")
    if faction is None or world.entity(faction).data.get("dissolved"):
        return []
    seat = world.entity(faction).data["seat"]
    events = [Event("heir_returned", (person,), seat, {"faction": faction, "plot": framed["plot"]})]
    claim = {"person": person, "kind": "returned", "plot": framed["plot"]}
    occurrence = SC.live(world, faction)
    if occurrence is not None:
        return events + [Event("claim_joined", (person,), seat, {"occurrence": occurrence.id, "claim": claim})]
    holders = [{"person": h, "kind": "elder"} for h in C.staff(world, faction, ("leader",))]
    if not holders:
        return events
    return events + SC.begin_events(world, faction, n, "return", [claim] + holders, None,
                                    force=world.entity(person).data.get("is_player", False))


@effect("heir_returned")
def _returned(world, event) -> None:
    person, d = event.actors[0], event.data
    seat = world.entity(d["faction"]).data["seat"]
    world.unrelate(person, "located_in")
    world.relate(person, seat, "located_in")
    world.update_data(person, framed=None)
    world.set_meta("exiles", [p for p in exiles(world) if p != person])
    plot = P.plot_of(world, d["plot"])
    if plot is not None and plot.data["state"] == "open":  # they bring the planted evidence, and the truth
        clues = [dict(c, found_by=c["found_by"] + [person]) if c["kind"] == "planted" and person not in c["found_by"]
                 else c for c in plot.data["clues"]]
        world.update_data(plot.id, clues=clues)
        P.learn(world, person, world.entity(plot.id), 1.0, "witness")


@effect("claim_joined")
def _joined(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "claimants": crisis["claimants"] + [event.data["claim"]]})


def returns_due(world, n: int) -> list[Event]:
    """Each season: exiles whose time has come, alive and free, come home (spec 6.3)."""
    events = []
    for person in exiles(world):
        entity = world.entity(person)
        framed = entity.data.get("framed") or {}
        if not alive(world, person) or entity.data.get("sealed_in"):
            if entity.data.get("dead"):
                events.append(Event("exile_ended", (), None, {"person": person}))
            continue
        if framed.get("returns_at") is not None and n >= framed["returns_at"]:
            events += return_events(world, person, n)
    return events


@effect("exile_ended")
def _exile_ended(world, event) -> None:
    world.set_meta("exiles", [p for p in exiles(world) if p != event.data["person"]])


def player_return_block(world, player: int, town: int) -> str | None:
    framed = world.entity(player).data.get("framed") or {}
    if not framed:
        return "You were never cast out."
    if world.entity(framed["faction"]).data.get("seat") != town:
        return "The seat you were cast out of is elsewhere."
    if lives.current_season(world) - framed["since"] < PLAYER_RETURN:
        return "It is too soon: the elders' anger is fresh."
    return None


P.EXPOSE_HOOKS["forgery"] = _forgery_exposed
P.EXPOSE_HOOKS["frame"] = _frame_exposed
world_clock.SEASON_HOOKS.append(returns_due)
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4h_task3.py`:
```python
"""Phase 4h, Task 3: frames in the clock, the truth as a proof, the returned in words, the exiles rule"""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def still(path: str) -> None:
    """A 4g test's fixture stills 4h's intrigue: they test the crisis alone."""
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    anchor = '    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)\n'
    if text.count(anchor) != 1:
        raise SystemExit(f"{path}: no single calm fixture")
    text = text.replace(anchor, anchor + "    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises\n")
    i = text.index("\n\n\n@pytest.fixture")
    text = text[:i] + "\nfrom tests.intrigue import still" + text[i:]
    file.write_text(text, encoding="utf-8", newline="\n")


edit('systems/world_clock.py', r'''import systems.puppets  # noqa: E402,F401  phase 4h: puppets and cult spies''', r'''import systems.puppets  # noqa: E402,F401  phase 4h: puppets and cult spies
import systems.frames  # noqa: E402,F401  phase 4h: forged wills, framed heirs and their return''')
edit('systems/claimants.py', r'''PROOF_LEAN = {"chief": 0.2, "blood": 0.3, "will": 0.5, "transmission": 0.4, "token": 0.3}  # blood: in clans only''', r'''PROOF_LEAN = {"chief": 0.2, "blood": 0.3, "will": 0.5, "transmission": 0.4, "token": 0.3,  # blood: in clans only
              "truth": 0.5}  # 4h: a returned heir whose frame was exposed''')
edit('systems/claimants.py', r'''    token = crisis.get("token")
    if token is not None and person in world.sources(token, "owns"):
        found.append("token")
    return found''', r'''    token = crisis.get("token")
    if token is not None and person in world.sources(token, "owns"):
        found.append("token")
    plot = world.entity(claimant["plot"]) if claimant.get("plot") is not None else None
    if claimant["kind"] == "returned" and plot is not None and plot.data.get("state") == "exposed":
        found.append("truth")
    return found''')
edit('narrate/crisis_text.py', r'''              "grand_elder": "the Grand Elder, down from seclusion", "regent": "a regent", "player": "a claimant"}''', r'''              "grand_elder": "the Grand Elder, down from seclusion", "regent": "a regent", "player": "a claimant",
              "returned": "the heir cast out, come back", "outsider": "an outsider named heir"}''')
edit('debug/invariants.py', r'''    for pid in listed:
        if world.entity(pid) is None or world.entity(pid).kind != "plot":''', r'''    import systems.frames as R
    for person in R.exiles(world):
        if not (world.entity(person).data.get("framed") or {}).get("returns_at"):
            out.append(f"{world.entity(person).name} waits in exile with no return")
    for pid in listed:
        if world.entity(pid) is None or world.entity(pid).kind != "plot":''')
print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4h_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_frames.py tests/test_plots.py`
Expected: `17 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: forgery and frames - a forged will's seal and scribe, a rival framed and exiled, the return years later

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: The new ways to legitimacy

A great sect's supreme art (made once, taught to a chief disciple of a year's standing, its manual maybe left in the late master's rooms: +0.6); the founder's test (passing settles the seat, failing strikes the claim and may kill: ruling 5); a claimant wed into the master's line (+0.3); an arbiter for a contest with no majority, whom a proud loser may defy; and a master with no chief disciple naming a respected outsider (whom the voters lean against).

**Files:**
- Create: `systems/legitimacy.py`
- Create: `tests/test_legitimacy.py`
- Modify (by `.patches/4h_task4.py`): `systems/world_clock.py`, `systems/claimants.py`, `systems/succession_crisis.py`, `systems/mortality.py`, `narrate/crisis_text.py`, `systems/testament.py`

**Interfaces:**
- Consumes: Tasks 1-3: `P.BEGUN_HOOKS`; 4g's `SC.settle_events`, `SC.decide_events`, `crisis_phase`, `named_chief`, `chambers_searched`, `C.PROOF_LEAN`, `C.proofs`, `T.at_mourning`; 4b's `married` bond; `mortality.death_events`.
- Produces:
  - `legitimacy` (L): `ART_KNOWN`, `HEIR_LEARNS`, `MANUAL_CHANCE`, `MANUAL_COMPLETENESS`, `MANUAL_FIND`, `TEST_BASE`, `TEST_PER_REALM`, `TEST_PER_WIT`, `TEST_BOUNDS`, `TEST_DEATH`, `NPC_TRY`, `MARRY_CHANCE`, `ARBITER_CHANCE`, `DEFY_CHANCE`, `OUTSIDER_CHANCE`, `OUTSIDER_LEAN`; `great`, `supreme_art(world, f) -> int`, `art_known(world, person, f) -> float`, `teaching_events(world, n)`, `test_chance(world, person)`, `test_block/test_events(world, occurrence, person)`, `married_line(world, crisis, person)`, `arbiter_of(world, f)`, `verdict(world, crisis, standing)`, `arbitration_events(world, occurrence, standing, ranked)`, `outsider_for(world, f, leader)`; events `art_taught`, `manual_found`, `founder_passed`, `founder_failed`, `wed_for_seat`; faction data `supreme_art`, `art_manual`, `heir_since`, `outsider`.
  - `testament.set_realm(world, person, index)`; `mortality` cause `founder_test`; `C` proofs `supreme_art`, `married_line`, the lean `OUTSIDER_LEAN`.

- [ ] **Step 1: Write the failing tests**

`tests/test_legitimacy.py`:
```python
import pytest

import systems.claimants as C
import systems.crisis_play as CP
import systems.encounters as encounters
import systems.legitimacy as L
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from systems.techniques import GRADE_MULT
from tests.test_crisis_play import crisis_at_seat, to_stage
from tests.intrigue import still
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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(L, "MANUAL_CHANCE", 0.0)


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def test_the_supreme_art_is_made_once_and_taught_to_a_chief_disciple_of_a_years_standing(game):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    art = L.supreme_art(world, sect)
    assert L.supreme_art(world, sect) == art and world.entity(art).data["grade"] == len(GRADE_MULT)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    since = world.entity(sect).data["heir_since"]
    n = since + L.HEIR_LEARNS + (4 - (since + L.HEIR_LEARNS) % 4) % 4
    commit(world, L.teaching_events(world, n))
    assert L.art_known(world, keeper, sect) == L.ART_KNOWN
    crisis = {"faction": sect, "claimants": [{"person": keeper, "kind": "chief"}], "leader": None}
    assert "supreme_art" in C.proofs(world, crisis, crisis["claimants"][0])


def test_a_manual_of_the_art_may_lie_in_the_late_masters_rooms(game, monkeypatch):
    monkeypatch.setattr(L, "MANUAL_CHANCE", 1.0)
    monkeypatch.setattr(L, "MANUAL_FIND", 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    manual = world.entity(sect).data["art_manual"]
    assert world.sources(manual, "owns") == [sect]  # the sect holds it until someone finds it
    to_stage(world, occurrence, seat, "announced")
    commit(world, CP.search_events(world, world.entity(occurrence.id), me))
    assert world.sources(manual, "owns") == [me] and world.entity(sect).data["art_manual"] is None


def test_passing_the_founders_test_takes_the_seat(game, monkeypatch):
    monkeypatch.setattr(L, "test_chance", lambda world, person: 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    occurrence = world.entity(occurrence.id)
    assert L.test_block(world, occurrence, me) is None
    commit(world, L.test_events(world, occurrence, me))
    assert C.role_in(world, me, sect) == "leader"
    assert SC.crisis_of(world.entity(occurrence.id))["outcome"]["how"] == "founder"


def test_failing_the_founders_test_costs_the_claim_and_can_cost_a_life(game, monkeypatch):
    monkeypatch.setattr(L, "test_chance", lambda world, person: 0.0)
    monkeypatch.setattr(L, "TEST_DEATH", 0.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    commit(world, L.test_events(world, world.entity(occurrence.id), me))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert SC.claimant(crisis, me) is None and me in crisis["tested"]
    from systems.bodies import load_body
    assert any(i.cause == "the founder's test" for i in load_body(world, me).injuries)
    monkeypatch.setattr(L, "TEST_DEATH", 1.0)
    before = world.entity(proud).data["realm"]
    commit(world, L.test_events(world, world.entity(occurrence.id), proud))
    assert world.entity(proud).data.get("dead")
    assert before


def test_an_ambitious_npc_may_try_the_test_in_the_mourning(game, monkeypatch):
    monkeypatch.setattr(L, "NPC_TRY", 1.0)
    monkeypatch.setattr(L, "test_chance", lambda world, person: 1.0)
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    [leader] = staff(world, sect, seat, "leader")  # the heralds' day came with the crisis: the mourning's work
    assert C.ambitious(world, leader) and world.entity(sect).data["history"][-1]["how"] == "founder"


def test_a_claimant_may_marry_into_the_late_masters_line(game, monkeypatch):
    monkeypatch.setattr(L, "MARRY_CHANCE", 1.0)
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [leader] = staff(world, sect, seat, "leader")
    daughter = founding.make_person(world, "test:daughter", seat, occupation="wandering swordsman", age=22)
    world.relate(leader, daughter, "kin_of", 0, {"role": "child"})
    world.relate(daughter, leader, "kin_of", 0, {"role": "parent"})
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    import systems.sky as sky
    sky.observe(world, seat)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    wed = [c for c in crisis["claimants"] if L.married_line(world, crisis, c["person"])]
    assert wed and "married_line" in C.proofs(world, crisis, wed[0])


def test_an_arbiter_may_rule_where_there_is_no_majority(game, monkeypatch):
    monkeypatch.setattr(L, "ARBITER_CHANCE", 1.0)
    monkeypatch.setattr(L, "DEFY_CHANCE", 0.0)
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {c["person"]: [c["person"]] for c in crisis["claimants"]}, [1, 2, 3]))
    to_stage(world, occurrence, seat, "active")
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["outcome"]["how"] == "arbiter" and world.chronicle_of_kind("arbitrated")


def test_a_proud_loser_may_defy_the_arbiter(game, monkeypatch):
    monkeypatch.setattr(L, "ARBITER_CHANCE", 1.0)
    monkeypatch.setattr(L, "DEFY_CHANCE", 1.0)
    monkeypatch.setattr(L, "verdict", lambda world, crisis, standing: next(
        c["person"] for c in standing if "proud" not in world.entity(c["person"]).data.get("traits", ())))
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {c["person"]: [c["person"]] for c in crisis["claimants"]}, [1, 2, 3]))
    to_stage(world, occurrence, seat, "active")
    assert SC.crisis_of(world.entity(occurrence.id))["phase"] == "strife"
    assert world.facts(predicate="defied_arbiter", subject=proud)


def test_a_master_with_no_chief_disciple_may_name_an_outsider(game, monkeypatch):
    monkeypatch.setattr(L, "OUTSIDER_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    [leader] = staff(world, sect, seat, "leader")
    wanderer = founding.make_person(world, "test:wanderer", seat, occupation="wandering swordsman", age=40,
                                    realm=world.entity(leader).data["realm"])
    commit(world, [Event("died", (leader, leader), seat, {"cause": "killed", "world": True})])
    assert world.entity(sect).data["outsider"] == wanderer
    import systems.lives as lives
    import systems.world_clock as clock
    clock.world_tick(world)
    world.set_time(world.time + lives.SEASON)
    clock.run_due(world)
    crisis = SC.crisis_of(SC.live(world, sect))
    outsider = SC.claimant(crisis, wanderer)
    assert outsider == {"person": wanderer, "kind": "outsider"}
    voter = next(v for v in C.voters(world, sect) if v != wanderer and not world.entity(v).data.get("is_player"))
    assert C.lean(world, crisis, voter, outsider, full=False) < C.lean(
        world, crisis, voter, {"person": wanderer, "kind": "elder"}, full=False)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_legitimacy.py`
Expected: `ModuleNotFoundError: No module named 'systems.legitimacy'`.

- [ ] **Step 3: Write the new modules**

`systems/legitimacy.py`:
```python
"""New ways to the seat (phase 4h spec 7): the supreme art, the founder's test, marriage into the master's
line, an arbiter's verdict, and an outsider named heir.
"""

import systems.claimants as C
import systems.lives as lives
import systems.plots as P
import systems.succession_crisis as SC
import systems.world_clock as world_clock
from systems import factions as F
from systems.agendas import _pair, spouse_of
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.items import create_manual
from systems.kin import kin_of
from systems.realms import REALMS
from systems.techniques import GRADE_MULT, create_technique, generate, known_arts, teach
from systems.tournaments import alive, realm_of
from world.body import add_injury
from world.events import Event, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

ART_KNOWN = 0.5  # the completeness that shows the art
HEIR_LEARNS = 4  # seasons as chief disciple before the leader teaches them half the art
MANUAL_CHANCE, MANUAL_COMPLETENESS, MANUAL_FIND = 0.5, 0.8, 0.5
TEST_BASE, TEST_PER_REALM, TEST_PER_WIT, TEST_BOUNDS = 0.02, 0.08, 0.02, (0.02, 0.5)
TEST_DEATH, NPC_TRY = 0.3, 0.3
MARRY_CHANCE = 0.2
ARBITER_CHANCE, DEFY_CHANCE = 0.3, 0.5
OUTSIDER_CHANCE, OUTSIDER_LEAN = 0.1, -0.2
WANDERERS = frozenset({"wandering swordsman"})
RIGHTEOUS = frozenset({"alliance", "orthodox_sect"})


def great(world, faction: int) -> bool:
    data = world.entity(faction).data
    return data.get("tier") == "great" and data.get("type") in F.STAFFED


# --- the supreme art -------------------------------------------------------------------------------------

def supreme_art(world, faction: int) -> int:
    """The sect's top-grade art, made once and seeded (spec 7)."""
    found = world.entity(faction).data.get("supreme_art")
    if found is not None:
        return found
    rng = rng_for(world.world_seed, f"world:{faction}:supreme_art")
    name, data = generate(rng, "martial", grade=len(GRADE_MULT))
    art = create_technique(world, name, {**data, "origin": "supreme", "faction": faction})
    world.update_data(faction, supreme_art=art)
    return art


def art_known(world, person: int, faction: int) -> float:
    art = world.entity(faction).data.get("supreme_art")
    if art is None:
        return 0.0
    return max((a.known_completeness for a in known_arts(world, person) if a.technique.id == art), default=0.0)


def teaching_events(world, n: int) -> list[Event]:
    """Once a year a great sect's chief disciple of a year's standing is taught half the supreme art (spec 7)."""
    if n % 4 != C.NAMING_SEASON:
        return []
    events = []
    for faction in world.entities_after("faction", "heir", 0):
        heir, since = faction.data.get("heir"), faction.data.get("heir_since")
        if great(world, faction.id) and since is not None and n - since >= HEIR_LEARNS and alive(world, heir) \
                and art_known(world, heir, faction.id) < ART_KNOWN:
            events.append(Event("art_taught", (heir,), faction.data.get("seat"), {"faction": faction.id}))
    return events


@effect("art_taught")
def _taught(world, event) -> None:
    art = supreme_art(world, event.data["faction"])
    teach(world, event.actors[0], art, completeness=ART_KNOWN, known_completeness=ART_KNOWN, source="sect")


@listen("named_chief")
def _named_since(world, event, event_id: int) -> None:
    """Remember when the chief disciple was named (the art is taught after a year)."""
    world.update_data(event.data["faction"], heir_since=lives.current_season(world))


@listen("died")
def _manual_left(world, event, event_id: int) -> None:
    """A great sect's master dies: a manual of the supreme art may lie in their chambers (0.5)."""
    victim = event.actors[-1]
    for fid, _, data in F.memberships(world, victim):
        if data.get("role") != "leader" or not great(world, fid) or world.entity(fid).data.get("dissolved"):
            continue
        if world.entity(fid).data.get("art_manual") is None \
                and rng_for(world.world_seed, f"manual:{fid}:{victim}").random() < MANUAL_CHANCE:
            manual = create_manual(world, fid, supreme_art(world, fid), MANUAL_COMPLETENESS)  # the sect holds it
            world.update_data(fid, art_manual=manual)


@listen("chambers_searched")
def _manual_found(world, event, event_id: int) -> None:
    """The late master's rooms: a search that turned up no will may turn up the manual (spec 7)."""
    occurrence = world.entity(event.data["occurrence"])
    faction = SC.crisis_of(occurrence)["faction"]
    manual = world.entity(faction).data.get("art_manual")
    if manual is None or event.data["found"]:
        return
    if rng_for(world.world_seed, f"manual:{occurrence.id}:{event.actors[0]}:{event.data['season']}").random() < MANUAL_FIND:
        commit(world, [Event("manual_found", (event.actors[0],), event.place, {"faction": faction, "manual": manual})])


@effect("manual_found")
def _found(world, event) -> None:
    manual = event.data["manual"]
    for owner in world.sources(manual, "owns"):
        world.unrelate(owner, "owns", manual)
    world.relate(event.actors[0], manual, "owns")
    world.update_data(event.data["faction"], art_manual=None)


# --- the founder's test ------------------------------------------------------------------------------------

def test_chance(world, person: int) -> float:
    wit = load_body(world, person).physique["comprehension"] if world.entity(person).data.get("is_player") else 5
    low, high = TEST_BOUNDS
    return max(low, min(high, TEST_BASE + TEST_PER_REALM * (realm_of(world, person) - 2) + TEST_PER_WIT * (wit - 5)))


def test_block(world, occurrence, person: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if not great(world, crisis["faction"]):
        return "This sect's founder left no test."
    if crisis["phase"] not in ("mourning", "canvass"):
        return "The founder's hall is closed now."
    if SC.claimant(crisis, person) is None:
        return "Only a claimant may enter the founder's hall."
    if person in crisis.get("tested", []):
        return "You have faced the founder's test."
    return None


def test_events(world, occurrence, person: int) -> list[Event]:
    """The founder's test: passing takes the seat; failing strikes the claim, and may kill (spec 7)."""
    place = occurrence.data["place"]
    rng = rng_for(world.world_seed, f"founder:{occurrence.id}:{person}")
    if rng.random() < test_chance(world, person):
        return [Event("founder_passed", (person,), place, {"occurrence": occurrence.id})] + \
            SC.settle_events(world, occurrence, person, "founder")
    dies = rng.random() < TEST_DEATH
    events = [Event("founder_failed", (person,), place, {"occurrence": occurrence.id, "dies": dies})]
    if dies and world.entity(person).data.get("is_player"):
        from systems.mortality import death_events  # the player's death goes the 4b way: dying, then an heir
        events += death_events(world, person, "founder_test", None)
    elif dies:
        events.append(Event("died", (person, person), place, {"cause": "founder_test", "world": True}))
    return events


@effect("founder_passed")
def _passed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "tested": crisis.get("tested", []) + [event.actors[0]]})


@effect("founder_failed")
def _failed(world, event) -> None:
    person = event.actors[0]
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "tested": crisis.get("tested", []) + [person],
                                           "claimants": [c for c in crisis["claimants"] if c["person"] != person]})
    if event.data["dies"]:
        return
    if world.entity(person).data.get("is_player"):
        body = load_body(world, person)
        add_injury(body, "torso", "internal", 4, world.time, "the founder's test")
        save_body(world, person, body)
    else:
        from systems.testament import set_realm
        set_realm(world, person, realm_of(world, person) - 1)


def _npc_tries(world, occurrence, stage: str) -> None:
    crisis = SC.crisis_of(occurrence)
    if not great(world, crisis["faction"]):
        return
    rng = rng_for(world.world_seed, f"founder:{occurrence.id}:{stage}")
    for c in list(SC.standing_claimants(world, crisis)):
        person = c["person"]
        if world.entity(person).data.get("is_player") or not C.ambitious(world, person) \
                or test_block(world, world.entity(occurrence.id), person) is not None or rng.random() >= NPC_TRY:
            continue
        commit(world, test_events(world, world.entity(occurrence.id), person))
        if SC.live(world, crisis["faction"]) is None:
            return


@listen("crisis_heralded")
def _mourning(world, event, event_id: int) -> None:
    occurrence = world.entity(event.data["occurrence"])
    _weddings(world, occurrence)
    _npc_tries(world, world.entity(occurrence.id), "mourning")


@listen("crisis_phase")
def _canvass(world, event, event_id: int) -> None:
    if event.data["phase"] == "canvass":
        _npc_tries(world, world.entity(event.data["occurrence"]), "canvass")


# --- marriage into the line -------------------------------------------------------------------------------

def married_line(world, crisis: dict, person: int) -> bool:
    leader = crisis.get("leader")
    spouse = spouse_of(world, person)
    return leader is not None and spouse is not None and (spouse, "child") in kin_of(world, leader)


def _weddings(world, occurrence) -> None:
    """In the mourning an unmarried claimant may wed an unmarried grown child of the late master (0.2)."""
    crisis = SC.crisis_of(occurrence)
    leader = crisis.get("leader")
    if leader is None:
        return
    rng = rng_for(world.world_seed, f"wed:{occurrence.id}")
    children = [k for k, role in kin_of(world, leader) if role == "child" and C.age_of(world, k) >= C.ADULT
                and spouse_of(world, k) is None and SC.claimant(crisis, k) is None]
    for c in crisis["claimants"]:
        person = c["person"]
        if not children or world.entity(person).data.get("is_player") or spouse_of(world, person) is not None:
            continue
        if rng.random() < MARRY_CHANCE:
            child = children.pop(0)
            commit(world, [Event("wed_for_seat", (person, child), occurrence.data["place"],
                                 {"occurrence": occurrence.id})])


@effect("wed_for_seat")
def _wed(world, event) -> None:
    _pair(world, event.actors[0], event.actors[1], "spouse")


# --- arbitration --------------------------------------------------------------------------------------------

def arbiter_of(world, faction: int) -> int | None:
    """The Murim Alliance, else the nearest orthodox sect not in crisis itself."""
    home = world.entity(faction).data.get("home")
    options = []
    for other in F.ensure_roster(world):
        o = world.entity(other)
        if other == faction or o.data.get("dissolved") or o.data.get("type") not in RIGHTEOUS:
            continue
        rank = 0 if o.data["type"] == "alliance" else 1
        options.append((rank, F.gap(home, o.data["home"]) if home and o.data.get("home") else 99, other))
    return min(options)[2] if options else None


def verdict(world, crisis: dict, standing: list[dict]) -> int:
    """Whom an arbiter names: proofs and realm only, no grudges (spec 7)."""
    weakest = min(realm_of(world, c["person"]) for c in standing)
    return max(standing, key=lambda c: (C.proof_lean(world, crisis, c) + C.REALM_LEAN * (realm_of(world, c["person"])
                                                                                       - weakest),
                                        -c["person"]))["person"]


def arbitration_events(world, occurrence, standing: list[dict], ranked: list[int]) -> list[Event]:
    """With no majority, an arbiter may rule before any trial (0.3); a proud loser may defy it (0.5)."""
    crisis, place = SC.crisis_of(occurrence), occurrence.data["place"]
    arbiter = arbiter_of(world, crisis["faction"])
    rng = rng_for(world.world_seed, f"arbiter:{occurrence.id}")
    if arbiter is None or rng.random() >= ARBITER_CHANCE:
        return []
    named = verdict(world, crisis, standing)
    loser = next(p for p in ranked if p != named)
    events = [Event("arbitrated", (named, loser), place, {"occurrence": occurrence.id, "arbiter": arbiter})]
    if SC.PROUD & set(world.entity(loser).data.get("traits", ())) and rng.random() < DEFY_CHANCE:
        return events + [Event("arbiter_defied", (loser, named), place, {"arbiter": arbiter}),
                         Event("crisis_refused", (loser, named), place, {"occurrence": occurrence.id})]
    return events + SC.settle_events(world, occurrence, named, "arbiter")


@listen("arbiter_defied")
def _defied(world, event, event_id: int) -> None:
    loser, named = event.actors
    variant = make_variant("defied_arbiter", loser, event.data["arbiter"], place=place_name(world, event.place))
    record_fact(world, loser, "defied_arbiter", event.data["arbiter"], place=event.place, source_event=event_id,
                weight=2.0, variant=variant)


# --- an outsider named heir ------------------------------------------------------------------------------

def outsider_for(world, faction: int, leader: int) -> int | None:
    """The best-known martial wanderer of the seat's region, at the late master's realm or above."""
    seat = world.entity(faction).data.get("seat")
    if seat is None:
        return None
    region = world.targets(seat, "located_in")
    towns = [t for t in world.sources(region[0], "located_in") if world.entity(t).kind == "town"] if region else []
    floor = realm_of(world, leader)
    able = [p.id for t in towns for p in people_at(world, t) if p.data.get("occupation") in WANDERERS
            and not p.data.get("is_player") and realm_of(world, p.id) >= floor and not F.memberships(world, p.id)]
    return max(able, key=lambda p: (realm_of(world, p), -p)) if able else None


@listen("died")
def _outsider_named(world, event, event_id: int) -> None:
    """A dying master with no chief disciple may name a respected outsider (0.1)."""
    victim = event.actors[-1]
    for fid, _, data in F.memberships(world, victim):
        faction = world.entity(fid)
        if data.get("role") != "leader" or faction.data.get("type") not in F.STAFFED or faction.data.get("heir"):
            continue
        if rng_for(world.world_seed, f"outsider:{fid}:{victim}").random() < OUTSIDER_CHANCE:
            chosen = outsider_for(world, fid, victim)
            if chosen is not None:
                world.update_data(fid, outsider=chosen)


def _outsider_claims(world, occurrence) -> None:
    """At a crisis's start the outsider named claims; a will read out names them."""
    crisis = SC.crisis_of(occurrence)
    outsider = world.entity(crisis["faction"]).data.get("outsider")
    if outsider is None:
        return
    world.update_data(crisis["faction"], outsider=None)
    if not alive(world, outsider) or SC.claimant(crisis, outsider) is not None:
        return
    will = crisis.get("will") or {}
    if will.get("state") == "read":
        will = {**will, "names": outsider}
    world.update_data(occurrence.id, data={**crisis, "will": will,
                                           "claimants": crisis["claimants"] + [{"person": outsider, "kind": "outsider"}]})


P.BEGUN_HOOKS.append(_outsider_claims)
world_clock.SEASON_HOOKS.append(teaching_events)
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4h_task4.py`:
```python
"""Phase 4h, Task 4: legitimacy in the clock, the new proofs and the outsider's lean, arbitration before a trial, a realm changed through the body"""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def still(path: str) -> None:
    """A 4g test's fixture stills 4h's intrigue: they test the crisis alone."""
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    anchor = '    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)\n'
    if text.count(anchor) != 1:
        raise SystemExit(f"{path}: no single calm fixture")
    text = text.replace(anchor, anchor + "    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises\n")
    i = text.index("\n\n\n@pytest.fixture")
    text = text[:i] + "\nfrom tests.intrigue import still" + text[i:]
    file.write_text(text, encoding="utf-8", newline="\n")


edit('systems/world_clock.py', r'''import systems.frames  # noqa: E402,F401  phase 4h: forged wills, framed heirs and their return''', r'''import systems.frames  # noqa: E402,F401  phase 4h: forged wills, framed heirs and their return
import systems.legitimacy  # noqa: E402,F401  phase 4h: the supreme art, the founder's test, marriage, arbiters''')
edit('systems/claimants.py', r'''              "truth": 0.5}  # 4h: a returned heir whose frame was exposed''', r'''              "truth": 0.5, "supreme_art": 0.6, "married_line": 0.3}  # 4h''')
edit('systems/claimants.py', r'''        found.append("truth")
    return found''', r'''        found.append("truth")
    from systems.legitimacy import ART_KNOWN, art_known, married_line  # phase 4h
    if art_known(world, person, crisis["faction"]) >= ART_KNOWN:
        found.append("supreme_art")
    if married_line(world, crisis, person):
        found.append("married_line")
    return found''')
edit('systems/claimants.py', r'''    if "loyal" in world.entity(voter).data.get("traits", ()) and person == named(world, crisis):
        value += LOYAL_LEAN''', r'''    if "loyal" in world.entity(voter).data.get("traits", ()) and person == named(world, crisis):
        value += LOYAL_LEAN
    if claimant["kind"] == "outsider":
        value += OUTSIDER_LEAN  # the sect's own resent an outsider (4h)''')
edit('systems/claimants.py', r'''LOYAL_LEAN = 0.2''', r'''LOYAL_LEAN = 0.2
OUTSIDER_LEAN = -0.2''')
edit('systems/succession_crisis.py', r'''    if tally[ranked[0]] * 2 > total:
        return settle_events(world, occurrence, ranked[0], "backing")
    a, b = ranked[:2]''', r'''    if tally[ranked[0]] * 2 > total:
        return settle_events(world, occurrence, ranked[0], "backing")
    from systems.legitimacy import arbitration_events  # phase 4h: an arbiter may rule before any trial
    ruled = arbitration_events(world, occurrence, standing, ranked)
    if ruled:
        return ruled
    a, b = ranked[:2]''')
edit('systems/mortality.py', r'''"sealed": "sealed in a secret realm", "realm": "in a secret realm"}''', r'''"sealed": "sealed in a secret realm", "realm": "in a secret realm",
          "founder_test": "in the founder's test"}''')
edit('narrate/crisis_text.py', r'''             "stepped_down": "named by the old master", "regency": "as regent"}''', r'''             "stepped_down": "named by the old master", "regency": "as regent",
             "founder": "chosen by the founder's hall", "arbiter": "by an arbiter's verdict"}''')
edit('systems/testament.py', r'''@effect("transmitted")
def _transmitted(world, event) -> None:
    leader, heir = event.actors
    top = min(len(REALMS) - 1, max(realm_of(world, heir) + 1, 0))
    top = min(top, max(realm_index(world.entity(leader).data.get("realm", "mortal")), realm_of(world, heir)))
    if world.entity(heir).data.get("is_player"):
        body = load_body(world, heir)
        if top > body.realm:
            body.realm, body.energy_years, body.bottleneck = top, REALMS[top].threshold, False
            save_body(world, heir, body)
    else:
        world.update_data(heir, realm=REALMS[top].label)
    world.update_data(event.data["faction"], transmitted=heir)''', r'''def set_realm(world, person: int, index: int) -> None:
    """A realm changed at a stroke: through the body when there is one, so body and label agree (4h)."""
    index = max(0, min(len(REALMS) - 1, index))
    entity = world.entity(person)
    if entity.data.get("is_player") or "body" in entity.data:
        body = load_body(world, person)
        body.realm, body.energy_years, body.bottleneck = index, REALMS[index].threshold, False
        save_body(world, person, body)
    else:
        world.update_data(person, realm=REALMS[index].label)


@effect("transmitted")
def _transmitted(world, event) -> None:
    leader, heir = event.actors
    top = min(len(REALMS) - 1, max(realm_of(world, heir) + 1, 0))
    top = min(top, max(realm_index(world.entity(leader).data.get("realm", "mortal")), realm_of(world, heir)))
    if top > realm_of(world, heir):
        set_realm(world, heir, top)
    world.update_data(event.data["faction"], transmitted=heir)''')
print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4h_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_legitimacy.py tests/test_testament.py tests/test_crisis_contest.py`
Expected: `26 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: new ways to the seat - the supreme art, the founder's test, a wedding, an arbiter, an outsider named heir

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: The player investigates

At the seat: examine the late master's body, search a suspect's quarters, accuse before the elders (a proud man falsely accused calls you out), attempt the founder's test, examine a read will, and, framed, return to demand the seat. In conversation: ask about the night the master died, the gift, the envoy, the will, the crime. Typed commands, outcomes and journal lines for every deed.

**Files:**
- Create: `engine/intrigue.py`
- Create: `narrate/grammar/intrigue.toml`
- Create: `narrate/intrigue_text.py`
- Create: `tests/test_intrigue_play.py`
- Modify (by `.patches/4h_task5.py`): `narrate/outcomes.py`, `engine/game.py`, `engine/commands.py`

**Interfaces:**
- Consumes: Tasks 1-4: `P.search_*`, `P.accuse_*`, `P.suspicions`, `M.examine_*`, `M.witness_plot`, `M.night_events`, `U.gift_plot`, `U.envoy_plot`, `U.asked_events`, `R.examine_will_*`, `R.ask_plot`, `R.asked_events`, `R.player_return_block`, `R.return_events`, `L.test_*`; 4g's `CrisisMixin`; `encounters.challenge_events`.
- Produces:
  - `engine/intrigue.py`: `IntrigueMixin` with `_general_extras`, `_conversation_extras`, `_do_examine_body`, `_do_examine_will`, `_do_founder_test`, `_do_search_quarters`, `_do_accuse`, `_do_ask_clue`, `_do_return_seat`, `_commit_quiet`.
  - `narrate/intrigue_text.py`: `CLUE_WORDS`, `clue_words(world, clue)`, the tales and deed lines; `narrate/grammar/intrigue.toml`.
  - `commands`: `accuse <name>`, `examine body`.

- [ ] **Step 1: Write the failing tests**

`tests/test_intrigue_play.py`:
```python
import random

import pytest

import systems.encounters as encounters
import systems.frames as R
import systems.legitimacy as L
import systems.murder as M
import systems.plots as P
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action, Choice
from engine.commands import parse
from engine.game import Game
from narrate.outcomes import SUMMARIES
from systems import factions as F
from systems.creation import CreationChoice
from tests.intrigue import still
from tests.test_crisis_play import crisis_at_seat, to_stage
from tests.test_plots import poisoned_sect
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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(L, "MANUAL_CHANCE", 0.0)


def labels(turn):
    return [c.label for c in turn.all_choices]


def a_murder(game, monkeypatch):
    monkeypatch.setattr(M, "MURDER_CHANCE", 1.0)
    monkeypatch.setattr(M, "RED_HERRING", 0.0)
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    sect, seat, leader, proud, plot = poisoned_sect(game)
    import systems.lives as lives
    import systems.world_clock as clock
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)
    return sect, seat, proud, plot


def test_the_body_the_quarters_and_the_accusation(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, proud, plot = a_murder(game, monkeypatch)
    turn = game.perform(Action("look"))
    assert "Examine the late master's body" in labels(turn)
    turn = game.perform(Action("examine_body", SC.live(world, sect).id))
    assert any("This was no natural death" in t for t, _ in turn.lines)
    assert any(f"You have found it" in t for t, _ in turn.lines)
    name = world.entity(proud).name
    assert f"Search {name}'s quarters" in labels(game.perform(Action("look")))
    game.perform(Action("search_quarters", proud))
    assert f"Accuse {name} before the elders" in labels(game.perform(Action("look")))
    turn = game.perform(Action("accuse", (proud, sect)))
    assert any("nowhere to hide" in t for t, _ in turn.lines)
    assert world.entity(plot.id).data["state"] == "exposed"


def test_the_witness_is_asked_about_the_night(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, proud, plot = a_murder(game, monkeypatch)
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "witness")
    turn = game.perform(Action("talk", witness))
    assert "Ask about the night the master died" in labels(turn)
    turn = game.perform(Action("ask_clue", (witness, "witness")))
    assert any("what they saw that night" in t for t, _ in turn.lines)
    assert P.suspicions(world, me, sect) == {proud: ["witness"]}


def test_a_proud_man_falsely_accused_calls_you_out(game, monkeypatch):
    monkeypatch.setattr(M, "RED_HERRING", 1.0)
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    monkeypatch.setattr(M, "MURDER_CHANCE", 1.0)
    world, me = game.world, game.player.id
    import tests.test_plots as TP
    innocent_sect = TP.poisoned_sect  # the plotter is pinned there; build a red herring by hand instead
    sect, seat, leader, proud, plot = innocent_sect(game)
    innocent = next(p for p in (c["witness"] for c in plot.data["clues"] if c.get("witness")) if p != proud)
    world.update_data(innocent, traits=["proud"])
    clues = [dict(c, points_to=innocent, false=True) if c["kind"] in ("witness", "motive") else c
             for c in plot.data["clues"]]
    world.update_data(plot.id, clues=clues)
    commit(world, P.found_events(world, world.entity(plot.id), "witness", me, seat))
    commit(world, P.found_events(world, world.entity(plot.id), "motive", me, seat))
    turn = game.perform(Action("accuse", (innocent, sect)))
    assert any("falls apart" in t for t, _ in turn.lines)
    assert game.challenger == innocent


def test_a_claimant_may_face_the_founders_test(game, monkeypatch):
    monkeypatch.setattr(L, "test_chance", lambda world, person: 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    assert "Enter the founder's hall and face the test" in labels(game.perform(Action("look")))
    turn = game.perform(Action("founder_test", occurrence.id))
    assert any("you are chosen" in t for t, _ in turn.lines)
    assert F.membership(world, me, sect)[1]["role"] == "leader"


def test_a_forged_wills_seal_can_be_examined(game, monkeypatch):
    monkeypatch.setattr(R, "FORGE_CHANCE", 1.0)
    monkeypatch.setattr(R, "seal_chance", lambda world, player: 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(proud, traits=["cunning"])
    to_stage(world, occurrence, seat, "announced")
    assert "Examine the will that was read" in labels(game.perform(Action("look")))
    turn = game.perform(Action("examine_will", occurrence.id))
    assert any("the seal is not the late master's" in t for t, _ in turn.lines)


def test_a_framed_player_may_demand_the_seat_back(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    commit(world, R.frame_events(world, world.entity(occurrence.id), proud, me, "frame:test", random.Random(1)))
    framed = world.entity(me).data["framed"]
    world.update_data(me, framed={**framed, "since": framed["since"] - R.PLAYER_RETURN})
    label = f"Demand the seat of the {world.entity(sect).name} you were cast out of"
    assert label in [c.label for c in game._general_extras()]  # a grudge may call the player out first
    game.perform(Action("return_seat", sect))
    assert world.chronicle_of_kind("heir_returned")


def test_typed_commands_reach_the_investigation(game):
    assert parse("examine body", []) == Action("examine_body")
    choices = [Choice("Accuse Ha Haolong before the elders", Action("accuse", (39, 9)))]
    assert parse("accuse ha haolong", choices) == Action("accuse", (39, 9))


def test_every_deed_of_the_investigation_has_a_journal_line():
    for kind in ("body_examined", "clue_found", "quarters_searched", "plot_exposed", "false_accusation",
                 "asked_night", "asked_about", "will_examined", "founder_passed", "founder_failed", "heir_returned"):
        assert kind in SUMMARIES, kind
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_intrigue_play.py`
Expected: 8 failed: the choices are not offered (`AssertionError: assert 'Examine the will that was read' in [...]`), `AssertionError: body_examined`, and the typed command unknown.

- [ ] **Step 3: Write the new modules**

`engine/intrigue.py`:
```python
"""The player's investigation (phase 4h spec 3-7, 11): examine the body, ask, search, accuse, the founder's hall,
the will, and the framed heir's return."""

import systems.encounters as encounters
import systems.frames as R
import systems.legitimacy as L
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.succession_crisis as SC
from engine.actions import Action, Choice
from world.events import commit

ASKS = {"night": "Ask about the night the master died", "silver": "Ask about the gift they took",
        "envoy": "Ask where they have come from", "scribe": "Ask about the will they wrote",
        "false_witness": "Ask about the crime they swore to", "seen": "Ask what they saw outside the walls"}


class IntrigueMixin:
    def _crises_here(self) -> list:
        """Live crises whose seat is this town (anyone at the seat may look into them)."""
        out = []
        for faction in self.world.entities_after("faction", "crisis", 0):
            occurrence = SC.live(self.world, faction.id)
            if occurrence is not None and occurrence.data["place"] == self.place.id:
                out.append(occurrence)
        return out

    def _seated_here(self) -> list[int]:
        return [f for f in self.world.entity(self.place.id).data.get("seats", [])
                if not self.world.entity(f).data.get("dissolved")]

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me = self.world, self.player.id
        for occurrence in self._crises_here():
            if M.examine_block(world, occurrence, me) is None:
                extras.append(Choice("Examine the late master's body", Action("examine_body", occurrence.id)))
            if L.test_block(world, occurrence, me) is None:
                extras.append(Choice("Enter the founder's hall and face the test", Action("founder_test", occurrence.id)))
            if R.examine_will_block(world, occurrence, me) is None:
                extras.append(Choice("Examine the will that was read", Action("examine_will", occurrence.id)))
        for suspect in sorted(P.suspicions(world, me)):
            if P.search_block(world, me, suspect) is None:
                extras.append(Choice(f"Search {world.entity(suspect).name}'s quarters", Action("search_quarters", suspect)))
            for faction in self._seated_here():
                if P.accuse_block(world, me, suspect, faction) is None:
                    extras.append(Choice(f"Accuse {world.entity(suspect).name} before the elders",
                                         Action("accuse", (suspect, faction))))
        framed = self.player.data.get("framed") or {}
        if framed and R.player_return_block(world, me, self.place.id) is None:
            extras.append(Choice(f"Demand the seat of the {world.entity(framed['faction']).name} you were cast out of",
                                 Action("return_seat", framed["faction"])))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        world, me = self.world, self.player.id
        if M.witness_plot(world, me, npc.id) is not None:
            extras.append(Choice(ASKS["night"], Action("ask_clue", (npc.id, "witness"))))
        if U.gift_plot(world, me, npc.id) is not None:
            extras.append(Choice(ASKS["silver"], Action("ask_clue", (npc.id, "silver"))))
        if U.envoy_plot(world, me, npc.id) is not None:
            extras.append(Choice(ASKS["envoy"], Action("ask_clue", (npc.id, "envoy"))))
        for kind, label in (("scribe", ASKS["scribe"]), ("false_witness", ASKS["false_witness"]), ("night", ASKS["seen"])):
            plot = R.ask_plot(world, me, npc.id, kind)
            if plot is not None and SC.live(world, plot.data["faction"]) is not None:  # people talk in a crisis
                extras.append(Choice(label, Action("ask_clue", (npc.id, kind))))
        return extras

    def _occurrence_here(self, occurrence_id):
        found = [o for o in self._crises_here() if o.id == occurrence_id]
        return found[0] if found else None

    def _do_examine_body(self, occurrence_id):
        if occurrence_id is None:  # typed: the crisis here, if one
            occurrence_id = next((o.id for o in self._crises_here()), None)
        occurrence = self._occurrence_here(occurrence_id)
        if occurrence is None or (why := M.examine_block(self.world, occurrence, self.player.id)) is not None:
            return self._turn([(why if occurrence else "There is no one lying in state here.", "system")])
        return self._turn(self._commit(M.examine_events(self.world, occurrence, self.player.id)))

    def _do_examine_will(self, occurrence_id):
        occurrence = self._occurrence_here(occurrence_id)
        if occurrence is None or (why := R.examine_will_block(self.world, occurrence, self.player.id)) is not None:
            return self._turn([(why if occurrence else "No will has been read here.", "system")])
        return self._turn(self._commit(R.examine_will_events(self.world, occurrence, self.player.id)))

    def _do_founder_test(self, occurrence_id):
        occurrence = self._occurrence_here(occurrence_id)
        if occurrence is None or (why := L.test_block(self.world, occurrence, self.player.id)) is not None:
            return self._turn([(why if occurrence else "There is no founder's hall open to you here.", "system")])
        return self._turn(self._commit(L.test_events(self.world, occurrence, self.player.id)))

    def _do_search_quarters(self, suspect):
        if not isinstance(suspect, int) or (why := P.search_block(self.world, self.player.id, suspect)) is not None:
            return self._turn([(why if isinstance(suspect, int) else "Whose quarters?", "system")])
        return self._turn(self._commit(P.search_events(self.world, self.player.id, suspect, self.place.id)))

    def _do_accuse(self, target):
        suspect, faction = target if isinstance(target, tuple) else (target, None)
        if faction is None:
            faction = next((f for f in self._seated_here() if P.accuse_block(self.world, self.player.id, suspect, f)
                            is None), None)
        if faction is None or (why := P.accuse_block(self.world, self.player.id, suspect, faction)) is not None:
            return self._turn([(why if faction is not None else "There are no elders here to hear you.", "system")])
        events = P.accuse_events(self.world, self.player.id, suspect, faction, self.place.id)
        lines = self._commit_quiet(events)
        if events[0].kind == "false_accusation" and SC.PROUD & set(self.world.entity(suspect).data.get("traits", ())) \
                and self.place.id in self.world.targets(suspect, "located_in"):
            lines += self._commit(encounters.challenge_events(self.player.id, suspect, self.place.id))
            self.challenger = suspect  # a proud man falsely accused calls you out
        return self._turn(lines)

    def _commit_quiet(self, events: list) -> list:
        """The player's deeds narrated; the world's events (no actors) committed without a line."""
        lines = []
        for event in events:
            if event.actors:
                lines += self._commit([event])
            else:
                commit(self.world, [event])
        return lines

    def _do_ask_clue(self, target):
        npc, kind = target if isinstance(target, tuple) else (None, None)
        if npc is None or self.focus != npc:
            return self._turn([("Speak with them first.", "system")])
        world, me, here = self.world, self.player.id, self.place.id
        if kind == "witness":
            events = M.night_events(world, me, npc, here)
        elif kind in ("silver", "envoy"):
            events = U.asked_events(world, me, npc, here, kind)
        else:
            events = R.asked_events(world, me, npc, here, kind)
        return self._turn(self._commit(events))

    def _do_return_seat(self, faction):
        if (why := R.player_return_block(self.world, self.player.id, self.place.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit_quiet(R.return_events(self.world, self.player.id,
                                                             lives.current_season(self.world))))
```

`narrate/grammar/intrigue.toml`:
```toml
[symbols]
intrigue_air = ["Someone in the hall is lying.", "A lamp gutters in the draught.", "Footsteps stop, and start again.", "The incense cannot hide everything.", "Every door in the hall seems to listen.", "The mourners' eyes follow you."]

[body_examined]
colour = "default"
lines = ["#intrigue_air#"]

[clue_found]
colour = "gold"
lines = ["#intrigue_air#"]

[quarters_searched]
colour = "dim"
lines = ["#intrigue_air#"]

[plot_exposed]
colour = "gold"
lines = ["#intrigue_air# #intrigue_air#"]

[thanked]
colour = "dim"
lines = ["#intrigue_air#"]

[false_accusation]
colour = "red"
lines = ["#intrigue_air#"]

[asked_night]
colour = "dim"
lines = ["#intrigue_air#"]

[asked_about]
colour = "dim"
lines = ["#intrigue_air#"]

[will_examined]
colour = "dim"
lines = ["#intrigue_air#"]

[founder_passed]
colour = "gold"
lines = ["#intrigue_air#"]

[founder_failed]
colour = "red"
lines = ["#intrigue_air#"]

[heir_returned]
colour = "gold"
lines = ["#intrigue_air#"]

[claim_joined]
colour = "dim"
lines = ["#intrigue_air#"]

[murder_revealed]
colour = "red"
lines = ["#intrigue_air#"]

[puppet_revealed]
colour = "red"
lines = ["#intrigue_air#"]

[spy_revealed]
colour = "red"
lines = ["#intrigue_air#"]

[forgery_revealed]
colour = "red"
lines = ["#intrigue_air#"]

[frame_revealed]
colour = "gold"
lines = ["#intrigue_air#"]
```

`narrate/intrigue_text.py`:
```python
"""What the player is told of plots (phase 4h spec 9, 11): the tales of exposures, what their clues say, their deeds."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

CLUE_WORDS = {"body": "{poison} on the late master's lips", "witness": "a witness saw {name} at the master's door",
              "motive": "letters and debts in {name}'s quarters", "silver": "{name}'s silver in a voter's purse",
              "envoy": "{name} is another sect's envoy", "night": "{name} seen outside the walls at night",
              "mark": "the cult's mark among {name}'s things", "seal": "the will's seal is false, and {name} had it made",
              "scribe": "the scribe who wrote the will for {name}", "planted": "the evidence was planted by {name}",
              "false_witness": "a witness paid by {name} to swear to the crime",
              "missing": "a witness gone missing, after crossing {name}"}
CRIME_WORDS = {"stole_art": "stole the sect's secret art", "killed_disciple": "killed a fellow disciple"}


def clue_words(world, kind: str, person, viewer: int, poison: str | None = None) -> str:
    return CLUE_WORDS.get(kind, "something that points at {name}").format(
        name=who(world, person, viewer), poison=poison or "a poison")


def _faction(world, faction) -> str:
    entity = world.entity(faction) if isinstance(faction, int) else None
    return f"the {entity.name}" if entity is not None and entity.kind == "faction" else "a sect"


def _poisoned(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} poisoned {who(world, v.get('target'), viewer)}.")


def _murdered(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} was exposed as the murderer of {who(world, v.get('target'), viewer)}.")


def _puppet(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} was a puppet of {_faction(world, v.get('target'))}.")


def _spy_for(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} was a spy for {_faction(world, v.get('target'))}.")


def _spy_exposed(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} was unmasked as a cult spy in {_faction(world, v.get('target'))}.")


def _framed(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} framed {who(world, v.get('target'), viewer)} for a crime never done.")


def _forged(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} forged the late master's will of {_faction(world, v.get('target'))}.")


def _cleared(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)}'s name was cleared in {_faction(world, v.get('target'))}.")


def _crime(predicate):
    def story(world, v, viewer) -> str:
        return cap(f"{who(world, v.get('actor'), viewer)} {CRIME_WORDS[predicate]} and was cast out of "
                   f"{_faction(world, v.get('target'))}.")
    return story


def _defied(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} defied the arbiter of {_faction(world, v.get('target'))}.")


def _false_accusation(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} accused {who(world, v.get('target'), viewer)} falsely.")


def _clue(world, v, viewer) -> str:
    return cap(f"In {_faction(world, v.get('target'))}: {clue_words(world, v.get('kind'), v.get('actor'), viewer)}.")


SPECIAL_PHRASES.update({"poisoned": _poisoned, "murdered": _murdered, "puppet_of": _puppet, "spy_for": _spy_for,
                        "spy_exposed": _spy_exposed, "framed": _framed, "forged_will": _forged, "cleared": _cleared,
                        "stole_art": _crime("stole_art"), "killed_disciple": _crime("killed_disciple"),
                        "defied_arbiter": _defied, "false_accusation": _false_accusation, "clue": _clue})


def _name(world, person) -> str:
    entity = world.entity(person) if person is not None else None
    return entity.name if entity is not None else "someone"


@outcome("body_examined", body_facts=False)
def _examined(world, event):
    if event.data["found"]:
        return [f"You kneel by the late master. The lips are dark: {event.data['poison']}. This was no natural death."], {}
    return ["You kneel by the late master and find nothing the physicians missed."], {}


@summary("body_examined")
def _examined_line(world, entry, names, place, other):
    return "Found poison on a dead master's lips." if entry.data["found"] else f"Looked on a dead master at {place}."


@outcome("clue_found", body_facts=False)
def _found(world, event):
    plot = world.entity(event.data["plot"])
    poison = next((c.get("poison") for c in plot.data["clues"] if c["kind"] == "body"), None)
    return [f"You have found it: {clue_words(world, event.data['kind'], event.data['points_to'], event.actors[0], poison)}."], {}


@summary("clue_found")
def _found_line(world, entry, names, place, other):
    return f"Found something that points at {other}."


@outcome("quarters_searched", body_facts=False)
def _searched(world, event):
    return (["You turn their quarters over, and something turns up."] if event.data["found"]
            else ["You turn their quarters over and find nothing."]), {}


@summary("quarters_searched")
def _searched_line(world, entry, names, place, other):
    return f"Searched {other}'s quarters."


@outcome("plot_exposed", body_facts=False)
def _exposed(world, event):
    plot = world.entity(event.data["plot"])
    return [f"Before the elders it all comes out: {plot.name}. {_name(world, plot.data['plotter'])} has nowhere to hide."], {}


@summary("plot_exposed")
def _exposed_line(world, entry, names, place, other):
    return f"Exposed {world.entity(entry.data['plot']).name} at {place}."


@outcome("false_accusation", body_facts=False)
def _false(world, event):
    return [f"The elders hear you out, and the evidence falls apart in your hands. {_name(world, event.actors[1])} "
            f"will not forget this."], {}


@summary("false_accusation")
def _false_line(world, entry, names, place, other):
    return f"Accused {other} falsely before the elders at {place}."


@outcome("asked_night", body_facts=False)
def _night(world, event):
    return (["They lower their voice and tell you what they saw that night."] if event.data["told"]
            else ["They saw nothing that night, they say."]), {}


@summary("asked_night")
def _night_line(world, entry, names, place, other):
    return f"Asked {other} about the night the master died."


@outcome("asked_about", body_facts=False)
def _asked(world, event):
    return (["They hesitate, then tell you more than they meant to."] if event.data["told"]
            else ["They have nothing to tell you."]), {}


@summary("asked_about")
def _asked_line(world, entry, names, place, other):
    return f"Questioned {other}."


@outcome("will_examined", body_facts=False)
def _will(world, event):
    return (["You hold the will to the light: the seal is not the late master's."] if event.data["found"]
            else ["The will looks like any will, and the seal like any seal."]), {}


@summary("will_examined")
def _will_line(world, entry, names, place, other):
    return f"Studied the late master's will at {place}."


@outcome("founder_passed", body_facts=False)
def _passed(world, event):
    return ["The founder's hall falls silent around you, and then the old bell rings once: you are chosen."], {}


@summary("founder_passed")
def _passed_line(world, entry, names, place, other):
    return f"{names[0]} passed the founder's test at {place}."


@outcome("founder_failed", body_facts=False)
def _failed(world, event):
    return ["The founder's hall rejects you. You come out broken, and without a claim."], {}


@summary("founder_failed")
def _failed_line(world, entry, names, place, other):
    return f"{names[0]} failed the founder's test at {place}."


@outcome("heir_returned", body_facts=False)
def _returned(world, event):
    return [f"{_name(world, event.actors[0])} comes back through the gate of the "
            f"{world.entity(event.data['faction']).name}, and demands the seat."], {}


@summary("heir_returned")
def _returned_line(world, entry, names, place, other):
    return f"{names[0]} returned to {place} to demand the seat."


for kind in ("murder_revealed", "puppet_revealed", "spy_revealed", "forgery_revealed", "frame_revealed",
             "thanked", "claim_joined"):
    @outcome(kind, body_facts=False)
    def _quiet(world, event):
        return [], {}
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4h_task5.py`:
```python
"""Phase 4h, Task 5: the investigation in the game: its mixin, its tales, its commands"""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def still(path: str) -> None:
    """A 4g test's fixture stills 4h's intrigue: they test the crisis alone."""
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    anchor = '    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)\n'
    if text.count(anchor) != 1:
        raise SystemExit(f"{path}: no single calm fixture")
    text = text.replace(anchor, anchor + "    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises\n")
    i = text.index("\n\n\n@pytest.fixture")
    text = text[:i] + "\nfrom tests.intrigue import still" + text[i:]
    file.write_text(text, encoding="utf-8", newline="\n")


edit('narrate/outcomes.py', r'''import narrate.crisis_text  # noqa: E402,F401
''', r'''import narrate.crisis_text  # noqa: E402,F401
import narrate.intrigue_text  # noqa: E402,F401
''')
edit('engine/game.py', r'''from engine.crisis import CrisisMixin''', r'''from engine.crisis import CrisisMixin
from engine.intrigue import IntrigueMixin''')
edit('engine/game.py', r'''class Game(CrisisMixin, SealedMixin,''', r'''class Game(IntrigueMixin, CrisisMixin, SealedMixin,''')
edit('engine/commands.py', r'''    "open": "open_meridian", "use": "use", "declare": "declare_for",''', r'''    "open": "open_meridian", "use": "use", "declare": "declare_for", "accuse": "accuse",''')
edit('engine/commands.py', r'''    "search chambers": Action("search_chambers"), "search": Action("search_chambers"), "step down": Action("step_down"),''', r'''    "search chambers": Action("search_chambers"), "search": Action("search_chambers"), "step down": Action("step_down"),
    "examine body": Action("examine_body"), "examine the body": Action("examine_body"),''')
print("task 5 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4h_task5.py`
Expected: `task 5 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_intrigue_play.py tests/test_commands.py`
Expected: `17 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the player investigates - the body, the quarters, the witness, the will, the founder's test, the accusation, the return

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: The player plots

Buy a poison from an unorthodox clan's keeper and slip it into a leader's tea; send a sworn follower to spy (they report the sect's plots each season and sway in its crises); fund a claimant (a puppet who remembers you); pay for false evidence against a rival (or have it point back at you); pay a scribe to forge the will. The camps may find the player's hand at each stage's change; an exposed scheme casts the player out, names the deed, and the town sets a bounty (ruling 9).

**Files:**
- Create: `systems/scheming.py`
- Create: `tests/test_scheming.py`
- Modify (by `.patches/4h_task6.py`): `systems/world_clock.py`, `systems/law.py`, `systems/attitude.py`, `engine/intrigue.py`, `narrate/intrigue_text.py`, `narrate/grammar/intrigue.toml`

**Interfaces:**
- Consumes: Tasks 1-5: `P.made_events`, `P.clue`, `P.SEASON_HOOKS`, `P.EXPOSE_HOOKS`, `M.murder_events`, `U.puppet_events`, `R.frame_events`, `R.forgery_events`, `IntrigueMixin`; 3c's sworn followers; 3b's `law`.
- Produces:
  - `scheming` (S): `POISON_PRICE`, `SPY_PRICE`, `FRAME_PRICE`, `FORGE_PRICE`, `FUND_PER_POWER`, `FRAME_BASE`, `FRAME_PER_WIT`, `FRAME_BOUNDS`, `NPC_FIND`, `SPY_SWAY`, `DEEDS`; `poisons_of`, `buy_poison_block/events(world, player, npc[, place])`, `poison_block/events(world, player, leader[, place])`, `spy_block/events(world, player, follower, faction[, place])`, `fund_price(world, f)`, `fund_block/events(world, player, occurrence, claimant)`, `frame_chance`, `frame_block/events(world, player, occurrence, rival)`, `forge_block(world, player, occurrence)`, `forge_events(world, player, occurrence, names)`; events `poison_bought`, `poison_slipped`, `spy_sent`, `spy_reported`, `claim_funded`, `frame_paid`, `forgery_paid`, `scheme_exposed`.
  - `IntrigueMixin`: `_do_buy_poison`, `_do_slip_poison`, `_do_plant_spy`, `_do_fund_claim`, `_do_frame_rival`, `_do_forge_will`. `law.SCHEMES`, `law.SCHEME_WEIGHT`; `attitude` judges the deeds.

- [ ] **Step 1: Write the failing tests**

`tests/test_scheming.py`:
```python
import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.law as law
import systems.legitimacy as L
import systems.lives as lives
import systems.plots as P
import systems.scheming as S
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.game import Game
from narrate.outcomes import SUMMARIES
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from tests.intrigue import still
from tests.test_crisis_contest import a_crisis
from tests.test_crisis_play import crisis_at_seat, to_stage
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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(L, "MANUAL_CHANCE", 0.0)
    monkeypatch.setattr(S, "NPC_FIND", 0.0)


def labels(turn):
    return [c.label for c in turn.all_choices]


def stand_at(world, me, town):
    world.unrelate(me, "located_in")
    world.relate(me, town, "located_in")


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def test_a_poison_is_bought_from_a_poison_valleys_keeper(game):
    world, me = game.world, game.player.id
    clan = of_type(world, "unorthodox_clan")
    seat = halls.seat_of(world, clan)
    stand_at(world, me, seat)
    [keeper] = halls.staff_at(world, clan, seat, roles=("keeper",))
    world.update_data(me, silver=100)
    assert f"Buy a poison ({S.POISON_PRICE} silver)" in labels(game.perform(Action("talk", keeper)))
    game.perform(Action("buy_poison", keeper))
    assert len(S.poisons_of(world, me)) == 1 and world.entity(me).data["silver"] == 100 - S.POISON_PRICE


def poisoner(game):
    world, me = game.world, game.player.id
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    stand_at(world, me, seat)
    vial = world.add_entity("treasure", "a vial of black lotus", {"kind": "poison", "value": 50, "used": False})
    world.relate(me, vial, "owns")
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    return sect, seat, leader, vial


def test_a_slipped_poison_kills_in_the_night_and_the_plot_bears_the_players_name(game):
    world, me = game.world, game.player.id
    sect, seat, leader, vial = poisoner(game)
    assert "Slip poison into their tea" in labels(game.perform(Action("talk", leader)))
    game.perform(Action("slip_poison", leader))
    assert world.entity(leader).data.get("dead") and world.entity(vial).data["used"]
    [plot] = P.plots_of(world, sect, ("murder",))
    assert plot.data["plotter"] == me and plot.data["target"] == leader and game.focus is None
    assert world.entity(sect).data["poisoned"] == plot.id  # whispers of poison: the seat is in doubt


def test_an_exposed_poisoner_is_cast_out_hunted_and_named(game):
    world, me = game.world, game.player.id
    sect, seat, leader, vial = poisoner(game)
    world.relate(me, sect, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    game.perform(Action("talk", leader))
    game.perform(Action("slip_poison", leader))
    [plot] = P.plots_of(world, sect, ("murder",))
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    commit(world, P.exposed_events(world, plot, elder, seat))
    assert F.membership(world, me, sect)[1]["status"] == "expelled"
    assert world.facts(predicate="poisoner", subject=me)
    assert law.bounty(world, seat, me) >= 100


def test_a_sworn_follower_can_be_sent_to_spy_and_reports(game):
    world, me = game.world, game.player.id
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    stand_at(world, me, seat)
    follower = founding.make_person(world, "test:follower", seat, occupation="wandering swordsman", age=25,
                                    sworn_to=me)
    world.update_data(me, silver=200)
    label = f"Send {world.entity(follower).name} to join the {world.entity(sect).name} in secret ({S.SPY_PRICE} silver)"
    assert label in labels(game.perform(Action("look")))
    game.perform(Action("plant_spy", (follower, sect)))
    [plot] = P.plots_of(world, sect, ("spy",))
    assert plot.data["plotter"] == follower and plot.data["patron"] == me
    assert C.role_in(world, follower, sect) == "disciple" and world.entity(follower).data["spy_of"] == me
    import systems.murder as M
    import random
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    commit(world, M.murder_events(world, sect, leader, elder, None, seat, random.Random(3)))
    [secret] = P.plots_of(world, sect, ("murder",))
    commit(world, P.season_events(world, lives.current_season(world)))
    assert me in world.entity(secret.id).data["known_by"]  # the spy told you


def test_silver_behind_a_claim_makes_a_puppet_that_remembers_you(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud = a_crisis(game)
    occurrence = SC.live(world, sect)
    world.update_data(me, silver=5000)
    price = S.fund_price(world, sect)
    label = f"Put silver behind {world.entity(keeper).name}'s claim ({price} silver)"
    assert label in labels(game.perform(Action("look")))
    game.perform(Action("fund_claim", (occurrence.id, keeper)))
    [plot] = P.plots_of(world, sect, ("puppet",))
    assert plot.data["plotter"] == me and plot.data["serves"] == keeper and world.entity(me).data["silver"] == 5000 - price
    crisis = SC.crisis_of(world.entity(occurrence.id))
    world.update_data(occurrence.id, data={**crisis, "sways": {str(v): {str(keeper): 5.0} for v in C.voters(world, sect)}})
    to_stage(world, occurrence, seat, "active")
    assert C.role_in(world, keeper, sect) == "leader"
    assert any(m.feeling == "grateful" for m in world.memories(keeper, about=me))


def test_false_evidence_casts_a_rival_out_or_points_back_at_you(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(me, silver=500)
    monkeypatch.setattr(S, "frame_chance", lambda world, player: 0.0)
    game.perform(Action("frame_rival", (occurrence.id, proud)))
    [failed] = P.plots_of(world, sect, ("frame",))
    assert failed.data["failed"] and SC.claimant(SC.crisis_of(world.entity(occurrence.id)), proud) is not None
    assert failed.data["clues"][0]["points_to"] == me
    monkeypatch.setattr(S, "frame_chance", lambda world, player: 1.0)
    game.perform(Action("frame_rival", (occurrence.id, keeper)))
    assert F.membership(world, keeper, sect)[1]["status"] == "expelled"
    assert SC.claimant(SC.crisis_of(world.entity(occurrence.id)), keeper) is None


def test_a_forged_will_names_whom_you_choose(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(me, silver=500)
    game.perform(Action("forge_will", (occurrence.id, proud)))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["will"]["state"] == "read" and crisis["will"]["names"] == proud
    [plot] = P.plots_of(world, sect, ("forgery",))
    assert plot.data["plotter"] == me


def test_the_camps_may_find_the_players_hand_in_a_plot(game, monkeypatch):
    monkeypatch.setattr(S, "NPC_FIND", 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(me, silver=500)
    game.perform(Action("forge_will", (occurrence.id, proud)))
    to_stage(world, occurrence, seat, "announced")
    [plot] = [world.entity(p.id) for p in world.entities("plot") if p.data["type"] == "forgery"]
    assert plot.data["state"] == "exposed" and world.facts(predicate="forger", subject=me)


def test_every_scheme_has_a_journal_line():
    for kind in ("poison_bought", "poison_slipped", "spy_sent", "claim_funded", "frame_paid", "forgery_paid"):
        assert kind in SUMMARIES, kind
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_scheming.py`
Expected: `ModuleNotFoundError: No module named 'systems.scheming'`.

- [ ] **Step 3: Write the new modules**

`systems/scheming.py`:
```python
"""The player as plotter (phase 4h spec 8): poison, a spy, a puppet, a frame, a forgery.

Each scheme makes a plot like any other: its clues are left, it can leak, and it can be exposed. When one of
the player's plots is exposed the deed is told (weight 3.0), the righteous judge it, the town sets a bounty,
and a sect the player belongs to casts them out.
"""

import systems.claimants as C
import systems.frames as R
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.succession_crisis as SC
from systems import factions as F
from systems.bodies import load_body
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.purse import silver_of
from systems.tournaments import alive
from world.events import Event, Witness, commit, effect, listen
from world.seed import rng_for

POISON_PRICE, SPY_PRICE, FRAME_PRICE, FORGE_PRICE = 50, 100, 100, 100
FUND_PER_POWER = 10
FRAME_BASE, FRAME_PER_WIT, FRAME_BOUNDS = 0.4, 0.1, (0.1, 0.8)
NPC_FIND = 0.15
SPY_SWAY = 0.15
DEEDS = {"murder": "poisoner", "spy": "spymaster", "frame": "framer", "forgery": "forger", "puppet": "puppet_master"}
OPEN = ("mourning", "canvass")


def _pay(world, player: int, amount: int) -> None:
    world.update_data(player, silver=silver_of(world, player) - amount)


def _wit(world, player: int) -> int:
    return load_body(world, player).physique["comprehension"]


# --- poison -------------------------------------------------------------------------------------------------

def poisons_of(world, player: int) -> list[int]:
    return [i for i in world.targets(player, "owns") if world.entity(i).kind == "treasure"
            and world.entity(i).data.get("kind") == "poison" and not world.entity(i).data.get("used")]


def buy_poison_block(world, player: int, npc: int) -> str | None:
    selling = [f for f, _, d in F.memberships(world, npc) if d.get("role") == "keeper"
               and d.get("status", "member") == "member" and world.entity(f).data.get("type") == "unorthodox_clan"
               and world.targets(npc, "located_in") == [world.entity(f).data.get("seat")]]
    if not selling:
        return "They sell no poisons."
    if silver_of(world, player) < POISON_PRICE:
        return f"A poison costs {POISON_PRICE} silver."
    return None


def buy_poison_events(world, player: int, npc: int, place: int) -> list[Event]:
    return [Event("poison_bought", (player, npc), place, {"silver": POISON_PRICE})]


@effect("poison_bought")
def _bought(world, event) -> None:
    player, seller = event.actors
    _pay(world, player, POISON_PRICE)
    world.update_data(seller, silver=silver_of(world, seller) + POISON_PRICE)
    item = world.add_entity("treasure", "a vial of black lotus", {"kind": "poison", "value": POISON_PRICE,
                                                                  "used": False})
    world.relate(player, item, "owns")


def poison_block(world, player: int, leader: int) -> str | None:
    if not poisons_of(world, player):
        return "You carry no poison."
    led = [f for f, _, d in F.memberships(world, leader) if d.get("role") == "leader"
           and d.get("status", "member") == "member" and world.entity(f).data.get("type") in F.STAFFED]
    if not led or world.entity(leader).data.get("is_player"):
        return "They are no sect's master."
    return None


def poison_events(world, player: int, leader: int, place: int) -> list[Event]:
    """Into their tea: they die in the night of an illness, and a murder plot bears the player's name."""
    faction = next(f for f, _, d in F.memberships(world, leader) if d.get("role") == "leader"
                   and d.get("status", "member") == "member")
    vial = poisons_of(world, player)[0]
    rng = rng_for(world.world_seed, f"scheme:poison:{player}:{leader}")
    return [Event("poison_slipped", (player, leader), place, {"faction": faction, "vial": vial}),
            Event("died", (leader, leader), place, {"cause": "illness", "world": True, "poisoned_by": player})] \
        + M.murder_events(world, faction, leader, player, None, place, rng)


@effect("poison_slipped")
def _slipped(world, event) -> None:
    vial = event.data["vial"]
    world.unrelate(event.actors[0], "owns", vial)
    world.update_data(vial, used=True)


# --- a spy of one's own ----------------------------------------------------------------------------------

def spy_block(world, player: int, follower: int, faction: int) -> str | None:
    if world.entity(follower).data.get("sworn_to") != player or not alive(world, follower):
        return "They are not sworn to you."
    if world.entity(faction).data.get("type") not in F.STAFFED or F.membership(world, follower, faction):
        return "They cannot join that sect in secret."
    if silver_of(world, player) < SPY_PRICE:
        return f"Setting them up costs {SPY_PRICE} silver."
    return None


def spy_events(world, player: int, follower: int, faction: int, place: int) -> list[Event]:
    key = f"spy:player:{follower}:{faction}"
    return [Event("spy_sent", (player, follower), place, {"faction": faction})] + \
        U.spy_events(world, faction, player, follower, key)


@effect("spy_sent")
def _sent(world, event) -> None:
    player, follower = event.actors
    faction = event.data["faction"]
    _pay(world, player, SPY_PRICE)
    world.relate(follower, faction, "member_of", 0, {"role": "disciple", "hall": 0, "merit": 0, "status": "member",
                                                    "secret": False})
    world.unrelate(follower, "located_in")
    world.relate(follower, world.entity(faction).data["seat"], "located_in")
    world.update_data(follower, sworn_to=None)


def _spy_reports(world, plot, n: int, rng) -> list[Event]:
    """The player's spy reports one hidden truth of their sect's plots each season (spec 8)."""
    patron = plot.data["patron"]
    if not (isinstance(patron, int) and world.entity(patron).data.get("is_player")):
        return []
    secrets = [p for p in P.plots_of(world, plot.data["faction"]) if p.id != plot.id and patron not in p.data["known_by"]]
    if not secrets:
        return []
    return [Event("spy_reported", (patron,), None, {"plot": rng.choice(sorted(secrets, key=lambda p: p.id)).id})]


@effect("spy_reported")
def _reported(world, event) -> None:
    P.learn(world, event.actors[0], world.entity(event.data["plot"]), 0.8, "told")


# --- backing a puppet -----------------------------------------------------------------------------------

def fund_price(world, faction: int) -> int:
    return FUND_PER_POWER * int(world.entity(faction).data.get("power", 50))


def fund_block(world, player: int, occurrence, claimant: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "Their camps are made; silver comes too late."
    if F.membership(world, player, crisis["faction"]):
        return "You cannot buy your own sect's seat from outside it."
    if SC.claimant(crisis, claimant) is None or claimant == player:
        return "They do not claim the seat."
    if any(p.data["type"] == "puppet" and p.data.get("occurrence") == occurrence.id
           for p in P.plots_of(world, crisis["faction"], ("puppet",))):
        return "Someone's silver is already behind a claimant here."
    if silver_of(world, player) < fund_price(world, crisis["faction"]):
        return f"Backing a claim here costs {fund_price(world, crisis['faction'])} silver."
    return None


def fund_events(world, player: int, occurrence, claimant: int) -> list[Event]:
    from systems.founding import my_sect
    patron = my_sect(world, player) or player
    price = fund_price(world, SC.crisis_of(occurrence)["faction"])
    return [Event("claim_funded", (player, claimant), occurrence.data["place"], {"silver": price})] + \
        U.puppet_events(world, occurrence, patron, claimant, f"puppet:player:{occurrence.id}", plotter=player)


@effect("claim_funded")
def _funded(world, event) -> None:
    _pay(world, event.actors[0], event.data["silver"])


@listen("crisis_settled")
def _grateful(world, event, event_id: int) -> None:
    """A puppet the player bought who wins remembers who paid (spec 8)."""
    for plot in P.plots_of(world, event.data["faction"], ("puppet",)):
        plotter = plot.data["plotter"]
        if plot.data["serves"] == event.data["winner"] and world.entity(plotter).data.get("is_player"):
            commit(world, [Event("puppet_thanks", (plotter, event.data["winner"]), event.place, {},
                                 witnesses=(Witness(event.data["winner"], "grateful", 0.8),))])


# --- a frame, and a forgery -----------------------------------------------------------------------------

def frame_chance(world, player: int) -> float:
    low, high = FRAME_BOUNDS
    return max(low, min(high, FRAME_BASE + FRAME_PER_WIT * (_wit(world, player) - 5)))


def frame_block(world, player: int, occurrence, rival: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "It is too late to plant anything now."
    if SC.claimant(crisis, rival) is None or rival == player:
        return "They do not claim the seat."
    if silver_of(world, player) < FRAME_PRICE:
        return f"False evidence costs {FRAME_PRICE} silver."
    return None


def frame_events(world, player: int, occurrence, rival: int) -> list[Event]:
    """100 silver of false evidence: it takes, and the rival is cast out; or it fails, and points at the player."""
    rng = rng_for(world.world_seed, f"scheme:frame:{occurrence.id}:{rival}")
    key = f"frame:player:{occurrence.id}:{rival}"
    events = [Event("frame_paid", (player, rival), occurrence.data["place"], {"silver": FRAME_PRICE})]
    if rng.random() < frame_chance(world, player):
        return events + R.frame_events(world, occurrence, player, rival, key, rng)
    crisis = SC.crisis_of(occurrence)
    return events + P.made_events(world, "frame", key, player, crisis["faction"], occurrence.data["place"],
                                  target=rival, clues=[P.clue("planted", player, at="quarters_of", owner=rival)],
                                  extra={"occurrence": occurrence.id, "crime": "stole_art", "failed": True})


@effect("frame_paid")
def _frame_paid(world, event) -> None:
    _pay(world, event.actors[0], event.data["silver"])


def forge_block(world, player: int, occurrence) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "The camps are made; a will now would fool no one."
    if (crisis.get("will") or {}).get("state") == "read":
        return "A will has been read; a second one would be laughed out of the hall."
    if silver_of(world, player) < FORGE_PRICE:
        return f"A scribe who will forge a master's hand costs {FORGE_PRICE} silver."
    return None


def forge_events(world, player: int, occurrence, names: int) -> list[Event]:
    return [Event("forgery_paid", (player,), occurrence.data["place"], {"silver": FORGE_PRICE})] + \
        R.forgery_events(world, occurrence, player, names, f"forgery:player:{occurrence.id}")


@effect("forgery_paid")
def _forgery_paid(world, event) -> None:
    _pay(world, event.actors[0], event.data["silver"])


# --- the spy's sway, and the NPCs who look into the player's plots -----------------------------------------

@listen("crisis_phase")
def _spies_and_suspicion(world, event, event_id: int) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    player = world.get_meta("player_id")
    rng = rng_for(world.world_seed, f"scheme:{occurrence.id}:{event.data['phase']}")
    camp = crisis.get("declared", {}).get(str(player))
    for spy in P.plots_of(world, crisis["faction"], ("spy",)):
        if spy.data["patron"] == player and camp is not None and event.data["phase"] in ("canvass",):
            voters = [v for v in C.voters(world, crisis["faction"]) if v != camp and not world.entity(v).data.get("is_player")]
            if voters:
                voter = rng.choice(voters)
                sways = {k: dict(v) for k, v in crisis.get("sways", {}).items()}
                sways.setdefault(str(voter), {})[str(camp)] = round(sways.get(str(voter), {}).get(str(camp), 0.0)
                                                                     + SPY_SWAY, 3)
                crisis = {**crisis, "sways": sways}
                world.update_data(occurrence.id, data=crisis)
    for plot in P.plots_of(world, crisis["faction"]):
        if plot.data["plotter"] != player or not [c for c in plot.data["clues"] if not c.get("lost")]:
            continue
        for c in SC.standing_claimants(world, SC.crisis_of(world.entity(occurrence.id))):
            if not world.entity(c["person"]).data.get("is_player") and rng.random() < NPC_FIND:
                commit(world, P.exposed_events(world, plot, c["person"], occurrence.data["place"]))
                break


# --- the player's plot exposed ----------------------------------------------------------------------------

@listen("plot_exposed")
def _player_exposed(world, event, event_id: int) -> None:
    plot = world.entity(event.data["plot"])
    plotter = plot.data["plotter"]
    if not world.entity(plotter).data.get("is_player") or plot.data.get("failed"):
        return
    commit(world, [Event("scheme_exposed", (plotter,), event.place, {"plot": plot.id, "deed": DEEDS[plot.data["type"]],
                                                                   "faction": plot.data["faction"]})])


@effect("scheme_exposed")
def _scheme_exposed(world, event) -> None:
    player, faction = event.actors[0], event.data["faction"]
    found = F.membership(world, player, faction)
    if found and found[1].get("status", "member") == "member":
        set_membership(world, player, faction, status="expelled")


@listen("scheme_exposed")
def _deed_told(world, event, event_id: int) -> None:
    player = event.actors[0]
    variant = make_variant(event.data["deed"], player, event.data["faction"], place=place_name(world, event.place))
    record_fact(world, player, event.data["deed"], event.data["faction"], place=event.place, source_event=event_id,
                weight=3.0, variant=variant)


_spy_year = P.SEASON_HOOKS["spy"]  # puppets' (imported above): a spy's year, and now the player's spy's report
P.SEASON_HOOKS["spy"] = lambda world, plot, n, rng: _spy_year(world, plot, n, rng) + _spy_reports(world, plot, n, rng)
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4h_task6.py`:
```python
"""Phase 4h, Task 6: the schemes in the clock, the law and the attitudes, the engine, the tales"""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def still(path: str) -> None:
    """A 4g test's fixture stills 4h's intrigue: they test the crisis alone."""
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    anchor = '    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)\n'
    if text.count(anchor) != 1:
        raise SystemExit(f"{path}: no single calm fixture")
    text = text.replace(anchor, anchor + "    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises\n")
    i = text.index("\n\n\n@pytest.fixture")
    text = text[:i] + "\nfrom tests.intrigue import still" + text[i:]
    file.write_text(text, encoding="utf-8", newline="\n")


edit('systems/world_clock.py', r'''import systems.legitimacy  # noqa: E402,F401  phase 4h: the supreme art, the founder's test, marriage, arbiters''', r'''import systems.legitimacy  # noqa: E402,F401  phase 4h: the supreme art, the founder's test, marriage, arbiters
import systems.scheming  # noqa: E402,F401  phase 4h: the player's own plots''')
edit('systems/law.py', r'''FINE_PER, WANTED, HUNTED = 20, 30, 50''', r'''FINE_PER, WANTED, HUNTED = 20, 30, 50
SCHEMES = frozenset({"poisoner", "spymaster", "framer", "forger", "puppet_master", "murdered"})  # 4h: 100 silver
SCHEME_WEIGHT = 5.0''')
edit('systems/law.py', r'''        elif fact.predicate == "crippled":
            weight = fact.weight''', r'''        elif fact.predicate == "crippled":
            weight = fact.weight
        elif fact.predicate in SCHEMES:
            weight = SCHEME_WEIGHT''')
edit('systems/attitude.py', r'''    "lied_about": -0.6, "owns_manual": 0.0, "paid_off": -0.1, "left_for_dead": -0.8, "is": 0.0,''', r'''    "lied_about": -0.6, "owns_manual": 0.0, "paid_off": -0.1, "left_for_dead": -0.8, "is": 0.0,
    "poisoner": -1.0, "murdered": -1.0, "framer": -0.8, "forger": -0.6, "spymaster": -0.6, "puppet_master": -0.5,
    "false_accusation": -0.3, "spy_exposed": -0.8,''')
edit('engine/intrigue.py', r'''import systems.puppets as U
import systems.succession_crisis as SC''', r'''import systems.puppets as U
import systems.scheming as S
import systems.succession_crisis as SC
from systems.founding import followers''')
edit('engine/intrigue.py', r'''        framed = self.player.data.get("framed") or {}''', r'''        for occurrence in self._crises_here():  # the schemes (spec 8)
            crisis = SC.crisis_of(occurrence)
            if S.forge_block(world, me, occurrence) is None:
                for c in SC.standing_claimants(world, crisis):
                    who = "yourself" if c["person"] == me else world.entity(c["person"]).name
                    extras.append(Choice(f"Have a will forged naming {who} ({S.FORGE_PRICE} silver)",
                                         Action("forge_will", (occurrence.id, c["person"]))))
            for c in SC.standing_claimants(world, crisis):
                if S.frame_block(world, me, occurrence, c["person"]) is None:
                    extras.append(Choice(f"Plant false evidence against {world.entity(c['person']).name} "
                                         f"({S.FRAME_PRICE} silver)", Action("frame_rival", (occurrence.id, c["person"]))))
                if S.fund_block(world, me, occurrence, c["person"]) is None:
                    extras.append(Choice(f"Put silver behind {world.entity(c['person']).name}'s claim "
                                         f"({S.fund_price(world, crisis['faction'])} silver)",
                                         Action("fund_claim", (occurrence.id, c["person"]))))
        for faction in self._seated_here():
            for follower in followers(world, me):
                if S.spy_block(world, me, follower, faction) is None:
                    extras.append(Choice(f"Send {world.entity(follower).name} to join the "
                                         f"{world.entity(faction).name} in secret ({S.SPY_PRICE} silver)",
                                         Action("plant_spy", (follower, faction))))
        framed = self.player.data.get("framed") or {}''')
edit('engine/intrigue.py', r'''        for kind, label in (("scribe", ASKS["scribe"]), ("false_witness", ASKS["false_witness"]), ("night", ASKS["seen"])):''', r'''        if S.buy_poison_block(world, me, npc.id) is None:
            extras.append(Choice(f"Buy a poison ({S.POISON_PRICE} silver)", Action("buy_poison", npc.id)))
        if S.poison_block(world, me, npc.id) is None:
            extras.append(Choice("Slip poison into their tea", Action("slip_poison", npc.id)))
        for kind, label in (("scribe", ASKS["scribe"]), ("false_witness", ASKS["false_witness"]), ("night", ASKS["seen"])):''')
append('engine/intrigue.py', r'''
    # --- the schemes (spec 8) ------------------------------------------------------------------------------

    def _scheme_target(self, target):
        occurrence_id, person = target if isinstance(target, tuple) else (None, None)
        return self._occurrence_here(occurrence_id), person

    def _do_forge_will(self, target):
        occurrence, names = self._scheme_target(target)
        if occurrence is None or (why := S.forge_block(self.world, self.player.id, occurrence)) is not None:
            return self._turn([(why if occurrence else "There is no crisis here.", "system")])
        return self._turn(self._commit_quiet(S.forge_events(self.world, self.player.id, occurrence, names)))

    def _do_frame_rival(self, target):
        occurrence, rival = self._scheme_target(target)
        if occurrence is None or (why := S.frame_block(self.world, self.player.id, occurrence, rival)) is not None:
            return self._turn([(why if occurrence else "There is no crisis here.", "system")])
        return self._turn(self._commit_quiet(S.frame_events(self.world, self.player.id, occurrence, rival)))

    def _do_fund_claim(self, target):
        occurrence, claimant = self._scheme_target(target)
        if occurrence is None or (why := S.fund_block(self.world, self.player.id, occurrence, claimant)) is not None:
            return self._turn([(why if occurrence else "There is no crisis here.", "system")])
        return self._turn(self._commit_quiet(S.fund_events(self.world, self.player.id, occurrence, claimant)))

    def _do_plant_spy(self, target):
        follower, faction = target if isinstance(target, tuple) else (None, None)
        if follower is None or (why := S.spy_block(self.world, self.player.id, follower, faction)) is not None:
            return self._turn([(why if follower is not None else "Send whom?", "system")])
        return self._turn(self._commit_quiet(S.spy_events(self.world, self.player.id, follower, faction, self.place.id)))

    def _do_buy_poison(self, npc):
        if self.focus != npc or (why := S.buy_poison_block(self.world, self.player.id, npc)) is not None:
            return self._turn([(why if self.focus == npc else "Speak with them first.", "system")])
        return self._turn(self._commit(S.buy_poison_events(self.world, self.player.id, npc, self.place.id)))

    def _do_slip_poison(self, npc):
        if self.focus != npc or (why := S.poison_block(self.world, self.player.id, npc)) is not None:
            return self._turn([(why if self.focus == npc else "Speak with them first.", "system")])
        lines = self._commit_quiet(S.poison_events(self.world, self.player.id, npc, self.place.id))
        self.focus = None  # they will not finish the conversation
        return self._turn(lines)
''')
append('narrate/intrigue_text.py', r'''

def _deed(predicate: str, words: str):
    def story(world, v, viewer) -> str:
        return cap(f"{who(world, v.get('actor'), viewer)} {words} {_faction(world, v.get('target'))}.")
    return story


SPECIAL_PHRASES.update({"poisoner": _deed("poisoner", "was exposed as the poisoner in"),
                        "spymaster": _deed("spymaster", "was exposed as the one who planted a spy in"),
                        "framer": _deed("framer", "was exposed as the one who framed a claimant of"),
                        "forger": _deed("forger", "was exposed as the forger of a will in"),
                        "puppet_master": _deed("puppet_master", "was exposed as the silver behind a claimant of")})


@outcome("poison_bought", body_facts=False)
def _poison_bought(world, event):
    return [f"{_name(world, event.actors[1])} wraps a small black vial in cloth and takes your silver without a word."], {}


@summary("poison_bought")
def _poison_bought_line(world, entry, names, place, other):
    return f"Bought a poison in {place}."


@outcome("poison_slipped", body_facts=False)
def _slipped(world, event):
    return [f"You pour the tea. {_name(world, event.actors[1])} drinks, and does not see the dawn."], {}


@summary("poison_slipped")
def _slipped_line(world, entry, names, place, other):
    return f"Poisoned {other}."


@outcome("spy_sent", body_facts=False)
def _spy_sent(world, event):
    return [f"{_name(world, event.actors[1])} bows, takes your silver, and goes to knock on the "
            f"{world.entity(event.data['faction']).name}'s gate as a stranger."], {}


@summary("spy_sent")
def _spy_sent_line(world, entry, names, place, other):
    return f"Sent {other} to spy for you."


@outcome("claim_funded", body_facts=False)
def _funded(world, event):
    return [f"Your silver goes quietly to {_name(world, event.actors[1])}'s camp."], {}


@summary("claim_funded")
def _funded_line(world, entry, names, place, other):
    return f"Put silver behind {other}'s claim."


@outcome("frame_paid", body_facts=False)
def _frame_paid(world, event):
    return ["The evidence is made, and placed where it will be found."], {}


@summary("frame_paid")
def _frame_paid_line(world, entry, names, place, other):
    return f"Paid for false evidence against {other}."


@outcome("forgery_paid", body_facts=False)
def _forgery_paid(world, event):
    return ["A scribe who owes no one anything copies the late master's hand, and a will is read out."], {}


@summary("forgery_paid")
def _forgery_paid_line(world, entry, names, place, other):
    return f"Had a will forged at {place}."


for kind in ("scheme_exposed", "puppet_thanks", "spy_reported", "framed_out", "plot_made"):
    @outcome(kind, body_facts=False)
    def _quiet_deed(world, event):
        return [], {}
''')
append('narrate/grammar/intrigue.toml', r'''
[poison_bought]
colour = "dim"
lines = ["#intrigue_air#"]

[poison_slipped]
colour = "red"
lines = ["#intrigue_air#"]

[spy_sent]
colour = "dim"
lines = ["#intrigue_air#"]

[claim_funded]
colour = "dim"
lines = ["#intrigue_air#"]

[frame_paid]
colour = "dim"
lines = ["#intrigue_air#"]

[forgery_paid]
colour = "dim"
lines = ["#intrigue_air#"]

[scheme_exposed]
colour = "red"
lines = ["#intrigue_air#"]

[puppet_thanks]
colour = "dim"
lines = ["#intrigue_air#"]

[plot_made]
colour = "dim"
lines = ["#intrigue_air#"]

[framed_out]
colour = "red"
lines = ["#intrigue_air#"]

[wed_for_seat]
colour = "dim"
lines = ["#intrigue_air#"]

[arbitrated]
colour = "default"
lines = ["#intrigue_air#"]

[arbiter_defied]
colour = "red"
lines = ["#intrigue_air#"]
''')
print("task 6 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4h_task6.py`
Expected: `task 6 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_scheming.py tests/test_intrigue_play.py`
Expected: `17 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the player plots - poison, a spy, a puppet, a frame, a forged will, and the price of being found out

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: The screens

The Succession block's "Found" and "Suspicions" (the player's clues only), "Your schemes" on the standing page with what could betray each, the scene brief's suspicions, and help.

**Files:**
- Create: `tests/test_intrigue_screens.py`
- Modify (by `.patches/4h_task7.py`): `engine/crisis_page.py`, `engine/standing_page.py`, `engine/game.py`, `narrate/brief.py`, `narrate/intrigue_text.py`

**Interfaces:**
- Consumes: Tasks 1-6: `P.found_by`, `P.suspicions`, `P.plots_of`, `clue_words`, `S.DEEDS`; 4g's `succession_lines`.
- Produces:
  - `engine/crisis_page.py`: `found_lines(world, player, faction)`, `scheme_lines(world, player)`.
  - `narrate/intrigue_text.intrigue_facts(world, town, player)`; the help line `examine body | accuse <name>`.

- [ ] **Step 1: Write the failing tests**

`tests/test_intrigue_screens.py`:
```python
import pytest

import systems.encounters as encounters
import systems.legitimacy as L
import systems.murder as M
import systems.plots as P
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.crisis_page import scheme_lines, succession_lines
from engine.game import Game
from narrate.brief import scene_brief
from systems.creation import CreationChoice
from tests.intrigue import still
from tests.test_intrigue_play import a_murder
from tests.test_scheming import poisoner
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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(L, "MANUAL_CHANCE", 0.0)


def texts(lines):
    return " | ".join(t for t, _ in lines)


def test_the_succession_block_shows_what_you_have_found_and_whom_you_suspect(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, proud, plot = a_murder(game, monkeypatch)
    world.relate(me, sect, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    assert "Found:" not in texts(succession_lines(world, me))
    game.perform(Action("examine_body", SC.live(world, sect).id))
    text = texts(succession_lines(world, me))
    assert "Found:" in text and "on the late master's lips" in text
    assert f"Suspicions: {world.entity(proud).name} (1 thing)" in text


def test_your_schemes_are_listed_with_what_could_betray_them(game):
    world, me = game.world, game.player.id
    assert scheme_lines(world, me) == []
    sect, seat, leader, vial = poisoner(game)
    game.perform(Action("talk", leader))
    game.perform(Action("slip_poison", leader))
    text = texts(scheme_lines(world, me))
    assert "Your schemes:" in text and "The poisoning of" in text and "the body" in text
    assert "Your schemes:" in texts(game.perform(Action("standing")).lines)


def test_the_scene_brief_carries_your_suspicions(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, proud, plot = a_murder(game, monkeypatch)
    game.perform(Action("examine_body", SC.live(world, sect).id))
    brief = scene_brief(world, seat, me, "t")
    assert any(f"You suspect {world.entity(proud).name}" in fact for fact in brief.facts)


def test_help_names_the_investigation(game):
    assert any("examine body | accuse <name>" in t for t, _ in game.perform(Action("help")).lines)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_intrigue_screens.py`
Expected: `ImportError: cannot import name 'scheme_lines' from 'engine.crisis_page'`.

- [ ] **Step 3: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4h_task7.py`:
```python
"""Phase 4h, Task 7: what you found and suspect, your schemes, help, the brief's suspicions"""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def still(path: str) -> None:
    """A 4g test's fixture stills 4h's intrigue: they test the crisis alone."""
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    anchor = '    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)\n'
    if text.count(anchor) != 1:
        raise SystemExit(f"{path}: no single calm fixture")
    text = text.replace(anchor, anchor + "    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises\n")
    i = text.index("\n\n\n@pytest.fixture")
    text = text[:i] + "\nfrom tests.intrigue import still" + text[i:]
    file.write_text(text, encoding="utf-8", newline="\n")


edit('engine/crisis_page.py', r'''        trial = crisis.get("trial") or {}
        if trial.get("pending"):''', r'''        lines += found_lines(world, player, fid)
        trial = crisis.get("trial") or {}
        if trial.get("pending"):''')
append('engine/crisis_page.py', r'''

def found_lines(world, player: int, faction: int) -> list[Line]:
    """What the player has found in this faction's plots, and whom it points at (phase 4h spec 11)."""
    import systems.plots as P
    from narrate.intrigue_text import clue_words
    lines: list[Line] = []
    suspects: dict[int, int] = {}
    for plot in P.plots_of(world, faction):
        poison = next((c.get("poison") for c in plot.data["clues"] if c["kind"] == "body"), None)
        for c in P.found_by(world, plot, player):
            lines.append((f"  Found: {clue_words(world, c['kind'], c['points_to'], player, poison)}.", "dim"))
            suspects[c["points_to"]] = suspects.get(c["points_to"], 0) + 1
    if suspects:
        said = [f"{world.entity(p).name} ({n} {'thing' if n == 1 else 'things'})" for p, n in
                sorted(suspects.items(), key=lambda kv: -kv[1])]
        lines.append((f"  Suspicions: {', '.join(said)}", "dim"))
    return lines


def scheme_lines(world, player: int) -> list[Line]:
    """The player's own open plots, and what could betray each (spec 11)."""
    import systems.plots as P
    mine = [world.entity(p) for p in P.open_plots(world)
            if player in (world.entity(p).data["plotter"], world.entity(p).data["patron"])]
    if not mine:
        return []
    lines: list[Line] = [("", "default"), ("Your schemes:", "heading")]
    words = {"body": "the body", "witness": "a witness", "motive": "letters", "silver": "the silver",
             "envoy": "your envoy", "night": "a witness", "mark": "a mark", "seal": "the seal",
             "scribe": "the scribe", "planted": "the evidence", "false_witness": "the witness", "missing": "a missing witness"}
    for plot in mine:
        risks = sorted({words.get(c["kind"], c["kind"]) for c in plot.data["clues"] if not c.get("lost")})
        lines.append((f"  {plot.name[:1].upper()}{plot.name[1:]}: could be betrayed by {', '.join(risks) or 'nothing'}",
                      "dim"))
    return lines
''')
edit('engine/standing_page.py', r'''    from engine.crisis_page import succession_lines  # phase 4g: the seats in contest
    lines += succession_lines(world, player)''', r'''    from engine.crisis_page import scheme_lines, succession_lines  # phase 4g: the seats in contest; 4h: schemes
    lines += succession_lines(world, player)
    lines += scheme_lines(world, player)''')
edit('engine/game.py', r'''    ("  claim | declare <name> | search chambers | step down: a sect's succession (see standing, F6)", "system"),''', r'''    ("  claim | declare <name> | search chambers | step down: a sect's succession (see standing, F6)", "system"),
    ("  examine body | accuse <name>: what a crisis hides; your schemes are on the standing page", "system"),''')
edit('narrate/brief.py', r'''    from narrate.crisis_text import crisis_facts  # a sect's seat in contest here (phase 4g)
    facts += crisis_facts(world, place_id, player_id)''', r'''    from narrate.crisis_text import crisis_facts  # a sect's seat in contest here (phase 4g)
    facts += crisis_facts(world, place_id, player_id)
    from narrate.intrigue_text import intrigue_facts  # what the player suspects here (phase 4h)
    facts += intrigue_facts(world, place_id, player_id)''')
append('narrate/intrigue_text.py', r'''

def intrigue_facts(world, town: int, player: int) -> list[str]:
    """The player's suspicions of those at this seat, for the scene's brief (spec 11)."""
    import systems.plots as P
    facts = []
    for faction in world.entity(town).data.get("seats", []):
        for suspect, kinds in P.suspicions(world, player, faction).items():
            facts.append(f"You suspect {_name(world, suspect)} of a hidden crime against the "
                         f"{world.entity(faction).name} ({len(kinds)} {'thing points' if len(kinds) == 1 else 'things point'} at them).")
    return facts
''')
print("task 7 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4h_task7.py`
Expected: `task 7 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_intrigue_screens.py tests/test_crisis_screens.py tests/test_standing_page.py`
Expected: `15 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: intrigue screens - what you have found, whom you suspect, your schemes, the brief's suspicions, help

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 8: Intrigue far away, and end to end

Far summaries (spec 10): an exposed plotter cannot win, a puppet is weighed up, and an ambitious claimant of a great sect may pass the founder's test (ruling 11). The fork guide's section 9, the speed of the plot hooks and of a turn, and a plotting heir played at random through forced crises.

**Files:**
- Create: `tests/test_intrigue_fuzz.py`
- Create: `tests/test_intrigue_season.py`
- Modify (by `.patches/4h_task8.py`): `systems/succession_crisis.py`, `systems/plots.py`, `systems/legitimacy.py`, `docs/world-events.md`

**Interfaces:**
- Consumes: Everything above.
- Produces:
  - `P.exposed_plotters(world, f) -> set[int]`, `P.puppet_served(world, f) -> set[int]`, `L.far_founder(world, f, standing, rng) -> int | None`; `SC._summarised` reads them.
  - `docs/world-events.md` section 9; `tests/test_intrigue_fuzz.py`: `test_a_plotting_heir`.

- [ ] **Step 1: Write the failing tests**

`tests/test_intrigue_fuzz.py`:
```python
"""A plotting heir, played at random through poisoned masters, puppets, forgeries and frames (phase 4h):
nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing


@pytest.mark.parametrize("seed", [5, 21])
def test_a_plotting_heir(tmp_path, seed, monkeypatch):
    import systems.claimants as C
    import systems.frames as R
    import systems.lives as lives
    import systems.murder as M
    import systems.puppets as U
    import systems.succession_crisis as SC
    import systems.world_events as W
    from systems import factions as F
    from systems import founding, halls
    from world.events import Event, commit
    monkeypatch.setitem(W.TYPES, "succession_crisis", {**W.TYPES["succession_crisis"],
                                                       "stages": {**W.TYPES["succession_crisis"]["stages"],
                                                                  "announced": 4, "active": 8, "aftermath": 3}})
    monkeypatch.setattr(M, "MURDER_CHANCE", 1.0)
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    monkeypatch.setattr(U, "PUPPET_CHANCE", 0.5)
    monkeypatch.setattr(R, "FORGE_CHANCE", 0.5)
    monkeypatch.setattr(R, "FRAME_CHANCE", 0.3)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Plotter{seed}", world_seed=seed)
    world = app.game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    me = world.get_meta("player_id")
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    world.update_data(me, silver=20000)
    founding.make_person(world, f"fuzz:follower:{seed}", seat, occupation="wandering swordsman", age=25, sworn_to=me)
    vial = world.add_entity("treasure", "a vial of black lotus", {"kind": "poison", "value": 50, "used": False})
    world.relate(me, vial, "owns")
    app.submit("look")

    def a_leader_falls(world):
        """The seat falls empty by a natural death (a poisoning, most often), and a crisis begins here."""
        if SC.live(world, sect) is not None:
            return
        for leader in C.staff(world, sect, ("leader",)):
            if world.entity(leader).data.get("is_player"):
                return
            commit(world, [Event("died", (leader, leader), seat, {"cause": "illness", "world": True})])
        claims = C.declare(world, sect, None)
        if len(claims) >= 2:
            commit(world, SC.begin_events(world, sect, lives.current_season(world), "suspicion", claims, None,
                                          force=True))
    happened = set()
    for step in range(300):
        game = app.game
        if game is None:
            break
        if step % 25 == 0 and game.world.get_meta("player_id") == me and game.focus is None and game.combat is None:
            a_leader_falls(game.world)
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.6 and app.choices:
            stay = [n for n, c in enumerate(app.choices, 1) if c.action.verb not in ("travel", "routes")]
            app.submit(str(rng.choice(stay or [1])))
        else:
            app.submit(rng.choice(["claim", "examine body", "standing", "look", "rest", "journal", "sky",
                                   "accuse " + rng.choice("abcdefghijklmnopqrstuvwxyz"), "meditate week"]))
        if rng.random() < 0.05:
            app.handle_key("f6", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    assert {"plot_made", "crisis_settled"} <= happened, happened
    app.shutdown()
```

`tests/test_intrigue_season.py`:
```python
import gc
import random
import time
from pathlib import Path

import pytest

import systems.encounters as encounters
import systems.legitimacy as L
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from tests.intrigue import still
from tests.test_crisis_contest import a_crisis
from tests.test_intrigue_play import a_murder
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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(L, "MANUAL_CHANCE", 0.0)


def average(fn, n=10) -> float:
    """CPU time per call, averaged: Windows' CPU clock ticks in 15.6 ms steps (4e ruling 19)."""
    fn()
    gc.collect()
    start = time.process_time()
    for _ in range(n):
        fn()
    return (time.process_time() - start) / n


def test_the_fork_guide_covers_succession_intrigue():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("open_plots", "RED_HERRING", "ACCUSE_CLUES", "EXPOSE_HOOKS", "MURDER_CHANCE", "PUPPET_CHANCE",
                 "SPY_CHANCE", "FORGE_CHANCE", "RETURN_SEASONS", "ART_KNOWN", "TEST_BOUNDS", "ARBITER_CHANCE",
                 "check_plots", "still(monkeypatch)"):
        assert word in guide, word


def test_the_plot_hooks_stay_cheap_with_fifty_open_plots(game):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    for i in range(50):
        commit(world, P.made_events(world, "murder", f"speed:{i}", elder, sect, seat, target=leader,
                                    clues=[P.clue("body", elder), P.clue("motive", elder, at="quarters")]))
    assert len(P.open_plots(world)) == 50
    n = lives.current_season(world)
    assert average(lambda: P.season_events(world, n)) < 0.005


def test_a_turn_at_a_seat_with_plots_costs_little(game, monkeypatch):
    world = game.world
    sect, seat, proud, plot = a_murder(game, monkeypatch)
    assert average(lambda: game.perform(Action("look"))) < 0.05


def test_far_away_an_exposed_plotter_cannot_win_and_a_puppet_is_weighed_up(game, monkeypatch):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    elders = halls.staff_at(world, sect, seat, roles=("elder",))
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    commit(world, P.made_events(world, "forgery", "far:test", elders[0], sect, seat, target=sect,
                                clues=[P.clue("seal", elders[0])]))
    [plot] = P.plots_of(world, sect, ("forgery",))
    commit(world, P.exposed_events(world, plot, None, seat))
    assert P.exposed_plotters(world, sect) == {elders[0]}
    for _ in range(3):  # whatever the rolls, the stained never win
        standing = [{"person": elders[0], "kind": "elder"}, {"person": elders[1], "kind": "elder"}]
        commit(world, [SC.Event("crisis_summarised", (), seat, {"faction": sect, "season": random.randrange(10 ** 6),
                                                                 "cause": "close", "leader": leader,
                                                                 "claimants": standing})])
        assert C_role(world, elders[0], sect) != "leader"


def C_role(world, person, faction):
    import systems.claimants as C
    return C.role_in(world, person, faction)


def test_far_away_the_founders_hall_may_choose(game, monkeypatch):
    monkeypatch.setattr(L, "NPC_TRY", 1.0)
    monkeypatch.setattr(L, "test_chance", lambda world, person: 1.0)
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    elders = halls.staff_at(world, sect, seat, roles=("elder",))
    world.update_data(elders[1], traits=["proud"])
    world.update_data(elders[0], traits=["kind"])
    standing = [{"person": e, "kind": "elder"} for e in elders]
    assert L.far_founder(world, sect, standing, random.Random(1)) == elders[1]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_intrigue_fuzz.py tests/test_intrigue_season.py`
Expected: 3 failed, 4 passed: the fork guide (`AssertionError: open_plots`), `L.far_founder` and `P.exposed_plotters` missing (`AttributeError`); the two speed tests and both fuzz seeds already pass.

- [ ] **Step 3: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4h_task8.py`:
```python
"""Phase 4h, Task 8: plots and the founder's hall far away, the fork guide's section 9"""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def still(path: str) -> None:
    """A 4g test's fixture stills 4h's intrigue: they test the crisis alone."""
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    anchor = '    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)\n'
    if text.count(anchor) != 1:
        raise SystemExit(f"{path}: no single calm fixture")
    text = text.replace(anchor, anchor + "    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises\n")
    i = text.index("\n\n\n@pytest.fixture")
    text = text[:i] + "\nfrom tests.intrigue import still" + text[i:]
    file.write_text(text, encoding="utf-8", newline="\n")


edit('systems/succession_crisis.py', r'''    standing = standing_claimants(world, crisis)
    if not standing:
        return
    weakest = min(realm_of(world, c["person"]) for c in standing)
    weights = [1 + FAR_PROOF * len(C.proofs(world, crisis, c)) + FAR_REALM * (realm_of(world, c["person"]) - weakest)
               for c in standing]
    winner = rng.choices([c["person"] for c in standing], weights=weights)[0]''', r'''    from systems.legitimacy import far_founder  # phase 4h: plots and the founder's hall count far away too
    from systems.plots import exposed_plotters, puppet_served
    stained = exposed_plotters(world, faction)
    standing = [c for c in standing_claimants(world, crisis) if c["person"] not in stained]
    if not standing:
        return
    weakest = min(realm_of(world, c["person"]) for c in standing)
    backed = puppet_served(world, faction)
    weights = [1 + FAR_PROOF * len(C.proofs(world, crisis, c)) + FAR_REALM * (realm_of(world, c["person"]) - weakest)
               + (1 if c["person"] in backed else 0) for c in standing]
    winner = far_founder(world, faction, standing, rng) or \
        rng.choices([c["person"] for c in standing], weights=weights)[0]
''')
edit('systems/plots.py', r'''def clue(kind: str, points_to: int, **more) -> dict:''', r'''def exposed_plotters(world, faction: int) -> set[int]:
    """Plotters whose plots against this faction were exposed: far away, they cannot win its seat (spec 10)."""
    return {p.data["plotter"] for p in world.entities("plot") if p.data["faction"] == faction
            and p.data["state"] == "exposed"}


def puppet_served(world, faction: int) -> set[int]:
    return {p.data["serves"] for p in plots_of(world, faction, ("puppet",))}


def clue(kind: str, points_to: int, **more) -> dict:''')
edit('systems/legitimacy.py', r'''def _npc_tries(world, occurrence, stage: str) -> None:''', r'''def far_founder(world, faction: int, standing: list[dict], rng) -> int | None:
    """Far away, an ambitious claimant of a great sect may try the founder's test, and passing wins (spec 10)."""
    if not great(world, faction):
        return None
    for c in sorted(standing, key=lambda c: c["person"]):
        if C.ambitious(world, c["person"]) and rng.random() < NPC_TRY and rng.random() < test_chance(world, c["person"]):
            return c["person"]
    return None


def _npc_tries(world, occurrence, stage: str) -> None:''')
append('docs/world-events.md', r'''
## 9. Succession intrigue (phase 4h)

A hidden truth is a `plot` entity: `type` one of `murder`, `puppet`, `spy`, `frame`, `forgery`; its plotter,
patron, target, faction and the claimant it serves; its `clues` (each pointing at a person, some deliberately
false: `RED_HERRING`); who knows it (`known_by`); its `state` (`open`, `exposed`, `buried`, `cold`, `void`); and a
secret fact of its truth (recorded with `spread = False`). The meta row `open_plots` lists the open ones: the
seasonal hooks (leaks, burial, `COLD_SEASONS`, each type's own) read only it.

**Where the rules live:**
- `systems/plots.py`: the model, clues, `suspicions`, `accuse_events` (two clues: `ACCUSE_CLUES`), exposure and
  `EXPOSE_HOOKS`, `SEASON_HOOKS`, `BEGUN_HOOKS`, the leaks (`LEAK_CHANCE`), burial (`BURY_CHANCE`), the quarters
  search, and `contest_exposures` (NPCs who know speak before the elders).
- `systems/murder.py`: `MURDER_CHANCE`, `motives`, `POISONS`, the body, the witness, the letters.
- `systems/puppets.py`: `PUPPET_CHANCE`, the gift-sways, the lent fighter, the pocket (`in_pocket`); cult spies
  (`SPY_CHANCE`, `THEFT_CHANCE`).
- `systems/frames.py`: `FORGE_CHANCE`, `FRAME_CHANCE`, exile (`exiles`, `RETURN_SEASONS`) and the return.
- `systems/legitimacy.py`: the supreme art (`ART_KNOWN`), the founder's test (`TEST_BOUNDS`, `TEST_DEATH`),
  marriage (`MARRY_CHANCE`), arbitration (`ARBITER_CHANCE`, `DEFY_CHANCE`), an outsider (`OUTSIDER_CHANCE`).
- `systems/scheming.py`: the player's poison, spy, puppet, frame and forgery, and their exposure (`DEEDS`).

**Saved state:** on a faction, `poisoned` (a murder's plot until its crisis begins), `pocket`, `supreme_art`,
`art_manual`, `heir_since`, `outsider`; on a person, `spy_of`, `framed`, `searched`; the meta rows `open_plots` and
`exiles`.

**Tests:** `tests/intrigue.py`'s `still(monkeypatch)` stills every intrigue for tests of what came before it.

**The rules:** `check_plots` in `debug/invariants.py` holds the index to the open plots, the plots' people real,
every clue pointing at its plotter (unless marked false), spies members of the sect they spy on, exposed plotters
struck from the claims, and exiles with a return to come.
''')
print("task 8 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4h_task8.py`
Expected: `task 8 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_intrigue_season.py tests/test_intrigue_fuzz.py`
Expected: `7 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Run the 500-year soak**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: intrigue far away and end to end - the stained never win, puppets weighed, the founder's hall, the guide, speed, fuzz

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Self-review

- **Spec coverage:**
  - §2 the plot, its index and hooks (Task 1; the spy's year Task 2; returns Task 3), §3 clues, accusation, exposure (Task 1; the NPC rule at the contest Task 1);
  - §4 the poisoned master (Task 1), §5.1 puppets and §5.2 spies (Task 2), §6 forgery, framing and the return (Task 3);
  - §7 the supreme art, the founder's test, marriage, arbitration, the outsider (Task 4);
  - §8 the player's schemes (Task 6), the investigation's actions (Task 5), §9 knowledge (Tasks 1, 7), §10 far away (Tasks 1-4, 8);
  - §11 screens (Tasks 5, 7), §12 `check_plots` (Tasks 1-3), §13 testing (every task; the fuzz and the speed in Task 8).
- **Dry run:**
  - every task was applied in order to a copy of master; its tests failed as each Step 2 says, then passed;
  - the whole suite passed after every task, and the 500-year soak passed at the end.
