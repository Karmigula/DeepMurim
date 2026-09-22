# DeepMurim Phase 1 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a playable walk-around of DeepMurim. You can:
- start a world and walk between seeded towns forever;
- talk to NPCs, who remember you across saves;
- read procedural prose beside ASCII art that docks left or right.

**Architecture:**
- A SQLite `.world` file is the single source of truth. Every change goes through `events.commit`, which appends to the chronicle and applies any registered effect in one transaction.
- Places and people are pure functions of `(world_seed, path)` until first observed. At that point they are written to the database, and from then on the database wins.
- A pure engine (`Game`) turns `Action`s into `Turn`s. A pure layout turns a `Turn` into a character grid. Only `render/screen.py` and `main.py` touch pygame.

**Tech Stack:**
- Python 3.14, pygame-ce, and the standard library: `sqlite3` with json1, `tomllib`, `hashlib`, `textwrap`.
- pytest for tests.

**Spec:** `docs/superpowers/specs/2026-09-22-deepmurim-design.md` (phase 1 = §8 item 1)

## Global Constraints

- Python 3.14 (`.venv` created with `python -m venv .venv`). Dependencies: `pygame-ce>=2.5`, `pytest>=8` only.
- Only `render/screen.py` and `main.py` may `import pygame`. `world/`, `systems/`, `engine/`, `narrate/`, `render/art.py`, `render/layout.py`, `render/menu.py`, and `app.py` must never import pygame.
- The engine is the only writer to the database. State changes happen via `world.events.commit` (generation/materialization is the one exception: it writes entities directly, inside a transaction).
- Narrators never read the database. The engine builds a `Brief` (spec §6.0) and narrators only phrase it. This is what lets Haiku narrate adequately in phase 6.
- Seeded generation must be deterministic across processes. Use `world.seed.rng_for`; never use `hash()` or unseeded `random`.
- Font: `assets/fonts/IBMPlexMono-Regular.ttf`, copied from `E:\AIExperiments\AsciiCrawler\assets\fonts\`.
- Art frame: `art_width = 40` columns, default side `left`, F2 swaps sides, F3 hides it, and both settings persist in `settings.json`.
- Time unit is the *watch*: 4 watches per day (morning, midday, dusk, night), 90 days per season, 4 seasons per year.
- Every commit message ends with a blank line then `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run tests with: `.venv/Scripts/python.exe -m pytest -q` (from the repo root).
- Spec deviation (intentional): there is no separate `materialized` table. `entities.seed_path UNIQUE` records materialization.

## Review Focus

1. **Junk on the command line.** Empty, whitespace, `999`, emoji or Cyrillic, or 5000 characters must give a harmless "unknown" or nothing, never a crash. Tested in Task 9.
2. **Ambiguous names.** `talk li` when Li Wei and Li Mei are both present must offer a choice, not pick one silently. Tested in Task 9.
3. **Tiny or odd window sizes.** At 20×6, 1×1, or a width too narrow for the art frame, the layout must return a grid of exactly that size and hide the art. Tested in Task 11.
4. **Corrupt, missing, or future-version save.** Must raise `SaveError` with a readable message, and the title screen must show it rather than crash. Tested in Tasks 3 and 12.
5. **Extreme coordinates.** Regions at (-1_000_000, 1_000_000_000) must generate the same result every time. Tested in Task 2.

---

## File map

| File | Responsibility |
|---|---|
| `requirements.txt`, `pytest.ini`, `run.bat`, `.gitignore` | project plumbing |
| `paths.py` | `bundled()` / `beside()` file locations (from AsciiCrawler) |
| `settings_store.py` | `load_values` / `save_values` JSON settings |
| `config.py` | `Config` dataclass, `PALETTE`, `config_from(values)` |
| `world/seed.py` | `seed_for`, `rng_for` |
| `world/gen/names.py` | name tables and pickers |
| `world/gen/region.py`, `town.py`, `npc.py` | pure seeded specs |
| `world/gen/materialize.py` | seed spec → DB entity, `people_at`, labels |
| `world/db.py` | `World`, `Entity`, `ChronicleEntry`, `Memory`, `SaveError` |
| `world/events.py` | `Event`, `Witness`, `effect`, `commit` |
| `systems/time.py` | watches/dates, `advance` |
| `systems/travel.py` | routes, travel events, travel effect, `location_of` |
| `systems/talk.py` | greet/ask/farewell events, talk effects |
| `narrate/base.py`, `narrate/proposals.py` | `Narrator` protocol (`narrate(brief)`), `Line`, proposal types (phase-6 seam) |
| `narrate/brief.py` | `Brief`: engine-built, id-free, ranked facts; the only input any narrator (grammar or Haiku) gets |
| `narrate/procedural.py`, `narrate/grammar/core.toml` | Tracery-lite grammar narrator |
| `engine/game.py`, `engine/journal.py`, `engine/commands.py` | `Game`, `Action`, `Choice`, `Turn`, parser |
| `render/art.py`, `assets/art/*.art` | art parsing and composition |
| `render/layout.py`, `render/menu.py` | pure grid composition |
| `render/screen.py`, `app.py`, `main.py` | pygame window, key-driven app state, loop |

---

### Task 1: Project scaffold, settings, config

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `paths.py`, `settings_store.py`, `config.py`, `world/__init__.py`, `world/gen/__init__.py`, `systems/__init__.py`, `engine/__init__.py`, `narrate/__init__.py`, `render/__init__.py`, `assets/fonts/IBMPlexMono-Regular.ttf` (copied)
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `paths.bundled(*parts) -> Path`, `paths.beside(*parts) -> Path`, `settings_store.load_values(path=None) -> dict`, `settings_store.save_values(values, path=None) -> bool`, `config.Color`, `config.PALETTE: dict[str, Color]`, `config.Config`, `config.config_from(values: dict) -> Config`

- [ ] **Step 1: Plumbing files and venv**

`requirements.txt`:
```
pygame-ce>=2.5
pytest>=8
```
`pytest.ini`:
```
[pytest]
testpaths = tests
pythonpath = .
```
Create empty `__init__.py` in `world/`, `world/gen/`, `systems/`, `engine/`, `narrate/`, `render/`. Then run:
```bash
mkdir -p assets/fonts tests && cp /e/AIExperiments/AsciiCrawler/assets/fonts/IBMPlexMono-Regular.ttf assets/fonts/
python -m venv .venv && .venv/Scripts/python.exe -m pip install -q -r requirements.txt
```

- [ ] **Step 2: Write the failing test** — `tests/test_settings.py`
```python
from config import config_from
from settings_store import load_values, save_values


def test_roundtrip(tmp_path):
    path = tmp_path / "s.json"
    assert save_values({"art_side": "right"}, path)
    assert load_values(path) == {"art_side": "right"}


def test_missing_and_corrupt_give_empty(tmp_path):
    assert load_values(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert load_values(bad) == {}


def test_config_applies_settings():
    config = config_from({"art_side": "right", "show_art": False})
    assert config.art_side == "right"
    assert config.show_art is False


def test_config_ignores_bad_values():
    config = config_from({"art_side": "up", "show_art": "yes"})
    assert config.art_side == "left"
    assert config.show_art is True
```

- [ ] **Step 3: Run it to verify it fails** — `.venv/Scripts/python.exe -m pytest tests/test_settings.py -q` → FAIL (`ModuleNotFoundError: config`)

- [ ] **Step 4: Implement**

`paths.py`:
```python
"""Where things are, whether running from source or frozen into one exe.

Bundled files ship inside the game (fonts, art, grammar). Beside files belong
to the player (saves, settings) and live next to the game so they survive
upgrades.
"""

import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
_SOURCE = Path(__file__).resolve().parent


def bundled(*parts) -> Path:
    """A read-only file shipped with the game."""
    root = Path(getattr(sys, "_MEIPASS", _SOURCE)) if FROZEN else _SOURCE
    return root.joinpath(*parts)


def beside(*parts) -> Path:
    """A file the player owns, next to the game rather than inside it."""
    root = Path(sys.executable).resolve().parent if FROZEN else _SOURCE
    return root.joinpath(*parts)
```
`settings_store.py`:
```python
"""A flat JSON file of preferences. Every failure is silent and gives defaults."""

import json
from pathlib import Path

from paths import beside

DEFAULT_PATH = beside("settings.json")


def load_values(path: Path | None = None) -> dict:
    target = DEFAULT_PATH if path is None else path
    try:
        with open(target, encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


def save_values(values: dict, path: Path | None = None) -> bool:
    target = DEFAULT_PATH if path is None else path
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(values, handle, indent=2)
    except OSError:
        return False
    return True
```
`config.py`:
```python
"""Every size and colour in one place."""

from dataclasses import dataclass

Color = tuple[int, int, int]

PALETTE: dict[str, Color] = {
    "default": (205, 200, 190),
    "dim": (115, 112, 108),
    "system": (140, 140, 165),
    "player": (240, 220, 150),
    "npc": (150, 200, 230),
    "gold": (225, 185, 85),
    "jade": (90, 195, 145),
    "red": (205, 75, 65),
    "blue": (95, 145, 215),
    "sky": (125, 165, 215),
    "white": (235, 235, 230),
    "brown": (160, 115, 75),
    "green": (95, 165, 85),
    "grey": (145, 145, 145),
    "purple": (165, 115, 195),
    "rule": (70, 70, 80),
}


@dataclass
class Config:
    window_title: str = "DeepMurim"
    window_width: int = 1280
    window_height: int = 800
    font_path: str = "assets/fonts/IBMPlexMono-Regular.ttf"
    font_size: int = 16
    background_color: Color = (12, 12, 16)
    art_width: int = 40
    art_height: int = 18
    art_side: str = "left"
    show_art: bool = True


def config_from(values: dict) -> Config:
    """A Config with any valid stored preferences applied; bad values ignored."""
    config = Config()
    if values.get("art_side") in ("left", "right"):
        config.art_side = values["art_side"]
    if isinstance(values.get("show_art"), bool):
        config.show_art = values["show_art"]
    return config
```

- [ ] **Step 5: Run tests** → PASS (4 passed)

- [ ] **Step 6: Commit**
```bash
git add -A && git commit -m "chore: scaffold project, settings, config" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Seeded generation (pure specs)

**Files:**
- Create: `world/seed.py`, `world/gen/names.py`, `world/gen/region.py`, `world/gen/town.py`, `world/gen/npc.py`
- Test: `tests/test_gen.py`

**Interfaces:**
- Produces:
  - `seed_for(world_seed: int, path: str) -> int`, `rng_for(world_seed, path) -> random.Random`
  - `TERRAINS`, `RegionSpec(x, y, name, terrain, town_count)`, `region_path(x, y) -> str`, `region_spec(world_seed, x, y) -> RegionSpec`
  - `TownSpec(x, y, index, name, kind, terrain, npc_count)`, `town_path(x, y, i) -> str`, `town_spec(world_seed, x, y, i) -> TownSpec` (raises `ValueError` if `i` is out of range)
  - `NpcSpec(surname, given, gender, age, occupation, traits, realm, portrait)` with `.name`, `npc_path(town_path, i) -> str`, `npc_spec(world_seed, town_path, i) -> NpcSpec`
  - `PORTRAIT_PARTS = {"hair": 4, "face": 4, "robe": 4}`

- [ ] **Step 1: Write the failing test** — `tests/test_gen.py`
```python
import subprocess
import sys

import pytest

from world.gen.npc import npc_spec
from world.gen.region import TERRAINS, region_spec
from world.gen.town import town_path, town_spec
from world.seed import seed_for


def test_seed_is_stable_and_distinct():
    assert seed_for(1, "a") == seed_for(1, "a")
    assert seed_for(1, "a") != seed_for(1, "b")
    assert seed_for(1, "a") != seed_for(2, "a")


def test_region_is_deterministic_at_extreme_coordinates():
    assert region_spec(7, -1_000_000, 1_000_000_000) == region_spec(7, -1_000_000, 1_000_000_000)


def test_regions_vary():
    terrains = {region_spec(3, x, 0).terrain for x in range(60)}
    assert len(terrains) > 2 and terrains <= set(TERRAINS)


def test_town_index_out_of_range():
    count = region_spec(5, 0, 0).town_count
    with pytest.raises(ValueError):
        town_spec(5, 0, 0, count)


def test_npc_same_in_another_process():
    here = repr(npc_spec(99, town_path(0, 0, 0), 2))
    code = (
        "from world.gen.npc import npc_spec; from world.gen.town import town_path;"
        "print(repr(npc_spec(99, town_path(0, 0, 0), 2)))"
    )
    there = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert here == there


def test_npc_has_full_portrait():
    spec = npc_spec(1, town_path(0, 0, 0), 0)
    assert dict(spec.portrait).keys() == {"hair", "face", "robe"}
    assert spec.name == f"{spec.surname} {spec.given}"
```

- [ ] **Step 2: Run to verify fails** — `.venv/Scripts/python.exe -m pytest tests/test_gen.py -q` → FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement**

`world/seed.py`:
```python
"""Deterministic randomness keyed by a path through the world.

The same (world_seed, path) gives the same numbers in every process and every
run, which is what lets an unvisited town exist without being stored.
"""

import hashlib
import random


def seed_for(world_seed: int, path: str) -> int:
    digest = hashlib.blake2b(f"{world_seed}/{path}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def rng_for(world_seed: int, path: str) -> random.Random:
    return random.Random(seed_for(world_seed, path))
```
`world/gen/names.py`:
```python
"""Name tables. Chinese and Korean murim flavour, mixed on purpose."""

import random

SURNAMES = (
    "Li", "Wang", "Zhang", "Chen", "Zhao", "Namgung", "Jegal", "Dang", "Moyong", "Peng",
    "Hwang", "Baek", "Seo", "Mok", "Yeon", "Tang", "Ma", "Gu", "Jin", "Ha",
)
GIVEN_HEAD = (
    "Wei", "Jin", "Hao", "Mei", "Lan", "Tae", "Seo", "Yun", "Feng", "Ling",
    "Ho", "Min", "Rin", "Shen", "Kai", "Yeon", "Bo", "Xue", "Ha", "Do",
)
GIVEN_TAIL = ("", "", "long", "hwa", "yang", "ryeong", "an", "jun", "yu", "ming", "su", "hyun", "rou", "woo")
PLACE_PREFIX = (
    "Azure", "Jade", "Crimson", "White Crane", "Iron", "Misty", "Willow", "Plum Blossom",
    "Black Rock", "Golden", "Stone Bridge", "Autumn", "Red Cliff", "Cloud", "Pine",
    "Thunder", "Silver", "Falling Leaf", "Nine Bends", "Dragon Well",
)
SETTLEMENT_SUFFIX = {"village": "Village", "town": "Town", "city": "City"}
REGION_NOUN = {
    "plains": "Plains", "mountains": "Peaks", "river": "Riverlands",
    "forest": "Woods", "marsh": "Marshes", "hills": "Hills",
}


def person_name(rng: random.Random) -> tuple[str, str]:
    return rng.choice(SURNAMES), rng.choice(GIVEN_HEAD) + rng.choice(GIVEN_TAIL)


def place_name(rng: random.Random, suffix: str) -> str:
    return f"{rng.choice(PLACE_PREFIX)} {suffix}"
```
`world/gen/region.py`:
```python
from dataclasses import dataclass

from world.gen.names import REGION_NOUN, place_name
from world.seed import rng_for

TERRAINS = ("plains", "mountains", "river", "forest", "marsh", "hills")


@dataclass(frozen=True)
class RegionSpec:
    x: int
    y: int
    name: str
    terrain: str
    town_count: int


def region_path(x: int, y: int) -> str:
    return f"region:{x},{y}"


def region_spec(world_seed: int, x: int, y: int) -> RegionSpec:
    rng = rng_for(world_seed, region_path(x, y))
    terrain = rng.choice(TERRAINS)
    return RegionSpec(x, y, "the " + place_name(rng, REGION_NOUN[terrain]), terrain, rng.randint(1, 3))
```
`world/gen/town.py`:
```python
from dataclasses import dataclass

from world.gen.names import SETTLEMENT_SUFFIX, place_name
from world.gen.region import region_path, region_spec
from world.seed import rng_for

KINDS = ("village", "village", "town", "town", "city")
NPC_COUNT = {"village": (2, 4), "town": (3, 6), "city": (5, 8)}


@dataclass(frozen=True)
class TownSpec:
    x: int
    y: int
    index: int
    name: str
    kind: str
    terrain: str
    npc_count: int


def town_path(x: int, y: int, i: int) -> str:
    return f"{region_path(x, y)}/town:{i}"


def town_spec(world_seed: int, x: int, y: int, i: int) -> TownSpec:
    region = region_spec(world_seed, x, y)
    if not 0 <= i < region.town_count:
        raise ValueError(f"region {x},{y} has {region.town_count} towns, not index {i}")
    rng = rng_for(world_seed, town_path(x, y, i))
    kind = rng.choice(KINDS)
    low, high = NPC_COUNT[kind]
    return TownSpec(x, y, i, place_name(rng, SETTLEMENT_SUFFIX[kind]), kind, region.terrain, rng.randint(low, high))
```
`world/gen/npc.py`:
```python
from dataclasses import dataclass

from world.gen.names import person_name
from world.seed import rng_for

OCCUPATIONS = (
    "innkeeper", "herbalist", "blacksmith", "merchant", "wandering swordsman", "beggar",
    "scholar", "hunter", "constable", "tea seller", "monk", "fortune teller",
)
TRAITS = (
    "proud", "kind", "greedy", "cautious", "hot-tempered", "curious",
    "honest", "cunning", "lazy", "loyal", "secretive", "cheerful",
)
REALMS = ("mortal", "mortal", "mortal", "third-rate", "third-rate", "second-rate", "first-rate")
PORTRAIT_PARTS = {"hair": 4, "face": 4, "robe": 4}


@dataclass(frozen=True)
class NpcSpec:
    surname: str
    given: str
    gender: str
    age: int
    occupation: str
    traits: tuple[str, str]
    realm: str
    portrait: tuple[tuple[str, int], ...]

    @property
    def name(self) -> str:
        return f"{self.surname} {self.given}"


def npc_path(town_path: str, i: int) -> str:
    return f"{town_path}/npc:{i}"


def npc_spec(world_seed: int, town_path: str, i: int) -> NpcSpec:
    rng = rng_for(world_seed, npc_path(town_path, i))
    surname, given = person_name(rng)
    return NpcSpec(
        surname=surname,
        given=given,
        gender=rng.choice(("man", "woman")),
        age=rng.randint(16, 70),
        occupation=rng.choice(OCCUPATIONS),
        traits=tuple(rng.sample(TRAITS, 2)),
        realm=rng.choice(REALMS),
        portrait=tuple((part, rng.randrange(count)) for part, count in PORTRAIT_PARTS.items()),
    )
```

- [ ] **Step 4: Run tests** → PASS (6 passed)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: seeded region/town/npc generation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 3: World database

**Files:**
- Create: `world/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces:
  - `SaveError(Exception)`
  - `Entity(id, kind, name, seed_path, created_at, data: dict)`
  - `ChronicleEntry(id, time, kind, actors: tuple[int,...], place, data, weight)`
  - `Memory(owner, event: ChronicleEntry, feeling, intensity, indelible)`
- `World` methods:
  - Lifecycle: `create(path, world_seed)` (classmethod), `open(path)` (classmethod), `close()`, `transaction()` (a context manager, nestable), `digest() -> str`.
  - Meta: `get_meta(key, default=None)`, `set_meta(key, value)`, the properties `world_seed` and `time`, and `set_time(t)`.
  - Entities: `add_entity(kind, name, data=None, seed_path=None) -> int`, `entity(id) -> Entity | None`, `entity_by_seed(path) -> Entity | None`, `entities(kind) -> list[Entity]`, `update_data(id, **changes)`.
  - Relations: `relate(a, b, kind, value=0.0, data=None)`, `unrelate(a, kind, b=None)`, `targets(a, kind) -> list[int]`, `sources(b, kind) -> list[int]`.
  - History: `append_chronicle(kind, actors, place, data, weight) -> int`, `chronicle_about(entity_id, limit=20) -> list[ChronicleEntry]` (newest first), `add_memory(owner, event_id, feeling, intensity, indelible=False)`, `memories(owner, about=None) -> list[Memory]` (oldest first).

- [ ] **Step 1: Write the failing test** — `tests/test_db.py`
```python
import sqlite3

import pytest

from world.db import SCHEMA_VERSION, SaveError, World


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "t.world", world_seed=42)
    yield w
    w.close()


def test_create_and_reopen(tmp_path):
    path = tmp_path / "a.world"
    World.create(path, 7).close()
    w = World.open(path)
    assert w.world_seed == 7 and w.time == 0
    w.close()


def test_create_refuses_existing(tmp_path):
    path = tmp_path / "a.world"
    World.create(path, 1).close()
    with pytest.raises(SaveError):
        World.create(path, 1)


def test_open_missing_corrupt_and_future(tmp_path):
    with pytest.raises(SaveError, match="No save"):
        World.open(tmp_path / "missing.world")
    junk = tmp_path / "junk.world"
    junk.write_bytes(b"this is not sqlite at all" * 100)
    with pytest.raises(SaveError):
        World.open(junk)
    future = tmp_path / "future.world"
    w = World.create(future, 1)
    w.set_meta("schema_version", SCHEMA_VERSION + 1)
    w.close()
    with pytest.raises(SaveError, match="version"):
        World.open(future)


def test_entities(world):
    eid = world.add_entity("person", "Li Wei", {"age": 30}, seed_path="p/1")
    assert world.entity(eid).data == {"age": 30}
    assert world.entity_by_seed("p/1").id == eid
    world.update_data(eid, age=31, scar=True)
    assert world.entity(eid).data == {"age": 31, "scar": True}
    assert [e.id for e in world.entities("person")] == [eid]
    assert world.entity(9999) is None
    with pytest.raises(sqlite3.IntegrityError):
        world.add_entity("person", "Dup", seed_path="p/1")


def test_relations(world):
    a, b, c = (world.add_entity("x", n) for n in "abc")
    world.relate(a, b, "located_in")
    world.relate(a, b, "located_in", value=2.0)  # upsert, no duplicate
    world.relate(c, b, "located_in")
    assert world.targets(a, "located_in") == [b]
    assert world.sources(b, "located_in") == [a, c]
    world.unrelate(a, "located_in")
    assert world.targets(a, "located_in") == []


def test_transaction_rolls_back(world):
    with pytest.raises(RuntimeError):
        with world.transaction():
            world.add_entity("ghost", "Nobody")
            with world.transaction():  # nested joins the outer one
                world.add_entity("ghost", "Nobody2")
            raise RuntimeError
    assert world.entities("ghost") == []


def test_chronicle_and_memories(world):
    a, b, c = (world.add_entity("person", n) for n in "abc")
    e1 = world.append_chronicle("met", (a, b), None, {}, 1.0)
    e2 = world.append_chronicle("met", (c, b), None, {}, 1.0)
    world.add_memory(b, e1, "curious", 0.3)
    world.add_memory(b, e2, "wary", 0.5, indelible=True)
    assert [m.event.id for m in world.memories(b)] == [e1, e2]
    assert [m.event.id for m in world.memories(b, about=a)] == [e1]
    assert world.memories(b, about=c)[0].indelible is True
    assert [e.id for e in world.chronicle_about(b)] == [e2, e1]


def test_digest_changes_with_state(world):
    before = world.digest()
    world.add_entity("x", "y")
    assert world.digest() != before
```

- [ ] **Step 2: Run to verify fails** → FAIL (ModuleNotFoundError: world.db)

- [ ] **Step 3: Implement** — `world/db.py`
```python
"""The world file: one SQLite database per save, the single source of truth.

Nothing outside the engine writes here. Every table stays even when a system
doesn't use it yet, so later phases add tables rather than reshaping these.
"""

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
create table if not exists meta(key text primary key, value text not null);
create table if not exists entities(
    id integer primary key, kind text not null, name text not null,
    seed_path text unique, created_at integer not null, data text not null default '{}');
create table if not exists relations(
    a integer not null, b integer not null, kind text not null,
    value real not null default 0, since integer not null, data text not null default '{}',
    primary key(a, b, kind));
create index if not exists relations_b on relations(b, kind);
create table if not exists chronicle(
    id integer primary key, time integer not null, kind text not null,
    actors text not null, place integer, data text not null default '{}',
    weight real not null default 1);
create table if not exists memories(
    owner integer not null, event_id integer not null, feeling text not null,
    intensity real not null, indelible integer not null default 0,
    primary key(owner, event_id));
create table if not exists facts(
    id integer primary key, subject integer not null, predicate text not null,
    object text not null, time integer not null, source_event integer);
create table if not exists beliefs(
    knower integer not null, fact_id integer not null, variant text not null default '{}',
    source integer, confidence real not null, learned_at integer not null,
    primary key(knower, fact_id));
"""

TABLES = ("meta", "entities", "relations", "chronicle", "memories", "facts", "beliefs")
_ENTRY_COLUMNS = "c.id, c.time, c.kind, c.actors, c.place, c.data, c.weight"


class SaveError(Exception):
    """A save file that can't be opened, with a message fit to show a player."""


@dataclass(frozen=True)
class Entity:
    id: int
    kind: str
    name: str
    seed_path: str | None
    created_at: int
    data: dict


@dataclass(frozen=True)
class ChronicleEntry:
    id: int
    time: int
    kind: str
    actors: tuple[int, ...]
    place: int | None
    data: dict
    weight: float


@dataclass(frozen=True)
class Memory:
    owner: int
    event: ChronicleEntry
    feeling: str
    intensity: float
    indelible: bool


def _entry(row) -> ChronicleEntry:
    return ChronicleEntry(row[0], row[1], row[2], tuple(json.loads(row[3])), row[4], json.loads(row[5]), row[6])


def _entity(row) -> Entity | None:
    if row is None:
        return None
    return Entity(row[0], row[1], row[2], row[3], row[4], json.loads(row[5]))


class World:
    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        self._conn = conn
        self.path = path
        self._depth = 0

    @classmethod
    def create(cls, path, world_seed: int) -> "World":
        path = Path(path)
        if path.exists():
            raise SaveError(f"{path.name} already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = cls._connect(path)
        conn.executescript(SCHEMA)
        world = cls(conn, path)
        with world.transaction():
            world.set_meta("schema_version", SCHEMA_VERSION)
            world.set_meta("world_seed", world_seed)
            world.set_meta("time", 0)
        return world

    @classmethod
    def open(cls, path) -> "World":
        path = Path(path)
        if not path.is_file():
            raise SaveError(f"No save at {path}")
        try:
            conn = cls._connect(path)
            row = conn.execute("select value from meta where key = 'schema_version'").fetchone()
        except sqlite3.DatabaseError as exc:
            raise SaveError(f"{path.name} is not a DeepMurim save ({exc})") from exc
        version = json.loads(row[0]) if row else None
        if version != SCHEMA_VERSION:
            conn.close()
            raise SaveError(f"{path.name} has save version {version}; this game reads version {SCHEMA_VERSION}")
        return cls(conn, path)

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(path, isolation_level=None)
        conn.execute("pragma journal_mode = wal")
        return conn

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """All-or-nothing. Nested calls join the outermost transaction."""
        if self._depth == 0:
            self._conn.execute("begin immediate")
        self._depth += 1
        try:
            yield
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self._conn.execute("rollback")
            raise
        self._depth -= 1
        if self._depth == 0:
            self._conn.execute("commit")

    # --- meta -------------------------------------------------------------
    def get_meta(self, key: str, default=None):
        row = self._conn.execute("select value from meta where key = ?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    def set_meta(self, key: str, value) -> None:
        self._conn.execute(
            "insert into meta(key, value) values(?, ?) on conflict(key) do update set value = excluded.value",
            (key, json.dumps(value)),
        )

    @property
    def world_seed(self) -> int:
        return int(self.get_meta("world_seed"))

    @property
    def time(self) -> int:
        return int(self.get_meta("time", 0))

    def set_time(self, t: int) -> None:
        self.set_meta("time", t)

    # --- entities ---------------------------------------------------------
    def add_entity(self, kind: str, name: str, data: dict | None = None, seed_path: str | None = None) -> int:
        cursor = self._conn.execute(
            "insert into entities(kind, name, seed_path, created_at, data) values(?, ?, ?, ?, ?)",
            (kind, name, seed_path, self.time, json.dumps(data or {})),
        )
        return cursor.lastrowid

    def entity(self, entity_id: int) -> Entity | None:
        return _entity(self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities where id = ?", (entity_id,)
        ).fetchone())

    def entity_by_seed(self, seed_path: str) -> Entity | None:
        return _entity(self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities where seed_path = ?", (seed_path,)
        ).fetchone())

    def entities(self, kind: str) -> list[Entity]:
        rows = self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities where kind = ? order by id", (kind,)
        )
        return [_entity(row) for row in rows]

    def update_data(self, entity_id: int, **changes) -> None:
        current = self.entity(entity_id)
        if current is None:
            raise KeyError(entity_id)
        merged = {**current.data, **changes}
        self._conn.execute("update entities set data = ? where id = ?", (json.dumps(merged), entity_id))

    # --- relations --------------------------------------------------------
    def relate(self, a: int, b: int, kind: str, value: float = 0.0, data: dict | None = None) -> None:
        self._conn.execute(
            "insert into relations(a, b, kind, value, since, data) values(?, ?, ?, ?, ?, ?) "
            "on conflict(a, b, kind) do update set value = excluded.value, data = excluded.data",
            (a, b, kind, value, self.time, json.dumps(data or {})),
        )

    def unrelate(self, a: int, kind: str, b: int | None = None) -> None:
        if b is None:
            self._conn.execute("delete from relations where a = ? and kind = ?", (a, kind))
        else:
            self._conn.execute("delete from relations where a = ? and b = ? and kind = ?", (a, b, kind))

    def targets(self, a: int, kind: str) -> list[int]:
        rows = self._conn.execute("select b from relations where a = ? and kind = ? order by since, b", (a, kind))
        return [row[0] for row in rows]

    def sources(self, b: int, kind: str) -> list[int]:
        rows = self._conn.execute("select a from relations where b = ? and kind = ? order by a", (b, kind))
        return [row[0] for row in rows]

    # --- chronicle & memories ----------------------------------------------
    def append_chronicle(self, kind: str, actors: Sequence[int], place: int | None, data: dict, weight: float) -> int:
        cursor = self._conn.execute(
            "insert into chronicle(time, kind, actors, place, data, weight) values(?, ?, ?, ?, ?, ?)",
            (self.time, kind, json.dumps(list(actors)), place, json.dumps(data), weight),
        )
        return cursor.lastrowid

    def chronicle_about(self, entity_id: int, limit: int = 20) -> list[ChronicleEntry]:
        rows = self._conn.execute(
            f"select {_ENTRY_COLUMNS} from chronicle c "
            "where exists(select 1 from json_each(c.actors) where json_each.value = ?) "
            "order by c.id desc limit ?",
            (entity_id, limit),
        )
        return [_entry(row) for row in rows]

    def add_memory(self, owner: int, event_id: int, feeling: str, intensity: float, indelible: bool = False) -> None:
        self._conn.execute(
            "insert into memories(owner, event_id, feeling, intensity, indelible) values(?, ?, ?, ?, ?)",
            (owner, event_id, feeling, intensity, int(indelible)),
        )

    def memories(self, owner: int, about: int | None = None) -> list[Memory]:
        sql = (
            f"select m.owner, m.feeling, m.intensity, m.indelible, {_ENTRY_COLUMNS} "
            "from memories m join chronicle c on c.id = m.event_id where m.owner = ?"
        )
        params: list = [owner]
        if about is not None:
            sql += " and exists(select 1 from json_each(c.actors) where json_each.value = ?)"
            params.append(about)
        rows = self._conn.execute(sql + " order by c.id", params)
        return [Memory(row[0], _entry(row[4:]), row[1], row[2], bool(row[3])) for row in rows]

    # --- integrity ----------------------------------------------------------
    def digest(self) -> str:
        """A hash of every row, for proving a save reloads identically."""
        h = hashlib.sha256()
        for table in TABLES:
            rows = sorted(repr(row) for row in self._conn.execute(f"select * from {table}"))
            h.update(table.encode())
            for row in rows:
                h.update(row.encode())
        return h.hexdigest()
```

- [ ] **Step 4: Run tests** → PASS (8 passed)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: SQLite world database" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 4: Events, effects, time

**Files:**
- Create: `world/events.py`, `systems/time.py`
- Test: `tests/test_events.py`

**Interfaces:**
- Consumes: `World` (Task 3)
- Produces:
  - `Witness(owner, feeling, intensity, indelible=False)`
  - `Event(kind, actors, place=None, data={}, weight=1.0, witnesses=())`
  - `EFFECTS`, `effect(kind)` decorator, `commit(world, events) -> list[int]`
  - `systems.time`:
    - Constants: `WATCHES_PER_DAY = 4`, `SEASONS`, `WATCH_NAMES`
    - `season_of(t) -> str` (lowercase)
    - `format_date(t) -> str`
    - `format_season_year(t) -> str`, for example `"the spring of year 1"`
    - `advance(world, watches)`

- [ ] **Step 1: Write the failing test** — `tests/test_events.py`
```python
import pytest

from systems.time import advance, format_date, format_season_year, season_of
from world.db import World
from world.events import EFFECTS, Event, Witness, commit, effect


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "t.world", 1)
    yield w
    w.close()


def test_commit_writes_chronicle_and_memories(world):
    a, b = world.add_entity("person", "A"), world.add_entity("person", "B")
    [eid] = commit(world, [Event("met", (a, b), None, {"x": 1}, witnesses=(Witness(b, "curious", 0.3),))])
    assert world.chronicle_about(a)[0].id == eid
    assert world.memories(b)[0].feeling == "curious"


def test_effect_runs_and_failure_rolls_back(world):
    calls = []

    @effect("test_ok")
    def _ok(w, ev):
        calls.append(ev.kind)

    @effect("test_boom")
    def _boom(w, ev):
        raise RuntimeError("boom")

    try:
        a = world.add_entity("person", "A")
        commit(world, [Event("test_ok", (a,))])
        assert calls == ["test_ok"]
        with pytest.raises(RuntimeError):
            commit(world, [Event("test_ok", (a,)), Event("test_boom", (a,))])
        assert len(world.chronicle_about(a)) == 1
    finally:
        EFFECTS.pop("test_ok", None)
        EFFECTS.pop("test_boom", None)


def test_time_formatting(world):
    assert format_date(0) == "Year 1, Spring day 1, morning"
    one_season_and_a_bit = 90 * 4 + 4 + 2
    assert format_date(one_season_and_a_bit) == "Year 1, Summer day 2, dusk"
    assert format_date(360 * 4) == "Year 2, Spring day 1, morning"
    assert season_of(90 * 4) == "summer"
    assert format_season_year(0) == "the spring of year 1"
    advance(world, 5)
    assert world.time == 5
```

- [ ] **Step 2: Run to verify fails** → FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement**

`world/events.py`:
```python
"""Every state change is an Event, committed atomically with its effects."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from world.db import World


@dataclass(frozen=True)
class Witness:
    owner: int
    feeling: str
    intensity: float
    indelible: bool = False


@dataclass(frozen=True)
class Event:
    kind: str
    actors: tuple[int, ...]
    place: int | None = None
    data: dict = field(default_factory=dict)
    weight: float = 1.0
    witnesses: tuple[Witness, ...] = ()


Effect = Callable[[World, Event], None]
EFFECTS: dict[str, Effect] = {}


def effect(kind: str) -> Callable[[Effect], Effect]:
    """Register how an event kind changes state beyond being recorded."""
    def register(fn: Effect) -> Effect:
        EFFECTS[kind] = fn
        return fn
    return register


def commit(world: World, events: Sequence[Event]) -> list[int]:
    """Record, remember and apply events; all of them or none of them."""
    ids = []
    with world.transaction():
        for event in events:
            event_id = world.append_chronicle(event.kind, event.actors, event.place, event.data, event.weight)
            for witness in event.witnesses:
                world.add_memory(witness.owner, event_id, witness.feeling, witness.intensity, witness.indelible)
            apply = EFFECTS.get(event.kind)
            if apply is not None:
                apply(world, event)
            ids.append(event_id)
    return ids
```
`systems/time.py`:
```python
"""The calendar. One tick is a watch: four to a day."""

from world.db import World

WATCHES_PER_DAY = 4
DAYS_PER_SEASON = 90
SEASONS = ("Spring", "Summer", "Autumn", "Winter")
WATCH_NAMES = ("morning", "midday", "dusk", "night")


def _parts(t: int) -> tuple[int, str, int, str]:
    day = t // WATCHES_PER_DAY
    year = day // (DAYS_PER_SEASON * 4) + 1
    season = SEASONS[(day % (DAYS_PER_SEASON * 4)) // DAYS_PER_SEASON]
    return year, season, day % DAYS_PER_SEASON + 1, WATCH_NAMES[t % WATCHES_PER_DAY]


def season_of(t: int) -> str:
    return _parts(t)[1].lower()


def format_date(t: int) -> str:
    year, season, day, watch = _parts(t)
    return f"Year {year}, {season} day {day}, {watch}"


def format_season_year(t: int) -> str:
    year, season, _, _ = _parts(t)
    return f"the {season.lower()} of year {year}"


def advance(world: World, watches: int) -> None:
    world.set_time(world.time + watches)
```

- [ ] **Step 4: Run tests** → PASS (3 passed)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: events, effects and calendar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 5: Materialization

**Files:**
- Create: `world/gen/materialize.py`
- Test: `tests/test_materialize.py`

**Interfaces:**
- Consumes: specs (Task 2), `World` (Task 3)
- Produces:
  - `ensure_region(world, x, y) -> int`
  - `ensure_town(world, x, y, i) -> int`
  - `populate(world, town_id) -> list[Entity]` (idempotent; returns the people present)
  - `people_at(world, place_id, exclude=None) -> list[Entity]`
  - `town_label(world, x, y, i) -> str`, `region_label(world, x, y) -> str` (the database wins over the seed)
  - `region_of(world, town_id) -> Entity`
- Entity data shapes:
  - region: `{"x", "y", "terrain", "town_count"}`
  - town: `{"x", "y", "index", "kind", "terrain", "npc_count", "populated"}`
  - person: `{"surname", "given", "gender", "age", "occupation", "traits": [..], "realm", "portrait": {"hair": n, "face": n, "robe": n}}`

- [ ] **Step 1: Write the failing test** — `tests/test_materialize.py`
```python
import pytest

from world.db import World
from world.gen.materialize import ensure_town, people_at, populate, region_of, town_label
from world.gen.town import town_spec


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "t.world", 42)
    yield w
    w.close()


def test_ensure_town_is_idempotent_and_linked(world):
    tid = ensure_town(world, 0, 0, 0)
    assert ensure_town(world, 0, 0, 0) == tid
    assert region_of(world, tid).data["x"] == 0
    assert world.entity(tid).name == town_spec(42, 0, 0, 0).name


def test_populate_once(world):
    tid = ensure_town(world, 0, 0, 0)
    people = populate(world, tid)
    assert len(people) == world.entity(tid).data["npc_count"]
    assert [p.id for p in populate(world, tid)] == [p.id for p in people]
    assert {"occupation", "portrait", "traits"} <= people[0].data.keys()


def test_database_wins_over_seed(world):
    tid = ensure_town(world, 0, 0, 0)
    people = populate(world, tid)
    other = ensure_town(world, 1, 0, 0)
    mover = people[0]
    world.unrelate(mover.id, "located_in")
    world.relate(mover.id, other, "located_in")
    assert mover.id not in [p.id for p in populate(world, tid)]
    world._conn.execute("update entities set name = 'Renamed' where id = ?", (tid,))
    assert town_label(world, 0, 0, 0) == "Renamed"


def test_same_seed_same_people(tmp_path):
    names = []
    for n in range(2):
        w = World.create(tmp_path / f"{n}.world", 42)
        names.append([p.name for p in populate(w, ensure_town(w, 0, 0, 0))])
        w.close()
    assert names[0] == names[1]


def test_people_at_excludes(world):
    tid = ensure_town(world, 0, 0, 0)
    people = populate(world, tid)
    assert people[0].id not in [p.id for p in people_at(world, tid, exclude=people[0].id)]
```

- [ ] **Step 2: Run to verify fails** → FAIL

- [ ] **Step 3: Implement** — `world/gen/materialize.py`
```python
"""Turning seeds into records. After this, the database wins over the seed."""

from world.db import Entity, World
from world.gen.npc import npc_path, npc_spec
from world.gen.region import region_path, region_spec
from world.gen.town import town_path, town_spec


def ensure_region(world: World, x: int, y: int) -> int:
    path = region_path(x, y)
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    spec = region_spec(world.world_seed, x, y)
    data = {"x": x, "y": y, "terrain": spec.terrain, "town_count": spec.town_count}
    return world.add_entity("region", spec.name, data, path)


def ensure_town(world: World, x: int, y: int, i: int) -> int:
    path = town_path(x, y, i)
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    spec = town_spec(world.world_seed, x, y, i)
    with world.transaction():
        region_id = ensure_region(world, x, y)
        data = {
            "x": x, "y": y, "index": i, "kind": spec.kind, "terrain": spec.terrain,
            "npc_count": spec.npc_count, "populated": False,
        }
        town_id = world.add_entity("town", spec.name, data, path)
        world.relate(town_id, region_id, "located_in")
    return town_id


def people_at(world: World, place_id: int, exclude: int | None = None) -> list[Entity]:
    people = []
    for entity_id in world.sources(place_id, "located_in"):
        entity = world.entity(entity_id)
        if entity.kind == "person" and entity_id != exclude:
            people.append(entity)
    return people


def populate(world: World, town_id: int) -> list[Entity]:
    """Create the town's seeded residents the first time anyone looks."""
    town = world.entity(town_id)
    if not town.data["populated"]:
        with world.transaction():
            for i in range(town.data["npc_count"]):
                spec = npc_spec(world.world_seed, town.seed_path, i)
                data = {
                    "surname": spec.surname, "given": spec.given, "gender": spec.gender,
                    "age": spec.age, "occupation": spec.occupation, "traits": list(spec.traits),
                    "realm": spec.realm, "portrait": dict(spec.portrait),
                }
                person = world.add_entity("person", spec.name, data, npc_path(town.seed_path, i))
                world.relate(person, town_id, "located_in")
            world.update_data(town_id, populated=True)
    return [p for p in people_at(world, town_id) if not p.data.get("is_player")]


def region_of(world: World, town_id: int) -> Entity:
    return world.entity(world.targets(town_id, "located_in")[0])


def town_label(world: World, x: int, y: int, i: int) -> str:
    found = world.entity_by_seed(town_path(x, y, i))
    return found.name if found else town_spec(world.world_seed, x, y, i).name


def region_label(world: World, x: int, y: int) -> str:
    found = world.entity_by_seed(region_path(x, y))
    return found.name if found else region_spec(world.world_seed, x, y).name
```

- [ ] **Step 4: Run tests** → PASS (5 passed)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: lazy materialization of seeded places and people" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 6: Travel and talk systems

**Files:**
- Create: `systems/travel.py`, `systems/talk.py`
- Test: `tests/test_systems.py`

**Interfaces:**
- Consumes: `commit`, `effect`, `Event`, `Witness` (Task 4), materialize helpers (Task 5), `advance` (Task 4)
- Produces:
  - `systems.travel`:
    - `Route(label, dest: tuple[int,int,int], watches)`
    - `routes_from(world, town) -> list[Route]`
    - `travel_events(traveller, origin, route) -> list[Event]`
    - `location_of(world, entity_id) -> Entity`
    - Effect `"travelled"`: moves the actor to `data["to"]` and advances time by `data["watches"]`.
  - `systems.talk`:
    - Constant `TOPICS = ("work", "town")`
    - `conversations_with(world, npc_id, about) -> list[Memory]` (only `met` and `conversed` memories)
    - `greet_events(world, player, npc_id, place) -> list[Event]`: kind `"met"` the first time and `"conversed"` after that, with `data={"times": prior_count}`
    - `ask_events(player, npc_id, place, topic) -> list[Event]`
    - `farewell_events(player, npc_id, place) -> list[Event]`
    - Effects on `met` and `conversed`: advance 1 watch.

- [ ] **Step 1: Write the failing test** — `tests/test_systems.py`
```python
import pytest

from systems.talk import conversations_with, greet_events
from systems.travel import location_of, routes_from, travel_events
from world.db import World
from world.events import commit
from world.gen.materialize import ensure_town, populate


@pytest.fixture
def setup(tmp_path):
    world = World.create(tmp_path / "t.world", 42)
    town = ensure_town(world, 0, 0, 0)
    player = world.add_entity("person", "Hero", {"is_player": True})
    world.relate(player, town, "located_in")
    yield world, town, player
    world.close()


def test_routes_cover_local_towns_and_four_roads(setup):
    world, town, _ = setup
    routes = routes_from(world, world.entity(town))
    local = world.entity(world.targets(town, "located_in")[0]).data["town_count"] - 1
    assert len(routes) == local + 4
    assert sum("road" in r.label for r in routes) == 4


def test_travel_moves_and_takes_time(setup):
    world, town, player = setup
    north = next(r for r in routes_from(world, world.entity(town)) if "north" in r.label)
    commit(world, travel_events(player, town, north))
    here = location_of(world, player)
    assert (here.data["x"], here.data["y"], here.data["index"]) == north.dest
    assert world.time == north.watches


def test_greeting_is_remembered(setup):
    world, town, player = setup
    npc = populate(world, town)[0].id
    [first] = greet_events(world, player, npc, town)
    assert first.kind == "met"
    commit(world, [first])
    [second] = greet_events(world, player, npc, town)
    assert second.kind == "conversed" and second.data["times"] == 1
    commit(world, [second])
    assert len(conversations_with(world, npc, player)) == 2
    assert world.time == 2
```

- [ ] **Step 2: Run to verify fails** → FAIL

- [ ] **Step 3: Implement**

`systems/travel.py`:
```python
"""Moving between towns: within a region by foot, between regions by road."""

from dataclasses import dataclass

from systems.time import advance
from world.db import Entity, World
from world.events import Event, effect
from world.gen.materialize import ensure_town, region_label, region_of, town_label

DIRECTIONS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
LOCAL_WATCHES = 4   # one day
ROAD_WATCHES = 12   # three days


@dataclass(frozen=True)
class Route:
    label: str
    dest: tuple[int, int, int]
    watches: int


def routes_from(world: World, town: Entity) -> list[Route]:
    x, y, i = town.data["x"], town.data["y"], town.data["index"]
    routes = []
    for j in range(region_of(world, town.id).data["town_count"]):
        if j != i:
            routes.append(Route(f"Walk to {town_label(world, x, y, j)} (1 day)", (x, y, j), LOCAL_WATCHES))
    for name, (dx, dy) in DIRECTIONS.items():
        nx, ny = x + dx, y + dy
        label = f"Take the {name} road to {town_label(world, nx, ny, 0)}, {region_label(world, nx, ny)} (3 days)"
        routes.append(Route(label, (nx, ny, 0), ROAD_WATCHES))
    return routes


def travel_events(traveller: int, origin: int, route: Route) -> list[Event]:
    return [Event("travelled", (traveller,), origin, {"to": list(route.dest), "watches": route.watches})]


def location_of(world: World, entity_id: int) -> Entity:
    return world.entity(world.targets(entity_id, "located_in")[0])


@effect("travelled")
def _arrive(world: World, event: Event) -> None:
    x, y, i = event.data["to"]
    dest = ensure_town(world, x, y, i)
    traveller = event.actors[0]
    world.unrelate(traveller, "located_in")
    world.relate(traveller, dest, "located_in")
    advance(world, event.data["watches"])
```
`systems/talk.py`:
```python
"""Conversation. Phase 1: meeting, remembering, small talk."""

from systems.time import advance
from world.db import Memory, World
from world.events import Event, Witness, effect

TOPICS = ("work", "town")


def conversations_with(world: World, npc_id: int, about: int) -> list[Memory]:
    return [m for m in world.memories(npc_id, about=about) if m.event.kind in ("met", "conversed")]


def greet_events(world: World, player: int, npc_id: int, place: int) -> list[Event]:
    past = conversations_with(world, npc_id, player)
    kind, feeling = ("conversed", "familiar") if past else ("met", "curious")
    return [Event(kind, (player, npc_id), place, {"times": len(past)}, witnesses=(Witness(npc_id, feeling, 0.3),))]


def ask_events(player: int, npc_id: int, place: int, topic: str) -> list[Event]:
    return [Event("asked", (player, npc_id), place, {"topic": topic}, witnesses=(Witness(npc_id, "engaged", 0.1),))]


def farewell_events(player: int, npc_id: int, place: int) -> list[Event]:
    return [Event("parted", (player, npc_id), place)]


@effect("met")
@effect("conversed")
def _talking_takes_a_watch(world: World, event: Event) -> None:
    advance(world, 1)
```

- [ ] **Step 4: Run tests** → PASS (3 passed)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: travel and talk systems" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 7: Briefs and narration (protocol, proposals, procedural grammar)

The engine pre-digests everything into a `Brief` (spec §6.0), so any narrator only has to phrase given facts. This applies equally to the procedural grammar here and to Haiku in phase 6. Narrators never touch the database.

**Files:**
- Create: `narrate/base.py`, `narrate/brief.py`, `narrate/proposals.py`, `narrate/procedural.py`, `narrate/grammar/core.toml`
- Test: `tests/test_brief.py`, `tests/test_narrate.py`

**Interfaces:**
- Consumes: `World`, `Event`, `rng_for`, time helpers, `region_of`, `people_at`, `conversations_with`, `town_path`
- Produces:
  - In `narrate/base.py`:
    - `Line = tuple[str, str]` (text, palette key)
    - `Narrator` protocol (runtime_checkable) with `narrate(brief) -> list[Line]`
  - In `narrate/brief.py`:
    - `PlaceBrief(name, kind, region, terrain, season, watch)`
    - `PersonBrief(name, role, traits: tuple[str, ...], realm, toward_player)`
    - `Brief(kind, when, place, player, other, details: dict[str, str], facts: tuple[str, ...], seed: int, salt: str)` with `.to_prompt() -> str`
    - `event_brief(world, event_id, event) -> Brief`, `scene_brief(world, place_id, player_id, salt) -> Brief`
    - `MAX_FACTS = 6`, `MAX_PROMPT = 1200`
  - In `narrate/proposals.py`: `Proposal(kind, payload, source="claude")`, `Verdict(accepted, reason="")`, the `Validator` protocol, and `RejectAll`
  - In `narrate/procedural.py`: `Grammar.load(directory=None)`, `Grammar.expand(key, rng, context) -> str`, `context_of(brief) -> dict[str, str]`, and `ProceduralNarrator(grammar=None)`
  - Scene briefs have `kind == "scene"`. The procedural grammar key is `scene.<terrain>`.

- [ ] **Step 1: Write the failing brief test** — `tests/test_brief.py`
```python
import pytest

from narrate.brief import MAX_FACTS, MAX_PROMPT, event_brief, scene_brief
from systems.talk import greet_events
from world.db import World
from world.events import Event, commit
from world.gen.materialize import ensure_town, populate


@pytest.fixture
def setup(tmp_path):
    world = World.create(tmp_path / "t.world", 42)
    town = ensure_town(world, 0, 0, 0)
    player = world.add_entity("person", "Hero", {"is_player": True, "realm": "mortal"})
    world.relate(player, town, "located_in")
    npc = populate(world, town)[0]
    yield world, town, player, npc
    world.close()


def greet(world, player, npc, town):
    events = greet_events(world, player, npc.id, town)
    [eid] = commit(world, events)
    return event_brief(world, eid, events[0])


def test_first_meeting_brief(setup):
    world, town, player, npc = setup
    brief = greet(world, player, npc, town)
    assert brief.kind == "met"
    assert brief.other.name == npc.name and brief.other.role == npc.data["occupation"]
    assert brief.other.toward_player == "stranger"
    assert brief.place.name == world.entity(town).name
    assert brief.player.name == "Hero"


def test_repeat_meeting_brief_carries_history(setup):
    world, town, player, npc = setup
    greet(world, player, npc, town)
    brief = greet(world, player, npc, town)
    assert brief.kind == "conversed"
    assert brief.other.toward_player == "acquaintance"
    assert brief.details["times_ordinal"] == "second"
    assert brief.details["first_met_season"] == "the spring of year 1"
    assert f"You first met {npc.name} in the spring of year 1." in brief.facts
    assert brief.facts[0].startswith("You first met")  # most salient first


def test_prompt_is_small_labelled_and_id_free(setup):
    world, town, player, npc = setup
    for _ in range(12):
        brief = greet(world, player, npc, town)
    prompt = brief.to_prompt()
    assert len(prompt) <= MAX_PROMPT and len(brief.facts) <= MAX_FACTS
    for label in ("EVENT:", "WHEN:", "WHERE:", "YOU:", "THEM:", "FACTS:"):
        assert label in prompt
    assert "{" not in prompt and "seed" not in prompt.lower() and "salt" not in prompt.lower()
    assert brief.other.toward_player == "familiar face"


def test_travel_and_scene_briefs(setup):
    world, town, player, _ = setup
    event = Event("travelled", (player,), town, {"to": [0, 0, 0], "watches": 12})
    brief = event_brief(world, 99, event)
    assert brief.details["dest"] == world.entity(town).name and brief.details["days"] == "three days"
    assert brief.other is None and "THEM:" not in brief.to_prompt()
    scene = scene_brief(world, town, player, "look")
    assert scene.kind == "scene" and scene.place.terrain == world.entity(town).data["terrain"]
    assert any(fact.startswith("Here:") for fact in scene.facts)
```

- [ ] **Step 2: Write the failing narrator test** — `tests/test_narrate.py`
```python
import random

from narrate.base import Narrator
from narrate.brief import Brief, PersonBrief, PlaceBrief, event_brief, scene_brief
from narrate.procedural import Grammar, ProceduralNarrator
from narrate.proposals import Proposal, RejectAll
from world.db import World
from world.events import Event
from world.gen.materialize import ensure_town, populate

PLACE = PlaceBrief("Jade Town", "town", "the Misty Peaks", "mountains", "spring", "dusk")
YOU = PersonBrief("Hero", "you", (), "mortal", "self")
LI = PersonBrief("Li Wei", "innkeeper", ("proud", "greedy"), "mortal", "acquaintance")


def brief(kind, other=LI, **details):
    return Brief(kind, "Year 1, Spring day 3, dusk", PLACE, YOU, other, details, (), 42, f"t:{kind}")


def test_is_a_narrator():
    assert isinstance(ProceduralNarrator(), Narrator)


def test_grammar_expands_symbols_and_keeps_unknown_fields():
    grammar = Grammar({"k": {"lines": ["#a# {name} {missing}"]}, "symbols": {"a": ["#b#"], "b": ["hi"]}})
    assert grammar.expand("k", random.Random(1), {"name": "Mo"}) == "hi Mo {missing}"


def test_deterministic_per_salt():
    narrator = ProceduralNarrator()
    b = brief("met")
    assert narrator.narrate(b) == narrator.narrate(b)
    assert "Li Wei" in narrator.narrate(b)[0][0]


def test_every_kind_renders_fully_from_a_brief_alone():
    narrator = ProceduralNarrator()
    cases = [
        brief("began", None),
        brief("met"),
        brief("conversed", times_ordinal="second", first_met_season="the spring of year 1"),
        brief("asked", topic="work"),
        brief("asked", topic="town"),
        brief("parted"),
        brief("travelled", None, dest="Jade Town", days="three days"),
        brief("scene", None),
    ]
    for b in cases:
        [(text, _)] = narrator.narrate(b)
        assert "#" not in text and "{" not in text, (b.kind, text)


def test_unknown_kind_falls_back():
    assert ProceduralNarrator().narrate(brief("mystery")) == [("[mystery]", "dim")]


def test_real_world_scene_and_opening(tmp_path):
    world = World.create(tmp_path / "t.world", 42)
    town = ensure_town(world, 0, 0, 0)
    player = world.add_entity("person", "Hero", {"is_player": True})
    world.relate(player, town, "located_in")
    populate(world, town)
    [(text, _)] = ProceduralNarrator().narrate(scene_brief(world, town, player, "look"))
    assert world.entity(town).name in text
    [(text, _)] = ProceduralNarrator().narrate(event_brief(world, 1, Event("began", (player,), town)))
    assert "Hero" in text
    world.close()


def test_reject_all():
    verdict = RejectAll().validate(None, Proposal("npc", {}))
    assert not verdict.accepted and verdict.reason
```

- [ ] **Step 3: Run to verify both fail** — `.venv/Scripts/python.exe -m pytest tests/test_brief.py tests/test_narrate.py -q` → FAIL (ModuleNotFoundError)

- [ ] **Step 4: Implement**

`narrate/base.py`:
```python
"""The seam between the engine and whoever writes the prose.

A narrator gets a finished Brief and returns lines. It never reads the world:
everything it may say is already in the brief.
"""

from typing import Protocol, runtime_checkable

Line = tuple[str, str]  # (text, palette key)


@runtime_checkable
class Narrator(Protocol):
    def narrate(self, brief) -> list[Line]: ...
```
`narrate/brief.py`:
```python
"""Briefs: the engine's pre-digested account of one moment.

All recall and relevance judgement happens here, in tested code. A narrator,
whether a grammar or a small model like Haiku, only has to phrase these facts.
Rules: no entity ids, only what the player knows, ranked facts, short.
"""

from dataclasses import dataclass, field

from systems.talk import conversations_with
from systems.time import WATCH_NAMES, format_date, format_season_year, season_of
from world.db import Entity, World
from world.gen.materialize import people_at, region_of
from world.gen.town import town_path

MAX_FACTS = 6
MAX_PROMPT = 1200
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")
NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


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
    role = "you" if data.get("is_player") else data.get("occupation", "stranger")
    return PersonBrief(entity.name, role, tuple(data.get("traits", ())), data.get("realm", "mortal"), toward)


def _relationship(world: World, npc: Entity, player: Entity, include_current: bool) -> tuple[list[str], dict[str, str], int]:
    """Ranked facts about the player and this person, details, and the prior-conversation count.

    Salience order (spec §6.0): first meeting, then encounter count, then traits.
    Later phases insert indelible memories, grudges and obligations above these.
    `include_current` is True when the event being narrated is itself a conversation
    that has already been committed, so it must not count as "before".
    """
    history = conversations_with(world, npc.id, player.id)
    prior = max(0, len(history) - 1) if include_current else len(history)
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
    return facts, details, prior


def event_brief(world: World, event_id: int, event) -> Brief:
    player = world.entity(event.actors[0])
    other = world.entity(event.actors[1]) if len(event.actors) > 1 else None
    facts: list[str] = []
    details: dict[str, str] = {}
    other_brief = None
    if other is not None:
        facts, details, prior = _relationship(world, other, player, event.kind in ("met", "conversed"))
        other_brief = _person(other, _toward(prior))
        details["times_ordinal"] = ordinal(prior + 1)
    if "topic" in event.data:
        details["topic"] = str(event.data["topic"])
    place_id = event.place
    if event.kind == "travelled":
        dest = world.entity_by_seed(town_path(*event.data["to"]))
        details["dest"] = dest.name if dest else "a town"
        details["days"] = days_phrase(event.data["watches"])
        facts.insert(0, f"You travelled {details['days']} to reach {details['dest']}.")
        if dest is not None:
            place_id = dest.id
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
    )


def scene_brief(world: World, place_id: int, player_id: int, salt: str) -> Brief:
    player = world.entity(player_id)
    present = [p for p in people_at(world, place_id, exclude=player_id)]
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
`narrate/proposals.py`:
```python
"""What an AI may *suggest*. Nothing here writes state; the engine validates first.

Phase 1 only defines the shapes so phase 6 plugs in without reshaping the engine.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol

ProposalKind = Literal["prose", "dialogue", "npc", "rumor", "action"]


@dataclass(frozen=True)
class Proposal:
    kind: ProposalKind
    payload: dict = field(default_factory=dict)
    source: str = "claude"


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: str = ""


class Validator(Protocol):
    def validate(self, world, proposal: Proposal) -> Verdict: ...


class RejectAll:
    """The phase 1 validator: nothing from outside the engine is trusted yet."""

    def validate(self, world, proposal: Proposal) -> Verdict:
        return Verdict(False, f"No validator for {proposal.kind} proposals yet")
```
`narrate/procedural.py`:
```python
"""Prose from grammar files, filled only from a Brief. Deterministic per brief.salt."""

import random
import re
import tomllib
from pathlib import Path

from narrate.base import Line
from narrate.brief import Brief
from paths import bundled
from world.seed import rng_for

SYMBOL = re.compile(r"#(\w+)#")


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
        return text.format_map(_KeepMissing(context))


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
    def __init__(self, grammar: Grammar | None = None) -> None:
        self.grammar = grammar or Grammar.load()

    def narrate(self, brief: Brief) -> list[Line]:
        if brief.kind == "scene":
            key = f"scene.{brief.place.terrain}"
        elif brief.kind == "asked":
            key = f"asked.{brief.details.get('topic', '')}"
        else:
            key = brief.kind
        if key not in self.grammar.tables:
            return [(f"[{brief.kind}]", "dim")]
        rng = rng_for(brief.seed, brief.salt)
        colour = self.grammar.tables[key].get("colour", "default")
        return [(self.grammar.expand(key, rng, context_of(brief)), colour)]
```
`narrate/grammar/core.toml`:
```toml
[symbols]
greeting = ["Well met.", "Traveller.", "Hm.", "Greetings, young hero.", "Another wanderer, is it?", "Mind your step."]
look = ["looks you over", "eyes you warily", "offers a shallow bow", "barely glances up", "studies your hands for calluses", "sizes up your stance"]
remember = ["You again.", "I remember your face.", "Back so soon?", "The world is small, it seems.", "Ah, it's you."]
farewell = ["May the heavens favour your path.", "Walk carefully.", "Don't make trouble here.", "Until the rivers meet again."]
road = ["dusty", "rutted", "winding", "rain-slick", "bandit-haunted", "quiet", "pilgrim-worn"]
wind = ["A cold wind", "A warm breeze", "A restless wind", "Still air"]

[began]
colour = "gold"
lines = [
  "Your story begins in {town}, in the {season} of the first year. You carry little but a name: {player}.",
  "{player} arrives in {town} with empty pockets and a head full of legends. The martial world waits.",
]

[met]
colour = "npc"
lines = [
  "{npc_full}, a {trait} {occupation}, #look#. \"#greeting# The name is {npc_full}.\"",
  "A {trait} {occupation} #look#. \"#greeting#\" They give their name as {npc_full}.",
]

[conversed]
colour = "npc"
lines = [
  "{npc} #look#. \"#remember# We first spoke in {first_met_season}, did we not?\"",
  "\"#remember#\" says {npc}. It is the {times_ordinal} time the two of you have spoken.",
]

["asked.work"]
colour = "npc"
lines = [
  "\"Work? I am a {occupation}. It feeds me, mostly,\" says {npc}.",
  "{npc} shrugs. \"A {occupation}'s life. The sect people never pay what they owe.\"",
]

["asked.town"]
colour = "npc"
lines = [
  "\"{town}? A {kind} of {region}. Quiet, until it isn't,\" says {npc}.",
  "{npc} lowers their voice. \"{town} looks peaceful. Every {kind} in {region} does, from the outside.\"",
]

[parted]
colour = "npc"
lines = [
  "\"#farewell#\" {npc} turns back to their business.",
  "{npc} nods. \"#farewell#\"",
]

[travelled]
colour = "default"
lines = [
  "You take the #road# road for {days}. At {watch} you reach {dest}.",
  "After {days} on the #road# road, {dest} rises ahead of you at {watch}.",
]

["scene.plains"]
lines = [
  "{town} sits among open fields. #wind# moves through the {season} grain at {watch}.",
  "Flat land runs to the horizon around {town}. Farmers bend in the fields this {season} {watch}.",
]

["scene.mountains"]
lines = [
  "{town} clings to a mountainside. Mist pours between the peaks this {season} {watch}.",
  "Stone steps wind up through {town}. Somewhere above, a sect bell rings at {watch}.",
]

["scene.river"]
lines = [
  "Boats crowd the docks of {town}. The river runs broad and brown this {season} {watch}.",
  "{town} straddles the river. Ferrymen shout prices across the water at {watch}.",
]

["scene.forest"]
lines = [
  "{town} huddles beneath old trees. #wind# stirs the {season} canopy at {watch}.",
  "Woodcutters stack timber at the edge of {town}. The forest is loud with birds at {watch}.",
]

["scene.marsh"]
lines = [
  "{town} stands on stilts above the reeds. Frogs drone through the {season} {watch}.",
  "Plank walkways link the houses of {town}. The marsh smells of rot and lotus at {watch}.",
]

["scene.hills"]
lines = [
  "{town} rolls over green hills. Tea terraces catch the {season} light at {watch}.",
  "Goat paths criss-cross the hills around {town}. #wind# carries woodsmoke at {watch}.",
]
```

- [ ] **Step 5: Run tests** — `.venv/Scripts/python.exe -m pytest tests/test_brief.py tests/test_narrate.py -q` → PASS (11 passed)

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: briefs and procedural narration (phase-6 narrator seam)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 8: Game engine

**Files:**
- Create: `engine/game.py`, `engine/journal.py`
- Test: `tests/test_game.py`

**Interfaces:**
- Consumes: everything from Tasks 3–7. All prose goes through `narrator.narrate(brief)`; the engine builds the brief with `event_brief` or `scene_brief`.
- Produces:
  - `Action(verb: str, target=None)` (frozen)
  - `Choice(label: str, action: Action)` (frozen)
  - `Turn(lines: list[Line], choices: list[Choice], art: dict, status: str)`
  - `Game`:
    - `new(path, player_name, world_seed=None, narrator=None)` (classmethod)
    - `load(path, narrator=None)` (classmethod; raises `SaveError`)
    - Properties `world`, `player`, and `place`
    - Methods `start() -> Turn`, `look() -> Turn`, `perform(action) -> Turn`, `close()`
  - Verbs: `look`, `travel` (target is the dest tuple), `talk` (target is the npc id), `ask` (target is the topic), `farewell`, `journal`, `help`, `unknown` (target is the text), `ambiguous` (target is a tuple of Choices).
  - Art dicts:
    - `{"type": "scene", "terrain": str, "settlement": str, "watch": int}`
    - `{"type": "portrait", "parts": {"hair": n, "face": n, "robe": n}}`
  - `engine.journal.summarize(world, entry) -> str`

- [ ] **Step 1: Write the failing test** — `tests/test_game.py`
```python
import pytest

from engine.game import Action, Game
from world.db import SaveError


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=42)
    yield g
    g.close()


def verbs(turn):
    return [c.action.verb for c in turn.choices]


def test_start_shows_opening_scene_and_choices(game):
    turn = game.start()
    assert any("Hero" in text for text, _ in turn.lines)  # the 'began' narration
    assert {"talk", "travel", "look", "journal"} <= set(verbs(turn))
    assert turn.art["type"] == "scene"
    assert "Hero" in turn.status and "Year 1" in turn.status


def test_talk_focuses_and_farewell_returns(game):
    talk = next(c for c in game.start().choices if c.action.verb == "talk")
    turn = game.perform(talk.action)
    assert turn.art["type"] == "portrait"
    assert set(verbs(turn)) == {"ask", "farewell"}
    turn = game.perform(Action("ask", "work"))
    assert turn.lines
    turn = game.perform(Action("farewell"))
    assert turn.art["type"] == "scene"


def test_talk_to_someone_absent_commits_nothing(game):
    before = game.world.digest()
    turn = game.perform(Action("talk", 99999))
    assert turn.lines[0][1] == "system"
    assert game.world.digest() == before


def test_travel_changes_place_and_time(game):
    start = game.place.id
    road = next(c for c in game.start().choices if c.action.verb == "travel" and "north" in c.label)
    turn = game.perform(road.action)
    assert game.place.id != start
    assert "Year 1, Spring day 4" in turn.status
    assert any(c.action.verb == "talk" for c in turn.choices)  # new town was populated


def test_journal_lists_history(game):
    talk = next(c for c in game.start().choices if c.action.verb == "talk")
    game.perform(talk.action)
    lines = [text for text, _ in game.perform(Action("journal")).lines]
    assert any("set out from" in line for line in lines)
    assert any("Met " in line for line in lines)


def test_unknown_and_ambiguous(game):
    assert game.perform(Action("unknown", "dance")).lines[0][1] == "system"
    options = tuple(game.start().choices[:2])
    turn = game.perform(Action("ambiguous", options))
    assert turn.choices == list(options)


def test_load_missing_raises(tmp_path):
    with pytest.raises(SaveError):
        Game.load(tmp_path / "none.world")
```

- [ ] **Step 2: Run to verify fails** → FAIL

- [ ] **Step 3: Implement**

`engine/journal.py`:
```python
"""One-line summaries of chronicle entries for the player's journal."""

from systems.time import format_date
from world.db import ChronicleEntry, World
from world.gen.town import town_path


def summarize(world: World, entry: ChronicleEntry) -> str:
    names = [world.entity(a).name for a in entry.actors]
    place = world.entity(entry.place).name if entry.place else "the road"
    other = names[1] if len(names) > 1 else "someone"
    match entry.kind:
        case "began":
            text = f"{names[0]} set out from {place}."
        case "met":
            text = f"Met {other} in {place}."
        case "conversed":
            text = f"Spoke again with {other} in {place}."
        case "asked":
            text = f"Asked {other} about {entry.data.get('topic', 'things')}."
        case "parted":
            text = f"Took leave of {other}."
        case "travelled":
            dest = world.entity_by_seed(town_path(*entry.data["to"]))
            text = f"Left {place} for {dest.name if dest else 'parts unknown'}."
        case _:
            text = entry.kind
    return f"{format_date(entry.time)} - {text}"
```
`engine/game.py`:
```python
"""The engine: Actions in, Turns out. The only code that commits events."""

import random
from dataclasses import dataclass

import systems.talk as talk
import systems.travel as travel
from engine.journal import summarize
from narrate.base import Line, Narrator
from narrate.brief import event_brief, scene_brief
from narrate.procedural import ProceduralNarrator
from systems.time import format_date
from world.db import Entity, SaveError, World
from world.events import Event, commit
from world.gen.materialize import ensure_town, people_at, populate, region_of

HELP = [
    ("Type a number, or a command:", "system"),
    ("  look | talk <name> | go <place or direction> | ask <work|town> | bye | journal | help", "system"),
    ("  F2 swap art side | F3 hide art | PgUp/PgDn scroll | F11 fullscreen | Esc menu", "system"),
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


class Game:
    def __init__(self, world: World, narrator: Narrator | None = None) -> None:
        self.world = world
        self.narrator = narrator or ProceduralNarrator()
        self.focus: int | None = None
        self._pending: list[Line] = []

    @classmethod
    def new(cls, path, player_name: str, world_seed: int | None = None, narrator=None) -> "Game":
        seed = world_seed if world_seed is not None else random.SystemRandom().randrange(2**31)
        world = World.create(path, seed)
        town = ensure_town(world, 0, 0, 0)
        with world.transaction():
            player = world.add_entity("person", player_name, {"is_player": True, "age": 18, "realm": "mortal"})
            world.relate(player, town, "located_in")
            world.set_meta("player_id", player)
        populate(world, town)
        game = cls(world, narrator)
        game._pending = game._commit([Event("began", (player,), town)])
        return game

    @classmethod
    def load(cls, path, narrator=None) -> "Game":
        world = World.open(path)
        if world.get_meta("player_id") is None:
            world.close()
            raise SaveError(f"{world.path.name} has no player")
        return cls(world, narrator)

    def close(self) -> None:
        self.world.close()

    @property
    def player(self) -> Entity:
        return self.world.entity(self.world.get_meta("player_id"))

    @property
    def place(self) -> Entity:
        return travel.location_of(self.world, self.player.id)

    # --- turns ----------------------------------------------------------------
    def start(self) -> Turn:
        return self.look()

    def look(self) -> Turn:
        return self._do_look(None)

    def perform(self, action: Action) -> Turn:
        handler = getattr(self, f"_do_{action.verb}", None)
        if handler is None:
            return self._turn([(f"You can't do that ({action.verb}).", "system")])
        return handler(action.target)

    def _do_look(self, _target) -> Turn:
        self.focus = None
        return self._turn(self._describe("look") + self._presence())

    def _do_travel(self, dest) -> Turn:
        routes = {r.dest: r for r in travel.routes_from(self.world, self.place)}
        route = routes.get(tuple(dest) if dest is not None else None)
        if route is None:
            return self._turn([("You can't get there from here.", "system")])
        self.focus = None
        lines = self._commit(travel.travel_events(self.player.id, self.place.id, route))
        populate(self.world, self.place.id)
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
        return self._turn(self._commit(talk.ask_events(self.player.id, self.focus, self.place.id, topic)))

    def _do_farewell(self, _target) -> Turn:
        if self.focus is None:
            return self._turn([("You aren't talking to anyone.", "system")])
        lines = self._commit(talk.farewell_events(self.player.id, self.focus, self.place.id))
        self.focus = None
        return self._turn(lines)

    def _do_journal(self, _target) -> Turn:
        entries = list(reversed(self.world.chronicle_about(self.player.id, limit=15)))
        lines = [(f"Chronicle of {self.player.name}:", "gold")]
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

    # --- helpers --------------------------------------------------------------
    def _commit(self, events: list[Event]) -> list[Line]:
        ids = commit(self.world, events)
        lines: list[Line] = []
        for event_id, event in zip(ids, events):
            lines += self.narrator.narrate(event_brief(self.world, event_id, event))
        return lines

    def _describe(self, salt: str) -> list[Line]:
        return self.narrator.narrate(scene_brief(self.world, self.place.id, self.player.id, salt))

    def _presence(self) -> list[Line]:
        people = people_at(self.world, self.place.id, exclude=self.player.id)
        if not people:
            return [("No one of note is here.", "dim")]
        described = []
        for person in people:
            known = " (knows you)" if talk.conversations_with(self.world, person.id, self.player.id) else ""
            described.append(f"{person.name} the {person.data.get('occupation', 'stranger')}{known}")
        return [("Here: " + ", ".join(described) + ".", "dim")]

    def _choices(self) -> list[Choice]:
        if self.focus is not None:
            return [
                Choice("Ask about their work", Action("ask", "work")),
                Choice(f"Ask about {self.place.name}", Action("ask", "town")),
                Choice("Say farewell", Action("farewell")),
            ]
        choices = [
            Choice(f"Talk to {p.name} ({p.data.get('occupation', 'stranger')})", Action("talk", p.id))
            for p in people_at(self.world, self.place.id, exclude=self.player.id)
        ]
        choices += [Choice(r.label, Action("travel", r.dest)) for r in travel.routes_from(self.world, self.place)]
        choices += [Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]
        return choices

    def _art(self) -> dict:
        if self.focus is not None:
            return {"type": "portrait", "parts": self.world.entity(self.focus).data["portrait"]}
        place = self.place
        return {"type": "scene", "terrain": place.data["terrain"], "settlement": place.data["kind"], "watch": self.world.time % 4}

    def _status(self) -> str:
        player, place = self.player, self.place
        region = region_of(self.world, place.id)
        return f"{player.name} | {player.data.get('realm', 'mortal')} | {format_date(self.world.time)} | {place.name}, {region.name}"

    def _turn(self, lines: list[Line]) -> Turn:
        lines, self._pending = self._pending + lines, []
        return Turn(lines, self._choices(), self._art(), self._status())
```

- [ ] **Step 4: Run tests** → PASS (7 passed). Note: day 4 after a 3-day road holds because the start is day 1, morning; 12 watches later is day 4, morning.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: game engine with look/talk/travel/journal" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 9: Command parser

**Files:**
- Create: `engine/commands.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Consumes: `Action`, `Choice` (Task 8)
- Produces: `parse(text: str, choices: list[Choice]) -> Action | None`
  - Returns `None` for empty input.
  - Returns `Action("ambiguous", tuple[Choice, ...])` when more than one choice matches.
  - Returns `Action("unknown", text)` when nothing matches.

- [ ] **Step 1: Write the failing test** — `tests/test_commands.py`
```python
from engine.commands import parse
from engine.game import Action, Choice

CHOICES = [
    Choice("Talk to Li Wei (innkeeper)", Action("talk", 1)),
    Choice("Talk to Li Mei (herbalist)", Action("talk", 2)),
    Choice("Talk to Lin Ho (monk)", Action("talk", 3)),
    Choice("Take the north road to Jade Town, the Misty Peaks (3 days)", Action("travel", (0, -1, 0))),
    Choice("Look around", Action("look")),
]


def test_empty_is_nothing():
    assert parse("", CHOICES) is None
    assert parse("   \t ", CHOICES) is None


def test_numbers():
    assert parse("4", CHOICES) == Action("travel", (0, -1, 0))
    assert parse("999", CHOICES).verb == "unknown"
    assert parse("0", CHOICES).verb == "unknown"


def test_global_words():
    assert parse("LOOK", CHOICES) == Action("look")
    assert parse("journal", CHOICES) == Action("journal")
    assert parse("bye", CHOICES) == Action("farewell")


def test_exact_word_beats_prefix():
    assert parse("talk to li wei", CHOICES) == Action("talk", 1)
    assert parse("talk monk", CHOICES) == Action("talk", 3)


def test_ambiguous_names():
    action = parse("talk li", CHOICES)
    assert action.verb == "ambiguous"
    assert {c.action.target for c in action.target} == {1, 2}


def test_travel_by_direction_and_prefix():
    assert parse("go north", CHOICES) == Action("travel", (0, -1, 0))
    assert parse("go jad", CHOICES) == Action("travel", (0, -1, 0))


def test_junk_never_crashes():
    for junk in ["говорить 🐉", "x" * 5000, "talk", "go ", "ask about", "!!!", "\x00\x01"]:
        action = parse(junk, CHOICES)
        assert action is None or action.verb in {"unknown", "ambiguous", "talk", "travel"}
```

- [ ] **Step 2: Run to verify fails** → FAIL

- [ ] **Step 3: Implement** — `engine/commands.py`
```python
"""Typed commands to Actions, matched against what the player can do right now.

The parser knows only global words and the current choices, so every command
the engine can take also has a number to press.
"""

import re

from engine.game import Action, Choice

GLOBAL = {
    "look": "look", "l": "look", "journal": "journal", "j": "journal", "chronicle": "journal",
    "help": "help", "?": "help", "bye": "farewell", "farewell": "farewell", "leave": "farewell",
}
PREFIX_VERBS = {"talk": "talk", "speak": "talk", "go": "travel", "travel": "travel", "walk": "travel", "ask": "ask"}
FILLER = {"to", "about", "with", "the"}
WORD = re.compile(r"[a-z0-9']+")


def _words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def parse(text: str, choices: list[Choice]) -> Action | None:
    cleaned = " ".join(text.split())[:200]
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered.isdigit():
        n = int(lowered)
        return choices[n - 1].action if 1 <= n <= len(choices) else Action("unknown", cleaned)
    if lowered in GLOBAL:
        return Action(GLOBAL[lowered])
    head, _, rest = lowered.partition(" ")
    verb = PREFIX_VERBS.get(head)
    wanted = [w for w in _words(rest) if w not in FILLER]
    if verb is None or not wanted:
        return Action("unknown", cleaned)
    pool = [c for c in choices if c.action.verb == verb]
    exact = [c for c in pool if all(w in _words(c.label) for w in wanted)]
    prefix = [c for c in pool if all(any(lw.startswith(w) for lw in _words(c.label)) for w in wanted)]
    for matches in (exact, prefix):
        if len(matches) == 1:
            return matches[0].action
        if len(matches) > 1:
            return Action("ambiguous", tuple(matches))
    return Action("unknown", cleaned)
```
Note: `talk li` matches Li Wei and Li Mei exactly. Lin Ho is left out because an exact match exists, so the exact tier is ambiguous between two, which is correct. `go jad` has no exact match, so the prefix tier finds one.

- [ ] **Step 4: Run tests** → PASS (7 passed)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: command parser" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 10: ASCII art loader, composer, and assets

**Files:**
- Create: `render/art.py`, `assets/art/*.art` (listed below)
- Test: `tests/test_art.py`

**Interfaces:**
- Consumes: `bundled` (Task 1), `TERRAINS`, `PORTRAIT_PARTS`, `town.KINDS`
- Produces:
  - `ArtCell = tuple[str, str] | None` (char, palette key); `Art = list[list[ArtCell]]`
  - Loading: `parse_art(text) -> Art`, `load_art(name) -> Art` (missing gives `[]`)
  - Helpers: `art_width(art) -> int`, `blank(w, h) -> Art`, `stamp(canvas, art, top, left)`
  - Composition: `compose_scene(terrain, settlement, watch, w, h) -> Art`, `compose_portrait(parts, w, h) -> Art`, `render_request(request: dict, w, h) -> Art` (always exactly `h` rows of `w` cells)
- Art format:
  - Lines starting with `;` are comments.
  - `{colour}` switches the colour, using a palette key; `{/}` resets to `default`. The colour persists across lines.
  - A space is transparent.

- [ ] **Step 1: Write the failing test** — `tests/test_art.py`
```python
from render.art import art_width, blank, compose_portrait, compose_scene, load_art, parse_art, render_request, stamp
from world.gen.npc import PORTRAIT_PARTS
from world.gen.region import TERRAINS
from world.gen.town import KINDS


def test_markup_and_transparency():
    art = parse_art("; comment\n{red}ab {/}c\nd")
    assert art[0] == [("a", "red"), ("b", "red"), None, ("c", "default")]
    assert art[1] == [("d", "default")]


def test_colour_persists_across_lines():
    assert parse_art("{jade}a\nb")[1] == [("b", "jade")]


def test_stamp_clips():
    canvas = blank(3, 2)
    stamp(canvas, parse_art("abcd\nefgh\nijkl"), -1, 1)
    assert [len(r) for r in canvas] == [3, 3]
    assert canvas[0][1] == ("e", "default") and canvas[0][2] == ("f", "default")
    assert canvas[1][2] == ("j", "default")


def test_render_request_is_exact_size_even_when_tiny():
    for w, h in [(40, 18), (5, 3), (1, 1)]:
        for req in [
            {"type": "scene", "terrain": "river", "settlement": "town", "watch": 2},
            {"type": "portrait", "parts": {"hair": 0, "face": 0, "robe": 0}},
            {"type": "nonsense"},
        ]:
            art = render_request(req, w, h)
            assert len(art) == h and all(len(r) == w for r in art)


def test_missing_art_is_empty():
    assert load_art("does_not_exist") == []


def test_every_asset_exists_and_fits():
    names = [f"sky_{w}" for w in range(4)] + [f"terrain_{t}" for t in TERRAINS]
    names += [f"settlement_{k}" for k in set(KINDS)] + ["title"]
    names += [f"{part}_{n}" for part, count in PORTRAIT_PARTS.items() for n in range(count)]
    for name in names:
        art = load_art(name)
        assert art, name
        assert art_width(art) <= 40 and len(art) <= 18, name
    assert compose_scene("mountains", "city", 3, 40, 18)
    assert compose_portrait({"hair": 1, "face": 2, "robe": 3}, 40, 18)
```

- [ ] **Step 2: Run to verify fails** → FAIL

- [ ] **Step 3: Implement** — `render/art.py`
```python
"""ASCII art: parse `.art` files and compose layered scenes and portraits.

No pygame here. Cells carry palette keys; the layout resolves them to colours.
"""

import re
from functools import cache

from paths import bundled

ArtCell = tuple[str, str] | None
Art = list[list[ArtCell]]
MARKUP = re.compile(r"\{(/|[a-z_]+)\}")


def parse_art(text: str) -> Art:
    rows: Art = []
    colour = "default"
    for raw in text.splitlines():
        if raw.startswith(";"):
            continue
        row: list[ArtCell] = []
        pos = 0
        for match in MARKUP.finditer(raw):
            row += [None if ch == " " else (ch, colour) for ch in raw[pos:match.start()]]
            colour = "default" if match.group(1) == "/" else match.group(1)
            pos = match.end()
        row += [None if ch == " " else (ch, colour) for ch in raw[pos:]]
        rows.append(row)
    return rows


@cache
def _load(name: str) -> tuple[tuple[ArtCell, ...], ...]:
    path = bundled("assets", "art", f"{name}.art")
    if not path.is_file():
        return ()
    return tuple(tuple(row) for row in parse_art(path.read_text(encoding="utf-8")))


def load_art(name: str) -> Art:
    return [list(row) for row in _load(name)]


def art_width(art: Art) -> int:
    return max((len(row) for row in art), default=0)


def blank(w: int, h: int) -> Art:
    return [[None] * w for _ in range(h)]


def stamp(canvas: Art, art: Art, top: int, left: int) -> None:
    """Draw `art` onto `canvas`; transparent cells and anything off-canvas are skipped."""
    height = len(canvas)
    width = len(canvas[0]) if canvas else 0
    for r, row in enumerate(art):
        y = top + r
        if not 0 <= y < height:
            continue
        for c, cell in enumerate(row):
            x = left + c
            if cell is not None and 0 <= x < width:
                canvas[y][x] = cell


def compose_scene(terrain: str, settlement: str, watch: int, w: int, h: int) -> Art:
    canvas = blank(w, h)
    sky = load_art(f"sky_{watch}")
    stamp(canvas, sky, 0, (w - art_width(sky)) // 2)
    for layer in (load_art(f"terrain_{terrain}"), load_art(f"settlement_{settlement}")):
        stamp(canvas, layer, h - len(layer), (w - art_width(layer)) // 2)
    return canvas


def compose_portrait(parts: dict, w: int, h: int) -> Art:
    pieces = [load_art(f"{part}_{parts.get(part, 0)}") for part in ("hair", "face", "robe")]
    canvas = blank(w, h)
    top = max(0, (h - sum(len(p) for p in pieces)) // 2)
    for piece in pieces:
        stamp(canvas, piece, top, (w - art_width(piece)) // 2)
        top += len(piece)
    return canvas


def render_request(request: dict, w: int, h: int) -> Art:
    kind = request.get("type")
    if kind == "scene":
        return compose_scene(request["terrain"], request["settlement"], request["watch"], w, h)
    if kind == "portrait":
        return compose_portrait(request["parts"], w, h)
    return blank(w, h)
```

- [ ] **Step 4: Create the art assets** (in `assets/art/`, UTF-8, keep every line ≤ 40 chars wide after removing markup)

`title.art`:
```
{gold} ___  ___ ___ ___
|   \| __| __| _ \
| |) | _|| _||  _/
|___/|___|___|_|
{red} __  __ _   _ ___ ___ __  __
|  \/  | | | | _ \_ _|  \/  |
| |\/| | |_| |   /| || |\/| |
|_|  |_|\___/|_|_\___|_|  |_|
{dim}  the martial world never forgets
```
`sky_0.art` (morning):
```
{gold}             \  |  /
            -- .-"-. --
              (     )
{sky}   ~~~~       '-'        ~~~~
        ~~~~        ~~~~~
```
`sky_1.art` (midday):
```
{white}     .--.               .--.
  .-(    ).         .-(    ).
 (___.__)__)       (___.__)__)
{gold}                \ | /
               -- O --
```
`sky_2.art` (dusk):
```
{red} ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
{gold}       ~~~~~    .---.    ~~~~~
{red}   ~~~~~~~~    (     )    ~~~~~~~~
{purple} ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
```
`sky_3.art` (night):
```
{white}  *        .       *      .    *
      .   *      _..      .
  .          *  (  '    *     .
      *          '._)      .
   .      .    *      *       *
```
`terrain_plains.art`:
```
{green}   ,     ,,      ,    ,,     ,    ,
 ,,  ,     ,  ,,    ,     ,,   ,   ,
{gold}_,-._,-._,-._,-._,-._,-._,-._,-._,-.
{green}   "  ''  "   ''   "  ''   "   ''  "
```
`terrain_mountains.art`:
```
{grey}              /\
        /\   /  \      /\
       /  \ /    \    /  \  /\
      /    \/{white}^^{grey}  \  /    \/  \
     /{white}^^{grey}  /      \/      \    \
    /    /            {white}^^{grey}  \    \
{green}  ^^^^ ^^^^^^   ^^^^^^^  ^^^^^^^^^
 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
```
`terrain_river.art`:
```
{green}  ,,  ,     ,,       ,,    ,   ,,
{brown}_____________________________________
{blue} ~~~  ~~~~   ~~~   ~~~~   ~~~   ~~~
   ~~~~   ~~~   ~~~~   ~~~~  ~~~~
{brown}_____________________________________
```
`terrain_forest.art`:
```
{green}    /\      /\    /\      /\    /\
   /  \    /  \  /  \    /  \  /  \
  /    \  /    \/    \  /    \/    \
 /______\/______\_____\/______\_____\
{brown}    ||      ||     ||      ||     ||
```
`terrain_marsh.art`:
```
{green}   |  ,|,   |    ,|,   |   ,|,  |
  ,|,  |   ,|,    |   ,|,   |  ,|,
{jade} ~~~~ .  ~~~~~  .  ~~~~  . ~~~~~ .
  . ~~~~~  .  ~~~~~  .  ~~~~  . ~~~
```
`terrain_hills.art`:
```
{green}        _.--.__           _.--._
    _.-'       '-.    _.-'      '-._
 .-'              '--'              '-
  ,,    ,    ,,     ,     ,,    ,   ,,
```
`settlement_village.art`:
```
{brown}      /\          /\
     /  \        /  \
    /____\      /____\
    | [] |      | [] |
____|____|______|____|____
```
`settlement_town.art`:
```
{red}            _/\_
          _/____\_
          \ |  | /
   _/\_   _/____\_   _/\_
  /____\  | {gold}[]{red} |   /____\
{brown}  |[]|  |__|____|__| |[]|
__|__|__|__________|_|__|__
```
`settlement_city.art`:
```
{grey}   _/\_      _/\___/\_      _/\_
  /____\    /_________\    /____\
  |_[]_|____|  _____  |____|_[]_|
  |  |  |  |  |     |  |  |  |  |
__|__|__|__|__|     |__|__|__|__|__
```
`hair_0.art` (topknot): 
```
{brown}      _
    _( )_
   /     \
```
`hair_1.art` (long hair):
```
{grey}    .-----.
   /       \
  |         |
```
`hair_2.art` (bamboo hat):
```
{gold}     ___
  __/   \__
 /_________\
```
`hair_3.art` (headband):
```
{red}   .-----.
  /=======\~
 |         |
```
`face_0.art`:
```
 |  o   o  |
 |    >    |
 |   ---   |
  \_______/
```
`face_1.art` (stern):
```
 |  -   -  |
 |    |    |
 |   ___   |
  \_______/
```
`face_2.art` (scarred):
```
 |  o  \o  |
 |    L   \|
 |   \_/   |
  \_______/
```
`face_3.art` (bearded):
```
 |  ^   ^  |
 |    >    |
 |  (vvv)  |
  \_\|||/_/
```
`robe_0.art`:
```
{jade}   ___| |___
  /  \   /  \
 /   |\ /|   \
 |   | V |   |
 |___|___|___|
```
`robe_1.art` (swordsman):
```
{blue}   ___| |___   /
  /  \   /  \ /
 /   |\ /|   X
 |   | V |  /|
 |___|___|___|
```
`robe_2.art` (monk):
```
{gold}   ___| |___
  / o o o o \
 /   \   /   \
 |    \ /    |
 |_____V_____|
```
`robe_3.art` (merchant):
```
{purple}   ___| |___
  /  |$ $|  \
 /   |   |  {gold}{){purple}
 |   |___|   |
 |___________|
```
Note: in `robe_3.art`, `{)` is not markup, because the regex needs `[a-z_]+` or `/` inside the braces. So `{gold}{)` renders the two characters `{)` in gold.

- [ ] **Step 5: Run tests** → PASS (6 passed)

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: ascii art loader, composer and first art set" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 11: Layout and title menu (pure grid composition)

**Files:**
- Create: `render/layout.py`, `render/menu.py`
- Test: `tests/test_layout.py`

**Interfaces:**
- Consumes: `Art`, `load_art`, `art_width`, `stamp` (Task 10), `PALETTE` (Task 1), `Line` (Task 7)
- Produces:
  - `Cell = tuple[str, Color] | None`; `Grid = list[list[Cell]]`
  - `View(status, log, art, choices, command, art_side="left", show_art=True, scroll=0)`
  - `compose(view, cols, rows, palette, art_width) -> Grid`
  - `row_text(grid, r) -> str`
  - `compose_title(cols, rows, palette, options, selected, message="", prompt=None) -> Grid`
  - `MIN_LOG_WIDTH = 30`: the art is hidden when the log would be narrower than this.

- [ ] **Step 1: Write the failing test** — `tests/test_layout.py`
```python
from config import PALETTE
from render.art import parse_art
from render.layout import View, compose, row_text
from render.menu import compose_title

ART = parse_art("\n".join(["@" * 10] * 4))


def view(**kw):
    base = dict(status="Hero | mortal", log=[("hello world", "default")], art=ART,
                choices=["Look around", "Read your journal"], command="tal", art_side="left", show_art=True)
    base.update(kw)
    return View(**base)


def body_rows(grid):
    return [row_text(grid, r) for r in range(2, len(grid) - 4)]


def test_art_left():
    grid = compose(view(), 100, 30, PALETTE, 40)
    rows = body_rows(grid)
    assert any("@" in r[:40] for r in rows) and not any("@" in r[40:] for r in rows)
    assert any(r[42:].startswith("hello world") for r in rows)


def test_art_right():
    grid = compose(view(art_side="right"), 100, 30, PALETTE, 40)
    rows = body_rows(grid)
    assert any("@" in r[60:] for r in rows) and not any("@" in r[:60] for r in rows)
    assert any(r[1:].startswith("hello world") for r in rows)


def test_art_hidden():
    grid = compose(view(show_art=False), 100, 30, PALETTE, 40)
    assert not any("@" in r for r in body_rows(grid))
    assert any(r[1:].startswith("hello world") for r in body_rows(grid))


def test_too_narrow_hides_art():
    grid = compose(view(), 60, 30, PALETTE, 40)
    assert not any("@" in r for r in body_rows(grid))


def test_status_choices_and_command():
    grid = compose(view(), 100, 30, PALETTE, 40)
    assert "Hero | mortal" in row_text(grid, 0)
    assert row_text(grid, 29).startswith("> tal_")
    assert row_text(grid, 27).strip() == "1) Look around"
    assert row_text(grid, 28).strip() == "2) Read your journal"


def test_log_scrolls_and_wraps():
    log = [(f"line {n}", "default") for n in range(100)]
    grid = compose(view(log=log, show_art=False), 100, 30, PALETTE, 40)
    text = "\n".join(body_rows(grid))
    assert "line 99" in text and "line 10 " not in text
    grid = compose(view(log=log, show_art=False, scroll=50), 100, 30, PALETTE, 40)
    assert "line 49" in "\n".join(body_rows(grid)) and "line 99" not in "\n".join(body_rows(grid))
    long = [("word " * 100, "default")]
    grid = compose(view(log=long, show_art=False), 50, 30, PALETTE, 40)
    assert sum("word" in r for r in body_rows(grid)) > 5


def test_tiny_windows_keep_exact_size():
    for cols, rows in [(20, 6), (1, 1), (5, 2), (41, 3)]:
        grid = compose(view(), cols, rows, PALETTE, 40)
        assert len(grid) == rows and all(len(r) == cols for r in grid)
        title = compose_title(cols, rows, PALETTE, ["New world", "Quit"], 0, "oops", "Name: _")
        assert len(title) == rows and all(len(r) == cols for r in title)


def test_title_marks_selection_and_message():
    grid = compose_title(100, 40, PALETTE, ["Continue", "New world", "Quit"], 1, "Bad save")
    text = "\n".join(row_text(grid, r) for r in range(40))
    assert "> New world" in text and "  Continue" in text and "Bad save" in text
```

- [ ] **Step 2: Run to verify fails** → FAIL

- [ ] **Step 3: Implement**

`render/layout.py`:
```python
"""The game screen as a grid of (char, colour) cells. No pygame.

  row 0            status
  row 1            rule
  rows 2..         art frame | log      (art frame docks left or right)
  rule
  choices (up to 9)
  last row         > command
"""

import textwrap
from collections.abc import Sequence
from dataclasses import dataclass

from config import Color
from narrate.base import Line
from render.art import Art, art_width

Cell = tuple[str, Color] | None
Grid = list[list[Cell]]
MIN_LOG_WIDTH = 30


@dataclass
class View:
    status: str
    log: Sequence[Line]
    art: Art
    choices: Sequence[str]
    command: str
    art_side: str = "left"
    show_art: bool = True
    scroll: int = 0


def row_text(grid: Grid, r: int) -> str:
    return "".join(cell[0] if cell else " " for cell in grid[r])


class _Canvas:
    def __init__(self, cols: int, rows: int, palette: dict[str, Color]) -> None:
        self.cols, self.rows, self.palette = cols, rows, palette
        self.grid: Grid = [[None] * cols for _ in range(rows)]

    def colour(self, key: str) -> Color:
        return self.palette.get(key, self.palette["default"])

    def put(self, r: int, c: int, text: str, key: str) -> None:
        if not 0 <= r < self.rows:
            return
        colour = self.colour(key)
        for i, ch in enumerate(text):
            if 0 <= c + i < self.cols and ch != " ":
                self.grid[r][c + i] = (ch, colour)

    def hline(self, r: int) -> None:
        self.put(r, 0, "─" * self.cols, "rule")

    def vline(self, c: int, top: int, bottom: int) -> None:
        for r in range(top, bottom):
            self.put(r, c, "│", "rule")


def compose(view: View, cols: int, rows: int, palette: dict[str, Color], art_cols: int) -> Grid:
    canvas = _Canvas(cols, rows, palette)
    canvas.put(0, 1, view.status[: max(0, cols - 2)], "gold")
    if rows < 4:
        return canvas.grid
    canvas.hline(1)
    command_row = rows - 1
    visible = view.command[-max(1, cols - 3):]
    canvas.put(command_row, 0, f"> {visible}_", "player")

    choice_rows = max(0, min(len(view.choices), 9, (rows - 5) // 2))
    choice_top = command_row - choice_rows
    for k, label in enumerate(view.choices[:choice_rows]):
        canvas.put(choice_top + k, 1, f"{k + 1}) {label}"[: max(0, cols - 2)], "jade")
    canvas.hline(choice_top - 1)

    body_top, body_bottom = 2, choice_top - 1
    body_h = body_bottom - body_top
    if body_h <= 0:
        return canvas.grid

    show_art = view.show_art and cols - art_cols - 1 >= MIN_LOG_WIDTH + 2 and body_h >= 3
    if show_art:
        if view.art_side == "left":
            art_left, divider, log_left = 0, art_cols, art_cols + 2
        else:
            art_left, divider, log_left = cols - art_cols, cols - art_cols - 1, 1
        log_width = cols - art_cols - 3
        canvas.vline(divider, body_top, body_bottom)
        _draw_art(canvas, view.art, art_left, art_cols, body_top, body_h)
    else:
        log_left, log_width = 1, max(1, cols - 2)

    wrapped: list[Line] = []
    for text, key in view.log:
        for piece in textwrap.wrap(text, log_width) or [""]:
            wrapped.append((piece, key))
    scroll = min(max(0, view.scroll), max(0, len(wrapped) - body_h))
    end = len(wrapped) - scroll
    for k, (piece, key) in enumerate(wrapped[max(0, end - body_h):end]):
        canvas.put(body_top + k, log_left, piece, key)
    return canvas.grid


def _draw_art(canvas: _Canvas, art: Art, left: int, width: int, top: int, height: int) -> None:
    top += max(0, (height - len(art)) // 2)
    left += max(0, (width - art_width(art)) // 2)
    for r, row in enumerate(art[:height]):
        for c, cell in enumerate(row[:width]):
            if cell is not None:
                canvas.put(top + r, left + c, cell[0], cell[1])
```
`render/menu.py`:
```python
"""Title and name-entry screens as grids. No pygame."""

from config import Color
from render.art import art_width, load_art
from render.layout import Grid, _Canvas


def compose_title(
    cols: int, rows: int, palette: dict[str, Color], options: list[str], selected: int,
    message: str = "", prompt: str | None = None,
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
        for i, option in enumerate(options):
            text = ("> " if i == selected else "  ") + option
            canvas.put(y, max(0, (cols - 14) // 2), text, "gold" if i == selected else "default")
            y += 1
    if message:
        canvas.put(y + 1, max(0, (cols - len(message)) // 2), message, "red")
    return canvas.grid
```

- [ ] **Step 4: Run tests** → PASS (8 passed)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: pure layout with dockable art frame, title menu" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 12: App state, pygame screen, main loop, launcher

**Files:**
- Create: `app.py`, `render/screen.py`, `main.py`, `run.bat`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `Game`, `parse`, `render_request`, `compose`, `compose_title`, `config_from`, settings store
- Produces:
  - `App(config, saves_dir, settings_path)` with `handle_key(key: str, text: str)`, `grid(cols, rows) -> Grid`, `shutdown()`, and the attributes `state`, `running`, `log`, `choices`, `message`
    - Key names follow `pygame.key.name`: `"return"`, `"enter"`, `"escape"`, `"backspace"`, `"up"`, `"down"`, `"page up"`, `"page down"`, `"f2"`, `"f3"`.
  - `Screen(config)` with `cols`, `rows`, `draw(grid)`, `present()`, `resize(size)`, `toggle_fullscreen()`, `screenshot(path)`, `close()`
  - `main.py --smoke out.png` renders a scripted session headless and saves a PNG.

- [ ] **Step 1: Write the failing test** — `tests/test_app.py`
```python
import pytest

from app import App
from config import Config


@pytest.fixture
def app(tmp_path):
    a = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    yield a
    a.shutdown()


def type_text(app, text):
    for ch in text:
        app.handle_key(ch, ch)


def new_game(app, name="Mo Rin"):
    assert app.title_options()[0] == "New world"
    app.handle_key("return", "\r")
    assert app.state == "name"
    type_text(app, name)
    app.handle_key("return", "\r")
    assert app.state == "game"


def test_new_game_flow(app):
    assert app.title_options() == ["New world", "Quit"]
    new_game(app)
    assert app.log and app.choices
    before = len(app.log)
    app.handle_key("1", "1")  # digit with empty command picks a choice
    assert len(app.log) > before
    assert len(app.grid(100, 30)) == 30


def test_typed_command_and_unknown(app):
    new_game(app)
    type_text(app, "dance wildly")
    app.handle_key("return", "\r")
    assert any("Not understood" in text for text, _ in app.log)
    assert app.command == ""


def test_f2_swaps_side_and_persists(app, tmp_path):
    new_game(app)
    app.handle_key("f2", "")
    assert app.config.art_side == "right"
    assert '"right"' in (tmp_path / "settings.json").read_text()
    app.handle_key("f3", "")
    assert app.config.show_art is False


def test_escape_to_title_then_continue(app):
    new_game(app)
    app.handle_key("escape", "\x1b")
    assert app.state == "title"
    assert app.title_options()[0] == "Continue"
    app.handle_key("return", "\r")
    assert app.state == "game" and app.choices


def test_corrupt_save_shows_message(app, tmp_path):
    saves = tmp_path / "saves"
    saves.mkdir()
    (saves / "broken.world").write_bytes(b"garbage" * 50)
    assert app.title_options()[0] == "Continue"
    app.handle_key("return", "\r")
    assert app.state == "title" and app.message
```

- [ ] **Step 2: Run to verify fails** → FAIL

- [ ] **Step 3: Implement**

`app.py`:
```python
"""What the player is looking at and how keys change it. No pygame here:
keys arrive as pygame.key.name strings plus the typed text, so this is testable."""

import re
import time
from pathlib import Path

from config import PALETTE, Config
from engine.commands import parse
from engine.game import Game, Turn
from render.art import render_request
from render.layout import Grid, View, compose
from render.menu import compose_title
from settings_store import save_values
from world.db import SaveError

MAX_LOG = 500
MAX_COMMAND = 200
MAX_NAME = 24


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "hero"


class App:
    def __init__(self, config: Config, saves_dir: Path, settings_path: Path) -> None:
        self.config = config
        self.saves_dir = Path(saves_dir)
        self.settings_path = Path(settings_path)
        self.state = "title"
        self.running = True
        self.selected = 0
        self.message = ""
        self.name = ""
        self.game: Game | None = None
        self.log: list = []
        self.choices: list = []
        self.art: list = []
        self.status = ""
        self.command = ""
        self.scroll = 0

    # --- saves --------------------------------------------------------------
    def latest_save(self) -> Path | None:
        saves = sorted(self.saves_dir.glob("*.world"), key=lambda p: p.stat().st_mtime, reverse=True)
        return saves[0] if saves else None

    def title_options(self) -> list[str]:
        return (["Continue"] if self.latest_save() else []) + ["New world", "Quit"]

    # --- keys -----------------------------------------------------------------
    def handle_key(self, key: str, text: str) -> None:
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
                self._continue()
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
            self._start_new(self.name.strip() or "Nameless")
        elif len(text) == 1 and text.isprintable() and len(self.name) < MAX_NAME:
            self.name += text

    def _game_key(self, key: str, text: str) -> None:
        if key == "f2":
            self.config.art_side = "right" if self.config.art_side == "left" else "left"
            self._save_settings()
        elif key == "f3":
            self.config.show_art = not self.config.show_art
            self._save_settings()
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
            if not self.command and text in "123456789":
                self.submit(text)
            elif len(self.command) < MAX_COMMAND:
                self.command += text

    # --- game -----------------------------------------------------------------
    def submit(self, text: str) -> None:
        action = parse(text, self.choices)
        self.command = ""
        if action is None or self.game is None:
            return
        self.log.append((f"> {text.strip()}", "player"))
        self._show(self.game.perform(action))

    def _show(self, turn: Turn) -> None:
        if self.log:
            self.log.append(("", "default"))
        self.log.extend(turn.lines)
        del self.log[:-MAX_LOG]
        self.choices = turn.choices
        self.art = render_request(turn.art, self.config.art_width, self.config.art_height)
        self.status = turn.status
        self.scroll = 0

    def _start_new(self, name: str) -> None:
        path = self.saves_dir / f"{slug(name)}-{time.time_ns()}.world"
        self._close_game()
        self.game = Game.new(path, name)
        self.log = []
        self._show(self.game.start())
        self.state = "game"

    def _continue(self) -> None:
        path = self.latest_save()
        try:
            game = Game.load(path)
        except SaveError as exc:
            self.message = str(exc)
            return
        self._close_game()
        self.game, self.log, self.message = game, [], ""
        self._show(game.start())
        self.state = "game"

    def _close_game(self) -> None:
        if self.game is not None:
            self.game.close()
            self.game = None

    def _save_settings(self) -> None:
        save_values({"art_side": self.config.art_side, "show_art": self.config.show_art}, self.settings_path)

    def shutdown(self) -> None:
        self._close_game()

    # --- drawing ----------------------------------------------------------------
    def grid(self, cols: int, rows: int) -> Grid:
        if self.state == "title":
            return compose_title(cols, rows, PALETTE, self.title_options(), self.selected, self.message)
        if self.state == "name":
            return compose_title(cols, rows, PALETTE, [], 0, self.message, f"What is your name? {self.name}_")
        view = View(
            status=self.status, log=self.log, art=self.art,
            choices=[c.label for c in self.choices], command=self.command,
            art_side=self.config.art_side, show_art=self.config.show_art, scroll=self.scroll,
        )
        return compose(view, cols, rows, PALETTE, self.config.art_width)
```
`render/screen.py`:
```python
"""The pygame window: draws a grid of (char, colour) cells in a monospace font.

One of only two modules allowed to import pygame. Adapted from AsciiCrawler's
render/screen.py, with cells sized to the font rather than square.
"""

import pygame

from config import Config
from paths import bundled

FALLBACK = {"│": "|", "─": "-"}


class Screen:
    def __init__(self, config: Config) -> None:
        pygame.init()
        pygame.key.set_repeat(400, 35)
        pygame.display.set_caption(config.window_title)
        self._config = config
        path = bundled(config.font_path)
        self._font = pygame.font.Font(str(path) if path.is_file() else None, config.font_size)
        self.cell_w = self._font.size("M")[0]
        self.cell_h = self._font.get_linesize()
        self._cache: dict = {}
        self._fullscreen = False
        self._windowed = (config.window_width, config.window_height)
        self._open(self._windowed, pygame.RESIZABLE)

    def _open(self, size, flags) -> None:
        self._window = pygame.display.set_mode(size, flags)
        width, height = self._window.get_size()
        self.cols = max(1, width // self.cell_w)
        self.rows = max(1, height // self.cell_h)

    def resize(self, size) -> None:
        if not self._fullscreen:
            self._windowed = size
            self._open(size, pygame.RESIZABLE)

    def toggle_fullscreen(self) -> None:
        """Borderless fullscreen on the desktop resolution, or back to the window."""
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self._open((0, 0), pygame.NOFRAME)
        else:
            self._open(self._windowed, pygame.RESIZABLE)

    def draw(self, grid) -> None:
        self._window.fill(self._config.background_color)
        for r, row in enumerate(grid[: self.rows]):
            for c, cell in enumerate(row[: self.cols]):
                if cell is not None:
                    self._window.blit(self._glyph(*cell), (c * self.cell_w, r * self.cell_h))

    def _glyph(self, ch: str, colour) -> pygame.Surface:
        key = (ch, colour)
        if key not in self._cache:
            metrics = self._font.metrics(ch)
            if not metrics or metrics[0] is None:
                ch = FALLBACK.get(ch, "?")
            self._cache[key] = self._font.render(ch, True, colour)
        return self._cache[key]

    def present(self) -> None:
        pygame.display.flip()

    def screenshot(self, path) -> None:
        pygame.image.save(self._window, str(path))

    def close(self) -> None:
        pygame.quit()
```
`main.py`:
```python
"""DeepMurim. `python main.py` to play; `python main.py --smoke out.png` for a headless check."""

import os
import sys
import tempfile
from pathlib import Path


def run(smoke_png: str | None = None) -> None:
    if smoke_png:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    import pygame

    from app import App
    from config import config_from
    from paths import beside
    from render.screen import Screen
    from settings_store import DEFAULT_PATH, load_values

    if smoke_png:
        temp = Path(tempfile.mkdtemp())
        config = config_from({})
        app = App(config, temp / "saves", temp / "settings.json")
    else:
        config = config_from(load_values())
        app = App(config, beside("saves"), DEFAULT_PATH)
    screen = Screen(config)

    if smoke_png:
        for key, text in [("return", "\r"), *[(ch, ch) for ch in "Tester"], ("return", "\r"), ("1", "1")]:
            app.handle_key(key, text)
        screen.draw(app.grid(screen.cols, screen.rows))
        screen.screenshot(smoke_png)
        app.shutdown()
        screen.close()
        return

    clock = pygame.time.Clock()
    while app.running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                app.running = False
            elif event.type == pygame.VIDEORESIZE:
                screen.resize(event.size)
            elif event.type == pygame.KEYDOWN:
                key = pygame.key.name(event.key)
                if key == "f11":
                    screen.toggle_fullscreen()
                else:
                    app.handle_key(key, event.unicode)
        screen.draw(app.grid(screen.cols, screen.rows))
        screen.present()
        clock.tick(30)
    app.shutdown()
    screen.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    run(args[1] if len(args) >= 2 and args[0] == "--smoke" else None)
```
`run.bat`:
```bat
@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
.venv\Scripts\python.exe main.py
```

- [ ] **Step 4: Run tests** → `.venv/Scripts/python.exe -m pytest -q` → all PASS

- [ ] **Step 5: Headless smoke** — `.venv/Scripts/python.exe main.py --smoke "$SCRATCH/smoke.png"`, then open the PNG with the Read tool. Expected:
  - a status bar;
  - scene art on the left, behind a `│` divider;
  - a log showing the opening narration and the first choice's result;
  - numbered choices;
  - a `> _` command line.

  If box characters show as `?`, check `FALLBACK`.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: playable window, app state, launcher" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 13: End-to-end persistence

**Files:**
- Test: `tests/test_persistence.py` (no production code expected. If a test fails, fix the owning module.)

**Interfaces:**
- Consumes: `Game`, `Action`

- [ ] **Step 1: Write the test** — `tests/test_persistence.py`
```python
from engine.game import Action, Game


def talk_choice(turn):
    return next(c for c in turn.choices if c.action.verb == "talk")


def test_npc_remembers_across_reload(tmp_path):
    path = tmp_path / "w.world"
    game = Game.new(path, "Tester", world_seed=42)
    choice = talk_choice(game.start())
    npc_name = game.world.entity(choice.action.target).name
    game.perform(choice.action)
    game.perform(Action("farewell"))
    digest = game.world.digest()
    game.close()

    game = Game.load(path)
    assert game.world.digest() == digest
    look = game.start()
    assert any("(knows you)" in text for text, _ in look.lines)
    turn = game.perform(choice.action)
    assert game.world.chronicle_about(game.player.id, limit=1)[0].kind == "conversed"
    assert any(npc_name in text for text, _ in turn.lines)
    game.close()


def test_same_seed_same_world(tmp_path):
    names = []
    for n in range(2):
        game = Game.new(tmp_path / f"{n}.world", "Tester", world_seed=7)
        names.append((game.place.name, [c.label for c in game.start().choices]))
        game.close()
    assert names[0] == names[1]


def test_there_and_back_again(tmp_path):
    game = Game.new(tmp_path / "w.world", "Tester", world_seed=42)
    home = game.place.id
    residents = {c.action.target for c in game.start().choices if c.action.verb == "talk"}
    north = next(c for c in game.look().choices if "north road" in c.label)
    game.perform(north.action)
    south = next(c for c in game.look().choices if "south road" in c.label)
    turn = game.perform(south.action)
    assert game.place.id == home
    assert {c.action.target for c in turn.choices if c.action.verb == "talk"} == residents
    game.close()
```

- [ ] **Step 2: Run** — `.venv/Scripts/python.exe -m pytest -q` → all PASS. If something fails, find the cause with superpowers:systematic-debugging before changing anything.

- [ ] **Step 3: Manual check** — run `run.bat` and walk through the following:
  1. Choose New world and enter a name.
  2. Press `1` to talk, then `3` to say farewell.
  3. Travel north.
  4. Press F2: the art moves right. Press F3: the art hides.
  5. Press Esc, then Continue: the log reloads and "(knows you)" shows once you're back home.

- [ ] **Step 4: Commit** — `git add -A && git commit -m "test: end-to-end persistence and stability" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

## Self-review notes

- **Spec §8.1 coverage:**
  - Window, layout, and dockable frame: Tasks 11 and 12.
  - Choices plus command line: Tasks 9, 11, and 12.
  - Database and chronicle: Tasks 3 and 4.
  - Seeded generation: Tasks 2 and 5.
  - Travel, look, and talk with memory: Tasks 6 and 8.
  - Procedural narration: Task 7.
  - Art loader with scenes and portraits: Task 10.
  - Save, load, and new world: Tasks 3, 12, and 13.
  - Narrator, `Brief`, and proposal interfaces: Task 7. Briefs meet the spec §6.0 bar: at most 6 ranked facts, no ids, and a prompt of at most 1,200 characters (`test_brief.py`).
- **Deferred to later phases (by the spec):** facts and beliefs are used only as empty tables, and there is no level-of-detail simulation.
- **Review Focus:**
  - Items 1 and 2: `test_commands.py`.
  - Item 3: `test_layout.py::test_tiny_windows_keep_exact_size`.
  - Item 4: `test_db.py::test_open_missing_corrupt_and_future` and `test_app.py::test_corrupt_save_shows_message`.
  - Item 5: `test_gen.py::test_region_is_deterministic_at_extreme_coordinates`.
