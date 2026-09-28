# Phase 5d: Forging and Formations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The player forges weapons and armour from materials, refines what they hold, and names a masterwork into legend; learns formation patterns and lays them to guard a sect, fight within, hide and cultivate in peace, and read the ancient arrays of secret realms; and the world's smiths and formation masters practise, take commissions, and meet once a year.

**Architecture:**
- **5b's craft shape, twice over.** Forging keeps a mastery per form and a level; formations keep a mastery per pattern (`knows_formation`) and a level. Materials, manuals and flags are items.
- **What a formation does is read where the rule lives.** `systems/arrays.py` holds small factors that 3c's gate, 5c's theft, 2b's fighters and fleeing and challengers, and 2a's meditation read from the town the formation was laid on. Nothing there writes.
- **The world's side is 5c's:** crafters' skill a seed until it rises (a lives agenda), commissions small records, the Meet one meta row.

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-28-phase5d-forging-formations-design.md`

## Global Constraints

- **Save format:** no save-format version change. New state lives in:
  - `material`, `forge`, `formation`, `formation_manual` and `flags` entities; 3c's `buildings` (`forge`);
  - person data `forge_mastery`, `forge_xp`, `last_forged`, `formation_xp`, `craft_skill`, `commissions`, `slain_game`; gear data `forged_by`;
  - town data `ore_sold` and `formations`; the meta row `meet`.
- **Knowledge vs truth:**
  - a formation laid is named to its owner and to one who knows the pattern; to anyone else it is "something laid here";
  - a crafter's skill is told when you talk shop with them;
  - a masterwork's legend and the Meet's champions are facts that spread; a sect's legend in 5a's tales is not quoted in a rumour (ruling 9).
- **Reads never write:** pages, choices and blocks never make an item or a person; a formation's strength is read from the town.
- **One effect per event kind:** new modules `@listen` or register hooks. Existing effects are never re-registered, and no handler name is reused (ruling 10).
- **Seeded rolls stay where they were:** new rolls use their own seeded streams (`ore:`, `forge:`, `lay:`, `ward:`, `craft_rise:`, `meet:`), never the life clock's shared season stream; no occupation is added (ruling 2).
- **Speed (CPU time, averaged after `gc.collect()`):**
  - a season of 200 NPCs with the craft agenda stays within +10% of 5c's season;
  - `fighter_for` inside an array stays within +10%;
  - the crafts, anvil and smith menus are each under 20 ms;
  - the 500-year soak keeps its limits.
- **Commits:** every commit message ends with the session's Co-Authored-By attribution line.

## Review Focus

1. **A formation is read, never written, where its rule lives:** Task 4 pins every hook with `tests/test_arrays.py`, and `test_a_place_without_formations_reads_nothing_more` pins that a town without one costs nothing more.
2. **Handler names:** `study` is 2b's (a martial manual); the pattern's is `study_formation`. Task 7 pins it with the whole suite's `test_buying_and_studying_a_manual`.
3. **No faction named before it is known:** 5a's blade legends name sects, so a rumour of one does not quote it (ruling 9). Every fuzz run checks it on each screen; the gear fuzz found it.
4. **The craft agenda stays cheap:** within +10% of 5c's season, measured on the same people rolled back. Task 8 pins it with `test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5cs`.
5. **Random play through the anvil, the arrays, the masters and the Meet:** no crash, no rule broken. Task 8 pins it with `test_a_wandering_smith`.

## Plan-time rulings (deviations from the spec, argued)

1. **Star iron stays a treasure** (it still sells as one) and counts as a material of grade 3, as 5b ruled for prize herbs. *Cost if wrong:* none.
2. **Smiths are blacksmiths by trade and formation masters are fortune tellers** (the geomancers of wuxia). A new occupation would reshuffle every seeded person. *Cost if wrong:* none.
3. **A forged grade is the materials' mean, rounded down,** a grade more for a master of the form (mastery 0.8). *Cost if wrong:* none.
4. **Only weapons are named masterworks,** since 5a's famous items are weapons; three names are seeded from 5a's `NAMES`, none already a famous weapon's. *Cost if wrong:* a masterwork robe has no name.
5. **A sect's defences are laid only at a seat of one's own sect; the Heavenly Gate only at the player's own sect's gate.** *Cost if wrong:* none.
6. **A battle array acts on everyone in its town until the next dawn:** `fighter_for` does not know a fighter's foe, so the Confusion array weakens everyone but its owner. *Cost if wrong:* an ally is weakened too.
7. **The Meet is its own yearly module, not a 4e tournament kind:** a bracket of fights does not fit a show of work. It is decided in the season after it closes, and its seeded masters are names, not people. *Cost if wrong:* none.
8. **A crafter's talk options fold into one "Their craft..." submenu,** as 5c's "Alchemy and medicine...", and `tests/test_game.py`'s conversation test gains the verb. *Cost if wrong:* none.
9. **A rumour of a blade legend quotes a smith's own legend ("forged by ...") and otherwise says only that the blade is one of legend:** 5a's legends name sects the hearer may never have heard of. *Cost if wrong:* none.
10. **Studying a formation manual is `study_formation`,** with no typed `study`: 2b's `study` studies a martial manual. *Cost if wrong:* none.
11. **Flags are bought from formation masters only;** forging them from spirit iron is left for later. *Cost if wrong:* flags come only from masters.
12. **Patterns are learnt from manuals and from passing an ancient array; no manual lies in a realm's chambers,** since adding one would reshuffle 4f's seeded prizes. *Cost if wrong:* realms teach, but hold no manuals.
13. **A great sect keeps its own ward, seeded 0-1,** weighed in 5c's theft; 5c's test of the realms' weight now holds it aside. *Cost if wrong:* none.
14. **NPC masters lay no battle arrays** (the spec left it open). *Cost if wrong:* none.
15. **A smith forges on commission a grade below their skill, for twice the stall's price of that grade.** *Cost if wrong:* none.
16. **A latent fault the fuzz reached once Task 5 moved its paths:** a death at a turn's end (5b's poison, 5c's worms) shows the scene it came in, and the dead lie `buried_at`, not `located_in`, so `check_people` took the people standing there for strangers. The rule now counts those where the dead fell. *Cost if wrong:* none.

## Files

| File | Responsibility |
|---|---|
| `systems/data/materials.toml`, `systems/materials.py` | Materials, the smith's ore, a slain beast's parts, forges. |
| `systems/forging.py` | Forging, mastery and level, refining, masterworks. |
| `systems/data/formations.toml`, `systems/formations.py` | Patterns, manuals, flags, laying, 4f's trials. |
| `systems/arrays.py` | What formations do, read where each rule lives. |
| `systems/craft_world.py` | Smiths' and formation masters' skill, wares and commissions. |
| `systems/meet.py` | The Meet of Hammer and Furnace. |
| `engine/crafts.py`, `engine/crafts_page.py` | `CraftsMixin`: choices, menus, handlers; the crafts page and the sheet's lines. |
| `narrate/crafts_text.py`, `narrate/grammar/crafts.toml` | Outcomes, journal lines, rumours. |

Existing files touched: `world/db.py`, `systems/sect.py`, `systems/world_clock.py`, `systems/chambers.py`, `systems/sect_seasons.py`, `systems/hall_theft.py`, `systems/duel.py`, `systems/encounters.py`, `systems/cultivation.py`, `systems/smithy.py`, `debug/invariants.py`, `engine/game.py`, `engine/commands.py`, `engine/sheet.py`, `narrate/outcomes.py`, `docs/world-events.md`, and the tests `tests/test_hall_theft.py` and `tests/test_game.py`.

**How each task is laid out:**
1. The tests, as whole new files.
2. The new modules, as whole files.
3. The run that shows what the edits must still do.
4. One patch script, `.patches/5d_taskN.py`, holding the task's edits to existing files (including files made by earlier tasks). Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: Materials and the forge

Materials are items of a table (`systems/data/materials.toml`): iron ingots and black steel from any smith, spirit iron in a city, bones and cores from a slain beast, and 4d's star iron, which counts as a material of grade 3 and stays a treasure. A smith's ore is a seeded stock by the season, as 5a's stall. Gear is worked at one's own forge (300 silver), a smith's rented for the day (30), or the own sect's `forge` building. `check_crafts` joins the rules.

**Files:**
- Create: `systems/data/materials.toml`
- Create: `systems/materials.py`
- Create: `tests/test_materials.py`
- Modify (by `.patches/5d_task1.py`): `systems/sect.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: 4c's `market.drift`, `event_factor`; 4a's `lives.current_season`; 3c's `sect.built`, `founding.my_sect`; 4d's `star_iron` treasure; 5b's butchering as the model.
- Produces:
  - `M` (systems/materials.py): `MATERIALS`, `STOCK`, `FORGE_PRICE`, `FORGE_RENT`, `CORE_REALM`, `PARTS`; `make_material(world, name, owner, how)`, `material_info(item)`, `materials_of(world, person)`, `spend(world, person, items)`, `stock(world, town)`, `price(world, town, name)`, `buy_block(world, person, town, key)`, `buy_events(world, person, town, key)`, `parts_block(world, person, beast, part, place)`, `parts_events(world, person, beast, part, place)`, `forge_of(world, person)`, `sect_forge(world, person, place)`, `rent(world, person, place)`, `forge_block(world, person, place)`, `buy_forge_block(world, person)`, `buy_forge_events(world, person, town)`; events `beast_parts_taken`, `forge_bought`, `material_bought`.
  - `sect.BUILDINGS['forge']`; `debug.invariants.check_crafts(world)`.

- [ ] **Step 1: Write the tests**

`tests/test_materials.py`:
```python
import pytest

import systems.encounters as encounters
import systems.materials as M
import systems.sect as sect_mod
from debug.invariants import check_crafts
from engine.game import Game
from systems import factions as F
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit


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


def a_beast(game, tag, realm="third-rate"):
    world = game.world
    beast = world.add_entity("person", "a grey wolf", {"beast": True, "occupation": "grey wolf", "realm": realm,
                                                       "traits": ["hot-tempered"]}, f"test:beast:{tag}")
    world.relate(beast, game.place.id, "located_in")
    commit(world, [Event("died", (game.player.id, beast), game.place.id, {"cause": "killed"})])
    return beast


def test_every_material_has_a_grade_and_a_way_to_be_had():
    for name, row in M.MATERIALS.items():
        assert 0 <= row["grade"] <= 4, name
        assert row["sold"] or row.get("source"), name


def test_the_smith_sells_iron_by_the_season_and_a_bought_ingot_is_gone_from_the_stock(game):
    world, me, town = game.world, game.player.id, game.place.id
    offers = M.stock(world, town)
    assert offers and M.stock(world, town) == offers
    kind = world.entity(town).data["kind"]
    assert all(kind in M.MATERIALS[o["material"]]["sold"] for o in offers)
    first = offers[0]
    assert M.buy_block(world, me, town, first["key"]) is None
    commit(world, M.buy_events(world, me, town, first["key"]))
    assert first["key"] not in [o["key"] for o in M.stock(world, town)]
    [item] = M.materials_of(world, me)
    assert M.material_info(item) == (first["material"], M.MATERIALS[first["material"]]["grade"])
    assert silver_of(world, me) == 5000 - M.price(world, town, first["material"])


def test_star_iron_is_a_material_of_the_third_grade_and_stays_a_treasure(game):
    world, me = game.world, game.player.id
    lump = world.add_entity("treasure", "a lump of star iron", {"kind": "star_iron", "value": 500, "used": False})
    world.relate(me, lump, "owns")
    assert M.material_info(world.entity(lump)) == ("star iron", 3)
    M.spend(world, me, [lump])
    assert M.material_info(world.entity(lump)) is None


def test_a_slain_beast_gives_its_bones_and_a_strong_one_its_core(game):
    world, me, here = game.world, game.player.id, game.place.id
    weak, strong = a_beast(game, "weak", "third-rate"), a_beast(game, "strong", "second-rate")
    assert "too weak" in M.parts_block(world, me, weak, "core", here)
    assert M.parts_block(world, me, weak, "bone", here) is None
    commit(world, M.parts_events(world, me, weak, "bone", here))
    assert "already" in M.parts_block(world, me, weak, "bone", here)
    commit(world, M.parts_events(world, me, strong, "core", here))
    assert sorted(M.material_info(m) for m in M.materials_of(world, me)) == [("beast bone", 1), ("beast core", 2)]


def test_a_living_beast_gives_nothing(game):
    world, me, here = game.world, game.player.id, game.place.id
    wolf = world.add_entity("person", "a grey wolf", {"beast": True, "realm": "second-rate"}, "test:beast:alive")
    world.relate(wolf, here, "located_in")
    assert M.parts_block(world, me, wolf, "bone", here) is not None


def test_a_forge_is_owned_rented_or_the_sects_own(game):
    world, me, town = game.world, game.player.id, game.place.id
    assert M.forge_block(world, me, town) is None and M.rent(world, me, town) == M.FORGE_RENT
    commit(world, M.buy_forge_events(world, me, town))
    assert M.forge_of(world, me) is not None and M.rent(world, me, town) == 0
    assert "forge" in sect_mod.BUILDINGS


def test_the_own_sects_forge_is_worked_for_nothing_at_its_seat(game):
    world, me, town = game.world, game.player.id, game.place.id
    sect = world.add_entity("faction", "Pine Cloud Hall", {
        "type": "player_sect", "tier": "minor", "home": [0, 0], "seat": town, "path": "righteous", "taboos": [],
        "trial": "spar", "ranks": list(F.LADDERS["orthodox_sect"]), "treasury": 2000, "power": 20, "wealth": 0,
        "buildings": {"forge": {"done_at": 0, "built": True}}, "last_tick": world.time, "founder": me,
        "dissolved": False, "chronicle": [], "arts": [], "forms": [], "branches": []})
    world.update_data(me, sect=sect)
    assert M.sect_forge(world, me, town) and M.rent(world, me, town) == 0


def test_the_rules_hold_materials_to_the_table(game):
    world, me = game.world, game.player.id
    M.make_material(world, "iron ingot", me)
    assert check_crafts(world) == []
    world.add_entity("material", "moon silver", {"material": "moon silver", "grade": 7})
    assert "material" in " | ".join(check_crafts(world))
```

- [ ] **Step 2: Write the new modules**

`systems/data/materials.toml`:
```toml
# The materials of the forge (phase 5d spec 2): the same in every world.
# grade 0-4 (iron to divine, as 5a's gear); price in silver at a smith's, where it is sold at all;
# sold: the kinds of town whose smith keeps it; source: how else it is had.

["iron ingot"]
grade = 0
price = 10
sold = ["village", "town", "city"]

["black steel"]
grade = 1
price = 60
sold = ["town", "city"]

["spirit iron"]
grade = 2
price = 300
sold = ["city"]

["star iron"]
grade = 3
price = 0
sold = []
source = "a star fall (4d)"

["beast bone"]
grade = 1
price = 0
sold = []
source = "a slain beast"

["beast core"]
grade = 2
price = 0
sold = []
source = "a slain beast of realm 2 or more"
```

`systems/materials.py`:
```python
"""Materials and the forge (phase 5d spec 2): what gear is forged from, where it is had, and where it is worked.

A material is an item (`kind = "material"`): a `material` name of the table (`systems/data/materials.toml`) and its
`grade`. 4d's star iron counts as a material of grade 3 and stays a treasure (it still sells as one). A smith sells
iron and steel by the season, as 5a's stall sells gear; a slain beast gives its bones and, if strong, its core. Gear
is forged at one's own forge, at a smith's rented for the day, or at one's own sect's forge.
"""

import tomllib
from pathlib import Path

import systems.lives as lives
from systems.market import drift, event_factor
from systems.purse import silver_of
from systems.realms import realm_index
from world.events import Event, effect
from world.seed import rng_for

MATERIALS = tomllib.loads((Path(__file__).parent / "data" / "materials.toml").read_text(encoding="utf-8"))
STOCK = {"iron ingot": (3, 6), "black steel": (1, 3), "spirit iron": (0, 1)}
FORGE_PRICE, FORGE_RENT = 300, 30
CORE_REALM = 2
PARTS = ("bone", "core")


def make_material(world, name: str, owner: int | None, how: str = "found") -> int:
    item = world.add_entity("material", name, {"material": name, "grade": MATERIALS[name]["grade"], "how": how})
    if owner is not None:
        world.relate(owner, item, "owns")
    return item


def material_info(item) -> tuple[str, int] | None:
    """(name, grade) of a material: a forge's own, or 4d's star iron (spec 2)."""
    if item is None or item.data.get("used"):
        return None
    if item.kind == "material":
        return item.data["material"], item.data["grade"]
    if item.kind == "treasure" and item.data.get("kind") == "star_iron":
        return "star iron", MATERIALS["star iron"]["grade"]
    return None


def materials_of(world, person: int) -> list:
    return [e for e in (world.entity(i) for i in world.targets(person, "owns")) if material_info(e) is not None]


def spend(world, person: int, items) -> None:
    for item in items:
        world.unrelate(person, "owns", item)
        world.update_data(item, used=True)


# --- the smith's ore --------------------------------------------------------------------------------------

def stock(world, town: int) -> list[dict]:
    """This season's materials at the smith's: {key, material}, less what was bought."""
    kind = world.entity(town).data.get("kind")
    season = lives.current_season(world)
    rng = rng_for(world.world_seed, f"ore:{town}:{season}")
    out = []
    for name in sorted(STOCK):
        if kind not in MATERIALS[name]["sold"]:
            continue
        for n in range(rng.randint(*STOCK[name])):
            out.append({"key": f"{name}:{n}", "material": name})
    sold = (world.entity(town).data.get("ore_sold") or {}).get(str(season), [])
    return [o for o in out if o["key"] not in sold]


def price(world, town: int, name: str) -> int:
    return max(1, round(MATERIALS[name]["price"] * event_factor(world, town, "iron") * drift(world, town, "gear")))


def buy_block(world, person: int, town: int, key: str) -> str | None:
    offer = next((o for o in stock(world, town) if o["key"] == key), None)
    if offer is None:
        return "The smith has none of that now."
    if silver_of(world, person) < price(world, town, offer["material"]):
        return "You cannot pay for it."
    return None


def buy_events(world, person: int, town: int, key: str) -> list[Event]:
    offer = next(o for o in stock(world, town) if o["key"] == key)
    return [Event("material_bought", (person,), town, {**offer, "season": lives.current_season(world),
                                                        "price": price(world, town, offer["material"])})]


@effect("material_bought")
def _bought(world, event) -> None:
    person, town, d = event.actors[0], event.place, event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    sold = world.entity(town).data.get("ore_sold") or {}
    season = str(d["season"])
    world.update_data(town, ore_sold={season: sold.get(season, []) + [d["key"]]})  # only this season's list is kept
    make_material(world, d["material"], person, "bought")


# --- a slain beast ----------------------------------------------------------------------------------------

def parts_block(world, person: int, beast: int, part: str, place) -> str | None:
    entity = world.entity(beast) if isinstance(beast, int) else None
    if entity is None or not entity.data.get("beast") or not entity.data.get("dead") or part not in PARTS:
        return "There is nothing to take."
    if place not in world.targets(beast, "buried_at") + world.targets(beast, "located_in"):
        return "It is not here."
    if part in (entity.data.get("parts_taken") or []):
        return "That has been taken already."
    if part == "core" and realm_index(entity.data.get("realm", "mortal")) < CORE_REALM:
        return "It was too weak a beast to carry a core."
    return None


def parts_events(world, person: int, beast: int, part: str, place) -> list[Event]:
    return [Event("beast_parts_taken", (person, beast), place, {"part": part})]


@effect("beast_parts_taken")
def _parts(world, event) -> None:
    person, beast = event.actors
    part = event.data["part"]
    world.update_data(beast, parts_taken=(world.entity(beast).data.get("parts_taken") or []) + [part])
    make_material(world, f"beast {part}", person, "butchered")


# --- the forge --------------------------------------------------------------------------------------------

def forge_of(world, person: int) -> int | None:
    return next((i for i in world.targets(person, "owns") if world.entity(i).kind == "forge"
                 and not world.entity(i).data.get("cracked")), None)


def sect_forge(world, person: int, place) -> bool:
    """The player's own sect's forge, at its seat (3c's buildings)."""
    import systems.sect as sect_mod
    from systems.founding import my_sect
    sect = my_sect(world, person)
    return sect is not None and world.entity(sect).data.get("seat") == place and sect_mod.built(world, sect, "forge")


def rent(world, person: int, place) -> int:
    return 0 if forge_of(world, person) is not None or sect_forge(world, person, place) else FORGE_RENT


def forge_block(world, person: int, place) -> str | None:
    """One's own forge, one's own sect's, or a town smith's to rent."""
    if forge_of(world, person) is not None or sect_forge(world, person, place):
        return None
    if world.entity(place).kind != "town":
        return "You need a forge, or a town's smith to rent one."
    if silver_of(world, person) < FORGE_RENT:
        return f"The smith's forge costs {FORGE_RENT} silver for the day."
    return None


def buy_forge_block(world, person: int) -> str | None:
    if forge_of(world, person) is not None:
        return "You have a forge already."
    if silver_of(world, person) < FORGE_PRICE:
        return f"An anvil and a forge cost {FORGE_PRICE} silver."
    return None


def buy_forge_events(world, person: int, town: int) -> list[Event]:
    return [Event("forge_bought", (person,), town, {"price": FORGE_PRICE})]


@effect("forge_bought")
def _forge(world, event) -> None:
    person = event.actors[0]
    world.update_data(person, silver=silver_of(world, person) - event.data["price"])
    world.relate(person, world.add_entity("forge", "an anvil and a travelling forge", {"cracked": False}), "owns")
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_materials.py`
Expected: `1 error`: collection stops: the tests import `check_crafts`, which Step 4 adds.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5d_task1.py`:
```python
"""Phase 5d, Task 1: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/sect.py', r''', "herb_garden": (250, 10), "pill_hall": (300, 15)}''', r''', "herb_garden": (250, 10), "pill_hall": (300, 15),
             "forge": (300, 15)}''')
edit('systems/world_clock.py', r'''import systems.control  # noqa: E402,F401  phase 5c: control pills, their masters and their bound
''', r'''import systems.control  # noqa: E402,F401  phase 5c: control pills, their masters and their bound
import systems.materials  # noqa: E402,F401  phase 5d: materials and the forge
''')
edit('debug/invariants.py', r'''    problems += check_alchemy_world(world)
''', r'''    problems += check_alchemy_world(world)
    problems += check_crafts(world)
''')
edit('debug/invariants.py', r'''def check_toxins(world) -> list[str]:''', r'''def check_crafts(world) -> list[str]:
    """Materials of the table (phase 5d)."""
    from systems.materials import MATERIALS
    out = []
    for item in world.entities("material"):
        if item.data.get("material") not in MATERIALS or not 0 <= item.data.get("grade", -1) <= 4:
            out.append(f"{item.name} (#{item.id}) is no material of the table")
    return out


def check_toxins(world) -> list[str]:''')
print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5d_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_materials.py`
Expected: `8 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1387 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: materials and the forge - iron by the season, bones and cores from the slain, star iron, and forges owned, rented or built"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 2: Forging, refining and masterworks

Forging takes a slot, a form and one to three materials: the grade is their mean, rounded down, one more for a master of the form (ruling 3), at most divine. One roll on the form's mastery, strength and the forging level; success makes 5a's gear with `forged_by`, and a burn takes the worst tenth of failures. Refining lifts a held piece a grade with a finer material on a harder roll, and one failure in ten cracks it. A weapon of treasure grade the player forged is named once from three seeded names and joins 5a's famous weapons with a legend. `World.rename` gives an entity a new name.

**Files:**
- Create: `systems/forging.py`
- Create: `tests/test_forging.py`
- Modify (by `.patches/5d_task2.py`): `world/db.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Task 1's `materials`; 5a's `gear.make_item`, `gear_name`, `famous` (`NAMES`, `FORM_WORDS`, `famous_weapons`); 3a's `facts.record_fact`.
- Produces:
  - `FG` (systems/forging.py): `MIN_MATERIALS`, `MAX_MATERIALS`, `FIRST_MASTERY`, `MASTERY_STEP`, `MASTER_AT`, `BOUNDS`, `BURN_SHARE`, `REFINE_PENALTY`, `REFINE_CRACK`, `MASTERWORK_GRADE`, `WATCHES`, `FORMS`; `mastery(world, person, form)`, `level(world, person)`, `chance(world, person, form)`, `grade_of(world, person, form, items)`, `forge_block(world, person, place, slot, form, items)`, `forge_events(world, person, place, slot, form, items)`, `refine_block(world, person, place, item_id, material_id)`, `refine_events(world, person, place, item_id, material_id)`, `masterwork_block(world, person, item_id)`, `names_for(world, item_id)`, `masterwork_events(world, person, item_id, name, place)`; events `forged`, `gear_refined`, `masterwork_named`.
  - `World.rename(entity_id, name)`; forging masteries and masterworks in `check_crafts`.

- [ ] **Step 1: Write the tests**

`tests/test_forging.py`:
```python
import pytest

import systems.encounters as encounters
import systems.famous as FW
import systems.forging as FG
import systems.gear as gear
import systems.materials as M
from debug.invariants import check_crafts
from engine.game import Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
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


def mats(game, *names):
    return [M.make_material(game.world, n, game.player.id) for n in names]


def test_the_grade_is_the_mean_of_the_materials_and_a_master_adds_one(game):
    world, me = game.world, game.player.id
    assert FG.grade_of(world, me, "sword", mats(game, "iron ingot", "black steel", "spirit iron")) == 1
    assert FG.grade_of(world, me, "sword", mats(game, "spirit iron", "star iron")) == 2
    world.update_data(me, forge_mastery={"sword": 0.8})
    assert FG.grade_of(world, me, "sword", mats(game, "spirit iron", "star iron")) == 3
    assert FG.grade_of(world, me, "sword", mats(game, "star iron", "star iron")) == 4


def test_a_forged_blade_is_made_by_the_smith_and_teaches_the_hand(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    monkeypatch.setattr(FG, "BOUNDS", (1.0, 1.0))
    items = mats(game, "black steel", "black steel")
    assert FG.forge_block(world, me, town, "weapon", "sword", items) is None
    start = world.time
    commit(world, FG.forge_events(world, me, town, "weapon", "sword", items))
    made = world.entity(world.entity(me).data["last_forged"])
    assert made.data["grade"] == 1 and made.data["form"] == "sword" and made.data["maker"] == me
    assert made.name == "a fine steel sword" and made.id in world.targets(me, "owns")
    assert FG.mastery(world, me, "sword") == pytest.approx(FG.FIRST_MASTERY + FG.MASTERY_STEP)
    assert world.entity(me).data["forge_xp"] == 2 and world.time == start + FG.WATCHES
    assert silver_of(world, me) == 5000 - M.FORGE_RENT and not M.materials_of(world, me)


def test_a_failed_forging_spends_the_materials_and_the_worst_burn(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    monkeypatch.setattr(FG, "BOUNDS", (0.0, 0.0))
    commit(world, FG.forge_events(world, me, town, "armour", "mail", mats(game, "iron ingot")))
    assert not gear.gear_items(world, me) or all(i.data.get("forged_by") is None for i in gear.gear_items(world, me))
    assert not M.materials_of(world, me)
    monkeypatch.setattr(FG, "BURN_SHARE", 1.0)
    commit(world, FG.forge_events(world, me, town, "armour", "mail", mats(game, "iron ingot")))
    assert any(i.cause == "a forge's fire" for i in load_body(world, me).injuries)


def test_nothing_of_no_shape_is_forged_and_the_anvil_takes_one_to_three(game):
    world, me, town = game.world, game.player.id, game.place.id
    assert "shape" in FG.forge_block(world, me, town, "weapon", "mail", mats(game, "iron ingot"))
    assert "1 to 3" in FG.forge_block(world, me, town, "weapon", "sword", mats(game, *["iron ingot"] * 4))


def test_the_forging_level_grows_with_what_is_forged(game):
    world, me = game.world, game.player.id
    assert FG.level(world, me) == 0
    world.update_data(me, forge_xp=40)
    assert FG.level(world, me) == 2


def test_refining_lifts_a_held_piece_a_grade_with_a_finer_material(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    sword = gear.make_item(world, "weapon", "sword", 0, me, "bought")
    [steel] = mats(game, "black steel")
    [ingot] = mats(game, "iron ingot")
    assert "finer" in FG.refine_block(world, me, town, sword, ingot)
    monkeypatch.setattr(FG, "BOUNDS", (1.0, 1.0))
    monkeypatch.setattr(FG, "REFINE_PENALTY", 0.0)
    assert FG.refine_block(world, me, town, sword, steel) is None
    commit(world, FG.refine_events(world, me, town, sword, steel))
    assert world.entity(sword).data["grade"] == 1 and world.entity(sword).name == "a fine steel sword"


def test_a_failed_refining_now_and_then_cracks_the_piece(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    sword = gear.make_item(world, "weapon", "sword", 0, me, "bought")
    monkeypatch.setattr(FG, "BOUNDS", (0.0, 0.0))
    monkeypatch.setattr(FG, "REFINE_CRACK", 1.0)
    commit(world, FG.refine_events(world, me, town, sword, mats(game, "black steel")[0]))
    assert world.entity(sword).data["broken"] and world.entity(sword).data["grade"] == 0


def test_a_treasure_of_ones_own_forging_is_named_and_made_famous(game):
    world, me, town = game.world, game.player.id, game.place.id
    bought = gear.make_item(world, "weapon", "sword", 3, me, "bought")
    assert "own forging" in FG.masterwork_block(world, me, bought)
    blade = gear.make_item(world, "weapon", "saber", 3, me, "forged", maker=me, forged_by=me)
    low = gear.make_item(world, "weapon", "saber", 2, me, "forged", maker=me, forged_by=me)
    assert "treasure" in FG.masterwork_block(world, me, low)
    assert FG.masterwork_block(world, me, blade) is None
    names = FG.names_for(world, blade)
    assert len(names) == 3 and all(n.endswith("Saber") for n in names) and FG.names_for(world, blade) == names
    commit(world, FG.masterwork_events(world, me, blade, names[1], town))
    assert world.entity(blade).name == names[1] and world.entity(blade).data["famous"]
    assert blade in FW.famous_weapons(world)
    [fact] = [f for f in world.facts(predicate="blade_legend") if f.subject == blade]
    assert fact.variant["legend"] == f"forged by {world.entity(me).name}"
    assert "already" in FG.masterwork_block(world, me, blade)
    assert check_crafts(world) == []


def test_the_rules_hold_a_forging_mastery_to_0_1(game):
    world, me = game.world, game.player.id
    world.update_data(me, forge_mastery={"sword": 1.5})
    assert "mastery" in " | ".join(check_crafts(world))
```

- [ ] **Step 2: Write the new modules**

`systems/forging.py`:
```python
"""Forging and refining (phase 5d spec 3): gear from materials, a grade more on what one holds, and masterworks.

Forging takes a slot, a form and one to three materials: the grade is the materials' mean, rounded down, a grade
more for a master of the form, at most divine. One roll on the form's mastery, strength and the forging level; a
success makes the item and teaches the hand. Refining raises a held piece one grade with a better material, on a
harder roll. A weapon of the treasure grade the player forged may be named once: it becomes a famous weapon.
"""

import math

import systems.famous as FW
import systems.gear as gear
import systems.materials as M
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.body import add_injury
from world.events import Event, effect, listen
from world.seed import rng_for

MIN_MATERIALS, MAX_MATERIALS = 1, 3
FIRST_MASTERY, MASTERY_STEP, MASTER_AT = 0.1, 0.05, 0.8
BOUNDS = (0.1, 0.95)
BURN_SHARE = 0.1           # the worst tenth of failures burns the smith
REFINE_PENALTY, REFINE_CRACK = 0.2, 0.1
MASTERWORK_GRADE = 3
WATCHES = 4                # a day at the forge
FORMS = {"weapon": gear.WEAPON_FORMS, "armour": gear.ARMOURS}


def mastery(world, person: int, form: str) -> float | None:
    return (world.entity(person).data.get("forge_mastery") or {}).get(form)


def level(world, person: int) -> int:
    return int(math.floor(math.sqrt(world.entity(person).data.get("forge_xp", 0) / 10)))


def chance(world, person: int, form: str) -> float:
    strength = load_body(world, person).physique.get("strength", 10)
    raw = 0.35 + 0.4 * (mastery(world, person, form) or FIRST_MASTERY) + 0.03 * (strength - 10) \
        + 0.05 * level(world, person)
    return max(BOUNDS[0], min(BOUNDS[1], raw))


def _learn(world, person: int, form: str, grade: int) -> None:
    masteries = dict(world.entity(person).data.get("forge_mastery") or {})
    masteries[form] = round(min(1.0, (masteries.get(form) or FIRST_MASTERY) + MASTERY_STEP), 3)
    world.update_data(person, forge_mastery=masteries,
                      forge_xp=world.entity(person).data.get("forge_xp", 0) + grade + 1)


def _burn(world, person: int) -> None:
    body = load_body(world, person)
    add_injury(body, "right arm", "burn", 2, world.time, "a forge's fire")
    save_body(world, person, body)


def _materials_block(world, person: int, items) -> str | None:
    if not MIN_MATERIALS <= len(items) <= MAX_MATERIALS or len(set(items)) != len(items):
        return f"Put {MIN_MATERIALS} to {MAX_MATERIALS} materials on the anvil."
    owned = set(world.targets(person, "owns"))
    if any(i not in owned or M.material_info(world.entity(i)) is None for i in items):
        return "You have no such materials."
    return None


# --- forging -------------------------------------------------------------------------------------------------

def grade_of(world, person: int, form: str, items) -> int:
    grades = [M.material_info(world.entity(i))[1] for i in items]
    bonus = 1 if (mastery(world, person, form) or 0.0) >= MASTER_AT else 0
    return min(4, sum(grades) // len(grades) + bonus)


def forge_block(world, person: int, place, slot: str, form: str, items) -> str | None:
    if form not in FORMS.get(slot, ()):
        return "Nothing of that shape is forged."
    return _materials_block(world, person, items) or M.forge_block(world, person, place)


def forge_events(world, person: int, place, slot: str, form: str, items) -> list[Event]:
    odds = chance(world, person, form)
    roll = rng_for(world.world_seed, f"forge:{person}:{world.time}").random()
    return [Event("forged", (person,), place, {
        "slot": slot, "form": form, "materials": list(items), "grade": grade_of(world, person, form, items),
        "success": roll < odds, "burned": roll > 1 - (1 - odds) * BURN_SHARE, "rent": M.rent(world, person, place)})]


@effect("forged")
def _forged(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["rent"])
    M.spend(world, person, d["materials"])
    from systems.time import advance
    advance(world, WATCHES)
    if d["success"]:
        item = gear.make_item(world, d["slot"], d["form"], d["grade"], person, "forged", maker=person,
                              forged_by=person)
        world.update_data(person, last_forged=item)
        _learn(world, person, d["form"], d["grade"])
    elif d["burned"]:
        _burn(world, person)


# --- refining -------------------------------------------------------------------------------------------------

def refine_block(world, person: int, place, item_id, material_id) -> str | None:
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item.kind != "gear" or item_id not in world.targets(person, "owns"):
        return "You hold no such piece."
    if item.data.get("broken"):
        return "A broken piece is past refining."
    if item.data["grade"] >= 4:
        return "Nothing is finer than divine."
    why = _materials_block(world, person, [material_id])
    if why:
        return why
    if M.material_info(world.entity(material_id))[1] < item.data["grade"] + 1:
        return "Only a finer material lifts a piece a grade."
    return M.forge_block(world, person, place)


def refine_events(world, person: int, place, item_id: int, material_id: int) -> list[Event]:
    item = world.entity(item_id)
    odds = max(BOUNDS[0], chance(world, person, item.data["form"]) - REFINE_PENALTY)
    roll = rng_for(world.world_seed, f"refine_gear:{person}:{item_id}:{world.time}").random()
    return [Event("gear_refined", (person,), place, {
        "item": item_id, "material": material_id, "success": roll < odds, "grade": item.data["grade"] + 1,
        "cracked": roll > 1 - (1 - odds) * REFINE_CRACK, "rent": M.rent(world, person, place)})]


@effect("gear_refined")
def _refined(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["rent"])
    M.spend(world, person, [d["material"]])
    from systems.time import advance
    advance(world, WATCHES)
    item = world.entity(d["item"])
    if d["success"]:
        world.update_data(item.id, grade=d["grade"])
        if not item.data.get("famous"):  # a plain piece is called by its grade; a famous one keeps its name
            world.rename(item.id, gear.gear_name(item.data["slot"], item.data["form"], d["grade"]))
        _learn(world, person, item.data["form"], d["grade"])
    elif d["cracked"]:
        world.update_data(item.id, broken=True)


# --- masterworks ------------------------------------------------------------------------------------------------

def masterwork_block(world, person: int, item_id) -> str | None:
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item.kind != "gear" or item_id not in world.targets(person, "owns"):
        return "You hold no such piece."
    if item.data["slot"] != "weapon" or item.data.get("forged_by") != person:
        return "Only a weapon of your own forging can be named by you."
    if item.data.get("famous"):
        return "It has a name already."
    if item.data["grade"] < MASTERWORK_GRADE or item.data.get("broken"):
        return "Only a treasure is worth a name."
    return None


def names_for(world, item_id: int) -> list[str]:
    """Three names the smith might give their masterwork, none a famous weapon's already (seeded)."""
    item = world.entity(item_id)
    used = {world.entity(i).name for i in FW.famous_weapons(world)}
    rng = rng_for(world.world_seed, f"masterwork:{item_id}")
    out: list[str] = []
    for _ in range(40):
        name = f"the {rng.choice(FW.NAMES)} {FW.FORM_WORDS[item.data['form']]}"
        if name not in used and name not in out:
            out.append(name)
        if len(out) == 3:
            break
    return out


def masterwork_events(world, person: int, item_id: int, name: str, place) -> list[Event]:
    return [Event("masterwork_named", (person,), place, {"item": item_id, "name": name})]


@effect("masterwork_named")
def _named(world, event) -> None:
    person, d = event.actors[0], event.data
    world.rename(d["item"], d["name"])
    world.update_data(d["item"], famous=True)
    world.set_meta("famous_weapons", FW.famous_weapons(world) + [d["item"]])


@listen("masterwork_named")
def _legend(world, event, event_id: int) -> None:
    person, item = event.actors[0], event.data["item"]
    variant = make_variant("blade_legend", item, person, place=place_name(world, event.place))
    variant.update(legend=f"forged by {world.entity(person).name}")
    record_fact(world, item, "blade_legend", person, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_forging.py`
Expected: `3 failed, 6 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5d_task2.py`:
```python
"""Phase 5d, Task 2: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('world/db.py', r'''    # --- relations --------------------------------------------------------''', r'''    def rename(self, entity_id: int, name: str) -> None:
        """A new name for an entity (phase 5d: a refined piece, a named masterwork)."""
        current = self.entity(entity_id)
        if current is None:
            raise KeyError(entity_id)
        self._conn.execute("update entities set name = ? where id = ?", (name, entity_id))
        self._remember(replace(current, name=name))

    # --- relations --------------------------------------------------------''')
edit('systems/world_clock.py', r'''import systems.materials  # noqa: E402,F401  phase 5d: materials and the forge
''', r'''import systems.materials  # noqa: E402,F401  phase 5d: materials and the forge
import systems.forging  # noqa: E402,F401  phase 5d: forging, refining and masterworks
''')
edit('debug/invariants.py', r'''            out.append(f"{item.name} (#{item.id}) is no material of the table")
    return out''', r'''            out.append(f"{item.name} (#{item.id}) is no material of the table")
    for person in world.entities_after("person", "forge_mastery", 0):
        if any(not 0 <= m <= 1 for m in person.data["forge_mastery"].values()):
            out.append(f"{person.name} (#{person.id}) has a forging mastery out of 0-1")
    famous = set(world.get_meta("famous_weapons") or [])
    for item in world.entities("gear"):
        if item.data.get("forged_by") is not None and item.data.get("famous") and item.id not in famous:
            out.append(f"{item.name} (#{item.id}) is a named masterwork missing from the famous index")
    return out''')
print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5d_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_forging.py`
Expected: `9 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1396 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: forging - gear from materials, a grade more on what one holds, and masterworks named into legend"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 3: Formation patterns, flags and laying

Patterns are a table (`systems/data/formations.toml`): two sect defences, three battle arrays, two wards. A person knows one through `knows_formation` (its value the mastery) and gains a formation level. Manuals teach them; flags are one item that counts them. Laying spends the pattern's flags on one roll; what is laid lives on the town until the next dawn, a month, a season or a year. A sect's defences are laid only at a seat of one's own sect, the Heavenly Gate only at one's own sect's (ruling 5). 4f's formation trials are easier for a formation master, and one passed now and then teaches a pattern.

**Files:**
- Create: `systems/data/formations.toml`
- Create: `systems/formations.py`
- Create: `tests/test_formations.py`
- Modify (by `.patches/5d_task3.py`): `systems/chambers.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: 4f's `chambers.trial_events` and `trial_attempted`; 3b's memberships; 5b's craft shape.
- Produces:
  - `FM` (systems/formations.py): `PATTERNS`, `FIRST_MASTERY`, `MASTERY_STEP`, `BOUNDS`, `MANUAL_PRICE`, `FLAG_PRICE`, `TRIAL_LEVEL`, `TRIAL_TEACHES`, `WATCHES`; `pattern_entity(world, key)`, `known(world, person)`, `mastery(world, person, key)`, `learn(world, person, key, value)`, `level(world, person)`, `manual_price(key)`, `make_manual(world, owner, key, how)`, `manuals_of(world, person)`, `study_block(world, person, item_id)`, `study_events(world, person, item_id, place)`, `flags_item(world, person)`, `flags_of(world, person)`, `add_flags(world, person, count)`, `spend_flags(world, person, count)`, `chance(world, person, key)`, `until(world, key)`, `laid(world, place, key, owner)`, `strength(world, place, key, owner)`, `site_block(world, person, key, place)`, `lay_block(world, person, key, place)`, `lay_events(world, person, key, place)`, `place_formation(world, place, key, owner, strength_)`, `trial_bonus(world, person)`; events `formation_laid`, `formation_studied`.
  - a formation master's bonus in 4f's formation trial; patterns, flags and laid formations in `check_crafts`.

- [ ] **Step 1: Write the tests**

`tests/test_formations.py`:
```python
import pytest

import systems.encounters as encounters
import systems.formations as FM
from debug.invariants import check_crafts
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.body import WATCHES_PER_DAY
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


def test_every_pattern_has_a_use_flags_and_a_difficulty():
    for key, row in FM.PATTERNS.items():
        assert row["use"] in ("defence", "battle", "ward") and row["flags"] >= 1 and 1 <= row["difficulty"] <= 3, key
        assert (row["days"] == 0) == (row["use"] == "battle"), key


def test_a_manual_studied_teaches_its_pattern_and_is_kept(game):
    world, me = game.world, game.player.id
    manual = FM.make_manual(world, me, "confusion", "bought")
    assert FM.study_block(world, me, manual) is None
    commit(world, FM.study_events(world, me, manual, game.place.id))
    assert FM.mastery(world, me, "confusion") == FM.FIRST_MASTERY and manual in world.targets(me, "owns")
    assert "already" in FM.study_block(world, me, manual)
    assert FM.manual_price("killing") == FM.MANUAL_PRICE * 9


def test_flags_are_one_item_that_counts_them(game):
    world, me = game.world, game.player.id
    FM.add_flags(world, me, 5)
    FM.add_flags(world, me, 3)
    assert FM.flags_of(world, me) == 8 and len([i for i in world.targets(me, "owns")
                                                 if world.entity(i).kind == "flags"]) == 1
    FM.spend_flags(world, me, 8)
    assert FM.flags_of(world, me) == 0 and check_crafts(world) == []


def test_a_battle_array_is_laid_until_the_next_dawn_and_teaches_the_hand(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    FM.learn(world, me, "binding")
    FM.add_flags(world, me, 10)
    assert FM.lay_block(world, me, "binding", town) is None
    monkeypatch.setattr(FM, "BOUNDS", (1.0, 1.0))
    commit(world, FM.lay_events(world, me, "binding", town))
    [laid] = FM.laid(world, town)
    assert laid["pattern"] == "binding" and laid["owner"] == me and laid["until"] % WATCHES_PER_DAY == 0
    assert laid["strength"] == pytest.approx(0.5 + FM.FIRST_MASTERY / 2)
    assert FM.flags_of(world, me) == 10 - FM.PATTERNS["binding"]["flags"]
    assert FM.mastery(world, me, "binding") == pytest.approx(FM.FIRST_MASTERY + FM.MASTERY_STEP)
    assert world.entity(me).data["formation_xp"] == 3
    world.set_time(laid["until"])
    assert FM.laid(world, town) == [] and FM.strength(world, town, "binding") == 0.0


def test_a_failed_laying_spends_the_flags(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    FM.learn(world, me, "seclusion")
    FM.add_flags(world, me, 3)
    monkeypatch.setattr(FM, "BOUNDS", (0.0, 0.0))
    commit(world, FM.lay_events(world, me, "seclusion", town))
    assert FM.laid(world, town) == [] and FM.flags_of(world, me) == 0


def test_a_harder_pattern_is_harder_to_lay_and_a_master_lays_it_better(game):
    world, me = game.world, game.player.id
    FM.learn(world, me, "confusion")
    FM.learn(world, me, "killing")
    assert FM.chance(world, me, "killing") < FM.chance(world, me, "confusion")
    before = FM.chance(world, me, "killing")
    world.update_data(me, formation_xp=90)
    assert FM.level(world, me) == 3 and FM.chance(world, me, "killing") == pytest.approx(before + 0.15)


def test_a_sects_defences_are_laid_at_the_seat_of_ones_own_sect(game):
    world, me, town = game.world, game.player.id, game.place.id
    FM.learn(world, me, "veiled_garden")
    FM.learn(world, me, "heavenly_gate")
    FM.add_flags(world, me, 20)
    assert "own sect" in FM.lay_block(world, me, "veiled_garden", town)
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.relate(me, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 0, "status": "member",
                                            "secret": False})
    assert FM.lay_block(world, me, "veiled_garden", seat) is None
    assert "your own sect's gate" in FM.lay_block(world, me, "heavenly_gate", seat)


def test_a_formation_master_reads_an_ancient_array_better_and_it_may_teach_them(game, monkeypatch):
    world, me = game.world, game.player.id
    world.update_data(me, formation_xp=40)
    assert FM.trial_bonus(world, me) == pytest.approx(2 * FM.TRIAL_LEVEL)
    monkeypatch.setattr(FM, "TRIAL_TEACHES", 1.0)
    realm = world.add_entity("secret_realm", "a test realm", {"floors": [[{"kind": "trial", "state": "untouched",
                                                                            "contents": {"trial": "formation"}}]]})
    FM._array_teaches(world, Event("trial_attempted", (me,), realm, {"realm": realm, "floor": 1, "chamber": 0,
                                                                      "trial": "formation", "passed": True}), 0)
    assert len(FM.known(world, me)) == 1


def test_the_rules_hold_a_laid_formation_to_a_pattern_and_a_person(game):
    world, town = game.world, game.place.id
    world.update_data(town, formations=[{"pattern": "nothing", "owner": 999999, "until": 10 ** 9, "strength": 2}])
    assert "malformed" in " | ".join(check_crafts(world))
```

- [ ] **Step 2: Write the new modules**

`systems/data/formations.toml`:
```toml
# Formation patterns (phase 5d spec 4-5): the same in every world.
# use: defence (laid at a sect's seat), battle (a town, until the next dawn), ward (a town, for `days`);
# flags: the flags spent to lay it; difficulty 1-3 (it weighs the roll and the manual's price);
# days: how long it holds (0: until the next dawn).

[heavenly_gate]
name = "the Heavenly Gate array"
use = "defence"
flags = 8
difficulty = 3
days = 360

[veiled_garden]
name = "the Veiled Garden ward"
use = "defence"
flags = 6
difficulty = 2
days = 360

[confusion]
name = "the Confusion array"
use = "battle"
flags = 3
difficulty = 1
days = 0

[binding]
name = "the Binding array"
use = "battle"
flags = 4
difficulty = 2
days = 0

[killing]
name = "the Killing array"
use = "battle"
flags = 5
difficulty = 3
days = 0

[concealment]
name = "the Concealment array"
use = "ward"
flags = 4
difficulty = 2
days = 30

[seclusion]
name = "the Seclusion ward"
use = "ward"
flags = 3
difficulty = 1
days = 90
```

`systems/formations.py`:
```python
"""Formations (phase 5d spec 4): patterns learnt and mastered, laid with flags where one stands.

A pattern (`systems/data/formations.toml`) is known through a `knows_formation` relation to the world's pattern
entity (`formation:{key}`), whose value is its mastery; the formation level grows with what is laid. Patterns come
from manuals (items), and now and then from passing an ancient array in a secret realm. Flags are one item that
counts them. Laying spends the flags on one roll; what is laid lives on the place (`formations`), until the next
dawn for a battle array, a month for concealment, a season for a seclusion ward, a year for a sect's defences.
What each does is `systems/arrays.py`.
"""

import math
import tomllib
from pathlib import Path

from systems.bodies import load_body
from world.body import WATCHES_PER_DAY
from world.events import Event, effect, listen
from world.seed import rng_for

PATTERNS = tomllib.loads((Path(__file__).parent / "data" / "formations.toml").read_text(encoding="utf-8"))
FIRST_MASTERY, MASTERY_STEP = 0.1, 0.05
BOUNDS = (0.1, 0.95)
MANUAL_PRICE = 100         # silver x difficulty squared
FLAG_PRICE = 20
TRIAL_LEVEL = 0.05         # a secret realm's formation trial is easier by this a formation level
TRIAL_TEACHES = 0.25       # an ancient array passed now and then teaches a pattern
WATCHES = 2                # laying a formation takes half a day


# --- patterns as knowledge ------------------------------------------------------------------------------------

def pattern_entity(world, key: str) -> int:
    path = f"formation:{key}"
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    return world.add_entity("formation", PATTERNS[key]["name"], {"key": key, **PATTERNS[key]}, path)


def known(world, person: int) -> dict[str, float]:
    """{pattern key: mastery} for what this person knows."""
    return {world.entity(p).data["key"]: value for p, value, _ in world.relations_from(person, "knows_formation")}


def mastery(world, person: int, key: str) -> float | None:
    return known(world, person).get(key)


def learn(world, person: int, key: str, value: float = FIRST_MASTERY) -> None:
    if mastery(world, person, key) is None:
        world.relate(person, pattern_entity(world, key), "knows_formation", value)


def level(world, person: int) -> int:
    return int(math.floor(math.sqrt(world.entity(person).data.get("formation_xp", 0) / 10)))


# --- manuals -----------------------------------------------------------------------------------------------------

def manual_price(key: str) -> int:
    return MANUAL_PRICE * PATTERNS[key]["difficulty"] ** 2


def make_manual(world, owner: int, key: str, how: str) -> int:
    item = world.add_entity("formation_manual", f"a manual of {PATTERNS[key]['name']}", {"pattern": key, "how": how})
    world.relate(owner, item, "owns")
    return item


def manuals_of(world, person: int) -> list:
    return [e for e in (world.entity(i) for i in world.targets(person, "owns"))
            if e is not None and e.kind == "formation_manual"]


def study_block(world, person: int, item_id) -> str | None:
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item.kind != "formation_manual" or item_id not in world.targets(person, "owns"):
        return "You have no such manual."
    if mastery(world, person, item.data["pattern"]) is not None:
        return "You know that pattern already."
    return None


def study_events(world, person: int, item_id: int, place) -> list[Event]:
    return [Event("formation_studied", (person,), place, {"item": item_id,
                                                          "pattern": world.entity(item_id).data["pattern"]})]


@effect("formation_studied")
def _studied(world, event) -> None:
    learn(world, event.actors[0], event.data["pattern"])


# --- flags -------------------------------------------------------------------------------------------------------

def flags_item(world, person: int):
    return next((e for e in (world.entity(i) for i in world.targets(person, "owns"))
                 if e is not None and e.kind == "flags"), None)


def flags_of(world, person: int) -> int:
    found = flags_item(world, person)
    return found.data["count"] if found is not None else 0


def add_flags(world, person: int, count: int) -> None:
    found = flags_item(world, person)
    if found is not None:
        world.update_data(found.id, count=found.data["count"] + count)
        return
    item = world.add_entity("flags", "formation flags", {"count": count})
    world.relate(person, item, "owns")


def spend_flags(world, person: int, count: int) -> None:
    found = flags_item(world, person)
    left = found.data["count"] - count
    if left > 0:
        world.update_data(found.id, count=left)
    else:
        world.unrelate(person, "owns", found.id)
        world.update_data(found.id, count=0, used=True)


# --- laying ------------------------------------------------------------------------------------------------------

def chance(world, person: int, key: str) -> float:
    wit = load_body(world, person).physique.get("comprehension", 10)
    raw = 0.3 + 0.4 * (mastery(world, person, key) or 0.0) + 0.03 * (wit - 10) + 0.05 * level(world, person) \
        - 0.1 * PATTERNS[key]["difficulty"]
    return max(BOUNDS[0], min(BOUNDS[1], raw))


def until(world, key: str) -> int:
    days = PATTERNS[key]["days"]
    if days:
        return world.time + days * WATCHES_PER_DAY
    return (world.time // WATCHES_PER_DAY + 1) * WATCHES_PER_DAY  # the next dawn


def laid(world, place, key: str | None = None, owner: int | None = None) -> list[dict]:
    """The formations holding at a place now (read, never written)."""
    entity = world.entity(place) if place is not None else None
    if entity is None:
        return []
    return [f for f in entity.data.get("formations") or [] if f["until"] > world.time
            and (key is None or f["pattern"] == key) and (owner is None or f["owner"] == owner)]


def strength(world, place, key: str, owner: int | None = None) -> float:
    """The strongest of this pattern holding here (for this owner), or 0."""
    return max((f["strength"] for f in laid(world, place, key, owner)), default=0.0)


def site_block(world, person: int, key: str, place) -> str | None:
    """Where a pattern may be laid: a sect's defences at a seat of the layer's sect; anything else in a town."""
    entity = world.entity(place)
    if entity is None or entity.kind != "town":
        return "Formations are laid in a town."
    if PATTERNS[key]["use"] == "defence":
        from systems import factions as F
        mine = [f for f, _, d in F.memberships(world, person) if d.get("status", "member") == "member"]
        if not any(world.entity(f).data.get("seat") == place for f in mine):
            return "A sect's defences are laid at the seat of your own sect."
        if key == "heavenly_gate" and not any(world.entity(f).data.get("type") == "player_sect"
                                              and world.entity(f).data.get("seat") == place for f in mine):
            return "Only your own sect's gate takes the Heavenly Gate array."
    return None


def lay_block(world, person: int, key: str, place) -> str | None:
    if key not in PATTERNS or mastery(world, person, key) is None:
        return "You do not know that pattern."
    why = site_block(world, person, key, place)
    if why:
        return why
    if flags_of(world, person) < PATTERNS[key]["flags"]:
        return f"It takes {PATTERNS[key]['flags']} flags."
    return None


def lay_events(world, person: int, key: str, place) -> list[Event]:
    roll = rng_for(world.world_seed, f"lay:{person}:{key}:{world.time}").random()
    skill = mastery(world, person, key)
    return [Event("formation_laid", (person,), place, {
        "pattern": key, "success": roll < chance(world, person, key), "flags": PATTERNS[key]["flags"],
        "strength": round(0.5 + skill / 2, 3), "until": until(world, key)})]


@effect("formation_laid")
def _laid(world, event) -> None:
    person, place, d = event.actors[0], event.place, event.data
    spend_flags(world, person, d["flags"])
    from systems.time import advance
    advance(world, WATCHES)
    if not d["success"]:
        return
    keep = [f for f in laid(world, place) if not (f["pattern"] == d["pattern"] and f["owner"] == person)]
    world.update_data(place, formations=keep + [{"pattern": d["pattern"], "owner": person, "until": d["until"],
                                                  "strength": d["strength"]}])
    world.relate(person, pattern_entity(world, d["pattern"]), "knows_formation",
                 round(min(1.0, mastery(world, person, d["pattern"]) + MASTERY_STEP), 3))
    world.update_data(person, formation_xp=world.entity(person).data.get("formation_xp", 0)
                      + PATTERNS[d["pattern"]]["difficulty"] + 1)


def place_formation(world, place: int, key: str, owner: int, strength_: float) -> None:
    """A formation laid by another's hand (a master's commission, a sect's own ward): no roll, no flags."""
    keep = [f for f in laid(world, place) if not (f["pattern"] == key and f["owner"] == owner)]
    world.update_data(place, formations=keep + [{"pattern": key, "owner": owner, "until": until(world, key),
                                                  "strength": round(strength_, 3)}])


# --- the ancient arrays of secret realms (4f) ---------------------------------------------------------------------

def trial_bonus(world, person: int) -> float:
    return TRIAL_LEVEL * level(world, person)


@listen("trial_attempted")
def _array_teaches(world, event, event_id: int) -> None:
    """An ancient array passed now and then teaches one of its patterns (spec 4)."""
    d, person = event.data, event.actors[0]
    if d.get("trial") != "formation" or not d.get("passed"):
        return
    rng = rng_for(world.world_seed, f"array_teaches:{d['realm']}:{d['floor']}:{d['chamber']}:{person}")
    unknown = sorted(k for k in PATTERNS if mastery(world, person, k) is None)
    if unknown and rng.random() < TRIAL_TEACHES:
        learn(world, person, rng.choice(unknown))
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_formations.py`
Expected: `1 failed, 8 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5d_task3.py`:
```python
"""Phase 5d, Task 3: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/chambers.py', r'''        chance = _clamp(FORMATION_BASE + FORMATION_PER_COMPREHENSION * body.physique["comprehension"], FORMATION_BOUNDS)''', r'''        from systems.formations import trial_bonus  # phase 5d: a formation master reads an ancient array better
        chance = _clamp(FORMATION_BASE + FORMATION_PER_COMPREHENSION * body.physique["comprehension"]
                        + trial_bonus(world, player), FORMATION_BOUNDS)''')
edit('systems/world_clock.py', r'''import systems.forging  # noqa: E402,F401  phase 5d: forging, refining and masterworks
''', r'''import systems.forging  # noqa: E402,F401  phase 5d: forging, refining and masterworks
import systems.formations  # noqa: E402,F401  phase 5d: formation patterns, flags and laying
''')
edit('debug/invariants.py', r'''            out.append(f"{item.name} (#{item.id}) is a named masterwork missing from the famous index")
    return out''', r'''            out.append(f"{item.name} (#{item.id}) is a named masterwork missing from the famous index")
    from systems.formations import PATTERNS
    for person, value in world._conn.execute("select a, value from relations where kind = 'knows_formation'"):
        if not 0 <= value <= 1:
            out.append(f"#{person} knows a formation at mastery {value}")
    for flags in world.entities("flags"):
        if not flags.data.get("used") and flags.data.get("count", 0) < 1:
            out.append(f"{flags.name} (#{flags.id}) holds no flags")
    for place in world.entities_after("town", "formations", 0):
        for f in place.data["formations"]:
            owner = world.entity(f.get("owner") or 0)
            if f.get("pattern") not in PATTERNS or owner is None or not 0 <= f.get("strength", -1) <= 1:
                out.append(f"a formation laid in {place.name} is malformed: {f}")
    return out''')
print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5d_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_formations.py`
Expected: `9 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1405 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: formations - patterns learnt from manuals and ancient arrays, flags, and laying"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 4: What formations do

Each formation is a small factor read where its rule already lives (ruling 6): the Heavenly Gate halves 3c's gate chance at strength 1 and lifts the sect's own who stand there; the Veiled Garden, or a great sect's own seeded ward, cuts 5c's theft chance; the Killing array lifts its owner in any fight in the town, the Confusion array weakens everyone else, the Binding array holds every runner but its owner; Concealment hides its owner from avengers, rivals and hunters; the Seclusion ward speeds cultivation and halves deviation. 5c's theft test now weighs the realms alone.

**Files:**
- Create: `systems/arrays.py`
- Create: `tests/test_arrays.py`
- Modify (by `.patches/5d_task4.py`): `systems/sect_seasons.py`, `systems/hall_theft.py`, `systems/duel.py`, `systems/encounters.py`, `systems/cultivation.py`, `systems/world_clock.py`, `tests/test_hall_theft.py`

**Interfaces:**
- Consumes: Task 3's `formations.laid`, `strength`; 3c's gate; 5c's `hall_theft.chance`; 2b's `fighter_for`, fleeing, `challenge_from`; 2a's `meditate_events`.
- Produces:
  - `AR` (systems/arrays.py): `GATE_CUT`, `GATE_FIGHT`, `WARD_CUT`, `BATTLE`, `SECLUSION_GAIN`, `SECLUSION_DEVIATION`; `gate_factor(world, seat)`, `npc_ward(world, faction)`, `theft_cut(world, faction)`, `fight_factor(world, person)`, `held(world, runner)`, `concealed(world, person, place)`, `cultivation_factor(world, person, place)`, `deviation_factor(world, person, place)`.
  - `duel.fight_factor(world, person)`; the gate, theft, fleeing, challenge and meditation hooks.

- [ ] **Step 1: Write the tests**

`tests/test_arrays.py`:
```python
import pytest

import systems.arrays as AR
import systems.encounters as encounters
import systems.formations as FM
import systems.hall_theft as T
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.duel import fighter_for


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
    base = {"occupation": "tea seller", "traits": ["proud", "hot-tempered"], "realm": "second-rate", "age": 30,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:arrays:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def lay(game, key, owner=None, s=1.0, place=None):
    FM.place_formation(game.world, place or game.place.id, key, owner or game.player.id, s)


def test_a_killing_array_lifts_its_owner_and_a_confusion_array_weakens_everyone_else(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    mine, theirs = fighter_for(world, me, None).realm_mult, fighter_for(world, foe, None).realm_mult
    lay(game, "killing")
    assert fighter_for(world, me, None).realm_mult == pytest.approx(mine * (1 + AR.BATTLE))
    lay(game, "confusion")
    assert fighter_for(world, foe, None).realm_mult == pytest.approx(theirs * (1 - AR.BATTLE))
    assert fighter_for(world, me, None).realm_mult == pytest.approx(mine * (1 + AR.BATTLE))


def test_a_binding_array_holds_everyone_but_its_owner(game):
    world, me = game.world, game.player.id
    foe = someone(game, "runner")
    lay(game, "binding", owner=foe)
    assert AR.held(world, me) and not AR.held(world, foe)
    assert not encounters.flee_succeeds(world, me, foe)


def test_an_array_holds_until_the_next_dawn(game):
    world, me = game.world, game.player.id
    FM.learn(world, me, "killing")
    lay(game, "killing")
    [laid] = FM.laid(world, game.place.id)
    world.set_time(laid["until"])
    assert AR.fight_factor(world, me) == 1.0


def test_one_hidden_by_their_own_concealment_is_not_called_out(game):
    world, me = game.world, game.player.id
    foe = someone(game, "avenger")
    assert not AR.concealed(world, me, game.place.id)
    lay(game, "concealment")
    assert AR.concealed(world, me, game.place.id)
    assert encounters.challenge_from(world, me, game.place.id) is None
    other = someone(game, "other")
    assert not AR.concealed(world, other, game.place.id)  # it hides only the one who laid it


def test_a_seclusion_ward_speeds_cultivation_and_halves_deviation(game):
    import systems.cultivation as cultivation
    world, me, town = game.world, game.player.id, game.place.id
    before = cultivation.meditate_events(world, me, town, 7)[0].data["energy_gained"]
    lay(game, "seclusion", s=1.0)
    after = cultivation.meditate_events(world, me, town, 7)[0].data["energy_gained"]
    assert after == pytest.approx(before * (1 + AR.SECLUSION_GAIN), rel=0.01)
    assert AR.deviation_factor(world, me, town) == AR.SECLUSION_DEVIATION


def test_a_veiled_garden_or_a_great_sects_own_ward_cuts_a_thiefs_chance(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    own = AR.npc_ward(world, sect)
    assert 0 <= own <= 1 and AR.npc_ward(world, sect) == own
    world.update_data(me, realm="life-and-death")
    before = T.chance(world, me, sect)
    lay(game, "veiled_garden", s=1.0, place=seat)
    assert AR.theft_cut(world, sect) == pytest.approx(AR.WARD_CUT)
    assert T.chance(world, me, sect) <= before


def test_the_heavenly_gate_keeps_challengers_off_and_lifts_the_sects_own(game):
    world, me, town = game.world, game.player.id, game.place.id
    assert AR.gate_factor(world, town) == 1.0
    lay(game, "heavenly_gate", s=1.0)
    assert AR.gate_factor(world, town) == pytest.approx(1 - AR.GATE_CUT)
    sect = world.add_entity("faction", "Pine Cloud Hall", {"type": "player_sect", "tier": "minor", "seat": town,
                                                           "ranks": list(F.LADDERS["orthodox_sect"])})
    disciple = someone(game, "disciple")
    world.relate(disciple, sect, "member_of", 0, {"role": "disciple", "status": "member"})
    stranger = someone(game, "stranger")
    assert AR.fight_factor(world, disciple) == pytest.approx(1 + AR.GATE_FIGHT)
    assert AR.fight_factor(world, stranger) == 1.0


def test_a_place_without_formations_reads_nothing_more(game):
    assert AR.fight_factor(game.world, game.player.id) == 1.0 and not AR.held(game.world, game.player.id)
```

- [ ] **Step 2: Write the new modules**

`systems/arrays.py`:
```python
"""What formations do (phase 5d spec 5): the gate and the garden of a sect, a fight inside an array, a hidden
hero, and a warded seclusion.

Each is a small factor read where the rule already lives: 3c's gate, 5c's theft, 2b's fighters and fleeing, 2b's
challengers and 3b's hunters, and 2a's meditation. Nothing here writes: a formation's strength is read from the
place it was laid (`formations.laid`).
"""

from systems import factions as F
from systems.formations import strength
from world.seed import rng_for

GATE_CUT, GATE_FIGHT = 0.5, 0.2       # the Heavenly Gate: fewer challengers, stronger defenders
WARD_CUT = 0.3                        # the Veiled Garden: a thief's chance, less this x strength
BATTLE = 0.2                          # confusion weakens foes, killing strengthens the owner, by this x strength
SECLUSION_GAIN, SECLUSION_DEVIATION = 0.2, 0.5


def _here(world, person: int):
    found = world.targets(person, "located_in")
    return found[0] if found else None


# --- a sect's defences (spec 5.1) ----------------------------------------------------------------------------

def gate_factor(world, seat: int) -> float:
    """How much of 3c's gate chance a Heavenly Gate array at the seat leaves."""
    return 1.0 - GATE_CUT * strength(world, seat, "heavenly_gate")


def npc_ward(world, faction: int) -> float:
    """A great sect's own seeded ward over its garden and hall, 0-1."""
    data = world.entity(faction).data
    if data.get("tier") != "great" or data.get("type") == "player_sect":
        return 0.0
    return round(rng_for(world.world_seed, f"ward:{faction}").random(), 2)


def theft_cut(world, faction: int) -> float:
    """What a sect's ward takes off a thief's chance (5c): the laid Veiled Garden, or its own."""
    seat = world.entity(faction).data.get("seat")
    laid = strength(world, seat, "veiled_garden") if seat is not None else 0.0
    return WARD_CUT * max(laid, npc_ward(world, faction))


# --- a fight inside an array (spec 5.2) ---------------------------------------------------------------------------

def _owners(world, place, key: str) -> list[tuple[int, float]]:
    from systems.formations import laid
    return [(f["owner"], f["strength"]) for f in laid(world, place, key)]


def fight_factor(world, person: int) -> float:
    """What the arrays where this person stands make of their strength: the owner's Killing array lifts them,
    another's Confusion array weakens them; a sect's own gate array lifts its defenders."""
    place = _here(world, person)
    entity = world.entity(place) if place is not None else None
    if entity is None or not entity.data.get("formations"):
        return 1.0  # most places hold none: nothing more is read
    factor = 1.0
    for owner, s in _owners(world, place, "killing"):
        if owner == person:
            factor *= 1 + BATTLE * s
    for owner, s in _owners(world, place, "confusion"):
        if owner != person:
            factor *= 1 - BATTLE * s
    gate = strength(world, place, "heavenly_gate")
    if gate and any(world.entity(f).data.get("seat") == place and d.get("status", "member") == "member"
                    for f, _, d in F.memberships(world, person)):
        factor *= 1 + GATE_FIGHT * gate
    return round(factor, 4)


def held(world, runner: int) -> bool:
    """Whether a Binding array here holds this runner fast: laid by anyone but them."""
    place = _here(world, runner)
    return any(owner != runner for owner, _ in _owners(world, place, "binding")) if place is not None else False


# --- concealment and seclusion (spec 5.3) --------------------------------------------------------------------------

def concealed(world, person: int, place) -> bool:
    """No avenger, rival or bounty hunter finds one hidden by their own Concealment array here."""
    return place is not None and strength(world, place, "concealment", owner=person) > 0


def cultivation_factor(world, person: int, place) -> float:
    return 1 + SECLUSION_GAIN * strength(world, place, "seclusion", owner=person)


def deviation_factor(world, person: int, place) -> float:
    return SECLUSION_DEVIATION if strength(world, place, "seclusion", owner=person) > 0 else 1.0
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_arrays.py`
Expected: `3 failed, 5 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5d_task4.py`:
```python
"""Phase 5d, Task 4: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/sect_seasons.py', r'''    gate_chance = (GATE_BASE + (GATE_HOSTILE if hostile else 0.0)) * (0.5 if "walls" in has else 1.0)''', r'''    from systems.arrays import gate_factor  # phase 5d: a Heavenly Gate array keeps challengers off
    gate_chance = (GATE_BASE + (GATE_HOSTILE if hostile else 0.0)) * (0.5 if "walls" in has else 1.0) \
        * gate_factor(world, seat)''')
edit('systems/hall_theft.py', r'''    realm = realm_index(world.entity(thief).data.get("realm", "mortal"))
    return max(BOUNDS[0], min(BOUNDS[1], BASE + PER_REALM * (realm - guard_of(world, faction)[1])))''', r'''    from systems.arrays import theft_cut  # phase 5d: a sect's ward over its garden and hall
    realm = realm_index(world.entity(thief).data.get("realm", "mortal"))
    return max(BOUNDS[0], min(BOUNDS[1], BASE + PER_REALM * (realm - guard_of(world, faction)[1])
                              - theft_cut(world, faction)))''')
edit('systems/duel.py', r'''        name=person.name, realm_mult=REALMS[body.realm].multiplier * _dark_boost(world, person_id),''', r'''        name=person.name, realm_mult=REALMS[body.realm].multiplier * _dark_boost(world, person_id)
        * fight_factor(world, person_id),  # phase 5d: the arrays where they stand''')
edit('systems/duel.py', r'''def fighter_for(world, person_id: int, technique_id: int | None) -> Fighter:''', r'''def fight_factor(world, person_id: int) -> float:
    from systems.arrays import fight_factor as factor  # the arrays come after the duel in the import graph
    return factor(world, person_id)


def fighter_for(world, person_id: int, technique_id: int | None) -> Fighter:''')
edit('systems/duel.py', r'''        data["fled"] = rng.random() < flee_chance(me, them, harm["player"])''', r'''        from systems.arrays import held  # phase 5d: a Binding array holds the runner fast
        data["fled"] = not held(world, d.player) and rng.random() < flee_chance(me, them, harm["player"])''')
edit('systems/encounters.py', r'''    rng = rng_for(world.world_seed, f"roadflee:{person}:{world.time}")
    return rng.random() < flee_chance(''', r'''    from systems.arrays import held  # phase 5d: a Binding array holds the runner fast
    if held(world, player):
        return False
    rng = rng_for(world.world_seed, f"roadflee:{person}:{world.time}")
    return rng.random() < flee_chance(''')
edit('systems/encounters.py', r'''    """Someone here who calls the player out: an avenger, a grudge-holder, or a proud rival."""
''', r'''    """Someone here who calls the player out: an avenger, a grudge-holder, or a proud rival."""
    from systems.arrays import concealed  # phase 5d: hidden by one's own Concealment array, no one finds you
    if concealed(world, player, place):
        return None
''')
edit('systems/cultivation.py', r'''    gained = realms.add_energy(trial, energy_rate(body, heart_data, days, world.time) * days
                               * W.factor(world, place, "cultivation"))  # a qi tide (phase 4d)
    deviation = _deviation_from(body, heart_data, days) if heart_data else 0.0''', r'''    from systems.arrays import cultivation_factor, deviation_factor  # phase 5d: a Seclusion ward
    gained = realms.add_energy(trial, energy_rate(body, heart_data, days, world.time) * days
                               * W.factor(world, place, "cultivation")  # a qi tide (phase 4d)
                               * cultivation_factor(world, pid, place))
    deviation = round(_deviation_from(body, heart_data, days) * deviation_factor(world, pid, place), 3) \
        if heart_data else 0.0''')
edit('systems/world_clock.py', r'''import systems.formations  # noqa: E402,F401  phase 5d: formation patterns, flags and laying
''', r'''import systems.formations  # noqa: E402,F401  phase 5d: formation patterns, flags and laying
import systems.arrays  # noqa: E402,F401  phase 5d: what formations do
''')
edit('tests/test_hall_theft.py', r"""def test_the_chance_weighs_the_thiefs_realm_against_the_guards(game):
    world, me = game.world, game.player.id""", r"""def test_the_chance_weighs_the_thiefs_realm_against_the_guards(game, monkeypatch):
    monkeypatch.setattr("systems.arrays.npc_ward", lambda world, faction: 0.0)  # phase 5d: the realms alone
    world, me = game.world, game.player.id""")
print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5d_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_arrays.py`
Expected: `8 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1413 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: what formations do - the gate and the garden, arrays to fight in, concealment and a warded seclusion"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 5: Smiths, formation masters and commissions

Blacksmiths and fortune tellers by trade (ruling 2) carry a seeded skill 1-5 that rises one season in ten (a lives agenda: one hash, no Random). A master smith lifts the town's stall a grade. A formation master sells flags and the manuals their skill reaches, and lays a pattern on commission at `0.5 + skill / 10`; a smith forges on commission, a grade below their skill, ready in ten days.

**Files:**
- Create: `systems/craft_world.py`
- Create: `tests/test_craft_world.py`
- Modify (by `.patches/5d_task5.py`): `systems/smithy.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Tasks 3's `formations`; 5a's `smithy.cap`, `smithy.price`, `gear`; 4a's lives agendas.
- Produces:
  - `CW` (systems/craft_world.py): `CRAFTS`, `SKILLS`, `RISE_CHANCE`, `MASTER_SMITH`, `FORGE_SHARE`, `FORGE_DAYS`, `LAY_PRICE`, `FLAG_LOT`; `crafter(world, person)`, `skill(world, person)`, `title(world, person)`, `season_events(world, person, n, rng)`, `town_smith(world, town)`, `stall_lift(world, town)`, `teaches(world, master)`, `manual_block(world, person, master, key)`, `manual_events(world, person, master, key, place)`, `flags_block(world, person, master)`, `flags_events(world, person, master, place)`, `lay_price(key)`, `lay_strength(world, master)`, `commission_lay_block(world, person, master, key, place)`, `commission_lay_events(world, person, master, key, place)`, `forge_grade(world, smith)`, `forge_price(world, smith, town, slot)`, `pending(world, person)`, `commission_forge_block(world, person, smith, slot, form, town)`, `commission_forge_events(world, person, smith, slot, form, town)`, `ready(world, person, smith)`, `collect_events(world, person, smith, place)`; events `commission_collected`, `craft_rose`, `flags_bought`, `forge_commissioned`, `formation_commissioned`, `manual_bought`.
  - a master smith's lift in `smithy.cap`; craft skills in `check_crafts`; `check_people` counts those where the dead fell (ruling 16).

- [ ] **Step 1: Write the tests**

`tests/test_craft_world.py`:
```python
import pytest

import systems.craft_world as CW
import systems.encounters as encounters
import systems.formations as FM
import systems.gear as gear
import systems.lives as lives
import systems.smithy as smithy
from debug.invariants import check_crafts
from engine.game import Game
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=20000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "mortal", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:craft:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_smiths_and_formation_masters_carry_a_seeded_skill(game):
    world = game.world
    smith, master, seller = (someone(game, "smith", occupation="blacksmith"),
                             someone(game, "master", occupation="fortune teller"), someone(game, "seller"))
    assert CW.SKILLS[0] <= CW.skill(world, smith) <= CW.SKILLS[1] and CW.skill(world, smith) == CW.skill(world, smith)
    assert CW.crafter(world, master) == "formation master" and CW.skill(world, seller) is None
    assert CW.title(world, smith).endswith(" smith")


def test_a_crafters_skill_rises_now_and_then_in_their_seasons(game, monkeypatch):
    world = game.world
    smith = someone(game, "riser", occupation="blacksmith", craft_skill=2)
    lives.lived_to(world, smith)
    monkeypatch.setattr(CW, "RISE_CHANCE", 1.0)
    world.set_time(world.time + 2 * lives.SEASON)
    lives.catch_up(world, smith)
    assert world.entity(smith).data["craft_skill"] == 4
    assert CW.season_events in lives.AGENDAS


def test_a_master_smith_lifts_the_towns_stall_a_grade(game):
    world, town = game.world, game.place.id
    base = smithy.cap(world, town)
    someone(game, "master smith", occupation="blacksmith", craft_skill=CW.MASTER_SMITH)
    assert smithy.cap(world, town) == min(4, base + 1)


def test_a_formation_master_sells_flags_and_the_manuals_their_skill_reaches(game):
    world, me, town = game.world, game.player.id, game.place.id
    novice = someone(game, "novice", occupation="fortune teller", craft_skill=1)
    grand = someone(game, "grand", occupation="fortune teller", craft_skill=5)
    assert all(FM.PATTERNS[k]["difficulty"] == 1 for k in CW.teaches(world, novice))
    assert set(CW.teaches(world, grand)) == set(FM.PATTERNS)
    commit(world, CW.flags_events(world, me, novice, town))
    assert FM.flags_of(world, me) == CW.FLAG_LOT
    assert CW.manual_block(world, me, novice, "killing") is not None
    commit(world, CW.manual_events(world, me, grand, "killing", town))
    assert FM.manuals_of(world, me)[0].data["pattern"] == "killing"
    assert silver_of(world, me) == 20000 - CW.FLAG_LOT * FM.FLAG_PRICE - FM.manual_price("killing")


def test_a_master_lays_a_pattern_on_commission_at_their_skills_strength(game):
    world, me, town = game.world, game.player.id, game.place.id
    master = someone(game, "layer", occupation="fortune teller", craft_skill=4)
    assert CW.commission_lay_block(world, me, master, "confusion", town) is None
    commit(world, CW.commission_lay_events(world, me, master, "confusion", town))
    [laid] = FM.laid(world, town)
    assert laid["owner"] == me and laid["strength"] == pytest.approx(0.9)
    assert "own sect" in CW.commission_lay_block(world, me, master, "veiled_garden", town)


def test_a_smith_forges_on_commission_ready_in_ten_days(game):
    world, me, town = game.world, game.player.id, game.place.id
    smith = someone(game, "forger", occupation="blacksmith", craft_skill=4)
    assert CW.commission_forge_block(world, me, smith, "weapon", "spear", town) is None
    price = CW.forge_price(world, smith, town, "weapon")
    commit(world, CW.commission_forge_events(world, me, smith, "weapon", "spear", town))
    assert silver_of(world, me) == 20000 - price and CW.ready(world, me, smith) is None
    assert "already" in CW.commission_forge_block(world, me, smith, "weapon", "spear", town)
    world.set_time(world.time + CW.FORGE_DAYS * 4)
    commit(world, CW.collect_events(world, me, smith, town))
    [spear] = [i for i in gear.gear_items(world, me) if i.data["form"] == "spear"]
    assert spear.data["grade"] == 3 and spear.data["maker"] == world.entity(smith).name
    assert CW.pending(world, me) == []


def test_the_rules_hold_a_craft_skill_to_1_5(game):
    world = game.world
    someone(game, "odd", occupation="blacksmith", craft_skill=9)
    assert "craft skill" in " | ".join(check_crafts(world))


def test_the_dead_have_seen_those_where_they_fell(game):
    """A death at a turn's end (5b's poison, 5c's worms) shows the scene it came in: its people are not strangers."""
    from debug.invariants import check_people
    from engine.actions import Turn
    from systems.mortality import death_events
    world, me = game.world, game.player.id
    stranger = someone(game, "witness")
    commit(world, death_events(world, me, "poisoned", None))
    turn = Turn([(f"Here: {world.entity(stranger).name} the tea seller.", "dim")], [], {}, "")
    assert check_people(game, turn) == []
```

- [ ] **Step 2: Write the new modules**

`systems/craft_world.py`:
```python
"""The world's crafts (phase 5d spec 6): smiths and formation masters, their skill, their wares, their commissions.

Blacksmiths and fortune tellers by trade carry a seeded skill 1-5 (`craft_skill` once written) that rises now and
then in their seasons (a lives agenda: one hash, no Random, no entities). A master smith lifts their town's stall.
A formation master sells flags and the manuals of patterns their skill reaches, and lays a pattern on commission;
a smith forges on commission, ready in ten days.
"""

import math

import systems.control  # noqa: F401  5c's agendas run before this one, whatever is imported first
import systems.formations as FM
import systems.gear as gear
import systems.lives as lives
from systems.purse import silver_of
from world.events import Event, effect
from world.gen.materialize import people_at
from world.seed import rng_for, seed_for

CRAFTS = {"blacksmith": "smith", "fortune teller": "formation master"}
SKILLS = (1, 5)
RISE_CHANCE = 0.1
MASTER_SMITH = 4           # a town's best smith of this skill lifts its stall a grade
FORGE_SHARE = 2            # a commission costs twice the stall's price
FORGE_DAYS = 10
LAY_PRICE = 100            # silver x difficulty
FLAG_LOT = 5


def crafter(world, person: int) -> str | None:
    entity = world.entity(person)
    return CRAFTS.get(entity.data.get("occupation")) if entity is not None and not entity.data.get("dead") else None


def skill(world, person: int) -> int | None:
    """A smith's or formation master's skill: written once it has risen, else seeded."""
    if crafter(world, person) is None:
        return None
    entity = world.entity(person)
    if "craft_skill" in entity.data:
        return entity.data["craft_skill"]
    return rng_for(world.world_seed, f"craft:{lives.key(entity)}").randint(*SKILLS)


def title(world, person: int) -> str:
    words = ("", "an apprentice", "a journeyman", "a skilled", "a master", "a grandmaster")
    return f"{words[skill(world, person)]} {crafter(world, person)}"


def season_events(world, person: int, n: int, rng) -> list[Event]:
    """A smith's or formation master's skill rises one step, one season in ten (its own hash, spec 6)."""
    entity = world.entity(person)
    if entity.data.get("occupation") not in CRAFTS:
        return []
    if seed_for(world.world_seed, f"craft_rise:{lives.key(entity)}:{n}") / 2 ** 64 >= RISE_CHANCE:
        return []
    now = skill(world, person)
    return [] if now >= SKILLS[1] else [Event("craft_rose", (person,), lives.home(world, person),
                                              {"skill": now + 1, "season": n})]


lives.AGENDAS.append(season_events)


@effect("craft_rose")
def _rose(world, event) -> None:
    world.update_data(event.actors[0], craft_skill=event.data["skill"])


def town_smith(world, town: int) -> int | None:
    """The best smith living in a town, if any."""
    smiths = [p.id for p in people_at(world, town) if crafter(world, p.id) == "smith"]
    return max(smiths, key=lambda p: (skill(world, p), -p)) if smiths else None


def stall_lift(world, town: int) -> int:
    """A master smith lifts the town's stall a grade (5a's cap)."""
    best = town_smith(world, town)
    return 1 if best is not None and skill(world, best) >= MASTER_SMITH else 0


# --- a formation master's wares -----------------------------------------------------------------------------

def teaches(world, master: int) -> list[str]:
    """The patterns a formation master knows and sells: those of a difficulty their skill reaches."""
    if crafter(world, master) != "formation master":
        return []
    top = math.ceil(skill(world, master) / 2)
    return sorted(k for k, row in FM.PATTERNS.items() if row["difficulty"] <= top)


def manual_block(world, person: int, master: int, key: str) -> str | None:
    if key not in teaches(world, master):
        return "They sell no such manual."
    if silver_of(world, person) < FM.manual_price(key):
        return f"The manual costs {FM.manual_price(key)} silver."
    return None


def manual_events(world, person: int, master: int, key: str, place) -> list[Event]:
    return [Event("manual_bought", (person, master), place, {"pattern": key, "price": FM.manual_price(key)})]


@effect("manual_bought")
def _manual(world, event) -> None:
    person, master = event.actors
    _pay(world, person, master, event.data["price"])
    FM.make_manual(world, person, event.data["pattern"], "bought")


def flags_block(world, person: int, master: int) -> str | None:
    if crafter(world, master) != "formation master":
        return "They sell no flags."
    if silver_of(world, person) < FLAG_LOT * FM.FLAG_PRICE:
        return f"Five flags cost {FLAG_LOT * FM.FLAG_PRICE} silver."
    return None


def flags_events(world, person: int, master: int, place) -> list[Event]:
    return [Event("flags_bought", (person, master), place, {"count": FLAG_LOT, "price": FLAG_LOT * FM.FLAG_PRICE})]


@effect("flags_bought")
def _flags(world, event) -> None:
    person, master = event.actors
    _pay(world, person, master, event.data["price"])
    FM.add_flags(world, person, event.data["count"])


def _pay(world, person: int, to: int, amount: int) -> None:
    world.update_data(person, silver=silver_of(world, person) - amount)
    world.update_data(to, silver=silver_of(world, to) + amount)


# --- commissions ---------------------------------------------------------------------------------------------

def lay_price(key: str) -> int:
    return LAY_PRICE * FM.PATTERNS[key]["difficulty"]


def lay_strength(world, master: int) -> float:
    return round(min(1.0, 0.5 + skill(world, master) / 10), 3)


def commission_lay_block(world, person: int, master: int, key: str, place) -> str | None:
    if key not in teaches(world, master):
        return "They do not know that pattern."
    why = FM.site_block(world, person, key, place)
    if why:
        return why
    if silver_of(world, person) < lay_price(key):
        return f"They ask {lay_price(key)} silver."
    return None


def commission_lay_events(world, person: int, master: int, key: str, place) -> list[Event]:
    return [Event("formation_commissioned", (person, master), place, {
        "pattern": key, "price": lay_price(key), "strength": lay_strength(world, master)})]


@effect("formation_commissioned")
def _laid_for(world, event) -> None:
    person, master = event.actors
    _pay(world, person, master, event.data["price"])
    FM.place_formation(world, event.place, event.data["pattern"], person, event.data["strength"])


def forge_grade(world, smith: int) -> int:
    return max(0, min(4, skill(world, smith) - 1))


def forge_price(world, smith: int, town: int, slot: str) -> int:
    from systems.smithy import price  # the smith's stall comes after the crafts in the import graph
    return FORGE_SHARE * price(world, town, slot, forge_grade(world, smith))


def pending(world, person: int) -> list[dict]:
    return list(world.entity(person).data.get("commissions") or [])


def commission_forge_block(world, person: int, smith: int, slot: str, form: str, town: int) -> str | None:
    if crafter(world, smith) != "smith":
        return "They are no smith."
    if form not in (gear.WEAPON_FORMS if slot == "weapon" else gear.ARMOURS):
        return "Nothing of that shape is forged."
    if any(c["smith"] == smith for c in pending(world, person)):
        return "They are forging for you already."
    if silver_of(world, person) < forge_price(world, smith, town, slot):
        return f"They ask {forge_price(world, smith, town, slot)} silver."
    return None


def commission_forge_events(world, person: int, smith: int, slot: str, form: str, town: int) -> list[Event]:
    return [Event("forge_commissioned", (person, smith), town, {
        "slot": slot, "form": form, "grade": forge_grade(world, smith),
        "price": forge_price(world, smith, town, slot), "ready_at": world.time + FORGE_DAYS * 4})]


@effect("forge_commissioned")
def _commissioned(world, event) -> None:
    person, smith = event.actors
    d = event.data
    _pay(world, person, smith, d["price"])
    world.update_data(person, commissions=pending(world, person) + [
        {"smith": smith, "slot": d["slot"], "form": d["form"], "grade": d["grade"], "ready_at": d["ready_at"]}])


def ready(world, person: int, smith: int) -> dict | None:
    return next((c for c in pending(world, person) if c["smith"] == smith and c["ready_at"] <= world.time), None)


def collect_events(world, person: int, smith: int, place) -> list[Event]:
    return [Event("commission_collected", (person, smith), place, dict(ready(world, person, smith)))]


@effect("commission_collected")
def _collected(world, event) -> None:
    person, smith = event.actors
    d = event.data
    world.update_data(person, commissions=[c for c in pending(world, person) if c["smith"] != smith])
    gear.make_item(world, d["slot"], d["form"], d["grade"], person, "commissioned", maker=world.entity(smith).name)
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_craft_world.py`
Expected: `3 failed, 5 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5d_task5.py`:
```python
"""Phase 5d, Task 5: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/smithy.py', r'''def cap(world, town: int) -> int:
    return CAPS.get(world.entity(town).data.get("kind"), 0)''', r'''def cap(world, town: int) -> int:
    from systems.craft_world import stall_lift  # phase 5d: a master smith lifts the stall a grade
    return min(4, CAPS.get(world.entity(town).data.get("kind"), 0) + stall_lift(world, town))''')
edit('systems/world_clock.py', r'''import systems.arrays  # noqa: E402,F401  phase 5d: what formations do
''', r'''import systems.arrays  # noqa: E402,F401  phase 5d: what formations do
import systems.craft_world  # noqa: E402,F401  phase 5d: smiths and formation masters, and their commissions
''')
edit('debug/invariants.py', r'''            out.append(f"a formation laid in {place.name} is malformed: {f}")
    return out''', r'''            out.append(f"a formation laid in {place.name} is malformed: {f}")
    for person in world.entities_after("person", "craft_skill", 0):
        if not 1 <= person.data["craft_skill"] <= 5:
            out.append(f"{person.name} (#{person.id}) has a craft skill of {person.data['craft_skill']}")
    return out''')
edit('debug/invariants.py', r"""    here = world.targets(player_id, "located_in")
    if here:
        known |= {p.name.lower() for p in people_at(world, here[0])}""", r"""    here = world.targets(player_id, "located_in") or world.targets(player_id, "buried_at")  # the dead saw them (5d)
    if here:
        known |= {p.name.lower() for p in people_at(world, here[0])}""")
print("task 5 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5d_task5.py`
Expected: `task 5 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_craft_world.py`
Expected: `8 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1421 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: smiths and formation masters - skill that grows, wares, and commissions"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 6: The Meet of Hammer and Furnace

Each spring a host city (4e's) holds the Meet for 30 days (ruling 7). Seven seeded masters stand in each craft; the player shows one blade of their own forging and one pill of their own refining. When it closes it is decided in the next season: the best of each craft is news, and a player who wins takes 500 silver and a title.

**Files:**
- Create: `systems/meet.py`
- Create: `tests/test_meet.py`
- Modify (by `.patches/5d_task6.py`): `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: 4e's `tournaments.host_city` and `titles`; Task 2's forging masteries; 5b's pills.
- Produces:
  - `MT` (systems/meet.py): `CRAFTS`, `DAYS`, `FIELD`, `PRIZE`, `MASTER_SCORES`, `WORDS`; `current(world)`, `is_open(world, place)`, `masters(world, year, craft)`, `score(world, person, craft, item_id)`, `fits(world, person, craft, item_id)`, `enter_block(world, person, craft, item_id, place)`, `enter_events(world, person, craft, item_id, place)`, `standings(world, craft)`, `decide_events(world)`, `open_events(world, n)`, `season_hook(world, n)`; events `meet_decided`, `meet_entered`, `meet_opened`.
  - the Meet in `check_crafts`.

- [ ] **Step 1: Write the tests**

`tests/test_meet.py`:
```python
import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.gear as gear
import systems.meet as MT
from debug.invariants import check_crafts
from engine.game import Game
from systems.creation import CreationChoice
from systems.purse import silver_of
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


def opened(game):
    world = game.world
    commit(world, MT.open_events(world, 0))
    return MT.current(world)["town"]


def go(game, place):
    world, me = game.world, game.player.id
    world.unrelate(me, "located_in")
    world.relate(me, place, "located_in")


def test_the_meet_opens_each_spring_in_a_host_city_for_thirty_days(game):
    world = game.world
    assert MT.season_hook(world, 1) == []
    [opening] = MT.season_hook(world, 4)
    commit(world, [opening])
    m = MT.current(world)
    assert m["year"] == 2 and m["end"] - m["start"] == MT.DAYS * 4 and not m["decided"]
    assert check_crafts(world) == []


def test_seven_seeded_masters_stand_in_each_craft(game):
    world = game.world
    field = MT.masters(world, 1, "forging")
    assert len(field) == MT.FIELD and MT.masters(world, 1, "forging") == field
    assert all(MT.MASTER_SCORES[0] <= s <= MT.MASTER_SCORES[1] for _, s in field)


def test_only_ones_own_blade_or_pill_is_shown_once_a_craft(game):
    world, me = game.world, game.player.id
    town = opened(game)
    bought = gear.make_item(world, "weapon", "sword", 3, me, "bought")
    go(game, town)
    assert "own forging" in MT.enter_block(world, me, "forging", bought, town)
    blade = gear.make_item(world, "weapon", "sword", 4, me, "forged", maker=me, forged_by=me)
    world.update_data(me, forge_mastery={"sword": 0.9})
    assert MT.enter_block(world, me, "forging", blade, town) is None
    commit(world, MT.enter_events(world, me, "forging", blade, town))
    assert MT.current(world)["entries"]["forging"][str(me)] == 49.0
    assert "already" in MT.enter_block(world, me, "forging", blade, town)
    pill = A.make_pill(world, me, A.recipe_entity(world, "calming"), 2, 0.9)
    assert MT.enter_block(world, me, "refining", pill, town) is None


def test_the_best_of_each_craft_is_named_when_the_meet_closes(game):
    world, me = game.world, game.player.id
    town = opened(game)
    go(game, town)
    blade = gear.make_item(world, "weapon", "sword", 4, me, "forged", maker=me, forged_by=me)
    world.update_data(me, forge_mastery={"sword": 1.0}, silver=0)
    commit(world, MT.enter_events(world, me, "forging", blade, town))
    assert MT.decide_events(world) == []  # still open
    world.set_time(MT.current(world)["end"])
    commit(world, MT.decide_events(world))
    assert MT.current(world)["decided"]
    assert silver_of(world, me) == MT.PRIZE and any("anvil" in t for t in world.entity(me).data["titles"])
    facts = world.facts(predicate="meet_won")
    assert {f.variant["craft"] for f in facts} == set(MT.CRAFTS)
    assert MT.decide_events(world) == []  # decided once


def test_no_one_shows_a_piece_where_the_meet_is_not_held(game):
    world, me = game.world, game.player.id
    town = opened(game)
    blade = gear.make_item(world, "weapon", "sword", 4, me, "forged", maker=me, forged_by=me)
    elsewhere = game.place.id if game.place.id != town else None
    if elsewhere is not None:
        assert "not held here" in MT.enter_block(world, me, "forging", blade, elsewhere)
    world.set_time(MT.current(world)["end"])
    assert "not held here" in MT.enter_block(world, me, "forging", blade, town)


def test_the_rules_catch_a_malformed_meet(game):
    world = game.world
    world.set_meta("meet", {"year": 1, "town": 999999, "start": 10, "end": 5, "entries": {}, "decided": False})
    assert "Meet" in " | ".join(check_crafts(world))
```

- [ ] **Step 2: Write the new modules**

`systems/meet.py`:
```python
"""The Meet of Hammer and Furnace (phase 5d spec 6): once a year, in a host city, smiths show a blade and
alchemists a pill.

It opens each spring for 30 days in a city (4e's host). Seven seeded masters stand in each craft; the player may
show one piece in each. A blade scores `10 x grade + 10 x the smith's mastery of its form`, a pill
`10 x grade + 10 x purity`. When the Meet closes the best of each craft is named: the player, if they won, takes
500 silver and a title. The Meet is one meta row (`meet`), decided in the season after it closes.
"""

import systems.forging as FG
import systems.lives as lives
import systems.world_clock as world_clock
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import Event, commit, effect, listen
from world.gen.names import person_name
from world.seed import rng_for

CRAFTS = ("forging", "refining")
DAYS, FIELD, PRIZE = 30, 7, 500
MASTER_SCORES = (20.0, 55.0)
WORDS = {"forging": "the anvil", "refining": "the furnace"}


def current(world) -> dict | None:
    return world.get_meta("meet")


def is_open(world, place=None) -> bool:
    m = current(world)
    return m is not None and not m["decided"] and m["start"] <= world.time < m["end"] \
        and (place is None or m["town"] == place)


def masters(world, year: int, craft: str) -> list[tuple[str, float]]:
    """The seven masters of a craft at this year's Meet, and their scores (seeded)."""
    rng = rng_for(world.world_seed, f"meet:{year}:{craft}")
    out = []
    for _ in range(FIELD):
        surname, given = person_name(rng)
        out.append((f"{surname} {given}", round(rng.uniform(*MASTER_SCORES), 1)))
    return out


def score(world, person: int, craft: str, item_id: int) -> float:
    item = world.entity(item_id)
    if craft == "forging":
        return round(10 * item.data["grade"] + 10 * (FG.mastery(world, person, item.data["form"]) or 0.0), 1)
    return round(10 * item.data["grade"] + 10 * item.data.get("purity", 0.0), 1)


def fits(world, person: int, craft: str, item_id) -> bool:
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item_id not in world.targets(person, "owns") or item.data.get("used"):
        return False
    if craft == "forging":
        return item.kind == "gear" and item.data.get("forged_by") == person and not item.data.get("broken")
    return item.kind == "pill" and item.data.get("maker") == person


def enter_block(world, person: int, craft: str, item_id, place) -> str | None:
    if not is_open(world, place):
        return "The Meet is not held here now."
    if str(person) in current(world)["entries"].get(craft, {}):
        return "You have shown a piece in that craft already."
    if not fits(world, person, craft, item_id):
        return "Only a blade of your own forging, or a pill of your own refining, is shown."
    return None


def enter_events(world, person: int, craft: str, item_id: int, place) -> list[Event]:
    return [Event("meet_entered", (person,), place, {"craft": craft, "item": item_id,
                                                     "score": score(world, person, craft, item_id)})]


@effect("meet_entered")
def _entered(world, event) -> None:
    m = dict(current(world))
    entries = {k: dict(v) for k, v in m["entries"].items()}
    entries.setdefault(event.data["craft"], {})[str(event.actors[0])] = event.data["score"]
    world.set_meta("meet", {**m, "entries": entries})


def standings(world, craft: str) -> list[tuple[str, float, int | None]]:
    """(name, score, person or None) for the craft, best first."""
    m = current(world)
    rows = [(name, s, None) for name, s in masters(world, m["year"], craft)]
    rows += [(world.entity(int(p)).name, s, int(p)) for p, s in m["entries"].get(craft, {}).items()]
    return sorted(rows, key=lambda r: (-r[1], r[0]))


def decide_events(world) -> list[Event]:
    m = current(world)
    if m is None or m["decided"] or world.time < m["end"]:
        return []
    events = []
    for craft in CRAFTS:
        name, best, person = standings(world, craft)[0]
        events.append(Event("meet_decided", (person,) if person is not None else (), m["town"],
                            {"year": m["year"], "craft": craft, "name": name, "score": best,
                             "prize": PRIZE if person is not None else 0,
                             "title": f"champion of {WORDS[craft]} at the Meet of Hammer and Furnace, year {m['year']}"}))
    return events


@effect("meet_decided")
def _decided(world, event) -> None:
    d = event.data
    m = current(world)
    world.set_meta("meet", {**m, "decided": m["decided"] or d["craft"] == CRAFTS[-1]})
    if event.actors:
        champion = event.actors[0]
        world.update_data(champion, silver=silver_of(world, champion) + d["prize"],
                          titles=list(world.entity(champion).data.get("titles", [])) + [d["title"]])


@listen("meet_decided")
def _news(world, event, event_id: int) -> None:
    d = event.data
    subject = event.actors[0] if event.actors else event.place
    variant = make_variant("meet_won", event.actors[0] if event.actors else None, None,
                           place=place_name(world, event.place))
    variant.update(name=d["name"], craft=d["craft"], year=d["year"])
    record_fact(world, subject, "meet_won", None, place=event.place, source_event=event_id, weight=1.5, variant=variant)


def open_events(world, n: int) -> list[Event]:
    from systems.tournaments import host_city
    year = n // 4 + 1
    town = host_city(world, rng_for(world.world_seed, f"meet_host:{year}"))
    return [Event("meet_opened", (), town, {"year": year, "start": n * lives.SEASON,
                                            "end": n * lives.SEASON + DAYS * 4})]


@effect("meet_opened")
def _opened(world, event) -> None:
    d = event.data
    world.set_meta("meet", {"year": d["year"], "town": event.place, "start": d["start"], "end": d["end"],
                            "entries": {}, "decided": False})


def season_hook(world, n: int) -> list[Event]:
    """Each season the Meet that has closed is decided; each spring a new one opens."""
    commit(world, decide_events(world))
    return open_events(world, n) if n % 4 == 0 else []


world_clock.SEASON_HOOKS.append(season_hook)
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_meet.py`
Expected: `1 failed, 5 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5d_task6.py`:
```python
"""Phase 5d, Task 6: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.craft_world  # noqa: E402,F401  phase 5d: smiths and formation masters, and their commissions
''', r'''import systems.craft_world  # noqa: E402,F401  phase 5d: smiths and formation masters, and their commissions
import systems.meet  # noqa: E402,F401  phase 5d: the Meet of Hammer and Furnace
''')
edit('debug/invariants.py', r'''            out.append(f"{person.name} (#{person.id}) has a craft skill of {person.data['craft_skill']}")
    return out''', r'''            out.append(f"{person.name} (#{person.id}) has a craft skill of {person.data['craft_skill']}")
    meet = world.get_meta("meet")
    if meet is not None and (world.entity(meet.get("town") or 0) is None or not meet["start"] < meet["end"]):
        out.append(f"the Meet of Hammer and Furnace is malformed: {meet}")
    return out''')
print("task 6 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5d_task6.py`
Expected: `task 6 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_meet.py`
Expected: `6 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1427 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the Meet of Hammer and Furnace - a yearly contest of the anvil and the furnace"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 7: The player's crafts

`CraftsMixin` puts the crafts in the player's hands: a crafts page (levels, masteries, patterns, materials, manuals, what is laid here as known), the anvil (materials on it, forging each form, refining, naming a masterwork), materials and a forge at the smith's, a slain beast's bones and core, one "Their craft..." talk menu for smiths and formation masters (ruling 8), and the Meet where it is held. Every new deed has its outcome, journal line and grammar; 5a's blade legends gain a rumour (ruling 9); typed words and help reach it all.

**Files:**
- Create: `engine/crafts.py`
- Create: `engine/crafts_page.py`
- Create: `narrate/crafts_text.py`
- Create: `narrate/grammar/crafts.toml`
- Create: `tests/test_crafts_play.py`
- Modify (by `.patches/5d_task7.py`): `engine/game.py`, `engine/commands.py`, `engine/sheet.py`, `narrate/outcomes.py`, `tests/test_game.py`

**Interfaces:**
- Consumes: Everything above; 5a's smith menu and `GearMixin`; 5c's talk menus as the model.
- Produces:
  - `engine/crafts.py` (engine/crafts.py): `CRAFT_MENUS`, `TALK_MENU`.
  - `engine/crafts_page.py` (engine/crafts_page.py): `laid_lines(world, viewer, place)`, `crafts_lines(world, player, place)`, `meet_lines(world)`, `sheet_crafts_lines(world, player)`.
  - `narrate/crafts_text.py`: outcomes, journal lines, and the rumours `blade_legend` and `meet_won`.

- [ ] **Step 1: Write the tests**

`tests/test_crafts_play.py`:
```python
import pytest

import systems.encounters as encounters
import systems.formations as FM
import systems.gear as gear
import systems.materials as M
import systems.meet as MT
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.outcomes import SUMMARIES
from systems.creation import CreationChoice
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=20000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def labels(turn):
    return [c.label for c in turn.all_choices]


def pick(turn, verb):
    return next(c.action for c in turn.all_choices if c.action.verb == verb)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "mortal", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:cplay:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_materials_go_on_the_anvil_and_a_blade_is_forged(game, monkeypatch):
    import systems.forging as FG
    world, me = game.world, game.player.id
    monkeypatch.setattr(FG, "BOUNDS", (1.0, 1.0))
    for _ in range(2):
        M.make_material(world, "black steel", me)
    turn = game.perform(Action("anvil"))
    game.perform(pick(turn, "add_material"))
    turn = game.perform(Action("anvil"))
    forge = next(c for c in turn.all_choices if c.action.verb == "forge" and c.action.target == ("weapon", "sword"))
    assert forge.label == "Forge a fine steel sword"
    game.perform(forge.action)
    assert any(i.data.get("forged_by") == me for i in gear.gear_items(world, me))


def test_the_smith_sells_materials_and_a_forge(game):
    turn = game.perform(Action("smith"))
    assert any(label.startswith("Buy iron ingot") for label in labels(turn))
    assert f"Buy an anvil and a forge ({M.FORGE_PRICE} silver)" in labels(turn)
    game.perform(pick(turn, "buy_material"))
    assert M.materials_of(game.world, game.player.id)


def test_a_slain_beast_is_butchered_from_the_scene(game):
    world, me = game.world, game.player.id
    wolf = world.add_entity("person", "a grey wolf", {"beast": True, "occupation": "grey wolf",
                                                      "realm": "second-rate", "traits": ["hot-tempered"]}, "test:wolf")
    world.relate(wolf, game.place.id, "located_in")
    commit(world, [Event("died", (me, wolf), game.place.id, {"cause": "killed"})])
    game._slain_game = wolf
    turn = game.perform(Action("look"))
    assert "Take a grey wolf's bones" in labels(turn) and "Take a grey wolf's core" in labels(turn)
    game.perform(Action("take_parts", "core"))
    assert M.materials_of(world, me)


def test_a_manual_is_studied_and_its_pattern_laid_from_the_crafts_page(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(FM, "BOUNDS", (1.0, 1.0))
    FM.make_manual(world, me, "confusion", "bought")
    FM.add_flags(world, me, 5)
    turn = game.perform(Action("crafts"))
    game.perform(pick(turn, "study_formation"))
    turn = game.perform(Action("crafts"))
    game.perform(pick(turn, "lay_formation"))
    page = " | ".join(t for t, _ in game.perform(Action("crafts")).lines)
    assert "The Confusion array holds here, laid by you (1 day(s) left)." in page


def test_a_formation_master_sells_and_lays_in_conversation(game):
    world, me = game.world, game.player.id
    master = someone(game, "master", occupation="fortune teller", craft_skill=5)
    game.perform(Action("talk", master))
    turn = game.perform(Action("craft_talk"))
    assert any("grandmaster formation master" in t for t, _ in turn.lines)
    game.perform(pick(turn, "buy_flags"))
    assert FM.flags_of(world, me) == 5
    turn = game.perform(Action("craft_talk"))
    game.perform(pick(turn, "commission_lay"))
    assert FM.laid(world, game.place.id)


def test_a_smiths_commission_is_collected_in_conversation(game):
    world, me = game.world, game.player.id
    smith = someone(game, "smith", occupation="blacksmith", craft_skill=3)
    game.perform(Action("talk", smith))
    turn = game.perform(Action("craft_talk"))
    game.perform(pick(turn, "commission_forge"))
    world.set_time(world.time + 10 * 4)
    game.perform(Action("talk", smith))
    turn = game.perform(Action("craft_talk"))
    game.perform(pick(turn, "collect_commission"))
    assert any(i.data["owners"][0]["how"] == "commissioned" for i in gear.gear_items(world, me))


def test_a_masterwork_is_named_from_the_crafts_page(game):
    world, me = game.world, game.player.id
    blade = gear.make_item(world, "weapon", "sword", 3, me, "forged", maker=me, forged_by=me)
    turn = game.perform(Action("crafts"))
    turn = game.perform(pick(turn, "name_menu"))
    game.perform(pick(turn, "name_masterwork"))
    assert world.entity(blade).data["famous"]


def test_the_meet_is_entered_where_it_is_held(game):
    world, me = game.world, game.player.id
    commit(world, MT.open_events(world, 0))
    town = MT.current(world)["town"]
    world.unrelate(me, "located_in")
    world.relate(me, town, "located_in")
    gear.make_item(world, "weapon", "sword", 3, me, "forged", maker=me, forged_by=me)
    assert "The Meet of Hammer and Furnace" in labels(game.perform(Action("look")))
    turn = game.perform(Action("meet"))
    game.perform(pick(turn, "enter_meet"))
    assert str(me) in MT.current(world)["entries"]["forging"]


def test_the_sheet_shows_the_crafts(game):
    world, me = game.world, game.player.id
    FM.learn(world, me, "seclusion")
    assert any("the Seclusion ward" in t for t, _ in sheet_lines(world, me))


def test_typed_words_reach_the_crafts(game):
    turn = game.perform(Action("look"))
    for word, verb in (("crafts", "crafts"), ("anvil", "anvil"), ("forge", "anvil")):
        assert parse(word, turn.choices, turn.extra).verb == verb


def test_help_names_the_crafts(game):
    assert any("crafts | anvil | meet" in t for t, _ in game.perform(Action("help")).lines)


def test_every_craft_deed_has_a_journal_line():
    for kind in ("material_bought", "beast_parts_taken", "forge_bought", "forged", "gear_refined", "masterwork_named",
                 "formation_studied", "formation_laid", "manual_bought", "flags_bought", "formation_commissioned",
                 "forge_commissioned", "commission_collected", "meet_entered", "meet_decided"):
        assert kind in SUMMARIES, kind
```

- [ ] **Step 2: Write the new modules**

`engine/crafts.py`:
```python
"""Forging and formations in the engine (phase 5d spec 7): the anvil, refining and masterworks, materials at the
smith's and from the slain, formations known and laid, smiths' and formation masters' wares and commissions, and
the Meet of Hammer and Furnace."""

import systems.craft_world as CW
import systems.forging as FG
import systems.formations as FM
import systems.gear as gear
import systems.materials as M
import systems.meet as MT
import systems.pills as P
from engine.actions import Action, Choice
from engine.crafts_page import crafts_lines, meet_lines

CRAFT_MENUS = ("crafts", "anvil", "masterwork", "meet")
TALK_MENU = "craft_talk"


def _distinct(items) -> list:
    seen, out = set(), []
    for item in items:
        if item.name not in seen:
            seen.add(item.name)
            out.append(item)
    return out


class CraftsMixin:
    _anvil: tuple = ()
    _naming: int | None = None

    @property
    def _slain_game(self) -> int | None:
        """A beast just slain here, kept with the hero (a reload keeps it; an heir has none)."""
        slain = self.world.entity(self.player.id).data.get("slain_game")
        return slain["beast"] if slain and slain.get("place") == self.place.id else None

    @_slain_game.setter
    def _slain_game(self, beast: int | None) -> None:
        self.world.update_data(self.player.id,
                               slain_game=None if beast is None else {"beast": beast, "place": self.place.id})

    # --- choices -----------------------------------------------------------------------------------------------
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, here = self.world, self.player.id, self.place.id
        extras.append(Choice("Your crafts", Action("crafts")))
        if world.entity(here).kind == "town" or M.forge_of(world, me) is not None:
            extras.append(Choice("Work at the anvil", Action("anvil")))
        beast = self._slain_game
        if beast is not None:
            for part in M.PARTS:
                if M.parts_block(world, me, beast, part, here) is None:
                    word = "bones" if part == "bone" else "core"
                    extras.append(Choice(f"Take {world.entity(beast).name}'s {word}", Action("take_parts", part)))
        if MT.is_open(world, here):
            extras.append(Choice("The Meet of Hammer and Furnace", Action("meet")))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if CW.crafter(self.world, npc.id) is not None:
            extras.append(Choice("Their craft...", Action("craft_talk")))
        return extras

    def _craft_talk(self, npc) -> list:
        world, me, here = self.world, self.player.id, self.place.id
        out = []
        if CW.crafter(world, npc.id) == "formation master":
            out.append(Choice(f"Buy {CW.FLAG_LOT} formation flags ({CW.FLAG_LOT * FM.FLAG_PRICE} silver)",
                              Action("buy_flags", npc.id)))
            for key in CW.teaches(world, npc.id):
                name = FM.PATTERNS[key]["name"]
                if FM.mastery(world, me, key) is None:
                    out.append(Choice(f"Buy a manual of {name} ({FM.manual_price(key)} silver)",
                                      Action("buy_manual", (npc.id, key))))
                if CW.commission_lay_block(world, me, npc.id, key, here) is None:
                    out.append(Choice(f"Have them lay {name} here ({CW.lay_price(key)} silver)",
                                      Action("commission_lay", (npc.id, key))))
        else:
            if CW.ready(world, me, npc.id) is not None:
                out.append(Choice("Collect what they forged for you", Action("collect_commission", npc.id)))
            grade = gear.GRADE_WORDS[CW.forge_grade(world, npc.id)]
            for slot, forms in FG.FORMS.items():
                for form in forms:
                    if CW.commission_forge_block(world, me, npc.id, slot, form, here) is None:
                        what = form if slot == "weapon" else gear.ARMOUR_WORDS[form]
                        out.append(Choice(f"Commission a {grade} {what} "
                                          f"({CW.forge_price(world, npc.id, here, slot)} silver)",
                                          Action("commission_forge", (npc.id, slot, form))))
        return out

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        world, me, here = self.world, self.player.id, self.place.id
        if self.focus is not None:
            if self.submenu == TALK_MENU:
                options[TALK_MENU] = (self._craft_talk(world.entity(self.focus)), Action("talk_menu"))
            return options
        if self.submenu == "smith" and "smith" in options:  # iron and a forge of one's own, at the smith's
            choices, back = options["smith"]
            more = [Choice(f"Buy {o['material']} ({M.price(world, here, o['material'])} silver)",
                           Action("buy_material", o["key"])) for o in _first_of_each(M.stock(world, here))]
            if M.buy_forge_block(world, me) is None:
                more.append(Choice(f"Buy an anvil and a forge ({M.FORGE_PRICE} silver)", Action("buy_forge")))
            options["smith"] = (more + choices, back)
        if self.submenu not in CRAFT_MENUS:
            return options
        choices = []
        if self.submenu == "crafts":
            for manual in _distinct(FM.manuals_of(world, me)):
                if FM.study_block(world, me, manual.id) is None:
                    choices.append(Choice(f"Study {manual.name}", Action("study_formation", manual.id)))
            for key in sorted(FM.known(world, me)):
                if FM.lay_block(world, me, key, here) is None:
                    choices.append(Choice(f"Lay {FM.PATTERNS[key]['name']} here ({FM.PATTERNS[key]['flags']} flags)",
                                          Action("lay_formation", key)))
            for item in gear.gear_items(world, me):
                if FG.masterwork_block(world, me, item.id) is None:
                    choices.append(Choice(f"Name {item.name}", Action("name_menu", item.id)))
        elif self.submenu == "anvil":
            anvil = [m for m in self._anvil if m in world.targets(me, "owns")]
            if anvil and M.forge_block(world, me, here) is None:
                for slot, forms in FG.FORMS.items():
                    for form in forms:
                        what = form if slot == "weapon" else gear.ARMOUR_WORDS[form]
                        grade = gear.GRADE_WORDS[FG.grade_of(world, me, form, anvil)]
                        choices.append(Choice(f"Forge a {grade} {what}", Action("forge", (slot, form))))
            if anvil:
                choices.append(Choice("Clear the anvil", Action("clear_anvil")))
            if len(anvil) < FG.MAX_MATERIALS:
                choices += [Choice(f"Put {m.name} on the anvil", Action("add_material", m.id))
                            for m in _distinct(m for m in M.materials_of(world, me) if m.id not in anvil)]
            for item in gear.gear_items(world, me):
                for m in _distinct(M.materials_of(world, me)):
                    if FG.refine_block(world, me, here, item.id, m.id) is None:
                        choices.append(Choice(f"Refine {item.name} with {m.name}", Action("refine_gear", (item.id, m.id))))
        elif self.submenu == "masterwork" and self._naming is not None:
            choices = [Choice(f"Name it {name}", Action("name_masterwork", name))
                       for name in FG.names_for(world, self._naming)]
        elif self.submenu == "meet":
            for craft in MT.CRAFTS:
                pieces = gear.gear_items(world, me) if craft == "forging" else P.pills_of(world, me)
                for piece in _distinct(pieces):
                    if MT.enter_block(world, me, craft, piece.id, here) is None:
                        choices.append(Choice(f"Show {piece.name} ({MT.score(world, me, craft, piece.id)})",
                                              Action("enter_meet", (craft, piece.id))))
        options[self.submenu] = (choices, Action("back"))
        return options

    # --- the world around ---------------------------------------------------------------------------------------
    def _after_arrival(self) -> list:
        self._slain_game, self._anvil = None, ()
        return super()._after_arrival()

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is not None and data.get("killed") and self.world.entity(entry.actors[1]).data.get("beast"):
            self._slain_game = entry.actors[1]
        return lines

    # --- handlers ---------------------------------------------------------------------------------------------------
    def _do_crafts(self, _target):
        self.submenu = "crafts"
        return self._turn(crafts_lines(self.world, self.player.id, self.place.id))

    def _do_anvil(self, _target):
        self.submenu = "anvil"
        anvil = [self.world.entity(m).name for m in self._anvil if m in self.world.targets(self.player.id, "owns")]
        lines = [("The anvil", "heading"), (f"  On it: {', '.join(anvil) if anvil else 'nothing'}", "dim")]
        if (why := M.forge_block(self.world, self.player.id, self.place.id)) is not None:
            lines.append((f"  {why}", "dim"))
        return self._turn(lines)

    def _do_add_material(self, item):
        world, me = self.world, self.player.id
        if M.material_info(world.entity(item) if isinstance(item, int) else None) is None \
                or item not in world.targets(me, "owns"):
            return self._turn([("You have no such material.", "system")])
        if item not in self._anvil and len(self._anvil) < FG.MAX_MATERIALS:
            self._anvil = self._anvil + (item,)
        return self._do_anvil(None)

    def _do_clear_anvil(self, _target):
        self._anvil, self.submenu = (), "anvil"
        return self._turn([("You take the materials back off the anvil.", "system")])

    def _do_forge(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        slot, form = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        anvil = [m for m in self._anvil if m in world.targets(me, "owns")]
        if slot is None or (why := FG.forge_block(world, me, here, slot, form, anvil)) is not None:
            return self._turn([(why if slot is not None else "Forge what?", "system")])
        self._anvil, self.submenu = (), "anvil"
        return self._turn(self._commit(FG.forge_events(world, me, here, slot, form, anvil)))

    def _do_refine_gear(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        item, material = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        self.submenu = "anvil"
        if item is None or (why := FG.refine_block(world, me, here, item, material)) is not None:
            return self._turn([(why if item is not None else "Refine what?", "system")])
        self._anvil = tuple(m for m in self._anvil if m != material)
        return self._turn(self._commit(FG.refine_events(world, me, here, item, material)))

    def _do_name_menu(self, item):
        if (why := FG.masterwork_block(self.world, self.player.id, item)) is not None:
            return self._turn([(why, "system")])
        self._naming, self.submenu = item, "masterwork"
        return self._turn([(f"What will you call {self.world.entity(item).name}?", "system")])

    def _do_name_masterwork(self, name):
        world, me, item = self.world, self.player.id, self._naming
        if item is None or (why := FG.masterwork_block(world, me, item)) is not None \
                or name not in FG.names_for(world, item):
            return self._turn([("There is nothing to name.", "system")])
        self._naming = None
        return self._turn(self._commit(FG.masterwork_events(world, me, item, name, self.place.id)))

    def _do_buy_material(self, key):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "smith"
        if not isinstance(key, str) or (why := M.buy_block(world, me, here, key)) is not None:
            return self._turn([(why if isinstance(key, str) else "The smith has none of that.", "system")])
        return self._turn(self._commit(M.buy_events(world, me, here, key)))

    def _do_buy_forge(self, _target):
        self.submenu = "smith"
        if (why := M.buy_forge_block(self.world, self.player.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(M.buy_forge_events(self.world, self.player.id, self.place.id)))

    def _do_take_parts(self, part):
        world, me, here = self.world, self.player.id, self.place.id
        beast = self._slain_game
        if beast is None or (why := M.parts_block(world, me, beast, part, here)) is not None:
            return self._turn([("There is nothing to take.", "system")])
        return self._turn(self._commit(M.parts_events(world, me, beast, part, here)))

    def _do_study_formation(self, item):
        world, me = self.world, self.player.id
        if item is None:
            item = next((m.id for m in FM.manuals_of(world, me) if FM.study_block(world, me, m.id) is None), None)
        self.submenu = "crafts"
        if item is None or (why := FM.study_block(world, me, item)) is not None:
            return self._turn([(why if item is not None else "You have no manual to study.", "system")])
        return self._turn(self._commit(FM.study_events(world, me, item, self.place.id)))

    def _do_lay_formation(self, key):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "crafts"
        if not isinstance(key, str) or (why := FM.lay_block(world, me, key, here)) is not None:
            return self._turn([(why if isinstance(key, str) else "Lay what?", "system")])
        return self._turn(self._commit(FM.lay_events(world, me, key, here)))

    def _do_meet(self, _target):
        if not MT.is_open(self.world, self.place.id):
            return self._turn([("The Meet is not held here now.", "system")])
        self.submenu = "meet"
        return self._turn(meet_lines(self.world))

    def _do_enter_meet(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        craft, item = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        self.submenu = "meet"
        if craft is None or (why := MT.enter_block(world, me, craft, item, here)) is not None:
            return self._turn([(why if craft is not None else "Show what?", "system")])
        return self._turn(self._commit(MT.enter_events(world, me, craft, item, here)) + meet_lines(world))

    # --- in conversation -------------------------------------------------------------------------------------------
    def _do_craft_talk(self, _target):
        if self.focus is None or CW.crafter(self.world, self.focus) is None:
            return self._turn([("They have no craft to speak of.", "system")])
        self.submenu = TALK_MENU
        told = f"{self.world.entity(self.focus).name} is {CW.title(self.world, self.focus)}."
        return self._turn([(told, "dim"), ("What will you ask of them?", "system")])

    def _craft_deed(self, npc, why, events):
        if self.focus != npc:
            return self._turn([("They are not the one you are speaking with.", "system")])
        if why is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(events()))

    def _do_buy_flags(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        return self._craft_deed(npc, CW.flags_block(world, me, npc), lambda: CW.flags_events(world, me, npc, here))

    def _do_buy_manual(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, key = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        return self._craft_deed(npc, CW.manual_block(world, me, npc, key) if npc else "They sell nothing.",
                               lambda: CW.manual_events(world, me, npc, key, here))

    def _do_commission_lay(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, key = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        return self._craft_deed(npc, CW.commission_lay_block(world, me, npc, key, here) if npc else "They lay nothing.",
                               lambda: CW.commission_lay_events(world, me, npc, key, here))

    def _do_commission_forge(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, slot, form = target if isinstance(target, tuple) and len(target) == 3 else (None, None, None)
        return self._craft_deed(npc, CW.commission_forge_block(world, me, npc, slot, form, here) if npc
                               else "They forge nothing.",
                               lambda: CW.commission_forge_events(world, me, npc, slot, form, here))

    def _do_collect_commission(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        why = None if isinstance(npc, int) and CW.ready(world, me, npc) is not None else "Nothing of yours is ready."
        return self._craft_deed(npc, why, lambda: CW.collect_events(world, me, npc, here))


def _first_of_each(offers: list[dict]) -> list[dict]:
    seen, out = set(), []
    for o in offers:
        if o["material"] not in seen:
            seen.add(o["material"])
            out.append(o)
    return out
```

`engine/crafts_page.py`:
```python
"""The crafts page (phase 5d spec 7-8): forging and formations as the player knows them, what is laid here, the
Meet's standings, and the sheet's lines."""

import systems.forging as FG
import systems.formations as FM
import systems.materials as M
import systems.meet as MT


def laid_lines(world, viewer: int, place) -> list:
    """What is laid here: one's own and patterns one knows by name, the rest only as something (spec 8)."""
    lines = []
    known = FM.known(world, viewer)
    for f in FM.laid(world, place):
        name = FM.PATTERNS[f["pattern"]]["name"]
        name = name[:1].upper() + name[1:]
        if f["owner"] == viewer:
            days = max(1, round((f["until"] - world.time) / 4))
            lines.append((f"  {name} holds here, laid by you ({days} day(s) left).", "dim"))
        elif f["pattern"] in known:
            lines.append((f"  {name} is laid here, by another hand.", "dim"))
        else:
            lines.append(("  Something is laid here: the air is wrong.", "dim"))
    return lines


def crafts_lines(world, player: int, place) -> list:
    lines = [("Crafts", "heading"),
             (f"  Forging level {FG.level(world, player)} | formation level {FM.level(world, player)} | "
              f"{FM.flags_of(world, player)} formation flags", "dim")]
    masteries = world.entity(player).data.get("forge_mastery") or {}
    if masteries:
        lines.append(("  Forged: " + ", ".join(f"{form} {m:.2f}" for form, m in sorted(masteries.items())), "dim"))
    known = FM.known(world, player)
    lines.append(("Patterns you know:" if known else "You know no formations yet: a manual will teach one.", "heading"))
    lines += [(f"  {FM.PATTERNS[k]['name']} ({FM.PATTERNS[k]['use']}): mastery {m:.2f}", "dim")
              for k, m in sorted(known.items())]
    materials = M.materials_of(world, player)
    if materials:
        lines.append(("Materials:", "heading"))
        lines += [(f"  {m.name} (grade {M.material_info(m)[1]})", "dim") for m in materials]
    manuals = FM.manuals_of(world, player)
    if manuals:
        lines.append(("Manuals:", "heading"))
        lines += [(f"  {m.name}", "dim") for m in manuals]
    here = laid_lines(world, player, place)
    if here:
        lines.append(("Laid here:", "heading"))
        lines += here
    return lines


def meet_lines(world) -> list:
    m = MT.current(world)
    lines = [(f"The Meet of Hammer and Furnace, year {m['year']}", "heading")]
    for craft in MT.CRAFTS:
        top = MT.standings(world, craft)[:3]
        lines.append((f"  At {MT.WORDS[craft]}: " + "; ".join(f"{name} {score}" for name, score, _ in top), "dim"))
    return lines


def sheet_crafts_lines(world, player: int) -> list:
    masteries = world.entity(player).data.get("forge_mastery") or {}
    known = FM.known(world, player)
    if not masteries and not known:
        return []
    lines = [("", "default"), ("Crafts:", "heading"),
             (f"  Forging level {FG.level(world, player)}; formation level {FM.level(world, player)}", "default")]
    if known:
        lines.append(("  Patterns: " + ", ".join(FM.PATTERNS[k]["name"] for k in sorted(known)), "default"))
    return lines
```

`narrate/crafts_text.py`:
```python
"""What the player is told of the forge, formations, commissions and the Meet (phase 5d spec 7)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

import systems.formations as FM
import systems.gear as gear


def _name(world, entity_id) -> str:
    entity = world.entity(entity_id) if isinstance(entity_id, int) else None
    return entity.name if entity else "someone"


def _legend(world, v, viewer) -> str:
    """A smith's own legend is told whole; 5a's tell of sects the hearer may not know, so they are not quoted."""
    legend = v.get("legend") or ""
    if legend.startswith("forged by "):
        return cap(f"{_name(world, v.get('actor'))}: {legend}.")
    return cap(f"{_name(world, v.get('actor'))} is a blade of legend.")


def _meet(world, v, viewer) -> str:
    who_won = who(world, v.get("actor"), viewer) if v.get("actor") is not None else v.get("name", "someone")
    craft = "the anvil" if v.get("craft") == "forging" else "the furnace"
    return cap(f"{who_won} won {craft} at the Meet of Hammer and Furnace in {v.get('place') or 'a city'}.")


SPECIAL_PHRASES.setdefault("blade_legend", _legend)
SPECIAL_PHRASES["meet_won"] = _meet


@outcome("material_bought", body_facts=False)
def _bought(world, event):
    return [f"You pay {event.data['price']} silver for the {event.data['material']}."], {}


@summary("material_bought")
def _bought_line(world, entry, names, place, other):
    return f"Bought {entry.data['material']} at {place}."


@outcome("beast_parts_taken", body_facts=False)
def _parts(world, event):
    what = "bones" if event.data["part"] == "bone" else "core"
    return [f"You take {_name(world, event.actors[1])}'s {what}. A smith will want them."], {}


@summary("beast_parts_taken")
def _parts_line(world, entry, names, place, other):
    return f"Took the {entry.data['part']} of {other}."


@outcome("forge_bought", body_facts=False)
def _forge(world, event):
    return [f"An anvil and a travelling forge are yours, for {event.data['price']} silver."], {}


@summary("forge_bought")
def _forge_line(world, entry, names, place, other):
    return "Bought an anvil and a forge."


@outcome("forged", body_facts=False)
def _forged(world, event):
    d = event.data
    what = d["form"] if d["slot"] == "weapon" else gear.ARMOUR_WORDS[d["form"]]
    if d["success"]:
        return [f"The quench hisses: a {gear.GRADE_WORDS[d['grade']]} {what}, of your own forging."], {}
    return ["The metal cracks in the quench" + (" and the fire bites your arm." if d["burned"] else ".")], {}


@summary("forged")
def _forged_line(world, entry, names, place, other):
    return f"Forged a {entry.data['form']}." if entry.data["success"] else "A forging failed."


@outcome("gear_refined", body_facts=False)
def _refined(world, event):
    d = event.data
    if d["success"]:
        return [f"{cap(_name(world, d['item']))} comes out of the fire a grade finer."], {}
    return [f"{cap(_name(world, d['item']))} cracks under the hammer." if d["cracked"] else "The refining fails."], {}


@summary("gear_refined")
def _refined_line(world, entry, names, place, other):
    return "Refined a piece a grade." if entry.data["success"] else "A refining failed."


@outcome("masterwork_named", body_facts=False)
def _named(world, event):
    return [f"You cut the name into the tang: {event.data['name']}. It will be known."], {}


@summary("masterwork_named")
def _named_line(world, entry, names, place, other):
    return f"Named a masterwork {entry.data['name']}."


@outcome("formation_studied", body_facts=False)
def _studied(world, event):
    return [f"You work through the diagrams until {FM.PATTERNS[event.data['pattern']]['name']} is yours."], {}


@summary("formation_studied")
def _studied_line(world, entry, names, place, other):
    return f"Learnt {FM.PATTERNS[entry.data['pattern']]['name']}."


@outcome("formation_laid", body_facts=False)
def _laid(world, event):
    name = FM.PATTERNS[event.data["pattern"]]["name"]
    if event.data["success"]:
        return [f"The last flag goes in and {name} closes around the place."], {}
    return [f"A flag is out of true: {name} never closes, and the flags are spent."], {}


@summary("formation_laid")
def _laid_line(world, entry, names, place, other):
    name = FM.PATTERNS[entry.data["pattern"]]["name"]
    return f"Laid {name} in {place}." if entry.data["success"] else f"Failed to lay {name}."


@outcome("manual_bought", body_facts=False)
def _manual(world, event):
    return [f"{cap(_name(world, event.actors[1]))} sells you a manual of "
            f"{FM.PATTERNS[event.data['pattern']]['name']} for {event.data['price']} silver."], {}


@summary("manual_bought")
def _manual_line(world, entry, names, place, other):
    return f"Bought a formation manual from {other}."


@outcome("flags_bought", body_facts=False)
def _flags(world, event):
    return [f"{event.data['count']} formation flags, for {event.data['price']} silver."], {}


@summary("flags_bought")
def _flags_line(world, entry, names, place, other):
    return f"Bought formation flags from {other}."


@outcome("formation_commissioned", body_facts=False)
def _commissioned(world, event):
    return [f"{cap(_name(world, event.actors[1]))} walks the ground and lays "
            f"{FM.PATTERNS[event.data['pattern']]['name']} for you."], {}


@summary("formation_commissioned")
def _commissioned_line(world, entry, names, place, other):
    return f"Had {other} lay a formation in {place}."


@outcome("forge_commissioned", body_facts=False)
def _forge_commissioned(world, event):
    return [f"{cap(_name(world, event.actors[1]))} takes {event.data['price']} silver: come back in ten days."], {}


@summary("forge_commissioned")
def _forge_commissioned_line(world, entry, names, place, other):
    return f"Commissioned {other} to forge a {entry.data['form']}."


@outcome("commission_collected", body_facts=False)
def _collected(world, event):
    return [f"{cap(_name(world, event.actors[1]))} hands over the {event.data['form']}, still warm."], {}


@summary("commission_collected")
def _collected_line(world, entry, names, place, other):
    return f"Collected a {entry.data['form']} from {other}."


@outcome("meet_entered", body_facts=False)
def _entered(world, event):
    return [f"The judges look it over and mark {event.data['score']}."], {}


@summary("meet_entered")
def _entered_line(world, entry, names, place, other):
    return f"Showed a piece at the Meet of Hammer and Furnace in {place}."


@outcome("meet_decided", body_facts=False)
def _decided(world, event):
    return [f"The Meet is over: {event.data['name']} wins at "
            f"{'the anvil' if event.data['craft'] == 'forging' else 'the furnace'}."], {}


@summary("meet_decided")
def _decided_line(world, entry, names, place, other):
    return f"Won at the Meet of Hammer and Furnace, year {entry.data['year']}."
```

`narrate/grammar/crafts.toml`:
```toml
# Forging and formations (phase 5d): the forge, the arrays, and the Meet.

[symbols]
forge_air = ["Sparks jump from the anvil.", "The bellows breathe in and out.", "Hot iron ticks as it cools.", "Soot hangs under the rafters.", "Water hisses in the quench barrel.", "The hammer rings twice."]
array_air = ["The wind turns where it should not.", "A flag stirs with no wind to stir it.", "Shadows sit a little off their marks.", "The ground hums under your feet.", "Birds will not land here.", "The light bends at the edge of the array."]
meet_air = ["Crowds press along the judges' tables.", "Blades glitter on red cloth.", "Pill smoke and forge smoke mingle.", "A herald calls the next name.", "Merchants haggle over the losers' work.", "The judges confer behind a screen."]

[material_bought]
colour = "dim"
lines = ["#forge_air#"]

[beast_parts_taken]
colour = "dim"
lines = ["#forge_air#"]

[forge_bought]
colour = "dim"
lines = ["#forge_air#"]

[forged]
colour = "dim"
lines = ["#forge_air#"]

[gear_refined]
colour = "dim"
lines = ["#forge_air#"]

[masterwork_named]
colour = "dim"
lines = ["#forge_air#"]

[forge_commissioned]
colour = "dim"
lines = ["#forge_air#"]

[commission_collected]
colour = "dim"
lines = ["#forge_air#"]

[formation_studied]
colour = "dim"
lines = ["#array_air#"]

[formation_laid]
colour = "dim"
lines = ["#array_air#"]

[manual_bought]
colour = "dim"
lines = ["#array_air#"]

[flags_bought]
colour = "dim"
lines = ["#array_air#"]

[formation_commissioned]
colour = "dim"
lines = ["#array_air#"]

[meet_entered]
colour = "dim"
lines = ["#meet_air#"]

[meet_decided]
colour = "dim"
lines = ["#meet_air#"]
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crafts_play.py`
Expected: `12 failed`: the engine has no handlers for the new verbs until Step 4 puts the mixin into `Game`.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5d_task7.py`:
```python
"""Phase 5d, Task 7: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('engine/game.py', r'''from engine.alchemy_world import AlchemyWorldMixin
''', r'''from engine.alchemy_world import AlchemyWorldMixin
from engine.crafts import CraftsMixin
''')
edit('engine/game.py', r'''class Game(AlchemyWorldMixin, AlchemyMixin,''', r'''class Game(CraftsMixin, AlchemyWorldMixin, AlchemyMixin,''')
edit('engine/game.py', r'''    ("  guild | clinic | doctors | pill hall | night | bound | read <scroll> | treat <name>: the alchemy world",
     "system"),''', r'''    ("  guild | clinic | doctors | pill hall | night | bound | read <scroll> | treat <name>: the alchemy world",
     "system"),
    ("  crafts | anvil | meet | lay <pattern> | forge <form>: forging and formations", "system"),''')
edit('engine/commands.py', r'''    "bound": Action("bound_menu"), "read": Action("read_scroll"), "remedies": Action("remedies"),''', r'''    "bound": Action("bound_menu"), "read": Action("read_scroll"), "remedies": Action("remedies"),
    "crafts": Action("crafts"), "anvil": Action("anvil"), "forge": Action("anvil"), "meet": Action("meet"),
    "clear anvil": Action("clear_anvil"),''')
edit('engine/commands.py', r'''    "feed": "feed_servant",''', r'''    "feed": "feed_servant", "lay": "lay_formation", "forge": "forge",''')
edit('engine/sheet.py', r'''    from engine.alchemy_world_page import sheet_alchemy_world_lines  # phase 5c
    lines += sheet_alchemy_world_lines(world, player_id)''', r'''    from engine.alchemy_world_page import sheet_alchemy_world_lines  # phase 5c
    lines += sheet_alchemy_world_lines(world, player_id)
    from engine.crafts_page import sheet_crafts_lines  # phase 5d
    lines += sheet_crafts_lines(world, player_id)''')
edit('narrate/outcomes.py', r'''import narrate.alchemy_world_text  # noqa: E402,F401
''', r'''import narrate.alchemy_world_text  # noqa: E402,F401
import narrate.crafts_text  # noqa: E402,F401
''')
edit('tests/test_game.py', r"""<= {"ask", "farewell", "challenge", "spar", "learn_menu", "browse", "news", "tell_menu"}""", r"""<= {"ask", "farewell", "challenge", "spar", "learn_menu", "browse", "news", "tell_menu",
                                                                "craft_talk"}  # phase 5d: a smith or a formation master""")
print("task 7 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5d_task7.py`
Expected: `task 7 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crafts_play.py`
Expected: `12 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1439 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the player's crafts - the anvil, the crafts page, masters in conversation, and the Meet"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 8: Forging and formations end to end

The fork guide's section 13, the speed of a season of NPC crafts, of a fighter inside an array and of the new menus, and a wandering smith played at random.

**Files:**
- Create: `tests/test_crafts_fuzz.py`
- Create: `tests/test_crafts_season.py`
- Modify (by `.patches/5d_task8.py`): `docs/world-events.md`

**Interfaces:**
- Consumes: Everything above.
- Produces:
  - `docs/world-events.md` section 13; `tests/test_crafts_fuzz.py`: `test_a_wandering_smith`.

- [ ] **Step 1: Write the tests**

`tests/test_crafts_fuzz.py`:
```python
"""A wandering smith, played at random (phase 5d): buys iron, butchers, forges, refines, names, studies, lays
arrays and fights in them, commissions and enters the Meet; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing

WORDS = ["crafts", "anvil", "forge", "clear anvil", "meet", "study", "smith", "look", "rest", "journal", "challenge",
         "lay confusion", "lay killing", "lay binding", "lay seclusion", "lay concealment"]


@pytest.mark.parametrize("seed", [9, 31])
def test_a_wandering_smith(tmp_path, seed):
    import systems.formations as FM
    import systems.materials as M
    import systems.meet as MT
    from world.events import commit
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Smith{seed}", world_seed=seed)
    world = app.game.world
    me = world.get_meta("player_id")
    world.update_data(me, silver=5000)
    for name in ("iron ingot", "iron ingot", "black steel", "black steel", "spirit iron", "beast bone", "beast core"):
        M.make_material(world, name, me)
    for key in ("confusion", "killing", "binding", "seclusion", "concealment"):
        FM.learn(world, me, key)
    FM.add_flags(world, me, 40)
    commit(world, MT.open_events(world, 0))
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
            app.submit(rng.choice(WORDS))
        if rng.random() < 0.05:
            app.handle_key("f4", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    done = happened & {"forged", "gear_refined", "material_bought", "formation_laid", "formation_studied",
                       "flags_bought", "forge_bought", "masterwork_named", "meet_entered"}
    assert len(done) >= 3, done
    app.shutdown()
```

`tests/test_crafts_season.py`:
```python
import gc
import time
from pathlib import Path

import pytest

import systems.craft_world as CW
import systems.encounters as encounters
import systems.formations as FM
import systems.lives as lives
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
from systems.duel import fighter_for


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


def test_the_fork_guide_covers_the_crafts():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("materials.toml", "formations.toml", "forge_mastery", "knows_formation", "formations", "flags",
                 "craft_skill", "commissions", "`meet`", "check_crafts"):
        assert word in guide, word


class _Undo(Exception):
    pass


def test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5cs(game, monkeypatch):
    """The same 200 people live the same season again and again, rolled back, with and without the craft agenda."""
    from tests.test_alchemy_world_season import crowd
    world = game.world
    everything = list(lives.AGENDAS)
    before = [a for a in everything if a is not CW.season_events]
    people = crowd(world, game.place.id, "crafts")
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

    timings = {"5c": [], "5d": []}
    for n in range(12):
        which = "5c" if n % 2 == 0 else "5d"
        timings[which].append(season(before if which == "5c" else everything))
    total = {k: sum(sorted(v)[:-1]) for k, v in timings.items()}
    assert total["5d"] <= 1.10 * total["5c"] + 0.016, timings


def test_a_fighter_inside_an_array_is_quick_to_weigh(game):
    world, me = game.world, game.player.id
    plain = average(lambda: fighter_for(world, me, None), n=50)
    FM.place_formation(world, game.place.id, "killing", me, 1.0)
    FM.place_formation(world, game.place.id, "confusion", me, 1.0)
    assert average(lambda: fighter_for(world, me, None), n=50) <= 1.10 * plain + 0.0003


def test_the_crafts_anvil_and_meet_menus_are_quick(game):
    import systems.materials as M
    world, me = game.world, game.player.id
    for name in ("iron ingot", "black steel", "spirit iron"):
        M.make_material(world, name, me)
    for key in FM.PATTERNS:
        FM.learn(world, me, key)
    FM.add_flags(world, me, 50)
    for verb in ("crafts", "anvil", "smith"):
        assert average(lambda: game.perform(Action(verb))) < 0.02, verb
```

- [ ] **Step 2: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crafts_fuzz.py tests/test_crafts_season.py`
Expected: `1 failed, 5 passed`: the fork guide has no section 13 yet; the speed tests and the fuzz already pass.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5d_task8.py`:
```python
"""Phase 5d, Task 8: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('docs/world-events.md', r'''recipe, and the bound index to the living bound of living people.
''', r'''recipe, and the bound index to the living bound of living people.

## 13. Forging and formations (phase 5d)

**Materials** are entities (`kind = "material"`: a `material` name and its `grade`, 0-4) of the table in
`systems/data/materials.toml` (grade, price, the towns whose smith sells it, or how else it is had). 4d's star iron
counts as a material of grade 3 (`materials.material_info`). A smith's ore is a seeded stock by the season (town data
`ore_sold`). A forge is an entity the player owns, a smith's rented for the day, or the own sect's `forge` building.

**Forging** keeps a person's `forge_mastery` (`{form: mastery}`) and `forge_xp`; a forged item is 5a's gear with
`forged_by`. A named masterwork joins 5a's `famous_weapons` with a `blade_legend` fact. `World.rename` renames an
entity.

**Formations** are the patterns of `systems/data/formations.toml` (use, flags, difficulty, days). A person knows one
through a `knows_formation` relation to the pattern entity (`formation:{key}`), whose value is its mastery, and keeps
`formation_xp`. Flags are one `flags` item with a `count`; manuals are `formation_manual` items. What is laid lives on
the town (`formations`: `{pattern, owner, until, strength}`), read by `formations.laid` and `strength`.

**Where the rules live:**
- `systems/materials.py`, `systems/forging.py`: materials, the forge, forging, refining, masterworks.
- `systems/formations.py`: patterns, manuals, flags, laying, and 4f's formation trials (`trial_bonus`).
- `systems/arrays.py`: what formations do, read where each rule lives (3c's gate, 5c's theft, 2b's fighters and
  fleeing, 2b's challengers, 2a's meditation).
- `systems/craft_world.py`: smiths' and formation masters' `craft_skill` (a lives agenda), their wares, and
  `commissions` (a person's list of forgings awaited).
- `systems/meet.py`: the Meet of Hammer and Furnace, one meta row (`meet`), opened each spring and decided after.

**The rules:** `check_crafts` in `debug/invariants.py` holds materials to the table, masteries within 0-1, flags to at
least one, formations laid to a pattern and a person, craft skills within 1-5, a named masterwork to the famous index,
and the Meet to a town and a span.
''')
print("task 8 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5d_task8.py`
Expected: `task 8 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crafts_fuzz.py tests/test_crafts_season.py`
Expected: `6 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1445 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Run the 500-year soak**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: forging and formations end to end - the fork guide, speed, and a wandering smith's fuzz"
```

The message ends with the session's Co-Authored-By attribution line.

---

## Self-review

- **Spec coverage:**
  - §2 materials and the forge (Task 1); §3 forging, refining, masterworks (Task 2);
  - §4 patterns, manuals, flags, laying, realm trials (Task 3; rulings 11, 12); §5 what formations do (Task 4; rulings 6, 13, 14);
  - §6 smiths, formation masters, commissions (Task 5) and the Meet (Task 6); §7 the player (Task 7);
  - §8 knowledge (Tasks 5, 7; ruling 9); §9 `check_crafts` (Tasks 1-6); §10 level of detail and speed (Task 8); §11 testing (every task; the fuzz and speed in Task 8).
- **Dry run:**
  - every task was applied in order to a copy of master at ca1a07a: its new files, the run of Step 3 as it says, its edits, then the green run;
  - the whole suite passed after every task, and the 500-year soak passed at the end, but for one run: after Task 5,
    4e's `test_an_assembly_round_resolves_quickly`, which times a single round once, took over 60 ms. It measures
    about 21 ms with 5d and 20.5 ms on master, and passed on every other run; it is made to average its timing in
    5d's minors.
