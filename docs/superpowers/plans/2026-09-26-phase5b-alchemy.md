# Phase 5b: Alchemy, Medicine and Poison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The player learns herbs, discovers recipes by experiment, refines pills, and lives with what they do to the body: residue, active poison, the poison path and the Myriad Poison Body.

**Architecture:**
- **The body** gains `residue`, `venom`, `poisons`, `resist`, `baths` and `breakthrough_aid`.
  - Poison and residue run lazily in `world.body.settle`, as healing already does.
  - `systems/toxins.py` holds sealing, forcing out, antidotes and death by poison.
  - Its registries `WOUND_HOOKS` and `ABSORB_HOOKS` sit at the top of the module, ahead of the circular import.
- **Herbs** (`systems/data/herbs.toml`) and **base recipes** (`systems/data/recipes.toml`) are tables.
  - Herb and pill items are entities.
  - A recipe is known through a `knows_recipe` relation whose value is its mastery.
- **Each concern is its own module:** `herbs`, `alchemy`, `pills`, `poison_path`. The player's part is `AlchemyMixin` (`engine/alchemy.py`).

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-phase5b-alchemy-design.md`

## Global Constraints

- **Save format:** no save-format version change.
  - The body's new fields have defaults, so an old body loads as it was.
  - New state lives in:
    - `herb`, `pill`, `recipe` and `furnace` entities;
    - the person's `herb_lore`, `alchemy_xp`, `alchemy_hints` and `venom_coat`;
    - town data `herbs_sold`;
    - the meta row `poisoned`.
- **Knowledge vs truth:**
  - a herb's properties are shown once tasted or used;
  - a poison's grade only when it was taken knowingly;
  - a recipe's needs once discovered.
- **Reads never write:** pages, briefs and choices never make herbs, pills or recipes. The one exception is a world's recipe entity, which is made when first discovered or first known.
- **One effect per event kind:** new modules `@listen` or register hooks. Existing effects are never re-registered.
- **Seeded rolls stay where they were:**
  - new rolls (gathering, refining, venomous beasts, baths) use their own seeded streams;
  - no art element is added to the random choices.
- **Speed (CPU time, averaged after `gc.collect()`):**
  - an experiment or a refining under 5 ms;
  - the poison watch over 20 poisoned NPCs under 50 ms a season;
  - the refine choices with 30 herbs and 6 recipes under 50 ms;
  - the 500-year soak keeps its limits.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A poison that outlasts you during a long action (a week's rest, a journey):** you die when the action's turn is done, not midway, and a long rest does not outwait the death. Task 6 pins it with `test_a_poison_that_outlasts_you_is_your_death` and `test_a_poison_death_waits_for_the_deed_to_end`.
2. **A body full of residue:** pills are dulled, and past 60 they risk deviation. Task 1 pins it with `test_a_body_full_of_residue_risks_deviation_and_its_meridians`; Task 4 with `test_a_qi_pill_gives_energy_dulled_by_residue`.
3. **A Myriad Poison Body struck bare-handed:** it shrugs off lesser poisons, and the striker is poisoned. Task 5 pins it with `test_a_poison_body_shrugs_off_lesser_poisons_and_its_blood_poisons`.
4. **A 4d treasure herb in the furnace:** it counts as a herb of the table and is still sold as a treasure. Task 2 pins it with `test_a_won_herb_is_a_herb_of_the_table`.
5. **Random play through gathering, buying, tasting, experimenting, refining and swallowing:** no crash, no rule broken. Task 7 pins it with `test_a_wandering_alchemist`.

## Plan-time rulings (deviations from the spec, argued)

1. **The Poison Body is the existing `Myriad Poison Body` constitution** (2's table already has it). *Cost if wrong:* none.
2. **4d and 4f prize herbs stay treasures,** sellable as they were, and count as herbs of the table (`herbs.herb_info`: a thousand-year herb is grade 3, any other grade 2). Making them herb entities broke 4d's and 4f's rules and sales. *Cost if wrong:* none visible.
3. **Poison arts come only from an unorthodox clan keeper's manual** (300 silver). Adding `poison` to the random art elements would have reshuffled every seeded art in every world. *Cost if wrong:* poison arts are rarer among NPCs.
4. **A venomous beast replaces 3% of ordinary beast encounters in marsh and forest** (`encounters.BEAST_HOOKS`). It is not an extra roll on every road, which would have skewed 4d's beast tide. *Cost if wrong:* venomous beasts are rarer.
5. **A breakthrough pill adds `0.1 × potency` to the next breakthrough's chance** (capped at 0.95), spent on the attempt. A bottleneck is where a breakthrough begins, so there is none to "remove". *Cost if wrong:* none.
6. **A furnace cracks on the worst failing rolls:** the top `chance × 0.1` of rolls. The spec's "a roll below a tenth of the chance" would have been a success. *Cost if wrong:* none.
7. **Poison and residue run lazily in `settle`.** A strong poison that outlasts the body while active marks it `poisoned to death`, so a long action cannot outwait the death. *Cost if wrong:* none.
8. **Death by poison is checked once per turn,** through a new `_after_turn` hook that `Game.perform` calls. Mid-action checks killed the player halfway through an action that went on to read their place. *Cost if wrong:* a death lands at the end of the action, not its middle.
9. **4h's bought vial counts as grade 4 and kills as before; a brewed poison below grade 4 only sickens** (4h's schemes keep their shape). *Cost if wrong:* none.
10. **A poison's grade is shown only when it was taken knowingly** (tasting, fumes, swallowing), marked `named`. Antidotes and forcing out do not reveal it in 5b. *Cost if wrong:* the grade stays hidden longer.
11. **Every town has a herbalist, and an apothecary's furnace rents for 20 silver.** *Cost if wrong:* none.
12. **The recipe arithmetic:**
    - a polarity is balanced when the herbs' net is within 1;
    - an element of `none` counts as its own element;
    - no two base recipes share an element and a polarity;
    - discovery follows from the herbs alone, so the same herbs always give the same answer (no season seed).
    - *Cost if wrong:* none.
13. **`check_alchemy` does not require venom ≥ 60 of a Myriad Poison Body,** since the constitution can be born. *Cost if wrong:* none.
14. **Three latent faults the fuzz reached once 5b's choices moved its paths:**
    - 4g's "Step down in favour of" named successors the player never heard of (now filtered like 5a's claimants);
    - 4a let an 8-year-old of second-rate realm take an apprentice (`agendas.MASTER_AGE = 20`);
    - the tournament fuzz harness read a dead player's place.
    - *Cost if wrong:* none.

## Files

| File | Responsibility |
|---|---|
| `systems/toxins.py` | Residue, active poison, sealing, forcing out, antidotes, death by poison; `WOUND_HOOKS`, `ABSORB_HOOKS`. |
| `systems/data/herbs.toml`, `systems/herbs.py` | The herb table, herb lore, tasting, gathering, the herbalist, furnaces. |
| `systems/data/recipes.toml`, `systems/alchemy.py` | Base recipes, experiments, refining, mastery, the alchemy level, pills made. |
| `systems/pills.py` | Pills swallowed, residue left, venom on a blade. |
| `systems/poison_path.py` | The poison path, the Myriad Poison Body, venomous beasts, tempering baths. |
| `engine/alchemy.py`, `engine/alchemy_page.py` | `AlchemyMixin`: choices, menus, handlers; the alchemy page and the sheet's note. |
| `narrate/alchemy_text.py`, `narrate/grammar/alchemy.toml` | Outcomes, journal lines, the Poison Body's tale. |

Existing files touched: `world/body.py`, `systems/world_clock.py`, `systems/mortality.py`, `systems/duel.py`, `systems/cultivation.py`, `systems/scheming.py`, `systems/encounters.py`, `systems/attitude.py`, `systems/agendas.py`, `debug/invariants.py`, `engine/game.py`, `engine/hooks.py`, `engine/commands.py`, `engine/sheet.py`, `engine/crisis.py`, `narrate/outcomes.py`, `docs/world-events.md`, and the tests `test_fuzz.py`.

**How each task is laid out:**
1. The tests, as whole new files.
2. The red run.
3. The new modules, as whole files.
4. One patch script, `.patches/5b_taskN.py`, holding the task's edits to existing files (including files made by earlier tasks). Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: The body's toxins: residue and active poison

The body gains the gauges `residue` and `venom`, a list of active `poisons`, `resist`, `baths` and `breakthrough_aid`. Residue fades in `settle` (twice as fast for a pure pill's leavings) and, above 60, risks deviation and, above 90, a meridian. An active poison ebbs each unsealed watch and does one internal injury a day; a grade-4 or stronger poison that outlasts realm + 2 days kills (ruling 7). Sealing acupoints (realm 1+) holds a poison for 4 watches; forcing it out (realm 3+) costs 10 qi. NPCs carrying a poison are indexed in the meta row `poisoned`, so only they are looked at each season. `check_toxins` joins the rules.

**Files:**
- Create: `systems/toxins.py`
- Create: `tests/test_toxins.py`
- Modify (by `.patches/5b_task1.py`): `debug/invariants.py`, `systems/mortality.py`, `systems/world_clock.py`, `world/body.py`

**Interfaces:**
- Consumes: 2's `world.body` (`Body`, `settle`, `add_injury`), `systems.bodies.load_body/save_body`; 4a's `mortality.death_events`, `lives.SEASON_HOOKS`; `world.seed.rng_for`.
- Produces:
  - `world.body`: `Body.residue`, `Body.venom`, `Body.poisons` (`[{grade, strength, source, since, sealed_until, named}]`), `Body.resist`, `Body.baths`, `Body.breakthrough_aid`; `RESIDUE_FADE_PER_WEEK`, `LETHAL_POISON`, `POISONED_TO_DEATH`.
  - `toxins` (X): `WOUND_HOOKS`, `ABSORB_HOOKS` (at the top of the module), `DULL`, `DEVIATION_AT`, `MERIDIAN_AT`, `LETHAL_GRADE`, `SEAL_REALM`, `SEAL_WATCHES`, `FORCE_REALM`, `FORCE_QI`; `dulling(body)`, `leave_residue(body, grade, purity, rng) -> [problems]`, `poison(world, p, grade, strength, source) -> str`, `add_poison(world, p, body, grade, strength, source) -> 'resisted' | 'absorbed' | 'poisoned'`, `worst(body)`, `lethal(body)`, `seal_block/seal_events`, `force_block/force_events`, `cure(world, p, grade) -> int`, `death_events(world, p)`, `season_hook(world, n)`, `days_to_death(body, poison)`, `residue_rng(world, p, salt)`; events `acupoints_sealed`, `poison_forced`.
  - `mortality.CAUSES['poisoned']`; `debug.invariants.check_toxins(world)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_toxins.py`:
```python
import random

import pytest

import systems.toxins as X
from debug.invariants import check_toxins
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import WATCHES_PER_DAY
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:tox:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def later(world, watches):
    world.set_time(world.time + watches)


def set_realm(world, person, realm):
    body = load_body(world, person)
    body.realm = realm
    body.energy_years = {0: 0.0, 1: 1.0, 2: 5.0, 3: 20.0}[realm]
    save_body(world, person, body)


def test_residue_dulls_pills_and_fades_with_time(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    assert X.dulling(body) == 1.0
    X.leave_residue(body, 3, 0.4, random.Random(1))
    assert body.residue == pytest.approx(18.0) and X.dulling(body) == pytest.approx(1 - 18 / 150)
    save_body(world, me, body)
    later(world, 7 * WATCHES_PER_DAY)
    assert load_body(world, me).residue < 18.0


def test_a_body_full_of_residue_risks_deviation_and_its_meridians(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.residue = 95.0
    harms = X.leave_residue(body, 1, 0.9, random.Random(4))
    assert set(harms) <= {"deviation", "meridian"}
    clean = load_body(world, me)
    assert X.leave_residue(clean, 1, 0.9, random.Random(4)) == []  # below the thresholds: no risk


def test_a_poison_spreads_does_harm_each_day_and_ebbs(game):
    world, me = game.world, game.player.id
    X.poison(world, me, 2, 2 * WATCHES_PER_DAY, "test")
    later(world, WATCHES_PER_DAY)
    body = load_body(world, me)
    [p] = body.poisons
    assert p["strength"] == WATCHES_PER_DAY and any(i.cause == "poison" for i in body.injuries)
    later(world, 2 * WATCHES_PER_DAY)
    assert load_body(world, me).poisons == []  # spent


def test_a_strong_poison_that_outlasts_the_body_kills(game):
    world = game.world
    victim = someone(game, "victim")
    X.poison(world, victim, 5, 20, "test")
    assert world.get_meta("poisoned") == [victim] and check_toxins(world) == []
    assert X.death_events(world, victim) == []
    later(world, 3 * WATCHES_PER_DAY + 1)  # a mortal lasts realm + 2 days
    [died] = X.death_events(world, victim)
    assert died.kind == "died" and died.data["cause"] == "poisoned"


def test_sealing_the_acupoints_halts_the_spread(game):
    world, me = game.world, game.player.id
    X.poison(world, me, 2, 10, "test")
    assert X.seal_block(load_body(world, me), world.time) is not None  # a mortal cannot seal
    set_realm(world, me, 1)
    assert X.seal_block(load_body(world, me), world.time) is None
    commit(world, X.seal_events(world, me, game.place.id))
    later(world, X.SEAL_WATCHES)
    assert load_body(world, me).poisons[0]["strength"] == 10  # nothing spread while sealed
    assert X.seal_block(load_body(world, me), world.time) is None  # the seal has lapsed


def test_a_master_forces_the_poison_out(game):
    world, me = game.world, game.player.id
    set_realm(world, me, 2)
    X.poison(world, me, 1, 10, "test")
    assert X.force_block(load_body(world, me)) == "Only a first-rate master can force a poison out."
    set_realm(world, me, 3)
    body = load_body(world, me)
    body.qi = 50.0
    save_body(world, me, body)
    assert X.force_block(load_body(world, me)) is None
    [forced] = X.force_events(world, me, game.place.id)
    assert forced.data["cleared"]
    commit(world, [forced])
    assert load_body(world, me).poisons == []


def test_an_antidote_cures_poisons_of_its_grade_or_less(game):
    world = game.world
    victim = someone(game, "cured")
    X.poison(world, victim, 2, 10, "a")
    X.poison(world, victim, 4, 10, "b")
    assert X.cure(world, victim, 3) == 1
    assert [p["grade"] for p in load_body(world, victim).poisons] == [4]
    assert X.cure(world, victim, 5) == 1 and world.get_meta("poisoned") == []


def test_a_resistant_body_lets_a_weak_poison_pass(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.resist = 2
    save_body(world, me, body)
    assert X.poison(world, me, 2, 10, "test") == "resisted" and load_body(world, me).poisons == []


def test_the_dead_leave_the_poisoned_index(game):
    world = game.world
    victim = someone(game, "gone")
    X.poison(world, victim, 5, 20, "test")
    later(world, 4 * WATCHES_PER_DAY)
    commit(world, X.season_hook(world, 1))
    assert world.entity(victim).data.get("dead")
    X.season_hook(world, 2)
    assert world.get_meta("poisoned") == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_toxins.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'systems.toxins'`.

- [ ] **Step 3: Write the new modules**

`systems/toxins.py`:
```python
"""What poisons the body (phase 5b spec 4.2, 4.5): pill residue, and active poison.

Residue is a gauge a pill leaves behind; it dulls later pills and, high, risks deviation and meridian damage.
It fades as time passes (`world.body.settle`). An active poison spreads watch by watch while unsealed, doing
internal harm each day, until it is spent, sealed away, forced out, cured - or, for a strong one that lasts,
kills. Poisons run lazily with the body; the meta row `poisoned` lists the NPCs carrying one, so only they are
looked at for a poison's death.
"""

import systems.lives as lives
import systems.world_clock as world_clock
from systems.bodies import load_body, save_body
from world.body import WATCHES_PER_DAY
from world.events import Event, effect
from world.seed import rng_for

DULL = 150.0            # a pill works at 1 - residue / 150
DEVIATION_AT, MERIDIAN_AT = 60.0, 90.0
DEVIATION_RISK, MERIDIAN_RISK = 15.0, 0.3
LETHAL_GRADE = 4        # a poison this strong kills if it outlasts realm + 2 days
SEAL_REALM, SEAL_WATCHES = 1, 4
FORCE_REALM, FORCE_QI = 3, 10.0


# --- residue -------------------------------------------------------------------------------------------

def dulling(body) -> float:
    return max(0.0, 1.0 - body.residue / DULL)


def leave_residue(body, grade: int, purity: float, rng) -> list[str]:
    """A pill's residue, and what a body already full of it risks (spec 4.5): the harms it did, in words."""
    before = body.residue
    body.residue = min(100.0, round(before + grade * (1 - purity) * 10, 3))
    harms = []
    if before > DEVIATION_AT and rng.random() < (before - DEVIATION_AT) / 40:
        body.deviation = min(100.0, body.deviation + DEVIATION_RISK)
        harms.append("deviation")
    if before > MERIDIAN_AT and rng.random() < MERIDIAN_RISK:
        open_ones = [m for m, v in body.meridians.items() if v.state == "open"]
        if open_ones:
            body.meridians[sorted(open_ones)[0]].state = "damaged"
            harms.append("meridian")
    return harms


# --- active poison ---------------------------------------------------------------------------------------

def poison(world, person: int, grade: int, strength: int, source: str) -> str:
    """Put a poison in someone's body; a resistance or immunity may let it pass. Returns what happened."""
    body = load_body(world, person)
    if grade <= body.resist:
        return "resisted"
    body.poisons = body.poisons + [{"grade": int(grade), "strength": int(strength), "days": 0.0,
                                    "at": world.time, "sealed_until": 0, "source": source}]
    save_body(world, person, body)
    if not world.entity(person).data.get("is_player"):
        listed = world.get_meta("poisoned") or []
        if person not in listed:
            world.set_meta("poisoned", listed + [person])
    return "poisoned"


def worst(body) -> dict | None:
    return max(body.poisons, key=lambda p: (p["grade"], p["strength"])) if body.poisons else None


def lethal(body) -> dict | None:
    """The poison that has outlasted this body: of grade 4 or more, past realm + 2 days (spec 4.2)."""
    return next((p for p in body.poisons if p["grade"] >= LETHAL_GRADE and p["days"] > body.realm + 2), None)


def seal_block(body, now: int) -> str | None:
    if not body.poisons:
        return "There is no poison in you."
    if body.realm < SEAL_REALM:
        return "You have not the qi to seal your own acupoints."
    if any((p.get("sealed_until") or 0) > now for p in body.poisons):
        return "Your acupoints are sealed already."
    return None


def seal_events(world, person: int, place) -> list[Event]:
    return [Event("acupoints_sealed", (person,), place, {"until": world.time + SEAL_WATCHES})]


@effect("acupoints_sealed")
def _sealed(world, event) -> None:
    body = load_body(world, event.actors[0])
    body.poisons = [{**p, "sealed_until": event.data["until"]} for p in body.poisons]
    save_body(world, event.actors[0], body)


def force_block(body) -> str | None:
    if not body.poisons:
        return "There is no poison in you."
    if body.realm < FORCE_REALM:
        return "Only a first-rate master can force a poison out."
    if body.qi < FORCE_QI:
        return "Your qi is too low to drive it out."
    return None


def force_events(world, person: int, place) -> list[Event]:
    body = load_body(world, person)
    target = worst(body)
    cleared = target["grade"] <= body.realm - 1
    return [Event("poison_forced", (person,), place, {"grade": target["grade"], "cleared": cleared})]


@effect("poison_forced")
def _forced(world, event) -> None:
    person, d = event.actors[0], event.data
    body = load_body(world, person)
    target = worst(body)
    if target is not None:
        rest = [p for p in body.poisons if p is not target]
        body.poisons = rest if d["cleared"] else rest + [{**target, "strength": max(1, target["strength"] // 2)}]
    body.qi = max(0.0, body.qi - FORCE_QI)
    save_body(world, person, body)
    _forget_if_clean(world, person, body)


def cure(world, person: int, grade: int) -> int:
    """An antidote of this grade: every poison of its grade or less is gone. Returns how many."""
    body = load_body(world, person)
    gone = [p for p in body.poisons if p["grade"] <= grade]
    body.poisons = [p for p in body.poisons if p["grade"] > grade]
    save_body(world, person, body)
    _forget_if_clean(world, person, body)
    return len(gone)


def _forget_if_clean(world, person: int, body) -> None:
    if not body.poisons:
        listed = world.get_meta("poisoned") or []
        if person in listed:
            world.set_meta("poisoned", [p for p in listed if p != person])


def death_events(world, person: int) -> list[Event]:
    """If a poison has outlasted this body: the death it brings (spec 4.2); else nothing."""
    body = load_body(world, person)
    if lethal(body) is None or world.entity(person).data.get("dead"):
        return []
    from systems.mortality import death_events as dying
    if world.entity(person).data.get("is_player"):
        return dying(world, person, "poisoned", None)
    return [Event("died", (person, person), lives.home(world, person), {"cause": "poisoned", "world": True})]


def season_hook(world, n: int) -> list[Event]:
    """The NPCs who carry a poison: those it has outlasted die; the clean leave the index."""
    events = []
    for person in list(world.get_meta("poisoned") or []):
        entity = world.entity(person)
        if entity is None or entity.data.get("dead"):
            world.set_meta("poisoned", [p for p in world.get_meta("poisoned") or [] if p != person])
            continue
        body = load_body(world, person)
        events += death_events(world, person)
        _forget_if_clean(world, person, body)
    return events


world_clock.SEASON_HOOKS.append(season_hook)


def days_to_death(body, poison_: dict) -> float | None:
    """How long the body has before this poison kills, if it can: for the sheet."""
    if poison_["grade"] < LETHAL_GRADE:
        return None
    left = body.realm + 2 - poison_["days"]
    return max(0.0, left) if poison_["strength"] / WATCHES_PER_DAY > left else None


def residue_rng(world, person: int, salt):
    return rng_for(world.world_seed, f"residue:{person}:{salt}")
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5b_task1.py`:
```python
"""Phase 5b, Task 1: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('debug/invariants.py', r'''    problems += check_gear(world)
''', r'''    problems += check_gear(world)
    problems += check_toxins(world)
''')
edit('debug/invariants.py', r'''        out.append(f"{who} deviation {body.deviation:.1f} outside 0..100")
''', r'''        out.append(f"{who} deviation {body.deviation:.1f} outside 0..100")
    for gauge in ("residue", "venom"):  # phase 5b
        if not 0 <= getattr(body, gauge) <= 100:
            out.append(f"{who} {gauge} {getattr(body, gauge):.1f} outside 0..100")
    for p in body.poisons:
        if not 1 <= p["grade"] <= 5 or p["strength"] <= 0:
            out.append(f"{who} carries a malformed poison {p}")
''')
edit('debug/invariants.py', r'''            out.append(f"manual #{manual.id} claims less than it holds")
''', r'''            out.append(f"manual #{manual.id} claims less than it holds")
    return out


def check_toxins(world) -> list[str]:
    """The poisoned index lists only living-or-dead NPCs, once each (phase 5b)."""
    listed = world.get_meta("poisoned") or []
    out = [] if len(listed) == len(set(listed)) else ["an NPC is listed twice as poisoned"]
    for person in listed:
        entity = world.entity(person)
        if entity is None or entity.kind != "person" or entity.data.get("is_player"):
            out.append(f"the poisoned index lists #{person}, no NPC")
''')
edit('systems/mortality.py', r'''          "founder_test": "in the founder's test"}
''', r'''          "founder_test": "in the founder's test", "poisoned": "of poison"}
''')
edit('systems/world_clock.py', r'''import systems.spoils  # noqa: E402,F401  phase 5a: what the fallen carried
''', r'''import systems.spoils  # noqa: E402,F401  phase 5a: what the fallen carried
import systems.toxins  # noqa: E402,F401  phase 5b: residue, and the poisons that kill the NPCs who carry them
''')
edit('world/body.py', r'''WATCHES_PER_DAY = 4
''', r'''WATCHES_PER_DAY = 4
RESIDUE_FADE_PER_WEEK, PURE_FADE = 2.0, 0.8  # residue fades twice as fast in a body purer than this (5b)
''')
edit('world/body.py', r'''    next_injury_id: int = 1
''', r'''    next_injury_id: int = 1
    residue: float = 0.0        # pill residue, 0-100 (phase 5b)
    venom: float = 0.0          # poison taken in along the poison path, 0-100
    poisons: list = field(default_factory=list)  # active poisons: {grade, strength, days, sealed_until, source}
    resist: int = 0             # poisons of this grade or less pass harmlessly (a beast's blood)
    baths: dict = field(default_factory=dict)    # physique stat -> times raised by a tempering bath
    breakthrough_aid: float = 0.0  # a breakthrough pill's help, spent on the next attempt
''')
edit('world/body.py', r'''    settled.qi = min(max_qi(settled), settled.qi + max_qi(settled) * QI_REGEN_PER_DAY * days)
    settled.settled_at = now
    return settled
''', r'''    fade = RESIDUE_FADE_PER_WEEK * (2 if settled.purity > PURE_FADE else 1) * days / 7
    settled.residue = max(0.0, round(settled.residue - fade, 3))
    _run_poisons(settled, now)
    settled.qi = min(max_qi(settled), settled.qi + max_qi(settled) * QI_REGEN_PER_DAY * days)
    settled.settled_at = now
    return settled


def _run_poisons(body: Body, now: int) -> None:
    """Poisons spread watch by watch while unsealed: strength ebbs, and each full day does internal harm (5b)."""
    left = []
    for p in body.poisons:
        start = max(p.get("at", body.settled_at), body.settled_at)
        active = max(0, now - max(start, min(now, p.get("sealed_until") or 0)))
        watches = min(active, p["strength"])
        days_before = p.get("days", 0.0)
        p = {**p, "strength": p["strength"] - watches, "days": days_before + watches / WATCHES_PER_DAY,
             "at": now}
        for day in range(int(days_before) + 1, int(p["days"]) + 1):
            add_injury(body, "torso", "internal", p["grade"], now, "poison")
        if p["strength"] > 0:
            left.append(p)
    body.poisons = left
''')
print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5b_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_toxins.py tests/test_body.py`
Expected: `18 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the body's toxins - pill residue that dulls and deviates, active poison that spreads, is sealed, forced out, or kills

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: Herbs: the table, lore, gathering and the herbalist

24 herbs, each with element, polarity, potency, toxicity, the terrains it grows in and an age grade (a year to a thousand years). A herb's properties are known once tasted or used; tasting a herb of toxicity 3+ poisons the taster. Herbs are gathered in the wild over 2 watches (a rare find may be guarded), bought from every town's herbalist (ruling 11, dearer where they do not grow), and a furnace is bought for 200 silver. A 4d/4f prize herb stays a treasure and counts as a herb of the table (ruling 2). The base recipes' table is staged here too, for Task 3.

**Files:**
- Create: `systems/data/herbs.toml`
- Create: `systems/data/recipes.toml`
- Create: `systems/herbs.py`
- Create: `tests/test_herbs.py`
- Modify (by `.patches/5b_task2.py`): `systems/world_clock.py`

**Interfaces:**
- Consumes: Task 1's `toxins.poison`; 4c's `market.drift`; 4d's treasure items (`prize`).
- Produces:
  - `systems/data/herbs.toml`, `systems/data/recipes.toml`.
  - `herbs` (H): `HERBS`, `AGES`, `AGE_PRICE`, `TASTE_POISON_AT`, `GATHER_GRADES`, `GUARD_CHANCE`, `GATHER_WATCHES`, `STOCK`, `LACKED`, `FURNACE_PRICE`, `FURNACE_RENT`; `props(name)`, `herb_name(name, grade)`, `make_herb(world, name, grade, owner, how='found') -> int`, `herb_info(item) -> (name, grade) | None`, `herbs_of(world, p)`, `known(world, p, name)`, `learn(world, p, names)`, `spend(world, p, items)`, `taste_block/taste_events`, `growing(terrain)`, `gather_block/gather_events`, `stock(world, town)`, `price(world, town, name, grade)`, `buy_block/buy_events(world, p, town, key)`, `furnace_of`, `furnace_block/furnace_events`, `prize_herb(prize_name)`; events `herb_tasted`, `herbs_gathered`, `herb_bought`, `furnace_bought`.

- [ ] **Step 1: Write the failing tests**

`tests/test_herbs.py`:
```python
import pytest

import systems.herbs as H
from engine.game import Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit
from world.gen.materialize import region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def test_every_herb_is_well_made_and_grows_somewhere():
    for name, h in H.HERBS.items():
        assert h["element"] in ("fire", "water", "wood", "metal", "earth", "poison", "none"), name
        assert h["polarity"] in ("yin", "yang", "balanced") and 1 <= h["potency"] <= 5 and 0 <= h["toxicity"] <= 5
        assert h["terrains"] and h["price"] > 0
    assert len(H.HERBS) >= 24
    for terrain in ("plains", "mountains", "river", "forest", "marsh", "hills"):
        assert H.growing(terrain), terrain


def test_tasting_teaches_a_herb_and_a_toxic_one_poisons(game):
    world, me = game.world, game.player.id
    mild = H.make_herb(world, "willow bark", 0, me)
    assert not H.known(world, me, "willow bark") and H.taste_block(world, me, mild) is None
    commit(world, H.taste_events(world, me, mild, game.place.id))
    assert H.known(world, me, "willow bark") and mild not in world.targets(me, "owns")
    assert load_body(world, me).poisons == []
    black = H.make_herb(world, "black lotus", 0, me)
    commit(world, H.taste_events(world, me, black, game.place.id))
    [p] = load_body(world, me).poisons
    assert p["grade"] == 5 and p["strength"] == 10


def test_gathering_finds_the_herbs_of_the_land(game):
    world, me, town = game.world, game.player.id, game.place.id
    terrain = region_of(world, town).data["terrain"]
    found, guarded, start = [], 0, world.time
    for _ in range(12):
        [event] = H.gather_events(world, me, town)
        commit(world, [event])
        found += event.data["found"]
        guarded += event.data["guarded"]
    assert found and all(f["herb"] in H.growing(terrain) for f in found)
    assert world.time == start + 12 * H.GATHER_WATCHES
    assert len(H.herbs_of(world, me)) == len(found)


def test_the_herbalist_sells_by_the_season_dearer_for_what_does_not_grow_here(game):
    world, me, town = game.world, game.player.id, game.place.id
    offers = H.stock(world, town)
    assert H.STOCK[0] <= len(offers) <= H.STOCK[1]
    terrain = region_of(world, town).data["terrain"]
    local = next(n for n in H.HERBS if terrain in H.HERBS[n]["terrains"])
    other = next(n for n in H.HERBS if terrain not in H.HERBS[n]["terrains"])
    assert H.price(world, town, other, 0) >= round(H.props(other)["price"] * H.LACKED * 0.9)
    assert H.price(world, town, local, 0) <= round(H.props(local)["price"] * 1.1) + 1
    world.update_data(me, silver=1000)
    offer = offers[0]
    commit(world, H.buy_events(world, me, town, offer["key"]))
    assert [h.data["herb"] for h in H.herbs_of(world, me)] == [offer["herb"]]
    assert offer["key"] not in {o["key"] for o in H.stock(world, town)}


def test_a_furnace_is_bought_once(game):
    world, me, town = game.world, game.player.id, game.place.id
    world.update_data(me, silver=H.FURNACE_PRICE)
    assert H.furnace_block(world, me) is None
    commit(world, H.furnace_events(world, me, town))
    assert H.furnace_of(world, me) is not None and silver_of(world, me) == 0
    assert H.furnace_block(world, me) == "You have a furnace already."


def test_a_treasure_race_herb_is_a_herb_of_the_table():
    assert H.prize_herb("a thousand-year ginseng") == ("ginseng", 3)
    assert H.prize_herb("a blood lotus") == ("blood lotus", 2)


def test_a_won_herb_is_a_herb_of_the_table(game):
    from systems.races import make_prize
    world, me = game.world, game.player.id
    item = make_prize(world, me, {"kind": "herb", "name": "a thousand-year ginseng", "value": 300}, 1)
    assert world.entity(item).kind == "treasure"  # still 4d's treasure, sold as one
    assert H.herb_info(world.entity(item)) == ("ginseng", 3) and world.entity(item) in H.herbs_of(world, me)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_herbs.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'systems.herbs'`.

- [ ] **Step 3: Write the new modules**

`systems/data/herbs.toml`:
```toml
# The herbs of the world (phase 5b spec 2.1): the same properties in every world.
# element: fire water wood metal earth poison none; polarity: yin yang balanced;
# potency and toxicity 1-5 and 0-5; terrains where it grows; price in silver for a year-old herb.

[ginseng]
element = "earth"
polarity = "yang"
potency = 4
toxicity = 0
terrains = ["mountains", "forest"]
price = 30

["blood lotus"]
element = "fire"
polarity = "yang"
potency = 4
toxicity = 1
terrains = ["marsh", "river"]
price = 35

["snow lingzhi"]
element = "water"
polarity = "yin"
potency = 4
toxicity = 0
terrains = ["mountains"]
price = 40

["dragon-bone moss"]
element = "metal"
polarity = "yang"
potency = 5
toxicity = 1
terrains = ["hills", "mountains"]
price = 50

["frost lotus leaf"]
element = "water"
polarity = "yin"
potency = 2
toxicity = 0
terrains = ["river", "marsh"]
price = 12

["red flame root"]
element = "fire"
polarity = "yang"
potency = 3
toxicity = 1
terrains = ["hills", "plains"]
price = 15

["jade bamboo heart"]
element = "wood"
polarity = "balanced"
potency = 2
toxicity = 0
terrains = ["forest", "river"]
price = 10

["iron thorn"]
element = "metal"
polarity = "yang"
potency = 2
toxicity = 1
terrains = ["hills", "plains"]
price = 8

["yellow earth tuber"]
element = "earth"
polarity = "balanced"
potency = 2
toxicity = 0
terrains = ["plains", "hills"]
price = 6

["moon dew grass"]
element = "water"
polarity = "yin"
potency = 1
toxicity = 0
terrains = ["plains", "river", "forest"]
price = 4

["sunfire pepper"]
element = "fire"
polarity = "yang"
potency = 1
toxicity = 0
terrains = ["plains", "hills"]
price = 4

["willow bark"]
element = "wood"
polarity = "yin"
potency = 1
toxicity = 0
terrains = ["river", "forest", "plains"]
price = 3

["seven-star grass"]
element = "wood"
polarity = "balanced"
potency = 3
toxicity = 0
terrains = ["forest", "mountains"]
price = 18

["silver needle leaf"]
element = "metal"
polarity = "yin"
potency = 2
toxicity = 0
terrains = ["mountains", "hills"]
price = 11

["tiger bone vine"]
element = "earth"
polarity = "yang"
potency = 3
toxicity = 0
terrains = ["mountains", "forest"]
price = 20

["heaven's dew orchid"]
element = "none"
polarity = "balanced"
potency = 3
toxicity = 0
terrains = ["mountains", "forest"]
price = 25

["black lotus"]
element = "poison"
polarity = "yin"
potency = 3
toxicity = 5
terrains = ["marsh"]
price = 30

["scorpion tail weed"]
element = "poison"
polarity = "yang"
potency = 2
toxicity = 4
terrains = ["plains", "hills"]
price = 14

["corpse flower"]
element = "poison"
polarity = "yin"
potency = 2
toxicity = 3
terrains = ["marsh", "forest"]
price = 12

["green viper moss"]
element = "poison"
polarity = "balanced"
potency = 1
toxicity = 3
terrains = ["forest", "marsh"]
price = 8

["ghost reed"]
element = "poison"
polarity = "yin"
potency = 1
toxicity = 2
terrains = ["marsh", "river"]
price = 5

["purple cloud fungus"]
element = "wood"
polarity = "yang"
potency = 3
toxicity = 1
terrains = ["forest", "hills"]
price = 16

["cold iron sand"]
element = "metal"
polarity = "yin"
potency = 3
toxicity = 2
terrains = ["mountains", "river"]
price = 18

["golden sun peach"]
element = "fire"
polarity = "balanced"
potency = 2
toxicity = 0
terrains = ["plains", "hills", "river"]
price = 9
```

`systems/data/recipes.toml`:
```toml
# The base recipes (phase 5b spec 3.1): each asks a dominant element and a polarity of its herbs, a total potency
# of at least `potency`, and a total toxicity of at most `toxicity` (or, for a poison, at least `toxic`).
# No two share an element and a polarity, so a batch of herbs can answer only one.

[earth_qi]
effect = "qi"
element = "earth"
polarity = "yang"
potency = 6
toxicity = 2

[fire_qi]
effect = "qi"
element = "fire"
polarity = "yang"
potency = 6
toxicity = 2

[bottleneck]
effect = "bottleneck"
element = "metal"
polarity = "yang"
potency = 8
toxicity = 3

[purity]
effect = "purity"
element = "none"
polarity = "balanced"
potency = 5
toxicity = 1

[wood_healing]
effect = "healing"
element = "wood"
polarity = "balanced"
potency = 4
toxicity = 1

[earth_healing]
effect = "healing"
element = "earth"
polarity = "balanced"
potency = 4
toxicity = 1

[mending]
effect = "mending"
element = "water"
polarity = "balanced"
potency = 6
toxicity = 1

[calming]
effect = "calming"
element = "water"
polarity = "yin"
potency = 3
toxicity = 0

[cleansing]
effect = "cleansing"
element = "wood"
polarity = "yin"
potency = 4
toxicity = 0

[metal_antidote]
effect = "antidote"
element = "metal"
polarity = "yin"
potency = 5
toxicity = 2

[pure_antidote]
effect = "antidote"
element = "none"
polarity = "yin"
potency = 4
toxicity = 1

[yin_poison]
effect = "poison"
element = "poison"
polarity = "yin"
potency = 3
toxic = 6

[yang_poison]
effect = "poison"
element = "poison"
polarity = "yang"
potency = 3
toxic = 6

[venom]
effect = "venom"
element = "poison"
polarity = "balanced"
potency = 2
toxic = 4

[fire_tempering]
effect = "tempering"
element = "fire"
polarity = "balanced"
potency = 5
toxicity = 2

[metal_tempering]
effect = "tempering"
element = "metal"
polarity = "balanced"
potency = 5
toxicity = 2
```

`systems/herbs.py`:
```python
"""Herbs (phase 5b spec 2): named plants of fixed properties, known by tasting, gathered, bought and won.

A herb is an entity (`kind = "herb"`): its table `name` and a `grade` of age (a year, ten, a hundred, a thousand).
Its properties belong to the name (`systems/data/herbs.toml`). The player sees them only once known: their
`herb_lore` lists the names they have tasted or used.
"""

import tomllib
from pathlib import Path

import systems.lives as lives
import systems.toxins as toxins
from systems.market import drift, event_factor
from systems.purse import silver_of
from world.events import Event, effect
from world.gen.materialize import region_of
from world.seed import rng_for

HERBS = tomllib.loads((Path(__file__).parent / "data" / "herbs.toml").read_text(encoding="utf-8"))
AGES = ("a year", "ten years", "a hundred years", "a thousand years")
AGE_PRICE = (1, 4, 20, 200)
TASTE_POISON_AT = 3        # toxicity at which tasting poisons
GATHER_BASE, GATHER_TRIES = 0.35, 2
GATHER_GRADES = (0.70, 0.25, 0.05)
GUARD_CHANCE = 0.5
GATHER_WATCHES = 2
STOCK = (4, 8)
LACKED = 1.5               # a herb that does not grow in the region costs this much more
FURNACE_PRICE, FURNACE_RENT = 200, 20


def props(name: str) -> dict:
    return HERBS[name]


def herb_name(name: str, grade: int) -> str:
    return f"{name} ({AGES[grade]})"


def make_herb(world, name: str, grade: int, owner: int | None, how: str = "found") -> int:
    item = world.add_entity("herb", herb_name(name, grade), {"herb": name, "grade": grade, "how": how})
    if owner is not None:
        world.relate(owner, item, "owns")
    return item


def herb_info(item) -> tuple[str, int] | None:
    """(name, grade) of a herb of the table: a gathered or bought herb, or a treasure race's herb (spec 2.3)."""
    if item is None or item.data.get("used"):
        return None
    if item.kind == "herb":
        return item.data["herb"], item.data["grade"]
    if item.kind == "treasure" and item.data.get("kind") == "herb":
        return prize_herb(item.name)
    return None


def herbs_of(world, person: int) -> list:
    return [e for e in (world.entity(i) for i in world.targets(person, "owns")) if herb_info(e) is not None]


def known(world, person: int, name: str) -> bool:
    return name in (world.entity(person).data.get("herb_lore") or [])


def learn(world, person: int, names) -> None:
    lore = list(world.entity(person).data.get("herb_lore") or [])
    new = [n for n in names if n not in lore]
    if new:
        world.update_data(person, herb_lore=lore + new)


def spend(world, person: int, items) -> None:
    for item in items:
        world.unrelate(person, "owns", item)
        world.update_data(item, used=True)


# --- tasting ---------------------------------------------------------------------------------------------

def taste_block(world, person: int, item_id: int) -> str | None:
    if herb_info(world.entity(item_id)) is None or item_id not in world.targets(person, "owns"):
        return "You have no such herb."
    return None


def taste_events(world, person: int, item_id: int, place) -> list[Event]:
    name = herb_info(world.entity(item_id))[0]
    return [Event("herb_tasted", (person,), place, {"item": item_id, "herb": name,
                                                     "toxicity": props(name)["toxicity"]})]


@effect("herb_tasted")
def _tasted(world, event) -> None:
    person, d = event.actors[0], event.data
    learn(world, person, [d["herb"]])
    spend(world, person, [d["item"]])
    if d["toxicity"] >= TASTE_POISON_AT:
        toxins.poison(world, person, d["toxicity"], d["toxicity"] * 2, f"tasting {d['herb']}")


# --- gathering -------------------------------------------------------------------------------------------

def growing(terrain: str) -> list[str]:
    return sorted(n for n, h in HERBS.items() if terrain in h["terrains"])


def gather_block(world, person: int, place: int) -> str | None:
    if world.entity(place).kind != "town":
        return "There is nothing to gather here."
    return None


def gather_events(world, person: int, place: int) -> list[Event]:
    """Half a day in the town's surroundings: 0-2 herbs of the land, one perhaps guarded (spec 2.3)."""
    from systems.bodies import load_body
    rng = rng_for(world.world_seed, f"gather:{person}:{world.time}")
    terrain = region_of(world, place).data["terrain"]
    insight = load_body(world, person).insight
    found = []
    for _ in range(GATHER_TRIES):
        if rng.random() < GATHER_BASE + min(0.3, insight / 200):
            roll = rng.random()
            grade = 0 if roll < GATHER_GRADES[0] else 1 if roll < GATHER_GRADES[0] + GATHER_GRADES[1] else 2
            found.append({"herb": rng.choice(growing(terrain)), "grade": grade})
    guarded = any(f["grade"] == 2 for f in found) and rng.random() < GUARD_CHANCE
    return [Event("herbs_gathered", (person,), place, {"found": found, "guarded": guarded,
                                                       "watches": GATHER_WATCHES})]


@effect("herbs_gathered")
def _gathered(world, event) -> None:
    for f in event.data["found"]:
        make_herb(world, f["herb"], f["grade"], event.actors[0], "gathered")
    from systems.time import advance
    advance(world, event.data["watches"])


# --- the herbalist ----------------------------------------------------------------------------------------

def stock(world, town: int) -> list[dict]:
    """This season's herbs at the herbalist's: {key, herb, grade}, less what was bought."""
    season = lives.current_season(world)
    rng = rng_for(world.world_seed, f"herbalist:{town}:{season}")
    terrain = region_of(world, town).data["terrain"]
    local, others = growing(terrain), sorted(set(HERBS) - set(growing(terrain)))
    out = []
    for n in range(rng.randint(*STOCK)):
        pool = local if rng.random() < 0.75 else others
        out.append({"key": f"h{n}", "herb": rng.choice(pool), "grade": 1 if rng.random() < 0.2 else 0})
    sold = (world.entity(town).data.get("herbs_sold") or {}).get(str(season), [])
    return [o for o in out if o["key"] not in sold]


def price(world, town: int, name: str, grade: int) -> int:
    terrain = region_of(world, town).data["terrain"]
    factor = 1.0 if terrain in props(name)["terrains"] else LACKED
    return max(1, round(props(name)["price"] * AGE_PRICE[grade] * factor * event_factor(world, town, "herbs")
                        * drift(world, town, "herbs")))


def buy_block(world, person: int, town: int, key: str) -> str | None:
    offer = next((o for o in stock(world, town) if o["key"] == key), None)
    if offer is None:
        return "The herbalist has nothing like that now."
    if silver_of(world, person) < price(world, town, offer["herb"], offer["grade"]):
        return "You cannot pay for it."
    return None


def buy_events(world, person: int, town: int, key: str) -> list[Event]:
    offer = next(o for o in stock(world, town) if o["key"] == key)
    return [Event("herb_bought", (person,), town, {**offer, "season": lives.current_season(world),
                                                    "price": price(world, town, offer["herb"], offer["grade"])})]


@effect("herb_bought")
def _bought(world, event) -> None:
    person, town, d = event.actors[0], event.place, event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    sold = world.entity(town).data.get("herbs_sold") or {}
    season = str(d["season"])
    world.update_data(town, herbs_sold={season: sold.get(season, []) + [d["key"]]})
    make_herb(world, d["herb"], d["grade"], person, "bought")


def furnace_of(world, person: int) -> int | None:
    return next((i for i in world.targets(person, "owns") if world.entity(i).kind == "furnace"
                 and not world.entity(i).data.get("cracked")), None)


def furnace_block(world, person: int) -> str | None:
    if furnace_of(world, person) is not None:
        return "You have a furnace already."
    if silver_of(world, person) < FURNACE_PRICE:
        return f"A furnace costs {FURNACE_PRICE} silver."
    return None


def furnace_events(world, person: int, town: int) -> list[Event]:
    return [Event("furnace_bought", (person,), town, {"price": FURNACE_PRICE})]


@effect("furnace_bought")
def _furnace(world, event) -> None:
    person = event.actors[0]
    world.update_data(person, silver=silver_of(world, person) - event.data["price"])
    item = world.add_entity("furnace", "a bronze furnace", {"cracked": False})
    world.relate(person, item, "owns")


# --- legendary herbs ---------------------------------------------------------------------------------------

def prize_herb(prize_name: str) -> tuple[str, int]:
    """A treasure race's herb as a herb of the table (spec 2.3): a thousand years old, or a hundred."""
    name = prize_name.removeprefix("a ").removeprefix("an ")
    grade = 3 if name.startswith("thousand-year ") else 2
    name = name.removeprefix("thousand-year ")
    return (name if name in HERBS else "ginseng"), grade
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5b_task2.py`:
```python
"""Phase 5b, Task 2: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.toxins  # noqa: E402,F401  phase 5b: residue, and the poisons that kill the NPCs who carry them
''', r'''import systems.toxins  # noqa: E402,F401  phase 5b: residue, and the poisons that kill the NPCs who carry them
import systems.herbs  # noqa: E402,F401  phase 5b: herbs, tasting, gathering, the herbalist
''')
print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5b_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_herbs.py`
Expected: `7 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: herbs - a table of 24, lore learned by tasting, gathering in the wild, the herbalist, and furnaces

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: Recipes, experiments and refining

Herbs combine into a mix: the potency-weighted dominant element, a polarity balanced within 1, the summed potency and toxicity. 16 base recipes each need an element, a polarity, a potency and a toxicity ceiling; no two share an element and polarity (ruling 12). An experiment (2 to 4 herbs, 2 watches) discovers the recipe it meets, hints at what it misses, or leaves a sludge whose fumes poison at toxicity 5+. Refining a known recipe succeeds by mastery and the alchemy level; surplus potency makes more pills and a higher grade; the worst tenth of failures cracks the furnace (ruling 6).

**Files:**
- Create: `systems/alchemy.py`
- Create: `tests/test_alchemy.py`
- Modify (by `.patches/5b_task3.py`): `systems/world_clock.py`

**Interfaces:**
- Consumes: Task 2's `herbs` (`props`, `herb_info`, `herbs_of`, `learn`, `spend`, `furnace_of`, `FURNACE_RENT`); Task 1's `toxins.poison`; 3a's `record_fact`.
- Produces:
  - `alchemy` (AL): `RECIPES`, `NEEDS`, `MIN_HERBS`, `MAX_HERBS`, `BALANCED`, `FUMES_AT`, `DISCOVERED_MASTERY`, `MASTERY_STEP`, `CHANCE_BOUNDS`, `CRACK_SHARE`, `WATCHES`, `HINTS`; `combine(names) -> mix`, `met(recipe, mix)`, `best_match(mix) -> (key | None, met)`, `recipe_entity(world, key) -> int`, `known_recipes(world, p) -> [(recipe, mastery)]`, `mastery`, `level(world, p)`, `furnace_block(world, p, place)`, `experiment_block/experiment_events(world, p, place, herb_ids)`, `refine_chance(world, p, recipe)`, `refine_block/refine_events(world, p, place, recipe, herb_ids)`, `make_pill(world, p, recipe, grade, purity) -> int`; events `experimented`, `refined`; relation `knows_recipe`.

- [ ] **Step 1: Write the failing tests**

`tests/test_alchemy.py`:
```python
import pytest

import systems.alchemy as A
import systems.herbs as H
from engine.game import Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit

# a batch of herbs that meets each base recipe: the table and the recipes agree
BATCHES = {
    "earth_qi": ["ginseng", "tiger bone vine"], "fire_qi": ["blood lotus", "red flame root"],
    "bottleneck": ["dragon-bone moss", "iron thorn", "iron thorn"], "purity": ["heaven's dew orchid"] * 2,
    "wood_healing": ["jade bamboo heart"] * 2, "earth_healing": ["yellow earth tuber"] * 2,
    "mending": ["snow lingzhi", "red flame root"], "calming": ["frost lotus leaf"] * 2,
    "cleansing": ["willow bark"] * 4, "metal_antidote": ["silver needle leaf", "silver needle leaf", "cold iron sand"],
    "pure_antidote": ["heaven's dew orchid", "heaven's dew orchid", "moon dew grass", "willow bark"],
    "yin_poison": ["black lotus", "corpse flower"], "yang_poison": ["scorpion tail weed"] * 2,
    "venom": ["green viper moss", "ghost reed"], "fire_tempering": ["golden sun peach"] * 3,
    "metal_tempering": ["iron thorn", "iron thorn", "silver needle leaf", "silver needle leaf"],
}


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    world, me = g.world, g.player.id
    world.update_data(me, silver=10000)
    yield g
    g.close()


def herbs(game, names, grade=0):
    return [H.make_herb(game.world, n, grade, game.player.id) for n in names]


def test_every_base_recipe_can_be_met_by_its_batch_and_only_it():
    assert set(BATCHES) == set(A.RECIPES)
    for key, names in BATCHES.items():
        assert A.MIN_HERBS <= len(names) <= A.MAX_HERBS
        found, needs = A.best_match(A.combine(names))
        assert found == key and all(needs.values()), key


def test_the_right_herbs_discover_a_recipe_and_a_pill(game):
    world, me = game.world, game.player.id
    batch = herbs(game, BATCHES["calming"])
    assert A.experiment_block(world, me, game.place.id, batch) is None
    [event] = A.experiment_events(world, me, game.place.id, batch)
    assert event.data["result"] == "discovered"
    commit(world, [event])
    recipe = A.recipe_entity(world, "calming")
    assert A.mastery(world, me, recipe) == A.DISCOVERED_MASTERY
    [pill] = [world.entity(i) for i in world.targets(me, "owns") if world.entity(i).kind == "pill"]
    assert pill.data["effect"] == "calming" and pill.data["grade"] == 1
    assert H.known(world, me, "frost lotus leaf") and silver_of(world, me) == 10000 - H.FURNACE_RENT


def test_three_needs_of_four_leave_a_hint(game):
    world, me = game.world, game.player.id
    batch = herbs(game, ["moon dew grass", "moon dew grass"])  # water and yin, but too weak to calm
    [event] = A.experiment_events(world, me, game.place.id, batch)
    assert event.data["result"] == "hint" and event.data["missed"] == "potency"
    commit(world, [event])
    assert "too weak" in world.entity(me).data["alchemy_hints"][0]


def test_a_toxic_sludge_poisons_its_maker(game):
    world, me = game.world, game.player.id
    batch = herbs(game, ["black lotus", "golden sun peach", "golden sun peach"])  # fire, yin: near nothing
    [event] = A.experiment_events(world, me, game.place.id, batch)
    assert event.data["result"] == "sludge" and event.data["fumes"]
    commit(world, [event])
    assert load_body(world, me).poisons


def test_the_same_herbs_give_the_same_answer(game):
    world, me = game.world, game.player.id
    one = A.experiment_events(world, me, game.place.id, herbs(game, BATCHES["venom"]))[0].data
    two = A.experiment_events(world, me, game.place.id, herbs(game, BATCHES["venom"]))[0].data
    assert (one["result"], one["recipe"]) == (two["result"], two["recipe"])


def test_refining_a_known_recipe_makes_pills_and_mastery(game, monkeypatch):
    world, me = game.world, game.player.id
    commit(world, A.experiment_events(world, me, game.place.id, herbs(game, BATCHES["earth_qi"])))
    recipe = A.recipe_entity(world, "earth_qi")
    batch = herbs(game, ["ginseng", "ginseng", "tiger bone vine"])
    assert A.refine_block(world, me, game.place.id, recipe, batch) is None
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (1.0, 1.0))
    [event] = A.refine_events(world, me, game.place.id, recipe, batch)
    assert event.data["success"] and event.data["count"] == 2  # potency 11 over a need of 6
    commit(world, [event])
    assert A.mastery(world, me, recipe) == pytest.approx(A.DISCOVERED_MASTERY + A.MASTERY_STEP)
    assert world.entity(me).data["alchemy_xp"] == event.data["grade"]
    assert event.data["purity"] == pytest.approx(0.4 + 0.5 * A.DISCOVERED_MASTERY)


def test_refining_needs_the_recipe_and_herbs_that_meet_it(game):
    world, me = game.world, game.player.id
    recipe = A.recipe_entity(world, "earth_qi")
    batch = herbs(game, ["ginseng", "tiger bone vine"])
    assert A.refine_block(world, me, game.place.id, recipe, batch) == "You do not know that recipe."
    world.relate(me, recipe, "knows_recipe", 0.1)
    weak = herbs(game, ["willow bark", "moon dew grass"])
    assert "will not make it" in A.refine_block(world, me, game.place.id, recipe, weak)


def test_a_bad_failure_cracks_the_furnace_and_burns(game, monkeypatch):
    world, me = game.world, game.player.id
    commit(world, H.furnace_events(world, me, game.place.id))
    recipe = A.recipe_entity(world, "earth_qi")
    world.relate(me, recipe, "knows_recipe", 0.1)
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (0.001, 0.001))  # all but hopeless: every failure is the worst
    monkeypatch.setattr(A, "CRACK_SHARE", 1e9)
    [event] = A.refine_events(world, me, game.place.id, recipe, herbs(game, ["ginseng", "tiger bone vine"]))
    assert not event.data["success"] and event.data["cracked"]
    commit(world, [event])
    assert H.furnace_of(world, me) is None  # cracked
    assert any(i.cause == "a cracked furnace" for i in load_body(world, me).injuries)


def test_the_alchemy_level_grows_with_experience(game):
    world, me = game.world, game.player.id
    assert A.level(world, me) == 0
    world.update_data(me, alchemy_xp=40)
    assert A.level(world, me) == 2
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_alchemy.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'systems.alchemy'`.

- [ ] **Step 3: Write the new modules**

`systems/alchemy.py`:
```python
"""Recipes, experiments and refining (phase 5b spec 3).

Herbs in the furnace sum to four properties: a dominant element, a polarity, a total potency and a total
toxicity. A base recipe (`systems/data/recipes.toml`) asks one of each; the herbs that meet all four discover it,
three of four leave a hint, fewer a sludge. A known recipe is refined with one roll on mastery, comprehension and
the alchemy level; each success raises both.
"""

import math
import tomllib
from pathlib import Path

import systems.herbs as H
import systems.toxins as toxins
from systems.bodies import load_body, save_body
from systems.purse import silver_of
from systems.time import advance
from world.body import add_injury
from world.events import Event, effect
from world.seed import rng_for

RECIPES = tomllib.loads((Path(__file__).parent / "data" / "recipes.toml").read_text(encoding="utf-8"))
NEEDS = ("element", "polarity", "potency", "toxicity")
MIN_HERBS, MAX_HERBS = 2, 4
BALANCED = 1               # a net polarity within this is balanced
FUMES_AT = 5               # a sludge this toxic poisons its maker
DISCOVERED_MASTERY, MASTERY_STEP = 0.1, 0.05
CHANCE_BOUNDS = (0.1, 0.95)
CRACK_SHARE = 0.1          # the worst tenth of the chance's failing rolls cracks the furnace (ruling 6)
WATCHES = 2
FIRST_WORDS = ("Azure", "Jade", "Golden", "Crimson", "Nine-Turn", "Heavenly", "Purple Cloud", "Silver Moon",
               "Black Tortoise", "White Crane", "Thousand-Year", "Spring Rain")
LAST_WORDS = {"qi": "Qi Pill", "bottleneck": "Breakthrough Pill", "purity": "Clear Marrow Pill",
              "healing": "Wound-Closing Pill", "mending": "Meridian-Mending Pill", "calming": "Heart-Calming Pill",
              "cleansing": "Cleansing Pill", "antidote": "Antidote", "poison": "Poison", "venom": "Blade Venom",
              "tempering": "Tempering Draught"}
HINTS = {"element": "the herbs lean to the wrong element", "polarity": "the balance of yin and yang is off",
         "potency": "the brew is too weak", "toxicity": "the brew is too toxic" }


# --- what herbs add up to -------------------------------------------------------------------------------------

def combine(names: list[str]) -> dict:
    """The four properties of these herbs together."""
    weights: dict[str, int] = {}
    net = 0
    for name in names:
        p = H.props(name)
        weights[p["element"]] = weights.get(p["element"], 0) + p["potency"]
        net += {"yang": 1, "yin": -1}.get(p["polarity"], 0) * p["potency"]
    element = max(sorted(weights), key=lambda e: weights[e])
    polarity = "balanced" if abs(net) <= BALANCED else ("yang" if net > 0 else "yin")
    return {"element": element, "polarity": polarity, "potency": sum(H.props(n)["potency"] for n in names),
            "toxicity": sum(H.props(n)["toxicity"] for n in names)}


def met(recipe: dict, mix: dict) -> dict[str, bool]:
    toxic = mix["toxicity"] >= recipe["toxic"] if "toxic" in recipe else mix["toxicity"] <= recipe["toxicity"]
    return {"element": mix["element"] == recipe["element"], "polarity": mix["polarity"] == recipe["polarity"],
            "potency": mix["potency"] >= recipe["potency"], "toxicity": toxic}


def best_match(mix: dict) -> tuple[str | None, dict]:
    """The base recipe these herbs come closest to, and which needs they meet."""
    scored = sorted(((sum(met(r, mix).values()), key) for key, r in RECIPES.items()), key=lambda s: (-s[0], s[1]))
    score, key = scored[0]
    return key, met(RECIPES[key], mix)


# --- recipes as knowledge ----------------------------------------------------------------------------------

def recipe_entity(world, key: str) -> int:
    """A world's recipe for this base: named once, the same entity for everyone who learns it."""
    path = f"recipe:{key}"
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    rng = rng_for(world.world_seed, path)
    base = RECIPES[key]
    name = f"{rng.choice(FIRST_WORDS)} {LAST_WORDS[base['effect']]}"
    return world.add_entity("recipe", name, {"key": key, **base}, path)


def known_recipes(world, person: int) -> list[tuple[int, float]]:
    return [(r, value) for r, value, _ in world.relations_from(person, "knows_recipe")]


def mastery(world, person: int, recipe: int) -> float | None:
    return next((v for r, v in known_recipes(world, person) if r == recipe), None)


def level(world, person: int) -> int:
    return int(math.floor(math.sqrt(world.entity(person).data.get("alchemy_xp", 0) / 10)))


# --- the furnace -------------------------------------------------------------------------------------------

def furnace_block(world, person: int, place) -> str | None:
    """One's own furnace, or an apothecary's to rent in a town."""
    if H.furnace_of(world, person) is not None:
        return None
    if world.entity(place).kind != "town":
        return "You need a furnace, or a town's apothecary to rent one."
    if silver_of(world, person) < H.FURNACE_RENT:
        return f"The apothecary's furnace costs {H.FURNACE_RENT} silver."
    return None


def _rent(world, person: int) -> int:
    return 0 if H.furnace_of(world, person) is not None else H.FURNACE_RENT


def _herbs_block(world, person: int, herb_ids) -> str | None:
    if not MIN_HERBS <= len(herb_ids) <= MAX_HERBS or len(set(herb_ids)) != len(herb_ids):
        return f"Put {MIN_HERBS} to {MAX_HERBS} herbs in the furnace."
    owned = set(world.targets(person, "owns"))
    if any(h not in owned or H.herb_info(world.entity(h)) is None for h in herb_ids):
        return "You have no such herbs."
    return None


# --- experimenting (spec 3.2) ---------------------------------------------------------------------------------

def experiment_block(world, person: int, place, herb_ids) -> str | None:
    return _herbs_block(world, person, herb_ids) or furnace_block(world, person, place)


def experiment_events(world, person: int, place, herb_ids) -> list[Event]:
    names = [H.herb_info(world.entity(h))[0] for h in herb_ids]
    mix = combine(names)
    key, needs = best_match(mix)
    score = sum(needs.values())
    grade = min(H.herb_info(world.entity(h))[1] for h in herb_ids) + 1
    result = "discovered" if score == len(NEEDS) else "hint" if score == len(NEEDS) - 1 else "sludge"
    missed = next((n for n in NEEDS if not needs[n]), None) if result == "hint" else None
    return [Event("experimented", (person,), place, {
        "herbs": list(herb_ids), "names": names, "mix": mix, "result": result,
        "recipe": key if result != "sludge" else None, "missed": missed, "grade": grade,
        "rent": _rent(world, person), "fumes": result == "sludge" and mix["toxicity"] >= FUMES_AT})]


@effect("experimented")
def _experimented(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["rent"])
    H.spend(world, person, d["herbs"])
    H.learn(world, person, d["names"])
    advance(world, WATCHES)
    if d["result"] == "discovered":
        recipe = recipe_entity(world, d["recipe"])
        if mastery(world, person, recipe) is None:
            world.relate(person, recipe, "knows_recipe", DISCOVERED_MASTERY)
        make_pill(world, person, recipe, d["grade"], 0.4 + 0.5 * DISCOVERED_MASTERY)
    elif d["result"] == "hint":
        hints = list(world.entity(person).data.get("alchemy_hints") or [])
        hint = f"{' + '.join(d['names'])}: {HINTS[d['missed']]}"
        if hint not in hints:
            world.update_data(person, alchemy_hints=(hints + [hint])[-20:])
    elif d["fumes"]:
        toxins.poison(world, person, min(5, d["mix"]["toxicity"] // 2), d["mix"]["toxicity"], "a furnace's fumes")


# --- refining (spec 3.3) --------------------------------------------------------------------------------------

def refine_chance(world, person: int, recipe: int) -> float:
    body = load_body(world, person)
    wit = body.physique.get("comprehension", 5)
    raw = 0.35 + 0.4 * (mastery(world, person, recipe) or 0.0) + 0.03 * (wit - 5) + 0.05 * level(world, person)
    return max(CHANCE_BOUNDS[0], min(CHANCE_BOUNDS[1], raw))


def refine_block(world, person: int, place, recipe: int, herb_ids) -> str | None:
    if mastery(world, person, recipe) is None:
        return "You do not know that recipe."
    why = _herbs_block(world, person, herb_ids) or furnace_block(world, person, place)
    if why:
        return why
    needs = met(RECIPES[world.entity(recipe).data["key"]], combine([H.herb_info(world.entity(h))[0] for h in herb_ids]))
    if not all(needs.values()):
        return f"These herbs will not make it: {HINTS[next(n for n in NEEDS if not needs[n])]}."
    return None


def refine_events(world, person: int, place, recipe: int, herb_ids) -> list[Event]:
    base = world.entity(recipe).data
    mix = combine([H.herb_info(world.entity(h))[0] for h in herb_ids])
    skill = mastery(world, person, recipe)
    chance = refine_chance(world, person, recipe)
    roll = rng_for(world.world_seed, f"refine:{person}:{recipe}:{world.time}").random()
    success = roll < chance
    grade = min(5, min(H.herb_info(world.entity(h))[1] for h in herb_ids) + 1 + (1 if skill >= 0.8 else 0))
    allowance = base.get("toxicity", mix["toxicity"])
    purity = max(0.0, min(1.0, round(0.4 + 0.5 * skill - 0.1 * max(0, mix["toxicity"] - allowance), 3)))
    count = 1 + min(2, max(0, (mix["potency"] - base["potency"]) // 3))
    return [Event("refined", (person,), place, {
        "recipe": recipe, "herbs": list(herb_ids), "names": [H.herb_info(world.entity(h))[0] for h in herb_ids],
        "success": success, "count": count if success else 0, "grade": grade, "purity": purity,
        "cracked": not success and roll > 1 - chance * CRACK_SHARE, "rent": _rent(world, person)})]


@effect("refined")
def _refined(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["rent"])
    H.spend(world, person, d["herbs"])
    H.learn(world, person, d["names"])
    advance(world, WATCHES)
    if d["success"]:
        for _ in range(d["count"]):
            make_pill(world, person, d["recipe"], d["grade"], d["purity"])
        skill = mastery(world, person, d["recipe"])
        world.relate(person, d["recipe"], "knows_recipe", round(min(1.0, skill + MASTERY_STEP), 3))
        world.update_data(person, alchemy_xp=world.entity(person).data.get("alchemy_xp", 0) + d["grade"])
    elif d["cracked"]:
        furnace = H.furnace_of(world, person)
        if furnace is not None:
            world.update_data(furnace, cracked=True)
        body = load_body(world, person)
        add_injury(body, "right arm", "bruise", 2, world.time, "a cracked furnace")
        save_body(world, person, body)


# --- pills ---------------------------------------------------------------------------------------------------

def make_pill(world, person: int, recipe: int, grade: int, purity: float) -> int:
    """A pill of this recipe (spec 4.1), carried by its maker."""
    base = world.entity(recipe)
    item = world.add_entity("pill", base.name, {"effect": base.data["effect"], "grade": int(grade),
                                                "purity": round(float(purity), 3), "recipe": recipe, "maker": person,
                                                "used": False})
    world.relate(person, item, "owns")
    return item
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5b_task3.py`:
```python
"""Phase 5b, Task 3: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.herbs  # noqa: E402,F401  phase 5b: herbs, tasting, gathering, the herbalist
''', r'''import systems.herbs  # noqa: E402,F401  phase 5b: herbs, tasting, gathering, the herbalist
import systems.alchemy  # noqa: E402,F401  phase 5b: experiments and refining
''')
print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5b_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_alchemy.py`
Expected: `9 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: alchemy - herbs combined, recipes discovered by experiment, pills refined by mastery

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: Pills swallowed, and venom on a blade

A pill's effect works at its grade times the body's dulling: qi (capped by the bottleneck), breakthrough aid (ruling 5), purity, healing, mending, calming, cleansing, antidote, resistance; a poison pill poisons. Every pill but poison leaves residue by grade and purity. A poison pill coats a blade for 3 strikes. A 4h bought vial counts as grade 4 and kills as before; a brewed poison below grade 4 only sickens its victim (ruling 9).

**Files:**
- Create: `systems/pills.py`
- Create: `tests/test_pills.py`
- Modify (by `.patches/5b_task4.py`): `systems/cultivation.py`, `systems/duel.py`, `systems/scheming.py`, `systems/toxins.py`, `systems/world_clock.py`

**Interfaces:**
- Consumes: Tasks 1-3: `toxins` (`dulling`, `leave_residue`, `poison`, `cure`, `WOUND_HOOKS`), `alchemy.make_pill`, `alchemy.RECIPES`; 2's `duel._exchange`, `cultivation` breakthrough chance; 4h's `scheming.poisons_of`.
- Produces:
  - `pills` (PL): `LEGACY_GRADE`, `PURITY`, `SWALLOWED`, `VENOM_STRIKES`, `POISON_STRENGTH`; `pills_of(world, p)`, `effect_of(item)`, `grade_of(item)`, `swallow_block/swallow_events(world, p, place, item)`, `coat_block/coat_events(world, p, place, item)`; events `pill_taken`, `blade_coated`; person data `venom_coat`.
  - `duel._blow(...)` returns `form`; `duel._exchange` calls `toxins.WOUND_HOOKS(world, hitter, target, form, hitter_body, target_body)`; `scheming.poison_grade`.

- [ ] **Step 1: Write the failing tests**

`tests/test_pills.py`:
```python
import pytest

import systems.alchemy as A
import systems.duel as duel
import systems.gear as gear
import systems.pills as P
import systems.toxins as X
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import add_injury
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def pill(game, effect, grade=2, purity=1.0):
    key = next(k for k, r in A.RECIPES.items() if r["effect"] == effect)
    return A.make_pill(game.world, game.player.id, A.recipe_entity(game.world, key), grade, purity)


def room_to_grow(game):
    """A second-rate body far from its bottleneck, so a qi pill's years all count."""
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years, body.bottleneck = 2, 6.0, False
    save_body(game.world, game.player.id, body)


def swallow(game, item):
    world, me = game.world, game.player.id
    assert P.swallow_block(world, me, item) is None
    commit(world, P.swallow_events(world, me, game.place.id, item))


def test_a_qi_pill_gives_energy_dulled_by_residue(game):
    world, me = game.world, game.player.id
    room_to_grow(game)
    before = load_body(world, me).energy_years
    swallow(game, pill(game, "qi", grade=2))
    after = load_body(world, me).energy_years
    assert after == pytest.approx(before + 1.0)
    body = load_body(world, me)
    body.residue = 75.0
    save_body(world, me, body)
    swallow(game, pill(game, "qi", grade=2))
    assert load_body(world, me).energy_years - after == pytest.approx(1.0 * (1 - 75 / 150), abs=0.05)


def test_a_pill_leaves_residue_by_its_impurity(game):
    world, me = game.world, game.player.id
    swallow(game, pill(game, "calming", grade=3, purity=0.5))
    assert load_body(world, me).residue == pytest.approx(15.0)


def test_a_treasure_pill_is_a_grade_two_qi_pill(game):
    world, me = game.world, game.player.id
    room_to_grow(game)
    item = world.add_entity("treasure", "a Nine-Turn Golden Pill", {"kind": "pill", "qi_years": 2.0, "used": False})
    world.relate(me, item, "owns")
    before = load_body(world, me).energy_years
    swallow(game, item)
    body = load_body(world, me)
    assert body.energy_years == pytest.approx(before + 2.0) and body.residue == pytest.approx(6.0)


def test_healing_mending_calming_cleansing_and_purity(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    add_injury(body, "left arm", "cut", 3, world.time, "test")
    body.meridians["Lung"].state = "damaged"
    body.deviation, body.residue = 40.0, 40.0
    save_body(world, me, body)
    heals = load_body(world, me).injuries[0].heals_at
    swallow(game, pill(game, "healing", grade=2))
    assert load_body(world, me).injuries[0].heals_at < heals
    swallow(game, pill(game, "mending", grade=2))
    assert load_body(world, me).meridians["Lung"].state == "open"
    swallow(game, pill(game, "calming", grade=2))
    assert load_body(world, me).deviation <= 40.0 - 10
    swallow(game, pill(game, "cleansing", grade=2))
    assert load_body(world, me).residue < 40.0
    purity = load_body(world, me).purity
    swallow(game, pill(game, "purity", grade=2))
    assert load_body(world, me).purity > purity


def test_a_breakthrough_pill_helps_the_next_attempt(game):
    world, me = game.world, game.player.id
    swallow(game, pill(game, "bottleneck", grade=3))
    assert load_body(world, me).breakthrough_aid == pytest.approx(0.3)


def test_an_antidote_cures_and_a_poison_poisons(game):
    world, me = game.world, game.player.id
    swallow(game, pill(game, "poison", grade=3))
    [p] = load_body(world, me).poisons
    assert p["grade"] == 3 and p["strength"] == 3 * P.POISON_STRENGTH
    swallow(game, pill(game, "antidote", grade=3))
    assert load_body(world, me).poisons == []


def test_venom_goes_on_a_blade_and_poisons_its_wounds(game):
    world, me = game.world, game.player.id
    venom = pill(game, "venom", grade=2)
    assert P.swallow_block(world, me, venom) == "Venom goes on a blade, not down the throat."
    if gear.weapon_of(world, me) is None:
        pytest.skip("a hand art")
    commit(world, P.coat_events(world, me, game.place.id, venom))
    assert world.entity(me).data["venom_coat"] == {"grade": 2, "strikes": 3}
    foe = world.add_entity("person", "A Foe", {"occupation": "bandit", "traits": ["greedy"], "realm": "mortal",
                                               "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:pill:foe")
    world.relate(foe, game.place.id, "located_in")
    form = duel.best_art(world, me).form
    target = load_body(world, foe)
    X.WOUND_HOOKS[0](world, me, foe, form, load_body(world, me), target)
    assert target.poisons and target.poisons[0]["grade"] == 2
    assert world.entity(me).data["venom_coat"]["strikes"] == 2


def test_a_weak_brewed_poison_sickens_a_master_rather_than_killing(game):
    import systems.scheming as S
    from systems import factions as F
    from systems import halls
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    pill(game, "poison", grade=2)
    events = S.poison_events(world, me, leader, seat)
    assert [e.kind for e in events] == ["poison_slipped"]
    commit(world, events)
    assert not world.entity(leader).data.get("dead") and load_body(world, leader).poisons
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_pills.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'systems.pills'`.

- [ ] **Step 3: Write the new modules**

`systems/pills.py`:
```python
"""Pills and what they do (phase 5b spec 4.1): swallowed, a coat of venom on a blade, and the residue they leave.

A pill is an item (`kind = "pill"`) with its `effect`, `grade` (1-5) and `purity`. It works at
`grade x (1 - residue / 150)` and leaves `grade x (1 - purity) x 10` residue behind. 4d's treasure pills
(`qi_years`) are qi pills of grade 2, swallowed the same way. Poisons are slipped or taken; venom is put on a
blade; a tempering draught is for a bath.
"""

import systems.gear as gear
import systems.toxins as toxins
from systems.bodies import load_body, save_body
from systems.realms import add_energy
from world.body import heal_watches
from world.events import Event, effect

LEGACY_GRADE, LEGACY_PURITY = 2, 0.7
SWALLOWED = frozenset({"qi", "bottleneck", "purity", "healing", "mending", "calming", "cleansing", "antidote",
                       "poison"})
VENOM_STRIKES = 3
POISON_STRENGTH = 4        # a swallowed or slipped poison lasts grade x 4 watches


def pills_of(world, person: int) -> list:
    """The pills someone carries: made ones, and 4d's treasure pills."""
    out = []
    for item in (world.entity(i) for i in world.targets(person, "owns")):
        if item is None or item.data.get("used"):
            continue
        if item.kind == "pill" or (item.kind == "treasure" and item.data.get("kind") == "pill"):
            out.append(item)
    return out


def effect_of(item) -> str:
    return item.data.get("effect", "qi")


def grade_of(item) -> int:
    return item.data.get("grade", LEGACY_GRADE)


def swallow_block(world, person: int, item_id: int) -> str | None:
    item = world.entity(item_id)
    if item is None or item not in pills_of(world, person):
        return "You have no such pill."
    if effect_of(item) not in SWALLOWED:
        return "That is not taken by mouth." if effect_of(item) != "venom" else "Venom goes on a blade, not down the throat."
    return None


def swallow_events(world, person: int, place, item_id: int) -> list[Event]:
    item = world.entity(item_id)
    return [Event("pill_taken", (person,), place, {
        "item": item_id, "effect": effect_of(item), "grade": grade_of(item),
        "purity": item.data.get("purity", LEGACY_PURITY), "qi_years": item.data.get("qi_years")})]


@effect("pill_taken")
def _taken(world, event) -> None:
    person, d = event.actors[0], event.data
    world.unrelate(person, "owns", d["item"])
    world.update_data(d["item"], used=True)
    body = load_body(world, person)
    potency = d["grade"] * toxins.dulling(body)
    kind = d["effect"]
    if kind == "qi":  # a treasure pill keeps its own years, dulled like any other
        add_energy(body, d["qi_years"] * toxins.dulling(body) if d["qi_years"] is not None else 0.5 * potency)
    elif kind == "bottleneck":
        body.breakthrough_aid = round(body.breakthrough_aid + 0.1 * potency, 3)
    elif kind == "purity":
        body.purity = round(min(1.0, body.purity + 0.02 * potency), 3)
    elif kind == "healing":
        worst = sorted((i for i in body.injuries if not i.permanent and i.heals_at and i.heals_at > world.time),
                       key=lambda i: (-i.severity, i.id))[:max(1, round(potency))]
        for injury in worst:
            injury.heals_at = world.time + (injury.heals_at - world.time) // 2
    elif kind == "mending":
        damaged = sorted(n for n, m in body.meridians.items() if m.state == "damaged")
        severed = sorted(n for n, m in body.meridians.items() if m.state == "severed")
        if damaged:
            body.meridians[damaged[0]].state, body.meridians[damaged[0]].heals_at = "open", None
        elif severed and d["grade"] >= 4:
            body.meridians[severed[0]].state = "damaged"
            body.meridians[severed[0]].heals_at = world.time + heal_watches(3, body)
    elif kind == "calming":
        body.deviation = max(0.0, body.deviation - 10 * potency)
    elif kind == "cleansing":
        body.residue = max(0.0, body.residue - 10 * potency)
    if kind != "poison":
        toxins.leave_residue(body, d["grade"], d["purity"], toxins.residue_rng(world, person, event.data["item"]))
    save_body(world, person, body)
    if kind == "antidote":
        toxins.cure(world, person, d["grade"])
    elif kind == "poison":
        toxins.poison(world, person, d["grade"], d["grade"] * POISON_STRENGTH, "a swallowed poison")


# --- venom on a blade --------------------------------------------------------------------------------------

def coat_block(world, person: int, item_id: int) -> str | None:
    item = world.entity(item_id)
    if item is None or item not in pills_of(world, person) or effect_of(item) != "venom":
        return "You have no venom."
    if gear.weapon_of(world, person) is None:
        return "You carry no blade to coat."
    return None


def coat_events(world, person: int, place, item_id: int) -> list[Event]:
    return [Event("blade_coated", (person,), place, {"item": item_id, "grade": grade_of(world.entity(item_id))})]


@effect("blade_coated")
def _coated(world, event) -> None:
    person, d = event.actors[0], event.data
    world.unrelate(person, "owns", d["item"])
    world.update_data(d["item"], used=True)
    world.update_data(person, venom_coat={"grade": d["grade"], "strikes": VENOM_STRIKES})


def _venom_strikes(world, hitter: int, target: int, form: str, hitter_body, target_body) -> None:
    """A coated blade's wound poisons (spec 4.1); the coat wears off after three."""
    coat = world.entity(hitter).data.get("venom_coat")
    if not coat or form not in gear.WEAPON_FORMS:
        return
    toxins.add_poison(world, target, target_body, coat["grade"], coat["grade"] * 2, "a venomed blade")
    left = coat["strikes"] - 1
    world.update_data(hitter, venom_coat={**coat, "strikes": left} if left > 0 else None)


toxins.WOUND_HOOKS.append(_venom_strikes)
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5b_task4.py`:
```python
"""Phase 5b, Task 4: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/cultivation.py', r'''    chance = min(max(chance, 0.95), chance * W.factor(world, place, "breakthrough"))  # a qi tide (phase 4d)
''', r'''    chance = min(max(chance, 0.95), chance * W.factor(world, place, "breakthrough"))  # a qi tide (phase 4d)
    if body.breakthrough_aid:  # a breakthrough pill's help (phase 5b)
        chance = min(0.95, round(chance + body.breakthrough_aid, 3))
''')
edit('systems/cultivation.py', r'''        body.deviation = min(100.0, body.deviation + 30)
    if data["discovered"]:
        body.constitution_known = True
    save_body(world, pid, body)

''', r'''        body.deviation = min(100.0, body.deviation + 30)
    if data["discovered"]:
        body.constitution_known = True
    body.breakthrough_aid = 0.0  # a breakthrough pill's help is spent, whatever came of it (phase 5b)
    save_body(world, pid, body)

''')
edit('systems/duel.py', r'''    return {"target": target, "damage": round(damage, 2), "wound": list(hit) if hit else None}
''', r'''    return {"target": target, "damage": round(damage, 2), "wound": list(hit) if hit else None, "form": form}
''')
edit('systems/duel.py', r'''            add_injury(bodies[blow["target"]], location, kind, severity, world.time, f"{people[hitter].name}'s {weapon}")
''', r'''            add_injury(bodies[blow["target"]], location, kind, severity, world.time, f"{people[hitter].name}'s {weapon}")
            from systems.toxins import WOUND_HOOKS  # phase 5b: a wound may carry poison
            for hook in WOUND_HOOKS:
                hook(world, ids[hitter], ids[blow["target"]], blow.get("form", "bare"), bodies[hitter],
                     bodies[blow["target"]])
''')
edit('systems/scheming.py', r'''    return [i.id for i in items if i.kind == "treasure" and i.data.get("kind") == "poison" and not i.data.get("used")]
''', r'''    return [i.id for i in items if not i.data.get("used") and ((i.kind == "treasure" and i.data.get("kind") == "poison")
                                                               or (i.kind == "pill" and i.data.get("effect") == "poison"))]


def poison_grade(item) -> int:
    """A bought vial kills (grade 4); a brewed poison is as strong as its brewing (phase 5b)."""
    return item.data.get("grade", 4) if item.kind == "pill" else 4
''')
edit('systems/scheming.py', r'''    vial = poisons_of(world, player)[0]
    rng = rng_for(world.world_seed, f"scheme:poison:{player}:{leader}")
    return [Event("poison_slipped", (player, leader), place, {"faction": faction, "vial": vial}),
            Event("died", (leader, leader), place, {"cause": "illness", "world": True, "poisoned_by": player})] \
''', r'''    vial = max(poisons_of(world, player), key=lambda i: (poison_grade(world.entity(i)), -i))
    grade = poison_grade(world.entity(vial))
    rng = rng_for(world.world_seed, f"scheme:poison:{player}:{leader}")
    slipped = [Event("poison_slipped", (player, leader), place, {"faction": faction, "vial": vial, "grade": grade})]
    if grade < 4:  # too weak to kill: they fall ill, and live (phase 5b)
        return slipped
    return slipped + [Event("died", (leader, leader), place, {"cause": "illness", "world": True,
                                                              "poisoned_by": player})] \
''')
edit('systems/scheming.py', r'''    world.update_data(vial, used=True)
''', r'''    world.update_data(vial, used=True)
    if event.data.get("grade", 4) < 4:
        from systems.toxins import poison
        poison(world, event.actors[1], event.data["grade"], event.data["grade"] * 4, "a poisoned cup")
''')
edit('systems/toxins.py', r'''import systems.lives as lives
''', r'''# The registry first: modules that fill it (pills, the poison path) may load while this one is still loading.
WOUND_HOOKS: list = []  # (world, hitter, target, form, hitter_body, target_body): a wound that poisons (5b)

import systems.lives as lives  # noqa: E402
''')
edit('systems/toxins.py', r'''    if grade <= body.resist:
        return "resisted"
    body.poisons = body.poisons + [{"grade": int(grade), "strength": int(strength), "days": 0.0,
                                    "at": world.time, "sealed_until": 0, "source": source}]
    save_body(world, person, body)
''', r'''    result = add_poison(world, person, body, grade, strength, source)
    save_body(world, person, body)
    return result


def add_poison(world, person: int, body, grade: int, strength: int, source: str) -> str:
    """The same, into a body already loaded (a duel's wound): the caller saves it."""
    if grade <= body.resist:
        return "resisted"
    body.poisons = body.poisons + [{"grade": int(grade), "strength": int(strength), "days": 0.0,
                                    "at": world.time, "sealed_until": 0, "source": source}]
''')
edit('systems/world_clock.py', r'''import systems.alchemy  # noqa: E402,F401  phase 5b: experiments and refining
''', r'''import systems.alchemy  # noqa: E402,F401  phase 5b: experiments and refining
import systems.pills  # noqa: E402,F401  phase 5b: pills, residue, venom on a blade
''')
print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5b_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_pills.py tests/test_duel.py tests/test_scheming.py`
Expected: `28 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: pills - swallowed for qi, healing, cleansing and more, dulled by residue; venom on a blade

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: The poison path and the Myriad Poison Body

A poison art (bought for 300 silver from an unorthodox keeper, ruling 3) turns poison into qi and venom instead of harm; at 60 venom the practitioner turns into the Myriad Poison Body (ruling 1), which shrugs off poisons of grade 3 or less and whose blood poisons whoever strikes it bare-handed. Venomous beasts replace 3% of beast encounters in marsh and forest (ruling 4) and can be butchered for blood or core. A tempering bath raises a stat (3 per stat); a grade-3 herb may awaken a constitution. The righteous think less of a Poison Body.

**Files:**
- Create: `systems/poison_path.py`
- Create: `tests/test_poison_path.py`
- Modify (by `.patches/5b_task5.py`): `debug/invariants.py`, `systems/attitude.py`, `systems/encounters.py`, `systems/pills.py`, `systems/toxins.py`, `systems/world_clock.py`

**Interfaces:**
- Consumes: Tasks 1-4: `toxins.ABSORB_HOOKS`, `toxins.WOUND_HOOKS`, `herbs`, `pills`; 2's `constitutions`, `encounters.random_encounter`; 3b's `attitude.JUDGEMENT`; 3a's `record_fact`.
- Produces:
  - `poison_path` (PP): `POISON_BODY`, `PATH_MASTERY`, `QI_PER_POINT`, `TURNING`, `IMMUNE_GRADE`, `BARE_FORMS`, `ART_PRICE`, `BEASTS`, `AWAKENING`; `poison_mastery(world, p)`, `conversion(world, p, body)`, `turned(world, p)`, `poison_body_news`, `art_block/art_events(world, player, npc, place)`, `venomous_beast(world, player, region)`, `butcher_block/butcher_events(world, player, beast, place, part)`, `bath_block(world, p, place, stat, draught)`, `bath_events(world, p, place, stat, draught, herb=None)`; events `poison_art_bought`, `beast_butchered`, `bathed`; fact `poison_body`.
  - `encounters.BEAST_HOOKS`; `attitude.JUDGEMENT['poison_body']`; `debug.invariants.check_alchemy(world)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_poison_path.py`:
```python
import pytest

import systems.alchemy as A
import systems.poison_path as PP
import systems.toxins as X
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.herbs import make_herb
from systems.techniques import create_technique, generate, teach
from world.events import Event, commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=5000)
    yield g
    g.close()


def poison_art(game, mastery=0.6, form="palm"):
    world, me = game.world, game.player.id
    name, data = generate(rng_for(world.world_seed, "test:poison_art"), "martial", form=form, grade=2, element="poison")
    teach(world, me, create_technique(world, name, data), completeness=1.0, known_completeness=1.0,
          source="test", mastery=mastery)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "mortal", "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:pp:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_a_poison_art_turns_poison_into_qi_and_venom(game):
    world, me = game.world, game.player.id
    poison_art(game)
    body = load_body(world, me)
    body.realm, body.energy_years, body.bottleneck = 2, 6.0, False
    save_body(world, me, body)
    share = PP.conversion(world, me, load_body(world, me))
    assert share == pytest.approx(min(0.9, 0.3 + 0.5 * 0.6 + 0.05 * 2))
    X.poison(world, me, 4, 10, "test")
    after = load_body(world, me)
    assert after.venom == pytest.approx(share * 40) and after.energy_years > 6.0
    assert after.poisons and after.poisons[0]["strength"] == int(10 * (1 - share))


def test_without_the_art_a_poison_is_suffered_whole(game):
    world, me = game.world, game.player.id
    X.poison(world, me, 4, 10, "test")
    assert load_body(world, me).venom == 0 and load_body(world, me).poisons[0]["strength"] == 10


def test_enough_venom_turns_the_body_and_the_world_hears(game):
    world, me = game.world, game.player.id
    poison_art(game, mastery=1.0)
    body = load_body(world, me)
    body.venom = 55.0
    save_body(world, me, body)
    X.poison(world, me, 5, 10, "test")
    assert load_body(world, me).constitution == PP.POISON_BODY and world.facts(predicate="poison_body", subject=me)


def test_a_poison_body_shrugs_off_lesser_poisons_and_its_blood_poisons(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.constitution = PP.POISON_BODY
    save_body(world, me, body)
    assert X.poison(world, me, 3, 10, "test") == "absorbed" and load_body(world, me).poisons == []
    striker = someone(game, "striker")
    striker_body = load_body(world, striker)
    PP._strikes(world, striker, me, "fist", striker_body, load_body(world, me))
    assert striker_body.poisons and striker_body.poisons[0]["grade"] == PP.BLOOD_GRADE


def test_a_poison_arts_wound_poisons(game):
    world, me = game.world, game.player.id
    poison_art(game, form="palm")
    target = someone(game, "target")
    body = load_body(world, target)
    PP._strikes(world, me, target, "palm", load_body(world, me), body)
    assert body.poisons and body.poisons[0]["grade"] == 1 + int(0.6 * 3)
    clean = load_body(world, target)
    PP._strikes(world, me, target, "sword", load_body(world, me), clean)
    assert clean.poisons == []  # another art's wound carries none


def test_healing_works_at_half_on_a_poison_body(game):
    import systems.pills as P
    from world.body import add_injury
    world, me = game.world, game.player.id
    key = next(k for k, r in A.RECIPES.items() if r["effect"] == "healing")

    def healed_by_a_pill(poison_body: bool) -> int:
        body = load_body(world, me)
        body.injuries = []
        body.constitution = PP.POISON_BODY if poison_body else None
        for location in ("left arm", "right arm", "left leg"):
            add_injury(body, location, "cut", 3, world.time, "test")
        save_body(world, me, body)
        before = [i.heals_at for i in load_body(world, me).injuries]
        item = A.make_pill(world, me, A.recipe_entity(world, key), 2, 1.0)
        commit(world, P.swallow_events(world, me, game.place.id, item))
        return sum(1 for a, b in zip(before, (i.heals_at for i in load_body(world, me).injuries)) if b < a)
    assert healed_by_a_pill(False) == 2 and healed_by_a_pill(True) == 1


def test_an_unorthodox_keeper_sells_a_poison_art(game):
    world, me = game.world, game.player.id
    clan = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "unorthodox_clan")
    seat = halls.seat_of(world, clan)
    [keeper] = halls.staff_at(world, clan, seat, roles=("keeper",))[:1]
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    assert PP.art_block(world, me, keeper) is None
    commit(world, PP.art_events(world, me, keeper, seat))
    from systems.items import manuals_of
    [manual] = manuals_of(world, me)
    assert manual.technique.data["element"] == "poison"


def test_a_venomous_beast_bites_with_venom_and_can_be_butchered(game, monkeypatch):
    monkeypatch.setattr(PP, "BEAST_CHANCE", 1.0)
    world, me = game.world, game.player.id
    from world.gen.materialize import region_of
    region = region_of(world, game.place.id)
    world.update_data(region.id, terrain="marsh")
    beast = PP.venomous_beast(world, me, world.entity(region.id))
    assert world.entity(beast).data["venomous"]
    body = load_body(world, me)
    PP._strikes(world, beast, me, "claws", load_body(world, beast), body)
    assert any(p["grade"] == PP.BITE_GRADE for p in body.poisons)
    assert PP.butcher_block(world, me, beast, game.place.id) is not None  # it still lives
    commit(world, [Event("died", (me, beast), game.place.id, {"cause": "killed"})])
    assert PP.butcher_block(world, me, beast, game.place.id) is None
    commit(world, PP.butcher_events(world, me, beast, game.place.id, "blood"))
    assert load_body(world, me).resist == PP.BLOOD_RESIST
    assert PP.butcher_block(world, me, beast, game.place.id) == "There is nothing to take."


def test_a_tempering_bath_raises_a_stat_to_its_limit(game):
    world, me = game.world, game.player.id
    key = next(k for k, r in A.RECIPES.items() if r["effect"] == "tempering")
    before = load_body(world, me).physique["strength"]
    for n in range(PP.BATH_LIMIT):
        draught = A.make_pill(world, me, A.recipe_entity(world, key), 2, 1.0)
        assert PP.bath_block(world, me, game.place.id, "strength", draught) is None
        commit(world, PP.bath_events(world, me, game.place.id, "strength", draught))
    assert load_body(world, me).physique["strength"] == min(20, before + PP.BATH_LIMIT)
    draught = A.make_pill(world, me, A.recipe_entity(world, key), 2, 1.0)
    assert "no further" in PP.bath_block(world, me, game.place.id, "strength", draught)


def test_a_legendary_herb_in_the_bath_may_awaken_a_constitution(game, monkeypatch):
    monkeypatch.setattr(PP, "AWAKEN", 1.0)
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.constitution = None
    save_body(world, me, body)
    key = next(k for k, r in A.RECIPES.items() if r["effect"] == "tempering")
    draught = A.make_pill(world, me, A.recipe_entity(world, key), 2, 1.0)
    herb = make_herb(world, "snow lingzhi", 3, me)
    commit(world, PP.bath_events(world, me, game.place.id, "endurance", draught, herb))
    assert load_body(world, me).constitution == "Nine Yin Body"


def test_the_alchemy_rules_catch_a_malformed_pill(game):
    from debug.invariants import check_alchemy
    world, me = game.world, game.player.id
    key = next(k for k, r in A.RECIPES.items() if r["effect"] == "qi")
    item = A.make_pill(world, me, A.recipe_entity(world, key), 2, 1.0)
    make_herb(world, "ginseng", 1, me)
    assert check_alchemy(world) == []
    world.update_data(item, grade=9)
    assert any("malformed pill" in p for p in check_alchemy(world))
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_poison_path.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'systems.poison_path'`.

- [ ] **Step 3: Write the new modules**

`systems/poison_path.py`:
```python
"""The poison path, the Myriad Poison Body, venomous beasts and tempering baths (phase 5b spec 4.3-4.6).

A practitioner of a poison art (element `poison`, mastery 0.3 or more) turns part of any poison they take into qi,
and the rest into venom in the body; at 60 venom the body turns: a Myriad Poison Body, immune to lesser poisons,
its blood a venom to whoever strikes it bare-handed. Their own strikes leave poison. Poison arts are bought from
an unorthodox clan's keeper. A great venomous beast may come on the road in marsh and forest; its blood and its
core are worth having. A tempering draught and a day's bath raise the body.
"""

import systems.encounters as encounters
import systems.toxins as toxins
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.items import create_manual
from systems.purse import silver_of
from systems.realms import add_energy
from systems.techniques import create_technique, generate, known_arts
from world.body import PHYSIQUE, add_injury
from world.events import Event, effect
from world.seed import rng_for

POISON_BODY = "Myriad Poison Body"
PATH_MASTERY = 0.3
QI_PER_POINT = 0.02
TURNING = 60.0
IMMUNE_GRADE = 3
BLOOD_GRADE, BLOOD_STRENGTH = 3, 2
BARE_FORMS = frozenset({"bare", "claws", "palm", "fist", "finger"})
ART_PRICE = 300
BEAST_CHANCE, BEAST_TERRAINS = 0.03, frozenset({"marsh", "forest"})
BEASTS = ("great python", "red toad", "golden centipede")
BITE_GRADE, BITE_STRENGTH = 4, 8
BLOOD_RESIST, BLOOD_QI, CORE_QI, CORE_VENOM = 2, 1.0, 3.0, 10.0
BATH_PRICE, BATH_LIMIT, BATH_PAIN, AWAKEN = 30, 3, 0.3, 0.2
AWAKENING = {"fire": "Pure Yang Body", "water": "Nine Yin Body", "metal": "Heavenly Sword Bones",
             "earth": "Iron Bone Body", "wood": "Dragon Vein Body", "poison": POISON_BODY}


# --- the poison path ---------------------------------------------------------------------------------------

def poison_mastery(world, person: int) -> tuple[float, str | None]:
    """The best mastery of a poison art this person knows, and its form."""
    arts = [a for a in known_arts(world, person) if a.technique.data.get("element") == "poison"
            and a.technique.data.get("category") == "martial"]
    best = max(arts, key=lambda a: a.mastery, default=None)
    return (best.mastery, best.technique.data["form"]) if best else (0.0, None)


def conversion(world, person: int, body) -> float:
    mastery, _ = poison_mastery(world, person)
    if mastery < PATH_MASTERY:
        return 0.0
    return min(0.9, 0.3 + 0.5 * mastery + 0.05 * body.realm)


def _absorb(world, person: int, body, grade: int, strength: int) -> tuple[int, int]:
    """A practitioner takes a poison in: part becomes qi and venom, the rest is suffered (spec 4.3)."""
    share = conversion(world, person, body)
    if not share:
        return grade, strength
    points = share * grade * strength
    add_energy(body, points * QI_PER_POINT)
    body.venom = min(100.0, round(body.venom + points, 3))
    if body.venom >= TURNING and body.constitution != POISON_BODY:
        body.constitution, body.constitution_known = POISON_BODY, True
        here = world.targets(person, "located_in")
        poison_body_news(world, person, here[0] if here else None)
    return grade, int(strength * (1 - share))


def _immune(world, person: int, body, grade: int, strength: int) -> tuple[int, int]:
    """A Myriad Poison Body shrugs off the lesser poisons (spec 4.4)."""
    if body.constitution == POISON_BODY and grade <= IMMUNE_GRADE:
        return grade, 0
    return grade, strength


toxins.ABSORB_HOOKS.extend([_immune, _absorb])


def _strikes(world, hitter: int, target: int, form: str, hitter_body, target_body) -> None:
    """A poison art's wound leaves poison; a Poison Body's blood poisons a bare-handed striker; a venomous beast
    bites with venom (spec 4.3, 4.4, 4.6)."""
    mastery, art_form = poison_mastery(world, hitter)
    if mastery >= PATH_MASTERY and form == art_form:
        toxins.add_poison(world, target, target_body, 1 + int(mastery * 3), 2, "a poison art")
    if world.entity(hitter).data.get("venomous"):
        toxins.add_poison(world, target, target_body, BITE_GRADE, BITE_STRENGTH, "a venomous bite")
    if target_body.constitution == POISON_BODY and form in BARE_FORMS:
        toxins.add_poison(world, hitter, hitter_body, BLOOD_GRADE, BLOOD_STRENGTH, "a poison body's blood")


toxins.WOUND_HOOKS.append(_strikes)


def turned(world, person: int) -> bool:
    return load_body(world, person).constitution == POISON_BODY


def poison_body_news(world, person: int, place) -> None:
    """The world comes to hear of a Poison Body (spec 4.4): a fact like any other."""
    variant = make_variant("poison_body", person, None, place=place_name(world, place) if place else None)
    record_fact(world, person, "poison_body", None, place=place, weight=2.0, variant=variant)


# --- poison arts from an unorthodox clan's keeper -------------------------------------------------------------

def art_block(world, player: int, npc: int) -> str | None:
    from systems.scheming import buy_poison_block
    why = buy_poison_block(world, player, npc)
    if why is not None and why != "A poison costs 50 silver.":
        return "They teach no poisons."
    if silver_of(world, player) < ART_PRICE:
        return f"A poison art's manual costs {ART_PRICE} silver."
    return None


def art_events(world, player: int, npc: int, place) -> list[Event]:
    return [Event("poison_art_bought", (player, npc), place, {"silver": ART_PRICE})]


@effect("poison_art_bought")
def _art_bought(world, event) -> None:
    player, keeper = event.actors
    world.update_data(player, silver=silver_of(world, player) - ART_PRICE)
    world.update_data(keeper, silver=silver_of(world, keeper) + ART_PRICE)
    rng = rng_for(world.world_seed, f"poison_art:{player}:{world.time}")
    name, data = generate(rng, "martial", form=rng.choice(F.FAVOURED["unorthodox_clan"]), grade=2, element="poison")
    create_manual(world, player, create_technique(world, name, data), 1.0)


# --- venomous beasts -------------------------------------------------------------------------------------------

def venomous_beast(world, player: int, region) -> int | None:
    """When a beast comes on the roads of marsh and forest, it may be a great venomous one (spec 4.6); its own roll."""
    if region.data["terrain"] not in BEAST_TERRAINS:
        return None
    own = rng_for(world.world_seed, f"venomous:{player}:{world.time}")
    if own.random() >= BEAST_CHANCE:
        return None
    index = 0
    while world.entity_by_seed(f"{region.seed_path}/venomous:{index}") is not None:
        index += 1
    path = f"{region.seed_path}/venomous:{index}"
    species = own.choice(BEASTS)
    beast = world.add_entity("person", f"a {species}", {
        "beast": True, "venomous": True, "occupation": species, "traits": ["hot-tempered"], "realm": "second-rate",
        "roamer": True, "roamer_kind": "beast", "silver": 0}, path)
    world.relate(beast, region.id, "located_in")
    return beast


encounters.BEAST_HOOKS.append(venomous_beast)


def butcher_block(world, player: int, beast: int, place) -> str | None:
    data = world.entity(beast).data if world.entity(beast) is not None else {}
    if not data.get("venomous") or not data.get("dead") or data.get("butchered"):
        return "There is nothing to take."
    return None


def butcher_events(world, player: int, beast: int, place, part: str) -> list[Event]:
    return [Event("beast_butchered", (player, beast), place, {"part": part})]


@effect("beast_butchered")
def _butchered(world, event) -> None:
    player, beast = event.actors
    world.update_data(beast, butchered=True)
    body = load_body(world, player)
    if event.data["part"] == "blood":
        body.resist = max(body.resist, BLOOD_RESIST)
        add_energy(body, BLOOD_QI)
    else:
        add_energy(body, CORE_QI)
        if conversion(world, player, body):
            body.venom = min(100.0, body.venom + CORE_VENOM)
    save_body(world, player, body)


# --- tempering baths -------------------------------------------------------------------------------------------

def bath_block(world, person: int, place, stat: str, draught: int | None) -> str | None:
    if stat not in PHYSIQUE:
        return "No bath raises that."
    item = world.entity(draught) if draught is not None else None
    if item is None or item.kind != "pill" or item.data.get("effect") != "tempering" or draught not in world.targets(person, "owns"):
        return "A tempering bath needs a tempering draught."
    if load_body(world, person).baths.get(stat, 0) >= BATH_LIMIT:
        return f"Baths can raise your {stat} no further."
    if world.entity(place).kind != "town":
        return "A bath needs an inn or your sect's hall."
    if not _own_hall(world, person, place) and silver_of(world, person) < BATH_PRICE:
        return f"The inn's bath costs {BATH_PRICE} silver."
    return None


def _own_hall(world, person: int, place) -> bool:
    return any(world.entity(f).data.get("seat") == place and d.get("status", "member") == "member"
               for f, _, d in F.memberships(world, person))


def bath_events(world, person: int, place, stat: str, draught: int, herb: int | None = None) -> list[Event]:
    from systems.herbs import herb_info
    rng = rng_for(world.world_seed, f"bath:{person}:{world.time}")
    info = herb_info(world.entity(herb)) if herb is not None else None
    awaken = None
    if info is not None and info[1] >= 3 and rng.random() < AWAKEN:
        awaken = AWAKENING.get(_element(info[0]))
    return [Event("bathed", (person,), place, {
        "stat": stat, "draught": draught, "herb": herb, "pain": rng.random() < BATH_PAIN, "awaken": awaken,
        "price": 0 if _own_hall(world, person, place) else BATH_PRICE})]


def _element(name: str) -> str:
    from systems.herbs import props
    return props(name)["element"]


@effect("bathed")
def _bathed(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    for item in (d["draught"], d["herb"]):
        if item is not None:
            world.unrelate(person, "owns", item)
            world.update_data(item, used=True)
    body = load_body(world, person)
    body.physique[d["stat"]] = min(20, body.physique[d["stat"]] + 1)
    body.baths = {**body.baths, d["stat"]: body.baths.get(d["stat"], 0) + 1}
    if d["pain"]:
        add_injury(body, "torso", "internal", 1, world.time, "a tempering bath")
    if d["awaken"] and body.constitution is None:
        body.constitution, body.constitution_known = d["awaken"], True
    save_body(world, person, body)
    from systems.time import advance
    advance(world, 4)
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5b_task5.py`:
```python
"""Phase 5b, Task 5: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('debug/invariants.py', r'''    problems += check_toxins(world)
''', r'''    problems += check_toxins(world)
    problems += check_alchemy(world)
''')
edit('debug/invariants.py', r'''            out.append(f"manual #{manual.id} claims less than it holds")
''', r'''            out.append(f"manual #{manual.id} claims less than it holds")
    return out


def check_alchemy(world) -> list[str]:
    """Herbs of the table, pills of a known effect, grade and purity, recipes learnt within 0-1 (phase 5b)."""
    from systems.herbs import HERBS
    from systems.pills import SWALLOWED
    effects = SWALLOWED | {"venom", "tempering"}
    out = []
    for herb in world.entities("herb"):
        if herb.data.get("herb") not in HERBS or not 0 <= herb.data.get("grade", -1) <= 3:
            out.append(f"{herb.name} (#{herb.id}) is no herb of the table")
    for pill in world.entities("pill"):
        d = pill.data
        if d.get("effect") not in effects or not 1 <= d.get("grade", 0) <= 5 or not 0 <= d.get("purity", -1) <= 1:
            out.append(f"{pill.name} (#{pill.id}) is a malformed pill")
    for person, value in world._conn.execute("select a, value from relations where kind = 'knows_recipe'"):
        if not 0 <= value <= 1:
            out.append(f"#{person} knows a recipe at mastery {value}")
''')
edit('systems/attitude.py', r'''    "false_accusation": -0.3, "spy_exposed": -0.8,
''', r'''    "false_accusation": -0.3, "spy_exposed": -0.8,
    "poison_body": -0.4,  # phase 5b: folk keep away from a body that is poison
''')
edit('systems/encounters.py', r'''ROAD_HOOKS: list = []       # fn(world, player, town, rng) -> events or None; tried before the normal roll (phase 3b)
''', r'''ROAD_HOOKS: list = []       # fn(world, player, town, rng) -> events or None; tried before the normal roll (phase 3b)
BEAST_HOOKS: list = []      # fn(world, player, region) -> a beast or None: what comes when a beast comes (phase 5b)
''')
edit('systems/encounters.py', r'''    kind = "beast" if "beast" in kinds and tide > 1.0 and rng.random() < 1 - 1 / tide else rng.choice(kinds)
''', r'''    kind = "beast" if "beast" in kinds and tide > 1.0 and rng.random() < 1 - 1 / tide else rng.choice(kinds)
    special = next((b for b in (h(world, player, region) for h in BEAST_HOOKS) if b), None) if kind == "beast" else None
    if special is not None:
        return encounter_events(player, special, town.id, kind, 0, {"venomous": True})
''')
edit('systems/pills.py', r'''    kind = d["effect"]
''', r'''    kind = d["effect"]
    if kind in ("healing", "mending") and body.constitution == "Myriad Poison Body":
        potency *= 0.5  # a poison body takes healing hard (spec 4.4)
''')
edit('systems/toxins.py', r'''WOUND_HOOKS: list = []  # (world, hitter, target, form, hitter_body, target_body): a wound that poisons (5b)
''', r'''WOUND_HOOKS: list = []  # (world, hitter, target, form, hitter_body, target_body): a wound that poisons (5b)
ABSORB_HOOKS: list = []  # (world, person, body, grade, strength) -> (grade, strength): what a body lets in (5b)
''')
edit('systems/toxins.py', r'''        return "resisted"
''', r'''        return "resisted"
    for hook in ABSORB_HOOKS:  # the Myriad Poison Body's immunity, the poison path's conversion
        grade, strength = hook(world, person, body, grade, strength)
    if strength <= 0:
        return "absorbed"
''')
edit('systems/world_clock.py', r'''import systems.pills  # noqa: E402,F401  phase 5b: pills, residue, venom on a blade
''', r'''import systems.pills  # noqa: E402,F401  phase 5b: pills, residue, venom on a blade
import systems.poison_path  # noqa: E402,F401  phase 5b: the poison path, venomous beasts, tempering baths
''')
print("task 5 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5b_task5.py`
Expected: `task 5 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_poison_path.py tests/test_opponent.py tests/test_fight_flow.py`
Expected: `28 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the poison path - poison turned to qi, the Myriad Poison Body, venomous beasts, tempering baths

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: The player's alchemy

The alchemy page and its furnace tray (put in, light, empty, refine, swallow), gathering and tasting, the herbalist's menu, sealing and forcing out, butchering, tempering baths, coating a blade, buying a poison art in conversation, the sheet's constitution note, journal lines, help and typed commands. Death by poison lands once the turn's deed is done, through a new `_after_turn` hook (ruling 8). Three latent faults the fuzz reached are fixed (ruling 14).

**Files:**
- Create: `engine/alchemy.py`
- Create: `engine/alchemy_page.py`
- Create: `narrate/alchemy_text.py`
- Create: `narrate/grammar/alchemy.toml`
- Create: `tests/test_alchemy_play.py`
- Modify (by `.patches/5b_task6.py`): `engine/commands.py`, `engine/crisis.py`, `engine/game.py`, `engine/hooks.py`, `engine/sheet.py`, `narrate/outcomes.py`, `systems/agendas.py`, `systems/alchemy.py`, `systems/toxins.py`, `tests/test_fuzz.py`, `world/body.py`

**Interfaces:**
- Consumes: Tasks 1-5: everything above; 5a's mixin hooks (`_general_extras`, `_conversation_extras`, `_submenu_options`, `_after_duel`, `_after_arrival`); 3a's `known_people`.
- Produces:
  - `engine/alchemy.py`: `AlchemyMixin` with `_general_extras`, `_conversation_extras`, `_submenu_options` (`alchemy`, `herbalist`, `bath`), `_after_arrival`, `_after_duel`, `_after_turn`, and the `_do_*` handlers `alchemy`, `herbalist`, `bath_menu`, `gather`, `taste`, `add_herb`, `empty_furnace`, `experiment`, `refine`, `swallow`, `coat`, `buy_herb`, `buy_furnace`, `seal`, `force_out`, `butcher`, `bathe`, `buy_poison_art`.
  - `engine/alchemy_page.py`: `herb_line`, `poison_words`, `alchemy_lines`, `constitution_words`.
  - `narrate/alchemy_text.py`, `narrate/grammar/alchemy.toml`; `engine.hooks._after_turn`; `alchemy.find_batch`; `crisis._nameable`; `agendas.MASTER_AGE`.

- [ ] **Step 1: Write the failing tests**

`tests/test_alchemy_play.py`:
```python
import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.herbs as H
import systems.poison_path as PP
import systems.toxins as X
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.outcomes import SUMMARIES
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import WATCHES_PER_DAY
from world.events import commit


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


def labels(turn):
    return [c.label for c in turn.all_choices]


def test_the_alchemy_page_shows_herbs_as_known(game):
    world, me = game.world, game.player.id
    H.make_herb(world, "willow bark", 0, me)
    turn = game.perform(Action("alchemy"))
    text = " | ".join(t for t, _ in turn.lines)
    assert "willow bark (a year): its nature unknown until tasted" in text
    game.perform(Action("taste", H.herbs_of(world, me)[0].id))
    H.make_herb(world, "willow bark", 0, me)
    text = " | ".join(t for t, _ in game.perform(Action("alchemy")).lines)
    assert "willow bark (a year): wood, yin, potency 1, toxicity 0" in text


def test_herbs_go_in_the_furnace_and_the_furnace_is_lit(game):
    world, me = game.world, game.player.id
    one, two = (H.make_herb(world, "frost lotus leaf", 0, me) for _ in range(2))
    game.perform(Action("alchemy"))
    game.perform(Action("add_herb", one))
    turn = game.perform(Action("add_herb", two))
    assert "Light the furnace (2 herbs)" in labels(turn)
    game.perform(Action("experiment"))
    assert A.known_recipes(world, me)


def test_a_known_recipe_is_refined_from_the_herbs_carried(game, monkeypatch):
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (1.0, 1.0))
    world, me = game.world, game.player.id
    recipe = A.recipe_entity(world, "earth_qi")
    world.relate(me, recipe, "knows_recipe", 0.1)
    for name in ("ginseng", "tiger bone vine", "willow bark"):
        H.make_herb(world, name, 0, me)
    turn = game.perform(Action("alchemy"))
    assert f"Refine {world.entity(recipe).name}" in labels(turn)
    game.perform(Action("refine", recipe))
    assert any(world.entity(i).kind == "pill" for i in world.targets(me, "owns"))


def test_the_herbalist_sells_herbs_and_a_furnace(game):
    world, me = game.world, game.player.id
    turn = game.perform(Action("herbalist"))
    buys = [c for c in turn.all_choices if c.action.verb == "buy_herb"]
    assert buys and f"Buy a bronze furnace ({H.FURNACE_PRICE} silver)" in labels(turn)
    game.perform(buys[0].action)
    assert H.herbs_of(world, me)


def test_gathering_can_be_done_from_the_scene(game):
    world, me = game.world, game.player.id
    assert "Search the surroundings for herbs" in labels(game.perform(Action("look")))
    start = world.time
    game.perform(Action("gather"))
    assert world.time >= start + H.GATHER_WATCHES


def test_the_poisoned_may_seal_and_the_sheet_tells_of_it(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.realm, body.energy_years = 1, 1.0
    save_body(world, me, body)
    X.poison(world, me, 2, 20, "a hidden needle")
    assert "Seal your acupoints against the poison" in labels(game.perform(Action("look")))
    text = " | ".join(t for t, _ in sheet_lines(world, me))
    assert "1 poison(s) in your blood" in text
    page = " | ".join(t for t, _ in game.perform(Action("alchemy")).lines)
    assert "grade unknown" in page  # a needle's poison is not named until known


def test_a_poison_that_outlasts_you_is_your_death(game):
    world, me = game.world, game.player.id
    X.poison(world, me, 5, 40, "a hidden needle")
    world.set_time(world.time + 3 * WATCHES_PER_DAY + 1)
    turn = game.perform(Action("rest"))
    assert world.entity(me).data.get("dying") or world.entity(me).data.get("dead") or \
        any("poison" in t for t, _ in turn.lines)


def test_a_poison_death_waits_for_the_deed_to_end(game):
    world, me = game.world, game.player.id
    route = next(c.action for c in game.perform(Action("routes")).all_choices if c.action.verb == "travel")
    X.poison(world, me, 5, 40, "a hidden needle")
    world.set_time(world.time + 2 * WATCHES_PER_DAY)  # a day short of death: the road will take the rest
    assert not X.lethal(load_body(world, me))
    game.perform(route)  # travel commits step by step: death comes when the journey's turn is done, not midway
    assert world.entity(me).data.get("dying") or world.entity(me).data.get("dead")


def test_typed_words_reach_the_furnace(game):
    turn = game.perform(Action("look"))
    for word, verb in (("alchemy", "alchemy"), ("gather", "gather"), ("herbalist", "herbalist"), ("seal", "seal"),
                       ("force out", "force_out")):
        assert parse(word, turn.choices, turn.extra).verb == verb


def test_help_names_alchemy(game):
    assert any("alchemy | gather | herbalist" in t for t, _ in game.perform(Action("help")).lines)


def test_every_alchemy_deed_has_a_journal_line():
    for kind in ("herb_tasted", "herbs_gathered", "herb_bought", "furnace_bought", "experimented", "refined",
                 "pill_taken", "blade_coated", "acupoints_sealed", "poison_forced", "poison_art_bought",
                 "beast_butchered", "bathed"):
        assert kind in SUMMARIES, kind


def test_a_slain_venomous_beast_can_be_butchered_from_the_scene(game):
    world, me = game.world, game.player.id
    beast = world.add_entity("person", "a red toad", {"beast": True, "venomous": True, "occupation": "red toad",
                                                      "traits": ["hot-tempered"], "realm": "second-rate"}, "test:toad")
    world.update_data(beast, dead=True)
    game._slain_beast = beast
    assert "Drink a red toad's blood" in labels(game.perform(Action("look")))
    game.perform(Action("butcher", "blood"))
    assert load_body(world, me).resist == PP.BLOOD_RESIST


def test_a_strong_child_takes_no_apprentice(game):
    import random
    from systems.agendas import apprentice_events
    world = game.world
    child = world.add_entity("person", "A Prodigy", {"occupation": "merchant", "traits": [], "realm": "second-rate",
                                                     "age": 8, "portrait": {"hair": 0, "face": 0, "robe": 0}},
                             "test:prodigy")
    world.relate(child, game.place.id, "located_in")
    youth = world.add_entity("person", "A Willing Youth", {"occupation": "merchant", "traits": [], "realm": "mortal",
                                                          "age": 15, "lived_to": 4,
                                                          "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:youth")
    world.relate(youth, game.place.id, "located_in")  # someone to take on, were the child allowed to

    class Always(random.Random):
        def random(self):
            return 0.0
    assert apprentice_events(world, child, 4, Always()) == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_alchemy_play.py`
Expected: `13 failed`: no alchemy menu (`assert 'unknown' == 'alchemy'`), no herb or seal choices (`'Search the surroundings for herbs' in [...]`), no journal lines (`AssertionError: herb_tasted`), and a child of 8 taking an apprentice (`Left contains one more item: Event(kind='apprenticed'...`).

- [ ] **Step 3: Write the new modules**

`engine/alchemy.py`:
```python
"""Alchemy, medicine and poison in the engine (phase 5b spec 5): the page and its menu, the herbalist, gathering,
the furnace's tray, refining, pills, baths, venom, sealing and forcing out, a venomous beast's spoils, and death
by poison."""

import systems.alchemy as A
import systems.encounters as encounters
import systems.herbs as H
import systems.pills as P
import systems.poison_path as PP
import systems.toxins as X
from engine.actions import Action, Choice
from engine.alchemy_page import alchemy_lines
from systems.bodies import load_body
from world.body import PHYSIQUE
from world.gen.materialize import region_of

ALCHEMY_MENUS = ("alchemy", "herbalist", "bath")


class AlchemyMixin:
    _tray: tuple = ()
    _slain_beast: int | None = None

    # --- choices -----------------------------------------------------------------------------------------------
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, here = self.world, self.player.id, self.place.id
        extras.append(Choice("Your alchemy", Action("alchemy")))
        if H.gather_block(world, me, here) is None:
            extras.append(Choice("Search the surroundings for herbs", Action("gather")))
        if world.entity(here).kind == "town":
            extras.append(Choice("Visit the herbalist", Action("herbalist")))
        body = load_body(world, me)
        if X.seal_block(body, world.time) is None:
            extras.append(Choice("Seal your acupoints against the poison", Action("seal")))
        if X.force_block(body) is None:
            extras.append(Choice("Force the poison out with your qi", Action("force_out")))
        beast = self._slain_beast
        if beast is not None and PP.butcher_block(world, me, beast, here) is None:
            name = world.entity(beast).name
            extras.append(Choice(f"Drink {name}'s blood", Action("butcher", "blood")))
            extras.append(Choice(f"Take {name}'s inner core", Action("butcher", "core")))
        pills = P.pills_of(world, me)
        if any(P.effect_of(p) == "tempering" for p in pills):
            extras.append(Choice("Take a tempering bath...", Action("bath_menu")))
        venom = next((p for p in pills if P.effect_of(p) == "venom"), None)
        if venom is not None and P.coat_block(world, me, venom.id) is None:
            extras.append(Choice("Coat your blade with venom", Action("coat", venom.id)))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if PP.art_block(self.world, self.player.id, npc.id) is None:
            extras.append(Choice(f"Buy a poison art's manual ({PP.ART_PRICE} silver)", Action("buy_poison_art", npc.id)))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None or self.submenu not in ALCHEMY_MENUS:
            return options
        world, me, here = self.world, self.player.id, self.place.id
        if self.submenu == "alchemy":
            choices = [Choice(f"Swallow {p.name}", Action("swallow", p.id)) for p in P.pills_of(world, me)
                       if P.swallow_block(world, me, p.id) is None]
            tray = [t for t in self._tray if t in world.targets(me, "owns")]
            for herb in H.herbs_of(world, me):
                name = H.herb_name(*H.herb_info(herb))
                choices.append(Choice(f"Taste {name}", Action("taste", herb.id)))
                if herb.id not in tray and len(tray) < A.MAX_HERBS:
                    choices.append(Choice(f"Put {name} in the furnace", Action("add_herb", herb.id)))
            if len(tray) >= A.MIN_HERBS:
                choices.append(Choice(f"Light the furnace ({len(tray)} herbs)", Action("experiment")))
            if tray:
                choices.append(Choice("Empty the furnace", Action("empty_furnace")))
            for recipe, _ in A.known_recipes(world, me):
                if A.find_batch(world, me, recipe) is not None:
                    choices.append(Choice(f"Refine {world.entity(recipe).name}", Action("refine", recipe)))
            options["alchemy"] = (choices, Action("back"))
        elif self.submenu == "herbalist":
            choices = [Choice(f"Buy {H.herb_name(o['herb'], o['grade'])} ({H.price(world, here, o['herb'], o['grade'])} "
                              f"silver)", Action("buy_herb", o["key"])) for o in H.stock(world, here)]
            if H.furnace_block(world, me) is None:
                choices.append(Choice(f"Buy a bronze furnace ({H.FURNACE_PRICE} silver)", Action("buy_furnace")))
            options["herbalist"] = (choices, Action("back"))
        else:
            options["bath"] = ([Choice(f"Temper your {stat}", Action("bathe", stat)) for stat in PHYSIQUE],
                               Action("back"))
        return options

    # --- the world around ---------------------------------------------------------------------------------------
    def _after_arrival(self) -> list:
        self._slain_beast = None
        return super()._after_arrival()

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is not None and data.get("killed") and self.world.entity(entry.actors[1]).data.get("venomous"):
            self._slain_beast = entry.actors[1]
        return lines

    def _after_turn(self, turn):
        """After the whole deed, not in the middle of it: a poison that has outlasted you is your death (spec 4.2)."""
        turn = super()._after_turn(turn)
        if self.player.data.get("dying") or self.player.data.get("dead"):
            return turn
        deaths = X.death_events(self.world, self.player.id)
        if not deaths:
            return turn
        lines = self._commit(deaths) + self._death_lines()
        return self._turn(list(turn.lines) + lines)

    # --- handlers -----------------------------------------------------------------------------------------------
    def _do_alchemy(self, _target):
        self.submenu = "alchemy"
        return self._turn(alchemy_lines(self.world, self.player.id, list(self._tray)))

    def _do_herbalist(self, _target):
        self.submenu = "herbalist"
        return self._turn([(f"The herbalist of {self.place.name}", "heading")])

    def _do_bath_menu(self, _target):
        self.submenu = "bath"
        return self._turn([("Which part of your body will the bath temper?", "system")])

    def _do_gather(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        if (why := H.gather_block(world, me, here)) is not None:
            return self._turn([(why, "system")])
        events = H.gather_events(world, me, here)
        lines = self._commit(events)
        if events[0].data["guarded"]:  # a beast guards the best of it (spec 2.3)
            region = region_of(world, here)
            beast = encounters.make_roamer(world, region, "beast", encounters._free_roamer_slot(world, region), 0.5)
            met = encounters.encounter_events(me, beast, here, "beast", 0)
            lines += self._commit(met)
            self.encounter = encounters.encounter_state(met[0])
        return self._turn(lines)

    def _do_taste(self, item):
        if (why := H.taste_block(self.world, self.player.id, item)) is not None:
            return self._turn([(why, "system")])
        self.submenu = "alchemy"
        return self._turn(self._commit(H.taste_events(self.world, self.player.id, item, self.place.id)))

    def _do_add_herb(self, item):
        if H.herb_info(self.world.entity(item) if isinstance(item, int) else None) is None \
                or item not in self.world.targets(self.player.id, "owns"):
            return self._turn([("You have no such herb.", "system")])
        if item not in self._tray and len(self._tray) < A.MAX_HERBS:
            self._tray = self._tray + (item,)
        self.submenu = "alchemy"
        return self._turn(alchemy_lines(self.world, self.player.id, list(self._tray)))

    def _do_empty_furnace(self, _target):
        self._tray, self.submenu = (), "alchemy"
        return self._turn([("You tip the herbs back out.", "system")])

    def _do_experiment(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        tray = [t for t in self._tray if t in world.targets(me, "owns")]
        if (why := A.experiment_block(world, me, here, tray)) is not None:
            return self._turn([(why, "system")])
        self._tray, self.submenu = (), "alchemy"
        return self._turn(self._commit(A.experiment_events(world, me, here, tray)))

    def _do_refine(self, recipe):
        world, me, here = self.world, self.player.id, self.place.id
        batch = A.find_batch(world, me, recipe) if isinstance(recipe, int) else None
        if batch is None:
            return self._turn([("You have not the herbs for it.", "system")])
        if (why := A.refine_block(world, me, here, recipe, batch)) is not None:
            return self._turn([(why, "system")])
        self.submenu = "alchemy"
        return self._turn(self._commit(A.refine_events(world, me, here, recipe, batch)))

    def _do_swallow(self, item):
        world, me = self.world, self.player.id
        if item is None:  # typed: the first pill one can swallow
            item = next((p.id for p in P.pills_of(world, me) if P.swallow_block(world, me, p.id) is None), None)
        if item is None or (why := P.swallow_block(world, me, item)) is not None:
            return self._turn([(why if item is not None else "You have no pill to swallow.", "system")])
        return self._turn(self._commit(P.swallow_events(world, me, self.place.id, item)))

    def _do_coat(self, item):
        if (why := P.coat_block(self.world, self.player.id, item)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.coat_events(self.world, self.player.id, self.place.id, item)))

    def _do_buy_herb(self, key):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "herbalist"
        if (why := H.buy_block(world, me, here, key)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(H.buy_events(world, me, here, key)))

    def _do_buy_furnace(self, _target):
        if (why := H.furnace_block(self.world, self.player.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(H.furnace_events(self.world, self.player.id, self.place.id)))

    def _do_seal(self, _target):
        if (why := X.seal_block(load_body(self.world, self.player.id), self.world.time)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(X.seal_events(self.world, self.player.id, self.place.id)))

    def _do_force_out(self, _target):
        if (why := X.force_block(load_body(self.world, self.player.id))) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(X.force_events(self.world, self.player.id, self.place.id)))

    def _do_butcher(self, part):
        beast = self._slain_beast
        if beast is None or part not in ("blood", "core") \
                or (why := PP.butcher_block(self.world, self.player.id, beast, self.place.id)) is not None:
            return self._turn([("There is nothing to take.", "system")])
        return self._turn(self._commit(PP.butcher_events(self.world, self.player.id, beast, self.place.id, part)))

    def _do_bathe(self, stat):
        world, me, here = self.world, self.player.id, self.place.id
        draught = next((p.id for p in P.pills_of(world, me) if P.effect_of(p) == "tempering"), None)
        if (why := PP.bath_block(world, me, here, stat, draught)) is not None:
            return self._turn([(why, "system")])
        herb = next((h.id for h in H.herbs_of(world, me) if H.herb_info(h)[1] >= 3), None)
        return self._turn(self._commit(PP.bath_events(world, me, here, stat, draught, herb)))

    def _do_buy_poison_art(self, npc):
        if self.focus != npc or (why := PP.art_block(self.world, self.player.id, npc)) is not None:
            return self._turn([("They teach no poisons.", "system")])
        return self._turn(self._commit(PP.art_events(self.world, self.player.id, npc, self.place.id)))
```

`engine/alchemy_page.py`:
```python
"""The alchemist's page (phase 5b spec 5-6): recipes, herbs as known, the furnace's tray, the body's poisons."""

import systems.alchemy as A
import systems.herbs as H
from systems.bodies import load_body


def herb_line(world, viewer: int, item) -> str:
    name, grade = H.herb_info(item)
    if not H.known(world, viewer, name):
        return f"{H.herb_name(name, grade)}: its nature unknown until tasted"
    p = H.props(name)
    return (f"{H.herb_name(name, grade)}: {p['element']}, {p['polarity']}, potency {p['potency']}, "
            f"toxicity {p['toxicity']}")


def poison_words(body) -> list[str]:
    """What the body tells of its poisons: the grade only of those it knows (spec 6)."""
    out = []
    for p in body.poisons:
        grade = f"grade {p['grade']}" if p.get("named") else "grade unknown"
        out.append(f"poison in your blood ({grade}), {max(1, p['strength'] // 4)} day(s) of it left")
    return out


def alchemy_lines(world, player: int, tray: list[int]) -> list:
    body = load_body(world, player)
    lines = [("Alchemy", "heading"), (f"  Alchemy level {A.level(world, player)} | residue {body.residue:.0f} | "
                                     f"venom {body.venom:.0f}", "dim")]
    for words in poison_words(body):
        lines.append((f"  {words}", "red"))
    known = A.known_recipes(world, player)
    lines.append(("Recipes you know:" if known else "You know no recipes yet: experiment to find them.", "heading"))
    for recipe, mastery in known:
        entity = world.entity(recipe)
        lines.append((f"  {entity.name} ({entity.data['effect']}): mastery {mastery:.2f}", "dim"))
    herbs = H.herbs_of(world, player)
    if herbs:
        lines.append(("Herbs you carry:", "heading"))
        lines += [(f"  {herb_line(world, player, h)}", "dim") for h in herbs]
    if tray:
        names = ", ".join(H.herb_name(*H.herb_info(world.entity(h))) for h in tray if H.herb_info(world.entity(h)))
        lines.append((f"In the furnace: {names}", "dim"))
    for hint in (world.entity(player).data.get("alchemy_hints") or [])[-3:]:
        lines.append((f"  A note to yourself: {hint}", "dim"))
    return lines


def constitution_words(world, player: int) -> str:
    """The sheet's note of residue, venom and poisons, folded into its constitution line."""
    body = load_body(world, player)
    parts = [f"residue {body.residue:.0f}"]
    if body.venom:
        parts.append(f"venom {body.venom:.0f}")
    if body.poisons:
        parts.append(f"{len(body.poisons)} poison(s) in your blood")
    return " | " + " | ".join(parts)
```

`narrate/alchemy_text.py`:
```python
"""What the player is told of herbs, the furnace, pills and poison (phase 5b spec 5)."""

from narrate.outcomes import outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

HINT_WORDS = {"element": "the herbs lean to the wrong element", "polarity": "the balance of yin and yang is off",
              "potency": "the brew is too weak", "toxicity": "the brew is too toxic"}


def _poison_body(world, v, viewer) -> str:
    return f"{who(world, v.get('actor'), viewer).capitalize()} has a body of poison: their very blood is venom."


SPECIAL_PHRASES["poison_body"] = _poison_body


@outcome("herb_tasted", body_facts=False)
def _tasted(world, event):
    d = event.data
    line = f"You chew a little of the {d['herb']} and learn its nature."
    return [line + (" Your tongue goes numb: poison." if d["toxicity"] >= 3 else "")], {}


@summary("herb_tasted")
def _tasted_line(world, entry, names, place, other):
    return f"Tasted {entry.data['herb']}."


@outcome("herbs_gathered", body_facts=False)
def _gathered(world, event):
    found = event.data["found"]
    if not found:
        return ["Half a day in the hills and hollows turns up nothing worth the knife."], {}
    names = ", ".join(f["herb"] for f in found)
    return [f"Half a day's searching: {names}." + (" Something large is watching you." if event.data["guarded"] else "")], {}


@summary("herbs_gathered")
def _gathered_line(world, entry, names, place, other):
    return f"Gathered herbs near {place}." if entry.data["found"] else f"Searched for herbs near {place}."


@outcome("herb_bought", body_facts=False)
def _bought(world, event):
    return [f"You pay {event.data['price']} silver for the {event.data['herb']}."], {}


@summary("herb_bought")
def _bought_line(world, entry, names, place, other):
    return f"Bought {entry.data['herb']} at {place}."


@outcome("furnace_bought", body_facts=False)
def _furnace(world, event):
    return [f"A bronze furnace is yours, for {event.data['price']} silver."], {}


@summary("furnace_bought")
def _furnace_line(world, entry, names, place, other):
    return "Bought a furnace."


@outcome("experimented", body_facts=False)
def _experimented(world, event):
    d = event.data
    if d["result"] == "discovered":
        return ["The fumes clear on a single perfect pill. You have found a recipe."], {}
    if d["result"] == "hint":
        return [f"Close, but no: {HINT_WORDS[d['missed']]}."], {}
    return ["A black sludge." + (" Its fumes sting your eyes and lungs." if d["fumes"] else "")], {}


@summary("experimented")
def _experimented_line(world, entry, names, place, other):
    return {"discovered": "Discovered a recipe.", "hint": "Came close to a recipe."}.get(entry.data["result"],
                                                                                        "Burnt a batch of herbs.")


@outcome("refined", body_facts=False)
def _refined(world, event):
    d = event.data
    if d["success"]:
        return [f"{d['count']} pill(s) of grade {d['grade']} cool in the furnace."], {}
    return ["The furnace cracks and burns you." if d["cracked"] else "Only ash comes out."], {}


@summary("refined")
def _refined_line(world, entry, names, place, other):
    return f"Refined {entry.data['count']} pill(s)." if entry.data["success"] else "A refining failed."


@outcome("pill_taken", body_facts=False)
def _taken(world, event):
    return [f"You swallow the pill; its {event.data['effect']} works through you."], {}


@summary("pill_taken")
def _taken_line(world, entry, names, place, other):
    return f"Swallowed a {entry.data['effect']} pill."


@outcome("blade_coated", body_facts=False)
def _coated(world, event):
    return ["You work the venom into the edge. Three wounds' worth."], {}


@summary("blade_coated")
def _coated_line(world, entry, names, place, other):
    return "Coated a blade with venom."


@outcome("acupoints_sealed", body_facts=False)
def _sealed(world, event):
    return ["Two fingers, three points: the poison stops where it is, for now."], {}


@summary("acupoints_sealed")
def _sealed_line(world, entry, names, place, other):
    return "Sealed acupoints against a poison."


@outcome("poison_forced", body_facts=False)
def _forced(world, event):
    if event.data["cleared"]:
        return ["Black blood beads at your fingertips and the poison is gone."], {}
    return ["You drive some of it out; the rest holds on."], {}


@summary("poison_forced")
def _forced_line(world, entry, names, place, other):
    return "Forced a poison out."


@outcome("poison_art_bought", body_facts=False)
def _art(world, event):
    return ["A thin manual, stained, smelling of bitter almonds, changes hands."], {}


@summary("poison_art_bought")
def _art_line(world, entry, names, place, other):
    return "Bought a poison art."


@outcome("beast_butchered", body_facts=False)
def _butchered(world, event):
    if event.data["part"] == "blood":
        return ["The blood is hot and bitter. Your body will know that venom again."], {}
    return ["The core is the size of a fist and burns going down."], {}


@summary("beast_butchered")
def _butchered_line(world, entry, names, place, other):
    return f"Took the {entry.data['part']} of a venomous beast."


@outcome("bathed", body_facts=False)
def _bathed(world, event):
    d = event.data
    line = f"A day in the scalding herbs. Your {d['stat']} is the better for it."
    if d["pain"]:
        line += " It hurt more than it should have."
    if d["awaken"]:
        line += f" Something wakes in your bones: a {d['awaken']}."
    return [line], {}


@summary("bathed")
def _bathed_line(world, entry, names, place, other):
    return f"Took a tempering bath for {entry.data['stat']}."
```

`narrate/grammar/alchemy.toml`:
```toml
[symbols]
furnace_air = ["The furnace ticks as it cools.", "Bitter smoke hangs under the eaves.", "A smell of roots and iron.", "Somewhere a mortar grinds.", "The herbs keep their secrets poorly.", "Steam beads on the bronze."]

[herb_tasted]
colour = "dim"
lines = ["#furnace_air#"]

[herbs_gathered]
colour = "dim"
lines = ["#furnace_air#"]

[herb_bought]
colour = "dim"
lines = ["#furnace_air#"]

[furnace_bought]
colour = "dim"
lines = ["#furnace_air#"]

[experimented]
colour = "dim"
lines = ["#furnace_air#"]

[refined]
colour = "dim"
lines = ["#furnace_air#"]

[pill_taken]
colour = "dim"
lines = ["#furnace_air#"]

[blade_coated]
colour = "dim"
lines = ["#furnace_air#"]

[acupoints_sealed]
colour = "dim"
lines = ["#furnace_air#"]

[poison_forced]
colour = "dim"
lines = ["#furnace_air#"]

[poison_art_bought]
colour = "dim"
lines = ["#furnace_air#"]

[beast_butchered]
colour = "dim"
lines = ["#furnace_air#"]

[bathed]
colour = "dim"
lines = ["#furnace_air#"]
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5b_task6.py`:
```python
"""Phase 5b, Task 6: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('engine/commands.py', r'''    "smith": Action("smith"), "unwield": Action("put_away", "weapon"), "sheathe": Action("put_away", "weapon"),
''', r'''    "smith": Action("smith"), "unwield": Action("put_away", "weapon"), "sheathe": Action("put_away", "weapon"),
    "alchemy": Action("alchemy"), "pills": Action("alchemy"), "gather": Action("gather"),
    "search for herbs": Action("gather"), "herbalist": Action("herbalist"), "seal": Action("seal"),
    "seal acupoints": Action("seal"), "force out": Action("force_out"), "force poison": Action("force_out"),
    "light furnace": Action("experiment"), "experiment": Action("experiment"), "empty furnace": Action("empty_furnace"),
''')
edit('engine/commands.py', r'''    "wield": "wield", "wear": "wield", "inspect": "inspect", "buy": "buy_gear", "sell": "sell_gear",
''', r'''    "wield": "wield", "wear": "wield", "inspect": "inspect", "buy": ("buy_gear", "buy_herb"), "sell": "sell_gear",
    "taste": "taste", "refine": "refine", "add": "add_herb", "temper": "bathe",
''')
edit('engine/crisis.py', r'''    def _nameable_claimants(self, crisis: dict) -> list[dict]:
        """The standing claimants a choice may name: those heard of or met, those here, and yourself (5a review)."""
        world, me = self.world, self.player.id
        known = set(known_people(world, me)) | {p.id for p in people_at(world, self.place.id)} | {me}
        return [c for c in SC.standing_claimants(world, crisis) if c["person"] in known]
''', r'''    def _nameable(self) -> set[int]:
        """Whom a choice may name: those heard of or met, those here, and yourself (5a review, 5b)."""
        world, me = self.world, self.player.id
        return set(known_people(world, me)) | {p.id for p in people_at(world, self.place.id)} | {me}

    def _nameable_claimants(self, crisis: dict) -> list[dict]:
        known = self._nameable()
        return [c for c in SC.standing_claimants(self.world, crisis) if c["person"] in known]
''')
edit('engine/crisis.py', r'''                for successor in R.successors(world, me, fid):
''', r'''                known = self._nameable()
                for successor in [s for s in R.successors(world, me, fid) if s in known]:  # only whom you know (5b)
''')
edit('engine/game.py', r'''from engine.crisis import CrisisMixin
''', r'''from engine.crisis import CrisisMixin
from engine.alchemy import AlchemyMixin
''')
edit('engine/game.py', r'''    ("  F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu", "system"),
]


class Game(GearMixin, IntrigueMixin, CrisisMixin, SealedMixin, RivalMixin, ChamberMixin, DelveMixin, LineageMixin, MarketMixin, SkyMixin, TournamentMixin, WorldMixin, FactionsMixin, JoiningMixin, RanksMixin, DutiesMixin, PoliticsMixin, LeavingMixin, LawMixin, LandMixin, FoundingMixin, SectMixin, SeasonsMixin, GossipMixin, MasksMixin, InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks):
''', r'''    ("  alchemy | gather | herbalist | taste <herb> | refine <recipe> | swallow | seal | force out: herbs, pills, poison",
     "system"),
    ("  F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu", "system"),
]


class Game(AlchemyMixin, GearMixin, IntrigueMixin, CrisisMixin, SealedMixin, RivalMixin, ChamberMixin, DelveMixin, LineageMixin, MarketMixin, SkyMixin, TournamentMixin, WorldMixin, FactionsMixin, JoiningMixin, RanksMixin, DutiesMixin, PoliticsMixin, LeavingMixin, LawMixin, LandMixin, FoundingMixin, SectMixin, SeasonsMixin, GossipMixin, MasksMixin, InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks):
''')
edit('engine/game.py', r'''        return handler(action.target)
''', r'''        return self._after_turn(handler(action.target))
''')
edit('engine/hooks.py', r'''    def _after_duel(self, data: dict) -> list:
        return []
''', r'''    def _after_duel(self, data: dict) -> list:
        return []

    def _after_turn(self, turn):
        """The turn once the whole deed is done (phase 5b: a poison's death waits for it)."""
        return turn
''')
edit('engine/sheet.py', r'''
from engine.gear_page import armour_words, weapon_words
''', r'''
from engine.alchemy_page import constitution_words
from engine.gear_page import armour_words, weapon_words
''')
edit('engine/sheet.py', r'''        (f"Constitution: {body.constitution if body.constitution and body.constitution_known else 'unknown'}", "default"),
''', r'''        (f"Constitution: {body.constitution if body.constitution and body.constitution_known else 'unknown'}"
         f"{constitution_words(world, player_id)}", "default"),
''')
edit('narrate/outcomes.py', r'''import narrate.gear_text  # noqa: E402,F401
''', r'''import narrate.gear_text  # noqa: E402,F401
import narrate.alchemy_text  # noqa: E402,F401
''')
edit('systems/agendas.py', r'''REVENGE_CHANCE, FEUD_DEATH, APPRENTICE_CHANCE = 0.1, 0.2, 0.05
''', r'''REVENGE_CHANCE, FEUD_DEATH, APPRENTICE_CHANCE = 0.1, 0.2, 0.05
MASTER_AGE = 20  # no child takes a disciple, however strong
''')
edit('systems/agendas.py', r'''    if realm_index(entity.data.get("realm", "mortal")) < 2 or _kin(world, person, "disciple") \
            or rng.random() >= APPRENTICE_CHANCE:
''', r'''    if realm_index(entity.data.get("realm", "mortal")) < 2 or _age(entity) < MASTER_AGE \
            or _kin(world, person, "disciple") or rng.random() >= APPRENTICE_CHANCE:  # a master is grown (5b fuzz)
''')
edit('systems/alchemy.py', r'''    return item
''', r'''    return item


def find_batch(world, person: int, recipe: int) -> list[int] | None:
    """The cheapest handful of carried herbs that meets a known recipe, if any (for the refine choice)."""
    from itertools import combinations
    base = RECIPES[world.entity(recipe).data["key"]]
    herbs = sorted(H.herbs_of(world, person), key=lambda h: (H.herb_info(h)[1], H.props(H.herb_info(h)[0])["price"], h.id))
    fitting = [h for h in herbs if H.props(H.herb_info(h)[0])["element"] in (base["element"], "none")
               or H.props(H.herb_info(h)[0])["polarity"] == base["polarity"]][:10]
    for size in range(MIN_HERBS, MAX_HERBS + 1):
        for batch in combinations(fitting, size):
            if all(met(base, combine([H.herb_info(h)[0] for h in batch])).values()):
                return [h.id for h in batch]
    return None
''')
edit('systems/toxins.py', r'''from world.body import WATCHES_PER_DAY
''', r'''from world.body import POISONED_TO_DEATH, WATCHES_PER_DAY
''')
edit('systems/toxins.py', r'''FORCE_REALM, FORCE_QI = 3, 10.0
''', r'''FORCE_REALM, FORCE_QI = 3, 10.0
NAMED = frozenset({"a swallowed poison", "a furnace's fumes"})
''')
edit('systems/toxins.py', r'''    body.poisons = body.poisons + [{"grade": int(grade), "strength": int(strength), "days": 0.0,
                                    "at": world.time, "sealed_until": 0, "source": source}]
''', r'''    named = source in NAMED or source.startswith("tasting ")  # a poison one took knowingly: its grade is known
    body.poisons = body.poisons + [{"grade": int(grade), "strength": int(strength), "days": 0.0,
                                    "at": world.time, "sealed_until": 0, "source": source, "named": named}]
''')
edit('systems/toxins.py', r'''    """The poison that has outlasted this body: of grade 4 or more, past realm + 2 days (spec 4.2)."""
    return next((p for p in body.poisons if p["grade"] >= LETHAL_GRADE and p["days"] > body.realm + 2), None)
''', r'''    """The poison that has outlasted this body: of grade 4 or more, past realm + 2 days (spec 4.2), even if it has
    since run its course (a long rest does not outwait one's own death)."""
    found = next((p for p in body.poisons if p["grade"] >= LETHAL_GRADE and p["days"] > body.realm + 2), None)
    if found is None and POISONED_TO_DEATH in body.flags:
        return {"grade": LETHAL_GRADE, "strength": 0, "days": body.realm + 3, "source": "a poison"}
    return found
''')
edit('tests/test_fuzz.py', r'''        elif T.here(game.world, game.place.id, T.KINDS, ("announced",)) is not None and rng.random() < 0.5:
''', r'''        elif game.world.targets(game.player.id, "located_in")                 and T.here(game.world, game.place.id, T.KINDS, ("announced",)) is not None and rng.random() < 0.5:
''')
edit('world/body.py', r'''RESIDUE_FADE_PER_WEEK, PURE_FADE = 2.0, 0.8  # residue fades twice as fast in a body purer than this (5b)
''', r'''RESIDUE_FADE_PER_WEEK, PURE_FADE = 2.0, 0.8  # residue fades twice as fast in a body purer than this (5b)
LETHAL_POISON, POISONED_TO_DEATH = 4, "poisoned to death"
''')
edit('world/body.py', r'''            add_injury(body, "torso", "internal", p["grade"], now, "poison")
''', r'''            add_injury(body, "torso", "internal", p["grade"], now, "poison")
        if p["grade"] >= LETHAL_POISON and p["days"] > body.realm + 2 and POISONED_TO_DEATH not in body.flags:
            body.flags.append(POISONED_TO_DEATH)  # it outlasted the body, even if it ran out since
''')
print("task 6 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5b_task6.py`
Expected: `task 6 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_alchemy_play.py tests/test_sheet.py tests/test_commands.py`
Expected: `26 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the player's alchemy - the furnace page, gathering, the herbalist, baths, poison felt and fought

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: Alchemy end to end

The fork guide's section 11, the speed of experiments, refining, the refine choices and the poison watch, and a wandering alchemist played at random.

**Files:**
- Create: `tests/test_alchemy_fuzz.py`
- Create: `tests/test_alchemy_season.py`
- Modify (by `.patches/5b_task7.py`): `docs/world-events.md`

**Interfaces:**
- Consumes: Everything above.
- Produces:
  - `docs/world-events.md` section 11.
  - `tests/test_alchemy_fuzz.py`: `test_a_wandering_alchemist`.

- [ ] **Step 1: Write the failing tests**

`tests/test_alchemy_fuzz.py`:
```python
"""A wandering alchemist, played at random (phase 5b): gathers, buys, tastes, experiments, refines, swallows and
fights; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing


@pytest.mark.parametrize("seed", [6, 33])
def test_a_wandering_alchemist(tmp_path, seed):
    import systems.herbs as H
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Alchemist{seed}", world_seed=seed)
    world = app.game.world
    me = world.get_meta("player_id")
    world.update_data(me, silver=3000)
    for name in ("ginseng", "tiger bone vine", "frost lotus leaf", "frost lotus leaf", "black lotus", "corpse flower",
                 "willow bark", "willow bark", "golden sun peach", "golden sun peach", "golden sun peach"):
        H.make_herb(world, name, 0, me)
    app.submit("look")
    happened = set()
    for step in range(260):
        game = app.game
        if game is None:
            break
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.6 and app.choices:
            stay = [n for n, c in enumerate(app.choices, 1) if c.action.verb not in ("travel", "routes")]
            app.submit(str(rng.choice(stay or [1])))
        else:
            app.submit(rng.choice(["alchemy", "gather", "herbalist", "swallow", "seal", "force out", "look", "rest",
                                   "journal", "experiment", "empty furnace",
                                   "taste " + rng.choice(("ginseng", "lotus", "willow", "peach", "vine")),
                                   "add " + rng.choice(("ginseng", "lotus", "willow", "peach", "vine"))]))
        if rng.random() < 0.05:
            app.handle_key("f4", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    done = happened & {"herb_tasted", "herbs_gathered", "herb_bought", "experimented", "refined", "pill_taken"}
    assert len(done) >= 3, done
    app.shutdown()
```

`tests/test_alchemy_season.py`:
```python
import gc
import time
from pathlib import Path

import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.herbs as H
import systems.toxins as X
from engine.game import Game
from systems.creation import CreationChoice

BATCH = ["ginseng", "tiger bone vine"]


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=100000)
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


def test_the_fork_guide_covers_alchemy():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("herbs.toml", "recipes.toml", "herb_lore", "knows_recipe", "residue", "poisoned", "WOUND_HOOKS",
                 "ABSORB_HOOKS", "BEAST_HOOKS", "Myriad Poison Body", "check_alchemy"):
        assert word in guide, word


def test_an_experiment_and_a_refining_are_quick(game):
    world, me = game.world, game.player.id
    herbs = [H.make_herb(world, n, 0, me) for n in BATCH]
    assert average(lambda: A.experiment_events(world, me, game.place.id, herbs)) < 0.005
    recipe = A.recipe_entity(world, "earth_qi")
    world.relate(me, recipe, "knows_recipe", 0.5)
    assert average(lambda: A.refine_events(world, me, game.place.id, recipe, herbs)) < 0.005


def test_the_poison_watch_over_twenty_poisoned_is_quick(game):
    world = game.world
    for n in range(20):
        person = world.add_entity("person", f"Sick {n}", {"occupation": "tea seller", "traits": [], "realm": "mortal",
                                                          "portrait": {"hair": 0, "face": 0, "robe": 0}}, f"test:sick:{n}")
        world.relate(person, game.place.id, "located_in")
        X.poison(world, person, 2, 40, "test")
    assert len(world.get_meta("poisoned")) == 20
    assert average(lambda: X.season_hook(world, 1)) < 0.05


def test_the_refine_choices_stay_quick_with_many_herbs(game):
    world, me = game.world, game.player.id
    for n in range(30):
        H.make_herb(world, sorted(H.HERBS)[n % len(H.HERBS)], 0, me)
    for key in list(A.RECIPES)[:6]:
        world.relate(me, A.recipe_entity(world, key), "knows_recipe", 0.2)
    assert average(lambda: [A.find_batch(world, me, r) for r, _ in A.known_recipes(world, me)]) < 0.05
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_alchemy_fuzz.py tests/test_alchemy_season.py`
Expected: `1 failed, 5 passed`: the fork guide (`AssertionError: herbs.toml`); the speed tests and the fuzz already pass.

- [ ] **Step 3: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5b_task7.py`:
```python
"""Phase 5b, Task 7: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('docs/world-events.md', r'''their seed.
''', r'''their seed.

## 11. Alchemy, medicine and poison (phase 5b)

**Herbs** are entities (`kind = "herb"`: a `herb` name and a `grade` of age, 0-3) whose properties belong to the
name, in `systems/data/herbs.toml` (element, polarity, potency, toxicity, terrains, price). A 4d treasure herb
counts as a herb of the table (`herbs.herb_info`). A person's `herb_lore` lists the names they know.

**Recipes** are the base needs in `systems/data/recipes.toml` (a dominant element, a polarity, a total potency, a
toxicity bound); a world's recipe entity (`recipe:{key}`) is made when first found, and a person knows it through a
`knows_recipe` relation whose value is their mastery. **Pills** are entities (`kind = "pill"`: `effect`, `grade`,
`purity`, `recipe`, `maker`).

**The body** gains `residue`, `venom`, `poisons` (active: grade, strength, days, sealed_until, named), `resist`,
`baths` and `breakthrough_aid`, all run lazily by `world.body.settle`. The meta row `poisoned` lists the NPCs
carrying a poison, so only they are looked at for a poison's death.

**Where the rules live:**
- `systems/toxins.py`: residue, active poison, sealing, forcing out, antidotes, death by poison; the registries
  `WOUND_HOOKS` (a wound that poisons) and `ABSORB_HOOKS` (what a body lets in).
- `systems/herbs.py`, `systems/alchemy.py`, `systems/pills.py`: herbs, experiments and refining, pills and venom.
- `systems/poison_path.py`: the poison path, the Myriad Poison Body, venomous beasts (`encounters.BEAST_HOOKS`),
  tempering baths.

**The rules:** `check_alchemy` in `debug/invariants.py` holds herbs of the table, well-made pills and masteries
within 0-1; `check_body` keeps residue and venom within 0-100 and poisons well formed; `check_toxins` keeps the
poisoned index to NPCs.
''')
print("task 7 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5b_task7.py`
Expected: `task 7 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_alchemy_season.py tests/test_alchemy_fuzz.py`
Expected: `6 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Run the 500-year soak**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: alchemy end to end - the fork guide, speed, and a wandering alchemist's fuzz

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Self-review

- **Spec coverage:**
  - §2.1-2.3 herbs, lore, gathering, the herbalist, furnaces (Task 2);
  - §3.1-3.3 recipes, experiments, refining (Task 3);
  - §4.1 pills (Task 4); §4.2 active poison and §4.5 residue (Task 1); §4.3 the poison path, §4.4 the Poison Body, §4.5 tempering, §4.6 venomous beasts (Task 5);
  - §5 the player (Task 6); §6 knowledge (Tasks 2, 3, 6; ruling 10); §7 `check_alchemy` (Tasks 1, 5); §8 LOD and speed (Tasks 1, 7); §9 testing (every task; the fuzz and speed in Task 7).
- **Dry run:**
  - every task was applied in order to a copy of master; its tests failed as each Step 2 says, then passed;
  - the whole suite passed after every task, and the 500-year soak passed at the end.
