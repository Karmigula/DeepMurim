# DeepMurim Phase 2b (Combat & Sources) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- **Duels:** exchange-round duels where realm, technique, body and choices all matter, against an opponent that reads your habits.
- **Opponents:** spar or challenge NPCs, meet bandits, beasts and rival wanderers on the road, and be challenged by NPCs who hold a grudge.
- **Sources of arts:** learn from teachers, buy manuals that may secretly be incomplete, and turn glimpsed fragments into arts of your own.

**Architecture:**
- **Pure core:** duel arithmetic (`systems/combat_core.py`) and the opponent's mind (`systems/opponent.py`) are pure functions over `Fighter` snapshots, so a solver (`systems/duel_sim.py`) can test balance with no database.
- **World layer:** `systems/duel.py` builds fighters from bodies and decides every exchange from seeded randomness. It stores the whole result in the event, and effects only apply it, so replay and narration agree.
- **Engine hooks:** the engine gains a `GameHooks` base with extension points. Each new feature arrives as a mixin (`FightMixin`, `RoadsMixin`, `DealingsMixin`, `InventingMixin`) that overrides the hooks cooperatively, which keeps `engine/game.py` from growing without bound.
- **Narration registry:** a `narrate/outcomes.py` registry lets each feature supply its own outcome lines and journal summaries.

**Tech Stack:** Python 3.14, pygame-ce (window only), sqlite3/json1, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-22-phase2-cultivation-combat-design.md` §9 (combat) and §10 (opponents and sources), built on the merged 2a code. Parent: `docs/superpowers/specs/2026-09-22-deepmurim-design.md` §6.0 (Briefs).

## Global Constraints

- The engine is the only writer. State changes go through `world.events.commit`. **Generation writes directly, inside a transaction**: materializing roamers, NPC arts, NPC purses, merchant goods, and lazy bodies.
- **No new tables; the schema stays at version 1.**
  - New data lives in entity `data`, plus the relations `owns` (person→manual) and `knows`.
  - New entity kind: `manual`.
  - Beasts are `person` entities with `data["beast"] = True`.
- All randomness comes from `world.seed.rng_for`. Salts:
  - `duel:{duel_id}:{n}` for exchanges, `duel:{duel_id}:verdict` for verdicts
  - `road:{player}:{time}` for road encounters, `challenge:{player}:{place}:{time}` for challenges
  - `accept:{mode}:{npc}:{time}` for accepting a fight
  - `{seed_path}/arts`, `{seed_path}/silver` and `{seed_path}/goods` for NPC generation
- **Every exchange, ending, encounter and lesson is one Event whose data holds the complete outcome.** Effects never roll dice.
- **No death in phase 2.** Losing means injuries, robbery, humiliation, or a permanent crippling injury.
- **Briefs:** at most 6 facts, at most 4 outcome lines, a prompt of at most 1,200 characters, no ids.
  - Never include a manual's true completeness or an undiscovered constitution.
  - Only `known_completeness` and `claimed_completeness` are ever shown.
- **Menus:** at most 9 choices shown. Folded choices go in `Turn.extra`. Labels use ASCII `...`.
- Only `render/screen.py` and `main.py` import pygame.
- **Patch scripts:**
  - Changes to existing files that aren't whole-file rewrites ship as `.patches/2b_taskN.py` scripts. Task 1 adds `.patches/` to `.gitignore`.
  - Run a task's patch script **after** writing its files and **before** its test run, from the repo root: `python .patches/2b_taskN.py`.
  - Each patch script asserts that every search string occurs exactly once.
- **Tests:** run with `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.
- Every commit message ends with a blank line, then `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Balance constants were tuned in a prototype against spec §9.5 before this plan was written.** They are `DAMAGE_BASE = 35`, a Guard that counters for ×0.5, and an AI with `RECENT_WEIGHT = 0.75` and `PATTERN_WEIGHT = 3.0`.
  - Prototype results: a realm gap wins about 99%, equal fighters about 50%, and fixed moves at most 49%.
  - Cycling the four moves wins 53% and alternating Strike/Feint 56%.
  - If a balance test fails, retune these constants and record a ruling. **Never loosen a spec target.**
- **Intentional spec deviations**, which Task 10 writes back into the spec:
  1. Guard counters a Strike for ×0.5 as well as gaining an opening. Without the counter, "always Strike" beats any adaptive opponent.
  2. `DAMAGE_BASE` is 35, not 10. That puts fights at the spec's 3–8 exchanges.
  3. The AI reads your recent moves (+0.75 each) and the patterns in what you play next (+3.0 spread across observed follow-ups), not +0.5 on the last three moves. This stops predictable cycles from exploiting it.
  4. "Watching duels" gives no fragments yet: NPC-versus-NPC duels arrive with the phase 4 world simulation.
  5. Created arts get generated names; there is no typed naming.
  6. Roaming bandits, beasts and wanderers are located in their **region**, not in a town.

## Review Focus

1. **Quitting mid-fight, mid-encounter or mid-challenge, then pressing Continue.** The fight or encounter must resume exactly, never vanish and never double-apply. Tested in Tasks 4, 6 and 7.
2. **Commands that don't belong in the current state.** Typing `meditate` mid-fight, pressing `Talk` during an encounter, or giving a verdict when there is none. Each must refuse politely, change nothing, and never crash. Tested in Tasks 6 and 7.
3. **Paying with silver you don't have.** Buying a manual, paying a toll or paying for a lesson with too little silver must refuse and leave everything unchanged. Tested in Tasks 1 and 8.
4. **A lopsided fight.** A severed-meridian art, zero qi, a beast opponent, or a first-rate bandit against a mortal must all resolve without crashing, and the player never dies. Tested in Tasks 4 and 10.
5. **A flawed manual.** Its true completeness must never appear in any output until practice at the cap triggers the revealing deviation. Tested in Tasks 8 and 10.

---

## File map

| File | Responsibility |
|---|---|
| `systems/purse.py` | seeded NPC purses, `paid` event |
| `systems/items.py` | manuals as items, ownership, `handed_over` event |
| `systems/combat_core.py` | pure duel arithmetic: `Fighter`, power, resolution table, wounds, flee |
| `systems/opponent.py` | the opponent's intent/qi/give-up choices, tendency words |
| `systems/duel_sim.py` | headless duels for balance tests |
| `systems/duel.py` | NPC arts, fighters from bodies, `Duel` state, start/exchange/verdict/yield events and effects, rebuild |
| `narrate/outcomes.py` | registries: outcome builders, body-fact kinds, journal summaries |
| `narrate/combat_text.py` + `narrate/grammar/combat.toml` | duel outcome lines, summaries, prose |
| `engine/hooks.py`, `engine/fight.py` | `GameHooks` extension points; `FightMixin` |
| `engine/game.py`, `engine/commands.py` (rewrite) | hooks wired in; fight words |
| `render/art.py` (modify), `assets/art/beast.art` | duel art: portrait or beast, plus a harm bar |
| `systems/encounters.py`, `engine/roads.py`, `narrate/road_text.py`, `narrate/grammar/roads.toml` | road encounters, grudge challenges |
| `systems/learning.py`, `engine/dealings.py`, `narrate/learning_text.py`, `narrate/grammar/learning.toml` | teachers, merchant manuals, studying, the flaw reveal |
| `systems/inventing.py`, `engine/inventing.py`, `narrate/grammar/inventing.toml` | turning fragments into arts |
| `debug/invariants.py` (modify) | combat, item, purse and fragment rules |

---

### Task 1: Purse and manuals

**Files:**
- Create: `systems/purse.py`, `systems/items.py`
- Modify: `.gitignore` (add `.patches/`)
- Test: `tests/test_purse_items.py`

**Interfaces:**
- Produces:
  - In `systems/purse.py`: `OCCUPATION_SILVER`, `silver_of(world, person_id) -> int` (seeds and stores an NPC's purse on first use), `payment_events(payer, payee, place, amount, reason) -> list[Event]`, and an effect for the `paid` event kind. The effect raises `ValueError` if the payer can't afford it.
  - In `systems/items.py`:
    - `Manual(item, technique)`, with `.name`, `.true_completeness`, `.claimed` and `.grade`
    - `create_manual(world, owner_id, technique_id, true_completeness, claimed=1.0) -> int`
    - `manuals_of(world, person_id) -> list[Manual]`, `manual_price(manual) -> int`
    - `transfer_events(giver, taker, place, item_ids, reason) -> list[Event]`, with an effect for `handed_over`

- [ ] **Step 1: Write the failing test** — `tests/test_purse_items.py`
```python
import pytest

from engine.game import Game
from systems.creation import CreationChoice
from systems.items import create_manual, manual_price, manuals_of, transfer_events
from systems.purse import payment_events, silver_of
from systems.techniques import create_technique, generate
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "merchant"))
    yield g
    g.close()


def merchant(game):
    pid = game.world.add_entity("person", "Rich Ma", {"occupation": "merchant", "traits": ["greedy"]}, seed_path="test:merchant")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def technique(game, grade=2):
    name, data = generate(rng_for(1, "t"), "martial", form="palm", grade=grade)
    return create_technique(game.world, name, data)


def test_npc_purses_are_seeded_and_stable(game):
    npc = merchant(game)
    first = silver_of(game.world, npc)
    assert 40 <= first <= 200 and silver_of(game.world, npc) == first
    assert game.world.entity(npc).data["silver"] == first
    assert silver_of(game.world, game.player.id) == 200  # merchant's runaway


def test_payment_moves_silver(game):
    npc = merchant(game)
    before = silver_of(game.world, npc)
    commit(game.world, payment_events(game.player.id, npc, game.place.id, 50, "test"))
    assert silver_of(game.world, game.player.id) == 150 and silver_of(game.world, npc) == before + 50


def test_paying_more_than_you_have_changes_nothing(game):
    npc = merchant(game)
    before = (silver_of(game.world, game.player.id), silver_of(game.world, npc))
    with pytest.raises(ValueError):
        commit(game.world, payment_events(game.player.id, npc, game.place.id, 5000, "test"))
    assert (silver_of(game.world, game.player.id), silver_of(game.world, npc)) == before


def test_manuals_are_owned_priced_and_handed_over(game):
    npc = merchant(game)
    item = create_manual(game.world, npc, technique(game, grade=2), 0.6)
    [manual] = manuals_of(game.world, npc)
    assert manual.item.id == item and manual.claimed == 1.0 and manual.true_completeness == 0.6
    assert manual.name.endswith(" manual") and manual_price(manual) == 15 * 4 + 10
    commit(game.world, transfer_events(npc, game.player.id, game.place.id, [item], "bought"))
    assert manuals_of(game.world, npc) == [] and [m.item.id for m in manuals_of(game.world, game.player.id)] == [item]
    with pytest.raises(ValueError):
        commit(game.world, transfer_events(npc, game.player.id, game.place.id, [item], "again"))
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: systems.purse`)

- [ ] **Step 3: Implement.** First run `printf '.patches/\n' >> .gitignore`.

`systems/purse.py`:
```python
"""Silver (phase 2 spec §8). Changed only through events; NPC purses are seeded on first use."""

from world.db import World
from world.events import Event, effect
from world.seed import rng_for

OCCUPATION_SILVER = {
    "merchant": (40, 200), "innkeeper": (20, 80), "scholar": (10, 60), "blacksmith": (15, 60),
    "constable": (10, 40), "wandering swordsman": (5, 50), "bandit": (10, 120), "beggar": (0, 5),
}
DEFAULT_SILVER = (5, 30)


def silver_of(world: World, person_id: int) -> int:
    entity = world.entity(person_id)
    if "silver" in entity.data:
        return int(entity.data["silver"])
    if entity.data.get("beast"):
        amount = 0
    else:
        low, high = OCCUPATION_SILVER.get(entity.data.get("occupation"), DEFAULT_SILVER)
        key = entity.seed_path or f"entity:{person_id}"
        amount = rng_for(world.world_seed, f"{key}/silver").randint(low, high)
    world.update_data(person_id, silver=amount)
    return amount


def payment_events(payer: int, payee: int | None, place: int, amount: int, reason: str) -> list[Event]:
    actors = (payer,) if payee is None else (payer, payee)
    return [Event("paid", actors, place, {"amount": int(amount), "reason": reason})]


@effect("paid")
def _paid(world: World, event: Event) -> None:
    amount, payer = event.data["amount"], event.actors[0]
    have = silver_of(world, payer)
    if amount < 0 or amount > have:
        raise ValueError(f"#{payer} cannot pay {amount} silver (has {have})")
    world.update_data(payer, silver=have - amount)
    if len(event.actors) > 1:
        payee = event.actors[1]
        world.update_data(payee, silver=silver_of(world, payee) + amount)
```
`systems/items.py`:
```python
"""Manuals as items (phase 2 spec §10), owned through the `owns` relation.

A manual carries a technique, how complete it truly is, and how complete it
claims to be. Only the claim is ever shown, until practice proves it wrong.
"""

from dataclasses import dataclass

from world.db import Entity, World
from world.events import Event, effect


@dataclass(frozen=True)
class Manual:
    item: Entity
    technique: Entity

    @property
    def name(self) -> str:
        return self.item.name

    @property
    def true_completeness(self) -> float:
        return self.item.data["true_completeness"]

    @property
    def claimed(self) -> float:
        return self.item.data["claimed_completeness"]

    @property
    def grade(self) -> int:
        return self.technique.data["grade"]


def create_manual(world: World, owner_id: int, technique_id: int, true_completeness: float, claimed: float = 1.0) -> int:
    technique = world.entity(technique_id)
    data = {"technique": technique_id, "true_completeness": round(true_completeness, 2), "claimed_completeness": claimed}
    with world.transaction():
        item = world.add_entity("manual", f"{technique.name} manual", data)
        world.relate(owner_id, item, "owns")
    return item


def manuals_of(world: World, person_id: int) -> list[Manual]:
    manuals = []
    for item_id in world.targets(person_id, "owns"):
        item = world.entity(item_id)
        if item.kind == "manual":
            manuals.append(Manual(item, world.entity(item.data["technique"])))
    return manuals


def manual_price(manual: Manual) -> int:
    return int(15 * manual.grade ** 2 * manual.claimed) + 10


def transfer_events(giver: int, taker: int, place: int, item_ids, reason: str) -> list[Event]:
    return [Event("handed_over", (giver, taker), place, {"items": list(item_ids), "reason": reason})]


@effect("handed_over")
def _handed_over(world: World, event: Event) -> None:
    giver, taker = event.actors
    for item in event.data["items"]:
        if item not in world.targets(giver, "owns"):
            raise ValueError(f"#{giver} does not own item #{item}")
        world.unrelate(giver, "owns", item)
        world.relate(taker, item, "owns")
```

- [ ] **Step 4: Run tests** → `tests/test_purse_items.py` PASS (4 passed), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: purses and manuals" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 2: Duel arithmetic (pure)

**Files:**
- Create: `systems/combat_core.py`
- Test: `tests/test_combat_core.py`

**Interfaces:**
- Consumes: `BODY_PARTS`, `REGULAR` (world.body)
- Produces:
  - Constants: `INTENTS`, `QI_OUTPUTS`, `QI_MULT`, `QI_COST`, `ALL_IN_DEVIATION=8`, `DAMAGE_BASE=35.0`, `INJURY_THRESHOLD=8.0`, `BROKEN=85.0`, `MAX_HARM=100.0`, `CONDITION_ORDER`, `FORM_STATS_EXTRA`
  - `Fighter(name, realm_mult, stage, technique, form, grade_mult, mastery, compat, body_fit, limb_injuries, leg_injuries, agility, qi, traits=(), beast=False, stance_favours=None)`. `form` is an art form, `"bare"`, or `"claws"`.
  - `Blow(target, damage)` and `Resolution(blows, openings, reveals, recover)`, where sides are `"a"` or `"b"`
  - Functions:
    - `condition_of(harm) -> str`, `limbs_for(form)`, `technique_power(f)`, `affordable(output, qi) -> str`
    - `power(f, intent, output, harm, opening) -> float`
    - `effects(a_intent, b_intent) -> list[tuple]`
    - `resolve(a_intent, b_intent, a_power, b_power, rng, scale=1.0) -> Resolution`
    - `wound(form, damage, rng, spar=False) -> tuple[str, str, int] | None`
    - `flee_chance(runner, chaser, runner_harm) -> float`

- [ ] **Step 1: Write the failing test** — `tests/test_combat_core.py`
```python
import random

import pytest

from systems.combat_core import (
    DAMAGE_BASE, INTENTS, Fighter, affordable, condition_of, effects, flee_chance, power, resolve, wound,
)
from world.body import REGULAR


def fighter(**kw):
    base = dict(name="A", realm_mult=1.0, stage=0, technique="Palm", form="palm", grade_mult=1.0, mastery=0.5,
                compat=1.0, body_fit=1.0, limb_injuries=0, leg_injuries=0, agility=10, qi=30.0)
    base.update(kw)
    return Fighter(**base)


class Fixed:
    """An rng whose uniform() always returns 1.0, to test exact damage."""

    def uniform(self, a, b):
        return 1.0


def test_condition_bands():
    assert [condition_of(h) for h in (0, 15, 35, 60, 85, 120)] == ["fresh", "bruised", "hurt", "badly hurt", "broken", "broken"]


def test_power_parts():
    assert power(fighter(), "strike", "steady", 0, False) == pytest.approx(1.0)
    assert power(fighter(realm_mult=3.0), "strike", "steady", 0, False) == pytest.approx(3.0)
    assert power(fighter(technique=None, form="bare"), "strike", "steady", 0, False) == pytest.approx(0.5)
    assert power(fighter(), "strike", "steady", 0, True) == pytest.approx(1.2)
    assert power(fighter(stance_favours="strike"), "strike", "steady", 0, False) == pytest.approx(1.1)
    assert power(fighter(limb_injuries=2), "strike", "steady", 0, False) == pytest.approx(0.85 ** 2)
    assert power(fighter(), "strike", "all-in", 70, False) == pytest.approx(1.7 * 0.7)
    assert power(fighter(beast=True, technique=None, form="claws"), "strike", "steady", 0, False) == pytest.approx(0.8)


def test_qi_output_drops_to_what_you_can_pay():
    assert affordable("all-in", 30) == "all-in"
    assert affordable("all-in", 7) == "full"
    assert affordable("full", 2) == "restrained"
    assert affordable("steady", 0) == "restrained"


def test_every_pair_has_a_rule_and_mirrors():
    swap = {"a": "b", "b": "a"}
    for x in INTENTS:
        for y in INTENTS:
            forward = sorted(effects(x, y), key=repr)
            backward = sorted(((e[0], swap[e[1]], *e[2:]) for e in effects(y, x)), key=repr)
            assert forward == backward, (x, y)


def test_resolution_table():
    r = resolve("strike", "probe", 1.0, 1.0, Fixed())
    assert [(b.target, b.damage) for b in r.blows] == [("b", DAMAGE_BASE)]
    r = resolve("strike", "guard", 1.0, 1.0, Fixed())
    assert [(b.target, b.damage) for b in r.blows] == [("a", DAMAGE_BASE * 0.5)] and r.openings == ("b",)
    r = resolve("feint", "probe", 1.0, 1.0, Fixed())
    assert r.blows[0].target == "a" and r.reveals == ("b",)
    assert resolve("guard", "guard", 1.0, 1.0, Fixed()).recover == ("a", "b")
    assert resolve("strike", "probe", 3.0, 1.0, Fixed()).blows[0].damage == pytest.approx(DAMAGE_BASE * 3 ** 0.8, abs=0.01)
    assert resolve("strike", "probe", 1.0, 1.0, Fixed(), scale=0.5).blows[0].damage == pytest.approx(DAMAGE_BASE / 2)


def test_wounds():
    rng = random.Random(1)
    assert wound("sword", 7.9, rng) is None
    assert wound("sword", 30, rng)[1:] == ("cut", 3)
    assert wound("fist", 40, rng)[1] == "fracture"
    assert wound("finger", 20, rng)[0] in REGULAR
    assert wound("finger", 60, rng, spar=True)[1:] == ("bruise", 2)
    assert wound("palm", 20, rng)[0] == "torso"
    assert wound("claws", 20, rng)[1] == "cut"


def test_flee_chance():
    a = fighter(agility=10)
    assert flee_chance(a, fighter(agility=10), 0) == pytest.approx(0.5)
    assert flee_chance(fighter(agility=18), a, 0) > 0.85
    assert flee_chance(fighter(leg_injuries=2), a, 70) < 0.1
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: systems.combat_core`)

- [ ] **Step 3: Implement** — `systems/combat_core.py`
```python
"""Duel arithmetic (phase 2 spec §9.2). Pure: fighter snapshots in, numbers out.

The engine builds `Fighter`s from bodies and arts; everything here is a
function of them plus a seeded rng, which is what lets a solver test balance
without a database. Deviations from the spec's first draft (Guard counters a
Strike; a larger damage base) come from the balance targets in §9.5.
"""

import math
from dataclasses import dataclass

from world.body import BODY_PARTS, REGULAR

INTENTS = ("strike", "feint", "guard", "probe")
QI_OUTPUTS = ("restrained", "steady", "full", "all-in")
QI_MULT = {"restrained": 0.7, "steady": 1.0, "full": 1.3, "all-in": 1.7}
QI_COST = {"restrained": 1, "steady": 3, "full": 6, "all-in": 12}
ALL_IN_DEVIATION = 8
DAMAGE_BASE = 35.0
INJURY_THRESHOLD = 8.0
OPENING_BONUS = 1.2
STANCE_BONUS = 1.1
BARE_HANDS = 0.5
BEAST_WEAPONS = 0.8
LIMB_PENALTY = 0.85
BROKEN = 85.0
MAX_HARM = 100.0
CONDITION_BANDS = ((15.0, "fresh"), (35.0, "bruised"), (60.0, "hurt"), (85.0, "badly hurt"))
CONDITION_ORDER = ("fresh", "bruised", "hurt", "badly hurt", "broken")
CONDITION_MULT = {"fresh": 1.0, "bruised": 0.95, "hurt": 0.85, "badly hurt": 0.7, "broken": 0.5}
ARMS = ("left arm", "right arm")
LEGS = ("left leg", "right leg")
FORM_LIMBS = {"footwork": LEGS}  # every other form fights with the arms
FORM_STATS_EXTRA = {"bare": ("strength",), "claws": ("strength", "agility")}
FORM_WOUND = {
    "sword": "cut", "saber": "cut", "spear": "cut", "claws": "cut", "staff": "bruise", "fist": "bruise",
    "bare": "bruise", "footwork": "bruise", "palm": "internal", "finger": "meridian",
}
BLUNT_TARGETS = ("head", "torso", "left arm", "right arm")
FORM_TARGETS = {
    "footwork": ("left leg", "right leg", "torso"), "palm": ("torso",),
    "fist": BLUNT_TARGETS, "bare": BLUNT_TARGETS, "staff": BLUNT_TARGETS,
}
# (A's intent, B's intent) -> effects, seen from A:
#   ("hit", target, multiplier) | ("opening", side) | ("reveal", learner) | ("recover", side)
TABLE = {
    ("strike", "strike"): [("hit", "b", 0.7), ("hit", "a", 0.7)],
    ("strike", "feint"): [("hit", "b", 1.0)],
    ("strike", "guard"): [("hit", "a", 0.5), ("opening", "b")],  # the guard turns the blow and counters
    ("strike", "probe"): [("hit", "b", 1.0)],
    ("feint", "feint"): [],
    ("feint", "guard"): [("hit", "b", 0.8)],
    ("feint", "probe"): [("hit", "a", 0.6), ("reveal", "b")],
    ("guard", "guard"): [("recover", "a"), ("recover", "b")],
    ("guard", "probe"): [("reveal", "b")],
    ("probe", "probe"): [("reveal", "a"), ("reveal", "b")],
}
SWAP = {"a": "b", "b": "a"}


@dataclass(frozen=True)
class Fighter:
    name: str
    realm_mult: float
    stage: int                 # 0..3: early, middle, late, peak
    technique: str | None      # the art's name, or None
    form: str                  # an art form, "bare" or "claws"
    grade_mult: float
    mastery: float
    compat: float
    body_fit: float            # 0.8 + 0.4 * governing stat / 20
    limb_injuries: int         # unhealed injuries on the limbs this form uses
    leg_injuries: int
    agility: int
    qi: float
    traits: tuple[str, ...] = ()
    beast: bool = False
    stance_favours: str | None = None


@dataclass(frozen=True)
class Blow:
    target: str
    damage: float


@dataclass(frozen=True)
class Resolution:
    blows: tuple[Blow, ...]
    openings: tuple[str, ...]
    reveals: tuple[str, ...]
    recover: tuple[str, ...]


def condition_of(harm: float) -> str:
    for limit, name in CONDITION_BANDS:
        if harm < limit:
            return name
    return "broken"


def limbs_for(form: str) -> tuple[str, ...]:
    return FORM_LIMBS.get(form, ARMS)


def technique_power(f: Fighter) -> float:
    if f.beast:
        return BEAST_WEAPONS
    if f.technique is None:
        return BARE_HANDS
    return f.grade_mult * (0.5 + f.mastery) * f.compat


def affordable(output: str, qi: float) -> str:
    index = QI_OUTPUTS.index(output)
    while index > 0 and QI_COST[QI_OUTPUTS[index]] > qi:
        index -= 1
    return QI_OUTPUTS[index]


def power(f: Fighter, intent: str, output: str, harm: float, opening: bool) -> float:
    value = (f.realm_mult * (1 + 0.1 * f.stage) * technique_power(f) * QI_MULT[output]
             * CONDITION_MULT[condition_of(harm)] * f.body_fit * LIMB_PENALTY ** f.limb_injuries)
    if opening:
        value *= OPENING_BONUS
    if f.stance_favours == intent:
        value *= STANCE_BONUS
    return value


def effects(a_intent: str, b_intent: str) -> list[tuple]:
    if (a_intent, b_intent) in TABLE:
        return TABLE[(a_intent, b_intent)]
    return [(e[0], SWAP[e[1]], *e[2:]) for e in TABLE[(b_intent, a_intent)]]


def resolve(a_intent: str, b_intent: str, a_power: float, b_power: float, rng, scale: float = 1.0) -> Resolution:
    blows, openings, reveals, recover = [], [], [], []
    for effect in effects(a_intent, b_intent):
        kind, side = effect[0], effect[1]
        if kind == "hit":
            hitter, target = (a_power, b_power) if side == "b" else (b_power, a_power)
            damage = DAMAGE_BASE * (hitter / max(target, 1e-6)) ** 0.8 * effect[2] * rng.uniform(0.8, 1.2) * scale
            blows.append(Blow(side, round(damage, 2)))
        elif kind == "opening":
            openings.append(side)
        elif kind == "reveal":
            reveals.append(side)
        else:
            recover.append(side)
    return Resolution(tuple(blows), tuple(openings), tuple(reveals), tuple(recover))


def wound(form: str, damage: float, rng, spar: bool = False) -> tuple[str, str, int] | None:
    """(location, kind, severity) for a blow, or None if it only bruised the fight, not the body."""
    if damage < INJURY_THRESHOLD:
        return None
    severity = min(5, 1 + int(damage // 12))
    kind = FORM_WOUND.get(form, "bruise")
    if spar:
        severity = min(2, severity)
        if kind == "meridian":
            kind = "bruise"
    if kind == "meridian":
        return (rng.choice(REGULAR), "meridian", severity)
    if kind == "bruise" and severity >= 4:
        kind = "fracture"
    return (rng.choice(FORM_TARGETS.get(form, BODY_PARTS)), kind, severity)


def flee_chance(runner: Fighter, chaser: Fighter, runner_harm: float) -> float:
    x = ((runner.agility - chaser.agility) / 4 - 0.5 * runner.leg_injuries
         - 0.5 * CONDITION_ORDER.index(condition_of(runner_harm)))
    return 1 / (1 + math.exp(-x))
```

- [ ] **Step 4: Run tests** → PASS (7 passed), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: pure duel arithmetic" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 3: The opponent's mind and the balance solver

**Files:**
- Create: `systems/opponent.py`, `systems/duel_sim.py`
- Test: `tests/test_opponent.py`

**Interfaces:**
- Consumes: Task 2
- Produces:
  - In `systems/opponent.py`:
    - Constants: `COUNTER`, `RECENT_WEIGHT=0.75`, `PATTERN_WEIGHT=3.0`
    - `intent_weights(traits, player_history, beast=False) -> dict`, `choose_intent(rng, weights) -> str`
    - `tendency(traits, beast=False) -> str`, giving "direct strikes", "feints and tricks", "a patient guard" or "testing probes"
    - `choose_output(traits, qi, own_harm, their_harm) -> str`
    - `gives_up(rng, traits, occupation, harm, beast=False) -> "yield" | "flee" | None`
  - In `systems/duel_sim.py`: `simulate(player, npc, strategy, rng, max_exchanges=40) -> (result, exchanges)`, where result is `"player"`, `"npc"` or `"draw"` and `strategy(rng, history) -> intent`.

- [ ] **Step 1: Write the failing test** — `tests/test_opponent.py`
```python
import random
import statistics

from systems.combat_core import INTENTS, Fighter
from systems.duel_sim import simulate
from systems.opponent import (
    COUNTER, PATTERN_WEIGHT, RECENT_WEIGHT, choose_intent, choose_output, gives_up, intent_weights, tendency,
)


def fighter(realm_mult=1.0, traits=("curious", "honest")):
    return Fighter("F", realm_mult, 0, "Palm", "palm", 1.0, 0.5, 1.0, 1.0, 0, 0, 10, 30.0, traits)


def random_player(rng, history):
    return rng.choice(INTENTS)


def always(intent):
    return lambda rng, history: intent


def rate(player, npc, strategy, n, seed=0):
    rng = random.Random(seed)
    results = [simulate(player, npc, strategy, rng) for _ in range(n)]
    return sum(r == "player" for r, _ in results) / n, statistics.mean(length for _, length in results)


def test_weights_follow_temper_habit_and_pattern():
    assert intent_weights(("hot-tempered",), [])["strike"] == 3.0
    assert intent_weights(("cunning",), [])["feint"] == 3.0
    after_strikes = intent_weights((), ["strike", "strike", "strike"])
    assert after_strikes["guard"] > 1 + 3 * RECENT_WEIGHT  # habit plus the strike-follows-strike pattern
    cycle = intent_weights((), ["strike", "feint", "guard", "probe", "strike"])
    assert cycle[COUNTER["feint"]] >= 1 + PATTERN_WEIGHT  # after a strike, this player feints
    assert intent_weights((), [], beast=True)["strike"] == 3.0


def test_choices():
    rng = random.Random(3)
    picks = [choose_intent(rng, {"strike": 1.0, "feint": 0.0, "guard": 0.0, "probe": 0.0}) for _ in range(20)]
    assert set(picks) == {"strike"}
    assert choose_output(("hot-tempered",), 30, 60, 10) == "all-in"
    assert choose_output(("hot-tempered",), 7, 60, 10) == "full"
    assert choose_output(("calm",), 30, 60, 10) == "steady"
    assert tendency(("cunning",)) == "feints and tricks" and tendency((), beast=True) == "direct strikes"


def test_giving_up_only_when_badly_hurt():
    rng = random.Random(1)
    assert gives_up(rng, ("cautious",), "tea seller", 20) is None
    outcomes = {gives_up(random.Random(s), ("cautious",), "tea seller", 70) for s in range(40)}
    assert outcomes == {None, "yield"}
    assert {gives_up(random.Random(s), (), "bandit", 70) for s in range(40)} == {None, "flee"}


def test_one_realm_gap_nearly_always_wins():
    weak, strong = fighter(1.0), fighter(3.0)
    assert rate(weak, strong, random_player, 200)[0] <= 0.05
    assert rate(strong, weak, random_player, 200)[0] >= 0.95


def test_equal_fighters_are_a_coin_toss_of_a_few_exchanges():
    win, length = rate(fighter(), fighter(), random_player, 400)
    assert 0.35 <= win <= 0.65
    assert 3 <= length <= 8


def test_no_fixed_strategy_dominates():
    for intent in INTENTS:
        assert rate(fighter(), fighter(), always(intent), 300)[0] <= 0.70, intent


def test_predictable_patterns_are_read():
    cycle = rate(fighter(), fighter(), lambda rng, h: INTENTS[len(h) % 4], 300)[0]
    alternate = rate(fighter(), fighter(), lambda rng, h: ("strike", "feint")[len(h) % 2], 300)[0]
    assert cycle <= 0.65 and alternate <= 0.65
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: systems.opponent`)

- [ ] **Step 3: Implement**

`systems/opponent.py`:
```python
"""How an NPC fights (phase 2 spec §9.4).

An opponent leans on its temper, then reads the player: each of your last
three moves raises the weight of its counter, and so does the move you have
tended to play after the one you just played. Predictable fighters lose.
"""

from systems.combat_core import INTENTS, affordable, condition_of

COUNTER = {"strike": "guard", "guard": "feint", "feint": "probe", "probe": "strike"}
RECENT_WEIGHT = 0.75
PATTERN_WEIGHT = 3.0
TRAIT_WEIGHTS = {
    "hot-tempered": {"strike": 3.0}, "proud": {"strike": 3.0},
    "cautious": {"guard": 2.0, "probe": 2.0}, "cunning": {"feint": 3.0},
}
BEAST_WEIGHTS = {"strike": 3.0, "feint": 0.5, "guard": 1.0, "probe": 0.5}
TENDENCY_WORDS = {"strike": "direct strikes", "feint": "feints and tricks", "guard": "a patient guard", "probe": "testing probes"}


def _base(traits, beast: bool) -> dict[str, float]:
    if beast:
        return dict(BEAST_WEIGHTS)
    weights = {i: 1.0 for i in INTENTS}
    for trait in traits:
        for intent, weight in TRAIT_WEIGHTS.get(trait, {}).items():
            weights[intent] = max(weights[intent], weight)
    return weights


def intent_weights(traits, player_history, beast: bool = False) -> dict[str, float]:
    weights = _base(traits, beast)
    history = [i for i in player_history if i in COUNTER]
    for intent in history[-3:]:
        weights[COUNTER[intent]] += RECENT_WEIGHT
    if len(history) >= 2:
        last = history[-1]
        follows = [history[k + 1] for k in range(len(history) - 1) if history[k] == last][-4:]
        for following in follows:
            weights[COUNTER[following]] += PATTERN_WEIGHT / len(follows)
    return weights


def choose_intent(rng, weights: dict[str, float]) -> str:
    roll = rng.random() * sum(weights[i] for i in INTENTS)
    for intent in INTENTS:
        roll -= weights[intent]
        if roll < 0:
            return intent
    return INTENTS[-1]


def tendency(traits, beast: bool = False) -> str:
    weights = _base(traits, beast)
    return TENDENCY_WORDS[max(INTENTS, key=lambda i: weights[i])]


def choose_output(traits, qi: float, own_harm: float, their_harm: float) -> str:
    if "hot-tempered" in traits and own_harm > their_harm + 20:
        return affordable("all-in", qi)
    return affordable("steady", qi)


def gives_up(rng, traits, occupation: str, harm: float, beast: bool = False) -> str | None:
    if condition_of(harm) != "badly hurt":
        return None
    if (occupation == "bandit" or beast) and rng.random() < 0.3:
        return "flee"
    if ("cautious" in traits or "kind" in traits) and rng.random() < 0.4:
        return "yield"
    return None
```
`systems/duel_sim.py`:
```python
"""Headless duels for balance testing (phase 2 spec §9.5). No database, no events."""

from systems.combat_core import BROKEN, MAX_HARM, QI_COST, Fighter, affordable, power, resolve
from systems.opponent import choose_intent, choose_output, intent_weights


def simulate(player: Fighter, npc: Fighter, strategy, rng, max_exchanges: int = 40) -> tuple[str, int]:
    harm = {"a": 0.0, "b": 0.0}
    qi = {"a": player.qi, "b": npc.qi}
    openings: set[str] = set()
    history: list[str] = []
    for n in range(1, max_exchanges + 1):
        mine = strategy(rng, history)
        theirs = choose_intent(rng, intent_weights(npc.traits, history, npc.beast))
        my_output = affordable("steady", qi["a"])
        their_output = choose_output(npc.traits, qi["b"], harm["b"], harm["a"])
        qi["a"] = max(0.0, qi["a"] - QI_COST[my_output])
        qi["b"] = max(0.0, qi["b"] - QI_COST[their_output])
        mine_power = power(player, mine, my_output, harm["a"], "a" in openings)
        their_power = power(npc, theirs, their_output, harm["b"], "b" in openings)
        result = resolve(mine, theirs, mine_power, their_power, rng)
        openings = set(result.openings)
        for side in result.recover:
            qi[side] += 2
        for blow in result.blows:
            harm[blow.target] = min(MAX_HARM, harm[blow.target] + blow.damage)
        history.append(mine)
        if harm["a"] >= BROKEN and harm["b"] >= BROKEN:
            return "draw", n
        if harm["b"] >= BROKEN:
            return "player", n
        if harm["a"] >= BROKEN:
            return "npc", n
    return "draw", max_exchanges
```

- [ ] **Step 4: Run tests** → PASS (7 passed), and the full suite passes. If a balance test fails, tune `DAMAGE_BASE`, `RECENT_WEIGHT` or `PATTERN_WEIGHT` and record a ruling. Never widen a target.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: opponent AI that reads habits and patterns, balance solver" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 4: Duels in the world

**Files:**
- Create: `systems/duel.py`
- Test: `tests/test_duel.py`

**Interfaces:**
- Consumes: Tasks 1–3; `load_body`, `save_body` (bodies); `martial_arts`, `teach`, `generate`, `create_technique`, `compatibility`, `usable`, `grade_mult`, `FORM_STATS`, `FORMS` (techniques); `REALMS`, `STAGES`, `stage_of`, `realm_index` (realms); `people_at`
- Produces:
  - Constants: `MODES = ("duel", "spar", "encounter", "test")`, `GENTLE_MODES = ("spar", "test")`, `SPAR_EXCHANGES = 3`, `TEST_EXCHANGES = 3`, `MAX_EXCHANGES = 30`
  - `Duel(duel_id, player, opponent, place, mode, exchange, harm, technique, opponent_technique, output, history, openings, stage, witnesses, purpose, revealed)`, with `Duel.from_event(event_id, event)`
  - NPC arts: `ensure_npc_arts(world, pid) -> list[Known]`, which sets `data["teacher"]` and `data["arts_ready"]`
  - Fighters: `best_art(world, pid) -> Known | None`, `fighter_for(world, pid, technique_id) -> Fighter`
  - Event builders:
    - `start_events(world, player, opponent, place, mode, purpose=None, opening=None)`
    - `exchange_events(world, duel, intent) -> list[Event]`, where `intent` is one of `INTENTS` or `"flee"`
    - `verdict_events(world, duel, choice)`, `yield_events(world, duel)`
  - State: `apply_record(duel, exchange_data)`, `active_duel(world, player_id) -> Duel | None`, `accepts(world, npc_id, player_id, mode) -> bool`, `refusal_events(player, npc, place, mode)`
  - Helpers: `npc_verdict(rng, opponent, player_silver) -> (verdict, amount, crippled)`, `fragment_of(world, technique_id, rng) -> dict`
  - Event kinds: `duel_started`, `exchange` (weight 0.2), `duel_ended`, and `refused_duel`. Their data is below.
  - The results `duel_ended` can carry: won, lost, fled, escaped, drawn, spar_won, spar_lost, spar_even, passed, failed.

```
duel_started  {mode, technique, technique_name, opponent_technique, opponent_technique_name, witnesses, purpose, opening}
exchange      {duel, n, player_intent, opponent_intent, player_output, opponent_output, player_output_choice,
               player_technique, player_technique_name, opponent_technique_name, blows:[{target, damage, wound}],
               openings, reveals, recover, tendency, qi_spent:{player, opponent}, deviation_added,
               fled, gave_up, fragment, stage, harm_after:{player, opponent}}
duel_ended    {duel, mode, result, reason, verdict, by, silver, crippled, loot, insight, life_and_death, fragment, purpose}
```

- [ ] **Step 1: Write the failing test** — `tests/test_duel.py`
```python
import pytest

import systems.duel as duel
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.combat_core import BROKEN, INTENTS
from systems.creation import CreationChoice
from systems.items import create_manual, manuals_of
from systems.purse import silver_of
from systems.techniques import create_technique, generate
from world.body import add_injury
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def npc(game, realm="mortal", traits=("curious", "honest"), occupation="tea seller", tag=""):
    data = {"occupation": occupation, "traits": list(traits), "realm": realm, "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Opponent {tag}", data, seed_path=f"test:{realm}:{occupation}:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def make_strong(game, realm=3, energy=20.0):
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years = realm, energy
    save_body(game.world, game.player.id, body)


def start(game, opponent, mode="duel"):
    events = duel.start_events(game.world, game.player.id, opponent, game.place.id, mode)
    [event_id] = commit(game.world, events)
    return duel.Duel.from_event(event_id, events[0])


def fight(game, d, intent="strike", limit=40):
    """Exchange until the duel ends or waits for a verdict; returns the last batch of events."""
    for _ in range(limit):
        events = duel.exchange_events(game.world, d, intent)
        commit(game.world, events)
        duel.apply_record(d, events[0].data)
        if len(events) > 1 or d.stage == "verdict":
            return events
    raise AssertionError("the fight never ended")


def test_npc_arts_are_seeded_once(game):
    swordsman = npc(game, occupation="wandering swordsman", tag="s")
    first = duel.ensure_npc_arts(game.world, swordsman)
    again = duel.ensure_npc_arts(game.world, swordsman)
    assert [a.technique.id for a in first] == [a.technique.id for a in again]
    assert first[0].form == "sword" and game.world.entity(swordsman).data["arts_ready"]


def test_fighter_reflects_body_and_art(game):
    art = duel.best_art(game.world, game.player.id)
    me = duel.fighter_for(game.world, game.player.id, art.technique.id)
    assert me.realm_mult == 1 and me.technique == art.name and me.form == art.form
    body = load_body(game.world, game.player.id)
    add_injury(body, "right arm", "cut", 2, game.world.time, "x")
    save_body(game.world, game.player.id, body)
    hurt = duel.fighter_for(game.world, game.player.id, art.technique.id)
    assert hurt.limb_injuries == (1 if art.form != "footwork" else 0)
    assert duel.fighter_for(game.world, game.player.id, None).form == "bare"


def test_exchange_is_decided_up_front_and_applied(game):
    d = start(game, npc(game, tag="a"))
    first = duel.exchange_events(game.world, d, "strike")
    assert first[0].data == duel.exchange_events(game.world, d, "strike")[0].data  # deterministic
    commit(game.world, first)
    data = first[0].data
    assert data["player_intent"] == "strike" and data["opponent_intent"] in INTENTS
    assert set(data["harm_after"]) == {"player", "opponent"}
    wounds_on_me = sum(1 for b in data["blows"] if b["target"] == "player" and b["wound"])
    assert len(load_body(game.world, game.player.id).injuries) == wounds_on_me


def test_beating_a_weaker_opponent_asks_for_a_verdict_and_robbing_takes_all(game):
    make_strong(game)
    victim = npc(game, tag="b")
    name, art = generate(rng_for(1, "m"), "martial", form="palm")
    item = create_manual(game.world, victim, create_technique(game.world, name, art), 0.7)
    before_mine, theirs = silver_of(game.world, game.player.id), silver_of(game.world, victim)
    d = start(game, victim)
    fight(game, d)
    assert d.stage == "verdict" and d.harm["opponent"] >= BROKEN
    [end] = duel.verdict_events(game.world, d, "rob")
    commit(game.world, [end])
    assert end.data["result"] == "won" and end.data["loot"] == [item]
    assert silver_of(game.world, game.player.id) == before_mine + theirs and silver_of(game.world, victim) == 0
    assert [m.item.id for m in manuals_of(game.world, game.player.id)] == [item]
    assert game.world.memories(victim, about=game.player.id)[-1].feeling == "humiliated"


def test_crippling_is_permanent_and_never_forgotten(game):
    make_strong(game)
    victim = npc(game, tag="c")
    d = start(game, victim)
    fight(game, d)
    [end] = duel.verdict_events(game.world, d, "cripple")
    commit(game.world, [end])
    assert any(i.permanent for i in load_body(game.world, victim).injuries)
    memory = game.world.memories(victim, about=game.player.id)[-1]
    assert memory.feeling == "hatred" and memory.indelible


def test_losing_to_a_bandit_costs_silver_but_never_life(game):
    bandit = npc(game, realm="first-rate", traits=("greedy", "cunning"), occupation="bandit", tag="d")
    before = silver_of(game.world, game.player.id)
    d = start(game, bandit)
    events = fight(game, d)
    end = events[-1]
    assert end.kind == "duel_ended" and end.data["result"] == "lost" and end.data["by"] == "opponent"
    assert end.data["verdict"] in ("rob", "cripple") and silver_of(game.world, game.player.id) <= before
    assert game.world.entity(game.player.id) is not None


def test_a_spar_is_short_and_gentle(game):
    friend = npc(game, tag="e")
    d = start(game, friend, mode="spar")
    events = fight(game, d)
    assert events[-1].data["result"] in ("spar_won", "spar_lost", "spar_even") and d.exchange <= 3
    for entry in game.world.chronicle_about(game.player.id, limit=10):
        for blow in entry.data.get("blows", []):
            assert blow["wound"] is None or blow["wound"][2] <= 2
    assert game.world.memories(friend, about=game.player.id)[-1].feeling == "sparred"


def test_fleeing(game, monkeypatch):
    d = start(game, npc(game, tag="f"))
    monkeypatch.setattr(duel, "flee_chance", lambda *a: 0.0)
    [failed] = duel.exchange_events(game.world, d, "flee")
    assert failed.data["fled"] is False and failed.data["blows"][0]["target"] == "player"
    monkeypatch.setattr(duel, "flee_chance", lambda *a: 1.0)
    escaped = duel.exchange_events(game.world, d, "flee")
    assert escaped[0].data["fled"] is True and escaped[-1].data["result"] == "fled"


def test_an_opponent_can_yield_and_a_win_upward_teaches(game, monkeypatch):
    elder = npc(game, realm="third-rate", tag="g")
    d = start(game, elder)
    monkeypatch.setattr(duel, "gives_up", lambda *a: "yield")
    events = duel.exchange_events(game.world, d, "guard")
    commit(game.world, events)
    duel.apply_record(d, events[0].data)
    assert events[0].data["gave_up"] == "yield" and d.stage == "verdict"
    [end] = duel.verdict_events(game.world, d, "spare")
    commit(game.world, [end])
    assert end.data["insight"] == 5.0 and end.data["life_and_death"]
    body = load_body(game.world, game.player.id)
    assert "life_and_death_insight" in body.flags and body.insight >= 5.0


def test_a_duel_in_progress_is_rebuilt_from_the_chronicle(game):
    d = start(game, npc(game, tag="h"))
    for intent in ("probe", "guard"):
        events = duel.exchange_events(game.world, d, intent)
        commit(game.world, events)
        duel.apply_record(d, events[0].data)
        if len(events) > 1:
            pytest.skip("the duel ended early for this seed")
    rebuilt = duel.active_duel(game.world, game.player.id)
    assert rebuilt is not None
    assert (rebuilt.exchange, rebuilt.harm, rebuilt.history, rebuilt.stage) == (d.exchange, d.harm, d.history, d.stage)
    commit(game.world, duel.yield_events(game.world, d))
    assert duel.active_duel(game.world, game.player.id) is None


def test_who_accepts_a_fight(game):
    proud = npc(game, traits=("proud", "loyal"), tag="i")
    assert duel.accepts(game.world, proud, game.player.id, "duel")
    assert duel.refusal_events(game.player.id, proud, game.place.id, "spar")[0].kind == "refused_duel"
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: systems.duel`)

- [ ] **Step 3: Implement** — `systems/duel.py`
```python
"""Duels in the world (phase 2 spec §9): fighters built from bodies, and the
events a fight is made of.

The arithmetic lives in combat_core and the opponent's mind in opponent.
Every exchange is decided here, stored whole in its event, and only applied
by the effect, so replays, the journal and the narrator all agree exactly.
"""

from dataclasses import dataclass, field

from systems.bodies import load_body, save_body
from systems.combat_core import (
    ALL_IN_DEVIATION, BROKEN, DAMAGE_BASE, FORM_STATS_EXTRA, INJURY_THRESHOLD, INTENTS, MAX_HARM, QI_COST,
    Fighter, affordable, flee_chance, limbs_for, power, resolve, wound,
)
from systems.items import manuals_of
from systems.opponent import choose_intent, choose_output, gives_up, intent_weights, tendency
from systems.purse import silver_of
from systems.realms import REALMS, STAGES, realm_index, stage_of
from systems.techniques import (
    FORM_STATS, FORMS, compatibility, create_technique, generate, grade_mult, martial_arts, teach, usable,
)
from systems.time import advance
from world.body import REGULAR, add_injury, unhealed
from world.events import Event, Witness, effect
from world.gen.materialize import people_at
from world.seed import rng_for

MODES = ("duel", "spar", "encounter", "test")
GENTLE_MODES = ("spar", "test")
SPAR_EXCHANGES = 3
TEST_EXCHANGES = 3
MAX_EXCHANGES = 30
GENTLE_SCALE = 0.5
FRAGMENT_CHANCE_PROBE = 0.3
FRAGMENT_CHANCE_SPAR = 0.5
MAX_FRAGMENTS = 12
FORM_BY_OCCUPATION = {
    "wandering swordsman": "sword", "hunter": "spear", "monk": "palm", "constable": "saber",
    "beggar": "staff", "blacksmith": "fist", "bandit": "saber",
}
TEACHER_CHANCE = {"wandering swordsman": 0.6, "monk": 0.5, "hunter": 0.2}
LEGS = ("left leg", "right leg")


@dataclass
class Duel:
    duel_id: int
    player: int
    opponent: int
    place: int
    mode: str
    exchange: int = 0
    harm: dict = field(default_factory=lambda: {"player": 0.0, "opponent": 0.0})
    technique: int | None = None
    opponent_technique: int | None = None
    output: str = "steady"
    history: list = field(default_factory=list)
    openings: list = field(default_factory=list)
    stage: str = "fighting"
    witnesses: list = field(default_factory=list)
    purpose: dict = field(default_factory=dict)
    revealed: str | None = None

    @classmethod
    def from_event(cls, event_id: int, event) -> "Duel":
        data = event.data
        player, opponent = event.actors
        return cls(
            event_id, player, opponent, event.place, data["mode"],
            technique=data["technique"], opponent_technique=data["opponent_technique"],
            openings=[data["opening"]] if data.get("opening") else [],
            witnesses=list(data["witnesses"]), purpose=dict(data.get("purpose") or {}),
        )


# --- who fights with what -----------------------------------------------------------

def ensure_npc_arts(world, person_id: int):
    """Every NPC knows at least one art; some are teachers. Seeded, created once."""
    person = world.entity(person_id)
    data = person.data
    if data.get("is_player") or data.get("beast") or data.get("arts_ready"):
        return martial_arts(world, person_id)
    key = person.seed_path or f"entity:{person_id}"
    rng = rng_for(world.world_seed, f"{key}/arts")
    realm = realm_index(data.get("realm", "mortal"))
    occupation = data.get("occupation", "")
    teacher = rng.random() < TEACHER_CHANCE.get(occupation, 0.0)
    with world.transaction():
        for i in range(rng.randint(1, 2) if teacher else 1):
            form = FORM_BY_OCCUPATION[occupation] if i == 0 and occupation in FORM_BY_OCCUPATION else rng.choice(FORMS)
            name, art = generate(rng, "martial", form=form, grade=max(1, min(6, realm + 1)))
            technique = create_technique(world, name, art)
            teach(world, person_id, technique, source="lineage", mastery=round(min(1.0, rng.uniform(0.2, 0.5) + 0.1 * realm), 3))
        world.update_data(person_id, arts_ready=True, teacher=teacher)
    return martial_arts(world, person_id)


def best_art(world, person_id: int):
    body = load_body(world, person_id)
    arts = [a for a in martial_arts(world, person_id) if usable(body, a.technique.data)]
    if not arts:
        return None
    return max(arts, key=lambda a: grade_mult(a.technique.data["grade"]) * (0.5 + a.mastery) * compatibility(body, a.technique.data))


def fighter_for(world, person_id: int, technique_id: int | None) -> Fighter:
    person = world.entity(person_id)
    body = load_body(world, person_id)
    beast = bool(person.data.get("beast"))
    art = None
    if not beast and technique_id is not None:
        art = next((a for a in martial_arts(world, person_id)
                    if a.technique.id == technique_id and usable(body, a.technique.data)), None)
    form = "claws" if beast else (art.form if art else "bare")
    stats = FORM_STATS.get(form) or FORM_STATS_EXTRA[form]
    stat = sum(body.physique[s] for s in stats) / len(stats)
    hurt = unhealed(body, world.time)
    limbs = limbs_for(form)
    return Fighter(
        name=person.name, realm_mult=REALMS[body.realm].multiplier, stage=STAGES.index(stage_of(body)),
        technique=art.name if art else None, form=form,
        grade_mult=grade_mult(art.technique.data["grade"]) if art else 1.0,
        mastery=art.mastery if art else 0.0,
        compat=compatibility(body, art.technique.data) if art else 1.0,
        body_fit=0.8 + 0.4 * (stat / 20),
        limb_injuries=sum(1 for i in hurt if i.location in limbs),
        leg_injuries=sum(1 for i in hurt if i.location in LEGS),
        agility=body.physique["agility"], qi=body.qi,
        traits=tuple(person.data.get("traits", ())), beast=beast,
        stance_favours=art.technique.data["stance"]["favours"] if art else None,
    )


def fragment_of(world, technique_id: int, rng) -> dict:
    technique = world.entity(technique_id)
    route = technique.data["route"]
    start = rng.randrange(max(1, len(route) - 1))
    return {"technique": technique.name, "form": technique.data["form"], "element": technique.data["element"],
            "segment": route[start:start + 2]}


# --- starting and refusing ----------------------------------------------------------

def accepts(world, npc_id: int, player_id: int, mode: str) -> bool:
    npc = world.entity(npc_id)
    traits = set(npc.data.get("traits", ()))
    rng = rng_for(world.world_seed, f"accept:{mode}:{npc_id}:{world.time}")
    if mode == "spar":
        return not (traits & {"cautious", "lazy"}) or rng.random() < 0.5
    if traits & {"proud", "hot-tempered"}:
        return True
    if realm_index(npc.data.get("realm", "mortal")) >= load_body(world, player_id).realm:
        return True
    return rng.random() < 0.5


def refusal_events(player: int, npc: int, place: int, mode: str) -> list[Event]:
    return [Event("refused_duel", (player, npc), place, {"mode": mode})]


def start_events(world, player: int, opponent: int, place: int, mode: str,
                 purpose: dict | None = None, opening: str | None = None) -> list[Event]:
    ensure_npc_arts(world, opponent)
    load_body(world, opponent)
    mine, theirs = best_art(world, player), best_art(world, opponent)
    witnesses = [p.id for p in people_at(world, place, exclude=player) if p.id != opponent]
    data = {
        "mode": mode, "technique": mine.technique.id if mine else None, "technique_name": mine.name if mine else None,
        "opponent_technique": theirs.technique.id if theirs else None,
        "opponent_technique_name": theirs.name if theirs else None,
        "witnesses": witnesses, "purpose": purpose or {}, "opening": opening,
    }
    return [Event("duel_started", (player, opponent), place, data)]


# --- one exchange --------------------------------------------------------------------

def _blow(target: str, damage: float, form: str, rng, gentle: bool) -> dict:
    hit = wound(form, damage, rng, spar=gentle)
    return {"target": target, "damage": round(damage, 2), "wound": list(hit) if hit else None}


def exchange_events(world, d: Duel, intent: str) -> list[Event]:
    n = d.exchange + 1
    rng = rng_for(world.world_seed, f"duel:{d.duel_id}:{n}")
    me = fighter_for(world, d.player, d.technique)
    them = fighter_for(world, d.opponent, d.opponent_technique)
    opponent = world.entity(d.opponent)
    gentle = d.mode in GENTLE_MODES
    scale = GENTLE_SCALE if gentle else 1.0
    data = {
        "duel": d.duel_id, "n": n, "player_intent": intent, "opponent_intent": None,
        "player_output": None, "opponent_output": None, "player_output_choice": d.output,
        "player_technique": d.technique, "player_technique_name": me.technique,
        "opponent_technique_name": them.technique, "blows": [], "openings": [], "reveals": [], "recover": [],
        "tendency": None, "qi_spent": {"player": 0, "opponent": 0}, "deviation_added": 0.0,
        "fled": None, "gave_up": None, "fragment": None, "stage": "fighting",
    }
    harm = dict(d.harm)
    if intent == "flee":
        data["fled"] = rng.random() < flee_chance(me, them, harm["player"])
        if not data["fled"]:
            chaser = power(them, "strike", "steady", harm["opponent"], False)
            runner = power(me, "guard", "steady", harm["player"], False)
            damage = DAMAGE_BASE * (chaser / max(runner, 1e-6)) ** 0.8 * rng.uniform(0.8, 1.2) * scale
            data["blows"].append(_blow("player", damage, them.form, rng, gentle))
    else:
        quitting = None if gentle else gives_up(rng, them.traits, opponent.data.get("occupation", ""), harm["opponent"], them.beast)
        if quitting:
            data["gave_up"] = quitting
        else:
            their_intent = choose_intent(rng, intent_weights(them.traits, d.history, them.beast))
            my_output = affordable(d.output, me.qi)
            their_output = choose_output(them.traits, them.qi, harm["opponent"], harm["player"])
            mine = power(me, intent, my_output, harm["player"], "player" in d.openings)
            theirs = power(them, their_intent, their_output, harm["opponent"], "opponent" in d.openings)
            result = resolve(intent, their_intent, mine, theirs, rng, scale)
            side = {"a": "player", "b": "opponent"}
            for blow in result.blows:
                form = them.form if blow.target == "a" else me.form
                data["blows"].append(_blow(side[blow.target], blow.damage, form, rng, gentle))
            data.update(
                opponent_intent=their_intent, player_output=my_output, opponent_output=their_output,
                openings=[side[s] for s in result.openings], reveals=[side[s] for s in result.reveals],
                recover=[side[s] for s in result.recover],
                qi_spent={"player": QI_COST[my_output], "opponent": QI_COST[their_output]},
                deviation_added=float(ALL_IN_DEVIATION) if my_output == "all-in" else 0.0,
            )
            if "player" in data["reveals"]:
                data["tendency"] = tendency(them.traits, them.beast)
                if d.opponent_technique is not None and rng.random() < FRAGMENT_CHANCE_PROBE:
                    data["fragment"] = fragment_of(world, d.opponent_technique, rng)
    for blow in data["blows"]:
        harm[blow["target"]] = min(MAX_HARM, harm[blow["target"]] + blow["damage"])
    data["harm_after"] = {side: round(value, 2) for side, value in harm.items()}
    ending = _ending(d, data, n)
    if ending == "verdict":
        data["stage"] = "verdict"
    events = [Event("exchange", (d.player, d.opponent), d.place, data, weight=0.2)]
    if isinstance(ending, tuple):
        events.append(_end_event(world, d, ending[0], ending[1], rng, data["harm_after"], n))
    return events


def _ending(d: Duel, data: dict, n: int):
    if data["fled"]:
        return ("fled", "fled")
    if data["gave_up"] == "flee":
        return ("escaped", "fled")
    mine, theirs = data["harm_after"]["player"], data["harm_after"]["opponent"]
    if d.mode == "spar":
        if any(b["damage"] >= INJURY_THRESHOLD for b in data["blows"]) or n >= SPAR_EXCHANGES:
            result = "spar_won" if theirs > mine else "spar_lost" if mine > theirs else "spar_even"
            return (result, "point" if n < SPAR_EXCHANGES else "limit")
        return None
    if d.mode == "test":
        if mine >= BROKEN:
            return ("failed", "broken")
        return ("passed", "limit") if n >= TEST_EXCHANGES else None
    if mine >= BROKEN:
        return ("lost", "broken")
    if theirs >= BROKEN or data["gave_up"] == "yield":
        return "verdict"
    return ("drawn", "exhausted") if n >= MAX_EXCHANGES else None


def apply_record(d: Duel, data: dict) -> None:
    """Advance the in-memory duel by one recorded exchange (also used to rebuild after a load)."""
    d.exchange = data["n"]
    d.harm = dict(data["harm_after"])
    d.openings = list(data["openings"])
    d.technique = data["player_technique"]
    d.output = data["player_output_choice"]
    d.stage = data["stage"]
    if data["player_intent"] in INTENTS:
        d.history.append(data["player_intent"])
    if data.get("tendency"):
        d.revealed = data["tendency"]


def active_duel(world, player_id: int) -> Duel | None:
    entries = world.chronicle_about(player_id, limit=80)  # newest first
    for entry in entries:
        if entry.kind == "duel_ended":
            return None
        if entry.kind == "duel_started":
            d = Duel.from_event(entry.id, entry)
            for later in reversed(entries):
                if later.kind == "exchange" and later.data.get("duel") == entry.id:
                    apply_record(d, later.data)
            return d
    return None


# --- endings --------------------------------------------------------------------------

def _cripple(rng) -> list:
    options = [["right arm", "fracture"], ["left arm", "fracture"], ["right leg", "fracture"],
               ["left leg", "fracture"], [rng.choice(REGULAR), "meridian"]]
    return rng.choice(options)


def npc_verdict(rng, opponent, player_silver: int) -> tuple[str, int, list | None]:
    if opponent.data.get("beast"):
        return "spare", 0, None  # a beast only wants you gone
    traits = set(opponent.data.get("traits", ()))
    ruthless = opponent.data.get("occupation") == "bandit" or {"cunning", "greedy"} <= traits
    greedy = ruthless or "greedy" in traits
    amount = int(player_silver * rng.uniform(0.3, 1.0)) if greedy else 0
    crippled = _cripple(rng) if ruthless and rng.random() < 0.25 else None
    return ("cripple" if crippled else "rob" if amount else "spare"), amount, crippled


def _end_event(world, d: Duel, result: str, reason: str, rng, harm: dict, exchanges: int,
               verdict: str | None = None) -> Event:
    opponent = world.entity(d.opponent)
    body = load_body(world, d.player)
    gap = realm_index(opponent.data.get("realm", "mortal")) - body.realm
    data = {
        "duel": d.duel_id, "mode": d.mode, "result": result, "reason": reason, "verdict": verdict, "by": None,
        "silver": 0, "crippled": None, "loot": [], "insight": 0.0, "life_and_death": False,
        "fragment": None, "purpose": d.purpose,
    }
    witnesses = []
    if result == "lost":
        chosen, amount, crippled = npc_verdict(rng, opponent, silver_of(world, d.player))
        data.update(verdict=chosen, by="opponent", silver=amount, crippled=crippled,
                    insight=5.0 * gap if gap > 0 else 0.0)
        feeling = "respect" if exchanges >= 4 or gap <= 0 else "contempt"
        witnesses.append(Witness(d.opponent, feeling, 0.5))
    elif result == "won":
        data["by"] = "player"
        if verdict == "rob":
            data["silver"] = silver_of(world, d.opponent)
            data["loot"] = [m.item.id for m in manuals_of(world, d.opponent)]
        if verdict == "cripple":
            data["crippled"] = _cripple(rng)
        data["insight"] = 5.0 * gap if gap > 0 else 1.0
        data["life_and_death"] = harm["player"] >= 60 or gap > 0
        feeling, weight, lasting = {
            "spare": ("grateful" if gap < 0 else "humiliated", 0.6, False),
            "rob": ("humiliated", 0.8, False),
            "cripple": ("hatred", 1.0, True),
        }[verdict]
        witnesses.append(Witness(d.opponent, feeling, weight, lasting))
    elif result.startswith("spar_"):
        data["insight"] = 3.0
        if d.opponent_technique is not None and rng.random() < FRAGMENT_CHANCE_SPAR:
            data["fragment"] = fragment_of(world, d.opponent_technique, rng)
        witnesses.append(Witness(d.opponent, "sparred", 0.3))
    elif result in ("passed", "failed"):
        witnesses.append(Witness(d.opponent, "respect" if result == "passed" else "contempt", 0.3))
    elif result == "fled":
        witnesses.append(Witness(d.opponent, "contempt", 0.4))
    witnesses += [Witness(w, "witnessed_duel", 0.2) for w in d.witnesses]
    return Event("duel_ended", (d.player, d.opponent), d.place, data, witnesses=tuple(witnesses))


def verdict_events(world, d: Duel, choice: str) -> list[Event]:
    if d.stage != "verdict" or choice not in ("spare", "rob", "cripple"):
        return []
    rng = rng_for(world.world_seed, f"duel:{d.duel_id}:verdict")
    reason = "broken" if d.harm["opponent"] >= BROKEN else "yielded"
    return [_end_event(world, d, "won", reason, rng, d.harm, d.exchange, verdict=choice)]


def yield_events(world, d: Duel) -> list[Event]:
    rng = rng_for(world.world_seed, f"duel:{d.duel_id}:yield")
    result = {"spar": "spar_lost", "test": "failed"}.get(d.mode, "lost")
    return [_end_event(world, d, result, "yielded", rng, d.harm, d.exchange)]


# --- effects -----------------------------------------------------------------------------

def _add_fragment(world, player: int, fragment: dict) -> None:
    fragments = list(world.entity(player).data.get("fragments", [])) + [fragment]
    world.update_data(player, fragments=fragments[-MAX_FRAGMENTS:])


@effect("exchange")
def _exchange(world, event: Event) -> None:
    data = event.data
    ids = dict(zip(("player", "opponent"), event.actors))
    people = {side: world.entity(pid) for side, pid in ids.items()}
    arts = {"player": data["player_technique_name"], "opponent": data["opponent_technique_name"]}
    bodies = {side: load_body(world, pid) for side, pid in ids.items()}
    for blow in data["blows"]:
        if blow["wound"]:
            location, kind, severity = blow["wound"]
            hitter = "opponent" if blow["target"] == "player" else "player"
            weapon = "claws" if people[hitter].data.get("beast") else (arts[hitter] or "bare hands")
            add_injury(bodies[blow["target"]], location, kind, severity, world.time, f"{people[hitter].name}'s {weapon}")
    for side, body in bodies.items():
        body.qi = max(0.0, body.qi - data["qi_spent"][side]) + (2.0 if side in data["recover"] else 0.0)
    bodies["player"].deviation = min(100.0, bodies["player"].deviation + data["deviation_added"])
    for side, body in bodies.items():
        save_body(world, ids[side], body)
    if data["fragment"]:
        _add_fragment(world, ids["player"], data["fragment"])


@effect("duel_ended")
def _ended(world, event: Event) -> None:
    data = event.data
    player, opponent = event.actors
    if data["silver"]:
        payer, payee = (player, opponent) if data["by"] == "opponent" else (opponent, player)
        amount = min(data["silver"], silver_of(world, payer))
        world.update_data(payer, silver=silver_of(world, payer) - amount)
        world.update_data(payee, silver=silver_of(world, payee) + amount)
    if data["crippled"]:
        victim, culprit = (player, opponent) if data["by"] == "opponent" else (opponent, player)
        body = load_body(world, victim)
        location, kind = data["crippled"]
        add_injury(body, location, kind, 5, world.time, f"being crippled by {world.entity(culprit).name}", permanent=True)
        save_body(world, victim, body)
    for item in data["loot"]:
        world.unrelate(opponent, "owns", item)
        world.relate(player, item, "owns")
    if data["insight"] or data["life_and_death"]:
        body = load_body(world, player)
        body.insight += data["insight"]
        if data["life_and_death"] and "life_and_death_insight" not in body.flags:
            body.flags.append("life_and_death_insight")
        save_body(world, player, body)
    if data["fragment"]:
        _add_fragment(world, player, data["fragment"])
    advance(world, 1)
```

- [ ] **Step 4: Run tests** → `tests/test_duel.py` PASS (11 passed, or 10 plus 1 skip if the rebuild test's seed ends the duel early), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: duels in the world - fighters, exchanges, verdicts, rebuild" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 5: Narrating duels

**Files:**
- Create: `narrate/outcomes.py`, `narrate/combat_text.py`, `narrate/grammar/combat.toml`, `.patches/2b_task5.py`
- Modify via the patch script: `narrate/brief.py` (use the registry), `narrate/procedural.py` (honour `details["grammar_key"]`), `engine/journal.py` (use registered summaries)
- Test: `tests/test_combat_text.py`

**Interfaces:**
- Consumes: the event data shapes from Task 4
- Produces:
  - In `narrate/outcomes.py`:
    - Registries: `OUTCOME_BUILDERS`, `BODY_FACT_KINDS`, `SUMMARIES`
    - Decorators: `outcome(kind, body_facts=True)` and `summary(kind)`
    - Helper: `cap(text)`
    - Feature modules register themselves on import. `outcomes.py` imports them at the bottom, and each later task appends one import line.
  - A registered builder returns `(outcome_lines, details)`. For kinds registered with `body_facts=True`, brief facts become the player's first 3 body facts followed by the relationship facts.
  - `details["grammar_key"]` picks the grammar table (for example `duel_ended.won`) when it exists.

- [ ] **Step 1: Write the failing test** — `tests/test_combat_text.py`
```python
import pytest

from engine.game import Game
from engine.journal import summarize
from narrate.brief import MAX_PROMPT, event_brief
from narrate.procedural import ProceduralNarrator
from systems.creation import CreationChoice
from world.events import Event


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def opponent(game, beast=False):
    data = {"occupation": "grey wolf" if beast else "bandit", "traits": ["greedy"], "realm": "mortal",
            "beast": beast, "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", "a grey wolf" if beast else "Opp Ma", data)
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def exchange(game, opp, **changes):
    data = {
        "duel": 1, "n": 1, "player_intent": "strike", "opponent_intent": "guard", "player_output": "steady",
        "opponent_output": "steady", "player_output_choice": "steady", "player_technique": None,
        "player_technique_name": "Pale Crane Palm", "opponent_technique_name": "Iron Tiger Fist",
        "blows": [{"target": "opponent", "damage": 20.0, "wound": ["left arm", "cut", 2]},
                  {"target": "player", "damage": 10.0, "wound": None}],
        "openings": [], "reveals": [], "recover": [], "tendency": None, "qi_spent": {"player": 3, "opponent": 3},
        "deviation_added": 0.0, "fled": None, "gave_up": None, "fragment": None, "stage": "fighting",
        "harm_after": {"player": 10.0, "opponent": 20.0},
    }
    data.update(changes)
    return Event("exchange", (game.player.id, opp), game.place.id, data)


def ended(game, opp, **changes):
    data = {"duel": 1, "mode": "duel", "result": "won", "reason": "broken", "verdict": "rob", "by": "player",
            "silver": 12, "crippled": None, "loot": [99], "insight": 1.0, "life_and_death": False,
            "fragment": None, "purpose": {}}
    data.update(changes)
    return Event("duel_ended", (game.player.id, opp), game.place.id, data)


def test_an_exchange_is_told_plainly(game):
    brief = event_brief(game.world, 1, exchange(game, opponent(game)))
    assert brief.outcome == (
        "You strike; Opp Ma guards.",
        "Your Pale Crane Palm lands on their left arm.",
        "Opp Ma's Iron Tiger Fist catches you.",
        "You are fresh; Opp Ma is bruised.",
    )
    assert len(brief.to_prompt()) <= MAX_PROMPT and brief.other.name == "Opp Ma"


def test_fleeing_yielding_and_beasts(game):
    opp = opponent(game)
    assert event_brief(game.world, 2, exchange(game, opp, fled=True, blows=[])).outcome[0] == "You break away and escape."
    assert event_brief(game.world, 3, exchange(game, opp, gave_up="yield", blows=[])).outcome[0] == "Opp Ma lowers their guard and yields."
    wolf = opponent(game, beast=True)
    lines = event_brief(game.world, 4, exchange(game, wolf, opponent_technique_name=None)).outcome
    assert lines[2] == "A grey wolf's claws catch you."


def test_endings_and_their_grammar(game):
    opp = opponent(game)
    won = event_brief(game.world, 5, ended(game, opp))
    assert won.outcome[:2] == ("You have beaten Opp Ma.", "You take 12 silver and 1 manual.")
    assert won.details["grammar_key"] == "duel_ended.won"
    assert ProceduralNarrator().narrate(won)[0][1] == "gold"
    lost = event_brief(game.world, 6, ended(game, opp, result="lost", by="opponent", verdict="cripple",
                                           silver=0, loot=[], crippled=["Liver", "meridian"]))
    assert "They cripple your Liver meridian for good." in lost.outcome
    assert lost.details["grammar_key"] == "duel_ended.lost"


def test_duel_journal_lines(game):
    opp = opponent(game)
    game.world.append_chronicle("duel_ended", (game.player.id, opp), game.place.id, ended(game, opp).data, 1.0)
    assert summarize(game.world, game.world.chronicle_about(game.player.id, limit=1)[0]).endswith("Beat Opp Ma.")
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: narrate.outcomes`, or outcome is empty)

- [ ] **Step 3: Implement**

`narrate/outcomes.py`:
```python
"""Registries that let each feature narrate its own events (phase 2b).

OUTCOME_BUILDERS[kind](world, event) -> (outcome lines, details)
BODY_FACT_KINDS: kinds whose brief facts lead with the player's body
SUMMARIES[kind](world, entry, names, place, other) -> one journal line
"""

from collections.abc import Callable

OUTCOME_BUILDERS: dict[str, Callable] = {}
BODY_FACT_KINDS: set[str] = set()
SUMMARIES: dict[str, Callable] = {}


def outcome(kind: str, body_facts: bool = True):
    def register(fn: Callable) -> Callable:
        OUTCOME_BUILDERS[kind] = fn
        if body_facts:
            BODY_FACT_KINDS.add(kind)
        return fn
    return register


def summary(kind: str):
    def register(fn: Callable) -> Callable:
        SUMMARIES[kind] = fn
        return fn
    return register


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


# Feature modules register on import. Each later task appends its module here.
import narrate.combat_text  # noqa: E402,F401
```
`narrate/combat_text.py`:
```python
"""What the player is told about duels: only facts from the event data."""

from narrate.outcomes import cap, outcome, summary
from systems.combat_core import condition_of

YOU = {"strike": "strike", "feint": "feint", "guard": "guard", "probe": "probe for an opening"}
THEM = {"strike": "strikes", "feint": "feints", "guard": "guards", "probe": "probes for an opening"}
MODE_WORDS = {"duel": "a duel", "spar": "a friendly spar", "encounter": "a fight", "test": "a test of skill"}
GROUP = {"won": "won", "spar_won": "won", "passed": "won", "lost": "lost", "spar_lost": "lost", "failed": "lost"}


def _name(world, event) -> str:
    return world.entity(event.actors[1]).name


def _is_beast(world, event) -> bool:
    return bool(world.entity(event.actors[1]).data.get("beast"))


def _place_of(wound) -> str:
    return f"{wound[0]} meridian" if wound[1] == "meridian" else wound[0]


@outcome("duel_started")
def _started(world, event):
    d, name = event.data, _name(world, event)
    lines = [f"You face {name} in {MODE_WORDS[d['mode']]}."]
    lines.append(f"You will fight with the {d['technique_name']}." if d["technique_name"] else "You will fight bare-handed.")
    if d["opponent_technique_name"]:
        lines.append(f"{cap(name)} settles into the stance of the {d['opponent_technique_name']}.")
    return lines, {"mode": MODE_WORDS[d["mode"]]}


@outcome("exchange")
def _exchange(world, event):
    d, name = event.data, _name(world, event)
    lines = []
    if d["fled"] is True:
        lines.append("You break away and escape.")
    elif d["fled"] is False:
        lines.append(f"You try to flee, but {name} cuts you off.")
    elif d["gave_up"] == "yield":
        lines.append(f"{cap(name)} lowers their guard and yields.")
    elif d["gave_up"] == "flee":
        lines.append(f"{cap(name)} turns and flees.")
    else:
        lines.append(f"You {YOU[d['player_intent']]}; {name} {THEM[d['opponent_intent']]}.")
    beast = _is_beast(world, event)
    for blow in d["blows"][:2]:
        wound = blow["wound"]
        if blow["target"] == "opponent":
            art = d["player_technique_name"] or "bare hands"
            lines.append(f"Your {art} lands{' on their ' + _place_of(wound) if wound else ''}.")
        else:
            weapon = "claws" if beast else (d["opponent_technique_name"] or "blow")
            verb = "catch" if weapon == "claws" else "catches"
            lines.append(f"{cap(name)}'s {weapon} {verb} {'your ' + _place_of(wound) if wound else 'you'}.")
    mine, theirs = condition_of(d["harm_after"]["player"]), condition_of(d["harm_after"]["opponent"])
    lines.append(f"You are {mine}; {name} is {theirs}.")
    if "player" in d["reveals"] and d["tendency"]:
        lines.append(f"You read their style: they favour {d['tendency']}.")
    if d["fragment"]:
        lines.append(f"You glimpse something of the {d['fragment']['technique']}.")
    return lines, {"you": mine, "them": theirs}


@outcome("duel_ended")
def _ended(world, event):
    d, name = event.data, _name(world, event)
    result = d["result"]
    lines = {
        "won": [f"You have beaten {name}."], "lost": [f"{cap(name)} has beaten you."],
        "fled": ["You got away."], "escaped": [f"{cap(name)} got away."],
        "drawn": ["Neither of you can go on, and you part ways."],
        "spar_won": [f"You win the spar against {name}."], "spar_lost": [f"{cap(name)} wins the spar."],
        "spar_even": ["The spar ends even."], "passed": [f"You pass {name}'s test."],
        "failed": [f"You fail {name}'s test."],
    }[result]
    if d["by"] == "player":
        if d["verdict"] == "spare":
            lines.append("You let them go.")
        if d["silver"] or d["loot"]:
            loot = f" and {len(d['loot'])} manual{'s' if len(d['loot']) != 1 else ''}" if d["loot"] else ""
            lines.append(f"You take {d['silver']} silver{loot}.")
        if d["crippled"]:
            lines.append(f"You cripple {name}'s {_place_of(d['crippled'])} for good.")
    elif d["by"] == "opponent":
        if d["verdict"] == "spare":
            lines.append("They let you go.")
        if d["silver"]:
            lines.append(f"They take {d['silver']} silver from you.")
        if d["crippled"]:
            lines.append(f"They cripple your {_place_of(d['crippled'])} for good.")
    if d["life_and_death"]:
        lines.append("You have faced death and understood something about the martial way.")
    elif d["insight"]:
        lines.append("The fight taught you something.")
    if d["fragment"]:
        lines.append(f"You glimpsed a piece of the {d['fragment']['technique']}.")
    return lines, {"result": result, "grammar_key": f"duel_ended.{GROUP.get(result, 'even')}"}


@outcome("refused_duel", body_facts=False)
def _refused(world, event):
    what = "to spar" if event.data["mode"] == "spar" else "your challenge"
    return [f"{cap(_name(world, event))} refuses {what}."], {}


RESULT_WORDS = {
    "won": "Beat {other}.", "lost": "Was beaten by {other}.", "fled": "Fled from {other}.",
    "escaped": "{other} fled.", "drawn": "Fought {other} to exhaustion.",
    "spar_won": "Won a spar with {other}.", "spar_lost": "Lost a spar with {other}.",
    "spar_even": "Sparred evenly with {other}.", "passed": "Passed {other}'s test.", "failed": "Failed {other}'s test.",
}


@summary("duel_started")
def _started_line(world, entry, names, place, other):
    return f"Faced {other} in {MODE_WORDS[entry.data['mode']]}."


@summary("exchange")
def _exchange_line(world, entry, names, place, other):
    return f"Traded blows with {other}."


@summary("duel_ended")
def _ended_line(world, entry, names, place, other):
    return cap(RESULT_WORDS[entry.data["result"]].format(other=other))


@summary("refused_duel")
def _refused_line(world, entry, names, place, other):
    return f"{cap(other)} refused to fight."
```
`narrate/grammar/combat.toml`:
```toml
[symbols]
clash = ["Steel rings on steel.", "Dust kicks up around your feet.", "Qi snaps through the air between you.", "Someone in the crowd gasps.", "A sleeve tears."]
footing = ["You shift your weight.", "They circle to your left.", "Neither of you blinks.", "Your breath comes hard.", "Sweat runs into your eyes."]
tension = ["The crowd draws back.", "The air goes still.", "Somewhere a dog stops barking.", "A merchant drags his stall out of the way.", "Your pulse slows as you settle."]
victory = ["The fight is yours.", "It is over, and you are still standing.", "Silence falls; you have won.", "You lower your hands, victorious."]
defeat = ["The ground rushes up to meet you.", "Your knees give way.", "You taste dirt and defeat.", "The world narrows to pain."]
parting = ["The fight ends without a victor.", "Both of you step back, breathing hard.", "It ends as suddenly as it began.", "Neither of you can claim the day."]
refusal = ["waves the idea away.", "shakes their head.", "laughs and declines.", "will not be drawn."]

[duel_started]
colour = "gold"
lines = [
  "You and {npc} square off. #tension#",
  "{npc} steps into the open to face you. #tension#",
]

[exchange]
colour = "default"
lines = ["#clash# #footing#", "#footing# #clash#"]

["duel_ended.won"]
colour = "gold"
lines = ["#victory# {npc} will remember this.", "#victory#"]

["duel_ended.lost"]
colour = "default"
lines = ["#defeat# {npc} stands over you.", "#defeat#"]

["duel_ended.even"]
colour = "default"
lines = ["#parting#", "#parting# {npc} watches you warily."]

[refused_duel]
colour = "npc"
lines = ["{npc} #refusal#", "{npc} considers it, then #refusal#"]
```
`.patches/2b_task5.py`:
```python
import pathlib


def patch(f, pairs):
    p = pathlib.Path(f)
    t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (f, a[:70])
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8", newline="\n")


patch("narrate/brief.py", [
    ("from systems.bodies import load_body\n",
     "from narrate.outcomes import BODY_FACT_KINDS, OUTCOME_BUILDERS\nfrom systems.bodies import load_body\n"),
    ("""    if event.kind in BODY_KINDS:
        outcome, extra = _body_outcome(event)
        details.update(extra)
        facts = player_facts(world, player.id)
""", """    if event.kind in BODY_KINDS:
        outcome, extra = _body_outcome(event)
        details.update(extra)
        facts = player_facts(world, player.id)
    if event.kind in OUTCOME_BUILDERS:
        more, extra = OUTCOME_BUILDERS[event.kind](world, event)
        outcome = list(outcome) + list(more)
        details.update(extra)
        if event.kind in BODY_FACT_KINDS:
            facts = player_facts(world, player.id)[:3] + facts
"""),
])
patch("narrate/procedural.py", [
    ("""    def _key(self, brief: Brief) -> str:
        if brief.kind == "scene":""",
     """    def _key(self, brief: Brief) -> str:
        wanted = brief.details.get("grammar_key")
        if wanted and wanted in self.grammar.tables:
            return wanted
        if brief.kind == "scene":"""),
])
patch("engine/journal.py", [
    ("from systems.time import days_word, format_date\n",
     "from narrate.outcomes import SUMMARIES\nfrom systems.time import days_word, format_date\n"),
    ("    data = entry.data\n    match entry.kind:",
     "    data = entry.data\n    if entry.kind in SUMMARIES:\n        return f\"{format_date(entry.time)} - {SUMMARIES[entry.kind](world, entry, names, place, other)}\"\n    match entry.kind:"),
])
print("task 5 patched")
```

- [ ] **Step 4: Run** `python .patches/2b_task5.py`, then the tests → `tests/test_combat_text.py` PASS (4 passed), and the full suite passes, including the grammar-variety lint on the new tables.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: narration registry and duel narration" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 6: Fighting in the engine

**Files:**
- Create: `engine/actions.py`, `engine/hooks.py`, `engine/fight.py`, `assets/art/beast.art`, `.patches/2b_task6.py`
- Rewrite: `engine/game.py`, `engine/commands.py`
- Modify via the patch script: `render/art.py` (the `duel` art request and harm bar)
- Test: `tests/test_fight_flow.py`

**Interfaces:**
- Consumes: Tasks 4–5
- Produces:
  - `engine/actions.py` holds `Action`, `Choice` and `Turn`. `engine.game` re-exports them, so existing imports keep working.
  - `GameHooks` in `engine/hooks.py` provides these hooks, all no-ops by default:
    - `_restore()`, `_gate(action)`
    - `_special_choices()`, `_special_art()`, `_special_status()`
    - `_conversation_extras(npc)`, `_practise_extras(body)`, `_submenu_options()`
    - `_after_arrival()`, `_after_look()`, `_after_duel(data)`
    - Mixins override them and call `super()`.
  - `class Game(FightMixin, GameHooks)`. Later tasks add their mixin to the front of this class line.
  - Game state: `Game.combat` (a `Duel` or `None`), `Game.encounter`, `Game.challenger`, and `Game._last_ids` (the event ids from the last `_commit`).
  - New verbs:
    - In conversation: `spar`, `challenge`
    - In a fight: `intent` (with `strike`/`feint`/`guard`/`probe`), `flee`, `yield_duel`, `use_menu`, `use` (a technique id or `"bare"`), `qi_output`, `verdict` (`spare`/`rob`/`cripple`)
  - `FightMixin._start_duel(opponent, mode, purpose=None, opening=None) -> list[Line]`, used by roads (Task 7) and dealings (Task 8)
  - Parser: `GLOBAL` maps words to whole `Action`s, including `strike`, `feint`, `guard`, `probe`, `flee`, `run`, `yield`, `surrender`, `spare`, `rob`, `cripple`, `spar` and `challenge`. The new prefix `use` searches the fight's technique choices.
  - Art request: `{"type": "duel", "parts": portrait|None, "beast": bool, "harm": float, "condition": str}`. It renders the portrait (or the beast art) with a harm bar on the bottom row.

- [ ] **Step 1: Write the failing test** — `tests/test_fight_flow.py`
```python
import pytest

from app import App
from config import Config
from debug.replay import replay
from engine.commands import parse
from engine.game import Action, Game
from render.art import render_request
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def rival(game, traits=("proud", "loyal")):
    data = {"occupation": "wandering swordsman", "traits": list(traits), "realm": "mortal",
            "portrait": {"hair": 1, "face": 1, "robe": 1}}
    pid = game.world.add_entity("person", "Rival Kang", data, seed_path="test:rival")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def make_strong(game):
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years = 3, 20.0
    save_body(game.world, game.player.id, body)


def verbs(choices):
    return [c.action.verb for c in choices]


def challenge(game, npc):
    game.perform(Action("talk", npc))
    return game.perform(Action("challenge", npc))


def test_conversation_offers_a_challenge_and_later_a_spar(game):
    npc = rival(game)
    first = game.perform(Action("talk", npc))
    assert "challenge" in verbs(first.choices) and "spar" not in verbs(first.choices)
    game.perform(Action("farewell"))
    assert "spar" in verbs(game.perform(Action("talk", npc)).choices)


def test_a_challenge_starts_a_fight_with_its_own_screen(game):
    turn = challenge(game, rival(game))
    assert game.combat is not None and game.focus is None
    assert verbs(turn.choices) == ["intent"] * 4 + ["use_menu", "qi_output", "yield_duel", "flee"]
    assert turn.art["type"] == "duel" and "vs Rival Kang" in turn.status


def test_other_actions_are_refused_mid_fight(game):
    challenge(game, rival(game))
    time = game.world.time
    turn = game.perform(Action("meditate", 7))
    assert turn.lines[-1] == ("You are fighting Rival Kang. Finish the fight first.", "system")
    assert game.world.time == time and game.combat is not None
    assert game.perform(Action("verdict", "rob")).lines[-1][1] == "system"


def test_fighting_to_a_verdict_and_sparing(game):
    make_strong(game)
    challenge(game, rival(game, traits=("proud", "honest")))
    for _ in range(40):
        turn = game.perform(Action("intent", "strike"))
        if game.combat is None or game.combat.stage == "verdict":
            break
    assert game.combat.stage == "verdict"
    assert [c.action for c in turn.choices] == [Action("verdict", "spare"), Action("verdict", "rob"), Action("verdict", "cripple")]
    turn = game.perform(Action("verdict", "spare"))
    assert game.combat is None and any("You have beaten Rival Kang." == t for t, _ in turn.lines)


def test_technique_and_qi_output(game):
    challenge(game, rival(game))
    assert verbs(game.perform(Action("use_menu")).choices)[-1] == "back"
    game.perform(Action("use", "bare"))
    assert game.combat.technique is None
    game.perform(Action("qi_output"))
    assert game.combat.output == "full"


def test_yielding_ends_the_fight(game):
    challenge(game, rival(game))
    game.perform(Action("yield_duel"))
    assert game.combat is None


def test_a_fight_resumes_after_reload(tmp_path):
    path = tmp_path / "g.world"
    game = Game.new(path, "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    challenge(game, rival(game))
    game.perform(Action("intent", "guard"))
    if game.combat is None:
        pytest.skip("this seed ended the fight in one exchange")
    harm = dict(game.combat.harm)
    game.close()
    again = Game.load(path)
    assert again.combat is not None and again.combat.harm == harm
    assert again.perform(Action("intent", "probe")).lines
    again.close()


def test_duel_art_is_exact_size():
    art = render_request({"type": "duel", "parts": {"hair": 0, "face": 0, "robe": 0}, "beast": False,
                          "harm": 50.0, "condition": "hurt"}, 40, 18)
    assert len(art) == 18 and all(len(r) == 40 for r in art)
    assert any(cell and cell[0] == "#" for cell in art[-1])
    tiny = render_request({"type": "duel", "parts": None, "beast": True, "harm": 0.0, "condition": "fresh"}, 5, 1)
    assert len(tiny) == 1 and len(tiny[0]) == 5


def test_fight_words():
    for word, action in [("strike", Action("intent", "strike")), ("FLEE", Action("flee")),
                         ("yield", Action("yield_duel")), ("rob", Action("verdict", "rob")),
                         ("challenge", Action("challenge")), ("look", Action("look"))]:
        assert parse(word, []) == action


def test_a_fight_through_the_app_replays_exactly(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    target = next(c for c in app.choices + app.extra if c.action.verb == "talk")
    app.submit("talk " + target.label.split(" (")[0].removeprefix("Talk to "))
    app.submit("challenge")
    for word in ("strike", "guard", "probe", "strike", "feint", "yield"):
        app.submit(word)
    path = app.session.path
    app.shutdown()
    assert replay(path, tmp_path / "r").mismatches == []
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: engine.hooks` / no `challenge` verb)

- [ ] **Step 3: Implement**

`engine/actions.py`:
```python
"""What the player can do (Action), how it is offered (Choice), and what comes back (Turn)."""

from dataclasses import dataclass, field

from narrate.base import Line


@dataclass(frozen=True)
class Action:
    verb: str
    target: object = None


@dataclass(frozen=True)
class Choice:
    label: str
    action: Action


@dataclass
class Turn:
    lines: list[Line]
    choices: list[Choice]
    art: dict
    status: str
    extra: list[Choice] = field(default_factory=list)  # valid now but folded off-screen

    @property
    def all_choices(self) -> list[Choice]:
        return self.choices + self.extra
```
`engine/hooks.py`:
```python
"""Extension points for feature mixins (phase 2b).

Each mixin overrides what it needs and calls super(), so several features can
add to the same hook: Game(FeatureMixins..., GameHooks).
"""


class GameHooks:
    def _restore(self) -> None:
        """Rebuild in-progress state (a fight, an encounter) after a load."""

    def _gate(self, action):
        """Return a Turn to refuse an action in the current state, or None to allow it."""
        return None

    def _special_choices(self):
        """(shown, extra) that replace the normal menus, or None."""
        return None

    def _special_art(self):
        return None

    def _special_status(self):
        return None

    def _conversation_extras(self, npc) -> list:
        return []

    def _practise_extras(self, body) -> list:
        return []

    def _submenu_options(self) -> dict:
        """name -> (options, back action) for feature submenus."""
        return {}

    def _after_arrival(self) -> list:
        return []

    def _after_look(self) -> list:
        return []

    def _after_duel(self, data: dict) -> list:
        return []
```
`engine/fight.py`:
```python
"""Fights in the engine (phase 2 spec §9): starting, exchanging, verdicts, and what the screen shows."""

import systems.duel as duel
import systems.talk as talk
from engine.actions import Action, Choice
from systems.combat_core import INTENTS, QI_OUTPUTS, condition_of
from systems.realms import realm_title
from systems.techniques import martial_arts, usable
from world.gen.materialize import people_at

FIGHT_VERBS = frozenset({
    "intent", "use_menu", "use", "qi_output", "yield_duel", "flee", "verdict",
    "help", "journal", "unknown", "ambiguous", "back",
})
INTENT_LABELS = {"strike": "Strike", "feint": "Feint", "guard": "Guard", "probe": "Probe for an opening"}
NOT_FIGHTING = "You are not fighting anyone."
DECIDE = "Decide their fate first."


class FightMixin:
    # --- state and gating ----------------------------------------------------------
    def _restore(self) -> None:
        super()._restore()
        self.combat = duel.active_duel(self.world, self.player.id)

    def _gate(self, action):
        if self.combat is not None and action.verb not in FIGHT_VERBS:
            name = self.world.entity(self.combat.opponent).name
            return self._turn([(f"You are fighting {name}. Finish the fight first.", "system")])
        return super()._gate(action)

    # --- menus ----------------------------------------------------------------------------
    def _special_choices(self):
        if self.combat is None:
            return super()._special_choices()
        uses = self._use_choices()
        if self.combat.stage == "verdict":
            return self._verdict_choices(), []
        if self.submenu == "use_menu":
            return uses + [Choice("Back", Action("back"))], []
        return self._fight_choices(), uses

    def _fight_choices(self) -> list[Choice]:
        d = self.combat
        art = self.world.entity(d.technique).name if d.technique else "bare hands"
        return [Choice(INTENT_LABELS[i], Action("intent", i)) for i in INTENTS] + [
            Choice(f"Change technique (now: {art})...", Action("use_menu")),
            Choice(f"Qi output: {d.output} (change)", Action("qi_output")),
            Choice("Yield", Action("yield_duel")),
            Choice("Flee", Action("flee")),
        ]

    def _use_choices(self) -> list[Choice]:
        body = self.body()
        arts = [a for a in martial_arts(self.world, self.player.id) if usable(body, a.technique.data)]
        choices = [Choice(f"Fight with the {a.name}", Action("use", a.technique.id)) for a in arts]
        return choices[:7] + [Choice("Fight bare-handed", Action("use", "bare"))]

    def _verdict_choices(self) -> list[Choice]:
        opponent = self.world.entity(self.combat.opponent)
        if opponent.data.get("beast"):
            return [Choice(f"Let {opponent.name} limp away", Action("verdict", "spare"))]
        return [
            Choice(f"Spare {opponent.name}", Action("verdict", "spare")),
            Choice(f"Rob {opponent.name}", Action("verdict", "rob")),
            Choice(f"Cripple {opponent.name}", Action("verdict", "cripple")),
        ]

    def _conversation_extras(self, npc) -> list:
        extras = []
        if not npc.data.get("beast"):
            if len(talk.conversations_with(self.world, npc.id, self.player.id)) >= 2:
                extras.append(Choice("Offer to spar", Action("spar", npc.id)))
            extras.append(Choice("Challenge them to a duel", Action("challenge", npc.id)))
        return extras + super()._conversation_extras(npc)

    # --- starting ---------------------------------------------------------------------------
    def _start_duel(self, opponent: int, mode: str, purpose: dict | None = None, opening: str | None = None) -> list:
        events = duel.start_events(self.world, self.player.id, opponent, self.place.id, mode, purpose, opening)
        lines = self._commit(events)
        self.combat = duel.Duel.from_event(self._last_ids[0], events[0])
        self.focus, self.submenu = None, None
        return lines

    def _offer_fight(self, npc_id, mode: str):
        npc_id = npc_id if npc_id is not None else self.focus
        present = {p.id for p in people_at(self.world, self.place.id, exclude=self.player.id)}
        if npc_id not in present:
            return self._turn([("There is no one like that here.", "system")])
        if not duel.accepts(self.world, npc_id, self.player.id, mode):
            return self._turn(self._commit(duel.refusal_events(self.player.id, npc_id, self.place.id, mode)))
        return self._turn(self._start_duel(npc_id, mode))

    def _do_spar(self, npc_id):
        return self._offer_fight(npc_id, "spar")

    def _do_challenge(self, npc_id):
        return self._offer_fight(npc_id, "duel")

    # --- fighting -----------------------------------------------------------------------------
    def _exchange(self, intent: str):
        events = duel.exchange_events(self.world, self.combat, intent)
        lines = self._commit(events)
        duel.apply_record(self.combat, events[0].data)
        if len(events) > 1:
            lines += self._finish_duel(events[-1].data)
        return self._turn(lines)

    def _do_intent(self, intent):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        if self.combat.stage == "verdict":
            return self._turn([(DECIDE, "system")])
        if intent not in INTENTS:
            return self._turn([("Strike, feint, guard or probe?", "system")])
        return self._exchange(intent)

    def _do_flee(self, _target):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        if self.combat.stage == "verdict":
            return self._turn([(DECIDE, "system")])
        return self._exchange("flee")

    def _do_yield_duel(self, _target):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        if self.combat.stage == "verdict":
            return self._turn([("You have already won. " + DECIDE, "system")])
        events = duel.yield_events(self.world, self.combat)
        lines = self._commit(events)
        return self._turn(lines + self._finish_duel(events[-1].data))

    def _do_verdict(self, choice):
        if self.combat is None or self.combat.stage != "verdict":
            return self._turn([("There is no one at your mercy.", "system")])
        events = duel.verdict_events(self.world, self.combat, choice)
        if not events:
            return self._turn([("Spare, rob or cripple?", "system")])
        lines = self._commit(events)
        return self._turn(lines + self._finish_duel(events[-1].data))

    def _do_use_menu(self, _target):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        self.submenu = "use_menu"
        return self._turn([("Which art will you fight with?", "system")])

    def _do_use(self, technique):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        valid = {c.action.target for c in self._use_choices()}
        if technique not in valid:
            return self._turn([("You can't fight with that now.", "system")])
        self.combat.technique = None if technique == "bare" else technique
        name = "bare hands" if technique == "bare" else f"the {self.world.entity(technique).name}"
        self.submenu = None
        return self._turn([(f"You will fight with {name}.", "system")])

    def _do_qi_output(self, _target):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        d = self.combat
        d.output = QI_OUTPUTS[(QI_OUTPUTS.index(d.output) + 1) % len(QI_OUTPUTS)]
        return self._turn([(f"You will put {d.output} qi behind your moves.", "system")])

    def _finish_duel(self, data: dict) -> list:
        self.combat, self.submenu = None, None
        return self._after_duel(data)

    # --- screen ---------------------------------------------------------------------------------
    def _special_art(self):
        if self.combat is None:
            return super()._special_art()
        opponent = self.world.entity(self.combat.opponent)
        harm = self.combat.harm["opponent"]
        return {"type": "duel", "parts": opponent.data.get("portrait"), "beast": bool(opponent.data.get("beast")),
                "harm": harm, "condition": condition_of(harm)}

    def _special_status(self):
        if self.combat is None:
            return super()._special_status()
        d, body = self.combat, self.body()
        opponent = self.world.entity(d.opponent).name
        art = self.world.entity(d.technique).name if d.technique else "bare hands"
        return (f"{self.player.name} | {realm_title(body)} | vs {opponent}: you {condition_of(d.harm['player'])}, "
                f"qi {body.qi:.0f} | them {condition_of(d.harm['opponent'])} | {art}, {d.output} qi")
```
`assets/art/beast.art`:
```
{grey}     /\     /\
    /  \___/  \
   |  {red}o{grey}     {red}o{grey}  |
    \    ^    /
     \_{white}vvvvv{grey}_/
       |     |
```
`engine/game.py`:
```python
"""The engine: Actions in, Turns out. The only code that commits events.

Feature mixins (fights, roads, dealings, invention) extend the engine through
the hooks in engine.hooks, so this file keeps the core loop: looking, talking,
travelling, cultivating, and turning state into a Turn.
"""

import random
import sqlite3

import systems.cultivation as cultivation
import systems.talk as talk
import systems.travel as travel
from engine.actions import Action, Choice, Turn
from engine.fight import FightMixin
from engine.hooks import GameHooks
from engine.journal import summarize
from narrate.base import Line, Narrator
from narrate.brief import event_brief, scene_brief
from narrate.procedural import ProceduralNarrator
from systems.bodies import load_body
from systems.creation import CreationChoice, apply_creation, build, wanderer_arts
from systems.realms import MAX_REALM, REALMS, energy_words, realm_title, requirement
from systems.techniques import known_arts, martial_arts, usable
from systems.time import format_date
from world.body import EXTRAORDINARY, Body, unhealed
from world.db import Entity, SaveError, World
from world.events import Event, commit
from world.gen.materialize import ensure_town, people_at, populate, region_of

__all__ = ["Action", "Choice", "Game", "Turn"]

MAX_SHOWN = 9  # digits 1-9 pick a choice with one key
KEEP_SUBMENU = frozenset({
    "people", "routes", "cultivate", "practise_menu", "meridian_menu", "ambiguous",
    "use_menu", "learn_menu", "browse", "create_menu",
})
QUIET_KINDS = frozenset({"exchange"})  # too many to list in the journal
BUSY = "Finish your conversation first."

HELP = [
    ("Type a number, or a command:", "system"),
    ("  look | talk <name> | go <place or direction> | ask <work|town> | bye | journal | help", "system"),
    ("  cultivate | meditate <day|week|month|season> | practise <art> | open <meridian> | rest | breakthrough", "system"),
    ("  challenge | spar | strike | feint | guard | probe | flee | yield | spare | rob | cripple", "system"),
    ("  F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu", "system"),
]


class Game(FightMixin, GameHooks):
    def __init__(self, world: World, narrator: Narrator | None = None) -> None:
        self.world = world
        self.narrator = narrator or ProceduralNarrator()
        self.focus: int | None = None
        self.submenu: str | None = None
        self.last_briefs: list = []  # what the narrator was given this turn (debug overlay, invariants)
        self.combat = None       # a systems.duel.Duel while fighting
        self.encounter = None    # a road encounter waiting for an answer (Task 7)
        self.challenger = None   # someone who just challenged the player (Task 7)
        self._last_ids: list[int] = []
        self._last_look: tuple[int, int] | None = None
        self._pending: list[Line] = []

    @classmethod
    def new(cls, path, player_name: str, world_seed: int | None = None, narrator=None,
            creation: CreationChoice | None = None) -> "Game":
        seed = world_seed if world_seed is not None else random.SystemRandom().randrange(2**31)
        world = World.create(path, seed)
        town = ensure_town(world, 0, 0, 0)
        made = build(seed, creation or CreationChoice())
        with world.transaction():
            player = world.add_entity("person", player_name, {"is_player": True, "age": 18, "realm": "mortal"})
            world.relate(player, town, "located_in")
            world.set_meta("player_id", player)
            arts = apply_creation(world, player, made)
        populate(world, town)
        game = cls(world, narrator)
        game._pending = game._commit([Event("began", (player,), town, {"origin": made.origin.title, "arts": arts})])
        return game

    @classmethod
    def load(cls, path, narrator=None) -> "Game":
        world = World.open(path)
        try:
            player_id = world.get_meta("player_id")
            player = world.entity(player_id) if isinstance(player_id, int) else None
            if player is None:
                raise SaveError(f"{world.path.name} has no player")
            if not world.targets(player.id, "located_in"):
                raise SaveError(f"{world.path.name}: {player.name} is nowhere in the world")
        except SaveError:
            world.close()
            raise
        except (sqlite3.DatabaseError, ValueError, KeyError, TypeError) as exc:
            world.close()
            raise SaveError(f"{world.path.name} is damaged ({exc})") from exc
        game = cls(world, narrator)
        if "body" not in player.data:  # a save from before bodies existed
            place = travel.location_of(world, player.id).id
            data = {"origin": "Wanderer", "arts": wanderer_arts(world.world_seed)}
            game._pending = game._commit([Event("body_awakened", (player.id,), place, data)])
        game._restore()
        return game

    def close(self) -> None:
        self.world.close()

    @property
    def player(self) -> Entity:
        return self.world.entity(self.world.get_meta("player_id"))

    @property
    def place(self) -> Entity:
        return travel.location_of(self.world, self.player.id)

    def body(self) -> Body:
        return load_body(self.world, self.player.id)

    # --- turns ----------------------------------------------------------------
    def start(self) -> Turn:
        return self.look()

    def look(self) -> Turn:
        self.last_briefs = []
        if self.combat is not None or self.encounter is not None or self.challenger is not None:
            return self._turn([])  # resuming mid-fight or mid-encounter: show its menu, not the town
        return self._do_look(None)

    def perform(self, action: Action) -> Turn:
        self.last_briefs = []
        gate = self._gate(action)
        if gate is not None:
            return gate
        handler = getattr(self, f"_do_{action.verb}", None)
        if handler is None:
            return self._turn([(f"You can't do that ({action.verb}).", "system")])
        if action.verb not in KEEP_SUBMENU:
            self.submenu = None
        return handler(action.target)

    def _do_people(self, _target) -> Turn:
        self.submenu = "people"
        return self._turn([("Who do you approach?", "system")])

    def _do_routes(self, _target) -> Turn:
        self.submenu = "routes"
        return self._turn([("Where to?", "system")])

    def _do_back(self, _target) -> Turn:
        return self._turn([])

    def _do_talk_menu(self, _target) -> Turn:
        return self._turn([])  # back to the plain conversation menu; focus is kept

    def _do_look(self, _target) -> Turn:
        self.focus = None
        here = (self.place.id, self.world.time)
        if here == self._last_look:
            return self._turn([("Nothing has changed since you last looked.", "dim")] + self._presence() + self._after_look())
        self._last_look = here
        return self._turn(self._describe("look") + self._presence() + self._after_look())

    def _do_travel(self, dest) -> Turn:
        routes = {r.dest: r for r in travel.routes_from(self.world, self.place)}
        route = routes.get(tuple(dest) if dest is not None else None)
        if route is None:
            return self._turn([("You can't get there from here.", "system")])
        self.focus = None
        lines = self._commit(travel.travel_events(self.player.id, self.place.id, route))
        populate(self.world, self.place.id)
        self._last_look = (self.place.id, self.world.time)
        return self._turn(lines + self._describe("arrive") + self._presence() + self._after_arrival())

    def _do_talk(self, npc_id) -> Turn:
        present = {p.id for p in people_at(self.world, self.place.id, exclude=self.player.id)}
        if npc_id not in present:
            return self._turn([("There is no one like that here.", "system")])
        self.focus = npc_id
        return self._turn(self._commit(talk.greet_events(self.world, self.player.id, npc_id, self.place.id)))

    def _do_ask(self, topic) -> Turn:
        if self.focus is None or topic not in talk.TOPICS:
            return self._turn([("Ask whom, about what?", "system")])
        npc, me = self.world.entity(self.focus), self.player.id
        if talk.repeats_if_asked(self.world, npc.id, me, topic) > talk.patience_of(npc):
            lines = self._commit(talk.lost_patience_events(me, npc.id, self.place.id, topic))
            self.focus = None
            return self._turn(lines)
        return self._turn(self._commit(talk.ask_events(me, npc.id, self.place.id, topic)))

    def _do_farewell(self, _target) -> Turn:
        if self.focus is None:
            return self._turn([("You aren't talking to anyone.", "system")])
        lines = self._commit(talk.farewell_events(self.player.id, self.focus, self.place.id))
        self.focus = None
        return self._turn(lines)

    def _do_journal(self, _target) -> Turn:
        entries = [e for e in reversed(self.world.chronicle_about(self.player.id, limit=60)) if e.kind not in QUIET_KINDS]
        lines = [(f"Chronicle of {self.player.name}:", "heading")]
        lines += [(summarize(self.world, e), "dim") for e in entries[-15:]]
        return self._turn(lines)

    def _do_help(self, _target) -> Turn:
        return self._turn(list(HELP))

    def _do_unknown(self, text) -> Turn:
        return self._turn([(f"Not understood: {str(text)[:60]!r}. Type 'help' for commands.", "system")])

    def _do_ambiguous(self, options) -> Turn:
        turn = self._turn([("Which one do you mean?", "system")])
        turn.choices = list(options)
        return turn

    # --- cultivation ----------------------------------------------------------------
    def _busy(self) -> Turn | None:
        return self._turn([(BUSY, "system")]) if self.focus is not None else None

    def _cultivated(self, events: list[Event], reason: str) -> Turn:
        if not events:
            return self._turn([(reason, "system")])
        lines = self._commit(events)
        self.submenu = "cultivate"
        return self._turn(lines)

    def _do_cultivate(self, _target) -> Turn:
        if busy := self._busy():
            return busy
        self.submenu = "cultivate"
        return self._turn(self._cultivation_status())

    def _do_practise_menu(self, _target) -> Turn:
        if busy := self._busy():
            return busy
        self.submenu = "practise_menu"
        return self._turn([("Which art will you drill?", "system")])

    def _do_meridian_menu(self, _target) -> Turn:
        if busy := self._busy():
            return busy
        self.submenu = "meridian_menu"
        return self._turn([("Which sealed meridian will you work on?", "system")])

    def _do_meditate(self, days) -> Turn:
        if busy := self._busy():
            return busy
        days = days if days in cultivation.MEDITATE_OPTIONS.values() else 7
        events = cultivation.meditate_events(self.world, self.player.id, self.place.id, days)
        return self._cultivated(events, "You cannot meditate now.")

    def _do_practise(self, technique_id) -> Turn:
        if busy := self._busy():
            return busy
        art = next((a for a in martial_arts(self.world, self.player.id) if a.technique.id == technique_id), None)
        if art is None:
            return self._turn([("You don't know that art.", "system")])
        if not usable(self.body(), art.technique.data):
            return self._turn([(f"A severed meridian puts the {art.name} beyond you now.", "system")])
        events = cultivation.practise_events(self.world, self.player.id, self.place.id, technique_id)
        return self._cultivated(events, "You cannot practise that now.")

    def _do_open_meridian(self, name) -> Turn:
        if busy := self._busy():
            return busy
        reason = cultivation.why_not_open(self.body(), name)
        if reason:
            return self._turn([(reason, "system")])
        events = cultivation.open_meridian_events(self.world, self.player.id, self.place.id, name)
        return self._cultivated(events, "Nothing happens.")

    def _do_rest(self, days) -> Turn:
        if busy := self._busy():
            return busy
        days = days if isinstance(days, int) and 0 < days <= 90 else cultivation.REST_DAYS
        events = cultivation.rest_events(self.world, self.player.id, self.place.id, days)
        return self._cultivated(events, "You cannot rest now.")

    def _do_breakthrough(self, _target) -> Turn:
        if busy := self._busy():
            return busy
        events = cultivation.breakthrough_events(self.world, self.player.id, self.place.id)
        return self._cultivated(events, "Your qi has not yet reached a bottleneck.")

    def _cultivation_status(self) -> list[Line]:
        body = self.body()
        who = "a mortal" if body.realm == 0 else f"a {realm_title(body)} warrior"
        lines = [(f"You are {who}, with {energy_words(body.energy_years)}.", "dim")]
        if body.bottleneck and body.realm < MAX_REALM:
            lines.append((f"Your qi presses against a bottleneck. Only a breakthrough to {REALMS[body.realm + 1].name} will let it grow.", "dim"))
            ready, needed = requirement(body, known_arts(self.world, self.player.id))
            if not ready:
                lines.append((f"You are not ready to break through: {needed}", "dim"))
        if body.deviation > 60:
            lines.append(("Your qi feels unruly; a deviation may be near.", "dim"))
        hurt = sorted({i.location for i in unhealed(body, self.world.time)})
        if hurt:
            lines.append(("Still healing: " + ", ".join(hurt) + ".", "dim"))
        return lines

    # --- helpers --------------------------------------------------------------
    def _commit(self, events: list[Event]) -> list[Line]:
        ids = commit(self.world, events)
        self._last_ids = ids
        lines: list[Line] = []
        for event_id, event in zip(ids, events):
            brief = event_brief(self.world, event_id, event)
            self.last_briefs.append(brief)
            lines += self.narrator.narrate(brief)
        return lines

    def _describe(self, salt: str) -> list[Line]:
        brief = scene_brief(self.world, self.place.id, self.player.id, salt)
        self.last_briefs.append(brief)
        return self.narrator.narrate(brief)

    def _presence(self) -> list[Line]:
        people = people_at(self.world, self.place.id, exclude=self.player.id)
        if not people:
            return [("No one of note is here.", "dim")]
        described = []
        for person in people:
            known = " (knows you)" if talk.conversations_with(self.world, person.id, self.player.id) else ""
            described.append(f"{person.name} the {person.data.get('occupation', 'stranger')}{known}")
        return [("Here: " + ", ".join(described) + ".", "dim")]

    # --- menus ----------------------------------------------------------------------
    def _choices(self) -> tuple[list[Choice], list[Choice]]:
        """(shown, extra). At most MAX_SHOWN are shown, so each has a single-key number.
        Everything valid but not shown goes in `extra`, so typed commands still reach it."""
        special = self._special_choices()
        if special is not None:
            return special
        feature_menus = self._submenu_options()
        if self.focus is not None:
            if self.submenu in feature_menus:
                options, back = feature_menus[self.submenu]
                return options[: MAX_SHOWN - 1] + [Choice("Back", back)], []
            npc = self.world.entity(self.focus)
            return [
                Choice("Ask about their work", Action("ask", "work")),
                Choice(f"Ask about {self.place.name}", Action("ask", "town")),
                *self._conversation_extras(npc),
                Choice("Say farewell", Action("farewell")),
            ], []
        body = self.body()
        people = [
            Choice(f"Talk to {p.name} ({p.data.get('occupation', 'stranger')})", Action("talk", p.id))
            for p in people_at(self.world, self.place.id, exclude=self.player.id)
        ]
        routes = [Choice(r.label, Action("travel", r.dest)) for r in travel.routes_from(self.world, self.place)]
        general = [Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]
        practise = [Choice(f"Practise the {a.name} for a week", Action("practise", a.technique.id))
                    for a in martial_arts(self.world, self.player.id)] + self._practise_extras(body)
        cultivate = self._cultivation_choices(body, bool(practise))
        meridians = [Choice(f"Work on the {m} meridian for a week", Action("open_meridian", m))
                     for m in EXTRAORDINARY if body.meridians[m].state == "blocked"]
        submenus = {
            "people": (people, Action("back")), "routes": (routes, Action("back")),
            "cultivate": (cultivate, Action("back")),
            "practise_menu": (practise, Action("cultivate")), "meridian_menu": (meridians, Action("cultivate")),
        }
        submenus.update(feature_menus)
        everything = people + routes + cultivate + practise + meridians + general
        for options, _ in feature_menus.values():
            everything += [c for c in options if c not in everything]
        if self.submenu in submenus:
            options, back = submenus[self.submenu]
            shown = options[: MAX_SHOWN - 1] + [Choice("Back", back)]
        else:
            shown = self._main_menu(people, routes, general)
        return shown, [c for c in everything if c not in shown]

    def _main_menu(self, people: list[Choice], routes: list[Choice], general: list[Choice]) -> list[Choice]:
        entry = Choice("Cultivate...", Action("cultivate"))
        fold = {"people": False, "routes": False}

        def menu() -> list[Choice]:
            items = [Choice(f"Talk to someone here ({len(people)})", Action("people"))] if fold["people"] else list(people)
            items += [Choice(f"Travel ({len(routes)} routes)", Action("routes"))] if fold["routes"] else list(routes)
            return items + [entry] + general

        for name, group in (("people", people), ("routes", routes)):
            if len(menu()) > MAX_SHOWN and len(group) > 1:
                fold[name] = True
        return menu()

    def _cultivation_choices(self, body: Body, can_practise: bool) -> list[Choice]:
        options = [
            Choice("Meditate for a day", Action("meditate", 1)),
            Choice("Meditate for a week", Action("meditate", 7)),
            Choice("Meditate for a month", Action("meditate", 30)),
            Choice("Seclusion for a season (90 days)", Action("meditate", 90)),
        ]
        if can_practise:
            options.append(Choice("Practise an art...", Action("practise_menu")))
        if any(body.meridians[m].state == "blocked" for m in EXTRAORDINARY):
            options.append(Choice("Work on opening a meridian...", Action("meridian_menu")))
        options.append(Choice("Rest for a week", Action("rest", 7)))
        if body.bottleneck and body.realm < MAX_REALM:
            options.append(Choice(f"Attempt breakthrough to {REALMS[body.realm + 1].name}", Action("breakthrough")))
        return options

    def _art(self) -> dict:
        special = self._special_art()
        if special is not None:
            return special
        if self.focus is not None:
            return {"type": "portrait", "parts": self.world.entity(self.focus).data["portrait"]}
        place = self.place
        return {"type": "scene", "terrain": place.data["terrain"], "settlement": place.data["kind"], "watch": self.world.time % 4}

    def _status(self) -> str:
        special = self._special_status()
        if special is not None:
            return special
        player, place = self.player, self.place
        region = region_of(self.world, place.id)
        return f"{player.name} | {realm_title(self.body())} | {format_date(self.world.time)} | {place.name}, {region.name}"

    def _turn(self, lines: list[Line]) -> Turn:
        lines, self._pending = self._pending + lines, []
        shown, extra = self._choices()
        return Turn(lines, shown, self._art(), self._status(), extra)
```
`engine/commands.py`:
```python
"""Typed commands to Actions, matched against what the player can do right now.

The parser knows only global words and the current choices (shown and folded),
so every command the engine can take also has a number to press somewhere.
"""

import re

from engine.actions import Action, Choice

GLOBAL = {
    "look": Action("look"), "l": Action("look"), "journal": Action("journal"), "j": Action("journal"),
    "chronicle": Action("journal"), "help": Action("help"), "?": Action("help"),
    "bye": Action("farewell"), "farewell": Action("farewell"), "leave": Action("farewell"),
    "cultivate": Action("cultivate"), "meditate": Action("meditate"), "rest": Action("rest"),
    "breakthrough": Action("breakthrough"),
    "strike": Action("intent", "strike"), "feint": Action("intent", "feint"),
    "guard": Action("intent", "guard"), "probe": Action("intent", "probe"),
    "flee": Action("flee"), "run": Action("flee"), "yield": Action("yield_duel"), "surrender": Action("yield_duel"),
    "spare": Action("verdict", "spare"), "rob": Action("verdict", "rob"), "cripple": Action("verdict", "cripple"),
    "spar": Action("spar"), "challenge": Action("challenge"),
}
PREFIX_VERBS = {
    "talk": "talk", "speak": "talk", "go": "travel", "travel": "travel", "walk": "travel", "ask": "ask",
    "meditate": "meditate", "practise": "practise", "practice": "practise", "train": "practise",
    "open": "open_meridian", "use": "use",
}
FILLER = {"to", "about", "with", "the"}
WORD = re.compile(r"[a-z0-9']+")


def _words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def parse(text: str, choices: list[Choice], extra: list[Choice] = ()) -> Action | None:
    """Numbers index the visible `choices`; words also search `extra` (folded-away choices)."""
    cleaned = " ".join(text.split())[:200]
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered.isascii() and lowered.isdigit():
        n = int(lowered)
        return choices[n - 1].action if 1 <= n <= len(choices) else Action("unknown", cleaned)
    if lowered in GLOBAL:
        return GLOBAL[lowered]
    head, _, rest = lowered.partition(" ")
    verb = PREFIX_VERBS.get(head)
    wanted = [w for w in _words(rest) if w not in FILLER]
    if verb is None or not wanted:
        return Action("unknown", cleaned)
    pool = [c for c in [*choices, *extra] if c.action.verb == verb]
    pool = list({c.action: c for c in pool}.values())  # a choice may be both visible and extra
    exact = [c for c in pool if all(w in _words(c.label) for w in wanted)]
    prefix = [c for c in pool if all(any(lw.startswith(w) for lw in _words(c.label)) for w in wanted)]
    for matches in (exact, prefix):
        if len(matches) == 1:
            return matches[0].action
        if len(matches) > 1:
            return Action("ambiguous", tuple(matches))
    return Action("unknown", cleaned)
```
`.patches/2b_task6.py`:
```python
import pathlib


def patch(f, pairs):
    p = pathlib.Path(f)
    t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (f, a[:70])
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8", newline="\n")


patch("render/art.py", [
    ("""def render_request(request: dict, w: int, h: int) -> Art:
    kind = request.get("type")""",
     """def harm_bar(harm: float, condition: str, w: int) -> list:
    filled = int(round(10 * min(max(harm, 0.0), 100.0) / 100))
    text = f"[{'#' * filled}{'.' * (10 - filled)}] {condition}"
    row: list = [None] * w
    start = max(0, (w - len(text)) // 2)
    for i, ch in enumerate(text):
        if 0 <= start + i < w and ch != " ":
            row[start + i] = (ch, "red" if ch == "#" else "dim")
    return row


def compose_duel(request: dict, w: int, h: int) -> Art:
    height = max(1, h - 2)
    if request.get("parts"):
        art = compose_portrait(request["parts"], w, height)
    else:
        art = blank(w, height)
        beast = load_art("beast")
        stamp(art, beast, max(0, (height - len(beast)) // 2), (w - art_width(beast)) // 2)
    rows = art + [[None] * w, harm_bar(request.get("harm", 0.0), request.get("condition", ""), w)]
    return rows[-h:] if h < len(rows) else rows


def render_request(request: dict, w: int, h: int) -> Art:
    kind = request.get("type")
    if kind == "duel":
        return compose_duel(request, w, h)"""),
])
print("task 6 patched")
```

- [ ] **Step 4: Run** `python .patches/2b_task6.py`, then the tests → `tests/test_fight_flow.py` PASS (10 passed, or 9 plus 1 skip), and the full suite passes. The existing fuzz test must stay clean. Its random presses can now start fights, and every duel event already has prose from Task 5.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: fighting in the engine - challenges, spars, exchanges, verdicts, duel screen" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 7: Road encounters and grudge challenges

**Files:**
- Create: `systems/encounters.py`, `engine/roads.py`, `narrate/road_text.py`, `narrate/grammar/roads.toml`, `.patches/2b_task7.py`
- Modify via the patch script: `engine/game.py` (add the mixin to the class line), `narrate/outcomes.py` (register the road text)
- Test: `tests/test_roads.py`

**Interfaces:**
- Consumes: Tasks 1–6 (`payment_events`, `silver_of`, `duel.fighter_for`, `flee_chance`, `FightMixin._start_duel`)
- Produces:
  - In `systems/encounters.py`:
    - Constants: `ENCOUNTER_CHANCE = 0.35`, `CHALLENGE_CHANCE = 0.3`, `GRUDGE_FEELINGS`, `BEASTS`
    - Region and roamers: `region_danger(world_seed, x, y) -> float`, `roamers(world, region_id) -> list[int]`, `make_roamer(world, region, kind, index, danger) -> int`, where kind is `"bandit"`, `"beast"` or `"wanderer"`
    - Encounter builders: `road_encounter_events(world, player, town) -> list[Event]`, `encounter_events(player, person, place, kind, toll) -> list[Event]`, `encounter_state(event) -> dict`, `resolved_events(player, person, place, how, kind) -> list[Event]`
    - Checks: `talk_succeeds(world, person, player) -> bool`, `flee_succeeds(world, player, person) -> bool`
    - Challenges: `challenge_from(world, player, place) -> int | None`, `challenge_events(player, npc, place)`, `decline_events(player, npc, place)`
    - After a load: `pending_encounter(world, player) -> dict | None`, `pending_challenge(world, player) -> int | None`
  - Event kinds:
    - `encounter` with data `{kind, toll, danger}`
    - `encounter_resolved` with data `{how, kind}`, where how is `paid`, `talked`, `fled` or `fight`
    - `challenge_issued`, and `declined_challenge` (the NPC remembers *contempt*)
  - `RoadsMixin` adds the verbs `road` (target `fight`/`flee`/`pay`/`talk`) and `answer_challenge` (target `True`/`False`). It restores a pending encounter or challenge after a load.

- [ ] **Step 1: Write the failing test** — `tests/test_roads.py`
```python
import pytest

import systems.encounters as encounters
from engine.game import Action, Game
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit
from world.gen.materialize import region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "merchant"))
    g.start()
    yield g
    g.close()


def meet(game, kind="bandit", toll=10):
    region = region_of(game.world, game.place.id)
    slot = {"bandit": 90, "beast": 91, "wanderer": 92}[kind]
    person = encounters.make_roamer(game.world, region, kind, slot, 0.2)
    events = encounters.encounter_events(game.player.id, person, game.place.id, kind, toll)
    commit(game.world, events)
    game.encounter = encounters.encounter_state(events[0])
    return person


def verbs(turn):
    return [c.action for c in turn.choices]


def test_danger_is_seeded_and_home_is_safe():
    assert encounters.region_danger(5, 0, 0) == 0.1
    assert encounters.region_danger(5, 3, -2) == encounters.region_danger(5, 3, -2)
    assert all(0 <= encounters.region_danger(5, x, 1) <= 1 for x in range(20))


def test_roamers_live_in_the_region(game):
    region = region_of(game.world, game.place.id)
    wolf = encounters.make_roamer(game.world, region, "beast", 0, 0.5)
    bandit = encounters.make_roamer(game.world, region, "bandit", 1, 0.5)
    assert game.world.entity(wolf).data["beast"] and game.world.entity(wolf).name.startswith("a ")
    assert game.world.entity(bandit).data["occupation"] == "bandit"
    assert set(encounters.roamers(game.world, region.id)) == {wolf, bandit}


def test_travel_can_end_in_an_encounter_that_blocks_everything_else(game, monkeypatch):
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 1e9)
    road = next(c.action for c in game.look().all_choices if c.action.verb == "travel")
    turn = game.perform(road)
    assert game.encounter is not None and turn.choices[0].action == Action("road", "fight")
    assert "Deal with them first" in game.perform(Action("meditate", 7)).lines[-1][0]


def test_paying_the_toll(game):
    bandit = meet(game, toll=10)
    mine, theirs = silver_of(game.world, game.player.id), silver_of(game.world, bandit)
    game.perform(Action("road", "pay"))
    assert game.encounter is None
    assert silver_of(game.world, game.player.id) == mine - 10 and silver_of(game.world, bandit) == theirs + 10


def test_no_silver_no_toll(game):
    meet(game, toll=10)
    game.world.update_data(game.player.id, silver=3)
    turn = game.perform(Action("road", "pay"))
    assert game.encounter is not None and "You don't have 10 silver." == turn.lines[-1][0]


def test_beasts_do_not_talk_and_failed_talk_means_a_fight(game, monkeypatch):
    meet(game, kind="beast", toll=0)
    assert Action("road", "talk") not in verbs(game.look())
    game.encounter = None
    meet(game, kind="bandit")
    monkeypatch.setattr(encounters, "talk_succeeds", lambda *a: False)
    game.perform(Action("road", "talk"))
    assert game.encounter is None and game.combat is not None and game.combat.mode == "encounter"


def test_fleeing_the_road(game, monkeypatch):
    meet(game, kind="wanderer", toll=0)
    monkeypatch.setattr(encounters, "flee_succeeds", lambda *a: True)
    game.perform(Action("road", "flee"))
    assert game.encounter is None and game.combat is None


def test_an_unanswered_encounter_survives_a_reload(tmp_path):
    path = tmp_path / "g.world"
    game = Game.new(path, "Hero", world_seed=11)
    person = meet(game)
    game.close()
    again = Game.load(path)
    assert again.encounter == {"person": person, "kind": "bandit", "toll": 10}
    again.close()


def test_a_grudge_becomes_a_challenge(game, monkeypatch):
    hothead = game.world.add_entity("person", "Hot Wu", {"occupation": "constable", "traits": ["hot-tempered", "proud"],
                                                          "realm": "mortal", "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(hothead, game.place.id, "located_in")
    commit(game.world, [encounters.Event("lost_patience", (game.player.id, hothead), game.place.id, {"topic": "work"},
                                         witnesses=(encounters.Witness(hothead, "annoyed", 0.5),))])
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 1.0)
    game.world.set_time(game.world.time + 4)
    turn = game.perform(Action("look"))
    assert game.challenger == hothead and [c.action.verb for c in turn.choices] == ["answer_challenge", "answer_challenge"]
    game.perform(Action("answer_challenge", False))
    assert game.challenger is None
    assert game.world.memories(hothead, about=game.player.id)[-1].feeling == "contempt"
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: systems.encounters`)

- [ ] **Step 3: Implement**

`systems/encounters.py`:
```python
"""Road encounters and grudge challenges (phase 2 spec §10).

Bandits, beasts and rival wanderers are real people of their region: they are
materialized once, live in the region (not a town), and remember you.
"""

from systems.duel import fighter_for
from systems.combat_core import flee_chance
from systems.items import create_manual
from systems.purse import silver_of
from systems.realms import realm_index
from systems.techniques import create_technique, generate
from world.events import Event, Witness, effect  # noqa: F401  (Witness re-exported for callers)
from world.gen.materialize import people_at, region_of
from world.gen.names import person_name
from world.gen.npc import PORTRAIT_PARTS, TRAITS
from world.gen.region import region_path
from world.seed import rng_for

ENCOUNTER_CHANCE = 0.35
CHALLENGE_CHANCE = 0.3
BANDIT_MANUAL_CHANCE = 0.25
GRUDGE_FEELINGS = frozenset({"annoyed", "humiliated", "hatred", "contempt"})
BEASTS = {"forest": ("grey wolf", "wild boar"), "mountains": ("mountain tiger", "grey wolf"), "marsh": ("marsh crocodile",)}
FRIENDLY = frozenset({"kind", "lazy", "cheerful", "honest"})


def region_danger(world_seed: int, x: int, y: int) -> float:
    if (x, y) == (0, 0):
        return 0.1  # the starting region is gentle
    return round(rng_for(world_seed, f"{region_path(x, y)}/danger").random() ** 1.5, 3)


def _realm_for(danger: float, rng) -> str:
    roll = danger + rng.uniform(-0.15, 0.15)
    return "mortal" if roll < 0.35 else "third-rate" if roll < 0.65 else "second-rate" if roll < 0.9 else "first-rate"


def roamers(world, region_id: int) -> list[int]:
    return [p for p in world.sources(region_id, "located_in") if world.entity(p).data.get("roamer")]


def make_roamer(world, region, kind: str, index: int, danger: float) -> int:
    path = f"{region.seed_path}/roamer:{index}"
    existing = world.entity_by_seed(path)
    if existing is not None:
        return existing.id
    rng = rng_for(world.world_seed, path)
    realm = _realm_for(danger, rng)
    if kind == "beast":
        species = rng.choice(BEASTS.get(region.data["terrain"], ("grey wolf",)))
        name = f"a {species}"
        data = {"beast": True, "occupation": species, "traits": ["hot-tempered"], "realm": realm,
                "roamer": True, "roamer_kind": kind, "silver": 0}
    else:
        surname, given = person_name(rng)
        occupation = "bandit" if kind == "bandit" else "wandering swordsman"
        traits = list(dict.fromkeys(["greedy", rng.choice(TRAITS)])) if kind == "bandit" else rng.sample(TRAITS, 2)
        name = f"{surname} {given}"
        data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": rng.randint(18, 55),
                "occupation": occupation, "traits": traits, "realm": realm, "roamer": True, "roamer_kind": kind,
                "portrait": {part: rng.randrange(count) for part, count in PORTRAIT_PARTS.items()}}
    with world.transaction():
        person = world.add_entity("person", name, data, path)
        world.relate(person, region.id, "located_in")
        if kind == "bandit" and rng.random() < BANDIT_MANUAL_CHANCE:
            art_name, art = generate(rng, "martial", grade=1 + realm_index(realm))
            create_manual(world, person, create_technique(world, art_name, art), rng.uniform(0.4, 1.0))
    return person


def encounter_events(player: int, person: int, place: int, kind: str, toll: int) -> list[Event]:
    return [Event("encounter", (player, person), place, {"kind": kind, "toll": int(toll)})]


def road_encounter_events(world, player: int, town) -> list[Event]:
    region = region_of(world, town.id)
    danger = region_danger(world.world_seed, region.data["x"], region.data["y"])
    rng = rng_for(world.world_seed, f"road:{player}:{world.time}")
    if rng.random() >= danger * ENCOUNTER_CHANCE:
        return []
    kinds = ["bandit", "wanderer"] + (["beast"] if region.data["terrain"] in BEASTS else [])
    kind = rng.choice(kinds)
    known = [p for p in roamers(world, region.id) if world.entity(p).data.get("roamer_kind") == kind]
    if known and rng.random() < 0.5:
        person = rng.choice(known)
    else:
        person = make_roamer(world, region, kind, len(roamers(world, region.id)), danger)
    toll = max(5, int(silver_of(world, player) * 0.2)) if kind == "bandit" else 0
    return encounter_events(player, person, town.id, kind, toll)


def encounter_state(event) -> dict:
    return {"person": event.actors[1], "kind": event.data["kind"], "toll": event.data["toll"]}


def resolved_events(player: int, person: int, place: int, how: str, kind: str) -> list[Event]:
    feeling = {"paid": "contempt", "fled": "contempt", "talked": "amused"}.get(how)
    witnesses = (Witness(person, feeling, 0.3),) if feeling else ()
    return [Event("encounter_resolved", (player, person), place, {"how": how, "kind": kind}, witnesses=witnesses)]


def talk_succeeds(world, person: int, player: int) -> bool:
    entity = world.entity(person)
    if entity.data.get("beast"):
        return False
    rng = rng_for(world.world_seed, f"roadtalk:{person}:{world.time}")
    if entity.data.get("roamer_kind") == "wanderer":
        return rng.random() < 0.8
    friendly = 0.3 if FRIENDLY & set(entity.data.get("traits", ())) else 0.0
    return rng.random() < 0.25 + friendly


def flee_succeeds(world, player: int, person: int) -> bool:
    rng = rng_for(world.world_seed, f"roadflee:{person}:{world.time}")
    return rng.random() < flee_chance(fighter_for(world, player, None), fighter_for(world, person, None), 0.0)


def challenge_from(world, player: int, place: int) -> int | None:
    rng = rng_for(world.world_seed, f"challenge:{player}:{place}:{world.time}")
    for person in people_at(world, place, exclude=player):
        if not set(person.data.get("traits", ())) & {"proud", "hot-tempered"}:
            continue
        grudges = [m for m in world.memories(person.id, about=player) if m.feeling in GRUDGE_FEELINGS]
        if grudges and rng.random() < CHALLENGE_CHANCE:
            return person.id
    return None


def challenge_events(player: int, npc: int, place: int) -> list[Event]:
    return [Event("challenge_issued", (player, npc), place, {})]


def decline_events(player: int, npc: int, place: int) -> list[Event]:
    return [Event("declined_challenge", (player, npc), place, {}, witnesses=(Witness(npc, "contempt", 0.4),))]


def pending_encounter(world, player: int) -> dict | None:
    for entry in world.chronicle_about(player, limit=30):  # newest first
        if entry.kind in ("encounter_resolved", "travelled", "duel_started"):
            return None
        if entry.kind == "encounter":
            return {"person": entry.actors[1], "kind": entry.data["kind"], "toll": entry.data["toll"]}
    return None


def pending_challenge(world, player: int) -> int | None:
    for entry in world.chronicle_about(player, limit=30):
        if entry.kind in ("declined_challenge", "duel_started", "travelled"):
            return None
        if entry.kind == "challenge_issued":
            return entry.actors[1]
    return None
```
`engine/roads.py`:
```python
"""Road encounters and grudge challenges in the engine (phase 2 spec §10)."""

import systems.encounters as encounters
from engine.actions import Action, Choice
from narrate.outcomes import cap
from systems.purse import payment_events, silver_of

ROAD_VERBS = frozenset({"road", "help", "journal", "unknown", "ambiguous"})
CHALLENGE_VERBS = frozenset({"answer_challenge", "help", "journal", "unknown", "ambiguous"})


class RoadsMixin:
    def _restore(self) -> None:
        super()._restore()
        if self.combat is None:
            self.encounter = encounters.pending_encounter(self.world, self.player.id)
            self.challenger = encounters.pending_challenge(self.world, self.player.id)

    def _gate(self, action):
        if self.encounter is not None and action.verb not in ROAD_VERBS:
            name = cap(self.world.entity(self.encounter["person"]).name)
            return self._turn([(f"{name} blocks the road. Deal with them first.", "system")])
        if self.challenger is not None and action.verb not in CHALLENGE_VERBS:
            name = self.world.entity(self.challenger).name
            return self._turn([(f"{name} is waiting for your answer.", "system")])
        return super()._gate(action)

    def _special_choices(self):
        if self.encounter is not None:
            return self._road_choices(), []
        if self.challenger is not None:
            return [Choice("Accept the challenge", Action("answer_challenge", True)),
                    Choice("Decline", Action("answer_challenge", False))], []
        return super()._special_choices()

    def _road_choices(self) -> list[Choice]:
        e = self.encounter
        choices = [Choice("Fight", Action("road", "fight")), Choice("Try to flee", Action("road", "flee"))]
        if e["kind"] == "bandit":
            choices.append(Choice(f"Pay the toll ({e['toll']} silver)", Action("road", "pay")))
        if e["kind"] != "beast":
            choices.append(Choice("Talk your way past", Action("road", "talk")))
        return choices

    def _special_art(self):
        who = self.encounter["person"] if self.encounter else self.challenger
        if who is None:
            return super()._special_art()
        person = self.world.entity(who)
        return {"type": "duel", "parts": person.data.get("portrait"), "beast": bool(person.data.get("beast")),
                "harm": 0.0, "condition": "fresh"}

    def _after_arrival(self) -> list:
        lines = super()._after_arrival()
        events = encounters.road_encounter_events(self.world, self.player.id, self.place)
        if events:
            lines += self._commit(events)
            self.encounter = encounters.encounter_state(events[0])
        return lines

    def _after_look(self) -> list:
        lines = super()._after_look()
        npc = encounters.challenge_from(self.world, self.player.id, self.place.id)
        if npc is not None:
            lines += self._commit(encounters.challenge_events(self.player.id, npc, self.place.id))
            self.challenger = npc
        return lines

    def _resolve(self, how: str) -> list:
        e = self.encounter
        self.encounter = None
        return self._commit(encounters.resolved_events(self.player.id, e["person"], self.place.id, how, e["kind"]))

    def _do_road(self, how):
        if self.encounter is None:
            return self._turn([("Nothing stands in your way.", "system")])
        e, me, place = self.encounter, self.player.id, self.place.id
        person = e["person"]
        if how == "pay":
            if e["kind"] != "bandit":
                return self._turn([("There is no toll to pay.", "system")])
            if silver_of(self.world, me) < e["toll"]:
                return self._turn([(f"You don't have {e['toll']} silver.", "system")])
            lines = self._commit(payment_events(me, person, place, e["toll"], "toll"))
            return self._turn(lines + self._resolve("paid"))
        if how == "talk":
            if e["kind"] == "beast":
                return self._turn([("It does not understand words.", "system")])
            if encounters.talk_succeeds(self.world, person, me):
                return self._turn(self._resolve("talked"))
            return self._turn(self._resolve("fight") + self._start_duel(person, "encounter"))
        if how == "flee":
            if encounters.flee_succeeds(self.world, me, person):
                return self._turn(self._resolve("fled"))
            return self._turn(self._resolve("fight") + self._start_duel(person, "encounter", opening="opponent"))
        if how == "fight":
            return self._turn(self._resolve("fight") + self._start_duel(person, "encounter"))
        return self._turn([("Fight, flee, pay or talk?", "system")])

    def _do_answer_challenge(self, accept):
        if self.challenger is None:
            return self._turn([("No one has challenged you.", "system")])
        npc, self.challenger = self.challenger, None
        if accept:
            return self._turn(self._start_duel(npc, "duel"))
        return self._turn(self._commit(encounters.decline_events(self.player.id, npc, self.place.id)))
```
`narrate/road_text.py`:
```python
"""What the player is told on the road, and about tolls and payments."""

from narrate.outcomes import cap, outcome, summary

HOW = {
    "paid": "You pay and are let through.", "talked": "You talk your way past {name}.",
    "fled": "You slip away from {name}.", "fight": "There is no way around it: you fight.",
}


def _name(world, event) -> str:
    return world.entity(event.actors[1]).name


@outcome("encounter")
def _encounter(world, event):
    d, name = event.data, _name(world, event)
    line = {
        "bandit": f"{cap(name)}, a bandit, blocks the road and demands {d['toll']} silver.",
        "beast": f"{cap(name)} stalks out onto the road, hungry.",
        "wanderer": f"{cap(name)}, a wandering swordsman, bars the road and looks you over.",
    }[d["kind"]]
    return [line], {"grammar_key": f"encounter.{d['kind']}"}


@outcome("encounter_resolved")
def _resolved(world, event):
    return [HOW[event.data["how"]].format(name=_name(world, event))], {}


@outcome("challenge_issued", body_facts=False)
def _challenge(world, event):
    return [f"{cap(_name(world, event))} blocks your way: they have not forgotten you."], {}


@outcome("declined_challenge", body_facts=False)
def _declined(world, event):
    return [f"You turn {_name(world, event)} down. They will not forget it."], {}


@outcome("paid", body_facts=False)
def _paid(world, event):
    return [f"You pay {event.data['amount']} silver."], {}


@summary("encounter")
def _encounter_line(world, entry, names, place, other):
    return f"Met {other} on the road."


@summary("encounter_resolved")
def _resolved_line(world, entry, names, place, other):
    return {"paid": f"Paid {other} to pass.", "talked": f"Talked past {other}.",
            "fled": f"Fled from {other}.", "fight": f"Fought {other} on the road."}[entry.data["how"]]


@summary("challenge_issued")
def _challenge_line(world, entry, names, place, other):
    return f"{cap(other)} challenged you."


@summary("declined_challenge")
def _declined_line(world, entry, names, place, other):
    return f"Declined {other}'s challenge."


@summary("paid")
def _paid_line(world, entry, names, place, other):
    return f"Paid {entry.data['amount']} silver ({entry.data['reason']})."
```
`narrate/grammar/roads.toml`:
```toml
[symbols]
roadside = ["Dust hangs over the road.", "The trees crowd close here.", "No one else is in sight.", "A crow calls from a dead branch.", "The wind drops."]
growl = ["A low growl rolls across the road.", "Its eyes catch the light.", "It circles, head low.", "Hackles rise along its back."]
bravado = ["They grin without warmth.", "Their hand rests on their weapon.", "They spit in the dust.", "They take their time looking you over."]
coins = ["Coins change hands.", "Silver clinks from purse to palm.", "The coins are counted twice.", "A few pieces of silver lighter, you go on."]
grudge = ["The street goes quiet.", "Heads turn.", "Someone mutters that this was bound to happen.", "A child is pulled indoors."]

["encounter.bandit"]
colour = "default"
lines = ["#roadside# #bravado#", "#bravado# #roadside#"]

["encounter.beast"]
colour = "default"
lines = ["#roadside# #growl#", "#growl# #roadside#"]

["encounter.wanderer"]
colour = "default"
lines = ["#roadside# #bravado#", "#bravado# #roadside#"]

[encounter_resolved]
colour = "default"
lines = ["#roadside#", "You go on your way. #roadside#"]

[challenge_issued]
colour = "npc"
lines = ["{npc} will not let it go. #grudge#", "#grudge# {npc} squares up to you."]

[declined_challenge]
colour = "npc"
lines = ["{npc} laughs at you. #grudge#", "#grudge# {npc} turns away in disgust."]

[paid]
colour = "default"
lines = ["#coins#", "#coins# The deal is done."]
```
`.patches/2b_task7.py`:
```python
import pathlib


def patch(f, pairs):
    p = pathlib.Path(f)
    t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (f, a[:70])
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8", newline="\n")


patch("engine/game.py", [
    ("from engine.fight import FightMixin\n", "from engine.fight import FightMixin\nfrom engine.roads import RoadsMixin\n"),
    ("class Game(FightMixin, GameHooks):", "class Game(RoadsMixin, FightMixin, GameHooks):"),
])
patch("narrate/outcomes.py", [
    ("import narrate.combat_text  # noqa: E402,F401\n",
     "import narrate.combat_text  # noqa: E402,F401\nimport narrate.road_text  # noqa: E402,F401\n"),
])
print("task 7 patched")
```

- [ ] **Step 4: Run** `python .patches/2b_task7.py`, then the tests → `tests/test_roads.py` PASS (10 passed), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: road encounters and grudge challenges" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 8: Teachers, manuals, and the manual that lies

**Files:**
- Create: `systems/learning.py`, `engine/dealings.py`, `narrate/learning_text.py`, `narrate/grammar/learning.toml`, `.patches/2b_task8.py`
- Modify via the patch script:
  - `engine/game.py` (the class line)
  - `narrate/outcomes.py` (the import)
  - `systems/techniques.py` (`set_known_completeness`)
  - `systems/cultivation.py` (reveal a manual's flaw through deviation)
  - `narrate/brief.py` (the reveal line)
- Test: `tests/test_learning.py`

**Interfaces:**
- Consumes: Tasks 1, 4, 6 (`ensure_npc_arts`, `manuals_of`, `payment_events`, `transfer_events`, `_start_duel`, the `_after_duel` hook)
- Produces:
  - In `systems/learning.py`:
    - Constants: `GOODS_CHANCE`, `STUDY_DAYS = 14`
    - Teaching: `lesson_price(known) -> int` (`20 × grade²`), `teachable_arts(world, npc, player)`, `can_ask_to_learn(world, npc, player) -> bool` (needs a previous conversation and a teacher), `lesson_events(world, player, teacher, place, technique_id, via)`, where `via` is `"silver"` or `"test"`
    - Manuals: `ensure_goods(world, npc) -> list[Manual]`, `purchase_events(world, player, seller, place, item_id)`, `unstudied(world, player) -> list[Manual]`, `study_events(world, player, place, item_id)`
  - Event kinds: `learned` with data `{technique, name, via, price}`, and `studied_manual` with data `{item, technique, name, days}`. **No completeness value is ever put in event data.**
  - `set_known_completeness(world, person_id, technique_id)`
  - Deviation events gain `reveal`. It is a technique id when the cause is a lying manual. The effect then sets `known_completeness` to the truth, and the outcome adds "You realise the manual was never complete."
  - `DealingsMixin` adds:
    - Conversation extras: `Ask to learn an art...` (`learn_menu`) and `Browse their manuals...` (`browse`)
    - Handlers: `learn_paid`, `learn_test`, `buy`, `study`
    - Practise-menu extras: `Study the X manual (2 weeks)`
    - A test spar that passes teaches the art, via `_after_duel`.

- [ ] **Step 1: Write the failing test** — `tests/test_learning.py`
```python
import pytest

import systems.cultivation as cultivation
import systems.duel as duel
import systems.learning as learning
from engine.game import Action, Game
from engine.sheet import sheet_lines
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.items import create_manual, manuals_of
from systems.purse import silver_of
from systems.techniques import create_technique, generate, known_arts, martial_arts, teach
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "merchant"))
    g.start()
    yield g
    g.close()


def person(game, occupation, name):
    data = {"occupation": occupation, "traits": ["kind", "honest"], "realm": "mortal", "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", name, data, seed_path=f"test:{name}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def acquainted(game, npc):
    game.perform(Action("talk", npc))
    game.perform(Action("farewell"))
    return game.perform(Action("talk", npc))


def teacher(game, monkeypatch):
    monkeypatch.setitem(duel.TEACHER_CHANCE, "wandering swordsman", 1.0)
    return person(game, "wandering swordsman", "Master Seo")


def test_a_teacher_offers_lessons_to_acquaintances(game, monkeypatch):
    master = teacher(game, monkeypatch)
    first = game.perform(Action("talk", master))
    assert Action("learn_menu") not in [c.action for c in first.choices]
    game.perform(Action("farewell"))
    turn = acquainted(game, master)
    assert Action("learn_menu") in [c.action for c in turn.choices]
    menu = game.perform(Action("learn_menu"))
    assert menu.choices[0].action.verb == "learn_paid" and menu.choices[1].action.verb == "learn_test"
    assert menu.choices[-1].action == Action("talk_menu")


def test_paying_for_a_lesson(game, monkeypatch):
    master = teacher(game, monkeypatch)
    acquainted(game, master)
    art = learning.teachable_arts(game.world, master, game.player.id)[0]
    price = learning.lesson_price(art)
    before = silver_of(game.world, game.player.id)
    game.perform(Action("learn_paid", art.technique.id))
    known = next(a for a in known_arts(game.world, game.player.id) if a.technique.id == art.technique.id)
    assert known.source == "taught" and known.teacher == master
    assert silver_of(game.world, game.player.id) == before - price


def test_no_silver_no_lesson(game, monkeypatch):
    master = teacher(game, monkeypatch)
    acquainted(game, master)
    art = learning.teachable_arts(game.world, master, game.player.id)[0]
    game.world.update_data(game.player.id, silver=0)
    turn = game.perform(Action("learn_paid", art.technique.id))
    assert turn.lines[-1] == ("You cannot afford that lesson.", "system")
    assert art.technique.id not in {a.technique.id for a in known_arts(game.world, game.player.id)}


def test_passing_a_test_spar_teaches_the_art(game, monkeypatch):
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years = 3, 20.0
    save_body(game.world, game.player.id, body)
    master = teacher(game, monkeypatch)
    acquainted(game, master)
    art = learning.teachable_arts(game.world, master, game.player.id)[0]
    game.perform(Action("learn_test", art.technique.id))
    assert game.combat is not None and game.combat.mode == "test"
    for _ in range(3):
        game.perform(Action("intent", "guard"))
    assert game.combat is None
    assert art.technique.id in {a.technique.id for a in known_arts(game.world, game.player.id)}


def test_buying_and_studying_a_manual(game, monkeypatch):
    monkeypatch.setitem(learning.GOODS_CHANCE, "merchant", 1.0)
    seller = person(game, "merchant", "Trader Oh")
    turn = game.perform(Action("talk", seller))
    assert Action("browse") in [c.action for c in turn.choices]
    goods = game.perform(Action("browse"))
    item = goods.choices[0].action.target
    game.perform(Action("buy", item))
    assert item in [m.item.id for m in manuals_of(game.world, game.player.id)]
    game.perform(Action("farewell"))
    start = game.world.time
    practise = game.perform(Action("practise_menu"))
    study = next(c.action for c in practise.choices if c.action.verb == "study")
    game.perform(study)
    manual = next(m for m in manuals_of(game.world, game.player.id) if m.item.id == item)
    known = next(a for a in known_arts(game.world, game.player.id) if a.technique.id == manual.technique.id)
    assert known.source == "manual" and known.completeness == manual.true_completeness and known.known_completeness == 1.0
    assert game.world.time == start + 14 * 4


def test_a_lying_manual_is_found_out_only_by_deviation(game):
    name, art = generate(rng_for(3, "flawed"), "martial", form="palm")
    technique = create_technique(game.world, name, dict(art, route=["Lung", "Heart"], element="neutral"))
    item = create_manual(game.world, game.player.id, technique, 0.4)
    commit(game.world, learning.study_events(game.world, game.player.id, game.place.id, item))
    teach(game.world, game.player.id, technique, completeness=0.4, known_completeness=1.0, source="manual", mastery=0.4)
    assert "completeness 100%" in "\n".join(t for t, _ in sheet_lines(game.world, game.player.id))
    body = load_body(game.world, game.player.id)
    body.deviation = 99.0
    for m in ("Lung", "Heart"):
        body.meridians[m].state = "open"
    save_body(game.world, game.player.id, body)
    turn = game.perform(Action("practise", technique))
    text = " ".join(t for t, _ in turn.lines)
    assert "manual" in text and "never complete" in text
    known = next(a for a in martial_arts(game.world, game.player.id) if a.technique.id == technique)
    assert known.known_completeness == 0.4
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: systems.learning`)

- [ ] **Step 3: Implement**

`systems/learning.py`:
```python
"""Teachers and manuals (phase 2 spec §10).

A teacher's art is learned whole. A manual teaches only what it truly
contains, while claiming more; the claim is what its reader believes until
practice at the true limit ends in a deviation that reveals the lie.
"""

from systems.duel import ensure_npc_arts
from systems.items import create_manual, manual_price, manuals_of, transfer_events
from systems.purse import payment_events
from systems.talk import conversations_with
from systems.techniques import create_technique, generate, known_arts, teach
from systems.time import advance
from world.events import Event, effect
from world.seed import rng_for

GOODS_CHANCE = {"merchant": 0.4, "scholar": 0.4}
STUDY_DAYS = 14


def lesson_price(known) -> int:
    return 20 * known.technique.data["grade"] ** 2


def teachable_arts(world, npc_id: int, player_id: int) -> list:
    arts = ensure_npc_arts(world, npc_id)
    if not world.entity(npc_id).data.get("teacher"):
        return []
    mine = {a.technique.id for a in known_arts(world, player_id)}
    return [a for a in arts if a.technique.id not in mine]


def can_ask_to_learn(world, npc_id: int, player_id: int) -> bool:
    return len(conversations_with(world, npc_id, player_id)) >= 2 and bool(teachable_arts(world, npc_id, player_id))


def lesson_events(world, player: int, teacher: int, place: int, technique_id: int, via: str) -> list[Event]:
    art = next((a for a in teachable_arts(world, teacher, player) if a.technique.id == technique_id), None)
    if art is None:
        return []
    price = lesson_price(art) if via == "silver" else 0
    events = payment_events(player, teacher, place, price, "lesson") if price else []
    return events + [Event("learned", (player, teacher), place,
                           {"technique": technique_id, "name": art.name, "via": via, "price": price})]


@effect("learned")
def _learned(world, event: Event) -> None:
    player, teacher = event.actors
    teach(world, player, event.data["technique"], source="taught", teacher=teacher)


def ensure_goods(world, npc_id: int) -> list:
    npc = world.entity(npc_id)
    if npc.data.get("goods_ready"):
        return manuals_of(world, npc_id)
    key = npc.seed_path or f"entity:{npc_id}"
    rng = rng_for(world.world_seed, f"{key}/goods")
    with world.transaction():
        if rng.random() < GOODS_CHANCE.get(npc.data.get("occupation"), 0.0):
            for _ in range(rng.randint(1, 2)):
                name, art = generate(rng, "martial", grade=rng.randint(1, 2))
                create_manual(world, npc_id, create_technique(world, name, art), rng.uniform(0.4, 1.0))
        world.update_data(npc_id, goods_ready=True)
    return manuals_of(world, npc_id)


def purchase_events(world, player: int, seller: int, place: int, item_id: int) -> list[Event]:
    manual = next((m for m in manuals_of(world, seller) if m.item.id == item_id), None)
    if manual is None:
        return []
    return (payment_events(player, seller, place, manual_price(manual), "manual")
            + transfer_events(seller, player, place, [item_id], "bought"))


def unstudied(world, player: int) -> list:
    known = {a.technique.id for a in known_arts(world, player)}
    return [m for m in manuals_of(world, player) if m.technique.id not in known]


def study_events(world, player: int, place: int, item_id: int) -> list[Event]:
    manual = next((m for m in unstudied(world, player) if m.item.id == item_id), None)
    if manual is None:
        return []
    data = {"item": item_id, "technique": manual.technique.id, "name": manual.technique.name, "days": STUDY_DAYS}
    return [Event("studied_manual", (player,), place, data)]


@effect("studied_manual")
def _studied(world, event: Event) -> None:
    player, data = event.actors[0], event.data
    advance(world, data["days"] * 4)
    item = world.entity(data["item"])
    teach(world, player, data["technique"], completeness=item.data["true_completeness"],
          known_completeness=item.data["claimed_completeness"], source="manual")
```
`engine/dealings.py`:
```python
"""Learning from teachers, trading and studying manuals, in the engine (phase 2 spec §10)."""

import systems.learning as learning
from engine.actions import Action, Choice
from systems.items import manual_price, manuals_of
from systems.purse import silver_of


class DealingsMixin:
    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if npc.data.get("beast"):
            return extras
        if learning.can_ask_to_learn(self.world, npc.id, self.player.id):
            extras.append(Choice("Ask to learn an art...", Action("learn_menu")))
        if learning.ensure_goods(self.world, npc.id):
            extras.append(Choice("Browse their manuals...", Action("browse")))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None:
            options["learn_menu"] = (self._lesson_choices(), Action("talk_menu"))
            options["browse"] = (self._goods_choices(), Action("talk_menu"))
        return options

    def _practise_extras(self, body) -> list:
        extras = super()._practise_extras(body)
        return extras + [Choice(f"Study the {m.name} (2 weeks)", Action("study", m.item.id))
                         for m in learning.unstudied(self.world, self.player.id)]

    def _lesson_choices(self) -> list[Choice]:
        choices = []
        for art in learning.teachable_arts(self.world, self.focus, self.player.id):
            price = learning.lesson_price(art)
            choices.append(Choice(f"Pay {price} silver to learn the {art.name}", Action("learn_paid", art.technique.id)))
            choices.append(Choice(f"Learn the {art.name} by passing a test spar", Action("learn_test", art.technique.id)))
        return choices

    def _goods_choices(self) -> list[Choice]:
        return [Choice(f"Buy the {m.name} ({manual_price(m)} silver)", Action("buy", m.item.id))
                for m in manuals_of(self.world, self.focus)]

    def _do_learn_menu(self, _target):
        if self.focus is None or not learning.can_ask_to_learn(self.world, self.focus, self.player.id):
            return self._turn([("No one here will teach you.", "system")])
        self.submenu = "learn_menu"
        return self._turn([("What would you learn?", "system")])

    def _do_browse(self, _target):
        if self.focus is None or not learning.ensure_goods(self.world, self.focus):
            return self._turn([("No one here is selling manuals.", "system")])
        self.submenu = "browse"
        return self._turn([("Which manual catches your eye?", "system")])

    def _do_learn_paid(self, technique_id):
        if self.focus is None:
            return self._turn([("Learn from whom?", "system")])
        events = learning.lesson_events(self.world, self.player.id, self.focus, self.place.id, technique_id, "silver")
        if not events:
            return self._turn([("They cannot teach you that.", "system")])
        if events[0].kind == "paid" and silver_of(self.world, self.player.id) < events[0].data["amount"]:
            return self._turn([("You cannot afford that lesson.", "system")])
        return self._turn(self._commit(events))

    def _do_learn_test(self, technique_id):
        if self.focus is None:
            return self._turn([("Learn from whom?", "system")])
        teachable = {a.technique.id for a in learning.teachable_arts(self.world, self.focus, self.player.id)}
        if technique_id not in teachable:
            return self._turn([("They cannot teach you that.", "system")])
        teacher = self.focus
        return self._turn(self._start_duel(teacher, "test", purpose={"teach": technique_id, "teacher": teacher}))

    def _do_buy(self, item_id):
        if self.focus is None:
            return self._turn([("Buy from whom?", "system")])
        events = learning.purchase_events(self.world, self.player.id, self.focus, self.place.id, item_id)
        if not events:
            return self._turn([("They don't have that.", "system")])
        if silver_of(self.world, self.player.id) < events[0].data["amount"]:
            return self._turn([("You cannot afford it.", "system")])
        return self._turn(self._commit(events))

    def _do_study(self, item_id):
        if busy := self._busy():
            return busy
        events = learning.study_events(self.world, self.player.id, self.place.id, item_id)
        return self._cultivated(events, "You have no such manual to study.")

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        if data["mode"] == "test" and purpose.get("teach") and data["result"] == "passed":
            events = learning.lesson_events(self.world, self.player.id, purpose["teacher"], self.place.id, purpose["teach"], "test")
            if events:
                lines += self._commit(events)
        return lines
```
`narrate/learning_text.py`:
```python
"""What the player is told about lessons, purchases and study. Never a true completeness."""

from narrate.outcomes import cap, outcome, summary


@outcome("learned", body_facts=False)
def _learned(world, event):
    teacher = world.entity(event.actors[1]).name
    how = " after passing their test" if event.data["via"] == "test" else ""
    return [f"{cap(teacher)} teaches you the {event.data['name']}{how}."], {"art": event.data["name"]}


@outcome("handed_over", body_facts=False)
def _handed(world, event):
    items = [world.entity(i).name for i in event.data["items"]]
    if event.data["reason"] == "bought":
        return [f"You buy the {', '.join(items)}."], {}
    return [f"The {', '.join(items)} changes hands."], {}


@outcome("studied_manual")
def _studied(world, event):
    return [f"You study the {event.data['name']} manual for two weeks.",
            "Its pages claim to hold the whole art."], {"art": event.data["name"], "days": "two weeks"}


@summary("learned")
def _learned_line(world, entry, names, place, other):
    return f"Learned the {entry.data['name']} from {other}."


@summary("handed_over")
def _handed_line(world, entry, names, place, other):
    return "Bought a manual." if entry.data["reason"] == "bought" else "Items changed hands."


@summary("studied_manual")
def _studied_line(world, entry, names, place, other):
    return f"Studied the {entry.data['name']} manual."
```
`narrate/grammar/learning.toml`:
```toml
[symbols]
lesson = ["They correct your stance with two fingers.", "They make you repeat the first form a hundred times.", "They speak little and demonstrate much.", "By the end your arms are shaking.", "They nod, once, when you finally get it right."]
bargain = ["The price is argued, then paid.", "They wrap it in oilcloth for you.", "They wet a thumb and count the silver.", "They insist it is a rare copy."]
pages = ["The ink is faded in places.", "Someone has scribbled notes in the margins.", "The diagrams are exquisite.", "The binding smells of camphor.", "Half the characters are in an old style."]

[learned]
colour = "npc"
lines = ["#lesson#", "{npc} takes you through the art. #lesson#"]

[handed_over]
colour = "default"
lines = ["#bargain#", "#bargain# The manual is yours."]

[studied_manual]
colour = "default"
lines = ["You pore over the manual for {days}. #pages#", "#pages# You read until the forms swim before your eyes."]
```
`.patches/2b_task8.py`:
```python
import pathlib


def patch(f, pairs):
    p = pathlib.Path(f)
    t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (f, a[:70])
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8", newline="\n")


patch("engine/game.py", [
    ("from engine.fight import FightMixin\n", "from engine.dealings import DealingsMixin\nfrom engine.fight import FightMixin\n"),
    ("class Game(RoadsMixin, FightMixin, GameHooks):", "class Game(DealingsMixin, RoadsMixin, FightMixin, GameHooks):"),
])
patch("narrate/outcomes.py", [
    ("import narrate.road_text  # noqa: E402,F401\n",
     "import narrate.road_text  # noqa: E402,F401\nimport narrate.learning_text  # noqa: E402,F401\n"),
])
tech = pathlib.Path("systems/techniques.py")
tech.write_text(tech.read_text(encoding="utf-8") + '''

def set_known_completeness(world: World, person_id: int, technique_id: int) -> None:
    """The knower learns the truth: belief becomes the real completeness."""
    for tech_id, mastery, data in world.relations_from(person_id, "knows"):
        if tech_id == technique_id:
            truth = {**data, "known_completeness": data.get("completeness", 1.0)}
            world.relate(person_id, technique_id, "knows", value=mastery, data=truth)
            return
''', encoding="utf-8", newline="\n")
patch("systems/cultivation.py", [
    ("from systems.techniques import compatibility, grade_mult, heart_method, known_arts, mastery_stage, practise_gain, set_mastery",
     "from systems.techniques import compatibility, grade_mult, heart_method, known_arts, mastery_stage, practise_gain, set_known_completeness, set_mastery"),
    ("def _deviation_event(world, pid: int, place: int, end, added: float, route, cause: str) -> list[Event]:",
     "def _deviation_event(world, pid: int, place: int, end, added: float, route, cause: str, reveal: int | None = None) -> list[Event]:"),
    ('''            "discovered": _discovers(end, "deviation")}
    return [Event("deviation", (pid,), place, data)]''',
     '''            "discovered": _discovers(end, "deviation"), "reveal": reveal}
    return [Event("deviation", (pid,), place, data)]'''),
    ('''    cause = (f"forcing the {known.name} beyond what it can give" if at_cap
             else f"practising the {known.name} against your body's grain")''',
     '''    manual_lie = at_cap and known.source == "manual" and known.known_completeness > known.completeness + 1e-9
    if manual_lie:
        cause = f"following a manual of the {known.name} whose instructions are wrong"
    elif at_cap:
        cause = f"forcing the {known.name} beyond what it can give"
    else:
        cause = f"practising the {known.name} against your body's grain"'''),
    ('''    return [Event("practised", (pid,), place, data)] + _deviation_event(world, pid, place, end, deviation, art["route"], cause)''',
     '''    reveal = technique_id if manual_lie else None
    return [Event("practised", (pid,), place, data)] + _deviation_event(world, pid, place, end, deviation, art["route"], cause, reveal)'''),
    ('''    body.deviation = float(DEVIATION_AFTER)''',
     '''    body.deviation = float(DEVIATION_AFTER)
    if data.get("reveal"):
        set_known_completeness(world, pid, data["reveal"])'''),
])
patch("narrate/brief.py", [
    ('''        out.append(f"Your qi deviated: {d['cause']}.")''',
     '''        out.append(f"Your qi deviated: {d['cause']}.")
        if d.get("reveal"):
            out.append("You realise the manual was never complete.")'''),
])
print("task 8 patched")
```

- [ ] **Step 4: Run** `python .patches/2b_task8.py`, then the tests → `tests/test_learning.py` PASS (6 passed), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: teachers, manuals, and the lying manual revealed by deviation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 9: Inventing an art from fragments

**Files:**
- Create: `systems/inventing.py`, `engine/inventing.py`, `narrate/invent_text.py`, `narrate/grammar/inventing.toml`, `.patches/2b_task9.py`
- Modify via the patch script: `engine/game.py` (the class line), `narrate/outcomes.py` (the import)
- Test: `tests/test_inventing.py`

**Interfaces:**
- Consumes: the fragments stored in `person.data["fragments"]` (Task 4); `technique_name`, `STANCES`, `INTENTS`, `create_technique`, `teach` (techniques)
- Produces:
  - In `systems/inventing.py`:
    - Constants: `MIN_FRAGMENTS = 3`, `MIN_INSIGHT = 20.0`, `CREATE_DAYS = 7`
    - `fragments_of(world, pid)`, `creatable_forms(world, pid) -> list[str]`, `why_not_create(world, pid) -> str | None`
    - `create_events(world, pid, place, form) -> list[Event]`, producing kind `created_technique` with data `{name, technique_data, used, days}`
    - The effect creates the technique and teaches it at mastery 0.1 with source `created`. The used fragments are consumed.
  - `InventingMixin`: `Create a new art...` in the practise menu leads to the `create_menu` submenu, which offers `create_art(form)`.

- [ ] **Step 1: Write the failing test** — `tests/test_inventing.py`
```python
import pytest

import systems.inventing as inventing
from engine.game import Action, Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.techniques import martial_arts

FRAGMENTS = [
    {"technique": "Azure Crane Palm", "form": "palm", "element": "water", "segment": ["Lung", "Heart"]},
    {"technique": "Iron Tiger Fist", "form": "fist", "element": "metal", "segment": ["Stomach", "Spleen"]},
    {"technique": "Silent Moon Palm", "form": "palm", "element": "water", "segment": ["Kidney", "Liver"]},
]


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def ready(game, insight=45.0):
    body = load_body(game.world, game.player.id)
    body.insight, body.realm, body.energy_years = insight, 1, 1.0
    save_body(game.world, game.player.id, body)
    game.world.update_data(game.player.id, fragments=list(FRAGMENTS))


def test_you_need_fragments_and_insight(game):
    assert "fragments" in inventing.why_not_create(game.world, game.player.id)
    ready(game, insight=5.0)
    assert "insight" in inventing.why_not_create(game.world, game.player.id)
    ready(game)
    assert inventing.why_not_create(game.world, game.player.id) is None
    assert inventing.creatable_forms(game.world, game.player.id) == ["fist", "palm"]


def test_creating_a_palm_art(game):
    ready(game)
    before = {a.technique.id for a in martial_arts(game.world, game.player.id)}
    start = game.world.time
    practise = game.perform(Action("practise_menu"))
    assert Action("create_menu") in [c.action for c in practise.choices]
    menu = game.perform(Action("create_menu"))
    palm = next(c.action for c in menu.choices if c.action == Action("create_art", "palm"))
    turn = game.perform(palm)
    new = [a for a in martial_arts(game.world, game.player.id) if a.technique.id not in before]
    assert len(new) == 1
    art = new[0]
    assert art.form == "palm" and art.source == "created" and art.mastery == pytest.approx(0.1)
    assert art.technique.data["creator"] == game.player.id and art.technique.data["element"] == "water"
    assert set(art.technique.data["route"]) <= {"Lung", "Heart", "Stomach", "Spleen", "Kidney", "Liver"}
    assert art.technique.data["grade"] == 2  # min(realm 1 + 1, 1 + 45 // 40)
    assert game.world.entity(game.player.id).data["fragments"] == []
    assert game.world.time == start + 7 * 4
    assert any("create" in t.lower() for t, _ in turn.lines)


def test_menus_hide_creation_until_ready(game):
    practise = game.perform(Action("practise_menu"))
    assert Action("create_menu") not in [c.action for c in practise.choices]
    assert game.perform(Action("create_menu")).lines[-1][1] == "system"
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: systems.inventing`)

- [ ] **Step 3: Implement**

`systems/inventing.py`:
```python
"""Turning glimpsed fragments into an art of your own (phase 2 spec §10).

The route is stitched from the fragments' meridian segments through your own
unsevered meridians; the grade is capped by both realm and insight.
"""

from collections import Counter

from systems.bodies import load_body
from systems.techniques import FORMS, INTENTS, STANCES, create_technique, teach, technique_name
from systems.time import advance
from world.body import REGULAR
from world.events import Event, effect
from world.seed import rng_for

MIN_FRAGMENTS = 3
MIN_INSIGHT = 20.0
CREATE_DAYS = 7


def fragments_of(world, pid: int) -> list[dict]:
    return list(world.entity(pid).data.get("fragments", []))


def creatable_forms(world, pid: int) -> list[str]:
    return sorted({f["form"] for f in fragments_of(world, pid) if f["form"] in FORMS})


def why_not_create(world, pid: int) -> str | None:
    fragments = fragments_of(world, pid)
    if len(fragments) < MIN_FRAGMENTS:
        return f"You need at least {MIN_FRAGMENTS} fragments of other arts; you have {len(fragments)}."
    if load_body(world, pid).insight < MIN_INSIGHT:
        return "You need deeper martial insight before you can create an art."
    if not creatable_forms(world, pid):
        return "Your fragments do not suggest any form you could build on."
    return None


def create_events(world, pid: int, place: int, form: str) -> list[Event]:
    if why_not_create(world, pid) or form not in creatable_forms(world, pid):
        return []
    body = load_body(world, pid)
    fragments = fragments_of(world, pid)
    rng = rng_for(world.world_seed, f"invent:{pid}:{world.time}")
    chosen = ([f for f in fragments if f["form"] == form] + [f for f in fragments if f["form"] != form])[:MIN_FRAGMENTS]
    route: list[str] = []
    for fragment in chosen:
        for meridian in fragment["segment"]:
            if meridian not in route and body.meridians[meridian].state != "severed":
                route.append(meridian)
    spare = [m for m in REGULAR if body.meridians[m].state == "open" and m not in route]
    while len(route) < 2 and spare:
        route.append(spare.pop(rng.randrange(len(spare))))
    favours = rng.choice(INTENTS)
    data = {
        "category": "martial", "form": form, "stance": {"name": rng.choice(STANCES[favours]), "favours": favours},
        "route": route[:6], "element": Counter(f["element"] for f in chosen).most_common(1)[0][0],
        "grade": max(1, min(6, body.realm + 1, 1 + int(body.insight // 40))),
        "power": round(rng.uniform(0.8, 1.3), 2), "speed": round(rng.uniform(0.8, 1.3), 2),
        "defence": round(rng.uniform(0.8, 1.3), 2), "creator": pid, "origin": "created",
    }
    event = {"name": technique_name(rng, form), "technique_data": data, "used": chosen, "days": CREATE_DAYS}
    return [Event("created_technique", (pid,), place, event)]


@effect("created_technique")
def _created(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    advance(world, data["days"] * 4)
    technique = create_technique(world, data["name"], data["technique_data"])
    teach(world, pid, technique, source="created", mastery=0.1)
    remaining = fragments_of(world, pid)
    for used in data["used"]:
        if used in remaining:
            remaining.remove(used)
    world.update_data(pid, fragments=remaining)
```
`engine/inventing.py`:
```python
"""Creating an art from fragments, in the engine."""

import systems.inventing as inventing
from engine.actions import Action, Choice


class InventingMixin:
    def _practise_extras(self, body) -> list:
        extras = super()._practise_extras(body)
        if inventing.why_not_create(self.world, self.player.id) is None:
            extras.append(Choice("Create a new art...", Action("create_menu")))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is None:
            forms = inventing.creatable_forms(self.world, self.player.id)
            options["create_menu"] = (
                [Choice(f"Create a {form} art (a week of seclusion)", Action("create_art", form)) for form in forms],
                Action("practise_menu"),
            )
        return options

    def _do_create_menu(self, _target):
        if busy := self._busy():
            return busy
        reason = inventing.why_not_create(self.world, self.player.id)
        if reason:
            return self._turn([(reason, "system")])
        self.submenu = "create_menu"
        return self._turn([("What form will your art take?", "system")])

    def _do_create_art(self, form):
        if busy := self._busy():
            return busy
        events = inventing.create_events(self.world, self.player.id, self.place.id, form)
        return self._cultivated(events, "You cannot create that art now.")
```
`narrate/invent_text.py`:
```python
"""What the player is told when they create an art."""

from narrate.outcomes import outcome, summary


@outcome("created_technique")
def _created(world, event):
    d = event.data
    sources = ", ".join(sorted({f["technique"] for f in d["used"]}))
    return [f"You create a new art: the {d['name']}!",
            f"It grew from what you glimpsed of the {sources}.",
            "No one else in the world knows it."], {"art": d["name"]}


@summary("created_technique")
def _created_line(world, entry, names, place, other):
    return f"Created the {entry.data['name']}."
```
`narrate/grammar/inventing.toml`:
```toml
[symbols]
insight = ["The pieces click together all at once.", "You see how the fragments want to flow.", "For a week you barely eat.", "You draw the route on the wall in charcoal.", "The last form comes to you in a dream."]
proof = ["When you finally move, the art moves with you.", "It is rough, but it is yours.", "The air hums as you run it through once.", "You laugh aloud, alone."]

[created_technique]
colour = "gold"
lines = ["#insight# #proof#", "#proof# #insight#"]
```
`.patches/2b_task9.py`:
```python
import pathlib


def patch(f, pairs):
    p = pathlib.Path(f)
    t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (f, a[:70])
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8", newline="\n")


patch("engine/game.py", [
    ("from engine.hooks import GameHooks\n", "from engine.hooks import GameHooks\nfrom engine.inventing import InventingMixin\n"),
    ("class Game(DealingsMixin, RoadsMixin, FightMixin, GameHooks):",
     "class Game(InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks):"),
])
patch("narrate/outcomes.py", [
    ("import narrate.learning_text  # noqa: E402,F401\n",
     "import narrate.learning_text  # noqa: E402,F401\nimport narrate.invent_text  # noqa: E402,F401\n"),
])
print("task 9 patched")
```

- [ ] **Step 4: Run** `python .patches/2b_task9.py`, then the tests → `tests/test_inventing.py` PASS (3 passed), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: invent your own art from fragments" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 10: Rules for fights, items and purses; fuzzing; docs

**Files:**
- Create: `.patches/2b_task10.py`
- Rewrite: `tests/test_fuzz.py`
- Modify via the patch script: `debug/invariants.py`, `docs/debugging.md`, and the phase 2 spec (an implementation-notes appendix)
- Test: `tests/test_invariants_2b.py`

**Interfaces:**
- Consumes: everything above
- Produces:
  - New rule checks in `check_world`:
    - every manual has exactly one owner and a real technique, and claims no less than it holds;
    - `known_completeness ≥ completeness`;
    - fragment lists are well-formed and hold at most 12.
  - New rule checks in `check_turn`:
    - a live duel has real participants, harm between 0 and 100, and a valid stage;
    - an encounter has a real person;
    - no brief detail key contains `true`.

- [ ] **Step 1: Write the failing test** — `tests/test_invariants_2b.py`
```python
import pytest

import systems.duel as duel
from debug.invariants import check_turn, check_world
from engine.game import Action, Game, Turn
from systems.creation import CreationChoice
from systems.items import create_manual
from systems.techniques import create_technique, generate, martial_arts
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def technique(game):
    name, art = generate(rng_for(2, "x"), "martial", form="fist")
    return create_technique(game.world, name, art)


def text(problems):
    return " | ".join(problems)


def test_manual_rules(game):
    item = create_manual(game.world, game.player.id, technique(game), 0.9, claimed=0.5)
    assert "claims less" in text(check_world(game.world))
    game.world.unrelate(game.player.id, "owns", item)
    assert "owners" in text(check_world(game.world))


def test_belief_never_below_truth(game):
    art = martial_arts(game.world, game.player.id)[0]
    game.world.relate(game.player.id, art.technique.id, "knows", value=0.05,
                      data={"completeness": 1.0, "known_completeness": 0.5, "source": "x"})
    assert "believes" in text(check_world(game.world))


def test_fragment_rules(game):
    game.world.update_data(game.player.id, fragments=[{"form": "palm"}] * 13)
    problems = text(check_world(game.world))
    assert "fragments" in problems


def test_live_duel_rules(game):
    npc = game.world.add_entity("person", "Foe", {"occupation": "bandit", "traits": ["proud"], "realm": "mortal",
                                                  "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(npc, game.place.id, "located_in")
    game.perform(Action("talk", npc))
    game.perform(Action("challenge", npc))
    assert check_turn(game, game.look(), []) == []
    game.combat.harm["opponent"] = 250.0
    game.combat.stage = "sulking"
    problems = text(check_turn(game, Turn([], [], {"type": "scene"}, "s"), []))
    assert "harm" in problems and "stage" in problems
```
`tests/test_fuzz.py` (replaces the file):
```python
"""Random play across several worlds. Any crash or invariant violation fails the run.

This is the standing bug-catcher: new systems get exercised here for free.
"""

import random

import pytest

import systems.encounters as encounters
from app import App
from config import Config

TYPED = ["look", "journal", "help", "talk li", "talk zzz", "go north", "go south", "ask work",
         "ask town", "bye", "²", "", "   ", "x" * 300, "go", "talk", "back", "9", "0",
         "cultivate", "meditate week", "meditate month", "meditate season", "rest", "breakthrough",
         "practise", "open governing", "open conception",
         "challenge", "spar", "strike", "feint", "guard", "probe", "flee", "yield", "spare", "rob", "cripple"]
FIGHTING = ["strike", "feint", "guard", "probe", "strike", "guard", "flee", "yield", "spare", "rob", "cripple", "1", "2", "3", "4"]
HOTKEYS = ["f2", "f3", "f4", "f12", "page up", "page down"]


@pytest.mark.parametrize("seed", [1, 7, 42, 1234])
def test_random_play_is_clean(tmp_path, seed):
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Fuzz{seed}", world_seed=seed)
    for step in range(250):
        roll = rng.random()
        if roll < 0.72 and app.choices:
            n = rng.randint(1, len(app.choices))
            app.handle_key(str(n), str(n))
        elif roll < 0.9:
            for ch in rng.choice(TYPED):
                app.handle_key(ch, ch)
            app.handle_key("return", "\r")
        elif roll < 0.95:
            app.handle_key(rng.choice(HOTKEYS), "")
        else:
            app.handle_key("escape", "\x1b")
            app.handle_key("escape", "\x1b")
            if app.state == "title":
                app.handle_key("return", "\r")  # Continue
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()


def test_years_of_cultivation_stay_clean(tmp_path):
    rng = random.Random(99)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Hermit", world_seed=99)
    for _ in range(150):
        app.submit(rng.choice(["meditate season", "meditate month", "rest", "breakthrough", "open governing",
                               "open conception", "cultivate", "1", "2", "3"]))
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    assert app.game.world.time > 4 * 360
    app.shutdown()


@pytest.mark.parametrize("seed", [3, 21])
def test_a_violent_life_stays_clean(tmp_path, seed, monkeypatch):
    """Roads full of bandits and beasts, and fights with everyone in town."""
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 3.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Brawler{seed}", world_seed=seed)
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2"]))
        elif rng.random() < 0.35 and app.choices:
            app.submit(str(rng.randint(1, len(app.choices))))
        else:
            app.submit(rng.choice(["challenge", "go north", "go east", "go south", "go west", "1", "look", "rest"]))
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()
```

- [ ] **Step 2: Run to verify it fails** → `tests/test_invariants_2b.py` FAILS (the rules don't exist yet). The fuzz tests are regression coverage. **If they fail, the failures are real bugs.** Fix each in its owning module with a failing test first (superpowers:systematic-debugging), never by loosening a rule.

- [ ] **Step 3: Implement** — `.patches/2b_task10.py`
```python
import pathlib


def patch(f, pairs):
    p = pathlib.Path(f)
    t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (f, a[:70])
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8", newline="\n")


patch("debug/invariants.py", [
    ("""    times = world.recent_chronicle_times()""",
     """    problems += check_items(world)
    times = world.recent_chronicle_times()"""),
    ("""        if person.data.get("silver", 0) < 0:""",
     """        problems += check_fragments(person)
        if person.data.get("silver", 0) < 0:"""),
    ("""        if mastery > data.get("completeness", 1.0) + EPS:""",
     """        if data.get("known_completeness", 1.0) < data.get("completeness", 1.0) - EPS:
            out.append(f"{person.name} believes an art is less complete than it is")
        if mastery > data.get("completeness", 1.0) + EPS:"""),
    ("""def check_turn(game, turn, recent_narration: Sequence[str]) -> list[str]:
    problems = []""",
     """def check_items(world) -> list[str]:
    out = []
    for manual in world.entities("manual"):
        owners = world.sources(manual.id, "owns")
        if len(owners) != 1:
            out.append(f"manual #{manual.id} has {len(owners)} owners")
        technique = world.entity(manual.data.get("technique"))
        if technique is None or technique.kind != "technique":
            out.append(f"manual #{manual.id} holds no real technique")
        if manual.data.get("claimed_completeness", 1.0) < manual.data.get("true_completeness", 1.0) - EPS:
            out.append(f"manual #{manual.id} claims less than it holds")
    return out


FRAGMENT_KEYS = {"technique", "form", "element", "segment"}


def check_fragments(person) -> list[str]:
    fragments = person.data.get("fragments", [])
    if len(fragments) > 12:
        return [f"{person.name} holds {len(fragments)} fragments (max 12)"]
    if any(set(f) != FRAGMENT_KEYS for f in fragments):
        return [f"{person.name} holds malformed fragments"]
    return []


def check_combat(game) -> list[str]:
    out = []
    d = getattr(game, "combat", None)
    if d is not None:
        for side in (d.player, d.opponent):
            if game.world.entity(side) is None:
                out.append(f"duel participant #{side} does not exist")
        for side, value in d.harm.items():
            if not 0 <= value <= 100:
                out.append(f"duel harm for {side} is {value}")
        if d.stage not in ("fighting", "verdict"):
            out.append(f"duel stage {d.stage!r} is not a stage")
    encounter = getattr(game, "encounter", None)
    if encounter is not None and game.world.entity(encounter["person"]) is None:
        out.append("an encounter with no one")
    return out


def check_turn(game, turn, recent_narration: Sequence[str]) -> list[str]:
    problems = check_combat(game)"""),
    ("""        if any("completeness" in key for key in brief.details):""",
     """        if any("true" in key for key in brief.details):
            problems.append(f"a hidden truth leaked into a {brief.kind} brief")
        if any("completeness" in key for key in brief.details):"""),
])

spec = pathlib.Path("docs/superpowers/specs/2026-09-22-phase2-cultivation-combat-design.md")
spec.write_text(spec.read_text(encoding="utf-8") + """
## 16. Implementation notes (phase 2b)

These choices were forced by the balance targets in §9.5 and were checked with a prototype solver before building:

- **Guard counters a Strike:** it deals ×0.5 as well as gaining an opening. Without this, "always Strike" beats any adaptive opponent.
- **Damage base is 35:** that puts duels at 3–8 exchanges (about 7 between equals).
- **The opponent reads habits and patterns:**
  - +0.75 to the counter of each of your last three moves;
  - +3.0, spread across what you have tended to play *after* your last move.
  - Result: fixed moves win at most about 49%, cycling all four about 53%, alternating two about 56%, and a realm gap about 99%.
- **Watching duels gives no fragments yet.** NPC-versus-NPC duels arrive with the phase 4 world simulation. Fragments come from probing and sparring.
- **Created arts get generated names.** There is no typed naming.
- **Roamers live in regions.** Road bandits, beasts and wanderers are located in their region, not a town. Beasts are persons with `beast: true`.
""", encoding="utf-8", newline="\n")

patch("docs/debugging.md", [
    ("- **Arts:** every known art is a technique, and mastery never exceeds completeness. No breakthrough skips a realm.",
     "- **Arts:** every known art is a technique, and mastery never exceeds completeness. No breakthrough skips a realm. Belief never falls below truth (`known_completeness >= completeness`).\n"
     "- **Items:** every manual has exactly one owner and a real technique, and never claims less than it holds.\n"
     "- **Fights:** a live duel has real participants, harm between 0 and 100, and a valid stage. An encounter has a real person. Fragment lists are well-formed and hold at most 12."),
])
print("task 10 patched")
```

- [ ] **Step 4: Run** `python .patches/2b_task10.py`, then the tests → `tests/test_invariants_2b.py` PASS (4 passed), and the **full suite passes, including all 7 fuzz runs**.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: rules for fights, items and purses; violent-life fuzzing; docs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

## Self-review notes

- **Spec coverage:**

| Spec section | Where it's covered |
|---|---|
| §8 Silver | Task 1: payments for lessons, tolls and manuals, plus robbery in the duel end effect |
| §9.1 State | Duel state and rebuild in Task 4, resume in the engine in Task 6 |
| §9.2 Exchange table, power, damage, flee, yield | Tasks 2 and 4 |
| §9.3 Endings and consequences | Task 4 (`_end_event`, `npc_verdict`, memories, insight, the life-and-death flag) |
| §9.4 Opponent AI | Task 3 |
| §9.5 Balance targets | Task 3 solver tests, with constants tuned in advance |
| §10 Spar and challenge | Tasks 4 and 6 |
| §10 Road encounters and NPC challenges | Task 7 |
| §10 Teachers and manuals | Task 8 |
| §10 Fragments and creation | Tasks 4 and 9 |
| §12 Briefs | Tasks 5, 7, 8 and 9; outcome registry, never a true completeness |
| §13 Invariants | Task 10 |
| §14 Testing | Solver (Task 3), determinism (replay test in Task 6), fuzz (Task 10), knowledge isolation (Tasks 8 and 10) |

- **Review Focus coverage:**

| Item | Test |
|---|---|
| 1 | `test_a_duel_in_progress_is_rebuilt_from_the_chronicle` (Task 4), `test_a_fight_resumes_after_reload` (Task 6), `test_an_unanswered_encounter_survives_a_reload` (Task 7) |
| 2 | `test_other_actions_are_refused_mid_fight` (Task 6), `test_travel_can_end_in_an_encounter_that_blocks_everything_else` (Task 7) |
| 3 | `test_paying_more_than_you_have_changes_nothing` (Task 1), `test_no_silver_no_toll` (Task 7), `test_no_silver_no_lesson` (Task 8) |
| 4 | `test_losing_to_a_bandit_costs_silver_but_never_life` (Task 4), `test_a_violent_life_stays_clean` (Task 10) |
| 5 | `test_a_lying_manual_is_found_out_only_by_deviation` (Task 8), the leak rules (Task 10) |
