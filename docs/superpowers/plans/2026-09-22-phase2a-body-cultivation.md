# DeepMurim Phase 2a (Body & Cultivation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every person a body that remembers what happens to it (a dantian, 20 meridians, physique, lasting injuries, a hidden constitution). Add a slow road of cultivation (meditation, seclusion, practising arts, opening meridians, rest, breakthroughs, qi deviation), with martial arts as real entities that can lie about how complete they are. The player gets to them through three creation modes, a Cultivate menu, and an F4 character sheet with an ASCII body chart.

**Architecture:**
- The body is a typed dataclass stored as JSON in `person.data["body"]`. `settle(body, now)` brings it forward in time as a pure function: healing, deviation fading, qi returning.
- Techniques are entities. Knowing one is a `knows` relation carrying mastery, true completeness, and believed completeness.
- Every cultivation action builds one Event with its outcome **precomputed** from seeded randomness. The effect applies exactly that and advances time, so replays and briefs are exact.
- Briefs gain an `outcome` list, the facts the player must be told. The procedural narrator shows these as dim lines.

**Tech Stack:** Python 3.14, pygame-ce (window only), sqlite3/json1, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-22-phase2-cultivation-combat-design.md` (sections for 2a: §3–§8, §11–§14). Parent: `docs/superpowers/specs/2026-09-22-deepmurim-design.md` (§6.0 Briefs).

## Global Constraints

- The engine is the only writer. State changes go through `world.events.commit`. Generation is the one exception: world materialization, character creation, and lazy NPC bodies write directly, inside a transaction.
- **No new tables; the schema stays at version 1.** New data lives in entity `data` JSON and in `relations`.
- All randomness uses `world.seed.rng_for(world_seed, path)`. Cultivation salts are `f"cultivate:{what}:{pid}:{world.time}"`.
- **Time unit:** the watch, with 4 per day. Cultivation effects advance time *before* applying results. The exception is `rested`, which halves healing times first, then advances.
- Only `render/screen.py` and `main.py` import pygame.
- **Briefs:** at most 6 facts, at most 4 outcome lines, a prompt of at most 1,200 characters, no entity ids.
  - Never include `completeness` (the truth) or an undiscovered constitution's name.
  - Only `known_completeness` is ever shown to the player.
- **Menus:** at most 9 choices shown. Folded choices go in `Turn.extra`, so typed commands still reach them.
- Menu labels use ASCII `...`, not the Unicode ellipsis.
- **Tests:** run with `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` from the repo root.
- Every commit message ends with a blank line, then `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Intentional spec deviations**, which Task 10 writes back into the spec:
  - The energy base rate is **0.015**, not 0.01. It was tuned to meet the spec's binding pacing band of 60–150 days to Third-rate.
  - Constitution discovery is a `discovered` field on the triggering event, not a separate `discovery` event.
  - `Brief` gains an `outcome` tuple.

## Review Focus

1. **Many in-game years pass in a session.** For example, 150 mixed seclusions, practice sessions and breakthrough attempts. No rule may break and no crash may happen. Tested in Task 10 (`test_years_of_cultivation_stay_clean`).
2. **Loading a phase 1 save.** It must get a body, arts and silver without a crash, and a Continue session on it must replay exactly. Tested in Tasks 4 and 8.
3. **Menus growing with content.** 8 blocked meridians plus Back must still fit in 9, and busy towns with the new Cultivate entry must fold Travel. Tested in Task 7.
4. **Point-buy edge input.** Pressing right past the pool or the maximum, left below the base, Enter on a non-Begin row, and cycling the form. None of these may corrupt the choice. Tested in Task 8.
5. **Typed cultivation commands while a different submenu is open, or mid-conversation.** For example `meditate season`, `open governing`, `rest`. They must reach the folded choice, or refuse politely. Tested in Task 7.

---

## File map

| File | Responsibility |
|---|---|
| `world/body.py` | Body/Meridian/Injury dataclasses, roll, injuries, `settle`, JSON (de)serialise |
| `world/db.py` (modify) | `relations_from(a, kind)` |
| `systems/realms.py` | realm ladder, stages, bottleneck, requirements, breakthrough chance, words |
| `systems/techniques.py` | technique generation/names, `Known`, `known_arts`, `teach`, compatibility, mastery words |
| `systems/bodies.py` | `ensure_body` (lazy NPC bodies), `load_body`, `save_body` |
| `systems/creation.py` | origins, `CreationChoice`, `build`, `apply_creation`, `body_awakened` effect |
| `systems/cultivation.py` | meditate/practise/open/rest/breakthrough event builders + effects, deviation |
| `systems/time.py` (modify) | `days_word` |
| `narrate/brief.py` (rewrite) | `outcome`, `player_facts`, body-event outcomes |
| `narrate/procedural.py` (rewrite) | breakthrough keys, outcome lines |
| `narrate/grammar/body.toml` | prose for the new event kinds |
| `engine/game.py` (rewrite) | creation in `new`, migration in `load`, Cultivate menus/handlers, menu folding |
| `engine/commands.py` (rewrite) | cultivation words |
| `engine/journal.py` (rewrite) | summaries for new kinds |
| `engine/sheet.py` | F4 sheet text |
| `render/body_chart.py` | ASCII body chart |
| `render/menu.py` (rewrite) | `message_key` parameter |
| `app.py` (rewrite) | creation screens, F4 sheet, creation in session header, snapshot before load |
| `debug/replay.py` (rewrite) | replay the recorded creation choice |
| `debug/invariants.py` (rewrite) | body, art and brief rules |

---

### Task 1: The body

**Files:**
- Create: `world/body.py`
- Modify: `world/db.py` (add `relations_from` below `sources`)
- Test: `tests/test_body.py`

**Interfaces:**
- Produces:
  - Constants: `REGULAR`, `EXTRAORDINARY`, `MERIDIANS`, `STATES`, `BODY_PARTS`, `LOCATIONS`, `INJURY_KINDS`, `ELEMENTS`, `PHYSIQUE`, `CONSTITUTIONS`, `WATCHES_PER_DAY`.
  - Dataclasses: `Meridian(state, flow, opening, heals_at)`, `Injury(id, location, kind, severity, permanent, since, heals_at, cause)`, and `Body(...)`. The `Body` fields are listed in the code below.
  - Functions:
    - `max_qi(body) -> float`
    - `to_dict(body) -> dict`, `from_dict(dict) -> Body`, `clone(body) -> Body`
    - `add_injury(body, location, kind, severity, now, cause, permanent=False) -> Injury`
    - `unhealed(body, now) -> list[Injury]`
    - `settle(body, now) -> Body`
    - `roll_body(rng, bias=None, physique=None, flow_bonus=0.0) -> Body`
    - `body_of(entity) -> Body | None`
  - Method: `World.relations_from(a, kind) -> list[tuple[int, float, dict]]`.

- [ ] **Step 1: Write the failing test** — `tests/test_body.py`
```python
import random

import pytest

from world.body import (
    EXTRAORDINARY, MERIDIANS, REGULAR, add_injury, body_of, clone, from_dict, max_qi, roll_body, settle,
    to_dict, unhealed,
)
from world.db import World


def body(seed=1, **kw):
    return roll_body(random.Random(seed), **kw)


def test_roll_is_deterministic_and_in_range():
    a, b = body(5), body(5)
    assert to_dict(a) == to_dict(b)
    assert set(a.meridians) == set(MERIDIANS)
    assert all(a.meridians[m].state == "open" and 0.4 <= a.meridians[m].flow <= 0.9 for m in REGULAR)
    assert all(a.meridians[m].state == "blocked" for m in EXTRAORDINARY)
    assert all(1 <= v <= 20 for v in a.physique.values())
    assert abs(a.nature["yin"] + a.nature["yang"] - 1) < 0.02
    assert abs(sum(a.nature[e] for e in ("metal", "wood", "water", "fire", "earth")) - 1) < 0.02
    assert 0.3 <= a.purity <= 1.0 and a.qi == max_qi(a)


def test_bias_and_overrides():
    scarred = body(3, bias={"scarred": 1, "strength": 5})
    assert sum(m.state == "scarred" for m in scarred.meridians.values()) == 1
    fixed = body(3, physique={"strength": 16, "agility": 8, "endurance": 8, "comprehension": 12}, flow_bonus=0.2)
    assert fixed.physique == {"strength": 16, "agility": 8, "endurance": 8, "comprehension": 12}
    assert all(fixed.meridians[m].flow >= 0.6 for m in REGULAR)


def test_roundtrip_through_json_dict():
    b = body(7)
    add_injury(b, "left arm", "cut", 2, now=0, cause="a test")
    assert to_dict(from_dict(to_dict(b))) == to_dict(b)
    assert to_dict(clone(b)) == to_dict(b) and clone(b) is not b


def test_injuries_heal_with_time_but_permanent_ones_never():
    b = body(2)
    b.physique["endurance"], b.constitution = 10, None
    cut = add_injury(b, "left arm", "cut", 2, now=0, cause="x")  # 20 days = 80 watches
    add_injury(b, "right leg", "fracture", 5, now=0, cause="y", permanent=True)
    assert cut.heals_at == 80
    assert {i.location for i in unhealed(settle(b, 79), 79)} == {"left arm", "right leg"}
    assert {i.location for i in settle(b, 80).injuries} == {"right leg"}


def test_meridian_injuries_damage_scar_and_sever():
    b = body(4)
    b.meridians["Lung"].flow, b.meridians["Heart"].flow = 0.7, 0.3
    add_injury(b, "Lung", "meridian", 2, now=0, cause="x")
    add_injury(b, "Heart", "meridian", 2, now=0, cause="x")
    add_injury(b, "Liver", "meridian", 5, now=0, cause="x")
    assert b.meridians["Lung"].state == "damaged" and b.meridians["Liver"].state == "severed"
    later = settle(b, 10_000)
    assert later.meridians["Lung"].state == "open"      # strong flow recovers
    assert later.meridians["Heart"].state == "scarred"  # weak flow scars
    assert later.meridians["Liver"].state == "severed"


def test_invalid_location_is_rejected():
    with pytest.raises(ValueError):
        add_injury(body(), "tail", "cut", 1, now=0, cause="x")


def test_deviation_fades_and_qi_returns():
    b = body(6)
    b.deviation, b.qi = 30, 0
    later = settle(b, 4 * 10)  # ten days
    assert later.deviation == pytest.approx(25)
    assert later.qi == pytest.approx(max_qi(b))


def test_settle_is_path_independent():
    b = body(8)
    b.deviation, b.qi = 80, 1
    add_injury(b, "torso", "internal", 3, now=0, cause="x")
    assert to_dict(settle(b, 200)) == to_dict(settle(settle(settle(b, 50), 120), 200))


def test_body_of_and_relations_from(tmp_path):
    world = World.create(tmp_path / "w.world", 1)
    pid = world.add_entity("person", "Hero", {"body": to_dict(body(1))})
    assert to_dict(body_of(world.entity(pid))) == to_dict(body(1))
    tech = world.add_entity("technique", "Palm", {})
    world.relate(pid, tech, "knows", value=0.25, data={"completeness": 0.8})
    assert world.relations_from(pid, "knows") == [(tech, 0.25, {"completeness": 0.8})]
    assert body_of(world.entity(world.add_entity("person", "Ghost"))) is None
    world.close()
```

- [ ] **Step 2: Run to verify it fails** — `.venv/Scripts/python.exe -m pytest tests/test_body.py -q -p no:cacheprovider` → FAIL (`ModuleNotFoundError: world.body`)

- [ ] **Step 3: Implement**

`world/body.py`:
```python
"""The body: dantian, meridians, physique and injuries (phase 2 spec §3).

Stored as JSON under a person's data["body"]. `settle` brings a body forward to
a moment in time: injuries heal, damaged meridians recover or scar, deviation
fades and qi returns. It is pure, so reading a body at time t gives the same
answer however long ago it was last written.
"""

import copy
from dataclasses import asdict, dataclass, field

REGULAR = (
    "Lung", "Large Intestine", "Stomach", "Spleen", "Heart", "Small Intestine",
    "Bladder", "Kidney", "Pericardium", "Triple Burner", "Gallbladder", "Liver",
)
EXTRAORDINARY = (
    "Governing", "Conception", "Penetrating", "Girdle",
    "Yin Linking", "Yang Linking", "Yin Heel", "Yang Heel",
)
MERIDIANS = REGULAR + EXTRAORDINARY
STATES = ("open", "blocked", "damaged", "scarred", "severed")
BODY_PARTS = ("head", "torso", "left arm", "right arm", "left leg", "right leg")
LOCATIONS = BODY_PARTS + MERIDIANS
INJURY_KINDS = ("bruise", "cut", "fracture", "internal", "meridian")
ELEMENTS = ("metal", "wood", "water", "fire", "earth")
PHYSIQUE = ("strength", "agility", "endurance", "comprehension")
CONSTITUTIONS = (
    "Nine Yin Body", "Pure Yang Body", "Heavenly Sword Bones",
    "Myriad Poison Body", "Iron Bone Body", "Dragon Vein Body",
)
CONSTITUTION_CHANCE = 0.04
WATCHES_PER_DAY = 4
DEVIATION_DECAY_PER_DAY = 0.5
QI_REGEN_PER_DAY = 0.5  # fraction of max qi recovered per day
HEAL_FASTER = {"Iron Bone Body": 1.5}


@dataclass
class Meridian:
    state: str = "open"
    flow: float = 0.5
    opening: float = 0.0          # progress towards opening, while blocked
    heals_at: int | None = None   # while damaged: when it recovers


@dataclass
class Injury:
    id: int
    location: str
    kind: str
    severity: int
    permanent: bool
    since: int
    heals_at: int | None
    cause: str


@dataclass
class Body:
    energy_years: float = 0.0
    qi: float = 10.0
    purity: float = 0.5
    nature: dict = field(default_factory=dict)
    meridians: dict = field(default_factory=dict)
    physique: dict = field(default_factory=dict)
    constitution: str | None = None
    constitution_known: bool = False
    injuries: list = field(default_factory=list)
    deviation: float = 0.0
    realm: int = 0
    bottleneck: bool = False
    insight: float = 0.0
    flags: list = field(default_factory=list)
    meditated_days: float = 0.0
    settled_at: int = 0
    next_injury_id: int = 1


def max_qi(body: Body) -> float:
    return 10.0 + 10.0 * body.energy_years * body.purity


def to_dict(body: Body) -> dict:
    return asdict(body)


def from_dict(data: dict) -> Body:
    data = copy.deepcopy(data)
    data["meridians"] = {name: Meridian(**m) for name, m in data.get("meridians", {}).items()}
    data["injuries"] = [Injury(**i) for i in data.get("injuries", [])]
    return Body(**data)


def clone(body: Body) -> Body:
    return from_dict(to_dict(body))


def heal_watches(severity: int, body: Body) -> int:
    days = severity ** 2 * 5 / (body.physique.get("endurance", 10) / 10)
    days /= HEAL_FASTER.get(body.constitution, 1.0)
    return max(1, round(days * WATCHES_PER_DAY))


def add_injury(body: Body, location: str, kind: str, severity: int, now: int, cause: str,
               permanent: bool = False) -> Injury:
    if location not in LOCATIONS:
        raise ValueError(f"no such body location: {location!r}")
    severity = max(1, min(5, int(severity)))
    heals_at = None if permanent else now + heal_watches(severity, body)
    injury = Injury(body.next_injury_id, location, kind, severity, permanent, now, heals_at, cause)
    body.next_injury_id += 1
    body.injuries.append(injury)
    meridian = body.meridians.get(location)
    if meridian is not None:
        if permanent or severity >= 5:
            meridian.state, meridian.heals_at = "severed", None
        elif meridian.state == "open":
            meridian.state, meridian.heals_at = "damaged", heals_at
        elif meridian.state == "damaged":
            meridian.heals_at = max(meridian.heals_at or 0, heals_at)
    return injury


def unhealed(body: Body, now: int) -> list[Injury]:
    return [i for i in body.injuries if i.permanent or (i.heals_at is not None and i.heals_at > now)]


def settle(body: Body, now: int) -> Body:
    settled = clone(body)
    if now <= settled.settled_at:
        return settled
    days = (now - settled.settled_at) / WATCHES_PER_DAY
    settled.injuries = unhealed(settled, now)
    for meridian in settled.meridians.values():
        if meridian.state == "damaged" and meridian.heals_at is not None and meridian.heals_at <= now:
            meridian.state = "open" if meridian.flow >= 0.5 else "scarred"
            meridian.heals_at = None
    settled.deviation = max(0.0, settled.deviation - DEVIATION_DECAY_PER_DAY * days)
    settled.qi = min(max_qi(settled), settled.qi + max_qi(settled) * QI_REGEN_PER_DAY * days)
    settled.settled_at = now
    return settled


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def roll_body(rng, bias: dict | None = None, physique: dict | None = None, flow_bonus: float = 0.0) -> Body:
    """A body from seeded dice. `bias` nudges an origin; `physique` fixes it (point-buy)."""
    bias = bias or {}
    if physique is None:
        physique = {p: int(_clamp(round(rng.gauss(10, 2.5)) + bias.get(p, 0), 1, 20)) for p in PHYSIQUE}
    else:
        physique = {p: int(physique[p]) for p in PHYSIQUE}
    meridians = {}
    for name in REGULAR:
        flow = _clamp(rng.uniform(0.4, 0.9) + flow_bonus + bias.get("flow", 0.0), 0.1, 1.0)
        meridians[name] = Meridian("open", round(flow, 2))
    for name in EXTRAORDINARY:
        meridians[name] = Meridian("blocked", 0.0)
    for name in rng.sample(REGULAR, int(bias.get("scarred", 0))):
        meridians[name].state = "scarred"
    yang = round(_clamp(rng.uniform(0.3, 0.7) + bias.get("yang", 0.0), 0.1, 0.9), 2)
    raw = [rng.random() + 0.05 for _ in ELEMENTS]
    total = sum(raw)
    nature = {"yin": round(1 - yang, 2), "yang": yang, **{e: round(w / total, 3) for e, w in zip(ELEMENTS, raw)}}
    purity = round(_clamp(rng.uniform(0.35, 0.6) + bias.get("purity", 0.0), 0.3, 1.0), 2)
    constitution = rng.choice(CONSTITUTIONS) if rng.random() < CONSTITUTION_CHANCE else None
    body = Body(purity=purity, nature=nature, meridians=meridians, physique=physique, constitution=constitution)
    body.qi = max_qi(body)
    return body


def body_of(entity) -> Body | None:
    raw = entity.data.get("body")
    return from_dict(raw) if raw else None
```
In the `World` class (world database module), add this method directly after `sources`:
```
    def relations_from(self, a: int, kind: str) -> list[tuple[int, float, dict]]:
        """(target, value, data) for each relation of this kind from `a`, oldest first."""
        rows = self._conn.execute(
            "select b, value, data from relations where a = ? and kind = ? order by since, b", (a, kind)
        )
        return [(row[0], row[1], json.loads(row[2])) for row in rows]
```

- [ ] **Step 4: Run tests** → PASS (9 passed). Then run the whole suite → all PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: the body - dantian, meridians, injuries, settle" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 2: Realms

**Files:**
- Create: `systems/realms.py`
- Test: `tests/test_realms.py`

**Interfaces:**
- Consumes: `Body`, `EXTRAORDINARY` (Task 1)
- Produces:
  - `Realm(name, threshold, multiplier, label)`, `REALMS` (8 entries), `IMMORTAL_PATH`, `MAX_REALM = 7`, `STAGES`
  - `next_threshold(realm) -> float | None`
  - `stage_of(body) -> str`, `realm_title(body) -> str`
  - `add_energy(body, years) -> float`: the energy actually added; it sets `bottleneck`.
  - `requirement(body, arts) -> tuple[bool, str]`. `arts` are objects with `.category`, `.mastery` and `.source`.
  - `breakthrough_chance(body, met) -> float`, `energy_words(years) -> str`, `realm_index(label) -> int`

- [ ] **Step 1: Write the failing test** — `tests/test_realms.py`
```python
import random
from types import SimpleNamespace as NS

import pytest

from systems.realms import (
    MAX_REALM, REALMS, add_energy, breakthrough_chance, energy_words, realm_index, realm_title, requirement,
    stage_of,
)
from world.body import EXTRAORDINARY, roll_body


def fresh(realm=0, energy=0.0):
    b = roll_body(random.Random(1))
    b.realm, b.energy_years = realm, energy
    return b


def art(category="martial", mastery=0.0, source="origin"):
    return NS(category=category, mastery=mastery, source=source)


def test_ladder():
    assert [r.threshold for r in REALMS] == [0, 1, 5, 20, 40, 60, 120, 240]
    assert MAX_REALM == 7 and realm_index("second-rate") == 2 and realm_index("nonsense") == 0


def test_stages_follow_energy_within_realm():
    assert stage_of(fresh(1, 1.0)) == "early"
    assert stage_of(fresh(1, 2.0)) == "middle"
    assert stage_of(fresh(1, 3.5)) == "late"
    assert stage_of(fresh(1, 4.99)) == "peak"
    assert realm_title(fresh(0, 0.2)) == "Mortal"
    assert realm_title(fresh(1, 2.5)) == "Third-rate (middle stage)"


def test_energy_stops_at_the_bottleneck():
    b = fresh(0, 0.9)
    assert add_energy(b, 0.05) == pytest.approx(0.05) and not b.bottleneck
    assert add_energy(b, 5.0) == pytest.approx(0.05)
    assert b.energy_years == 1.0 and b.bottleneck


def test_requirements_by_target_realm():
    b = fresh(0, 1.0)
    assert requirement(b, [])[0] is False
    b.flags.append("sensed_qi")
    assert requirement(b, [])[0] is True
    b = fresh(1, 5.0)
    assert requirement(b, [])[0] is False
    b.meridians["Conception"].state = "open"
    assert requirement(b, [])[0] is True
    b = fresh(2, 20.0)
    b.meridians["Governing"].state = b.meridians["Conception"].state = "open"
    assert requirement(b, [art(mastery=0.5)])[0] is False
    assert requirement(b, [art(mastery=0.7)])[0] is True
    assert requirement(b, [art("heart_method", 0.9)])[0] is False  # heart methods don't count
    b = fresh(3, 40.0)
    assert requirement(b, [art(mastery=1.0)])[0] is False
    b.flags.append("life_and_death_insight")
    assert requirement(b, [art(mastery=1.0)])[0] is True
    b = fresh(4, 60.0)
    b.insight = 250
    for m in EXTRAORDINARY:
        b.meridians[m].state = "open"
    assert requirement(b, [])[0] is True
    b = fresh(5, 120.0)
    assert requirement(b, [art(mastery=1.0, source="created")])[0] is True
    met, text = requirement(fresh(7, 240.0), [])
    assert not met and "not yet open" in text


def test_breakthrough_chance():
    b = fresh(0, 1.0)
    b.physique["comprehension"], b.purity, b.insight = 10, 0.5, 0
    assert breakthrough_chance(b, True) == pytest.approx(0.40)
    assert breakthrough_chance(b, False) == pytest.approx(0.04)
    b.physique["comprehension"] = 30
    assert breakthrough_chance(b, True) == 0.95


def test_energy_words():
    assert energy_words(0.0) == "barely a trace of internal energy"
    assert energy_words(0.5) == "less than a year of internal energy"
    assert energy_words(1.2) == "about one year of internal energy"
    assert energy_words(3.9) == "about three years of internal energy"
    assert energy_words(42) == "about 42 years of internal energy"
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: systems.realms`)

- [ ] **Step 3: Implement** — `systems/realms.py`
```python
"""The realm ladder (phase 2 spec §4): stages, bottlenecks, breakthrough conditions."""

from dataclasses import dataclass

from world.body import EXTRAORDINARY, Body


@dataclass(frozen=True)
class Realm:
    name: str
    threshold: float     # energy (years) at which this realm begins
    multiplier: float    # combat weight (phase 2b)
    label: str           # how data["realm"] spells it


REALMS = (
    Realm("Mortal", 0, 1, "mortal"),
    Realm("Third-rate", 1, 3, "third-rate"),
    Realm("Second-rate", 5, 6, "second-rate"),
    Realm("First-rate", 20, 12, "first-rate"),
    Realm("Peak", 40, 24, "peak"),
    Realm("Transcendent", 60, 48, "transcendent"),
    Realm("Profound", 120, 96, "profound"),
    Realm("Life-and-Death", 240, 192, "life-and-death"),
)
IMMORTAL_PATH = ("Foundation Establishment", "Core Formation", "Nascent Soul")  # locked in phase 2
MAX_REALM = len(REALMS) - 1
STAGES = ("early", "middle", "late", "peak")
LABEL_TO_INDEX = {r.label: i for i, r in enumerate(REALMS)}
NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
EPS = 1e-9


def realm_index(label: str) -> int:
    return LABEL_TO_INDEX.get(label, 0)


def next_threshold(realm: int) -> float | None:
    return REALMS[realm + 1].threshold if realm < MAX_REALM else None


def stage_of(body: Body) -> str:
    low = REALMS[body.realm].threshold
    high = next_threshold(body.realm) or low * 2
    fraction = (body.energy_years - low) / (high - low) if high > low else 0.0
    return STAGES[max(0, min(3, int(fraction * 4)))]


def realm_title(body: Body) -> str:
    if body.realm == 0:
        return "Mortal"
    return f"{REALMS[body.realm].name} ({stage_of(body)} stage)"


def add_energy(body: Body, years: float) -> float:
    """Add energy up to the bottleneck; returns what was actually added."""
    high = next_threshold(body.realm)
    before = body.energy_years
    body.energy_years = before + years if high is None else min(high, before + years)
    body.bottleneck = high is not None and body.energy_years >= high - EPS
    return body.energy_years - before


def requirement(body: Body, arts) -> tuple[bool, str]:
    """Whether the condition for the next realm is met, and what it is, in words."""
    target = body.realm + 1
    flags = body.flags

    def is_open(name: str) -> bool:
        return body.meridians[name].state == "open"

    martial = [a for a in arts if a.category == "martial"]
    if target > MAX_REALM:
        return False, "The way beyond is not yet open to you."
    if target == 1:
        return "sensed_qi" in flags, "You must first sense the qi within you."
    if target == 2:
        return is_open("Governing") or is_open("Conception"), "Open the Governing or Conception meridian."
    if target == 3:
        met = is_open("Governing") and is_open("Conception") and any(a.mastery >= 0.67 for a in martial)
        return met, "Open the Governing and Conception meridians and bring a martial art to Major Success."
    if target == 4:
        met = any(a.mastery >= 1.0 for a in martial) and "life_and_death_insight" in flags
        return met, "Bring a martial art to Great Completion and survive a true life-or-death fight."
    if target == 5:
        met = all(is_open(m) for m in EXTRAORDINARY) and body.insight >= 200
        return met, "Open all eight extraordinary meridians and gather deep martial insight."
    if target == 6:
        return any(a.source == "created" and a.mastery >= 1.0 for a in arts), "Create your own art and bring it to Great Completion."
    return "returned_to_origin" in flags, "Return to the origin of your martial way."


def breakthrough_chance(body: Body, met: bool) -> float:
    chance = 0.35 + 0.05 * (body.physique["comprehension"] - 10) + 0.1 * body.purity + min(0.2, body.insight / 500)
    chance = max(0.05, min(0.95, chance))
    return round(chance if met else chance * 0.1, 3)


def energy_words(years: float) -> str:
    if years < 0.05:
        return "barely a trace of internal energy"
    if years < 1:
        return "less than a year of internal energy"
    n = int(years)
    count = NUMBER_WORDS[n - 1] if n <= len(NUMBER_WORDS) else str(n)
    return f"about {count} year{'s' if n != 1 else ''} of internal energy"
```

- [ ] **Step 4: Run tests** → PASS (6 passed), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: realm ladder, stages, bottlenecks, breakthrough rules" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 3: Techniques

**Files:**
- Create: `systems/techniques.py`
- Test: `tests/test_techniques.py`

**Interfaces:**
- Consumes: `REGULAR`, `ELEMENTS`, `Body` (Task 1), `World.relations_from` (Task 1)
- Produces:
  - Constants: `FORMS`, `GRADE_MULT`, `INTENTS`, `ROUTE_FACTOR`, `FORM_STATS`
  - Generation: `grade_mult(grade)`, `technique_name(rng, form)`, `generate(rng, category, form=None, grade=1, element=None) -> (name, data)`, `create_technique(world, name, data) -> int`
  - Knowing arts:
    - `Known(technique, mastery, completeness, known_completeness, source, teacher)` with `.name`, `.category`, `.form`
    - `teach(world, person_id, technique_id, completeness=1.0, known_completeness=1.0, source="taught", teacher=None, mastery=0.05)`
    - `set_mastery(world, person_id, technique_id, mastery)`
    - `known_arts(world, pid) -> list[Known]`, `heart_method(world, pid) -> Known | None`, `martial_arts(world, pid) -> list[Known]`
  - Fit and progress: `alignment(element, nature)`, `usable(body, data)`, `compatibility(body, data) -> float`, `compat_words(c)`, `mastery_stage(m)`, `practise_gain(days, comprehension, compat, grade)`

- [ ] **Step 1: Write the failing test** — `tests/test_techniques.py`
```python
import random

import pytest

from systems.techniques import (
    FORMS, alignment, compat_words, compatibility, create_technique, generate, heart_method, known_arts,
    martial_arts, mastery_stage, practise_gain, set_mastery, teach, usable,
)
from world.body import REGULAR, roll_body
from world.db import World


def neutral_body():
    b = roll_body(random.Random(1))
    b.physique = {"strength": 10, "agility": 10, "endurance": 10, "comprehension": 10}
    return b


def art_data(**kw):
    data = {"category": "martial", "form": "sword", "route": ["Lung", "Heart"], "element": "neutral", "grade": 1}
    data.update(kw)
    return data


def test_generate_is_deterministic_and_well_formed():
    a = generate(random.Random(3), "martial", form="palm", grade=2)
    assert a == generate(random.Random(3), "martial", form="palm", grade=2)
    name, data = a
    assert "Palm" in name and data["form"] == "palm" and data["grade"] == 2
    assert 2 <= len(data["route"]) <= 6 and set(data["route"]) <= set(REGULAR)
    assert data["stance"]["favours"] in ("strike", "feint", "guard", "probe")
    _, heart = generate(random.Random(3), "heart_method")
    assert heart["form"] == "inner" and heart["category"] == "heart_method"
    assert {generate(random.Random(s), "martial")[1]["form"] for s in range(40)} <= set(FORMS)


def test_compatibility_route_nature_and_body():
    b = neutral_body()
    assert compatibility(b, art_data()) == pytest.approx(1.0)
    b.meridians["Heart"].state = "scarred"
    assert compatibility(b, art_data()) == pytest.approx(0.8)
    b.meridians["Heart"].state = "damaged"
    assert compatibility(b, art_data()) == pytest.approx(0.5)
    b.meridians["Heart"].state = "severed"
    assert compatibility(b, art_data()) == 0 and not usable(b, art_data())
    b = neutral_body()
    b.physique["agility"] = 20
    assert compatibility(b, art_data()) == pytest.approx(1.2)
    b = neutral_body()
    b.nature.update(yin=0.9, yang=0.1)
    assert compatibility(b, art_data(element="yin")) > 1.0 > compatibility(b, art_data(element="yang"))


def test_alignment_bounds():
    nature = {"yin": 0.5, "yang": 0.5, "metal": 0.6, "wood": 0.1, "water": 0.1, "fire": 0.1, "earth": 0.1}
    assert alignment("neutral", nature) == 0 and alignment("yin", nature) == 0
    assert alignment("metal", nature) == 1.0 and alignment("wood", nature) == pytest.approx(-0.5)


def test_words_and_stages():
    assert [compat_words(c) for c in (0.3, 0.6, 0.9, 1.1)] == ["fights your body", "sits awkwardly", "suits you", "made for you"]
    assert [mastery_stage(m) for m in (0.0, 0.4, 0.8, 1.0)] == ["Initial", "Minor Success", "Major Success", "Great Completion"]
    assert practise_gain(7, 10, 1.0, 1) == pytest.approx(0.028)
    assert practise_gain(7, 10, 1.0, 2) == pytest.approx(0.028 / 1.5)


def test_knowing_arts(tmp_path):
    world = World.create(tmp_path / "w.world", 1)
    pid = world.add_entity("person", "Hero")
    heart = create_technique(world, "Still Water Heart Method", art_data(category="heart_method", form="inner"))
    palm = create_technique(world, "Pale Crane Palm", art_data(form="palm"))
    teach(world, pid, heart, source="origin")
    teach(world, pid, palm, completeness=0.6, known_completeness=1.0, source="manual")
    assert [a.name for a in known_arts(world, pid)] == ["Still Water Heart Method", "Pale Crane Palm"]
    assert heart_method(world, pid).name == "Still Water Heart Method"
    assert [a.name for a in martial_arts(world, pid)] == ["Pale Crane Palm"]
    set_mastery(world, pid, palm, 0.5)
    known = martial_arts(world, pid)[0]
    assert known.mastery == 0.5 and known.completeness == 0.6 and known.known_completeness == 1.0
    world.close()
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: systems.techniques`)

- [ ] **Step 3: Implement** — `systems/techniques.py`
```python
"""Martial arts as things in the world (phase 2 spec §5).

A technique is an entity; knowing one is a `knows` relation carrying mastery
and completeness. `completeness` is what the art truly contains;
`known_completeness` is what its knower believes. Only the belief is ever shown.
"""

import math
from dataclasses import dataclass
from statistics import mean

from world.body import ELEMENTS, REGULAR, Body
from world.db import Entity, World

FORMS = ("sword", "saber", "spear", "staff", "palm", "fist", "finger", "footwork")
GRADE_MULT = (1.0, 1.5, 2.2, 3.2, 4.5, 6.5)
INTENTS = ("strike", "feint", "guard", "probe")
ELEMENT_CHOICES = ELEMENTS + ("yin", "yang", "neutral")
ROUTE_FACTOR = {"open": 1.0, "scarred": 0.8, "damaged": 0.5, "blocked": 0.3, "severed": 0.0}
FORM_STATS = {
    "sword": ("agility",), "finger": ("agility",), "footwork": ("agility",),
    "saber": ("strength",), "fist": ("strength",),
    "spear": ("strength", "agility"), "staff": ("strength", "agility"),
    "palm": ("endurance", "comprehension"), "inner": ("endurance", "comprehension"),
}
ADJECTIVES = (
    "Pale", "Iron", "Nine Bends", "Falling Leaf", "Azure", "Blood", "Silent", "Heavenly",
    "Drunken", "Hidden", "Golden", "Frost", "Burning", "Hundred Step", "Thousand Hand",
)
NOUNS = (
    "Crane", "Tiger", "Plum", "Thunder", "Serpent", "Cloud", "Mountain", "River",
    "Wolf", "Lotus", "Dragon", "Moon", "Wind", "Stone", "Phoenix",
)
FORM_WORDS = {
    "sword": ("Sword Art", "Sword"), "saber": ("Saber", "Saber Art"), "spear": ("Spear", "Spear Art"),
    "staff": ("Staff", "Staff Art"), "palm": ("Palm",), "fist": ("Fist",), "finger": ("Finger",),
    "footwork": ("Steps", "Footwork"), "inner": ("Heart Method", "Divine Art", "Qi Manual"),
}
STANCES = {
    "strike": ("Charging Bull Stance", "Falling Hammer Stance"),
    "feint": ("Shifting Shadow Stance", "Drunken Step Stance"),
    "guard": ("Iron Gate Stance", "Rooted Pine Stance"),
    "probe": ("Listening Wind Stance", "Watching Crane Stance"),
}
MASTERY_STAGES = ((0.34, "Initial"), (0.67, "Minor Success"), (1.0, "Major Success"))


def grade_mult(grade: int) -> float:
    return GRADE_MULT[max(1, min(len(GRADE_MULT), grade)) - 1]


def technique_name(rng, form: str) -> str:
    return f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)} {rng.choice(FORM_WORDS[form])}"


def generate(rng, category: str, form: str | None = None, grade: int = 1, element: str | None = None) -> tuple[str, dict]:
    form = "inner" if category == "heart_method" else (form or rng.choice(FORMS))
    element = element or rng.choice(ELEMENT_CHOICES)
    route = rng.sample(REGULAR, min(6, rng.randint(2, 3 + grade // 2)))
    favours = rng.choice(INTENTS)
    data = {
        "category": category, "form": form,
        "stance": {"name": rng.choice(STANCES[favours]), "favours": favours},
        "route": route, "element": element, "grade": grade,
        "power": round(rng.uniform(0.7, 1.3), 2), "speed": round(rng.uniform(0.7, 1.3), 2),
        "defence": round(rng.uniform(0.7, 1.3), 2), "creator": None, "origin": "seeded",
    }
    return technique_name(rng, form), data


def create_technique(world: World, name: str, data: dict) -> int:
    return world.add_entity("technique", name, data)


@dataclass(frozen=True)
class Known:
    technique: Entity
    mastery: float
    completeness: float
    known_completeness: float
    source: str
    teacher: int | None

    @property
    def name(self) -> str:
        return self.technique.name

    @property
    def category(self) -> str:
        return self.technique.data["category"]

    @property
    def form(self) -> str:
        return self.technique.data["form"]


def teach(world: World, person_id: int, technique_id: int, completeness: float = 1.0,
          known_completeness: float = 1.0, source: str = "taught", teacher: int | None = None,
          mastery: float = 0.05) -> None:
    data = {"completeness": completeness, "known_completeness": known_completeness, "source": source, "teacher": teacher}
    world.relate(person_id, technique_id, "knows", value=mastery, data=data)


def set_mastery(world: World, person_id: int, technique_id: int, mastery: float) -> None:
    for tech_id, _, data in world.relations_from(person_id, "knows"):
        if tech_id == technique_id:
            world.relate(person_id, technique_id, "knows", value=mastery, data=data)
            return
    raise KeyError(f"#{person_id} does not know technique #{technique_id}")


def known_arts(world: World, person_id: int) -> list[Known]:
    arts = []
    for tech_id, mastery, data in world.relations_from(person_id, "knows"):
        arts.append(Known(
            world.entity(tech_id), mastery, data.get("completeness", 1.0),
            data.get("known_completeness", 1.0), data.get("source", "unknown"), data.get("teacher"),
        ))
    return arts


def heart_method(world: World, person_id: int) -> Known | None:
    return next((a for a in known_arts(world, person_id) if a.category == "heart_method"), None)


def martial_arts(world: World, person_id: int) -> list[Known]:
    return [a for a in known_arts(world, person_id) if a.category == "martial"]


def alignment(element: str, nature: dict) -> float:
    if element == "neutral":
        return 0.0
    if element in ("yin", "yang"):
        return max(-1.0, min(1.0, nature.get(element, 0.5) * 2 - 1))
    return max(-1.0, min(1.0, (nature.get(element, 0.2) - 0.2) / 0.2))


def usable(body: Body, data: dict) -> bool:
    return all(body.meridians[m].state != "severed" for m in data["route"])


def compatibility(body: Body, data: dict) -> float:
    route = math.prod(ROUTE_FACTOR[body.meridians[m].state] for m in data["route"])
    nature = max(0.6, min(1.3, 1 + 0.3 * alignment(data["element"], body.nature)))
    stat = mean(body.physique[s] for s in FORM_STATS[data["form"]])
    fit = 0.8 + 0.4 * (stat / 20)
    return round(max(0.0, min(1.3, route * nature * fit)), 3)


def compat_words(c: float) -> str:
    if c < 0.4:
        return "fights your body"
    if c < 0.7:
        return "sits awkwardly"
    if c < 1.0:
        return "suits you"
    return "made for you"


def mastery_stage(mastery: float) -> str:
    for limit, name in MASTERY_STAGES:
        if mastery < limit:
            return name
    return "Great Completion"


def practise_gain(days: float, comprehension: float, compat: float, grade: int) -> float:
    return days * 0.004 * (comprehension / 10) * compat / grade_mult(grade)
```

- [ ] **Step 4: Run tests** → PASS (5 passed), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: techniques as entities, knowing arts, compatibility" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 4: Bodies on demand, character creation, old-save migration

**Files:**
- Create: `systems/bodies.py`, `systems/creation.py`
- Modify: `engine/game.py` (rewrite `new` and `load`, shown below as whole methods; the rest of the file is unchanged in this task)
- Test: `tests/test_creation.py`

**Interfaces:**
- Consumes: Tasks 1–3
- Produces:
  - In `systems/bodies.py`: `npc_body(world, entity) -> Body`, `ensure_body(world, pid) -> Body` (settled to now), `load_body(world, pid) -> Body`, and `save_body(world, pid, body)`.
    - `save_body` clamps qi to 0..max, and writes both `data["body"]` and the matching `data["realm"]` label.
  - In `systems/creation.py`:
    - `Origin(key, title, description, heart_grade, heart_element, art_forms, bias, silver, heart_completeness=1.0)`
    - `ORIGINS` (5 entries: hunter, scion, temple, merchant, beggar), `WANDERER`, `MODES`
    - Point-buy constants: `POINT_BASE=8`, `POINT_POOL=12`, `POINT_MAX=16`, `FLOW_POINT_COST=2`
    - `CreationChoice(mode="random", origin=None, physique=None, flow_points=0, form=None)`, with `to_dict()` and `from_dict()`. `physique` is a tuple of (name, value) pairs.
    - `Creation(origin, body, arts, silver)`, where each art is `(name, data, completeness)`.
    - `points_spent(physique, flow_points)`, `point_buy_problem(physique, flow_points) -> str | None`
    - `build(world_seed, choice) -> Creation`, `apply_creation(world, pid, creation) -> list[str]` (the art names), `wanderer_arts(world_seed) -> list[str]`
    - An effect for the `body_awakened` event kind.
  - `Game.new(path, player_name, world_seed=None, narrator=None, creation=None)`
    - The `began` event data becomes `{"origin": <origin title>, "arts": [names]}`.
  - `Game.load` migrates saves that have no body by committing `body_awakened`, with data `{"origin": "Wanderer", "arts": [...]}`.

- [ ] **Step 1: Write the failing test** — `tests/test_creation.py`
```python
import pytest

from engine.game import Game
from systems.bodies import ensure_body, load_body
from systems.creation import ORIGINS, CreationChoice, build, point_buy_problem
from systems.techniques import heart_method, known_arts, martial_arts
from world.body import REGULAR
from world.db import World

POINTS = {"strength": 12, "agility": 12, "endurance": 8, "comprehension": 10}  # 10 points spent


def test_each_origin_builds_its_kit():
    for key, origin in ORIGINS.items():
        made = build(7, CreationChoice("origin", key))
        assert made.origin.key == key and made.silver == origin.silver
        heart, art = made.arts
        assert heart[1]["category"] == "heart_method" and heart[1]["grade"] == origin.heart_grade
        assert art[1]["form"] in origin.art_forms
    scion = build(7, CreationChoice("origin", "scion"))
    assert scion.arts[0][2] == 0.8  # the family method's hidden flaw
    assert sum(scion.body.meridians[m].state == "scarred" for m in REGULAR) == 1
    assert build(7, CreationChoice("origin", "temple")).arts[0][1]["element"] == "yang"


def test_random_mode_is_seeded():
    a, b = build(11, CreationChoice()), build(11, CreationChoice())
    assert a.origin.key == b.origin.key and a.arts[1][0] == b.arts[1][0]
    assert {build(s, CreationChoice()).origin.key for s in range(40)} == set(ORIGINS)


def test_point_buy():
    assert point_buy_problem(POINTS, 1) is None
    made = build(3, CreationChoice("point_buy", physique=tuple(POINTS.items()), flow_points=1, form="saber"))
    assert made.body.physique == POINTS and made.arts[1][1]["form"] == "saber" and made.silver == 50
    assert "points spent" in point_buy_problem({**POINTS, "endurance": 16}, 0)
    assert point_buy_problem({**POINTS, "agility": 17}, 0)
    with pytest.raises(ValueError):
        build(3, CreationChoice("point_buy", physique=tuple(POINTS.items()), form="banjo"))


def test_choice_roundtrips_through_dict():
    choice = CreationChoice("point_buy", physique=tuple(POINTS.items()), flow_points=1, form="saber")
    assert CreationChoice.from_dict(choice.to_dict()) == choice
    assert CreationChoice.from_dict(CreationChoice().to_dict()) == CreationChoice()


def test_new_game_applies_creation(tmp_path):
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=5, creation=CreationChoice("origin", "merchant"))
    player = game.player
    assert player.data["silver"] == 200 and player.data["origin"] == "merchant"
    assert load_body(game.world, player.id).realm == 0
    assert heart_method(game.world, player.id) is not None and len(martial_arts(game.world, player.id)) == 1
    began = game.world.chronicle_about(player.id, limit=5)[-1]
    assert began.kind == "began" and began.data["origin"] == "Merchant's runaway" and len(began.data["arts"]) == 2
    game.close()


def test_old_saves_get_a_body_on_load(tmp_path):
    path = tmp_path / "old.world"
    game = Game.new(path, "Hero", world_seed=5)
    pid = game.player.id
    game.world._conn.execute(
        "update entities set data = json_remove(data, '$.body', '$.silver', '$.origin') where id = ?", (pid,)
    )
    game.world._conn.execute("delete from relations where a = ? and kind = 'knows'", (pid,))
    game.close()
    game = Game.load(path)
    assert "body" in game.player.data and game.player.data["origin"] == "wanderer"
    assert len(known_arts(game.world, pid)) == 2
    assert game.world.chronicle_about(pid, limit=1)[0].kind == "body_awakened"
    game.close()


def test_npc_bodies_follow_their_realm(tmp_path):
    world = World.create(tmp_path / "w.world", 9)
    npc = world.add_entity("person", "Old Master", {"realm": "second-rate"}, seed_path="npc:test")
    body = ensure_body(world, npc)
    assert body.realm == 2 and 5 <= body.energy_years < 20
    assert "sensed_qi" in body.flags and body.meridians["Governing"].state == "open"
    assert "body" in world.entity(npc).data
    assert ensure_body(world, npc).energy_years == body.energy_years
    world.close()
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: systems.bodies`)

- [ ] **Step 3: Implement**

`systems/bodies.py`:
```python
"""Getting a person's body. NPC bodies are rolled from their seed the first time
anything needs one; every save keeps data["realm"] in step with the body."""

from systems.realms import REALMS, next_threshold, realm_index
from world.body import Body, body_of, max_qi, roll_body, settle, to_dict
from world.db import World
from world.seed import rng_for


def npc_body(world: World, entity) -> Body:
    key = entity.seed_path or f"entity:{entity.id}"
    rng = rng_for(world.world_seed, f"{key}/body")
    body = roll_body(rng)
    body.realm = realm_index(entity.data.get("realm", "mortal"))
    low, high = REALMS[body.realm].threshold, next_threshold(body.realm)
    body.energy_years = round(low + ((high - low) * rng.uniform(0.0, 0.6) if high else 0.0), 3)
    if body.realm >= 1:
        body.flags.append("sensed_qi")
    for name in ("Governing", "Conception")[: max(0, body.realm - 1)]:
        body.meridians[name].state, body.meridians[name].flow = "open", 0.3
    body.qi = max_qi(body)
    body.settled_at = world.time
    return body


def ensure_body(world: World, person_id: int) -> Body:
    """The person's body brought up to now; created from their seed if they have none."""
    entity = world.entity(person_id)
    existing = body_of(entity)
    if existing is not None:
        return settle(existing, world.time)
    body = npc_body(world, entity)
    world.update_data(person_id, body=to_dict(body))
    return body


def load_body(world: World, person_id: int) -> Body:
    return ensure_body(world, person_id)


def save_body(world: World, person_id: int, body: Body) -> None:
    body.qi = max(0.0, min(body.qi, max_qi(body)))
    world.update_data(person_id, body=to_dict(body), realm=REALMS[body.realm].label)
```
`systems/creation.py`:
```python
"""Character creation (phase 2 spec §7): an origin, pure chance, or point-buy.

Creation is generation, like materializing a town: it writes the body, purse
and starting arts directly. Every mode rolls a hidden constitution.
"""

from dataclasses import dataclass, field

from systems.techniques import FORMS, create_technique, generate, teach
from world.body import PHYSIQUE, Body, roll_body, to_dict
from world.db import World
from world.events import Event, effect
from world.seed import rng_for


@dataclass(frozen=True)
class Origin:
    key: str
    title: str
    description: str
    heart_grade: int
    heart_element: str | None
    art_forms: tuple[str, ...]
    bias: dict = field(default_factory=dict)
    silver: int = 0
    heart_completeness: float = 1.0  # below 1.0 the family method is secretly incomplete


ORIGINS = {
    "hunter": Origin("hunter", "Hunter's child", "Raised on game trails; strong legs and a steady spear.",
                     1, None, ("spear", "fist"), {"strength": 2, "endurance": 2}, 30),
    "scion": Origin("scion", "Fallen clan scion", "Born to a ruined martial clan; the family method survived the fall.",
                    2, None, ("sword",), {"comprehension": 2, "scarred": 1}, 80, 0.8),
    "temple": Origin("temple", "Temple orphan", "Raised by monks on chanting, cold water and a single palm art.",
                     1, "yang", ("palm", "staff"), {"purity": 0.1, "endurance": 2}, 10),
    "merchant": Origin("merchant", "Merchant's runaway", "Fled a counting-house with quick feet and a fat purse.",
                       1, None, ("footwork",), {"agility": 2}, 200),
    "beggar": Origin("beggar", "Beggar-sect urchin", "Grew up in the alleys among ragged, dangerous masters.",
                     1, None, ("staff", "fist"), {"agility": 2, "comprehension": 1}, 5),
}
WANDERER = Origin("wanderer", "Wanderer", "A drifter with a little training and less money.",
                  1, None, ("fist", "sword", "palm"), {}, 20)
MODES = ("random", "origin", "point_buy")
POINT_BASE, POINT_POOL, POINT_MAX, FLOW_POINT_COST = 8, 12, 16, 2


@dataclass(frozen=True)
class CreationChoice:
    mode: str = "random"
    origin: str | None = None
    physique: tuple[tuple[str, int], ...] | None = None
    flow_points: int = 0
    form: str | None = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode, "origin": self.origin,
            "physique": dict(self.physique) if self.physique else None,
            "flow_points": self.flow_points, "form": self.form,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CreationChoice":
        physique = data.get("physique")
        return cls(
            data.get("mode", "random"), data.get("origin"),
            tuple(physique.items()) if physique else None,
            data.get("flow_points", 0), data.get("form"),
        )


@dataclass
class Creation:
    origin: Origin
    body: Body
    arts: list        # [(name, data, true completeness)]
    silver: int


def points_spent(physique: dict, flow_points: int) -> int:
    return sum(physique[p] - POINT_BASE for p in PHYSIQUE) + flow_points * FLOW_POINT_COST


def point_buy_problem(physique: dict, flow_points: int) -> str | None:
    if set(physique) != set(PHYSIQUE):
        return "Every attribute needs a value."
    for name in PHYSIQUE:
        if not POINT_BASE <= physique[name] <= POINT_MAX:
            return f"{name} must be between {POINT_BASE} and {POINT_MAX}."
    if flow_points < 0:
        return "Meridian openness cannot be negative."
    spent = points_spent(physique, flow_points)
    if spent > POINT_POOL:
        return f"{spent} points spent; only {POINT_POOL} available."
    return None


def build(world_seed: int, choice: CreationChoice) -> Creation:
    rng = rng_for(world_seed, "creation")
    if choice.mode == "origin":
        origin = WANDERER if choice.origin == "wanderer" else ORIGINS.get(choice.origin)
        if origin is None:
            raise ValueError(f"unknown origin {choice.origin!r}")
        body = roll_body(rng, bias=origin.bias)
    elif choice.mode == "point_buy":
        physique = dict(choice.physique or ())
        problem = point_buy_problem(physique, choice.flow_points)
        if problem:
            raise ValueError(problem)
        if choice.form not in FORMS:
            raise ValueError(f"choose a form from {FORMS}")
        origin = Origin("self_made", "Self-made", "Shaped by will alone.", 1, None, (choice.form,), {}, 50)
        body = roll_body(rng, physique=physique, flow_bonus=0.1 * choice.flow_points)
    elif choice.mode == "random":
        origin = ORIGINS[rng.choice(sorted(ORIGINS))]
        body = roll_body(rng)
    else:
        raise ValueError(f"unknown creation mode {choice.mode!r}")
    heart_name, heart = generate(rng, "heart_method", grade=origin.heart_grade, element=origin.heart_element)
    art_name, art = generate(rng, "martial", form=rng.choice(origin.art_forms), grade=1)
    return Creation(origin, body, [(heart_name, heart, origin.heart_completeness), (art_name, art, 1.0)], origin.silver)


def apply_creation(world: World, person_id: int, creation: Creation) -> list[str]:
    """Write body, purse and starting arts onto a person. Returns the art names."""
    creation.body.settled_at = world.time
    world.update_data(
        person_id, body=to_dict(creation.body), silver=creation.silver, realm="mortal",
        origin=creation.origin.key, origin_title=creation.origin.title,
    )
    names = []
    for name, data, completeness in creation.arts:
        technique = create_technique(world, name, data)
        teach(world, person_id, technique, completeness=completeness, known_completeness=1.0, source="origin")
        names.append(name)
    return names


def wanderer_arts(world_seed: int) -> list[str]:
    return [name for name, _, _ in build(world_seed, CreationChoice("origin", "wanderer")).arts]


@effect("body_awakened")
def _awaken(world: World, event: Event) -> None:
    """A save from before bodies existed: give its hero one."""
    apply_creation(world, event.actors[0], build(world.world_seed, CreationChoice("origin", "wanderer")))
```
In `engine/game.py`:
- Add these imports: `from systems.creation import CreationChoice, apply_creation, build, wanderer_arts`.
- Replace the whole `new` and `load` methods with:
```
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
        return game
```

- [ ] **Step 4: Run tests** → `tests/test_creation.py` PASS (7 passed), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: character creation modes, lazy NPC bodies, old-save migration" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 5: Cultivation actions

**Files:**
- Create: `systems/cultivation.py`
- Modify: `systems/time.py` (add `days_word`)
- Test: `tests/test_cultivation.py`

**Interfaces:**
- Consumes: Tasks 1–4
- Produces:
  - In `systems/time.py`: `days_word(days) -> str`, giving "a day", "a week", "a month", "a season", or "N days".
  - In `systems/cultivation.py`:
    - Constants: `BASE_RATE=0.015`, `MEDITATE_OPTIONS={"day":1,"week":7,"month":30,"season":90}`, `SECLUSION_DAYS=30`, `SENSE_QI_DAYS=7`, `PRACTISE_DAYS=7`, `OPEN_DAYS=7`, `REST_DAYS=7`, `FORCE_CHANCE=0.03`, `DEVIATION_LIMIT=100`, `DEVIATION_AFTER=40`
    - Helpers: `energy_rate(body, heart_data, days, now) -> float` (years per day), `opening_requirement(body) -> float`, `why_not_open(body, name) -> str | None`
    - Event builders, each returning `list[Event]` (empty when the action is impossible):
      - `meditate_events(world, pid, place, days)`
      - `practise_events(world, pid, place, technique_id, days=7)`
      - `open_meridian_events(world, pid, place, name, days=7)`
      - `rest_events(world, pid, place, days=7)`
      - `breakthrough_events(world, pid, place)`
    - Event kinds and their data:

| Kind | Data |
|---|---|
| `cultivated` | `{days, energy_gained, sensed_qi, stage_before, stage_after, reached_bottleneck, deviation_added, method}` |
| `practised` | `{technique, technique_id, days, mastery_before, mastery_after, stage_before, stage_after, compat, stalled, deviation_added, insight_gained, discovered}` |
| `opening_meridian` | `{meridian, days, progress_before, progress_after, opened, forced, forced_damage, deviation_added}` |
| `rested` | `{days, healed}` |
| `breakthrough` | `{success, realm_before, realm_after, target, requirement, met, chance, damaged, discovered}` |
| `deviation` | `{cause, damaged, energy_lost, discovered}` |

- [ ] **Step 1: Write the failing test** — `tests/test_cultivation.py`
```python
import statistics

import pytest

import systems.cultivation as cultivation
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.techniques import create_technique, martial_arts, teach
from systems.time import days_word
from world.body import add_injury
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=3, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def ids(game):
    return game.world, game.player.id, game.place.id


def edit_body(game, **changes):
    world, pid, _ = ids(game)
    body = load_body(world, pid)
    for key, value in changes.items():
        setattr(body, key, value)
    save_body(world, pid, body)
    return body


def run(game, events):
    commit(game.world, events)
    return load_body(game.world, game.player.id)


def test_days_word():
    assert [days_word(d) for d in (1, 7, 30, 90, 12)] == ["a day", "a week", "a month", "a season", "12 days"]


def test_meditation_builds_energy_and_senses_qi(game):
    world, pid, place = ids(game)
    [event] = cultivation.meditate_events(world, pid, place, 7)
    assert event.kind == "cultivated" and event.data["sensed_qi"] and event.data["energy_gained"] > 0
    body = run(game, [event])
    assert "sensed_qi" in body.flags and body.energy_years == pytest.approx(event.data["energy_gained"])
    assert world.time == 7 * 4


def test_seclusion_is_faster_per_day(game):
    world, pid, place = ids(game)
    week = cultivation.meditate_events(world, pid, place, 7)[0].data["energy_gained"] / 7
    month = cultivation.meditate_events(world, pid, place, 30)[0].data["energy_gained"] / 30
    assert month == pytest.approx(week * 1.2, rel=0.01)


def test_pacing_mortal_to_third_rate(tmp_path):
    days_needed = []
    for seed in range(50):
        g = Game.new(tmp_path / f"{seed}.world", "Hero", world_seed=seed, creation=CreationChoice("origin", "hunter"))
        world, pid, place = ids(g)
        days = 0
        while not load_body(world, pid).bottleneck and days < 1000:
            commit(world, cultivation.meditate_events(world, pid, place, 7))
            days += 7
        days_needed.append(days)
        g.close()
    assert 60 <= statistics.median(days_needed) <= 150, days_needed
    assert sorted(days_needed)[44] <= 250, days_needed  # 90th percentile


def test_bottleneck_and_breakthrough_success(game, monkeypatch):
    world, pid, place = ids(game)
    edit_body(game, energy_years=0.99, flags=["sensed_qi"])
    run(game, cultivation.meditate_events(world, pid, place, 30))
    body = load_body(world, pid)
    assert body.bottleneck and body.energy_years == 1.0
    monkeypatch.setattr(cultivation.realms, "breakthrough_chance", lambda b, met: 1.0)
    events = cultivation.breakthrough_events(world, pid, place)
    assert events[0].data["success"] and events[0].data["met"]
    body = run(game, events)
    assert body.realm == 1 and not body.bottleneck
    assert world.entity(pid).data["realm"] == "third-rate"


def test_breakthrough_failure_hurts(game, monkeypatch):
    world, pid, place = ids(game)
    edit_body(game, energy_years=1.0, bottleneck=True, flags=[])
    monkeypatch.setattr(cultivation.realms, "breakthrough_chance", lambda b, met: 0.0)
    events = cultivation.breakthrough_events(world, pid, place)
    event = events[0]
    assert not event.data["success"] and not event.data["met"] and event.data["damaged"]
    body = run(game, events)
    assert body.realm == 0 and body.energy_years == pytest.approx(0.95)
    assert all(body.meridians[m].state == "damaged" for m in event.data["damaged"])
    assert body.deviation == pytest.approx(30)


def test_no_breakthrough_without_bottleneck(game):
    assert cultivation.breakthrough_events(*ids(game)) == []


def test_practise_raises_mastery_to_the_completeness_cap(game):
    world, pid, place = ids(game)
    art = martial_arts(world, pid)[0]
    [event] = cultivation.practise_events(world, pid, place, art.technique.id)
    assert event.data["mastery_after"] > event.data["mastery_before"]
    run(game, [event])
    assert martial_arts(world, pid)[0].mastery == pytest.approx(event.data["mastery_after"])
    flawed = create_technique(world, "Broken Scroll Fist", dict(art.technique.data, form="fist"))
    teach(world, pid, flawed, completeness=0.3, known_completeness=1.0, source="manual", mastery=0.3)
    [event] = cultivation.practise_events(world, pid, place, flawed)
    assert event.data["stalled"] and event.data["mastery_after"] == pytest.approx(0.3)
    assert event.data["deviation_added"] >= 10.5


def test_deviation_strikes_at_the_limit(game):
    world, pid, place = ids(game)
    art = martial_arts(world, pid)[0]
    teach(world, pid, art.technique.id, completeness=0.05, mastery=0.05)
    edit_body(game, deviation=99.0)
    events = cultivation.practise_events(world, pid, place, art.technique.id)
    assert [e.kind for e in events] == ["practised", "deviation"]
    body = run(game, events)
    assert body.deviation == pytest.approx(40)
    assert any(body.meridians[m].state in ("damaged", "scarred") for m in events[1].data["damaged"])


def test_opening_a_meridian(game, monkeypatch):
    world, pid, place = ids(game)
    assert "need" in cultivation.why_not_open(load_body(world, pid), "Governing")
    edit_body(game, energy_years=2.5, realm=1,
              physique={"strength": 10, "agility": 10, "endurance": 10, "comprehension": 10})
    monkeypatch.setattr(cultivation, "FORCE_CHANCE", 0.0)
    weeks = 0
    while load_body(world, pid).meridians["Governing"].state == "blocked":
        run(game, cultivation.open_meridian_events(world, pid, place, "Governing"))
        weeks += 1
        assert weeks < 60
    body = load_body(world, pid)
    assert body.meridians["Governing"].flow == 0.3
    assert "already open" in cultivation.why_not_open(body, "Governing")


def test_forcing_a_meridian_can_damage_another(game, monkeypatch):
    world, pid, place = ids(game)
    edit_body(game, energy_years=2.5, realm=1)
    monkeypatch.setattr(cultivation, "FORCE_CHANCE", 1.0)
    [event] = cultivation.open_meridian_events(world, pid, place, "Conception")
    assert event.data["forced"] and event.data["forced_damage"]
    body = run(game, [event])
    assert body.meridians[event.data["forced_damage"]].state == "damaged"
    assert body.deviation == pytest.approx(15)


def test_rest_speeds_healing(game):
    world, pid, place = ids(game)
    body = load_body(world, pid)
    injury = add_injury(body, "left arm", "cut", 3, world.time, "a test")
    save_body(world, pid, body)
    body = run(game, cultivation.rest_events(world, pid, place))
    still = [i.heals_at for i in body.injuries if i.id == injury.id]
    assert not still or still[0] < injury.heals_at


def test_constitution_is_discovered_at_breakthrough(game, monkeypatch):
    world, pid, place = ids(game)
    edit_body(game, energy_years=1.0, bottleneck=True, flags=["sensed_qi"],
              constitution="Dragon Vein Body", constitution_known=False)
    monkeypatch.setattr(cultivation.realms, "breakthrough_chance", lambda b, met: 1.0)
    events = cultivation.breakthrough_events(world, pid, place)
    assert events[0].data["discovered"] == "Dragon Vein Body"
    assert run(game, events).constitution_known
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ImportError: cannot import name 'days_word'`, or no `systems.cultivation`)

- [ ] **Step 3: Implement**

Append this to the end of the time module (systems, time):
```
DAY_WORDS = {1: "a day", 7: "a week", 30: "a month", 90: "a season"}


def days_word(days: int) -> str:
    return DAY_WORDS.get(days, f"{days} days")
```
`systems/cultivation.py`:
```python
"""Cultivation actions (phase 2 spec §6).

Each builder computes the whole outcome from seeded randomness and puts it in
the Event's data; the effect advances time, then applies exactly that. So a
replay, the journal and the narrator's brief all see the same result.
"""

from systems import realms
from systems.bodies import load_body, save_body
from systems.techniques import compatibility, grade_mult, heart_method, known_arts, mastery_stage, practise_gain, set_mastery
from systems.time import advance
from world.body import EXTRAORDINARY, REGULAR, WATCHES_PER_DAY, add_injury, clone, max_qi, unhealed
from world.events import Event, effect
from world.seed import rng_for

BASE_RATE = 0.015
MEDITATE_OPTIONS = {"day": 1, "week": 7, "month": 30, "season": 90}
SECLUSION_DAYS = 30
SENSE_QI_DAYS = 7
PRACTISE_DAYS = 7
OPEN_DAYS = 7
REST_DAYS = 7
BREAKTHROUGH_DAYS = 1
FORCE_CHANCE = 0.03
DEVIATION_LIMIT = 100
DEVIATION_AFTER = 40
CONSTITUTION_RATE = {"Dragon Vein Body": 1.25, "Myriad Poison Body": 1.1}
CONSTITUTION_ELEMENT = {"Nine Yin Body": "yin", "Pure Yang Body": "yang"}
CONSTITUTION_FORM = {"Heavenly Sword Bones": "sword"}
OPPOSITE = {"yin": "yang", "yang": "yin"}


def _rng(world, pid: int, what: str):
    return rng_for(world.world_seed, f"cultivate:{what}:{pid}:{world.time}")


def route_flow(body, route) -> float:
    flows = [body.meridians[m].flow if body.meridians[m].state in ("open", "scarred") else 0.0 for m in route]
    return sum(flows) / len(flows) if flows else 0.0


def energy_rate(body, heart_data: dict | None, days: int, now: int) -> float:
    """Years of internal energy gained per day of meditation."""
    if heart_data is None:
        grade, flow = 0.5, route_flow(body, REGULAR)  # crude breathing, no method
    else:
        grade, flow = grade_mult(heart_data["grade"]), route_flow(body, heart_data["route"])
    rate = BASE_RATE * grade * (body.physique["comprehension"] / 10) * (0.5 + body.purity) * flow
    if days >= SECLUSION_DAYS:
        rate *= 1.2
    if any(i.kind == "internal" for i in unhealed(body, now)):
        rate *= 0.5
    rate *= CONSTITUTION_RATE.get(body.constitution, 1.0)
    if heart_data is not None and CONSTITUTION_ELEMENT.get(body.constitution) == heart_data["element"]:
        rate *= 1.5
    return rate


def _deviation_from(body, data: dict, days: int) -> float:
    extra = days * max(0.0, 0.5 - compatibility(body, data)) * 2
    element = CONSTITUTION_ELEMENT.get(body.constitution)
    if element and data["element"] == OPPOSITE[element]:
        extra += days * 0.5
    return round(extra, 3)


def _discovers(body, trigger: str, data: dict | None = None, mastery_after: float = 0.0) -> str | None:
    if body.constitution is None or body.constitution_known:
        return None
    if trigger in ("breakthrough", "deviation"):
        return body.constitution
    if trigger == "practise" and mastery_after >= 0.34 and data is not None:
        if CONSTITUTION_FORM.get(body.constitution) == data["form"] or CONSTITUTION_ELEMENT.get(body.constitution) == data["element"]:
            return body.constitution
    return None


def _deviation_event(world, pid: int, place: int, body, deviation_now: float, route, cause: str) -> list[Event]:
    if deviation_now < DEVIATION_LIMIT:
        return []
    rng = _rng(world, pid, "deviation")
    candidates = [m for m in route if m in body.meridians and body.meridians[m].state in ("open", "damaged")]
    damaged = rng.sample(candidates, min(len(candidates), rng.randint(1, 2))) if candidates else []
    data = {"cause": cause, "damaged": damaged, "energy_lost": round(body.energy_years * 0.1, 5),
            "discovered": _discovers(body, "deviation")}
    return [Event("deviation", (pid,), place, data)]


def _floor_energy(body) -> None:
    """Keep energy inside the current realm and recompute the bottleneck."""
    body.energy_years = max(realms.REALMS[body.realm].threshold, body.energy_years)
    realms.add_energy(body, 0.0)


# --- meditation ---------------------------------------------------------------

def meditate_events(world, pid: int, place: int, days: int) -> list[Event]:
    body = load_body(world, pid)
    heart = heart_method(world, pid)
    heart_data = heart.technique.data if heart else None
    trial = clone(body)
    gained = realms.add_energy(trial, energy_rate(body, heart_data, days, world.time) * days)
    deviation = _deviation_from(body, heart_data, days) if heart_data else 0.0
    data = {
        "days": days, "energy_gained": round(gained, 6),
        "sensed_qi": "sensed_qi" not in body.flags and body.meditated_days + days >= SENSE_QI_DAYS,
        "stage_before": realms.stage_of(body), "stage_after": realms.stage_of(trial),
        "reached_bottleneck": trial.bottleneck and not body.bottleneck,
        "deviation_added": deviation, "method": heart.name if heart else None,
    }
    route = heart_data["route"] if heart_data else list(REGULAR)
    cause = f"cultivating the {heart.name} against your body's grain" if heart else "breathing without a method"
    return [Event("cultivated", (pid,), place, data)] + _deviation_event(world, pid, place, body, body.deviation + deviation, route, cause)


@effect("cultivated")
def _cultivated(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    advance(world, data["days"] * WATCHES_PER_DAY)
    body = load_body(world, pid)
    realms.add_energy(body, data["energy_gained"])
    if data["sensed_qi"] and "sensed_qi" not in body.flags:
        body.flags.append("sensed_qi")
    body.meditated_days += data["days"]
    body.deviation = min(100.0, body.deviation + data["deviation_added"])
    body.qi = max_qi(body)
    save_body(world, pid, body)


# --- practice -----------------------------------------------------------------

def practise_events(world, pid: int, place: int, technique_id: int, days: int = PRACTISE_DAYS) -> list[Event]:
    body = load_body(world, pid)
    known = next((a for a in known_arts(world, pid) if a.technique.id == technique_id), None)
    if known is None or known.category != "martial":
        return []
    art = known.technique.data
    compat = compatibility(body, art)
    gain = practise_gain(days, body.physique["comprehension"], compat, art["grade"])
    if CONSTITUTION_FORM.get(body.constitution) == art["form"]:
        gain *= 1.5
    at_cap = known.mastery >= known.completeness - 1e-9
    after = min(known.completeness, known.mastery + gain)
    deviation = _deviation_from(body, art, days) + (days * 1.5 if at_cap else 0.0)
    data = {
        "technique": known.name, "technique_id": technique_id, "days": days,
        "mastery_before": round(known.mastery, 6), "mastery_after": round(after, 6),
        "stage_before": mastery_stage(known.mastery), "stage_after": mastery_stage(after),
        "compat": compat, "stalled": at_cap, "deviation_added": round(deviation, 3),
        "insight_gained": round(days * 0.05 * body.physique["comprehension"] / 10, 4),
        "discovered": _discovers(body, "practise", art, after),
    }
    cause = (f"forcing the {known.name} beyond what it can give" if at_cap
             else f"practising the {known.name} against your body's grain")
    return [Event("practised", (pid,), place, data)] + _deviation_event(world, pid, place, body, body.deviation + deviation, art["route"], cause)


@effect("practised")
def _practised(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    advance(world, data["days"] * WATCHES_PER_DAY)
    set_mastery(world, pid, data["technique_id"], data["mastery_after"])
    body = load_body(world, pid)
    body.insight += data["insight_gained"]
    body.deviation = min(100.0, body.deviation + data["deviation_added"])
    if data["discovered"]:
        body.constitution_known = True
    save_body(world, pid, body)


# --- opening extraordinary meridians --------------------------------------------

def opening_requirement(body) -> float:
    return 2 + 3 * sum(1 for m in EXTRAORDINARY if body.meridians[m].state == "open")


def why_not_open(body, name: str) -> str | None:
    if name not in EXTRAORDINARY:
        return f"{name} is not an extraordinary meridian."
    if body.meridians[name].state != "blocked":
        return f"Your {name} meridian is already {body.meridians[name].state}."
    need = opening_requirement(body)
    if body.energy_years < need:
        return f"You need {realms.energy_words(need)} before you can force open another extraordinary meridian."
    return None


def open_meridian_events(world, pid: int, place: int, name: str, days: int = OPEN_DAYS) -> list[Event]:
    body = load_body(world, pid)
    if why_not_open(body, name):
        return []
    rng = _rng(world, pid, "open")
    before = body.meridians[name].opening
    after = min(1.0, before + days * 0.01 * body.physique["comprehension"] / 10)
    forced = rng.random() < FORCE_CHANCE
    victims = [m for m in REGULAR if body.meridians[m].state == "open"]
    victim = rng.choice(victims) if forced and victims else None
    deviation = 15.0 if forced else 0.0
    data = {
        "meridian": name, "days": days, "progress_before": round(before, 6), "progress_after": round(after, 6),
        "opened": after >= 1.0, "forced": forced, "forced_damage": victim, "deviation_added": deviation,
    }
    return [Event("opening_meridian", (pid,), place, data)] + _deviation_event(
        world, pid, place, body, body.deviation + deviation, list(REGULAR), "forcing qi into a sealed meridian")


@effect("opening_meridian")
def _opening(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    advance(world, data["days"] * WATCHES_PER_DAY)
    body = load_body(world, pid)
    meridian = body.meridians[data["meridian"]]
    meridian.opening = data["progress_after"]
    if data["opened"]:
        meridian.state, meridian.flow, meridian.opening = "open", 0.3, 1.0
    if data["forced_damage"]:
        add_injury(body, data["forced_damage"], "meridian", 2, world.time, f"forcing open the {data['meridian']} meridian")
    body.deviation = min(100.0, body.deviation + data["deviation_added"])
    save_body(world, pid, body)


# --- rest ---------------------------------------------------------------------------

def rest_events(world, pid: int, place: int, days: int = REST_DAYS) -> list[Event]:
    body = load_body(world, pid)
    now, end = world.time, world.time + days * WATCHES_PER_DAY
    healed = [i.location for i in unhealed(body, now) if not i.permanent and now + (i.heals_at - now) // 2 <= end]
    return [Event("rested", (pid,), place, {"days": days, "healed": healed})]


@effect("rested")
def _rested(world, event: Event) -> None:
    pid, days, now = event.actors[0], event.data["days"], world.time
    body = load_body(world, pid)
    for injury in body.injuries:
        if not injury.permanent and injury.heals_at is not None:
            injury.heals_at = now + (injury.heals_at - now) // 2
    for meridian in body.meridians.values():
        if meridian.state == "damaged" and meridian.heals_at is not None:
            meridian.heals_at = now + (meridian.heals_at - now) // 2
    body.deviation = max(0.0, body.deviation - 0.5 * days)  # on top of the usual fading
    save_body(world, pid, body)
    advance(world, days * WATCHES_PER_DAY)


# --- breakthrough -----------------------------------------------------------------

def breakthrough_events(world, pid: int, place: int) -> list[Event]:
    body = load_body(world, pid)
    if not body.bottleneck or body.realm >= realms.MAX_REALM:
        return []
    met, requirement = realms.requirement(body, known_arts(world, pid))
    rng = _rng(world, pid, "breakthrough")
    chance = realms.breakthrough_chance(body, met)
    success = rng.random() < chance
    damaged = []
    if not success:
        heart = heart_method(world, pid)
        route = heart.technique.data["route"] if heart else list(REGULAR)
        candidates = [m for m in route if body.meridians[m].state == "open"]
        damaged = rng.sample(candidates, min(len(candidates), rng.randint(1, 2)))
    target = realms.REALMS[body.realm + 1].name
    data = {
        "success": success, "realm_before": body.realm, "realm_after": body.realm + (1 if success else 0),
        "target": target, "requirement": requirement, "met": met, "chance": chance,
        "damaged": damaged, "discovered": _discovers(body, "breakthrough"),
    }
    events = [Event("breakthrough", (pid,), place, data)]
    if not success:
        events += _deviation_event(world, pid, place, body, body.deviation + 30, damaged or list(REGULAR), "a failed breakthrough")
    return events


@effect("breakthrough")
def _breakthrough(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    advance(world, BREAKTHROUGH_DAYS * WATCHES_PER_DAY)
    body = load_body(world, pid)
    if data["success"]:
        body.realm += 1
        body.purity = min(1.0, round(body.purity + 0.05, 3))
        realms.add_energy(body, 0.0)
        body.qi = max_qi(body)
    else:
        for name in data["damaged"]:
            add_injury(body, name, "meridian", 3, world.time, f"the failed breakthrough to {data['target']}")
        body.energy_years *= 0.95
        _floor_energy(body)
        body.deviation = min(100.0, body.deviation + 30)
    if data["discovered"]:
        body.constitution_known = True
    save_body(world, pid, body)


@effect("deviation")
def _deviation(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    body = load_body(world, pid)
    for name in data["damaged"]:
        if body.meridians[name].state == "open":
            add_injury(body, name, "meridian", 3, world.time, data["cause"])
        elif body.meridians[name].state == "damaged":
            body.meridians[name].state, body.meridians[name].heals_at = "scarred", None
    body.energy_years -= data["energy_lost"]
    _floor_energy(body)
    body.deviation = float(DEVIATION_AFTER)
    if data["discovered"]:
        body.constitution_known = True
    save_body(world, pid, body)
```

- [ ] **Step 4: Run tests** → `tests/test_cultivation.py` PASS (14 passed), and the full suite passes. If the pacing test fails, **do not** loosen its band (it is spec §6's binding target). Tune `BASE_RATE`, ledger the new value as a ruling, and update the spec in Task 10.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: cultivation - meditation, practice, meridians, rest, breakthrough, deviation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 6: Briefs, prose and journal for the body

**Files:**
- Rewrite: `narrate/brief.py`, `narrate/procedural.py`, `engine/journal.py`
- Create: `narrate/grammar/body.toml`
- Modify (test): add `"body_awakened"` to `ONE_OFF_KEYS` in `tests/test_repeat.py`
- Test: `tests/test_brief_body.py`

**Interfaces:**
- Consumes: Tasks 1–5
- Produces:
  - `Brief.outcome: tuple[str, ...]` is a new **last** field (default `()`), so positional construction keeps working.
    - `to_prompt()` adds an `OUTCOME:` section.
    - Limits: `MAX_OUTCOME = 4`.
  - `player_facts(world, pid) -> list[str]`, ranked:
    1. permanent injuries;
    2. severed, then scarred meridians;
    3. unhealed injuries;
    4. unruly deviation;
    5. a known constitution;
    6. always last: the realm sentence.
  - `BODY_KINDS`, plus `growth_words(g)` and `progress_words(p)`.
  - Body-kind briefs carry `outcome` lines, `details`, and `facts = player_facts(...)`.
  - The procedural narrator appends each outcome line as a `(text, "dim")` line after the prose line.
    - The key for `breakthrough` is `breakthrough.success` or `breakthrough.failure`, from `details["success"]` being `"yes"` or `"no"`.
  - The journal summarises every new kind.

- [ ] **Step 1: Write the failing test** — `tests/test_brief_body.py`
```python
import pytest

import systems.cultivation as cultivation
from engine.game import Game
from engine.journal import summarize
from narrate.brief import MAX_PROMPT, event_brief, player_facts
from narrate.procedural import ProceduralNarrator
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import add_injury
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=3, creation=CreationChoice("origin", "scion"))
    yield g
    g.close()


def commit_and_brief(game, events):
    ids = commit(game.world, events)
    return [event_brief(game.world, i, e) for i, e in zip(ids, events)]


def test_opening_tells_origin_and_arts(game):
    text = " ".join(t for t, _ in game.start().lines)
    assert "Fallen clan scion" in text and "You know the" in text


def test_meditation_brief_has_outcome_and_realm(game):
    [brief] = commit_and_brief(game, cultivation.meditate_events(game.world, game.player.id, game.place.id, 7))
    assert brief.player.realm == "Mortal"
    assert brief.outcome[0].startswith("You meditated for a week")
    assert any("sensed the qi" in o for o in brief.outcome)
    prompt = brief.to_prompt()
    assert "OUTCOME:" in prompt and len(prompt) <= MAX_PROMPT


def test_player_facts_rank_permanent_injuries_first(game):
    world, pid = game.world, game.player.id
    body = load_body(world, pid)
    add_injury(body, "left arm", "cut", 2, world.time, "a training accident")
    add_injury(body, "right leg", "fracture", 5, world.time, "Peng Haoming's staff", permanent=True)
    body.deviation = 70
    save_body(world, pid, body)
    facts = player_facts(world, pid)
    assert facts[0] == "Your right leg never healed from Peng Haoming's staff."
    assert any("left arm" in f and "to heal" in f for f in facts)
    assert any("unruly" in f for f in facts)
    assert facts[-1].startswith("You are still a mortal")


def test_hidden_truths_never_reach_the_prompt(game):
    world, pid, place = game.world, game.player.id, game.place.id
    body = load_body(world, pid)
    body.constitution, body.constitution_known = "Nine Yin Body", False
    save_body(world, pid, body)
    [brief] = commit_and_brief(game, cultivation.meditate_events(world, pid, place, 7))
    prompt = brief.to_prompt()
    assert "Nine Yin" not in prompt and "0.8" not in prompt and "80%" not in prompt


def test_breakthrough_narration(game, monkeypatch):
    world, pid, place = game.world, game.player.id, game.place.id
    body = load_body(world, pid)
    body.energy_years, body.bottleneck = 1.0, True
    body.flags.append("sensed_qi")
    save_body(world, pid, body)
    monkeypatch.setattr(cultivation.realms, "breakthrough_chance", lambda b, met: 1.0)
    [brief] = commit_and_brief(game, cultivation.breakthrough_events(world, pid, place))
    assert brief.details["success"] == "yes" and "You broke through to Third-rate!" in brief.outcome
    lines = ProceduralNarrator().narrate(brief)
    assert lines[0][1] != "dim" and ("You broke through to Third-rate!", "dim") in lines


def test_journal_summaries(game):
    world, pid, place = game.world, game.player.id, game.place.id
    commit(world, cultivation.meditate_events(world, pid, place, 30))
    assert summarize(world, world.chronicle_about(pid, limit=1)[0]).endswith("Meditated for a month.")


def test_awakened_old_save_is_narrated(tmp_path):
    path = tmp_path / "old.world"
    game = Game.new(path, "Hero", world_seed=5)
    pid = game.player.id
    game.world._conn.execute("update entities set data = json_remove(data, '$.body') where id = ?", (pid,))
    game.world._conn.execute("delete from relations where a = ? and kind = 'knows'", (pid,))
    game.close()
    game = Game.load(path)
    assert "take stock" in " ".join(t for t, _ in game.start().lines).lower()
    game.close()
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ImportError: cannot import name 'player_facts'`)

- [ ] **Step 3: Implement**

`narrate/brief.py`:
```python
"""Briefs: the engine's pre-digested account of one moment.

All recall and relevance judgement happens here, in tested code. A narrator,
whether a grammar or a small model like Haiku, only has to phrase these facts.
Rules: no entity ids, only what the player knows, ranked facts, short.
`outcome` is what the player must be told happened; `facts` is context.
"""

from dataclasses import dataclass, field

from systems.bodies import load_body
from systems.realms import REALMS, energy_words, realm_title, stage_of
from systems.talk import conversations_with, times_asked
from systems.techniques import compat_words
from systems.time import WATCH_NAMES, days_word, format_date, format_season_year, season_of
from world.body import body_of, unhealed
from world.db import Entity, World
from world.gen.materialize import people_at, region_of
from world.gen.town import town_path

MAX_FACTS = 6
MAX_OUTCOME = 4
MAX_PROMPT = 1200
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")
NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
BODY_KINDS = frozenset({
    "began", "body_awakened", "cultivated", "practised", "opening_meridian", "rested", "breakthrough", "deviation",
})
INJURY_WORDS = {"bruise": "bruised", "cut": "cut", "fracture": "fractured", "internal": "hurt inside", "meridian": "damaged"}


@dataclass(frozen=True)
class PlaceBrief:
    name: str
    kind: str
    region: str
    terrain: str
    season: str
    watch: str


@dataclass(frozen=True)
class PersonBrief:
    name: str
    role: str
    traits: tuple[str, ...]
    realm: str
    toward_player: str


@dataclass(frozen=True)
class Brief:
    kind: str
    when: str
    place: PlaceBrief
    player: PersonBrief
    other: PersonBrief | None
    details: dict[str, str] = field(default_factory=dict)
    facts: tuple[str, ...] = ()
    seed: int = 0   # deterministic procedural text only; never shown to a model
    salt: str = ""
    outcome: tuple[str, ...] = ()

    def to_prompt(self) -> str:
        p = self.place
        lines = [
            f"EVENT: {self.kind}",
            f"WHEN: {self.when}",
            f"WHERE: {p.name} ({p.kind}) in {p.region}; {p.terrain}; {p.season}; {p.watch}",
            f"YOU: {self.player.name}, {self.player.realm}",
        ]
        if self.other is not None:
            o = self.other
            traits = ", ".join(o.traits) or "unremarkable"
            lines.append(f"THEM: {o.name}, {o.role}; {traits}; {o.realm}; to you: {o.toward_player}")
        if self.details:
            lines.append("DETAILS: " + "; ".join(f"{k}={v}" for k, v in sorted(self.details.items())))
        if self.outcome:
            lines.append("OUTCOME:")
            lines += [f"- {line}" for line in self.outcome[:MAX_OUTCOME]]
        lines.append("FACTS:")
        lines += [f"- {fact}" for fact in self.facts[:MAX_FACTS]]
        return "\n".join(lines)[:MAX_PROMPT]


def ordinal(n: int) -> str:
    return ORDINALS[n - 1] if 1 <= n <= len(ORDINALS) else f"{n}th"


def days_phrase(watches: int) -> str:
    days = max(1, watches // 4)
    if days == 1:
        return "a day"
    return f"{NUMBER_WORDS[days - 1] if days <= len(NUMBER_WORDS) else days} days"


def growth_words(gained: float) -> str:
    if gained < 0.02:
        return "by a trickle"
    if gained < 0.1:
        return "a little"
    if gained < 0.5:
        return "noticeably"
    return "greatly"


def progress_words(progress: float) -> str:
    if progress < 0.25:
        return "it barely stirs"
    if progress < 0.5:
        return "a thread of qi passes through"
    if progress < 0.75:
        return "it is half open"
    return "it is nearly open"


def _place(world: World, place_id: int) -> PlaceBrief:
    town = world.entity(place_id)
    return PlaceBrief(
        town.name, town.data["kind"], region_of(world, town.id).name, town.data["terrain"],
        season_of(world.time), WATCH_NAMES[world.time % 4],
    )


def _toward(prior_conversations: int) -> str:
    if prior_conversations == 0:
        return "stranger"
    return "acquaintance" if prior_conversations < 5 else "familiar face"


def _person(entity: Entity, toward: str) -> PersonBrief:
    data = entity.data
    if data.get("is_player"):
        body = body_of(entity)
        realm, role = (realm_title(body) if body else data.get("realm", "mortal")), "you"
    else:
        realm, role = data.get("realm", "mortal"), data.get("occupation", "stranger")
    return PersonBrief(entity.name, role, tuple(data.get("traits", ())), realm, toward)


def _relationship(world: World, npc: Entity, player: Entity) -> tuple[list[str], dict[str, str], int]:
    """Ranked facts about the player and this person, details, and the prior-conversation count.

    Salience order (spec §6.0): first meeting, then encounter count, then traits.
    Later phases insert indelible memories, grudges and obligations above these.
    Every event with another person happens inside a conversation whose opening
    greeting is already committed, so that greeting never counts as "before".
    """
    history = conversations_with(world, npc.id, player.id)
    prior = max(0, len(history) - 1)
    facts: list[str] = []
    details: dict[str, str] = {}
    met = [m for m in history if m.event.kind == "met"]
    if met and prior:
        season = format_season_year(met[0].event.time)
        details["first_met_season"] = season
        facts.append(f"You first met {npc.name} in {season}.")
    if prior:
        facts.append(f"You have spoken with {npc.name} {prior} time{'s' if prior != 1 else ''} before.")
    traits = npc.data.get("traits")
    if traits:
        facts.append(f"{npc.name} is {' and '.join(traits)}.")
    _patience_facts(world, npc, player, history, facts, details)
    return facts, details, prior


def _patience_facts(world, npc, player, greetings, facts, details) -> None:
    """Did this person lose patience with the player in the previous conversation, or ever?"""
    if not greetings:
        return
    current_start = greetings[-1].event.id
    previous_start = greetings[-2].event.id if len(greetings) > 1 else None
    lost = [
        m.event.id for m in world.memories(npc.id, about=player.id)
        if m.event.kind == "lost_patience" and m.event.id < current_start
    ]
    if not lost:
        return
    if previous_start is not None and lost[-1] > previous_start:
        details["annoyed_last_time"] = "yes"
        facts.insert(0, f"Last time, {npc.name} lost patience with your repeated questions.")
    else:
        facts.append(f"{npc.name} once lost patience with your repeated questions.")


def player_facts(world: World, player_id: int) -> list[str]:
    """What the player's own body says about them right now, most salient first."""
    if "body" not in world.entity(player_id).data:
        return []
    body = load_body(world, player_id)
    now = world.time
    facts = [f"Your {i.location} never healed from {i.cause}." for i in body.injuries if i.permanent]
    permanent_at = {i.location for i in body.injuries if i.permanent}
    facts += [f"Your {n} meridian is severed." for n, m in body.meridians.items() if m.state == "severed" and n not in permanent_at]
    facts += [f"Your {n} meridian is scarred." for n, m in body.meridians.items() if m.state == "scarred"]
    for injury in unhealed(body, now):
        if not injury.permanent:
            days = max(1, round((injury.heals_at - now) / 4))
            facts.append(f"Your {injury.location} is {INJURY_WORDS[injury.kind]} ({days} days to heal).")
    if body.deviation > 60:
        facts.append("Your qi feels unruly; a deviation may be near.")
    if body.constitution and body.constitution_known:
        facts.append(f"You have a {body.constitution}.")
    who = "You are still a mortal" if body.realm == 0 else f"You are a {REALMS[body.realm].name} warrior at the {stage_of(body)} stage"
    return facts[: MAX_FACTS - 1] + [f"{who}, with {energy_words(body.energy_years)}."]


def _body_outcome(event) -> tuple[list[str], dict[str, str]]:
    d, kind = event.data, event.kind
    out: list[str] = []
    details: dict[str, str] = {}
    if kind in ("began", "body_awakened"):
        details["origin"] = d.get("origin", "Wanderer")
        out.append(f"You begin as a {details['origin']}." if kind == "began" else "You take stock of your body and your training.")
        if d.get("arts"):
            out.append("You know the " + " and the ".join(d["arts"]) + ".")
    elif kind == "cultivated":
        details["days"] = days_word(d["days"])
        method = f" using the {d['method']}" if d.get("method") else ""
        out.append(f"You meditated for {details['days']}{method}.")
        if d["sensed_qi"]:
            out.append("For the first time, you sensed the qi within you.")
        out.append(f"Your internal energy grew {growth_words(d['energy_gained'])}." if d["energy_gained"] > 1e-9
                   else "Your internal energy did not grow.")
        if d["reached_bottleneck"]:
            out.append("Your qi has reached a bottleneck; it will not grow until you break through.")
        elif d["stage_after"] != d["stage_before"]:
            out.append(f"You advanced to the {d['stage_after']} stage.")
    elif kind == "practised":
        details.update(technique=d["technique"], days=days_word(d["days"]))
        out.append(f"You practised the {d['technique']} for {details['days']}.")
        if d["stage_after"] != d["stage_before"]:
            out.append(f"Your {d['technique']} reached {d['stage_after']}.")
        if d["stalled"]:
            out.append(f"Your progress in the {d['technique']} has stalled; something in it feels wrong.")
        elif d["compat"] < 0.7:
            out.append(f"The {d['technique']} {compat_words(d['compat'])}.")
    elif kind == "opening_meridian":
        details.update(meridian=d["meridian"], days=days_word(d["days"]))
        if d["opened"]:
            out.append(f"Your {d['meridian']} meridian is now open!")
        else:
            out.append(f"You worked at your {d['meridian']} meridian; {progress_words(d['progress_after'])}.")
        if d["forced"] and d["forced_damage"]:
            out.append(f"You forced the flow and damaged your {d['forced_damage']} meridian.")
    elif kind == "rested":
        details["days"] = days_word(d["days"])
        out.append(f"You rested for {details['days']}.")
        out += [f"Your {location} has healed." for location in d["healed"][:2]]
    elif kind == "breakthrough":
        details.update(target=d["target"], success="yes" if d["success"] else "no")
        if d["success"]:
            out.append(f"You broke through to {d['target']}!")
        else:
            out.append(f"Your breakthrough to {d['target']} failed.")
            if not d["met"]:
                out.append(f"You were not ready: {d['requirement']}")
            out += [f"The backlash damaged your {m} meridian." for m in d["damaged"][:2]]
    elif kind == "deviation":
        details["cause"] = d["cause"]
        out.append(f"Your qi deviated: {d['cause']}.")
        out += [f"It damaged your {m} meridian." for m in d["damaged"][:2]]
        out.append("You lost some of your internal energy.")
    if d.get("discovered"):
        out.insert(1, f"You discover that you have a {d['discovered']}.")
    return out, details


def event_brief(world: World, event_id: int, event) -> Brief:
    player = world.entity(event.actors[0])
    other = world.entity(event.actors[1]) if len(event.actors) > 1 else None
    facts: list[str] = []
    details: dict[str, str] = {}
    outcome: list[str] = []
    other_brief = None
    if other is not None:
        facts, details, prior = _relationship(world, other, player)
        other_brief = _person(other, _toward(prior))
        details["times_ordinal"] = ordinal(prior + 1)
    if "topic" in event.data:
        details["topic"] = str(event.data["topic"])
        if event.kind == "asked" and other is not None:
            repeats = times_asked(world, other.id, player.id, details["topic"]) - 1  # this question is committed
            if repeats > 0:
                details["asked_before"] = str(repeats)
                about = "their work" if details["topic"] == "work" else world.entity(event.place).name
                plural = "s" if repeats != 1 else ""
                facts.insert(0, f"You have already asked {other.name} about {about} {repeats} time{plural} before.")
    place_id = event.place
    if event.kind == "travelled":
        dest = world.entity_by_seed(town_path(*event.data["to"]))
        details["dest"] = dest.name if dest else "a town"
        details["days"] = days_phrase(event.data["watches"])
        facts.insert(0, f"You travelled {details['days']} to reach {details['dest']}.")
        if dest is not None:
            place_id = dest.id
    if event.kind in BODY_KINDS:
        outcome, extra = _body_outcome(event)
        details.update(extra)
        facts = player_facts(world, player.id)
    return Brief(
        kind=event.kind,
        when=format_date(world.time),
        place=_place(world, place_id),
        player=_person(player, "self"),
        other=other_brief,
        details=details,
        facts=tuple(facts[:MAX_FACTS]),
        seed=world.world_seed,
        salt=f"event:{event_id}",
        outcome=tuple(outcome[:MAX_OUTCOME]),
    )


def scene_brief(world: World, place_id: int, player_id: int, salt: str) -> Brief:
    player = world.entity(player_id)
    present = people_at(world, place_id, exclude=player_id)
    facts = []
    if present:
        facts.append("Here: " + ", ".join(f"{p.name} the {p.data.get('occupation', 'stranger')}" for p in present) + ".")
    known = [p.name for p in present if conversations_with(world, p.id, player_id)]
    if known:
        facts.append("You already know " + ", ".join(known) + ".")
    return Brief(
        kind="scene",
        when=format_date(world.time),
        place=_place(world, place_id),
        player=_person(player, "self"),
        other=None,
        facts=tuple(facts[:MAX_FACTS]),
        seed=world.world_seed,
        salt=f"scene:{place_id}:{world.time}:{salt}",
    )
```
`narrate/procedural.py`:
```python
"""Prose from grammar files, filled only from a Brief. Deterministic per brief.salt.

After the prose line, every `brief.outcome` line is shown dim: the grammar
colours the moment, the outcome says plainly what happened.
"""

import random
import re
import tomllib
from collections import deque
from pathlib import Path

from narrate.base import Line
from narrate.brief import Brief
from paths import bundled
from world.seed import rng_for

SYMBOL = re.compile(r"#(\w+)#")
SENTENCE_START = re.compile(r"(^|[.?!]\s+)([\"']?)([a-z])")


def sentence_case(text: str) -> str:
    """Capitalise the first letter of every sentence, including just inside a quote."""
    return SENTENCE_START.sub(lambda m: m.group(1) + m.group(2) + m.group(3).upper(), text)


class _KeepMissing(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class Grammar:
    def __init__(self, tables: dict) -> None:
        self.tables = tables

    @classmethod
    def load(cls, directory: Path | None = None) -> "Grammar":
        directory = directory or bundled("narrate", "grammar")
        tables: dict = {}
        for path in sorted(directory.glob("*.toml")):
            with open(path, "rb") as handle:
                for key, value in tomllib.load(handle).items():
                    if key == "symbols":
                        tables.setdefault("symbols", {}).update(value)
                    else:
                        tables[key] = value
        return cls(tables)

    def expand(self, key: str, rng: random.Random, context: dict) -> str:
        text = rng.choice(self.tables[key]["lines"])
        symbols = self.tables.get("symbols", {})
        for _ in range(10):
            expanded = SYMBOL.sub(lambda m: rng.choice(symbols[m.group(1)]) if m.group(1) in symbols else m.group(0), text)
            if expanded == text:
                break
            text = expanded
        return sentence_case(text.format_map(_KeepMissing(context)))


def context_of(brief: Brief) -> dict[str, str]:
    """Flatten a brief into grammar slots: the only data the grammar ever sees."""
    p = brief.place
    context = {
        "player": brief.player.name, "town": p.name, "kind": p.kind, "region": p.region,
        "terrain": p.terrain, "season": p.season, "watch": p.watch, "when": brief.when,
    }
    if brief.other is not None:
        o = brief.other
        context.update(
            npc=o.name, npc_full=o.name, occupation=o.role,
            trait=o.traits[0] if o.traits else "quiet", toward=o.toward_player,
        )
    context.update(brief.details)
    return context


class ProceduralNarrator:
    """Grammar prose with a short memory, so repeating an action doesn't repeat the text.

    The same salt always gives the same text (re-rendering a moment is stable).
    A new salt re-rolls away from the last RECENT texts of the same kind.
    """

    RECENT = 4
    REROLLS = 12

    def __init__(self, grammar: Grammar | None = None) -> None:
        self.grammar = grammar or Grammar.load()
        self._recent: dict[str, deque[str]] = {}
        self._last_salt: dict[str, tuple[str, str]] = {}

    def narrate(self, brief: Brief) -> list[Line]:
        outcome = [(line, "dim") for line in brief.outcome]
        key = self._key(brief)
        if key not in self.grammar.tables:
            return [(f"[{brief.kind}]", "dim")] + outcome
        colour = self.grammar.tables[key].get("colour", "default")
        salt, cached = self._last_salt.get(key, ("", ""))
        if salt == brief.salt:
            return [(cached, colour)] + outcome
        rng = rng_for(brief.seed, brief.salt)
        context = context_of(brief)
        recent = self._recent.setdefault(key, deque(maxlen=self.RECENT))
        text = self.grammar.expand(key, rng, context)
        for _ in range(self.REROLLS):
            if text not in recent:
                break
            text = self.grammar.expand(key, rng, context)
        recent.append(text)
        self._last_salt[key] = (brief.salt, text)
        return [(text, colour)] + outcome

    def _key(self, brief: Brief) -> str:
        if brief.kind == "scene":
            return f"scene.{brief.place.terrain}"
        if brief.kind == "breakthrough":
            return f"breakthrough.{'success' if brief.details.get('success') == 'yes' else 'failure'}"
        if brief.kind == "asked":
            key = f"asked.{brief.details.get('topic', '')}"
            if brief.details.get("asked_before") and f"{key}.again" in self.grammar.tables:
                return f"{key}.again"
            return key
        if brief.kind == "conversed" and brief.details.get("annoyed_last_time") and "conversed.annoyed" in self.grammar.tables:
            return "conversed.annoyed"
        return brief.kind
```
`narrate/grammar/body.toml`:
```toml
[symbols]
quiet_sound = ["the town murmurs beyond the wall", "rain ticks on the roof", "insects drone in the grass", "a bell tolls far off", "wind worries the shutters"]
qi_feel = ["Warmth gathers below your navel.", "Your breath slows until you hardly feel it.", "Qi stirs like a waking snake.", "Your limbs grow heavy, then light.", "A thin current circles your dantian."]
limb = ["wrists", "shoulders", "thighs", "forearms", "knuckles"]
drill_end = ["Sweat stings your eyes.", "The forms begin to flow a little easier.", "Your shadow keeps better time than you do.", "A passer-by stops to watch, then moves on.", "By the end you move without thinking."]
strain = ["Something deep inside resists.", "Sweat beads on your brow.", "The seal holds, but thins.", "Your pulse thunders in your ears."]
rest_note = ["Your body thanks you for it.", "Old aches loosen one by one.", "You sleep like the dead.", "Even your qi seems to settle."]
surge = ["Qi floods every channel at once.", "The world goes white for a heartbeat.", "A roar rises from your dantian.", "Your meridians burn like lit fuses."]
backlash = ["Blood fills your mouth.", "Pain lances through your chest.", "Your vision swims.", "Your hands shake uncontrollably."]

[body_awakened]
colour = "gold"
lines = ["You take stock of the body you were born with and the little you have learned."]

[cultivated]
colour = "default"
lines = [
  "You sit cross-legged for {days} while #quiet_sound#. #qi_feel#",
  "For {days} you guard your breath and follow the method. #qi_feel#",
]

[practised]
colour = "default"
lines = [
  "You drill the {technique} until your #limb# ache. #drill_end#",
  "Again and again you run the forms of the {technique}. #drill_end#",
]

[opening_meridian]
colour = "default"
lines = [
  "You press your qi against the sealed {meridian} meridian. #strain#",
  "Hour after hour you coax qi toward the {meridian} meridian. #strain#",
]

[rested]
colour = "default"
lines = [
  "You rest for {days}, eating well and sleeping long. #rest_note#",
  "For {days} you do nothing harder than walk and breathe. #rest_note#",
]

["breakthrough.success"]
colour = "gold"
lines = [
  "#surge# The wall inside you breaks, and you stand in {target}.",
  "You reach for {target}, and this time it answers. #surge#",
]

["breakthrough.failure"]
colour = "default"
lines = [
  "#surge# Then the flow turns on you, and the attempt collapses. #backlash#",
  "You reach for {target} and the qi recoils. #backlash#",
]

[deviation]
colour = "default"
lines = [
  "#backlash# Your qi runs wild through your meridians.",
  "Your qi twists against you. #backlash#",
]
```
`engine/journal.py`:
```python
"""One-line summaries of chronicle entries for the player's journal."""

from systems.time import days_word, format_date
from world.db import ChronicleEntry, World
from world.gen.town import town_path


def summarize(world: World, entry: ChronicleEntry) -> str:
    names = [world.entity(a).name for a in entry.actors]
    place = world.entity(entry.place).name if entry.place else "the road"
    other = names[1] if len(names) > 1 else "someone"
    data = entry.data
    match entry.kind:
        case "began":
            text = f"{names[0]} set out from {place}."
        case "body_awakened":
            text = "Took stock of body and training."
        case "met":
            text = f"Met {other} in {place}."
        case "conversed":
            text = f"Spoke again with {other} in {place}."
        case "asked":
            text = f"Asked {other} about {data.get('topic', 'things')}."
        case "parted":
            text = f"Took leave of {other}."
        case "lost_patience":
            text = f"{other} lost patience with your questions."
        case "travelled":
            dest = world.entity_by_seed(town_path(*data["to"]))
            text = f"Left {place} for {dest.name if dest else 'parts unknown'}."
        case "cultivated":
            text = f"Meditated for {days_word(data['days'])}."
        case "practised":
            text = f"Practised the {data['technique']}."
        case "opening_meridian":
            text = f"Opened the {data['meridian']} meridian." if data["opened"] else f"Worked on the {data['meridian']} meridian."
        case "rested":
            text = "Rested."
        case "breakthrough":
            text = f"Broke through to {data['target']}." if data["success"] else f"Failed to break through to {data['target']}."
        case "deviation":
            text = "Suffered a qi deviation."
        case _:
            text = entry.kind
    return f"{format_date(entry.time)} - {text}"
```
Then patch the older test:
```bash
python - <<'EOF'
import pathlib
p = pathlib.Path("tests/test_repeat.py"); t = p.read_text(encoding="utf-8")
a = 'ONE_OFF_KEYS = {"began"}'
assert t.count(a) == 1
p.write_text(t.replace(a, 'ONE_OFF_KEYS = {"began", "body_awakened"}'), encoding="utf-8", newline="\n")
EOF
```

- [ ] **Step 4: Run tests** → `tests/test_brief_body.py` PASS (7 passed), and the full suite passes, including the grammar variety lint on the new keys.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: briefs, prose and journal for cultivation and the body" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 7: The Cultivate menu, menu folding, typed commands

**Files:**
- Rewrite: `engine/game.py`, `engine/commands.py`
- Modify (tests): `tests/test_game.py`, `tests/test_persistence.py`. The patch below makes them look for folded travel choices in `all_choices`.
- Test: `tests/test_cultivate_menu.py`

**Interfaces:**
- Consumes: Tasks 1–6
- Produces:
  - `Game.body() -> Body`
  - New verbs: `routes`, `cultivate`, `practise_menu`, `meridian_menu`, `meditate`(days), `practise`(technique id), `open_meridian`(name), `rest`(days), `breakthrough`
  - Submenus `people`, `routes`, `cultivate`, `practise_menu` and `meridian_menu` each end with `Back`. In practise and meridian menus, Back returns to Cultivate.
  - The main menu folds people first, then routes, until 9 or fewer choices are shown.
  - The status reads `name | realm title | date | place, region`.
  - Parser: new global words `cultivate`, `meditate`, `rest` and `breakthrough`; new prefixes `meditate`, `practise`, `practice`, `train` and `open`.

- [ ] **Step 1: Write the failing test** — `tests/test_cultivate_menu.py`
```python
import pytest

from engine.commands import parse
from engine.game import Action, Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=42, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def verbs(choices):
    return [c.action.verb for c in choices]


def test_main_menu_always_fits_and_offers_cultivation(tmp_path):
    for seed in (1, 7, 42, 1234):
        g = Game.new(tmp_path / f"{seed}.world", "Hero", world_seed=seed)
        turn = g.start()
        assert len(turn.choices) <= 9
        assert {"cultivate", "look", "journal"} <= set(verbs(turn.choices))
        assert sum("road" in c.label for c in turn.all_choices) == 4
        g.close()


def test_busy_town_folds_travel_into_a_submenu(tmp_path):
    g = Game.new(tmp_path / "busy.world", "Hero", world_seed=7)
    turn = g.start()
    if "routes" in verbs(turn.choices):
        sub = g.perform(Action("routes"))
        assert sum("road" in c.label for c in sub.choices) == 4 and sub.choices[-1].action.verb == "back"
    g.close()


def test_cultivate_menu_and_meditation(game):
    menu = game.perform(Action("cultivate"))
    labels = [c.label for c in menu.choices]
    assert labels[:4] == ["Meditate for a day", "Meditate for a week", "Meditate for a month", "Seclusion for a season (90 days)"]
    assert "Practise an art..." in labels and "Rest for a week" in labels and labels[-1] == "Back"
    assert not any("breakthrough" in label for label in labels)
    assert any("mortal" in text for text, _ in menu.lines)
    turn = game.perform(Action("meditate", 7))
    assert game.submenu == "cultivate" and game.world.time == 28
    assert "You meditated for a week" in " ".join(t for t, _ in turn.lines)


def test_breakthrough_offered_only_at_bottleneck(game):
    body = load_body(game.world, game.player.id)
    body.energy_years, body.bottleneck = 1.0, True
    save_body(game.world, game.player.id, body)
    menu = game.perform(Action("cultivate"))
    assert "Attempt breakthrough to Third-rate" in [c.label for c in menu.choices]


def test_practise_and_meridian_menus(game):
    sub = game.perform(Action("practise_menu"))
    assert sub.choices[0].action.verb == "practise" and sub.choices[-1].action == Action("cultivate")
    turn = game.perform(sub.choices[0].action)
    assert "You practised the" in " ".join(t for t, _ in turn.lines)
    sub = game.perform(Action("meridian_menu"))
    assert len(sub.choices) == 9 and sub.choices[0].label == "Work on the Governing meridian for a week"
    turn = game.perform(sub.choices[0].action)
    assert turn.lines[-1][1] == "system" and "need" in turn.lines[-1][0]


def test_typed_cultivation_commands(game):
    turn = game.start()
    assert parse("meditate week", turn.choices, turn.extra) == Action("meditate", 7)
    assert parse("meditate season", turn.choices, turn.extra) == Action("meditate", 90)
    assert parse("rest", turn.choices, turn.extra) == Action("rest")
    assert parse("breakthrough", turn.choices, turn.extra) == Action("breakthrough")
    assert parse("cultivate", turn.choices, turn.extra) == Action("cultivate")
    assert parse("open governing", turn.choices, turn.extra) == Action("open_meridian", "Governing")
    art = next(c for c in turn.extra if c.action.verb == "practise")
    word = art.label.split()[2].lower()  # "Practise the <Adjective> ..."
    assert parse(f"practise {word}", turn.choices, turn.extra).verb in ("practise", "ambiguous")


def test_no_cultivating_mid_conversation(game):
    talk = next(c.action for c in game.start().all_choices if c.action.verb == "talk")
    game.perform(talk)
    assert game.perform(Action("meditate", 7)).lines[-1] == ("Finish your conversation first.", "system")


def test_status_shows_realm(game):
    assert "| Mortal |" in game.start().status
```

- [ ] **Step 2: Run to verify it fails** → FAIL (no `cultivate` verb, no `Game.body`)

- [ ] **Step 3: Implement**

`engine/game.py`:
```python
"""The engine: Actions in, Turns out. The only code that commits events."""

import random
import sqlite3
from dataclasses import dataclass, field

import systems.cultivation as cultivation
import systems.talk as talk
import systems.travel as travel
from engine.journal import summarize
from narrate.base import Line, Narrator
from narrate.brief import event_brief, scene_brief
from narrate.procedural import ProceduralNarrator
from systems.bodies import load_body
from systems.creation import CreationChoice, apply_creation, build, wanderer_arts
from systems.realms import MAX_REALM, REALMS, energy_words, realm_title
from systems.techniques import martial_arts, usable
from systems.time import format_date
from world.body import EXTRAORDINARY, Body, unhealed
from world.db import Entity, SaveError, World
from world.events import Event, commit
from world.gen.materialize import ensure_town, people_at, populate, region_of

MAX_SHOWN = 9  # digits 1-9 pick a choice with one key
KEEP_SUBMENU = frozenset({"people", "routes", "cultivate", "practise_menu", "meridian_menu", "ambiguous"})
BUSY = "Finish your conversation first."

HELP = [
    ("Type a number, or a command:", "system"),
    ("  look | talk <name> | go <place or direction> | ask <work|town> | bye | journal | help", "system"),
    ("  cultivate | meditate <day|week|month|season> | practise <art> | open <meridian> | rest | breakthrough", "system"),
    ("  F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu", "system"),
]


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
    extra: list[Choice] = field(default_factory=list)  # valid now but grouped off-screen

    @property
    def all_choices(self) -> list[Choice]:
        return self.choices + self.extra


class Game:
    def __init__(self, world: World, narrator: Narrator | None = None) -> None:
        self.world = world
        self.narrator = narrator or ProceduralNarrator()
        self.focus: int | None = None
        self.submenu: str | None = None
        self.last_briefs: list = []  # what the narrator was given this turn (debug overlay, invariants)
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
        return self._do_look(None)

    def perform(self, action: Action) -> Turn:
        self.last_briefs = []
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

    def _do_look(self, _target) -> Turn:
        self.focus = None
        here = (self.place.id, self.world.time)
        if here == self._last_look:
            return self._turn([("Nothing has changed since you last looked.", "dim")] + self._presence())
        self._last_look = here
        return self._turn(self._describe("look") + self._presence())

    def _do_travel(self, dest) -> Turn:
        routes = {r.dest: r for r in travel.routes_from(self.world, self.place)}
        route = routes.get(tuple(dest) if dest is not None else None)
        if route is None:
            return self._turn([("You can't get there from here.", "system")])
        self.focus = None
        lines = self._commit(travel.travel_events(self.player.id, self.place.id, route))
        populate(self.world, self.place.id)
        self._last_look = (self.place.id, self.world.time)
        return self._turn(lines + self._describe("arrive") + self._presence())

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
        entries = list(reversed(self.world.chronicle_about(self.player.id, limit=15)))
        lines = [(f"Chronicle of {self.player.name}:", "heading")]
        lines += [(summarize(self.world, e), "dim") for e in entries]
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
        if body.deviation > 60:
            lines.append(("Your qi feels unruly; a deviation may be near.", "dim"))
        hurt = sorted({i.location for i in unhealed(body, self.world.time)})
        if hurt:
            lines.append(("Still healing: " + ", ".join(hurt) + ".", "dim"))
        return lines

    # --- helpers --------------------------------------------------------------
    def _commit(self, events: list[Event]) -> list[Line]:
        ids = commit(self.world, events)
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
        if self.focus is not None:
            return [
                Choice("Ask about their work", Action("ask", "work")),
                Choice(f"Ask about {self.place.name}", Action("ask", "town")),
                Choice("Say farewell", Action("farewell")),
            ], []
        body = self.body()
        people = [
            Choice(f"Talk to {p.name} ({p.data.get('occupation', 'stranger')})", Action("talk", p.id))
            for p in people_at(self.world, self.place.id, exclude=self.player.id)
        ]
        routes = [Choice(r.label, Action("travel", r.dest)) for r in travel.routes_from(self.world, self.place)]
        general = [Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]
        cultivate = self._cultivation_choices(body)
        practise = [Choice(f"Practise the {a.name} for a week", Action("practise", a.technique.id))
                    for a in martial_arts(self.world, self.player.id)]
        meridians = [Choice(f"Work on the {m} meridian for a week", Action("open_meridian", m))
                     for m in EXTRAORDINARY if body.meridians[m].state == "blocked"]
        everything = people + routes + cultivate + practise + meridians + general
        submenus = {
            "people": (people, Action("back")), "routes": (routes, Action("back")),
            "cultivate": (cultivate, Action("back")),
            "practise_menu": (practise, Action("cultivate")), "meridian_menu": (meridians, Action("cultivate")),
        }
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

    def _cultivation_choices(self, body: Body) -> list[Choice]:
        options = [
            Choice("Meditate for a day", Action("meditate", 1)),
            Choice("Meditate for a week", Action("meditate", 7)),
            Choice("Meditate for a month", Action("meditate", 30)),
            Choice("Seclusion for a season (90 days)", Action("meditate", 90)),
        ]
        if martial_arts(self.world, self.player.id):
            options.append(Choice("Practise an art...", Action("practise_menu")))
        if any(body.meridians[m].state == "blocked" for m in EXTRAORDINARY):
            options.append(Choice("Work on opening a meridian...", Action("meridian_menu")))
        options.append(Choice("Rest for a week", Action("rest", 7)))
        if body.bottleneck and body.realm < MAX_REALM:
            options.append(Choice(f"Attempt breakthrough to {REALMS[body.realm + 1].name}", Action("breakthrough")))
        return options

    def _art(self) -> dict:
        if self.focus is not None:
            return {"type": "portrait", "parts": self.world.entity(self.focus).data["portrait"]}
        place = self.place
        return {"type": "scene", "terrain": place.data["terrain"], "settlement": place.data["kind"], "watch": self.world.time % 4}

    def _status(self) -> str:
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

from engine.game import Action, Choice

GLOBAL = {
    "look": "look", "l": "look", "journal": "journal", "j": "journal", "chronicle": "journal",
    "help": "help", "?": "help", "bye": "farewell", "farewell": "farewell", "leave": "farewell",
    "cultivate": "cultivate", "meditate": "meditate", "rest": "rest", "breakthrough": "breakthrough",
}
PREFIX_VERBS = {
    "talk": "talk", "speak": "talk", "go": "travel", "travel": "travel", "walk": "travel", "ask": "ask",
    "meditate": "meditate", "practise": "practise", "practice": "practise", "train": "practise",
    "open": "open_meridian",
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
        return Action(GLOBAL[lowered])
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
Patch the older tests, which assumed travel is always on the first screen:
```bash
python - <<'EOF'
import pathlib
def patch(f, pairs):
    p = pathlib.Path(f); t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (f, a)
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8", newline="\n")
patch("tests/test_game.py", [
    ('assert {"travel", "look", "journal"} <= set(verbs(turn))\n    assert any(c.action.verb == "talk" for c in turn.all_choices)',
     'assert {"cultivate", "look", "journal"} <= set(verbs(turn))\n    assert {"talk", "travel"} <= {c.action.verb for c in turn.all_choices}'),
    ('road = next(c for c in game.start().choices if c.action.verb == "travel" and "north" in c.label)',
     'road = next(c for c in game.start().all_choices if c.action.verb == "travel" and "north" in c.label)'),
    ('assert sum("road" in c.label for c in turn.choices) == 4',
     'assert sum("road" in c.label for c in turn.all_choices) == 4'),
    ('assert "road" in " ".join(c.label for c in g.perform(sub.choices[-1].action).choices)',
     'assert "road" in " ".join(c.label for c in g.perform(sub.choices[-1].action).all_choices)'),
])
patch("tests/test_persistence.py", [
    ('north = next(c for c in game.look().choices if "north road" in c.label)',
     'north = next(c for c in game.look().all_choices if "north road" in c.label)'),
    ('south = next(c for c in game.look().choices if "south road" in c.label)',
     'south = next(c for c in game.look().all_choices if "south road" in c.label)'),
])
EOF
```

- [ ] **Step 4: Run tests** → `tests/test_cultivate_menu.py` PASS (8 passed), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: Cultivate menu, menu folding, cultivation commands" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 8: Character creation screens and exact replays

**Files:**
- Rewrite: `app.py`, `render/menu.py`, `debug/replay.py`
- Modify: the smoke-test key script in `main.py`, plus the key scripts in `tests/test_app.py` and `tests/test_repeat.py` (via the patch step below)
- Test: `tests/test_creation_ui.py`

**Interfaces:**
- Consumes: `ORIGINS`, `CreationChoice`, `point_buy_problem`, `points_spent`, and the point-buy constants (Task 4); `FORMS` (Task 3)
- Produces:
  - App states `create`, `origin` and `points` sit between `name` and `game`. On the create screen, Random is option 0, so Enter once after the name starts a random character.
  - App attributes: `pending_name`, `points: dict`, `flow_points`, `form_index`, `points_row`.
  - `App.start_new(name, world_seed=None, creation=None)`
  - `App.open_save` copies the save to the session snapshot **before** loading it, so a migrated save replays exactly.
  - The session header gains `creation` (from `CreationChoice.to_dict()`), and replay rebuilds from it.
  - `compose_title(..., message_key="red")`

- [ ] **Step 1: Write the failing test** — `tests/test_creation_ui.py`
```python
import json

from app import App
from config import Config
from debug.replay import replay
from systems.creation import ORIGINS


def make(tmp_path):
    return App(Config(), tmp_path / "saves", tmp_path / "settings.json")


def to_create(app, name="Hero"):
    app.handle_key("return", "\r")  # New world
    for ch in name:
        app.handle_key(ch, ch)
    app.handle_key("return", "\r")
    assert app.state == "create"


def screen(app):
    return "\n".join("".join(c[0] if c else " " for c in row) for row in app.grid(120, 40))


def test_random_is_one_keypress(tmp_path):
    app = make(tmp_path)
    to_create(app)
    assert "Random (roll everything)" in screen(app)
    app.handle_key("return", "\r")
    assert app.state == "game" and app.game.player.data["origin"] in ORIGINS
    app.shutdown()


def test_choose_an_origin(tmp_path):
    app = make(tmp_path)
    to_create(app)
    app.handle_key("down", "")
    app.handle_key("return", "\r")
    assert app.state == "origin" and "Hunter's child" in screen(app)
    app.handle_key("down", "")
    assert ORIGINS["scion"].description in screen(app)
    app.handle_key("return", "\r")
    assert app.state == "game" and app.game.player.data["origin"] == "scion"
    app.shutdown()


def test_point_buy_respects_the_pool(tmp_path):
    app = make(tmp_path)
    to_create(app)
    app.handle_key("down", "")
    app.handle_key("down", "")
    app.handle_key("return", "\r")
    assert app.state == "points"
    for _ in range(20):
        app.handle_key("right", "")  # strength: 8 -> 16, the maximum
    assert app.points["strength"] == 16
    app.handle_key("left", "")
    app.handle_key("right", "")
    app.handle_key("return", "\r")  # Enter on a stat row just moves down a row
    assert app.points_row == 1
    for _ in range(20):
        app.handle_key("right", "")  # agility: only 4 points are left
    assert app.points["agility"] == 12 and "Points left: 0" in screen(app)
    for _ in range(3):
        app.handle_key("left", "")
    assert app.points["agility"] == 9
    for _ in range(10):
        app.handle_key("down", "")  # clamps on the last row, Begin
    app.handle_key("up", "")
    app.handle_key("right", "")  # form: sword -> saber
    app.handle_key("down", "")
    app.handle_key("return", "\r")
    assert app.state == "game" and app.game.player.data["origin"] == "self_made"
    assert app.game.player.data["body"]["physique"]["agility"] == 9
    app.shutdown()


def test_escape_walks_back(tmp_path):
    app = make(tmp_path)
    to_create(app)
    app.handle_key("down", "")
    app.handle_key("return", "\r")
    app.handle_key("escape", "\x1b")
    assert app.state == "create"
    app.handle_key("escape", "\x1b")
    assert app.state == "name"


def test_session_records_creation_and_replays(tmp_path):
    app = make(tmp_path)
    to_create(app)
    app.handle_key("down", "")
    app.handle_key("return", "\r")
    app.handle_key("return", "\r")  # hunter
    for key in ("1", "1"):
        app.handle_key(key, key)
    path = app.session.path
    app.shutdown()
    header = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert header["creation"] == {"mode": "origin", "origin": "hunter", "physique": None, "flow_points": 0, "form": None}
    assert replay(path, tmp_path / "r").mismatches == []


def test_replay_of_a_migrated_old_save(tmp_path):
    app = make(tmp_path)
    app.start_new("Hero", world_seed=5)
    pid = app.game.player.id
    app.game.world._conn.execute("update entities set data = json_remove(data, '$.body') where id = ?", (pid,))
    app.game.world._conn.execute("delete from relations where a = ? and kind = 'knows'", (pid,))
    app.handle_key("escape", "\x1b")
    app.handle_key("return", "\r")  # Continue: the save is migrated as it loads
    assert app.state == "game"
    app.submit("look")
    path = app.session.path
    app.shutdown()
    assert replay(path, tmp_path / "r").mismatches == []
```

- [ ] **Step 2: Run to verify it fails** → FAIL (after the name, the state is `game` rather than `create`)

- [ ] **Step 3: Implement**

`render/menu.py`:
```python
"""Title, name-entry and creation screens as grids. No pygame."""

from config import Color
from render.art import art_width, load_art
from render.layout import Grid, _Canvas


def compose_title(
    cols: int, rows: int, palette: dict[str, Color], options: list[str], selected: int,
    message: str = "", prompt: str | None = None, message_key: str = "red",
) -> Grid:
    canvas = _Canvas(cols, rows, palette)
    title = load_art("title")
    lines = len(title) + 2 + (1 if prompt else len(options)) + (2 if message else 0)
    top = max(0, (rows - lines) // 2)
    left = max(0, (cols - art_width(title)) // 2)
    for r, row in enumerate(title):
        for c, cell in enumerate(row):
            if cell is not None:
                canvas.put(top + r, left + c, cell[0], cell[1])
    y = top + len(title) + 2
    if prompt is not None:
        canvas.put(y, max(0, (cols - len(prompt)) // 2), prompt, "player")
        y += 1
    else:
        width = max((len(o) for o in options), default=0) + 2
        for i, option in enumerate(options):
            text = ("> " if i == selected else "  ") + option
            canvas.put(y, max(0, (cols - width) // 2), text, "gold" if i == selected else "default")
            y += 1
    if message:
        canvas.put(y + 1, max(0, (cols - len(message)) // 2), message, message_key)
    return canvas.grid
```
`debug/replay.py`:
```python
"""Re-run a recorded session and check every turn comes out the same.

Turns a bug report into an exact reproduction: same seed and creation choice
(or the snapshot taken before a continued save was loaded), same commands,
compared line by line.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from debug.session import load_session


@dataclass
class ReplayResult:
    commands: int = 0
    mismatches: list[str] = field(default_factory=list)


def _lines(turn) -> list[list[str]]:
    return [list(line) for line in turn.lines]


def replay(session_path, work_dir) -> ReplayResult:
    from app import App  # the app is what recorded the session, so it is what replays it
    from config import Config
    from systems.creation import CreationChoice

    entries = load_session(session_path)
    if not entries or entries[0].get("kind") != "session":
        return ReplayResult(0, [f"{session_path} is not a session log"])
    header = entries[0]
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    app = App(Config(), work / "saves", work / "settings.json", logs_dir=work / "logs")
    result = ReplayResult()
    try:
        if header["mode"] == "new":
            creation = CreationChoice.from_dict(header.get("creation") or {})
            app.start_new(header["player"], world_seed=header["seed"], creation=creation)
        else:
            copy = work / "saves" / "replay.world"
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(header["snapshot"], copy)
            if not app.open_save(copy):
                return ReplayResult(0, [f"could not open snapshot: {app.message}"])
        last_command = "(opening)"
        crashes_before = app.crash_count
        for entry in entries[1:]:
            kind = entry["kind"]
            if kind == "command":
                crashes_before = app.crash_count
                app.submit(entry["text"])
                result.commands += 1
                last_command = f"#{result.commands} {entry['text']!r}"
            elif kind == "turn":
                got = _lines(app.last_turn) if app.last_turn else []
                if got != entry["lines"]:
                    result.mismatches.append(f"after {last_command}: expected {entry['lines'][:3]} got {got[:3]}")
            elif kind == "crash" and app.crash_count == crashes_before:
                result.mismatches.append(f"after {last_command}: original crashed ({entry.get('error')}), replay did not")
    finally:
        app.shutdown()
    return result
```
`app.py`:
```python
"""What the player is looking at and how keys change it. No pygame here:
keys arrive as pygame.key.name strings plus the typed text, so this is testable.

Also the home of the debug kit's live half: every session is logged, every
turn is checked against the invariants, and exceptions become crash reports
instead of a dead window.
"""

import re
import shutil
import time
from collections import deque
from pathlib import Path

from config import PALETTE, Config
from debug.invariants import NARRATIVE, check_turn, check_world
from debug.reports import write_bug_report, write_crash_report
from debug.session import SessionLog, stamp
from engine.commands import parse
from engine.game import Game, Turn
from render.art import render_request
from render.layout import Grid, View, compose
from render.menu import compose_title
from settings_store import save_values
from systems.creation import (
    FLOW_POINT_COST, ORIGINS, POINT_BASE, POINT_MAX, POINT_POOL, CreationChoice, point_buy_problem, points_spent,
)
from systems.techniques import FORMS
from systems.time import format_date
from world.body import PHYSIQUE
from world.db import SaveError

MAX_LOG = 500
MAX_COMMAND = 200
MAX_NAME = 24
MAX_VIOLATIONS = 200
INSTANT_KEYS = "123456789"  # submit on press, so a held key must not auto-repeat them
CREATE_OPTIONS = ("Random (roll everything)", "Choose an origin", "Point-buy")
ORIGIN_KEYS = tuple(ORIGINS)
POINT_ROWS = PHYSIQUE + ("meridian openness", "form", "begin")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "hero"


class App:
    def __init__(self, config: Config, saves_dir: Path, settings_path: Path, logs_dir: Path | None = None) -> None:
        self.config = config
        self.saves_dir = Path(saves_dir)
        self.settings_path = Path(settings_path)
        self.logs_dir = Path(logs_dir) if logs_dir is not None else self.saves_dir.parent / "logs"
        self.state = "title"
        self.running = True
        self.selected = 0
        self.message = ""
        self.name = ""
        self.game: Game | None = None
        self.save_path: Path | None = None
        self.log: list = []
        self.choices: list = []
        self.extra: list = []
        self.art: list = []
        self.status = ""
        self.command = ""
        self.scroll = 0
        # character creation
        self.pending_name = ""
        self.origin_selected = 0
        self.points: dict = {}
        self.flow_points = 0
        self.form_index = 0
        self.points_row = 0
        # debug kit
        self.session: SessionLog | None = None
        self.last_turn: Turn | None = None
        self.crash_count = 0
        self.violations: list[str] = []
        self.debug_visible = False
        self.report_note = ""
        self._recent_narration: deque[str] = deque(maxlen=4)

    # --- saves --------------------------------------------------------------
    def latest_save(self) -> Path | None:
        saves = sorted(self.saves_dir.glob("*.world"), key=lambda p: p.stat().st_mtime, reverse=True)
        return saves[0] if saves else None

    def title_options(self) -> list[str]:
        return (["Continue"] if self.latest_save() else []) + ["New world", "Quit"]

    # --- keys -----------------------------------------------------------------
    def handle_key(self, key: str, text: str, repeat: bool = False) -> None:
        """`repeat` is True for key-repeat events from a held key."""
        if repeat and self.state == "game" and not self.command and len(text) == 1 and text in INSTANT_KEYS:
            return
        getattr(self, f"_{self.state}_key")(key, text)

    def _title_key(self, key: str, text: str) -> None:
        options = self.title_options()
        if key in ("up", "w"):
            self.selected = (self.selected - 1) % len(options)
        elif key in ("down", "s"):
            self.selected = (self.selected + 1) % len(options)
        elif key == "escape":
            self.running = False
        elif key in ("return", "enter"):
            choice = options[min(self.selected, len(options) - 1)]
            if choice == "Continue":
                self.open_save(self.latest_save())
            elif choice == "New world":
                self.state, self.name, self.message = "name", "", ""
            else:
                self.running = False

    def _name_key(self, key: str, text: str) -> None:
        if key == "escape":
            self.state = "title"
        elif key == "backspace":
            self.name = self.name[:-1]
        elif key in ("return", "enter"):
            self.pending_name = self.name.strip() or "Nameless"
            self.state, self.selected, self.message = "create", 0, ""
        elif len(text) == 1 and text.isprintable() and len(self.name) < MAX_NAME:
            self.name += text

    def _create_key(self, key: str, text: str) -> None:
        if key in ("up", "w"):
            self.selected = (self.selected - 1) % len(CREATE_OPTIONS)
        elif key in ("down", "s"):
            self.selected = (self.selected + 1) % len(CREATE_OPTIONS)
        elif key == "escape":
            self.state = "name"
        elif key in ("return", "enter"):
            if self.selected == 0:
                self.start_new(self.pending_name, creation=CreationChoice("random"))
            elif self.selected == 1:
                self.state, self.origin_selected = "origin", 0
            else:
                self.state, self.message = "points", ""
                self.points = {p: POINT_BASE for p in PHYSIQUE}
                self.flow_points, self.form_index, self.points_row = 0, 0, 0

    def _origin_key(self, key: str, text: str) -> None:
        if key in ("up", "w"):
            self.origin_selected = (self.origin_selected - 1) % len(ORIGIN_KEYS)
        elif key in ("down", "s"):
            self.origin_selected = (self.origin_selected + 1) % len(ORIGIN_KEYS)
        elif key == "escape":
            self.state = "create"
        elif key in ("return", "enter"):
            self.start_new(self.pending_name, creation=CreationChoice("origin", ORIGIN_KEYS[self.origin_selected]))

    def _points_key(self, key: str, text: str) -> None:
        if key == "up":
            self.points_row = max(0, self.points_row - 1)
        elif key == "down":
            self.points_row = min(len(POINT_ROWS) - 1, self.points_row + 1)
        elif key in ("left", "-") or text == "-":
            self._adjust(-1)
        elif key in ("right", "+", "=") or text in ("+", "="):
            self._adjust(1)
        elif key == "escape":
            self.state, self.message = "create", ""
        elif key in ("return", "enter"):
            if POINT_ROWS[self.points_row] != "begin":
                self.points_row += 1
                return
            problem = point_buy_problem(self.points, self.flow_points)
            if problem:
                self.message = problem
                return
            choice = CreationChoice("point_buy", physique=tuple(self.points.items()),
                                    flow_points=self.flow_points, form=FORMS[self.form_index])
            self.message = ""
            self.start_new(self.pending_name, creation=choice)

    def _adjust(self, delta: int) -> None:
        row = POINT_ROWS[self.points_row]
        left = POINT_POOL - points_spent(self.points, self.flow_points)
        if row in PHYSIQUE:
            value = self.points[row] + delta
            if POINT_BASE <= value <= POINT_MAX and (delta < 0 or left >= 1):
                self.points[row] = value
        elif row == "meridian openness":
            value = self.flow_points + delta
            if value >= 0 and (delta < 0 or left >= FLOW_POINT_COST):
                self.flow_points = value
        elif row == "form":
            self.form_index = (self.form_index + delta) % len(FORMS)

    def _game_key(self, key: str, text: str) -> None:
        if key == "f2":
            self.config.art_side = "right" if self.config.art_side == "left" else "left"
            self._save_settings()
        elif key == "f3":
            self.config.show_art = not self.config.show_art
            self._save_settings()
        elif key == "f9":
            if self.command.strip():
                self.bug_report()
            else:
                self.state, self.report_note = "report", ""
        elif key == "f12":
            self.debug_visible = not self.debug_visible
        elif key == "page up":
            self.scroll += 5
        elif key == "page down":
            self.scroll = max(0, self.scroll - 5)
        elif key == "escape":
            if self.command:
                self.command = ""
            else:
                self._close_game()
                self.state, self.selected = "title", 0
        elif key == "backspace":
            self.command = self.command[:-1]
        elif key in ("return", "enter"):
            self.submit(self.command)
        elif len(text) == 1 and text.isprintable():
            if not self.command and text in INSTANT_KEYS:
                self.submit(text)
            elif len(self.command) < MAX_COMMAND:
                self.command += text

    def _report_key(self, key: str, text: str) -> None:
        """F9 on an empty command line: ask for a description, Enter saves, Esc cancels."""
        if key == "escape":
            self.state = "game"
        elif key == "backspace":
            self.report_note = self.report_note[:-1]
        elif key in ("return", "enter"):
            self.command = self.report_note
            self.state = "game"
            self.bug_report()
        elif len(text) == 1 and text.isprintable() and len(self.report_note) < MAX_COMMAND:
            self.report_note += text

    # --- game -----------------------------------------------------------------
    def submit(self, text: str) -> None:
        action = parse(text, self.choices, self.extra)
        self.command = ""
        if action is None or self.game is None:
            return
        self.log.append((f"> {text.strip()}", "player"))
        self._record("command", text=text, verb=action.verb)
        try:
            turn = self.game.perform(action)
        except Exception as exc:  # the whole point: a bug becomes a report, not a dead game
            self.record_crash(exc, f"perform {action.verb}")
            return
        self._show(turn)

    def _show(self, turn: Turn) -> None:
        if self.log:
            self.log.append(("", "default"))
        self.log.extend(turn.lines)
        self.choices = turn.choices
        self.extra = turn.extra
        self.art = render_request(turn.art, self.config.art_width, self.config.art_height)
        self.status = turn.status
        self.scroll = 0
        self.last_turn = turn
        self._record(
            "turn", lines=[list(line) for line in turn.lines],
            choices=[c.label for c in turn.choices], status=turn.status, art=turn.art,
        )
        self._check(turn)
        del self.log[:-MAX_LOG]

    def _check(self, turn: Turn) -> None:
        try:
            problems = check_world(self.game.world) + check_turn(self.game, turn, list(self._recent_narration))
        except Exception as exc:
            problems = [f"invariant check itself failed: {exc!r}"]
        for text, key in turn.lines:
            if key in NARRATIVE and text:
                self._recent_narration.append(text)
        if problems:
            self.violations.extend(problems)
            del self.violations[:-MAX_VIOLATIONS]
            self._record("violation", problems=problems)
            more = f" (+{len(problems) - 1} more)" if len(problems) > 1 else ""
            self.log.append((f"debug: {problems[0][:90]}{more} - F12 for details, F9 to report", "red"))

    def start_new(self, name: str, world_seed: int | None = None, creation: CreationChoice | None = None) -> None:
        creation = creation or CreationChoice()
        path = self.saves_dir / f"{slug(name)}-{time.time_ns()}.world"
        self._close_game()
        self.game = Game.new(path, name, world_seed=world_seed, creation=creation)
        self.save_path = path
        self._open_session(mode="new", player=name, seed=self.game.world.world_seed, creation=creation.to_dict())
        self.log = []
        self._show(self.game.start())
        self.state = "game"

    def open_save(self, path: Path | None) -> bool:
        if path is None:
            self.message = "No save to continue"
            return False
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        snapshot = self.logs_dir / f"session-{stamp()}.start.world"
        try:
            shutil.copyfile(path, snapshot)  # before loading: loading may migrate the save
        except OSError as exc:
            self.message = f"Could not read {Path(path).name} ({exc})"
            return False
        try:
            game = Game.load(path)
        except SaveError as exc:
            self.message = str(exc)
            snapshot.unlink(missing_ok=True)
            return False
        self._close_game()
        self.game, self.save_path, self.log, self.message = game, Path(path), [], ""
        self._open_session(mode="continue", player=game.player.name, seed=game.world.world_seed, snapshot=str(snapshot))
        self._show(game.start())
        self.state = "game"
        return True

    def _open_session(self, **header) -> None:
        self.session = SessionLog(self.logs_dir / f"session-{stamp()}.jsonl")
        self.session.record("session", save=str(self.save_path), **header)
        self._recent_narration.clear()

    def _record(self, kind: str, **data) -> None:
        if self.session is not None:
            self.session.record(kind, **data)

    def _close_game(self) -> None:
        if self.game is not None:
            self.game.close()
            self.game = None
        if self.session is not None:
            self.session.close()

    def _save_settings(self) -> None:
        save_values({"art_side": self.config.art_side, "show_art": self.config.show_art}, self.settings_path)

    def shutdown(self) -> None:
        self._close_game()

    # --- debug kit ----------------------------------------------------------------
    def debug_context(self, where: str = "") -> dict:
        context = {
            "where": where, "state": self.state, "save": str(self.save_path),
            "session_log": str(self.session.path) if self.session else None,
            "command_buffer": self.command, "crashes": self.crash_count,
            "recent_violations": self.violations[-5:],
        }
        game = self.game
        if game is not None:
            try:
                place = game.place
                context.update(
                    seed=game.world.world_seed, time=game.world.time, date=format_date(game.world.time),
                    place=f"{place.name} #{place.id}", focus=game.focus, submenu=game.submenu,
                )
            except Exception as exc:
                context["game_state_error"] = repr(exc)
        return context

    def record_crash(self, exc: BaseException, where: str) -> Path:
        self.crash_count += 1
        recent = list(self.session.recent) if self.session else []
        path = write_crash_report(self.logs_dir, exc, self.debug_context(where), recent)
        self._record("crash", error=repr(exc), where=where, report=str(path))
        self.log.append((
            f"Something went wrong ({type(exc).__name__}). A crash report was saved to {path.name}. "
            "Press F9 to save a full bug report.", "red",
        ))
        return path

    def bug_report(self) -> Path | None:
        if self.game is None:
            return None
        note, self.command = self.command.strip(), ""
        folder = write_bug_report(
            self.logs_dir, self.game.world, self.session, note,
            self.debug_context("bug report"), self.violations[-50:],
        )
        self._record("bug_report", note=note, folder=str(folder))
        self.log.append((f"Bug report saved to {folder} - hand that folder to Claude.", "gold"))
        return folder

    def debug_lines(self) -> list:
        context = self.debug_context("overlay")
        lines = [
            (f"place {context.get('place')} | {context.get('date')} (t={context.get('time')}) | "
             f"focus {context.get('focus')} | submenu {context.get('submenu')}", "gold"),
            (f"save: {context['save']}", "dim"),
            (f"session log: {context['session_log']}", "dim"),
            (f"crashes this session: {self.crash_count} | invariant violations: {len(self.violations)}", "dim"),
            ("", "default"),
            ("Narrator input this turn (what Haiku would get):", "gold"),
        ]
        briefs = self.game.last_briefs if self.game is not None else []
        for brief in briefs:
            lines += [(f"  {line}", "default") for line in brief.to_prompt().splitlines()]
            lines.append(("", "default"))
        if not briefs:
            lines.append(("  (none this turn)", "dim"))
        lines.append(("Recent violations:", "gold"))
        lines += [(f"  {v}", "red") for v in self.violations[-8:]] or [("  none", "dim")]
        return lines

    # --- drawing ----------------------------------------------------------------
    def grid(self, cols: int, rows: int) -> Grid:
        if self.state == "title":
            return compose_title(cols, rows, PALETTE, self.title_options(), self.selected, self.message)
        if self.state == "name":
            return compose_title(cols, rows, PALETTE, [], 0, self.message, f"What is your name? {self.name}_")
        if self.state == "create":
            return compose_title(cols, rows, PALETTE, list(CREATE_OPTIONS), self.selected,
                                 f"Who is {self.pending_name}?", message_key="dim")
        if self.state == "origin":
            origin = ORIGINS[ORIGIN_KEYS[self.origin_selected]]
            return compose_title(cols, rows, PALETTE, [ORIGINS[k].title for k in ORIGIN_KEYS],
                                 self.origin_selected, origin.description, message_key="dim")
        if self.state == "points":
            left = POINT_POOL - points_spent(self.points, self.flow_points)
            options = [f"{p:<18}{self.points[p]:>3}" for p in PHYSIQUE]
            options += [f"{'meridian openness':<18}{self.flow_points:>3}", f"{'form':<18}{FORMS[self.form_index]:>8}", "Begin"]
            note = self.message or f"Points left: {left}   (left/right adjusts, Enter on Begin starts)"
            return compose_title(cols, rows, PALETTE, options, self.points_row, note,
                                 message_key="red" if self.message else "dim")
        status, log, command = self.status, self.log, self.command
        if self.state == "report":
            command = f"Describe the bug (Enter saves, Esc cancels): {self.report_note}"
        if self.debug_visible:
            seed = self.game.world.world_seed if self.game else "?"
            status = f"DEBUG (F12 closes) | seed {seed} | F9 reports a bug"
            log = self.debug_lines()
        view = View(
            status=status, log=log, art=self.art,
            choices=[c.label for c in self.choices], command=command,
            art_side=self.config.art_side, show_art=self.config.show_art,
            scroll=0 if self.debug_visible else self.scroll,
        )
        return compose(view, cols, rows, PALETTE, self.config.art_width)
```
Patch the key scripts that walked from name straight into the game:
```bash
python - <<'EOF'
import pathlib
def patch(f, pairs):
    p = pathlib.Path(f); t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (f, a)
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8", newline="\n")
patch("tests/test_app.py", [
    ('    type_text(app, name)\n    app.handle_key("return", "\\r")\n    assert app.state == "game"',
     '    type_text(app, name)\n    app.handle_key("return", "\\r")\n    assert app.state == "create"\n    app.handle_key("return", "\\r")  # Random\n    assert app.state == "game"'),
])
patch("tests/test_repeat.py", [
    ('    for ch in "Hero":\n        app.handle_key(ch, ch)\n    app.handle_key("return", "\\r")\n    app.handle_key("1", "1")',
     '    for ch in "Hero":\n        app.handle_key(ch, ch)\n    app.handle_key("return", "\\r")\n    app.handle_key("return", "\\r")  # Random\n    app.handle_key("1", "1")'),
])
patch("main.py", [
    ('("return", "\\r"), ("1", "1")]', '("return", "\\r"), ("return", "\\r"), ("1", "1")]'),
])
EOF
```

- [ ] **Step 4: Run tests** → `tests/test_creation_ui.py` PASS (7 passed), and the full suite passes. Then run `.venv/Scripts/python.exe main.py --smoke "$SCRATCH/smoke-2a.png"` and look at the PNG: the game screen should show a status bar with `| Mortal |`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: creation screens, creation in session log, snapshot before load" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 9: F4 character sheet and body chart

**Files:**
- Create: `engine/sheet.py`, `render/body_chart.py`
- Modify: `app.py` (F4 key, sheet view) and `FALLBACK` in `render/screen.py`, both via the patch step below
- Test: `tests/test_sheet.py`

**Interfaces:**
- Consumes: `Game.body()` (Task 7), `known_arts`, `compatibility`, `compat_words`, `mastery_stage` (Task 3), `realm_title` (Task 2), `unhealed`, `max_qi` (Task 1)
- Produces:
  - `sheet_lines(world, player_id) -> list[Line]`
  - `SYMBOL = {"open": "●", "damaged": "◐", "scarred": "◌", "severed": "×", "blocked": "·"}`
  - `body_chart(body, now, width, height) -> Art`, which always returns exactly the requested size
  - `App.sheet_visible`. F4 and F12 are mutually exclusive overlays.

- [ ] **Step 1: Write the failing test** — `tests/test_sheet.py`
```python
from app import App
from config import Config
from engine.game import Game
from engine.sheet import sheet_lines
from render.body_chart import body_chart
from render.screen import FALLBACK
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import add_injury


def test_sheet_shows_numbers_but_never_hidden_truths(tmp_path):
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=3, creation=CreationChoice("origin", "scion"))
    body = load_body(game.world, game.player.id)
    body.constitution, body.constitution_known = "Nine Yin Body", False
    save_body(game.world, game.player.id, body)
    text = "\n".join(t for t, _ in sheet_lines(game.world, game.player.id))
    for heading in ("Realm: Mortal", "Arts:", "Meridians:", "Injuries:"):
        assert heading in text
    assert "completeness 100%" in text and "80%" not in text  # the family method looks whole
    assert "Constitution: unknown" in text and "Nine Yin" not in text
    game.close()


def test_body_chart_colours_injured_parts(tmp_path):
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=3)
    body = load_body(game.world, game.player.id)
    add_injury(body, "left arm", "fracture", 5, 0, "x", permanent=True)
    art = body_chart(body, 0, 40, 18)
    assert len(art) == 18 and all(len(r) == 40 for r in art)
    colours = {cell[1] for row in art for cell in row if cell}
    assert "purple" in colours and "green" in colours
    tiny = body_chart(body, 0, 5, 3)
    assert len(tiny) == 3 and all(len(r) == 5 for r in tiny)
    game.close()


def test_symbols_have_font_fallbacks():
    for symbol in "●◐◌×·":
        assert symbol in FALLBACK


def test_f4_toggles_the_sheet(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Hero", world_seed=3)
    app.handle_key("f4", "")
    text = "\n".join("".join(c[0] if c else " " for c in row) for row in app.grid(120, 40))
    assert "CHARACTER SHEET" in text and "Arts:" in text
    app.handle_key("f12", "")
    assert app.sheet_visible is False and app.debug_visible
    app.handle_key("f4", "")
    assert app.sheet_visible and not app.debug_visible
    app.handle_key("f4", "")
    assert not app.sheet_visible
    app.shutdown()
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`ModuleNotFoundError: engine.sheet`)

- [ ] **Step 3: Implement**

`engine/sheet.py`:
```python
"""The F4 character sheet: exact numbers, for players who want them.

Never shows hidden truth: an art's real completeness and an undiscovered
constitution stay hidden; only what the character believes is printed.
"""

from narrate.base import Line
from render.body_chart import SYMBOL
from systems.bodies import load_body
from systems.realms import realm_title
from systems.techniques import compat_words, compatibility, known_arts, mastery_stage
from world.body import EXTRAORDINARY, REGULAR, max_qi, unhealed
from world.db import World


def sheet_lines(world: World, player_id: int) -> list[Line]:
    player = world.entity(player_id)
    body = load_body(world, player_id)
    now = world.time
    lines: list[Line] = [
        (f"{player.name} - {player.data.get('origin_title', 'Wanderer')}", "heading"),
        (f"Realm: {realm_title(body)} | energy {body.energy_years:.2f} years"
         f"{' | BOTTLENECK' if body.bottleneck else ''}", "default"),
        (f"Qi {body.qi:.1f} / {max_qi(body):.1f} | purity {body.purity:.2f} | deviation {body.deviation:.1f}", "default"),
        ("Nature: " + "  ".join(f"{k} {v:.2f}" for k, v in body.nature.items()), "dim"),
        ("Physique: " + "  ".join(f"{k} {v}" for k, v in body.physique.items()), "default"),
        (f"Insight {body.insight:.1f} | silver {player.data.get('silver', 0)}", "default"),
        (f"Constitution: {body.constitution if body.constitution and body.constitution_known else 'unknown'}", "default"),
        ("", "default"),
        ("Arts:", "heading"),
    ]
    for art in known_arts(world, player_id):
        data = art.technique.data
        compat = compatibility(body, data)
        kind = "heart method" if art.category == "heart_method" else data["form"]
        lines.append((
            f"  {art.name} ({kind}, grade {data['grade']}): {mastery_stage(art.mastery)} {art.mastery:.2f}"
            f" | {compat_words(compat)} ({compat:.2f}) | completeness {art.known_completeness:.0%}", "default",
        ))
    lines += [("", "default"), ("Meridians:", "heading")]
    lines.append(("  " + "  ".join(f"{m} {SYMBOL[body.meridians[m].state]}{body.meridians[m].flow:.2f}" for m in REGULAR), "default"))
    extraordinary = []
    for m in EXTRAORDINARY:
        meridian = body.meridians[m]
        detail = f"{meridian.opening:.0%}" if meridian.state == "blocked" else f"{meridian.flow:.2f}"
        extraordinary.append(f"{m} {SYMBOL[meridian.state]}{detail}")
    lines.append(("  " + "  ".join(extraordinary), "default"))
    lines += [("", "default"), ("Injuries:", "heading")]
    injuries = unhealed(body, now)
    for injury in injuries:
        when = "permanent" if injury.permanent else f"{max(1, round((injury.heals_at - now) / 4))} days to heal"
        lines.append((f"  {injury.location}: {injury.kind} (severity {injury.severity}) - {when} - {injury.cause}",
                      "red" if injury.permanent else "default"))
    if not injuries:
        lines.append(("  none", "dim"))
    return lines
```
`render/body_chart.py`:
```python
"""An ASCII figure coloured by injuries, plus meridian states. Pure: no pygame.

Parts: H head, T torso, R right arm, L left arm, r right leg, l left leg. The
figure faces the viewer, so its right side is on the viewer's left.
"""

from render.art import Art, blank, stamp
from world.body import EXTRAORDINARY, REGULAR, unhealed

FIGURE = (
    "    .-.    ",
    "   (   )   ",
    "    '-'    ",
    "  __| |__  ",
    " /  | |  \\ ",
    "/   | |   \\",
    "    |_|    ",
    "    / \\    ",
    "   /   \\   ",
    "  /     \\  ",
    " /       \\ ",
)
MASK = (
    "    HHH    ",
    "   HHHHH   ",
    "    HHH    ",
    "  RRTTTLL  ",
    " R  TTT  L ",
    "R   TTT   L",
    "    TTT    ",
    "    r l    ",
    "   r   l   ",
    "  r     l  ",
    " r       l ",
)
PART = {"H": "head", "T": "torso", "R": "right arm", "L": "left arm", "r": "right leg", "l": "left leg"}
SYMBOL = {"open": "●", "damaged": "◐", "scarred": "◌", "severed": "×", "blocked": "·"}
STATE_COLOUR = {"open": "green", "damaged": "gold", "scarred": "brown", "severed": "red", "blocked": "dim"}
SHORT = {
    "Governing": "Gov", "Conception": "Con", "Penetrating": "Pen", "Girdle": "Gir",
    "Yin Linking": "YinL", "Yang Linking": "YangL", "Yin Heel": "YinH", "Yang Heel": "YangH",
}


def part_colour(body, part: str, now: int) -> str:
    hurt = [i for i in unhealed(body, now) if i.location == part]
    if any(i.permanent for i in hurt):
        return "purple"
    worst = max((i.severity for i in hurt), default=0)
    return "green" if worst == 0 else "gold" if worst <= 2 else "red"


def _segment(text: str, key: str) -> list:
    return [None if ch == " " else (ch, key) for ch in text]


def body_chart(body, now: int, width: int, height: int) -> Art:
    rows: Art = []
    for text, mask in zip(FIGURE, MASK):
        rows.append([None if ch == " " else (ch, part_colour(body, PART[m], now)) for ch, m in zip(text, mask)])
    rows.append([])
    for group in (EXTRAORDINARY[:4], EXTRAORDINARY[4:]):
        row: list = []
        for name in group:
            state = body.meridians[name].state
            row += _segment(f"{SHORT[name]}{SYMBOL[state]} ", STATE_COLOUR[state])
        rows.append(row)
    summary: list = _segment("Regular ", "dim")
    for state in ("open", "damaged", "scarred", "severed"):
        count = sum(1 for m in REGULAR if body.meridians[m].state == state)
        if count:
            summary += _segment(f"{count}{SYMBOL[state]} ", STATE_COLOUR[state])
    rows.append(summary)
    canvas = blank(width, height)
    top = max(0, (height - len(rows)) // 2)
    for r, row in enumerate(rows):
        stamp(canvas, [row], top + r, (width - len(row)) // 2)
    return canvas
```
Patch the screen fallbacks and wire F4 into the app:
```bash
python - <<'EOF'
import pathlib
def patch(f, pairs):
    p = pathlib.Path(f); t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (f, a)
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8", newline="\n")
patch("render/screen.py", [
    ('FALLBACK = {"│": "|", "─": "-"}',
     'FALLBACK = {"│": "|", "─": "-", "●": "o", "◐": "c", "◌": "o", "×": "x", "·": "."}'),
])
patch("app.py", [
    ("from engine.game import Game, Turn\n",
     "from engine.game import Game, Turn\nfrom engine.sheet import sheet_lines\n"),
    ("from render.art import render_request\n",
     "from render.art import render_request\nfrom render.body_chart import body_chart\n"),
    ("        self.debug_visible = False\n",
     "        self.debug_visible = False\n        self.sheet_visible = False\n"),
    ('''        elif key == "f12":
            self.debug_visible = not self.debug_visible''',
     '''        elif key == "f12":
            self.debug_visible = not self.debug_visible
            self.sheet_visible = self.sheet_visible and not self.debug_visible
        elif key == "f4":
            self.sheet_visible = not self.sheet_visible
            self.debug_visible = self.debug_visible and not self.sheet_visible'''),
    ('''        status, log, command = self.status, self.log, self.command''',
     '''        status, log, command, art = self.status, self.log, self.command, self.art'''),
    ('''            log = self.debug_lines()
        view = View(
            status=status, log=log, art=self.art,''',
     '''            log = self.debug_lines()
        if self.sheet_visible and self.game is not None:
            status = "CHARACTER SHEET (F4 closes)"
            log = sheet_lines(self.game.world, self.game.player.id)
            art = body_chart(self.game.body(), self.game.world.time, self.config.art_width, self.config.art_height)
        view = View(
            status=status, log=log, art=art,'''),
    ("            scroll=0 if self.debug_visible else self.scroll,",
     "            scroll=0 if self.debug_visible or self.sheet_visible else self.scroll,"),
])
EOF
```

- [ ] **Step 4: Run tests** → `tests/test_sheet.py` PASS (4 passed), and the full suite passes.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: F4 character sheet with ASCII body chart" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 10: Invariants for bodies, long-play fuzzing, docs

**Files:**
- Rewrite: `debug/invariants.py`, `tests/test_fuzz.py`
- Modify: the debugging guide and the phase 2 spec (via the patch step below)
- Test: `tests/test_debug_body.py`

**Interfaces:**
- Consumes: everything above
- Produces:
  - New functions: `check_body(person, body) -> list[str]` and `check_arts(world, person) -> list[str]`.
  - `check_world` now also polices every person with a body (settled to now), their arts, and silver.
  - `check_turn` also catches:
    - leaks of an undiscovered constitution into a brief;
    - `completeness` keys in brief details;
    - a breakthrough that skips a realm.

- [ ] **Step 1: Write the failing test** — `tests/test_debug_body.py`
```python
import pytest

from debug.invariants import check_turn, check_world
from engine.game import Game, Turn
from narrate.brief import Brief, PersonBrief, PlaceBrief
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.techniques import martial_arts
from world.body import add_injury, to_dict


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=3, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def problems(game):
    return " | ".join(check_world(game.world))


def test_fresh_body_is_clean(game):
    assert check_world(game.world) == []


def test_body_invariants_catch_bad_numbers(game):
    world, pid = game.world, game.player.id
    body = load_body(world, pid)
    body.qi, body.deviation, body.energy_years = 1e6, 150, 3.0  # a mortal with 3 years and no bottleneck
    world.update_data(pid, body=to_dict(body))  # bypass save_body, which would clamp qi
    text = problems(game)
    assert "qi" in text and "deviation" in text and "energy" in text


def test_injury_and_meridian_invariants(game):
    world, pid = game.world, game.player.id
    body = load_body(world, pid)
    add_injury(body, "left arm", "cut", 2, world.time, "x")
    body.injuries[-1].severity = 9
    body.meridians["Lung"].state = "glowing"
    save_body(world, pid, body)
    text = problems(game)
    assert "severity 9" in text and "Lung" in text


def test_mastery_above_completeness_is_caught(game):
    world, pid = game.world, game.player.id
    art = martial_arts(world, pid)[0]
    world.relate(pid, art.technique.id, "knows", value=0.9, data={"completeness": 0.5, "known_completeness": 1.0, "source": "x"})
    assert "mastery" in problems(game)


def test_realm_label_must_match_body(game):
    game.world.update_data(game.player.id, realm="first-rate")
    assert "realm label" in problems(game)


def test_turn_catches_a_hidden_constitution_leak(game):
    world, pid = game.world, game.player.id
    body = load_body(world, pid)
    body.constitution, body.constitution_known = "Nine Yin Body", False
    save_body(world, pid, body)
    place = PlaceBrief("T", "town", "R", "plains", "spring", "dusk")
    you = PersonBrief("Hero", "you", (), "Mortal", "self")
    game.last_briefs = [Brief("cultivated", "now", place, you, None, {}, ("You have a Nine Yin Body.",), 1, "x")]
    assert any("constitution" in p for p in check_turn(game, Turn([], [], {"type": "scene"}, "s"), []))
```
`tests/test_fuzz.py` (replaces the file):
```python
"""Random play across several worlds. Any crash or invariant violation fails the run.

This is the standing bug-catcher: new systems get exercised here for free.
"""

import random

import pytest

from app import App
from config import Config

TYPED = ["look", "journal", "help", "talk li", "talk zzz", "go north", "go south", "ask work",
         "ask town", "bye", "²", "", "   ", "x" * 300, "go", "talk", "back", "9", "0",
         "cultivate", "meditate week", "meditate month", "meditate season", "rest", "breakthrough",
         "practise", "open governing", "open conception"]
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
    assert app.game.world.time > 4 * 360  # more than a year passed
    app.shutdown()
```

- [ ] **Step 2: Run to verify it fails** → `tests/test_debug_body.py` FAILS (the body rules don't exist yet). The fuzz tests are regression coverage and may already pass.

- [ ] **Step 3: Implement** — `debug/invariants.py`
```python
"""Rules that must hold after every turn. A broken rule is a bug caught early.

Checked live by the app (violations show in the log and F12 overlay) and by the
fuzz tests, so new systems are policed from the moment they exist.
"""

import re
from collections.abc import Sequence

from narrate.brief import MAX_FACTS, MAX_PROMPT
from systems.realms import MAX_REALM, REALMS, next_threshold
from world.body import INJURY_KINDS, LOCATIONS, MERIDIANS, STATES, from_dict, max_qi, settle

LEFTOVER = re.compile(r"\{\w+\}|#\w+#")
FALLBACK = re.compile(r"^\[\w+\]$")
LOWER_START = re.compile(r"(^|[.?!]\s+)[\"']?[a-z]")
NARRATIVE = {"npc", "default", "gold"}  # prose colours; dim/system lines may repeat legitimately
MAX_CHOICES = 9
EPS = 1e-6


def check_world(world) -> list[str]:
    problems = []
    player_id = world.get_meta("player_id")
    if player_id is not None and world.entity(player_id) is None:
        problems.append(f"player_id #{player_id} points at nothing")
    for person in world.entities("person"):
        places = world.targets(person.id, "located_in")
        if len(places) != 1:
            problems.append(f"{person.name} (#{person.id}) has {len(places)} locations")
        for place in places:
            if world.entity(place) is None:
                problems.append(f"{person.name} (#{person.id}) is located in missing entity #{place}")
        if person.data.get("silver", 0) < 0:
            problems.append(f"{person.name} (#{person.id}) has negative silver")
        if "body" in person.data:
            problems += check_body(person, settle(from_dict(person.data["body"]), world.time))
            problems += check_arts(world, person)
    times = world.recent_chronicle_times()
    for before, after in zip(times, times[1:]):
        if after < before:
            problems.append(f"chronicle time went backwards ({before} -> {after})")
    return problems


def check_body(person, body) -> list[str]:
    who = f"{person.name} (#{person.id})"
    out = []
    if not -EPS <= body.qi <= max_qi(body) + EPS:
        out.append(f"{who} qi {body.qi:.2f} outside 0..{max_qi(body):.2f}")
    if body.energy_years < 0:
        out.append(f"{who} has negative energy")
    if not 0 <= body.deviation <= 100:
        out.append(f"{who} deviation {body.deviation:.1f} outside 0..100")
    if not 0 <= body.realm <= MAX_REALM:
        return out + [f"{who} realm {body.realm} out of range"]
    low, high = REALMS[body.realm].threshold, next_threshold(body.realm)
    if body.energy_years < low - EPS or (high is not None and body.energy_years > high + EPS):
        out.append(f"{who} energy {body.energy_years:.3f} outside {REALMS[body.realm].name} bounds")
    elif high is not None and body.energy_years >= high - EPS and not body.bottleneck:
        out.append(f"{who} energy at {high} without a bottleneck")
    if person.data.get("realm") != REALMS[body.realm].label:
        out.append(f"{who} realm label {person.data.get('realm')!r} does not match body realm {REALMS[body.realm].label!r}")
    if set(body.meridians) != set(MERIDIANS):
        out.append(f"{who} is missing meridians")
    for name, meridian in body.meridians.items():
        if meridian.state not in STATES or not 0 <= meridian.flow <= 1:
            out.append(f"{who} {name} meridian state {meridian.state!r} flow {meridian.flow}")
    for injury in body.injuries:
        if (injury.location not in LOCATIONS or injury.kind not in INJURY_KINDS
                or not 1 <= injury.severity <= 5 or (injury.permanent and injury.heals_at is not None)):
            out.append(f"{who} has an invalid injury: {injury.location} {injury.kind} severity {injury.severity}")
    return out


def check_arts(world, person) -> list[str]:
    out = []
    for technique_id, mastery, data in world.relations_from(person.id, "knows"):
        technique = world.entity(technique_id)
        if technique is None or technique.kind != "technique":
            out.append(f"{person.name} knows #{technique_id}, which is not a technique")
        if mastery > data.get("completeness", 1.0) + EPS:
            out.append(f"{person.name} mastery {mastery:.2f} above completeness {data.get('completeness')}")
    return out


def check_turn(game, turn, recent_narration: Sequence[str]) -> list[str]:
    problems = []
    for text, key in turn.lines:
        if LEFTOVER.search(text):
            problems.append(f"leftover template slot in: {text[:80]}")
        if FALLBACK.match(text):
            problems.append(f"narration fallback, no grammar for {text}")
        if key in NARRATIVE and LOWER_START.search(text):
            problems.append(f"lowercase sentence start in: {text[:80]}")
        if key in NARRATIVE and text and text in recent_narration:
            problems.append(f"repeat of a recent line: {text[:80]}")
    if len(turn.choices) > MAX_CHOICES:
        problems.append(f"{len(turn.choices)} choices shown; only {MAX_CHOICES} have number keys")
    for choice in turn.all_choices:
        if not hasattr(game, f"_do_{choice.action.verb}"):
            problems.append(f"choice {choice.label!r} has no handler for verb {choice.action.verb!r}")
    hidden = None
    player_id = game.world.get_meta("player_id")
    player = game.world.entity(player_id) if player_id is not None else None
    if player is not None and "body" in player.data:
        body = from_dict(player.data["body"])
        if body.constitution and not body.constitution_known:
            hidden = body.constitution
    for brief in getattr(game, "last_briefs", []):
        prompt = brief.to_prompt()
        if len(brief.facts) > MAX_FACTS:
            problems.append(f"brief for {brief.kind} has {len(brief.facts)} facts (max {MAX_FACTS})")
        if len(prompt) > MAX_PROMPT:
            problems.append(f"brief for {brief.kind} is {len(prompt)} chars (max {MAX_PROMPT})")
        if LEFTOVER.search(prompt):
            problems.append(f"leftover template slot in {brief.kind} brief")
        if hidden and hidden in prompt:
            problems.append(f"undiscovered constitution leaked into a {brief.kind} brief")
        if any("completeness" in key for key in brief.details):
            problems.append(f"completeness leaked into a {brief.kind} brief")
    if player is not None:
        for entry in game.world.chronicle_about(player.id, limit=3):
            if entry.kind == "breakthrough" and entry.data.get("realm_after", 0) - entry.data.get("realm_before", 0) > 1:
                problems.append("a breakthrough skipped a realm")
    return problems
```
Write the decisions back into the spec and the debugging guide:
```bash
python - <<'EOF'
import pathlib
def patch(f, pairs):
    p = pathlib.Path(f); t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (f, a)
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8", newline="\n")
patch("docs/superpowers/specs/2026-09-22-phase2-cultivation-combat-design.md", [
    ("  - Formula: `0.01 × grade_mult(heart_method)", "  - Formula: `0.015 × grade_mult(heart_method)"),
    ("plus a `deviation` or `discovery` event when triggered.",
     "plus a `deviation` event when triggered. A discovered constitution is recorded as `discovered` on the event that revealed it."),
    ("`deviation`, `discovery`, `exchange`", "`deviation`, `exchange`"),
    ("- **New kinds:**", "- **Outcome:** `Brief.outcome` (at most 4 lines) says plainly what happened. Every narrator must convey it; the procedural narrator shows it as dim lines under the prose.\n- **New kinds:**"),
])
patch("docs/debugging.md", [
    ("- **Narrator fact sheets:** at most 6 facts, and at most 1,200 characters.",
     "- **Narrator fact sheets:** at most 6 facts, and at most 1,200 characters. They never contain an undiscovered constitution or a completeness value, and prose never starts a sentence in lowercase.\n"
     "- **Bodies:** qi is between 0 and max; energy is within the realm's bounds, with the bottleneck set at the cap; deviation is between 0 and 100; every meridian state and injury is valid; the realm label matches the body; silver is at least 0.\n"
     "- **Arts:** every known art is a technique, and mastery never exceeds completeness. No breakthrough skips a realm."),
])
EOF
```

- [ ] **Step 4: Run tests** → the full suite passes, including the fuzz tests. If the fuzz tests find violations, they are real bugs. Fix each one in its owning module with a failing test first (superpowers:systematic-debugging), and never by weakening a rule.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: body and art invariants, long-play fuzzing, docs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

## Self-review notes

- **Spec coverage for 2a:**

| Spec section | Where it's covered |
|---|---|
| §3 Body | Task 1 |
| §4 Realms | Task 2; breakthroughs in Task 5 |
| §5 Techniques | Task 3 |
| §6 Cultivation | Task 5; menus in Task 7 |
| §7 Creation | Tasks 4 and 8 |
| §8 Silver | Written at creation (Task 4) and checked by an invariant (Task 10). Payments are 2b. |
| §11 Menus and screens | Tasks 7 and 9 |
| §12 Briefs | Task 6 |
| §13 Invariants | Task 10 |
| §14 Testing | Pacing (Task 5), knowledge isolation (Tasks 6 and 10), migration (Tasks 4 and 8), determinism (replay in Task 8, fuzz in Task 10) |

- **Deferred to 2b** (spec §9–10): duels, opponent AI, encounters, challenges, teachers, manuals, fragments, technique creation, purse transactions.
- **Review Focus coverage:**

| Item | Test |
|---|---|
| 1 | `test_years_of_cultivation_stay_clean` (Task 10) |
| 2 | `test_old_saves_get_a_body_on_load` (Task 4), `test_replay_of_a_migrated_old_save` (Task 8) |
| 3 | `test_main_menu_always_fits_and_offers_cultivation`, `test_practise_and_meridian_menus` (Task 7) |
| 4 | `test_point_buy_respects_the_pool` (Task 8) |
| 5 | `test_typed_cultivation_commands`, `test_no_cultivating_mid_conversation` (Task 7) |
