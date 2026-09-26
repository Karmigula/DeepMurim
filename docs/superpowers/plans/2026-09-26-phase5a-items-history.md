# Phase 5a: Items with History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Weapons and armour become real things that matter in a fight and carry their past.
- A blade's grade strengthens the arts of its form, a weapon art fought bare-handed is weaker, and armour softens wounds.
- Every notable item remembers its maker, its owners and its deeds.
- Famous weapons are known by legend, change hands, and are ranked each spring.

**Architecture:**
- **Gear** is an entity (`kind = "gear"`), held through `owns`; a person `wields` one weapon and `wears` one armour.
- **Lazy gear:** an NPC's gear is only a seeded grade (`gear.seeded`) until it matters. Then `gear.materialize` makes the item, its history begun. The player's first weapon is carried the same way.
- **Combat** reads gear in one place, `duel.fighter_for`. It feeds `Fighter.weapon_mult` into `combat_core.technique_power` and `Fighter.weapon_grade` into breakage. So NPC-against-NPC fights (`duel_sim`) weigh gear too.
- **The other modules**, one concern each:
  - `provenance` (deeds, legends, recognition);
  - `famous` (named blades, heirlooms, the Chronicle);
  - `smithy`, `armoury` and `spoils` (the sources);
  - `GearMixin` (`engine/gear.py`), the player's part, over them all.

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-phase5a-items-history-design.md`

## Global Constraints

- **Save format:** no save-format version change.
  - New state lives in `gear` entities.
  - Person data: `gear`, `drew_treasure`.
  - Faction data: `armoury`.
  - Town data: `smith_sold`.
  - The Pavilion's `weapons`.
  - The meta rows `famous_weapons` and `famous_keys`.
- **Knowledge vs truth:**
  - an item's page names only the owners the player has met or heard of, and only the deeds they did or believe a tale of;
  - recognition and the scene brief read beliefs only.
- **Reads never write:**
  - a page, a brief, `gear.seeded` or `gear.weapon_mult` never makes an item;
  - making gear real is an action (taking, buying, inspecting your own plain weapon, a deed).
- **One effect per event kind:** new modules use `@listen` on existing kinds.
- **The entity cache (4e):** all gear state is written through `update_data`.
- **Seeded rolls stay where they were:** gear adds no draw to an existing random stream. Breakage has its own stream, and the player's first weapon adds no entity.
- **Speed (CPU time, `time.process_time`, averaged after `gc.collect()`):**
  - gear adds under 1 ms to a fighter's setup;
  - the Chronicle's survey takes under 20 ms;
  - a turn carrying a known blade takes under 50 ms;
  - the 500-year soak keeps its limits.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Taking a lawful person's weapon.**
   - The law calls it robbery, and a proud loser hates you for it.
   - Task 4 pins it with `test_taking_from_the_beaten_is_remembered_and_robbery_if_lawful`.
2. **A sect recognizes its blade on you.**
   - It demands it back; refusing lowers your standing with it.
   - Task 2 pins it with `test_a_sect_thinks_better_of_one_who_gives_back_and_worse_of_one_who_keeps`; Task 5 with `test_those_who_know_your_blade_speak_up`.
3. **A blade breaks mid-fight.**
   - The broken item stays yours, with its history, and fights as bare hands.
   - Task 1 pins it with `test_the_lesser_blade_may_break`.
4. **Leaving a sect with its armoury's blade.**
   - It is theft: a `stole` fact, and the sect claims the blade.
   - Task 4 pins it with `test_leaving_with_the_armourys_blade_is_theft`.
5. **Random play through buying, drawing, taking, wielding and selling.**
   - No crash, no rule broken.
   - Task 6 pins it with `test_an_armed_wanderer`.

## Plan-time rulings (deviations from the spec, argued)

1. **Armour softens the wound, not the fight.** Its share comes off the damage a wound is judged from; the fight's harm is unchanged. Wound severities are whole numbers 1-5, so 10-30% off a severity would rarely change anything. *Cost if wrong:* armour does not shorten fights.
2. **The player's first weapon is carried gear, not an item:** an iron weapon of their first art's form, written as data at creation. An item made at creation shifted every later entity id, and with them every roll seeded by an id. The first weapon is made real the way an NPC's is. *Cost if wrong:* none visible.
3. **Every NPC who fights with a weapon art carries at least an iron one.** The spec gave unranked commoners none: that fights bandits and hunters at ×0.6 and upset every balance the earlier phases tested. *Cost if wrong:* commoners hit as hard as before.
4. **Breakage rolls on its own seeded stream** (`duel:{id}:{n}:blades`), so the fight's own rolls are untouched. *Cost if wrong:* none.
5. **A deed is kept as `{event, kind, whom, weight}`** rather than a bare event id, so the twelve weightiest are kept without a lookup. `check_gear` checks `event`. *Cost if wrong:* none.
6. **Famous weapons are seeded per keeper, not per region:**
   - a great sect's master holds its treasure, and a clan keeps its heirloom (lost with chance 0.3), each once its master stands in the world;
   - a city's wandering master is one already living there;
   - nothing is made for a famous weapon, and seeding is tried each spring.
   - Regions have no keepers of their own, and making masters would move every later entity id. *Cost if wrong:* fewer famous blades in the wilds.
7. **A duel for a weapon follows 4g's duel for a token** (a duel `purpose`). 4e's wagers are bets on others' bouts, not staked duels. A covetous fighter's challenge stakes your blade. *Cost if wrong:* none.
8. **A sect's "stance toward the player" is 3b's standing, read from facts:**
   - `returned_gear`, weight 0.5, counts +1;
   - `kept_gear`, weight 1.0, counts -1;
   - `stole`, weight 1.5, counts -1.
   - The spec's +0.1 and -0.2 were written for faction-to-faction stance. *Cost if wrong:* the swings are larger than the spec's numbers.
9. **Taking from the lawful is `robbed` (3b's law reads it); carrying off an armoury's gear is `stole`,** which the law now counts for a faction target. *Cost if wrong:* none.
10. **Far away, a tournament won never passes a famous weapon.** No far tournament is fought for a weapon. Famous weapons pass far away only at deaths. *Cost if wrong:* fewer far changes of hands.
11. **A bearer who belongs to the clan or sect that claims a blade is never asked for it,** and a covetous fighter challenges at most once a visit. *Cost if wrong:* none.
12. **The character sheet folds gear into lines it already has.** Each weapon art's line names the weapon and its multiplier, and the insight line names the armour. The F4 window shows the sheet's tail, and three new lines pushed `Arts:` off it. *Cost if wrong:* none.
13. **Routine gear narration is dim** (the repeat rule allows dim lines to come round again). A returned heirloom's gold line has six variants, as the variety rule asks. *Cost if wrong:* none.
14. **Two latent faults the fuzz reached once the new choices moved its path:**
    - a crisis heralded after every claimant was struck names no one (4g raised an `IndexError`);
    - 4f's realm narration, six lines shared by nearly every realm event, repeated; it gains eight more.
    - *Cost if wrong:* none.
15. **Inspecting your own plain weapon makes it an item.** The player cannot open others' item pages. *Cost if wrong:* none.

## Files

| File | Responsibility |
|---|---|
| `systems/gear.py` | Grades, what someone carries, items, taking up and putting away, passing hands, breakage, the heir's inheritance. |
| `systems/provenance.py` | Deeds, legends, knowing a blade on sight, and what people do about it. |
| `systems/famous.py` | Famous weapons, how they pass, heirlooms, epithets, the Hundred Weapons Chronicle. |
| `systems/smithy.py` | The smith's stall. |
| `systems/armoury.py` | A sect's armoury. |
| `systems/spoils.py` | What the fallen carried. |
| `engine/gear.py` | `GearMixin`: choices, menus, the scene's reactions, handlers. |
| `engine/gear_page.py` | The inventory, an item's page, the sheet's notes, the Chronicle. |
| `narrate/gear_text.py`, `narrate/grammar/gear.toml` | Tales, deed lines, the brief's blades. |

Existing files touched: `systems/combat_core.py`, `systems/duel.py`, `systems/creation.py`, `systems/standing.py`, `systems/law.py`, `systems/realm_gates.py`, `systems/world_clock.py`, `systems/succession_crisis.py`, `debug/invariants.py`, `narrate/outcomes.py`, `narrate/brief.py`, `narrate/grammar/realm.toml`, `engine/game.py`, `engine/commands.py`, `engine/sheet.py`, `engine/sky.py`, `docs/world-events.md`.

**How each task is laid out:**
1. The tests, as whole new files.
2. The red run.
3. The new modules, as whole files.
4. One patch script, `.patches/5a_taskN.py`, holding the task's edits to existing files (including files made by earlier tasks). Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: Gear, grades, and the fight

Weapons and armour as items with owners, and gear an NPC carries as a seeded grade until it matters. A weapon's grade multiplies the arts of its form (a near form at x0.85, bare hands x0.6); armour takes its share off the damage a wound is judged from (ruling 1); a blade two grades below its foe may break, on its own roll (ruling 4). The hero's first weapon is carried gear (ruling 2). `check_gear` joins the rules.

**Files:**
- Create: `systems/gear.py`
- Create: `tests/test_gear.py`
- Modify (by `.patches/5a_task1.py`): `debug/invariants.py`, `systems/combat_core.py`, `systems/creation.py`, `systems/duel.py`

**Interfaces:**
- Consumes: 2's `duel.fighter_for`, `duel.best_art`, `duel.ensure_npc_arts`, `combat_core.Fighter`/`technique_power`/`wound`; 3b's `F.memberships`; `creation.apply_creation`.
- Produces:
  - `gear`: `GRADES`, `GRADE_WORDS`, `POWER`, `ARMOUR_SHARE`, `WEAPON_FORMS`, `NEAR`, `NEAR_MULT`, `UNARMED`, `ARMOURS`, `ARMOUR_WORDS`, `BREAK_GAP`, `BREAK_CHANCE`, `MAX_DEEDS`, `SLOTS = {weapon: wields, armour: wears}`; `seeded(world, p) -> {weapon, armour}`, `carried(world, p)`, `item_in(world, p, slot)`, `weapon_of(world, p) -> {grade, form, item, broken} | None`, `armour_of`, `weapon_mult(world, p, form)`, `armour_share(world, p)`, `weapon_grade(world, p, form)`, `gear_name(slot, form, grade)`, `make_item(world, slot, form, grade, owner, how, maker=None, name=None, path=None, **extra) -> int`, `gear_items(world, p)`, `best_weapon_form(world, p)`, `materialize(world, p, slot) -> int | None`, `fits(world, p, item, slot)`, `wield_events`, `put_away_events`, `pass_events(world, giver, taker, item, place, how)`, `break_events`, `starting_weapon(world, p, form)`; events `gear_taken_up`, `gear_put_away`, `gear_passed`, `weapon_broke`.
  - `Fighter.weapon_mult`, `Fighter.weapon_grade`; `duel._blow(..., armour=0.0)`, `duel._breakage`; `debug.invariants.check_gear(world)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_gear.py`:
```python
import random

import pytest

import systems.duel as duel
import systems.gear as gear
from debug.invariants import check_gear
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.combat_core import technique_power
from systems.creation import CreationChoice
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def sect_staff(world, role):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    return sect, seat, halls.staff_at(world, sect, seat, roles=(role,))


def commoner(game, tag="c", occupation="tea seller"):
    data = {"occupation": occupation, "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", data, seed_path=f"test:gear:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def my_art_form(game):
    return duel.best_art(game.world, game.player.id).form


def test_a_blade_strengthens_the_arts_of_its_form(game):
    world, me = game.world, game.player.id
    sword = gear.make_item(world, "weapon", "sword", 3, me, "bought")
    commit(world, gear.wield_events(world, me, sword, game.place.id))
    assert gear.weapon_mult(world, me, "sword") == gear.POWER[3]
    assert gear.weapon_mult(world, me, "saber") == pytest.approx(gear.POWER[3] * gear.NEAR_MULT)
    assert gear.weapon_mult(world, me, "spear") == gear.UNARMED
    assert gear.weapon_mult(world, me, "palm") == 1.0  # a hand art needs nothing
    world.update_data(sword, broken=True)
    assert gear.weapon_mult(world, me, "sword") == gear.UNARMED


def test_an_npc_carries_a_seeded_grade_and_no_item(game):
    world = game.world
    before = len(world.entities("gear"))
    sect, seat, elders = sect_staff(world, "elder")
    _, _, [keeper] = sect_staff(world, "keeper")
    assert gear.seeded(world, elders[0]) == {"weapon": 2, "armour": 1}  # an elder: spirit steel, fine armour
    assert gear.seeded(world, keeper)["weapon"] >= 1
    someone = commoner(game)
    assert gear.seeded(world, someone) == {"weapon": 0, "armour": None}  # an iron blade, and cloth
    assert gear.weapon_mult(world, someone, "saber") == 1.0  # their blade is for their art
    assert len(world.entities("gear")) == before  # reading gear makes nothing


def test_what_an_npc_carries_is_made_real_once(game):
    world = game.world
    sect, seat, elders = sect_staff(world, "elder")
    form = gear.best_weapon_form(world, elders[0])
    made = gear.materialize(world, elders[0], "weapon")
    if form is None:
        assert made is None  # a hand art: nothing to make
        return
    item = world.entity(made)
    assert item.data["grade"] == 2 and item.data["form"] == form
    assert item.data["owners"] == [{"person": elders[0], "since": world.time, "how": "carried"}]
    assert gear.materialize(world, elders[0], "weapon") == made
    assert gear.carried(world, elders[0])["weapon"] is None and gear.weapon_of(world, elders[0])["item"] == made
    assert check_gear(world) == []


def test_the_hero_starts_with_a_plain_weapon_for_their_art(game):
    world, me = game.world, game.player.id
    form = my_art_form(game)
    if form in gear.WEAPON_FORMS:
        assert gear.weapon_of(world, me) == {"grade": 0, "form": form, "item": None, "broken": False}
        assert gear.weapon_mult(world, me, form) == 1.0
    else:
        assert gear.weapon_of(world, me) is None


def test_a_fighter_strikes_harder_with_a_better_blade(game):
    world, me = game.world, game.player.id
    art = duel.best_art(world, me)
    if art.form not in gear.WEAPON_FORMS:
        pytest.skip("a hand art")
    plain = technique_power(duel.fighter_for(world, me, art.technique.id))
    blade = gear.make_item(world, "weapon", art.form, 4, me, "found")
    commit(world, gear.wield_events(world, me, blade, game.place.id))
    assert technique_power(duel.fighter_for(world, me, art.technique.id)) == pytest.approx(plain * gear.POWER[4])


def test_armour_softens_the_wound_not_the_fight(game):
    bare = duel._blow("player", 40.0, "saber", random.Random(1), False)
    armed = duel._blow("player", 40.0, "saber", random.Random(1), False, armour=0.3)
    assert bare["damage"] == armed["damage"] == 40.0
    assert armed["wound"][2] < bare["wound"][2]


def test_the_lesser_blade_may_break(game, monkeypatch):
    monkeypatch.setattr(gear, "BREAK_CHANCE", 1.0)
    world, me = game.world, game.player.id
    art = duel.best_art(world, me)
    if art.form not in gear.WEAPON_FORMS:
        pytest.skip("a hand art")
    mine = gear.make_item(world, "weapon", art.form, 0, me, "bought")
    commit(world, gear.wield_events(world, me, mine, game.place.id))
    foe = commoner(game, "foe", occupation="bandit")
    world.update_data(foe, gear={"weapon": 3, "armour": None})
    [started] = commit(world, duel.start_events(world, me, foe, game.place.id, "duel"))
    d = duel.Duel.from_event(started, world.chronicle_entry(started))
    events = duel.exchange_events(world, d, "strike")
    if events[0].data.get("broke") is None:
        pytest.skip("they did not meet blade to blade")  # the foe fought with a hand art
    commit(world, events)
    assert events[0].data["broke"] == "player" and world.entity(mine).data["broken"]
    assert gear.weapon_mult(world, me, art.form) == gear.UNARMED


def test_gear_changes_hands_and_remembers(game):
    world, me = game.world, game.player.id
    someone = commoner(game, "giver")
    world.update_data(someone, gear={"weapon": 1, "armour": None, "form": "saber"})
    item = gear.materialize(world, someone, "weapon")
    commit(world, gear.pass_events(world, someone, me, item, game.place.id, "taken"))
    history = world.entity(item).data["owners"]
    assert [h["person"] for h in history] == [someone, me] and history[-1]["how"] == "taken"
    assert world.targets(someone, "wields") == [] and gear.weapon_of(world, someone) is None
    commit(world, gear.wield_events(world, me, item, game.place.id))
    assert gear.item_in(world, me, "weapon").id == item and check_gear(world) == []
    other = gear.make_item(world, "weapon", "spear", 0, me, "bought")
    world.relate(me, other, "wields")
    assert any("at once" in p for p in check_gear(world))
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gear.py`
Expected: `ModuleNotFoundError: No module named 'systems.gear'`.

- [ ] **Step 3: Write the new modules**

`systems/gear.py`:
```python
"""Weapons and armour (phase 5a spec 2): grades, gear an NPC carries without it being made, and items with a past.

An NPC's gear is only a seeded grade (`seeded`) until it matters: taken, bought, inherited, looked at, or its
wielder killed by the player. Then `materialize` makes it an item that remembers its maker, its owners and its
deeds. A person wields at most one weapon (`wields`) and wears one armour (`wears`), each an item they own.
"""

from systems import factions as F
from systems.realms import realm_index
from world.events import Event, effect
from world.seed import rng_for

GRADES = ("iron", "fine", "spirit", "treasure", "divine")
GRADE_WORDS = ("iron", "fine steel", "spirit-steel", "treasure", "divine")
POWER = (1.0, 1.15, 1.3, 1.5, 1.8)
ARMOUR_SHARE = (0.10, 0.15, 0.20, 0.25, 0.30)
WEAPON_FORMS = ("sword", "saber", "spear", "staff")
NEAR = {"sword": "saber", "saber": "sword", "spear": "staff", "staff": "spear"}
NEAR_MULT, UNARMED = 0.85, 0.6
ARMOURS = ("robe", "mail", "inner_vest")
ARMOUR_WORDS = {"robe": "padded robe", "mail": "mail vest", "inner_vest": "silk inner vest"}
BREAK_GAP, BREAK_CHANCE = 2, 0.05
MAX_DEEDS = 12
REALM_GRADE = (0, 0, 1, 2, 2, 3, 3, 4)  # by realm index: mortal and third-rate iron ... life-and-death divine
ROLE_GRADE = {"disciple": 0, "keeper": 1, "elder": 2, "leader": 2}
ARMED = frozenset({"keeper", "elder", "leader"})  # those of rank wear armour; others go in cloth
SLOTS = {"weapon": "wields", "armour": "wears"}


# --- what someone carries ----------------------------------------------------------------------------

def seeded(world, person: int) -> dict:
    """What an NPC carries before anyone looks: a weapon grade (its form is their art's) and an armour grade."""
    data = world.entity(person).data
    if data.get("is_player") or data.get("beast"):
        return {"weapon": None, "armour": None}  # the player's own is written at creation
    grade, role_best = REALM_GRADE[min(realm_index(data.get("realm", "mortal")), len(REALM_GRADE) - 1)], None
    for fid, _, d in F.memberships(world, person):
        if d.get("status", "member") != "member" or d.get("role") not in ROLE_GRADE:
            continue
        role_grade = ROLE_GRADE[d["role"]]
        if d["role"] == "leader" and world.entity(fid).data.get("tier") == "great":
            role_grade = 3  # a great sect's master carries a treasure
        grade = max(grade, role_grade)
        role_best = d["role"] if role_best is None or ROLE_GRADE[d["role"]] > ROLE_GRADE[role_best] else role_best
    armour = max(0, grade - 1) if role_best in ARMED else None
    return {"weapon": grade, "armour": armour}


def carried(world, person: int) -> dict:
    """The gear a person carries without an item: their own record once any was made real, else the seeded."""
    data = world.entity(person).data
    return data["gear"] if data.get("gear") is not None else seeded(world, person)


def item_in(world, person: int, slot: str):
    found = world.targets(person, SLOTS[slot])
    return world.entity(found[0]) if found else None


def weapon_of(world, person: int) -> dict | None:
    """{grade, form (None: whatever their art), item, broken}, or None for bare hands."""
    item = item_in(world, person, "weapon")
    if item is not None:
        return {"grade": item.data["grade"], "form": item.data["form"], "item": item.id,
                "broken": bool(item.data.get("broken"))}
    gear = carried(world, person)
    grade = gear.get("weapon")
    return None if grade is None else {"grade": grade, "form": gear.get("form"), "item": None, "broken": False}


def armour_of(world, person: int) -> dict | None:
    item = item_in(world, person, "armour")
    if item is not None:
        return {"grade": item.data["grade"], "item": item.id}
    grade = carried(world, person).get("armour")
    return None if grade is None else {"grade": grade, "item": None}


def weapon_mult(world, person: int, form: str) -> float:
    """How a weapon art fares with what they hold (spec 2.2); arts of the hand need nothing."""
    if form not in WEAPON_FORMS:
        return 1.0
    w = weapon_of(world, person)
    if w is None or w["broken"]:
        return UNARMED
    if w["form"] is None or w["form"] == form:
        return POWER[w["grade"]]
    if NEAR.get(w["form"]) == form:
        return round(POWER[w["grade"]] * NEAR_MULT, 4)
    return UNARMED


def armour_share(world, person: int) -> float:
    a = armour_of(world, person)
    return 0.0 if a is None else ARMOUR_SHARE[a["grade"]]


def fighting(world, person: int, form: str) -> tuple[float, int | None]:
    """(weapon_mult, weapon_grade) for a fighter of this form, from one look at what they hold."""
    if form not in WEAPON_FORMS:
        return 1.0, None
    w = weapon_of(world, person)
    if w is None or w["broken"]:
        return UNARMED, None
    if w["form"] is None or w["form"] == form:
        return POWER[w["grade"]], w["grade"]
    if NEAR.get(w["form"]) == form:
        return round(POWER[w["grade"]] * NEAR_MULT, 4), w["grade"]
    return UNARMED, w["grade"]


def weapon_grade(world, person: int, form: str) -> int | None:
    """The grade of the weapon a weapon art strikes with, for breakage; None with bare hands or a hand art."""
    if form not in WEAPON_FORMS:
        return None
    w = weapon_of(world, person)
    return None if w is None or w["broken"] else w["grade"]


# --- items ---------------------------------------------------------------------------------------------

def gear_name(slot: str, form: str | None, grade: int) -> str:
    word = GRADE_WORDS[grade]
    what = form if slot == "weapon" else ARMOUR_WORDS[form]
    return f"{'an' if word[0] in 'aeiou' else 'a'} {word} {what}"


def make_item(world, slot: str, form: str, grade: int, owner: int | None, how: str, maker=None,
              name: str | None = None, path: str | None = None, **extra) -> int:
    """A gear item owned by `owner` (or by no one), its history begun."""
    data = {"slot": slot, "form": form, "grade": grade, "maker": maker, "made_at": world.time,
            "owners": [{"person": owner, "since": world.time, "how": how}] if owner is not None else [],
            "deeds": [], "famous": False, "epithet": None, "armoury": None, "broken": False, **extra}
    item = world.add_entity("gear", name or gear_name(slot, form, grade), data, path)
    if owner is not None:
        world.relate(owner, item, "owns")
    return item


def gear_items(world, person: int) -> list:
    return [e for e in (world.entity(i) for i in world.targets(person, "owns")) if e is not None and e.kind == "gear"]


def best_weapon_form(world, person: int) -> str | None:
    from systems.duel import best_art, ensure_npc_arts  # the duel module builds on this one
    ensure_npc_arts(world, person)
    art = best_art(world, person)
    return art.form if art is not None and art.form in WEAPON_FORMS else None


def materialize(world, person: int, slot: str) -> int | None:
    """Make what an NPC carries real (spec 2.5): an item with its history begun, which they now wield or wear."""
    item = item_in(world, person, slot)
    if item is not None:
        return item.id
    gear = dict(carried(world, person))
    grade = gear.get(slot)
    if grade is None:
        return None
    if slot == "weapon":
        form = gear.get("form") or best_weapon_form(world, person)
        if form is None:
            return None  # a hand art: whatever they carried was not a weapon for it
    else:
        form = ARMOURS[rng_for(world.world_seed, f"gear:{person}:armour").randrange(len(ARMOURS))]
    made = make_item(world, slot, form, grade, person, "carried", path=f"gear:{person}:{slot}")
    world.relate(person, made, SLOTS[slot])
    gear[slot] = None  # now the item, not the grade
    world.update_data(person, gear=gear)
    return made


def fits(world, person: int, item_id: int, slot: str) -> str | None:
    item = world.entity(item_id)
    if item is None or item.kind != "gear" or item_id not in world.targets(person, "owns"):
        return "You do not have that."
    if item.data["slot"] != slot:
        return "That is not " + ("a weapon." if slot == "weapon" else "armour.")
    return None


def wield_events(world, person: int, item_id: int, place: int) -> list[Event]:
    slot = world.entity(item_id).data["slot"]
    return [Event("gear_taken_up", (person,), place, {"item": item_id, "slot": slot})]


def put_away_events(world, person: int, slot: str, place: int) -> list[Event]:
    item = item_in(world, person, slot)
    return [] if item is None else [Event("gear_put_away", (person,), place, {"item": item.id, "slot": slot})]


@effect("gear_taken_up")
def _taken_up(world, event) -> None:
    person, d = event.actors[0], event.data
    world.unrelate(person, SLOTS[d["slot"]])
    world.relate(person, d["item"], SLOTS[d["slot"]])


@effect("gear_put_away")
def _put_away(world, event) -> None:
    world.unrelate(event.actors[0], SLOTS[event.data["slot"]], event.data["item"])


def pass_events(world, giver: int | None, taker: int | None, item_id: int, place, how: str) -> list[Event]:
    """An item changes hands (taken, bought, sold, drawn, returned, inherited, won, given, found)."""
    actors = tuple(p for p in (taker, giver) if p is not None)
    return [Event("gear_passed", actors, place, {"item": item_id, "giver": giver, "taker": taker, "how": how})]


@effect("gear_passed")
def _passed(world, event) -> None:
    d = event.data
    item = world.entity(d["item"])
    for owner in world.sources(item.id, "owns"):
        world.unrelate(owner, "owns", item.id)
        for rel in SLOTS.values():
            world.unrelate(owner, rel, item.id)
    owners = list(item.data["owners"])
    if d["taker"] is not None:
        world.relate(d["taker"], item.id, "owns")
        owners.append({"person": d["taker"], "since": world.time, "how": d["how"]})
    world.update_data(item.id, owners=owners, lost_at=None if d["taker"] is not None else event.place)


def break_events(world, person: int, place) -> list[Event]:
    return [Event("weapon_broke", (person,), place, {})]


@effect("weapon_broke")
def _broke(world, event) -> None:
    """The lesser blade gives way: an item stays, broken, with its past; a carried grade is simply gone."""
    person = event.actors[0]
    item = item_in(world, person, "weapon")
    if item is not None:
        world.update_data(item.id, broken=True)
        return
    gear = dict(carried(world, person))
    gear["weapon"] = None
    world.update_data(person, gear=gear)


def starting_weapon(world, person: int, form: str) -> None:
    """A new hero's plain weapon for their first art, carried until it matters, as an NPC's is (plan ruling 2)."""
    if form in WEAPON_FORMS:
        world.update_data(person, gear={"weapon": 0, "armour": None, "form": form})
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5a_task1.py`:
```python
"""Phase 5a, Task 1: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('debug/invariants.py', r'''    problems += check_items(world)
''', r'''    problems += check_items(world)
    problems += check_gear(world)
''')
edit('debug/invariants.py', r'''            out.append(f"manual #{manual.id} claims less than it holds")
''', r'''            out.append(f"manual #{manual.id} claims less than it holds")
    return out


def check_gear(world) -> list[str]:
    """Weapons and armour (phase 5a spec 7): one owner, what is wielded is owned, deeds are real."""
    from systems.gear import SLOTS
    out = []
    for item in world.entities("gear"):
        owners = world.sources(item.id, "owns")
        if len(owners) > 1:
            out.append(f"{item.name} (#{item.id}) has {len(owners)} owners")
        history = item.data.get("owners") or []
        if owners and (not history or history[-1]["person"] != owners[0]):
            out.append(f"{item.name} (#{item.id}) is owned by #{owners[0]}, whom its history does not end with")
        for deed in item.data.get("deeds", []):
            if world.chronicle_entry(deed) is None:
                out.append(f"{item.name} (#{item.id}) remembers a deed that never happened (#{deed})")
        for slot, rel in SLOTS.items():
            for holder in world.sources(item.id, rel):
                if holder not in owners:
                    out.append(f"#{holder} {rel} {item.name} (#{item.id}) without owning it")
                if item.data["slot"] != slot:
                    out.append(f"#{holder} {rel} {item.name} (#{item.id}), which is no {slot}")
    for rel in SLOTS.values():
        for holder, count in world._conn.execute(
                "select a, count(*) from relations where kind = ? group by a having count(*) > 1", (rel,)):
            out.append(f"#{holder} {rel} {count} things at once")
''')
edit('systems/combat_core.py', r'''    stance_favours: str | None = None
''', r'''    stance_favours: str | None = None
    weapon_mult: float = 1.0          # what they hold, for a weapon art (phase 5a)
    weapon_grade: int | None = None   # the blade that meets the other's, for breakage
''')
edit('systems/combat_core.py', r'''    return f.grade_mult * (0.5 + f.mastery) * f.compat
''', r'''    return f.grade_mult * (0.5 + f.mastery) * f.compat * f.weapon_mult
''')
edit('systems/creation.py', r'''
from systems.techniques import FORMS, create_technique, generate, teach
''', r'''
import systems.gear as gear
from systems.techniques import FORMS, create_technique, generate, teach
''')
edit('systems/creation.py', r'''        names.append(name)
''', r'''        names.append(name)
        if data["category"] == "martial" and world.entity(person_id).data.get("gear") is None:
            gear.starting_weapon(world, person_id, data["form"])  # a plain blade for a blade art (phase 5a)
''')
edit('systems/duel.py', r'''
import systems.world_events as W
''', r'''
import systems.gear as gear
import systems.world_events as W
''')
edit('systems/duel.py', r'''    limbs = limbs_for(form)
''', r'''    limbs = limbs_for(form)
    weapon_mult, weapon_grade = gear.fighting(world, person_id, form) if art else (1.0, None)
''')
edit('systems/duel.py', r'''        stance_favours=art.technique.data["stance"]["favours"] if art else None,
''', r'''        stance_favours=art.technique.data["stance"]["favours"] if art else None,
        weapon_mult=weapon_mult, weapon_grade=weapon_grade,
''')
edit('systems/duel.py', r'''def _blow(target: str, damage: float, form: str, rng, gentle: bool) -> dict:
    hit = wound(form, damage, rng, spar=gentle)
''', r'''def _blow(target: str, damage: float, form: str, rng, gentle: bool, armour: float = 0.0) -> dict:
    hit = wound(form, damage * (1 - armour), rng, spar=gentle)  # armour softens the wound, not the fight (5a)
''')
edit('systems/duel.py', r'''    scale = GENTLE_SCALE if gentle else 1.0
''', r'''    scale = GENTLE_SCALE if gentle else 1.0
    armour = {"player": gear.armour_share(world, d.player), "opponent": gear.armour_share(world, d.opponent)}
''')
edit('systems/duel.py', r'''            data["blows"].append(_blow("player", damage, them.form, rng, gentle))
''', r'''            data["blows"].append(_blow("player", damage, them.form, rng, gentle, armour["player"]))
''')
edit('systems/duel.py', r'''                data["blows"].append(_blow(side[blow.target], blow.damage, form, rng, gentle))
''', r'''                data["blows"].append(_blow(side[blow.target], blow.damage, form, rng, gentle, armour[side[blow.target]]))
            data["broke"] = _breakage(me, them, rng_for(world.world_seed, f"duel:{d.duel_id}:{n}:blades"))
''')
edit('systems/duel.py', r'''        events.append(_end_event(world, d, ending[0], ending[1], rng, data["harm_after"], n))
    return events

''', r'''        events.append(_end_event(world, d, ending[0], ending[1], rng, data["harm_after"], n))
    return events


def _breakage(me, them, rng) -> str | None:
    """Blade on blade: two grades apart or more, the lesser may break (spec 2.2). Its own roll: the fight's is untouched."""
    if me.weapon_grade is None or them.weapon_grade is None or abs(me.weapon_grade - them.weapon_grade) < gear.BREAK_GAP:
        return None
    if rng.random() >= gear.BREAK_CHANCE:
        return None
    return "player" if me.weapon_grade < them.weapon_grade else "opponent"

''')
edit('systems/duel.py', r'''        _add_fragment(world, ids["player"], data["fragment"])
''', r'''        _add_fragment(world, ids["player"], data["fragment"])
    if data.get("broke"):
        gear._broke(world, Event("weapon_broke", (ids[data["broke"]],), event.place, {}))
''')
print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5a_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gear.py tests/test_duel.py`
Expected: `19 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: gear - grades that strengthen an art, armour that softens a wound, blades that break, gear carried until it matters

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: Deeds, legends, and knowing a blade

A weapon wielded in a notable kill, a win over a ranked fighter, or a tournament remembers it (its twelve weightiest, ruling 5); a treasure-grade or famous blade's deeds are told (`wielded_in`). Whoever believes a tale knows the blade on sight: a proud or greedy fighter covets it, the kin of those it killed hate its bearer, and the faction that claims it demands it back (3b's standing reads the answer, ruling 8).

**Files:**
- Create: `narrate/gear_text.py`
- Create: `systems/provenance.py`
- Create: `tests/test_provenance.py`
- Modify (by `.patches/5a_task2.py`): `debug/invariants.py`, `narrate/outcomes.py`, `systems/gear.py`, `systems/standing.py`

**Interfaces:**
- Consumes: Task 1's `gear` (`weapon_of`, `materialize`, `carried`, `pass_events`); 3a's `record_fact`, `known_facts_about`; 4a's `kin_of`; 4d's Pavilion (`rankings.pavilion`, `rank_of`).
- Produces:
  - `provenance`: `LEGEND_GRADE`, `KILL_WEIGHT`, `LEADER_WEIGHT`, `BESTED_WEIGHT`, `TITLE_WEIGHT`, `COVET_CHANCE`, `KIN_HATRED`, `DEED_HOOKS`; `notable(world, p)`, `remember(world, p, deed, place)`, `ranked(world, p)`, `recognizers(world, item, people)`, `known_blades(world, viewer, people) -> [(person, item)]`, `killed_by`, `reactions(world, bearer, place, present) -> {covets, hates, demands}`, `hatred_events`, `demand_events(world, bearer, demander, item, place, hand_over)`; events `blade_known`, `blade_demanded`.
  - `narrate/gear_text.py`: the tales `wielded_in`, `returned_gear`, `kept_gear`; `standing` reads the two.

- [ ] **Step 1: Write the failing tests**

`tests/test_provenance.py`:
```python
import pytest

import systems.gear as gear
import systems.provenance as P
from debug.invariants import check_gear
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.standing import standing
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def the_sect(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    return sect, halls.seat_of(world, sect)


def someone(game, tag, **data):
    base = {"occupation": "wandering swordsman", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:prov:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def a_treasure_bearer(game, tag="bearer"):
    world = game.world
    bearer = someone(game, tag)
    world.update_data(bearer, gear={"weapon": 3, "armour": None, "form": "sword"})
    return bearer


def slay(game, killer, victim):
    [died] = commit(game.world, [Event("died", (killer, victim), game.place.id, {"cause": "killed"})])
    return died


def test_a_notable_kill_is_remembered_by_the_weapon_that_did_it(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    died = slay(game, me, elder)
    [deed] = gear.carried(world, me)["deeds"]  # a plain carried blade keeps it until it is made real
    assert deed == {"event": died, "kind": "killed", "whom": elder, "weight": P.KILL_WEIGHT}
    item = gear.materialize(world, me, "weapon")
    assert world.entity(item).data["deeds"] == [deed] and "deeds" not in gear.carried(world, me)


def test_a_nobody_killed_is_no_deed(game):
    world, me = game.world, game.player.id
    slay(game, me, someone(game, "nobody"))
    assert not gear.carried(world, me).get("deeds")


def test_a_treasure_blade_is_made_real_by_its_deed_and_told_of(game):
    world = game.world
    sect, seat = the_sect(world)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    bearer = a_treasure_bearer(game)
    died = slay(game, bearer, leader)
    item = gear.item_in(world, bearer, "weapon")
    assert item is not None and item.data["deeds"][0]["weight"] == P.LEADER_WEIGHT
    [fact] = world.facts(predicate="wielded_in", subject=item.id)
    assert fact.object == leader and fact.source_event == died
    assert check_gear(world) == []


def test_a_weapon_keeps_its_twelve_weightiest_deeds(game):
    world, me = game.world, game.player.id
    item = gear.make_item(world, "weapon", "spear", 0, me, "bought")
    commit(world, gear.wield_events(world, me, item, game.place.id))
    first = world.last_rowid("chronicle")
    for n in range(14):
        P.remember(world, me, {"event": first, "kind": "killed", "whom": None, "weight": float(n)}, game.place.id)
    weights = [d["weight"] for d in world.entity(item).data["deeds"]]
    assert weights == [float(n) for n in range(13, 1, -1)]


def test_the_tales_let_you_know_a_blade_on_sight(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    bearer = a_treasure_bearer(game)
    slay(game, bearer, leader)
    item = gear.item_in(world, bearer, "weapon")
    assert P.known_blades(world, me, [bearer]) == []
    [fact] = world.facts(predicate="wielded_in", subject=item.id)
    believe(world, me, fact.id, fact.data["variant"], None, 0.8, 1, "gossip")
    assert P.known_blades(world, me, [bearer]) == [(bearer, item.id)]


def test_those_who_know_a_blade_react_to_its_bearer(game, monkeypatch):
    monkeypatch.setattr(P, "COVET_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    item = gear.make_item(world, "weapon", "sword", 3, me, "found", claimed_by=sect)
    commit(world, gear.wield_events(world, me, item, game.place.id))
    died = slay(game, me, leader)
    [fact] = world.facts(predicate="wielded_in", subject=item)
    kin = someone(game, "kin")
    world.relate(leader, kin, "kin_of", 1.0, {"role": "child"})
    rival = someone(game, "rival", traits=["proud", "cunning"])
    member = someone(game, "member")
    world.relate(member, sect, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                "secret": False})
    for knower in (kin, rival, member):
        believe(world, knower, fact.id, fact.data["variant"], None, 0.8, 1, "gossip")
    seen = P.reactions(world, me, game.place.id, [kin, rival, member])
    assert seen["covets"] == rival and seen["demands"] == member
    assert seen["hates"] == [kin]
    commit(world, P.hatred_events(world, me, seen["hates"], game.place.id, item))
    assert any(m.feeling == "hatred" for m in world.memories(kin, about=me))
    assert P.reactions(world, me, game.place.id, [kin])["hates"] == []  # hated once, not each scene
    assert died


def test_handing_back_a_claimed_blade_or_keeping_it(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    member = someone(game, "claimant")
    world.relate(member, sect, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                "secret": False})
    kept = gear.make_item(world, "weapon", "sword", 2, me, "found", claimed_by=sect)
    commit(world, P.demand_events(world, me, member, kept, game.place.id, hand_over=False))
    assert kept in world.targets(me, "owns") and world.facts(predicate="kept_gear", subject=me)
    given = gear.make_item(world, "weapon", "saber", 2, me, "found", claimed_by=sect)
    commit(world, P.demand_events(world, me, member, given, game.place.id, hand_over=True))
    assert given in world.targets(member, "owns") and world.facts(predicate="returned_gear", subject=me)
    assert world.entity(given).data["owners"][-1]["how"] == "given"


def test_a_sect_thinks_better_of_one_who_gives_back_and_worse_of_one_who_keeps(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    member = someone(game, "judge")
    before = standing(world, sect, me).score
    blade = gear.make_item(world, "weapon", "sword", 2, me, "found", claimed_by=sect)
    commit(world, P.demand_events(world, me, member, blade, seat, hand_over=False))
    [fact] = world.facts(predicate="kept_gear", subject=me)
    believe(world, seat, fact.id, fact.data["variant"], None, 1.0, 0, "witness")  # the seat's town knows it
    worse = standing(world, sect, me).score
    assert worse < before and "you keep what is ours" in standing(world, sect, me).reasons
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_provenance.py`
Expected: `ModuleNotFoundError: No module named 'systems.provenance'`.

- [ ] **Step 3: Write the new modules**

`narrate/gear_text.py`:
```python
"""What the player is told of weapons and armour (phase 5a spec 3, 5): their tales and the deeds done with them."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

DEED_WORDS = {"killed": "slew {whom}", "bested": "bested {whom}", "won_tournament": "won a tournament"}


def deed_words(world, deed: str, whom, viewer: int) -> str:
    return DEED_WORDS.get(deed, "was wielded by {wielder}").format(whom=who(world, whom, viewer), wielder="someone")


def _wielded_in(world, v, viewer) -> str:
    blade = world.entity(v.get("actor"))
    name = blade.name if blade is not None else "a famous blade"
    text = f"{name}, in the hand of {who(world, v.get('wielder'), viewer)}, {deed_words(world, v.get('deed'), v.get('target'), viewer)}"
    return cap(text + (f" in {v['place']}." if v.get("place") else "."))


def _returned(world, v, viewer) -> str:
    faction = world.entity(v.get("target")) if isinstance(v.get("target"), int) else None
    return cap(f"{who(world, v.get('actor'), viewer)} gave the {faction.name if faction else 'sect'} back what was theirs.")


def _kept(world, v, viewer) -> str:
    faction = world.entity(v.get("target")) if isinstance(v.get("target"), int) else None
    return cap(f"{who(world, v.get('actor'), viewer)} keeps a blade the {faction.name if faction else 'sect'} calls its own.")


SPECIAL_PHRASES["wielded_in"] = _wielded_in
SPECIAL_PHRASES["returned_gear"] = _returned
SPECIAL_PHRASES["kept_gear"] = _kept


@outcome("blade_known", body_facts=False)
def _blade_known(world, event):
    item = world.entity(event.data["item"])
    return [f"{who(world, event.actors[0], event.actors[1])} stares at {item.name}. They know whose blood is on it."], {}


@summary("blade_known")
def _blade_known_line(world, entry, names, place, other):
    return f"Was known by the blade you carry, at {place}."


@outcome("blade_demanded", body_facts=False)
def _demanded(world, event):
    item = world.entity(event.data["item"])
    if event.data["handed"]:
        return [f"You hand over {item.name}. It goes back where they say it belongs."], {}
    return [f"You keep {item.name}. They will remember that you did."], {}


@summary("blade_demanded")
def _demanded_line(world, entry, names, place, other):
    return "Gave back a blade a sect called its own." if entry.data["handed"] else "Kept a blade a sect called its own."
```

`systems/provenance.py`:
```python
"""What a weapon has done, and who knows it (phase 5a spec 3.1-3.2).

A weapon wielded in a notable deed remembers it: an item keeps its twelve weightiest deeds, a carried grade keeps
them until it is made real. The deeds of a famous weapon, or of any of treasure grade or better, are told as
facts about the weapon (`wielded_in`), and spread like any rumour. Whoever believes one knows the weapon on
sight: a proud or greedy fighter may challenge its bearer for it, the kin of those it killed hate its bearer, and
the faction it was taken from demands it back.
"""

import systems.gear as gear
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.kin import kin_of
from systems.realms import realm_index
from world.events import Event, Witness, effect, listen
from world.seed import rng_for

LEGEND_GRADE = 3  # treasure grade or better is told of
KILL_WEIGHT, LEADER_WEIGHT, BESTED_WEIGHT, TITLE_WEIGHT = 3.0, 4.0, 2.0, 2.5
NOTABLE_RANK, NOTABLE_REALM = 3, 2
COVET_CHANCE, COVETOUS = 0.2, frozenset({"proud", "greedy"})
KIN_HATRED = 0.6
DEED_HOOKS: list = []  # (world, item entity, deed) -> None: a famous weapon's epithet (Task 3)


# --- deeds ----------------------------------------------------------------------------------------------

def notable(world, person: int) -> str | None:
    """Why this person's fall is worth remembering: a leader, a ranked member, a strong fighter; or None."""
    data = world.entity(person).data
    rows = F.memberships(world, person)
    if any(d.get("role") == "leader" and d.get("status", "member") == "member" for _, _, d in rows):
        return "leader"
    if any(rank >= NOTABLE_RANK and d.get("status", "member") == "member" for _, rank, d in rows) \
            or realm_index(data.get("realm", "mortal")) >= NOTABLE_REALM:
        return "notable"
    return None


def _keep(deeds: list, deed: dict) -> list:
    return sorted(deeds + [deed], key=lambda d: (-d["weight"], d["event"]))[:gear.MAX_DEEDS]


def remember(world, person: int, deed: dict, place) -> None:
    """The weapon this person struck with remembers the deed; a great one's is told (spec 3.1-3.2)."""
    w = gear.weapon_of(world, person)
    if w is None or w["broken"]:
        return  # bare hands leave no legend
    if w["item"] is None and w["grade"] >= LEGEND_GRADE and not world.entity(person).data.get("is_player"):
        gear.materialize(world, person, "weapon")  # a treasure is worth a name of its own
        w = gear.weapon_of(world, person)
    if w["item"] is None:
        carried = dict(gear.carried(world, person))
        carried["deeds"] = _keep(list(carried.get("deeds", [])), deed)
        world.update_data(person, gear=carried)
        return
    item = world.entity(w["item"])
    world.update_data(item.id, deeds=_keep(list(item.data["deeds"]), deed))
    if item.data.get("famous") or item.data["grade"] >= LEGEND_GRADE:
        variant = make_variant("wielded_in", item.id, deed.get("whom"), place=place_name(world, place))
        variant.update(wielder=person, deed=deed["kind"])
        record_fact(world, item.id, "wielded_in", deed.get("whom"), place=place, source_event=deed["event"],
                    weight=deed["weight"], variant=variant)
    for hook in DEED_HOOKS:
        hook(world, world.entity(item.id), deed)


@listen("died")
def _killed_with(world, event, event_id: int) -> None:
    killer, victim = event.actors[0], event.actors[-1]
    if killer == victim or world.entity(killer) is None or world.entity(killer).data.get("dead"):
        return
    why = notable(world, victim)
    if why is not None:
        remember(world, killer, {"event": event_id, "kind": "killed", "whom": victim,
                                 "weight": LEADER_WEIGHT if why == "leader" else KILL_WEIGHT}, event.place)


def ranked(world, person: int) -> bool:
    from systems.rankings import pavilion, rank_of  # the Pavilion comes after the duel in the import graph
    pav = pavilion(world)
    return pav is not None and rank_of(world.entity(pav).data.get("lists") or {}, person) is not None


@listen("duel_ended")
def _bested_with(world, event, event_id: int) -> None:
    d = event.data
    if d.get("killed") or d.get("player_killed"):
        return  # the death tells it
    player, opponent = event.actors
    if d["result"] == "won" and ranked(world, opponent):
        remember(world, player, {"event": event_id, "kind": "bested", "whom": opponent, "weight": BESTED_WEIGHT},
                 event.place)
    elif d["result"] == "lost" and d.get("by") == "opponent" and ranked(world, player):
        remember(world, opponent, {"event": event_id, "kind": "bested", "whom": player, "weight": BESTED_WEIGHT},
                 event.place)


@listen("tournament_won")
def _title_with(world, event, event_id: int) -> None:
    champion = event.data.get("champion")
    if champion is not None and world.entity(champion) is not None and not world.entity(champion).data.get("dead"):
        remember(world, champion, {"event": event_id, "kind": "won_tournament", "whom": None,
                                   "weight": TITLE_WEIGHT}, event.place)


# --- knowing a weapon on sight ----------------------------------------------------------------------------

def recognizers(world, item_id: int, people) -> set[int]:
    """Who among these believes any tale of this weapon (one query, the beliefs' actor index)."""
    return {belief.knower for belief, _ in world.known_facts_about(people, actors=[item_id], predicate="wielded_in")}


def known_blades(world, viewer: int, people) -> list[tuple[int, int]]:
    """(person, item) for each of these who wields a weapon the viewer knows by its tales."""
    held = [(p, world.targets(p, "wields")) for p in people if p != viewer]
    held = [(p, found[0]) for p, found in held if found]
    if not held:
        return []
    known = {fact.subject for _, fact in world.known_facts_about([viewer], actors=[i for _, i in held],
                                                                 predicate="wielded_in")}
    return [(p, i) for p, i in held if i in known]


def killed_by(world, item) -> list[int]:
    return [d["whom"] for d in item.data["deeds"] if d["kind"] == "killed" and d.get("whom") is not None]


def reactions(world, bearer: int, place: int, present: list[int]) -> dict:
    """What the people here make of the weapon the bearer carries: {covets, hates, demands} (spec 3.2)."""
    item = gear.item_in(world, bearer, "weapon")
    out = {"covets": None, "hates": [], "demands": None}
    if item is None:
        return out
    knowing = sorted(recognizers(world, item.id, [p for p in present if p != bearer]))
    if not knowing:
        return out
    grief = {k for victim in killed_by(world, item) for k, _ in kin_of(world, victim)}
    mine = realm_index(world.entity(bearer).data.get("realm", "mortal"))
    claimed = item.data.get("claimed_by")
    for person in knowing:
        data = world.entity(person).data
        if person in grief and not any(m.feeling == "hatred" for m in world.memories(person, about=bearer)):
            out["hates"].append(person)
        if claimed is not None and out["demands"] is None and any(
                f == claimed and d.get("status", "member") == "member" for f, _, d in F.memberships(world, person)):
            out["demands"] = person
        rng = rng_for(world.world_seed, f"covet:{person}:{item.id}:{world.time}")
        if out["covets"] is None and COVETOUS & set(data.get("traits", ())) \
                and abs(realm_index(data.get("realm", "mortal")) - mine) <= 1 and rng.random() < COVET_CHANCE:
            out["covets"] = person
    return out


def hatred_events(world, bearer: int, haters: list[int], place: int, item: int) -> list[Event]:
    return [Event("blade_known", (h, bearer), place, {"item": item},
                  witnesses=(Witness(h, "hatred", KIN_HATRED),)) for h in haters]


def demand_events(world, bearer: int, demander: int, item_id: int, place: int, hand_over: bool) -> list[Event]:
    """Hand it over (the sect thinks better of you) or refuse (worse), spec 3.2."""
    faction = world.entity(item_id).data["claimed_by"]
    events = [Event("blade_demanded", (bearer, demander), place,
                    {"item": item_id, "faction": faction, "handed": hand_over})]
    if hand_over:
        events += gear.pass_events(world, bearer, demander, item_id, place, "given")
    return events


@listen("blade_demanded")
def _demanded(world, event, event_id: int) -> None:
    bearer, d = event.actors[0], event.data
    predicate = "returned_gear" if d["handed"] else "kept_gear"
    variant = make_variant(predicate, bearer, d["faction"], place=place_name(world, event.place))
    record_fact(world, bearer, predicate, d["faction"], place=event.place, source_event=event_id,
                weight=0.5 if d["handed"] else 1.0, variant=variant)


@effect("blade_known")
def _known(world, event) -> None:
    pass  # the hatred is the witness's memory
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5a_task2.py`:
```python
"""Phase 5a, Task 2: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('debug/invariants.py', r'''            if world.chronicle_entry(deed) is None:
                out.append(f"{item.name} (#{item.id}) remembers a deed that never happened (#{deed})")
''', r'''            if world.chronicle_entry(deed["event"]) is None:
                out.append(f"{item.name} (#{item.id}) remembers a deed that never happened (#{deed['event']})")
        if len(item.data.get("deeds", [])) > 12:
            out.append(f"{item.name} (#{item.id}) remembers more than twelve deeds")
''')
edit('narrate/outcomes.py', r'''import narrate.intrigue_text  # noqa: E402,F401
''', r'''import narrate.intrigue_text  # noqa: E402,F401
import narrate.gear_text  # noqa: E402,F401
''')
edit('systems/gear.py', r'''    made = make_item(world, slot, form, grade, person, "carried", path=f"gear:{person}:{slot}")
    world.relate(person, made, SLOTS[slot])
    gear[slot] = None  # now the item, not the grade
''', r'''    made = make_item(world, slot, form, grade, person, "carried", path=f"gear:{person}:{slot}",
                     deeds=list(gear.get("deeds", [])) if slot == "weapon" else [])
    world.relate(person, made, SLOTS[slot])
    gear[slot] = None  # now the item, not the grade
    if slot == "weapon":
        gear.pop("deeds", None)
        gear.pop("form", None)
''')
edit('systems/gear.py', r'''        world.update_data(person, gear={"weapon": 0, "armour": None, "form": form})
''', r'''        world.update_data(person, gear={"weapon": 0, "armour": None, "form": form})


import systems.provenance  # noqa: E402,F401  (what a weapon has done: registers its listeners)
''')
edit('systems/standing.py', r'''                value, reason = 0.5, "you struck at our enemies"
''', r'''                value, reason = 0.5, "you struck at our enemies"
        if fact.predicate in ("returned_gear", "kept_gear") and target == faction_id:  # phase 5a: what was ours
            value, reason = (1.0, "you gave back what was ours") if fact.predicate == "returned_gear" \
                else (-1.0, "you keep what is ours")
''')
print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5a_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_provenance.py tests/test_gear.py`
Expected: `16 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: provenance - the deeds a blade remembers, its legend told, and those who know it on sight

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: Famous weapons and the Hundred Weapons Chronicle

Named blades with a founding legend, seeded per keeper once the keeper exists (ruling 6): a great sect's treasure, a clan's heirloom (sometimes lost), a city's wandering master's own. At a death they pass to the killer, else the heir, else lie where they fell; an heirloom given back wins the clan's favour; a slayer of a master earns an epithet; each spring the Pavilion ranks them. A 4f realm master's weapon is famous the day it is taken.

**Files:**
- Create: `systems/famous.py`
- Create: `tests/test_famous.py`
- Modify (by `.patches/5a_task3.py`): `debug/invariants.py`, `systems/provenance.py`, `systems/realm_gates.py`, `systems/world_clock.py`

**Interfaces:**
- Consumes: Tasks 1-2: `gear.make_item`, `gear.pass_events`, `gear.best_weapon_form`, `provenance.DEED_HOOKS`, `provenance.notable`, `provenance.ranked`; 4a's `SEASON_HOOKS`, `claimants.staff`; 4d's `ensure_pavilion`; 4f's `realm_gates.inherit`.
- Produces:
  - `famous` (FW): `NAMES`, `CLANS`, `LOST_HEIRLOOM`, `DIVINE_CHANCE`, `HEIRLOOM_STANCE`, `CHRONICLE_SIZE`, `TOP`; `famous_weapons(world)`, `make_famous(world, key, form, owner, how, legend, place, heirloom_of=None, name=None, grade=None)`, `ensure_famous(world)`, `heir_of`, `lying_at(world, place)`, `take_lying_events`, `return_block/return_events`, `standing_of`, `chronicle_events(world, n)`, `season_hook`, `chronicle_known(world, knower)`; events `heirloom_returned`, `weapons_ranked`; facts `blade_legend`, `weapon_ranked`, `weapons_ranked`.
  - `provenance.LEGENDS`: any tale of a blade makes it known.

- [ ] **Step 1: Write the failing tests**

`tests/test_famous.py`:
```python
import pytest

import systems.famous as FW
import systems.gear as gear
import systems.provenance as P
from debug.invariants import check_gear
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.beliefs import believe
from systems.claimants import staff
from systems.creation import CreationChoice
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def of_type(world, *kinds):
    return [i for i in F.ensure_roster(world) if world.entity(i).data["type"] in kinds]


def famous_of(world, faction):
    return next(i for i in FW.famous_weapons(world) if world.entity(i).seed_path == f"famous:faction:{faction}")


def staffed(world):
    """The factions' masters stand in the world once their seats are made (as a visit or a season makes them)."""
    for fid in F.ensure_roster(world):
        seat = halls.seat_of(world, fid)
        if seat is not None:
            halls.staff_at(world, fid, seat)


def test_great_sects_clans_and_cities_have_their_famous_blades(game):
    world = game.world
    staffed(world)
    FW.ensure_famous(world)
    listed = FW.famous_weapons(world)
    assert listed and len(listed) == len(set(listed))
    great = [f for f in F.ensure_roster(world) if world.entity(f).data.get("tier") == "great"
             and world.entity(f).data["type"] not in FW.CLANS]  # a great clan keeps an heirloom instead
    for sect in [g for g in great if staff(world, g, ("leader",))]:
        blade = world.entity(famous_of(world, sect))
        assert blade.data["famous"] and blade.data["grade"] >= 3
        leaders = staff(world, sect, ("leader",))
        if leaders:
            assert gear.item_in(world, leaders[0], "weapon").id == blade.id  # the master holds the sect's treasure
    for clan in [c for c in of_type(world, "martial_clan", "local_clan") if staff(world, c, ("leader",))]:
        heirloom = world.entity(famous_of(world, clan))
        assert heirloom.data["heirloom_of"] == clan and heirloom.data["claimed_by"] == clan
        assert world.sources(heirloom.id, "owns") or heirloom.data["lost_at"] is not None
    assert all(world.facts(predicate="blade_legend", subject=i) for i in listed)
    FW.ensure_famous(world)
    assert FW.famous_weapons(world) == listed  # seeded once
    assert check_gear(world) == []


def test_no_master_no_famous_blade_yet(game):
    world = game.world
    before = len(world.entities("person"))
    FW.ensure_famous(world)
    for fid in F.ensure_roster(world):
        if not staff(world, fid, ("leader",)):
            assert f"faction:{fid}" not in (world.get_meta("famous_keys") or [])
    assert len(world.entities("person")) == before  # no one is made for a blade


def a_keeper(game):
    world = game.world
    staffed(world)
    FW.ensure_famous(world)
    for item in FW.famous_weapons(world):
        owners = world.sources(item, "owns")
        if owners and not world.entity(owners[0]).data.get("is_player"):
            return owners[0], item
    raise AssertionError("no one keeps a famous blade")


def test_a_killer_takes_a_famous_blade_and_the_player_finds_it_lying(game):
    world, me = game.world, game.player.id
    keeper, item = a_keeper(game)
    killer = world.add_entity("person", "A Killer", {"occupation": "bandit", "traits": ["greedy"], "realm": "peak",
                                                     "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:killer")
    world.relate(killer, game.place.id, "located_in")
    commit(world, [Event("died", (killer, keeper), game.place.id, {"cause": "killed"})])
    assert item in world.targets(killer, "owns")
    commit(world, [Event("died", (me, killer), game.place.id, {"cause": "killed"})])
    assert not world.sources(item, "owns") and item in FW.lying_at(world, game.place.id)
    commit(world, FW.take_lying_events(world, me, item, game.place.id))
    assert item in world.targets(me, "owns") and world.entity(item).data["owners"][-1]["how"] == "found"
    assert check_gear(world) == []


def test_a_famous_blade_goes_to_the_heir_at_a_natural_death(game):
    world = game.world
    keeper, item = a_keeper(game)
    child = world.add_entity("person", "An Heir", {"occupation": "tea seller", "traits": ["kind"], "realm": "mortal",
                                                   "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:heir")
    world.relate(keeper, child, "kin_of", 1.0, {"role": "child"})
    commit(world, [Event("died", (keeper, keeper), None, {"cause": "age", "world": True})])
    assert item in world.targets(child, "owns")
    assert world.entity(item).data["owners"][-1] == {"person": child, "since": world.time, "how": "inherited"}


def test_an_heirloom_given_back_wins_the_clans_favour(game):
    world, me = game.world, game.player.id
    staffed(world)
    FW.ensure_famous(world)
    clan = of_type(world, "martial_clan", "local_clan")[0]
    item = famous_of(world, clan)
    for owner in world.sources(item, "owns"):
        world.unrelate(owner, "owns", item)
        world.unrelate(owner, "wields", item)
    world.relate(me, item, "owns")
    world.update_data(item, owners=world.entity(item).data["owners"] + [{"person": me, "since": 0, "how": "found"}])
    seat = world.entity(clan).data["seat"]
    assert FW.return_block(world, me, item, game.place.id if game.place.id != seat else -1) is not None
    [head] = staff(world, clan, ("leader",))[:1] or [None]
    if head is None:
        pytest.skip("the clan has no head")
    commit(world, FW.return_events(world, me, item, seat))
    assert item in world.targets(head, "owns")
    assert any(m.feeling == "grateful" and m.indelible for m in world.memories(head, about=me))
    assert world.facts(predicate="returned_gear", subject=me)


def test_a_famous_blade_that_slays_a_master_earns_an_epithet(game):
    world = game.world
    keeper, item = a_keeper(game)
    sect = next(f for f in F.ensure_roster(world) if staff(world, f, ("leader",))
                and staff(world, f, ("leader",))[0] != keeper)
    [master] = staff(world, sect, ("leader",))
    commit(world, [Event("died", (keeper, master), None, {"cause": "killed"})])
    assert world.entity(item).data["epithet"] == f"which slew {world.entity(master).name}"


def test_the_hundred_weapons_chronicle_ranks_and_is_told(game):
    world, me = game.world, game.player.id
    staffed(world)
    FW.ensure_famous(world)
    [ranked] = FW.chronicle_events(world, 4)
    order = ranked.data["order"]
    assert order == sorted(order, key=lambda i: FW.standing_of(world, i))
    commit(world, [ranked])
    news = world.facts(predicate="weapon_ranked")
    assert {f.subject for f in news} == set(order[:FW.CHRONICLE_SIZE])  # all new this year
    [told] = world.facts(predicate="weapons_ranked")
    assert FW.chronicle_known(world, me) is None
    believe(world, me, told.id, told.data["variant"], None, 1.0, 1, "posted")
    assert FW.chronicle_known(world, me)["order"] == order


def test_a_legend_alone_lets_you_know_a_famous_blade(game):
    world, me = game.world, game.player.id
    keeper, item = a_keeper(game)
    [legend] = world.facts(predicate="blade_legend", subject=item)
    believe(world, me, legend.id, legend.data["variant"], None, 1.0, 1, "gossip")
    assert P.known_blades(world, me, [keeper]) == [(keeper, item)]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_famous.py`
Expected: `ModuleNotFoundError: No module named 'systems.famous'`.

- [ ] **Step 3: Write the new modules**

`systems/famous.py`:
```python
"""Famous weapons (phase 5a spec 3.3): named blades with a legend, their keepers, how they pass, the Chronicle.

A great sect's master holds its treasure; a clan keeps its heirloom (or has lost it); a wandering master carries a
blade of their own through each city. They are items from the start, listed in the meta row `famous_weapons`.
They pass at a death to the killer, else the heir, else they lie where the dead fell. An heirloom given back to
its clan wins the clan's lasting favour. Each spring the Pavilion ranks them in the Hundred Weapons Chronicle.
"""

import systems.gear as gear
import systems.provenance as P
import systems.world_clock as world_clock
from systems import factions as F
from systems.claimants import staff
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from systems.kin import kin_of
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

NAMES = ("Frost Moon", "Nine Dragons", "Azure Cloud", "Blood Lotus", "Heaven Splitting", "Silent Thunder",
         "Jade Serpent", "Crimson Phoenix", "Northern Star", "White Tiger", "Black Tortoise", "Soul Reaving",
         "Autumn Water", "Burning Sun", "Falling Snow", "Seven Stars", "Iron Lotus", "Thousand Autumns",
         "Wandering Cloud", "Moonless Night")
FORM_WORDS = {"sword": "Sword", "saber": "Saber", "spear": "Spear", "staff": "Staff"}
CLANS = frozenset({"martial_clan", "local_clan"})
LOST_HEIRLOOM = 0.3
DIVINE_CHANCE = 0.25
HEIRLOOM_STANCE = 0.3
CHRONICLE_SIZE, TOP = 100, 10
FAMED_VICTIM = frozenset({"leader"})


# --- the index -------------------------------------------------------------------------------------------

def famous_weapons(world) -> list[int]:
    return list(world.get_meta("famous_weapons") or [])


def _name(world, rng, form: str) -> str:
    used = {world.entity(i).name for i in famous_weapons(world)}
    for _ in range(20):
        name = f"the {rng.choice(NAMES)} {FORM_WORDS[form]}"
        if name not in used:
            return name
    return f"the {rng.choice(NAMES)} {FORM_WORDS[form]} of {rng.randint(2, 99)}"


def make_famous(world, key: str, form: str, owner: int | None, how: str, legend: str, place,
                heirloom_of: int | None = None, name: str | None = None, grade: int | None = None) -> int:
    """A named weapon, famous from the start, with its founding legend told (spec 3.3)."""
    rng = rng_for(world.world_seed, f"famous:{key}")
    grade = grade if grade is not None else (4 if rng.random() < DIVINE_CHANCE else 3)
    item = gear.make_item(world, "weapon", form, grade, owner, how, name=name or _name(world, rng, form),
                          path=f"famous:{key}", famous=True, heirloom_of=heirloom_of, claimed_by=heirloom_of,
                          lost_at=None if owner is not None else place)
    world.set_meta("famous_weapons", famous_weapons(world) + [item])
    if owner is not None:
        world.unrelate(owner, "wields")
        world.relate(owner, item, "wields")
    variant = make_variant("blade_legend", item, owner, place=place_name(world, place) if place else None)
    variant.update(legend=legend)
    record_fact(world, item, "blade_legend", owner, place=place, weight=1.5, variant=variant)
    return item


def _form_for(world, person: int | None, rng) -> str:
    form = gear.best_weapon_form(world, person) if person is not None else None
    return form or rng.choice(gear.WEAPON_FORMS)


def ensure_famous(world) -> None:
    """Seed the famous weapons of the factions and cities the world has made (once each): a faction's only once
    its master stands in the world, a city's only if a wandering master lives there (nothing is made for it)."""
    seen = set(world.get_meta("famous_keys") or [])
    added = []
    for fid in F.ensure_roster(world):
        faction = world.entity(fid)
        kind, key = faction.data.get("type"), f"faction:{fid}"
        if key in seen or faction.data.get("dissolved") or not (faction.data.get("tier") == "great" or kind in CLANS):
            continue
        leaders = staff(world, fid, ("leader",))
        if not leaders:
            continue  # the world has not made its master yet: next spring, perhaps
        added.append(key)
        rng = rng_for(world.world_seed, f"famous:{key}:keeper")
        seat = faction.data.get("seat")
        if kind in CLANS:
            keeper = None if not leaders or rng.random() < LOST_HEIRLOOM else leaders[0]
            make_famous(world, key, _form_for(world, keeper, rng), keeper, "inherited",
                        f"the heirloom of the {faction.name}" + ("" if keeper else ", lost"), seat, heirloom_of=fid)
        else:
            keeper = leaders[0] if leaders else None
            make_famous(world, key, _form_for(world, keeper, rng), keeper, "inherited",
                        f"the treasure of the {faction.name}", seat)
    for town in world.entities("town"):
        key = f"city:{town.id}"
        if town.data.get("kind") != "city" or key in seen:
            continue
        added.append(key)
        wanderers = sorted((p for p in people_at(world, town.id) if p.data.get("occupation") == "wandering swordsman"
                            and not p.data.get("is_player") and not world.targets(p.id, "wields")),
                           key=lambda p: (-realm_index(p.data.get("realm", "mortal")), p.id))
        if wanderers:
            rng = rng_for(world.world_seed, f"famous:{key}:keeper")
            master = wanderers[0].id
            make_famous(world, key, _form_for(world, master, rng), master, "made", "a wandering master's own", town.id)
    if added:
        world.set_meta("famous_keys", sorted(seen | set(added)))


# --- how they pass ---------------------------------------------------------------------------------------

def heir_of(world, dead: int) -> int | None:
    return next((k for k, _ in kin_of(world, dead) if not world.entity(k).data.get("is_player")), None)


@listen("died")
def _passes_on(world, event, event_id: int) -> None:
    """At a death a famous blade goes to the killer who takes it, else the heir, else it lies there (spec 3.3)."""
    killer, dead = event.actors[0], event.actors[-1]
    for item in sorted(set(world.targets(dead, "owns")) & set(famous_weapons(world))):  # one query a death
        npc_killer = killer != dead and world.entity(killer) is not None \
            and not world.entity(killer).data.get("is_player") and not world.entity(killer).data.get("dead")
        if npc_killer:
            commit(world, gear.pass_events(world, dead, killer, item, event.place, "taken"))
            continue
        if killer != dead and world.entity(killer) is not None and world.entity(killer).data.get("is_player"):
            commit(world, gear.pass_events(world, dead, None, item, event.place, "lost"))  # there for the taking
            continue
        heir = heir_of(world, dead)
        commit(world, gear.pass_events(world, dead, heir, item, event.place, "inherited" if heir else "lost"))


def lying_at(world, place: int) -> list[int]:
    return [i for i in famous_weapons(world) if world.entity(i).data.get("lost_at") == place
            and not world.sources(i, "owns")]


def take_lying_events(world, person: int, item: int, place: int) -> list[Event]:
    return gear.pass_events(world, None, person, item, place, "found")


# --- heirlooms ---------------------------------------------------------------------------------------

def return_block(world, bearer: int, item_id: int, place: int) -> str | None:
    item = world.entity(item_id)
    clan = item.data.get("heirloom_of") if item is not None else None
    if clan is None or item_id not in world.targets(bearer, "owns"):
        return "That is no clan's heirloom of yours to give."
    if world.entity(clan).data.get("seat") != place:
        return "Its clan keeps its hall elsewhere."
    if not staff(world, clan, ("leader",)):
        return "There is no clan head here to receive it."
    return None


def return_events(world, bearer: int, item_id: int, place: int) -> list[Event]:
    clan = world.entity(item_id).data["heirloom_of"]
    head = staff(world, clan, ("leader",))[0]
    return gear.pass_events(world, bearer, head, item_id, place, "given") + [
        Event("heirloom_returned", (bearer, head), place, {"item": item_id, "clan": clan},
              witnesses=(Witness(head, "grateful", 0.9, True),))]


@effect("heirloom_returned")
def _returned(world, event) -> None:
    bearer, clan = event.actors[0], event.data["clan"]
    from systems.founding import my_sect
    sect = my_sect(world, bearer)
    if sect is not None:
        value = min(1.0, F.stance(world, clan, sect) + HEIRLOOM_STANCE)
        world.relate(clan, sect, "stance", value)
        world.relate(sect, clan, "stance", value)


@listen("heirloom_returned")
def _returned_news(world, event, event_id: int) -> None:
    variant = make_variant("returned_gear", event.actors[0], event.data["clan"], place=place_name(world, event.place))
    record_fact(world, event.actors[0], "returned_gear", event.data["clan"], place=event.place,
                source_event=event_id, weight=1.5, variant=variant)


# --- epithets ---------------------------------------------------------------------------------------

def _epithet(world, item, deed) -> None:
    """A famous weapon that slays someone of fame is named for it (spec 3.3), once."""
    if not item.data.get("famous") or item.data.get("epithet") or deed["kind"] != "killed" or deed.get("whom") is None:
        return
    if P.notable(world, deed["whom"]) == "leader" or P.ranked(world, deed["whom"]):
        world.update_data(item.id, epithet=f"which slew {world.entity(deed['whom']).name}")


P.DEED_HOOKS.append(_epithet)


# --- the Hundred Weapons Chronicle -------------------------------------------------------------------------

def standing_of(world, item_id: int) -> tuple:
    item = world.entity(item_id)
    return (-item.data["grade"], -round(sum(d["weight"] for d in item.data["deeds"]), 3), item_id)


def chronicle_events(world, n: int) -> list[Event]:
    from systems.rankings import ensure_pavilion
    pav = ensure_pavilion(world)
    order = sorted((i for i in famous_weapons(world) if not world.entity(i).data.get("broken")),
                   key=lambda i: standing_of(world, i))[:CHRONICLE_SIZE]
    before = world.entity(pav).data.get("weapons") or []
    return [Event("weapons_ranked", (pav,), world.entity(pav).data["town"],
                  {"year": n // 4 + 1, "order": order, "before": before})]


@effect("weapons_ranked")
def _ranked(world, event) -> None:
    world.update_data(event.actors[0], weapons=event.data["order"])


@listen("weapons_ranked")
def _ranked_news(world, event, event_id: int) -> None:
    pav, d = event.actors[0], event.data
    variant = make_variant("weapons_ranked", pav, None, place=place_name(world, event.place))
    variant.update(year=d["year"], first=(d["order"] or [None])[0])
    record_fact(world, pav, "weapons_ranked", None, place=event.place, weight=2.0, variant=variant,
                extra={"order": d["order"]})
    before = d["before"]
    for rank, item in enumerate(d["order"], 1):
        was = before.index(item) + 1 if item in before else None
        if was is None or (rank <= TOP < was):
            news = make_variant("weapon_ranked", item, None, place=place_name(world, event.place))
            news.update(rank=rank)
            record_fact(world, item, "weapon_ranked", None, place=event.place, weight=1.5, variant=news)


def season_hook(world, n: int) -> list[Event]:
    if n % 4:
        return []
    ensure_famous(world)
    return chronicle_events(world, n)


world_clock.SEASON_HOOKS.append(season_hook)


def chronicle_known(world, knower: int) -> dict | None:
    found = world.newest_known(knower, "weapons_ranked", "year")
    if found is None:
        return None
    belief, fact = found
    return {"year": belief.variant.get("year", 0), "order": fact.data.get("order", [])}
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5a_task3.py`:
```python
"""Phase 5a, Task 3: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('debug/invariants.py', r'''                    out.append(f"#{holder} {rel} {item.name} (#{item.id}), which is no {slot}")
''', r'''                    out.append(f"#{holder} {rel} {item.name} (#{item.id}), which is no {slot}")
    import systems.famous as FW
    listed = FW.famous_weapons(world)
    if len(listed) != len(set(listed)):
        out.append("a famous weapon is listed twice")
    famous = {i.id for i in world.entities("gear") if i.data.get("famous")}
    if famous != set(listed):
        out.append(f"the famous weapons listed are not the famous ones ({sorted(famous ^ set(listed))[:5]})")
''')
edit('systems/provenance.py', r'''KIN_HATRED = 0.6
''', r'''KIN_HATRED = 0.6
LEGENDS = frozenset({"wielded_in", "blade_legend", "weapon_ranked"})  # any tale of a blade makes it known
''')
edit('systems/provenance.py', r'''    return {belief.knower for belief, _ in world.known_facts_about(people, actors=[item_id], predicate="wielded_in")}
''', r'''    return {belief.knower for belief, fact in world.known_facts_about(people, actors=[item_id])
            if fact.predicate in LEGENDS}
''')
edit('systems/provenance.py', r'''    known = {fact.subject for _, fact in world.known_facts_about([viewer], actors=[i for _, i in held],
                                                                 predicate="wielded_in")}
''', r'''    known = {fact.subject for _, fact in world.known_facts_about([viewer], actors=[i for _, i in held])
             if fact.predicate in LEGENDS}
''')
edit('systems/provenance.py', r'''    claimed = item.data.get("claimed_by")
''', r'''    claimed = item.data.get("claimed_by")
    if claimed is not None and any(f == claimed and d.get("status", "member") == "member"
                                   for f, _, d in F.memberships(world, bearer)):
        claimed = None  # carried by one of its own
''')
edit('systems/realm_gates.py', r'''    weapon = world.add_entity("treasure", master["weapon"], {"kind": "weapon", "used": False, "value": WEAPON_VALUE})
    world.relate(person, weapon, "owns")
''', r'''    from systems.famous import make_famous  # phase 5a: the master's weapon is famous the day it is taken
    form = world.entity(master["art"]).data.get("form")
    make_famous(world, f"realm:{realm}", form if form in ("sword", "saber", "spear", "staff") else "sword", person,
                "found", f"buried with {master['name']}", realm, name=master["weapon"], grade=4)
''')
edit('systems/world_clock.py', r'''import systems.scheming  # noqa: E402,F401  phase 4h: the player's own plots
''', r'''import systems.scheming  # noqa: E402,F401  phase 4h: the player's own plots
import systems.famous  # noqa: E402,F401  phase 5a: famous weapons, how they pass, the Hundred Weapons Chronicle
''')
print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5a_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_famous.py tests/test_realm_gates.py tests/test_secret_realms.py`
Expected: `26 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: famous weapons - named blades and their keepers, how they pass, heirlooms, epithets, the Hundred Weapons Chronicle

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: The smith, the armoury, and the fallen

A town's smith stocks a seeded list each season, capped by the town's size, and buys gear back at half; a famous blade sells only to a city's merchant. A sect's armoury is a grade table drawn from by rank (an elder once at treasure grade), returned to, restocked; leaving with it is theft. The victor may take the loser's weapon and armour (robbery if the loser was lawful, ruling 9); a greedy victor may take yours.

**Files:**
- Create: `systems/armoury.py`
- Create: `systems/smithy.py`
- Create: `systems/spoils.py`
- Create: `tests/test_arms_trade.py`
- Modify (by `.patches/5a_task4.py`): `debug/invariants.py`, `systems/gear.py`, `systems/law.py`, `systems/standing.py`, `systems/world_clock.py`

**Interfaces:**
- Consumes: Tasks 1-3: `gear.materialize`, `gear.make_item`, `gear.pass_events`, `gear.gear_items`; 4c's `market.drift`; 3b's `left_events` kinds, `law.bounty`; 2's `duel.covets`.
- Produces:
  - `smithy` (SM): `BASE`, `CAPS`, `SELL_SHARE`, `FAMOUS_PRICE`; `cap`, `stock(world, town) -> [{key, slot, form, grade}]`, `price(world, town, slot, grade)`, `buy_block/buy_events(world, player, town, key)`, `smith_name`, `sell_price`, `buyer_for`, `sell_block/sell_events(world, player, town, item)`; events `gear_bought`, `gear_sold`.
  - `armoury` (A): `SEED`, `RANK_GRADE`, `ELDER_GRADE`; `seed_of`, `table(world, f)`, `allowed(world, p, f)`, `draw_block/draw_events(world, p, f, slot, place)`, `return_events(world, p, item, place)`, `season_hook`; events `armoury_drawn`, `armoury_returned`; the fact `stole`.
  - `spoils` (SP): `NPC_TAKES`; `beaten_by`, `lawful(world, p, place=None)`, `take_block/take_events(world, taker, loser, slot, place)`; event `gear_seized`.

- [ ] **Step 1: Write the failing tests**

`tests/test_arms_trade.py`:
```python
import pytest

import systems.armoury as A
import systems.gear as gear
import systems.smithy as SM
import systems.spoils as SP
from debug.invariants import check_gear
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def someone(game, tag, **data):
    base = {"occupation": "wandering swordsman", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:arms:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def the_sect(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    return sect, halls.seat_of(world, sect)


def join(world, me, sect, rank, role="member"):
    world.relate(me, sect, "member_of", rank, {"role": role, "hall": None, "merit": 0, "status": "member",
                                               "secret": False})


# --- the smith --------------------------------------------------------------------------------------------

def test_a_stall_stocks_by_the_season_capped_by_the_towns_size(game):
    world, town = game.world, game.place.id
    offers = SM.stock(world, town)
    assert 4 <= len(offers) <= 9
    assert all(o["grade"] <= SM.cap(world, town) for o in offers)
    assert SM.stock(world, town) == offers  # the same all season


def test_buying_makes_an_item_by_the_towns_smith_and_selling_pays_half(game):
    world, me, town = game.world, game.player.id, game.place.id
    world.update_data(me, silver=5000)
    offer = SM.stock(world, town)[0]
    cost = SM.price(world, town, offer["slot"], offer["grade"])
    assert SM.buy_block(world, me, town, offer["key"]) is None
    commit(world, SM.buy_events(world, me, town, offer["key"]))
    [item] = gear.gear_items(world, me)
    assert item.data["grade"] == offer["grade"] and item.data["maker"] == SM.smith_name(world, town)
    assert item.data["owners"][-1]["how"] == "bought" and silver_of(world, me) == 5000 - cost
    assert offer["key"] not in {o["key"] for o in SM.stock(world, town)}
    back = SM.sell_price(world, town, item.id)
    assert back == max(1, int(cost * SM.SELL_SHARE))
    commit(world, SM.sell_events(world, me, town, item.id))
    assert gear.gear_items(world, me) == [] and silver_of(world, me) == 5000 - cost + back
    assert check_gear(world) == []


def test_the_poor_cannot_buy(game):
    world, me, town = game.world, game.player.id, game.place.id
    world.update_data(me, silver=0)
    assert SM.buy_block(world, me, town, SM.stock(world, town)[0]["key"]) == "You cannot pay for it."


def test_a_famous_blade_sells_only_to_a_citys_merchant(game):
    world, me, town = game.world, game.player.id, game.place.id
    blade = gear.make_item(world, "weapon", "sword", 3, me, "found", famous=True)
    if world.entity(town).data.get("kind") != "city":
        assert SM.sell_block(world, me, town, blade) is not None
    else:
        pytest.skip("the start is a city")


# --- the armoury ------------------------------------------------------------------------------------------

def test_rank_draws_its_grade_from_the_armoury_and_returns_it(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    assert A.draw_block(world, me, sect, "weapon", seat) is not None  # not a member
    join(world, me, sect, 2)
    assert A.draw_block(world, me, sect, "weapon", game.place.id if game.place.id != seat else -1) is not None
    before = A.table(world, sect)
    commit(world, A.draw_events(world, me, sect, "weapon", seat))
    item = gear.item_in(world, me, "weapon")
    assert item.data["grade"] == 1 and item.data["armoury"] == sect and item.data["owners"][-1]["how"] == "drawn"
    assert A.table(world, sect)[1] == before[1] - 1
    assert A.draw_block(world, me, sect, "weapon", seat) == "You already hold one from the armoury."
    commit(world, A.return_events(world, me, item.id, seat))
    assert A.table(world, sect) == before and gear.item_in(world, me, "weapon") is None
    assert check_gear(world) == []


def test_an_elder_draws_a_treasure_once(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(world, me, sect, 4, role="elder")
    commit(world, A.draw_events(world, me, sect, "weapon", seat))
    assert gear.item_in(world, me, "weapon").data["grade"] == A.ELDER_GRADE
    assert A.allowed(world, me, sect) == A.RANK_GRADE[3]


def test_leaving_with_the_armourys_blade_is_theft(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(world, me, sect, 1)
    commit(world, A.draw_events(world, me, sect, "weapon", seat))
    item = gear.item_in(world, me, "weapon")
    from systems.membership import left_events
    commit(world, left_events(world, me, sect, seat, "deserter"))
    assert world.entity(item.id).data["claimed_by"] == sect
    assert world.facts(predicate="stole", subject=me)


def test_the_armoury_restocks_a_season_at_a_time(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(world, me, sect, 1)
    commit(world, A.draw_events(world, me, sect, "weapon", seat))
    low = min(A.seed_of(world, sect))
    assert A.table(world, sect)[low] == A.seed_of(world, sect)[low] - 1
    A.season_hook(world, 1)
    assert A.table(world, sect)[low] == A.seed_of(world, sect)[low]


# --- the fallen -------------------------------------------------------------------------------------------

def test_taking_from_the_beaten_is_remembered_and_robbery_if_lawful(game):
    world, me = game.world, game.player.id
    loser = someone(game, "loser", traits=["proud", "honest"])
    world.update_data(loser, gear={"weapon": 1, "armour": 0, "form": "saber"})
    assert SP.take_block(world, me, loser, "weapon", game.place.id) == "You have not beaten them."
    commit(world, [Event("duel_ended", (me, loser), game.place.id, {
        "duel": None, "mode": "duel", "result": "won", "reason": "yielded", "verdict": "spare", "by": "player",
        "silver": 0, "crippled": None, "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None,
        "purpose": {}, "killed": False, "left_for_dead": False})])
    assert SP.take_block(world, me, loser, "weapon", game.place.id) is None
    commit(world, SP.take_events(world, me, loser, "weapon", game.place.id))
    item = gear.item_in(world, me, "weapon") or gear.gear_items(world, me)[0]
    assert item.data["owners"][0]["person"] == loser and item.data["owners"][-1]["how"] == "taken"
    assert any(m.feeling == "hatred" and m.indelible for m in world.memories(loser, about=me))
    assert world.facts(predicate="robbed", subject=me)


def test_taking_from_a_bandit_is_no_crime(game):
    world, me = game.world, game.player.id
    bandit = someone(game, "bandit", occupation="bandit")
    world.update_data(bandit, dead=True)
    assert SP.take_block(world, me, bandit, "weapon", game.place.id) is None
    commit(world, SP.take_events(world, me, bandit, "weapon", game.place.id))
    assert not world.facts(predicate="robbed", subject=me)


def test_a_greedy_victor_may_take_your_weapon(game, monkeypatch):
    monkeypatch.setattr(SP, "NPC_TAKES", 1.0)
    world, me = game.world, game.player.id
    if gear.weapon_of(world, me) is None:
        pytest.skip("a hand art: nothing to take")
    victor = someone(game, "victor", traits=["greedy", "cunning"], occupation="bandit")
    commit(world, [Event("duel_ended", (me, victor), game.place.id, {
        "duel": None, "mode": "duel", "result": "lost", "reason": "broken", "verdict": "rob", "by": "opponent",
        "silver": 0, "crippled": None, "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None,
        "purpose": {}, "killed": False, "left_for_dead": False})])
    assert gear.weapon_of(world, me) is None
    assert gear.item_in(world, victor, "weapon") is None and gear.gear_items(world, victor)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_arms_trade.py`
Expected: `ModuleNotFoundError: No module named 'systems.armoury'`.

- [ ] **Step 3: Write the new modules**

`systems/armoury.py`:
```python
"""A sect's armoury (phase 5a spec 4.3): a grade table, drawn from by rank, restocked each season.

The table is counts, not items: a drawn weapon or armour is made then, belongs to the sect (`armoury`) and goes
back to the table when returned. Leaving the sect with one is theft.
"""

import systems.gear as gear
import systems.world_clock as world_clock
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, effect, listen

SEED = {"great": {0: 6, 1: 4, 2: 2, 3: 1}, "other": {0: 4, 1: 2, 2: 1}}
RANK_GRADE = {1: 0, 2: 1, 3: 2}  # rank 1 draws iron, 2 fine, 3 spirit; an elder a treasure, once
ELDER_GRADE = 3
THEFT_WEIGHT = 1.5
LEAVINGS = ("expelled", "deserted", "spy_exposed")


def seed_of(world, faction: int) -> dict[int, int]:
    return dict(SEED["great" if world.entity(faction).data.get("tier") == "great" else "other"])


def table(world, faction: int) -> dict[int, int]:
    """What the armoury holds now: {grade: count} (the seed until anything is drawn)."""
    found = world.entity(faction).data.get("armoury")
    return {int(k): v for k, v in found.items()} if found is not None else seed_of(world, faction)


def allowed(world, person: int, faction: int) -> int | None:
    found = F.membership(world, person, faction)
    if found is None:
        return None
    rank, data = found
    if data.get("status", "member") != "member" or rank < 1:
        return None
    if data.get("role") in ("elder", "leader") and not world.entity(person).data.get("drew_treasure"):
        return ELDER_GRADE
    return RANK_GRADE.get(min(rank, 3))


def drawn_from(world, person: int, faction: int, slot: str) -> int | None:
    return next((i.id for i in gear.gear_items(world, person)
                 if i.data.get("armoury") == faction and i.data["slot"] == slot), None)


def draw_block(world, person: int, faction: int, slot: str, place: int) -> str | None:
    if world.entity(faction).data.get("seat") != place:
        return "The armoury is at the sect's seat."
    best = allowed(world, person, faction)
    if best is None:
        return "Only a disciple of rank may draw from the armoury."
    if drawn_from(world, person, faction, slot) is not None:
        return "You already hold one from the armoury."
    if not any(table(world, faction).get(g, 0) > 0 for g in range(best + 1)):
        return "The armoury has nothing left for you."
    return None


def draw_events(world, person: int, faction: int, slot: str, place: int, form: str | None = None) -> list[Event]:
    best = allowed(world, person, faction)
    stocked = table(world, faction)
    grade = max(g for g in range(best + 1) if stocked.get(g, 0) > 0)
    if slot == "weapon":
        form = form or gear.best_weapon_form(world, person) or "sword"
    else:
        form = form or "mail"
    return [Event("armoury_drawn", (person,), place, {"faction": faction, "slot": slot, "grade": grade,
                                                       "form": form})]


@effect("armoury_drawn")
def _drawn(world, event) -> None:
    person, d = event.actors[0], event.data
    stocked = table(world, d["faction"])
    stocked[d["grade"]] -= 1
    world.update_data(d["faction"], armoury={str(k): v for k, v in stocked.items()})
    if d["grade"] == ELDER_GRADE:
        world.update_data(person, drew_treasure=True)
    item = gear.make_item(world, d["slot"], d["form"], d["grade"], person, "drawn",
                          maker=d["faction"], armoury=d["faction"])
    world.unrelate(person, gear.SLOTS[d["slot"]])
    world.relate(person, item, gear.SLOTS[d["slot"]])


def return_events(world, person: int, item_id: int, place: int) -> list[Event]:
    return gear.pass_events(world, person, None, item_id, place, "returned") + [
        Event("armoury_returned", (person,), place, {"item": item_id, "faction": world.entity(item_id).data["armoury"]})]


@effect("armoury_returned")
def _returned(world, event) -> None:
    d = event.data
    stocked = table(world, d["faction"])
    grade = world.entity(d["item"]).data["grade"]
    stocked[grade] = min(seed_of(world, d["faction"]).get(grade, 0), stocked.get(grade, 0) + 1)
    world.update_data(d["faction"], armoury={str(k): v for k, v in stocked.items()})
    world.update_data(d["item"], in_armoury=True)


def _left_with(world, event, event_id: int) -> None:
    """Leaving the sect with its armoury's gear is theft (spec 4.3)."""
    person, faction = event.actors[0], event.data["faction"]
    taken = [i for i in gear.gear_items(world, person) if i.data.get("armoury") == faction]
    for item in taken:
        world.update_data(item.id, claimed_by=faction)
    if taken:
        variant = make_variant("stole", person, faction, place=place_name(world, event.place))
        record_fact(world, person, "stole", faction, place=event.place, source_event=event_id,
                    weight=THEFT_WEIGHT, variant=variant)


for _kind in LEAVINGS:
    listen(_kind)(_left_with)


def season_hook(world, n: int) -> list:
    """Each season an armoury drawn from gets one more of its lowest grade back, up to its seed."""
    for faction in world.entities_after("faction", "armoury", 0):
        stocked, seed = table(world, faction.id), seed_of(world, faction.id)
        low = min(seed)
        if stocked.get(low, 0) < seed[low]:
            stocked[low] = stocked.get(low, 0) + 1
            world.update_data(faction.id, armoury={str(k): v for k, v in stocked.items()})
    return []


world_clock.SEASON_HOOKS.append(season_hook)
```

`systems/smithy.py`:
```python
"""The smith's stall (phase 5a spec 4.1): seasonal stock capped by the town's size, bought and sold for silver.

A stall's stock is only a seeded list (`stock`) until something is bought: then that offer becomes an item made
by the town's smith. Gear sells back at half its price; a famous weapon only to a rich buyer in a city.
"""

import systems.gear as gear
import systems.lives as lives
from systems import factions as F
from systems.market import drift
from systems.purse import silver_of
from world.events import Event, effect
from world.gen.materialize import people_at
from world.seed import rng_for

BASE = (20, 60, 250, 1000, 4000)  # silver by grade: iron, fine, spirit (and what a buyer pays for more)
ARMOUR_PRICE = 0.8
CAPS = {"village": 0, "town": 1, "city": 2}
SELL_SHARE = 0.5
FAMOUS_PRICE = 20
WEAPONS, ARMOURS = (3, 6), (1, 3)
SMITH_NAMES = ("Iron-Arm", "Old", "Red-Faced", "One-Eyed", "Quiet", "Hammer")


def cap(world, town: int) -> int:
    return CAPS.get(world.entity(town).data.get("kind"), 0)


def _forms(world, town: int) -> list[str]:
    """The weapon forms of the factions nearest this town, else every form."""
    here = world.entity(town).data
    near = sorted(F.ensure_roster(world), key=lambda f: (F.gap(world.entity(f).data["home"], (here["x"], here["y"])), f))
    forms = [f for fid in near[:3] for f in F.FAVOURED.get(world.entity(fid).data["type"], ()) if f in gear.WEAPON_FORMS]
    return sorted(set(forms)) or list(gear.WEAPON_FORMS)


def stock(world, town: int) -> list[dict]:
    """This season's offers: {key, slot, form, grade}, less what has been bought."""
    season = lives.current_season(world)
    rng = rng_for(world.world_seed, f"smith:{town}:{season}")
    top, forms, out = cap(world, town), _forms(world, town), []
    for n in range(rng.randint(*WEAPONS)):
        out.append({"key": f"w{n}", "slot": "weapon", "form": rng.choice(forms), "grade": rng.randint(0, top)})
    for n in range(rng.randint(*ARMOURS)):
        out.append({"key": f"a{n}", "slot": "armour", "form": rng.choice(gear.ARMOURS), "grade": rng.randint(0, top)})
    sold = (world.entity(town).data.get("smith_sold") or {}).get(str(season), [])
    return [o for o in out if o["key"] not in sold]


def price(world, town: int, slot: str, grade: int) -> int:
    base = BASE[grade] * (ARMOUR_PRICE if slot == "armour" else 1.0)
    return max(1, round(base * drift(world, town, "gear")))


def buy_block(world, player: int, town: int, key: str) -> str | None:
    offer = next((o for o in stock(world, town) if o["key"] == key), None)
    if offer is None:
        return "The smith has nothing like that now."
    if silver_of(world, player) < price(world, town, offer["slot"], offer["grade"]):
        return "You cannot pay for it."
    return None


def buy_events(world, player: int, town: int, key: str) -> list[Event]:
    offer = next(o for o in stock(world, town) if o["key"] == key)
    return [Event("gear_bought", (player,), town, {**offer, "season": lives.current_season(world),
                                                    "price": price(world, town, offer["slot"], offer["grade"])})]


def smith_name(world, town: int) -> str:
    rng = rng_for(world.world_seed, f"smith:{town}:name")
    return f"{rng.choice(SMITH_NAMES)} smith of {world.entity(town).name}"


@effect("gear_bought")
def _bought(world, event) -> None:
    player, town, d = event.actors[0], event.place, event.data
    world.update_data(player, silver=silver_of(world, player) - d["price"])
    sold = dict(world.entity(town).data.get("smith_sold") or {})
    season = str(d["season"])
    sold = {season: sold.get(season, []) + [d["key"]]}  # only this season's list is kept
    world.update_data(town, smith_sold=sold)
    gear.make_item(world, d["slot"], d["form"], d["grade"], player, "bought", maker=smith_name(world, town))


def sell_price(world, town: int, item_id: int) -> int:
    item = world.entity(item_id)
    base = price(world, town, item.data["slot"], item.data["grade"])
    if item.data.get("famous"):
        return base * FAMOUS_PRICE
    return max(1, int(base * SELL_SHARE * (0.2 if item.data.get("broken") else 1.0)))


def buyer_for(world, town: int, player: int) -> int | None:
    """Who in a city can pay for a famous blade: a merchant, else a master of a sect present."""
    if world.entity(town).data.get("kind") != "city":
        return None
    here = [p for p in people_at(world, town) if not p.data.get("is_player")]
    rich = [p.id for p in here if p.data.get("occupation") == "merchant"]
    return min(rich) if rich else None


def sell_block(world, player: int, town: int, item_id: int) -> str | None:
    item = world.entity(item_id)
    if item is None or item.kind != "gear" or item_id not in world.targets(player, "owns"):
        return "You do not have that."
    if item.data.get("armoury") is not None:
        return "That belongs to your sect's armoury."
    if item.data.get("famous") and buyer_for(world, town, player) is None:
        return "No one here could pay what it is worth. Try a city's merchants."
    return None


def sell_events(world, player: int, town: int, item_id: int) -> list[Event]:
    famous = world.entity(item_id).data.get("famous")
    buyer = buyer_for(world, town, player) if famous else None
    amount = sell_price(world, town, item_id)
    return gear.pass_events(world, player, buyer, item_id, town, "sold") + [
        Event("gear_sold", (player,) + ((buyer,) if buyer else ()), town, {"item": item_id, "price": amount})]


@effect("gear_sold")
def _sold(world, event) -> None:
    player = event.actors[0]
    world.update_data(player, silver=silver_of(world, player) + event.data["price"])
```

`systems/spoils.py`:
```python
"""What the fallen carried (phase 5a spec 4.2): the victor may take their weapon and armour.

Taking from someone lawful is robbery as the law sees it (a `robbed` fact); from a bandit, a demonic cult's
member, or one with a price on their head, it is not. The living loser never forgets it. An NPC who beats the
player may take the player's weapon: the greedy and the ruthless do, half the time.
"""

import systems.gear as gear
from systems import factions as F
from systems.attitude import is_bandit
from systems.duel import covets
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, Witness, commit, listen
from world.seed import rng_for

THEFT_WEIGHT = 1.5
NPC_TAKES = 0.5
PROUD = frozenset({"proud", "hot-tempered"})


def beaten_by(world, winner: int, loser: int) -> bool:
    """The loser lies dead, or lost their last fight with the winner."""
    if world.entity(loser).data.get("dead"):
        return True
    for entry in world.chronicle_about(winner, limit=40):
        if entry.kind == "duel_ended" and loser in entry.actors:
            return entry.data.get("result") == "won" and entry.data.get("by") == "player"
    return False


def lawful(world, person: int, place: int | None = None) -> bool:
    """Not a bandit, not of a demonic cult, and with no price on their head in this town."""
    if is_bandit(world.entity(person)):
        return False
    if place is not None and world.entity(place).kind == "town":
        from systems.law import bounty  # the law comes after the duel in the import graph
        if bounty(world, place, person) > 0:
            return False
    return not any(world.entity(f).data.get("type") == "demonic_cult" and d.get("status", "member") == "member"
                   for f, _, d in F.memberships(world, person))


def take_block(world, taker: int, loser: int, slot: str, place: int) -> str | None:
    if place not in world.targets(loser, "located_in"):
        return "They are not here."
    if not beaten_by(world, taker, loser):
        return "You have not beaten them."
    carried = gear.weapon_of(world, loser) if slot == "weapon" else gear.armour_of(world, loser)
    if carried is None:
        return "They carry nothing of the kind."
    if slot == "weapon" and carried["item"] is None and gear.best_weapon_form(world, loser) is None \
            and not gear.carried(world, loser).get("form"):
        return "They fought with their hands."
    return None


def take_events(world, taker: int, loser: int, slot: str, place: int) -> list[Event]:
    item = gear.materialize(world, loser, slot)
    living = not world.entity(loser).data.get("dead")
    feelings = ()
    if living:
        proud = PROUD & set(world.entity(loser).data.get("traits", ()))
        feelings = (Witness(loser, "hatred" if proud else "wronged", 0.8, True),)
    return gear.pass_events(world, loser, taker, item, place, "taken") + [
        Event("gear_seized", (taker, loser), place, {"item": item, "lawful": lawful(world, loser, place), "living": living},
              witnesses=feelings)]


@listen("gear_seized")
def _seized(world, event, event_id: int) -> None:
    if not event.data["lawful"]:
        return
    taker, loser = event.actors
    variant = make_variant("robbed", taker, loser, place=place_name(world, event.place))
    record_fact(world, taker, "robbed", loser, place=event.place, source_event=event_id, weight=THEFT_WEIGHT,
                variant=variant)


@listen("duel_ended")
def _victor_takes(world, event, event_id: int) -> None:
    """An NPC who beats the player may take the player's weapon (spec 4.2)."""
    d = event.data
    player, opponent = event.actors
    if d.get("by") != "opponent" or d.get("verdict") in ("kill", "spare") or d.get("mode") in ("spar", "test", "bout"):
        return
    victor = world.entity(opponent)
    ruthless = {"cunning", "greedy"} <= set(victor.data.get("traits", ()))
    if not (covets(victor) or ruthless) or gear.weapon_of(world, player) is None:
        return
    if rng_for(world.world_seed, f"spoils:{event_id}").random() >= NPC_TAKES:
        return
    item = gear.materialize(world, player, "weapon")
    if item is not None:
        commit(world, gear.pass_events(world, player, opponent, item, event.place, "taken"))
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5a_task4.py`:
```python
"""Phase 5a, Task 4: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('debug/invariants.py', r'''                    out.append(f"#{holder} {rel} {item.name} (#{item.id}), which is no {slot}")
''', r'''                    out.append(f"#{holder} {rel} {item.name} (#{item.id}), which is no {slot}")
    import systems.armoury as A
    for faction in world.entities_after("faction", "armoury", 0):
        stocked, seed = A.table(world, faction.id), A.seed_of(world, faction.id)
        if any(v < 0 or v > seed.get(g, 0) for g, v in stocked.items()):
            out.append(f"the {faction.name}'s armoury holds {stocked}, beyond its seed {seed}")
''')
edit('systems/gear.py', r'''    world.update_data(item.id, owners=owners, lost_at=None if d["taker"] is not None else event.place)
''', r'''    lost = d["how"] == "lost"  # dropped where they fell; a thing sold or returned goes to the stall or the armoury
    world.update_data(item.id, owners=owners, lost_at=event.place if lost else None)
''')
edit('systems/law.py', r'''            weight = SCHEME_WEIGHT
''', r'''            weight = SCHEME_WEIGHT
        elif fact.predicate == "stole" and target is not None and target.kind == "faction":
            weight = fact.weight  # a sect's armoury carried off (phase 5a)
''')
edit('systems/standing.py', r'''                value, reason = 0.5, "you struck at our enemies"
''', r'''                value, reason = 0.5, "you struck at our enemies"
        if fact.predicate == "stole" and target == faction_id:
            value, reason = -1.0, "you stole from our armoury"
''')
edit('systems/world_clock.py', r'''import systems.famous  # noqa: E402,F401  phase 5a: famous weapons, how they pass, the Hundred Weapons Chronicle
''', r'''import systems.famous  # noqa: E402,F401  phase 5a: famous weapons, how they pass, the Hundred Weapons Chronicle
import systems.smithy  # noqa: E402,F401  phase 5a: the smith's stall
import systems.armoury  # noqa: E402,F401  phase 5a: a sect's armoury, drawn from and restocked
import systems.spoils  # noqa: E402,F401  phase 5a: what the fallen carried
''')
print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5a_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_arms_trade.py tests/test_gear.py`
Expected: `19 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: sources of gear - the smith's stall, a sect's armoury, and what the fallen carried

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: The player's gear

The inventory and its menu (wield, wear, put away, inspect, return to the armoury, give back an heirloom), the smith's menu, drawing from the armoury, taking the beaten's gear or a famous blade lying here, a duel for a famous blade (ruling 7), the scene's reactions (hatred, a demand, a covetous challenge once a visit, ruling 11), an item's page as the player knows it, the sheet's notes (ruling 12), the Chronicle on the sky page, the brief's blades, help, commands, the heir's inheritance, and two latent faults (ruling 14).

**Files:**
- Create: `engine/gear.py`
- Create: `engine/gear_page.py`
- Create: `narrate/grammar/gear.toml`
- Create: `tests/test_gear_play.py`
- Modify (by `.patches/5a_task5.py`): `engine/commands.py`, `engine/game.py`, `engine/sheet.py`, `engine/sky.py`, `narrate/brief.py`, `narrate/gear_text.py`, `narrate/grammar/realm.toml`, `systems/gear.py`, `systems/succession_crisis.py`

**Interfaces:**
- Consumes: Tasks 1-4: everything above; 4g's duel-for-token pattern (`_start_duel(purpose)`, `_after_duel`); 3a's `known_people`.
- Produces:
  - `engine/gear.py`: `GearMixin` with `_general_extras`, `_conversation_extras`, `_submenu_options` (`gear`, `smith`), `_blade_reactions`, `_after_arrival`, `_after_look`, `_after_duel`, and the `_do_*` handlers `inventory`, `smith`, `wield`, `put_away`, `inspect`, `buy_gear`, `sell_gear`, `draw_gear`, `return_gear`, `return_heirloom`, `take_gear`, `take_lying`, `answer_demand`, `answer_challenge`, `duel_for_weapon`.
  - `engine/gear_page.py`: `history_line`, `inventory_lines`, `known_deeds`, `legends_known`, `item_lines`, `weapon_words`, `armour_words`, `chronicle_lines`.
  - `narrate/gear_text.py`: `gear_facts`, outcomes and journal lines; `narrate/grammar/gear.toml`; `gear._heir_takes_up`.

- [ ] **Step 1: Write the failing tests**

`tests/test_gear_play.py`:
```python
import pytest

import systems.encounters as encounters
import systems.famous as FW
import systems.gear as gear
import systems.provenance as provenance
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.brief import scene_brief
from narrate.outcomes import SUMMARIES
from systems import factions as F
from systems import halls
from systems.beliefs import believe
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


def labels(turn):
    return [c.label for c in turn.all_choices]


def someone(game, tag, **data):
    base = {"occupation": "wandering swordsman", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:play:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def a_blade(game, grade=3, **extra):
    world, me = game.world, game.player.id
    item = gear.make_item(world, "weapon", "sword", grade, me, "found", name="the Test Moon Sword", **extra)
    commit(world, gear.wield_events(world, me, item, game.place.id))
    return item


def test_the_gear_page_lists_what_you_hold_and_lets_you_change_it(game):
    world, me = game.world, game.player.id
    spare = gear.make_item(world, "armour", "mail", 1, me, "bought")
    turn = game.perform(Action("inventory"))
    text = " | ".join(t for t, _ in turn.lines)
    assert "Your gear" in text and "Wielding:" in text
    assert f"Wear {world.entity(spare).name}" in labels(turn)
    game.perform(Action("wield", spare))
    assert gear.item_in(world, me, "armour").id == spare
    assert f"Put away {world.entity(spare).name}" in labels(game.perform(Action("inventory")))


def test_typed_words_reach_your_gear(game):
    world, me = game.world, game.player.id
    spare = gear.make_item(world, "armour", "robe", 0, me, "bought")
    turn = game.perform(Action("inventory"))
    assert parse("gear", turn.choices) == Action("inventory")
    assert parse("wear padded robe", turn.choices, turn.extra) == Action("wield", spare)
    assert parse("unwield", turn.choices) == Action("put_away", "weapon")


def test_the_smith_sells_and_buys(game):
    world, me = game.world, game.player.id
    world.update_data(me, silver=5000)
    turn = game.perform(Action("smith"))
    buys = [c for c in turn.all_choices if c.action.verb == "buy_gear"]
    assert buys
    game.perform(buys[0].action)
    [item] = gear.gear_items(world, me)
    assert f"Sell {item.name}" in " ".join(labels(game.perform(Action("smith"))))


def test_a_member_of_rank_draws_from_the_armoury_at_the_seat(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    label = f"Draw a weapon from the {world.entity(sect).name}'s armoury"
    assert label in labels(game.perform(Action("look")))
    game.perform(Action("draw_gear", (sect, "weapon")))
    assert gear.item_in(world, me, "weapon").data["armoury"] == sect


def test_the_beaten_can_be_stripped_of_their_weapon(game):
    world, me = game.world, game.player.id
    loser = someone(game, "loser")
    world.update_data(loser, gear={"weapon": 1, "armour": None, "form": "saber"})
    [ended] = commit(world, [Event("duel_ended", (me, loser), game.place.id, {
        "duel": None, "mode": "duel", "result": "won", "reason": "yielded", "verdict": "spare", "by": "player",
        "silver": 0, "crippled": None, "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None,
        "purpose": {}, "killed": False, "left_for_dead": False})])
    game._beaten = loser
    label = f"Take {world.entity(loser).name}'s weapon"
    assert label in labels(game.perform(Action("look")))
    game.perform(Action("take_gear", (loser, "weapon")))
    assert any(i.data["owners"][0]["person"] == loser for i in gear.gear_items(world, me))


def test_those_who_know_your_blade_speak_up(game, monkeypatch):
    monkeypatch.setattr(provenance, "COVET_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    item = a_blade(game, claimed_by=sect)
    variant = {"predicate": "blade_legend", "actor": item, "target": None, "count": 1, "place": None, "realm": None,
               "art": None, "form": None, "masked": False, "soft": False, "legend": "a test"}
    fact = world.add_fact(item, "blade_legend", None, place=game.place.id, weight=1.0, is_true=True,
                          data={"variant": variant})
    member = someone(game, "member")
    world.relate(member, sect, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                "secret": False})
    rival = someone(game, "rival", traits=["proud", "cunning"])
    for knower in (member, rival):
        believe(world, knower, fact, variant, None, 1.0, 1, "gossip")
    turn = game.perform(Action("look"))
    assert game.challenger == rival and game._stake == (rival, item)
    game.perform(Action("answer_challenge", False))
    choices = labels(game.perform(Action("look")))
    assert f"Refuse to give up {world.entity(item).name}" in choices
    game.perform(Action("answer_demand", False))
    assert world.facts(predicate="kept_gear", subject=me) and turn


def test_an_item_page_tells_only_what_you_know(game):
    world, me = game.world, game.player.id
    first = someone(game, "first")
    world.unrelate(first, "located_in")  # its first bearer, far away and never met
    giver = someone(game, "giver")
    item = gear.make_item(world, "weapon", "sword", 2, first, "carried")
    commit(world, gear.pass_events(world, first, giver, item, None, "given"))
    commit(world, gear.pass_events(world, giver, me, item, game.place.id, "given"))
    lines = " | ".join(t for t, _ in game.perform(Action("inspect", item)).lines)
    assert "carried by someone" in lines and world.entity(first).name not in lines  # a name never learned
    assert f"given to {world.entity(giver).name}" in lines and "Made by" not in lines


def test_inspecting_your_plain_weapon_gives_it_a_past(game):
    world, me = game.world, game.player.id
    if gear.weapon_of(world, me) is None:
        pytest.skip("a hand art")
    game.perform(Action("inspect", None))
    item = gear.item_in(world, me, "weapon")
    assert item is not None and item.data["owners"][0] == {"person": me, "since": item.data["made_at"], "how": "carried"}


def test_the_sheet_shows_your_weapon_and_what_it_does(game):
    world, me = game.world, game.player.id
    a_blade(game, grade=4)
    text = " | ".join(t for t, _ in sheet_lines(world, me))
    assert "the Test Moon Sword x" in text and "no armour" in text


def test_the_brief_names_a_famous_blade_you_know_by_its_tales(game):
    world, me = game.world, game.player.id
    bearer = someone(game, "bearer")
    item = FW.make_famous(world, "test", "saber", bearer, "made", "a test legend", game.place.id)
    [legend] = world.facts(predicate="blade_legend", subject=item)
    assert not any(world.entity(item).name in f for f in scene_brief(world, game.place.id, me, "t").facts)
    believe(world, me, legend.id, legend.data["variant"], None, 1.0, 1, "gossip")
    assert any(f"{world.entity(bearer).name} carries {world.entity(item).name}" in f
               for f in scene_brief(world, game.place.id, me, "t2").facts)


def test_help_names_the_gear_commands(game):
    assert any("gear | smith | wield" in t for t, _ in game.perform(Action("help")).lines)


def test_every_gear_deed_has_a_journal_line():
    for kind in ("gear_taken_up", "gear_put_away", "gear_passed", "gear_bought", "gear_sold", "armoury_drawn",
                 "armoury_returned", "gear_seized", "heirloom_returned", "blade_demanded"):
        assert kind in SUMMARIES, kind


def test_an_heir_takes_up_the_blade_and_armour_of_the_one_before(game):
    from systems import agendas
    from systems.succession import succession_events
    world, old = game.world, game.player.id
    heir = someone(game, "heir", age=20)
    agendas._pair(world, old, heir, "child")
    blade = a_blade(game)
    robe = gear.make_item(world, "armour", "robe", 1, old, "bought")
    commit(world, gear.wield_events(world, old, robe, game.place.id))
    commit(world, succession_events(world, old, heir))
    assert gear.item_in(world, heir, "weapon").id == blade and gear.item_in(world, heir, "armour").id == robe
    assert world.entity(blade).data["owners"][-1]["how"] == "inherited"
    assert world.targets(old, "wields") == [] and world.targets(old, "wears") == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gear_play.py`
Expected: 13 failed: no gear menu, the typed words unknown (`Action(verb='unknown'...)`), no journal lines (`AssertionError: gear_taken_up`).

- [ ] **Step 3: Write the new modules**

`engine/gear.py`:
```python
"""Weapons and armour in the engine (phase 5a spec 5): the inventory, the smith, the armoury, the fallen's gear,
the blades people know, and duels for a weapon."""

import systems.armoury as armoury
import systems.encounters as encounters
import systems.famous as FW
import systems.gear as gear
import systems.provenance as provenance
import systems.smithy as smithy
import systems.spoils as spoils
from engine.actions import Action, Choice
from engine.gear_page import chronicle_lines, inventory_lines, item_lines
from world.events import commit
from world.gen.materialize import people_at

GEAR_MENUS = ("gear", "smith")


class GearMixin:
    _beaten: int | None = None
    _demand: tuple | None = None
    _stake: tuple | None = None
    _covet_asked: frozenset = frozenset()  # who has already called you out for your blade since you came here

    # --- choices ---------------------------------------------------------------------------------------------
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, here = self.world, self.player.id, self.place.id
        extras.append(Choice("Your gear", Action("inventory")))
        extras.append(Choice("Visit the smith", Action("smith")))
        for faction in world.entity(here).data.get("seats", []):
            for slot, what in (("weapon", "a weapon"), ("armour", "armour")):
                if armoury.draw_block(world, me, faction, slot, here) is None:
                    extras.append(Choice(f"Draw {what} from the {world.entity(faction).name}'s armoury",
                                         Action("draw_gear", (faction, slot))))
        loser = self._beaten
        if loser is not None and world.entity(loser) is not None:
            for slot, what in (("weapon", "weapon"), ("armour", "armour")):
                if spoils.take_block(world, me, loser, slot, here) is None:
                    extras.append(Choice(f"Take {world.entity(loser).name}'s {what}", Action("take_gear", (loser, slot))))
        for item in FW.lying_at(world, here):
            extras.append(Choice(f"Take up {world.entity(item).name}, lying here", Action("take_lying", item)))
        if self._demand is not None:
            demander, item = self._demand
            name = world.entity(item).name
            extras.append(Choice(f"Hand {name} over to {world.entity(demander).name}", Action("answer_demand", True)))
            extras.append(Choice(f"Refuse to give up {name}", Action("answer_demand", False)))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        item = gear.item_in(self.world, npc.id, "weapon")
        if item is not None and item.data.get("famous") and not npc.data.get("beast"):
            extras.append(Choice(f"Challenge them for {item.name}", Action("duel_for_weapon", (npc.id, item.id))))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None or self.submenu not in GEAR_MENUS:
            return options
        world, me, here = self.world, self.player.id, self.place.id
        if self.submenu == "gear":
            choices = []
            for item in gear.gear_items(world, me):
                slot = item.data["slot"]
                held = gear.item_in(world, me, slot)
                if held is None or held.id != item.id:
                    choices.append(Choice(f"{'Wield' if slot == 'weapon' else 'Wear'} {item.name}", Action("wield", item.id)))
                else:
                    choices.append(Choice(f"Put away {item.name}", Action("put_away", slot)))
                choices.append(Choice(f"Inspect {item.name}", Action("inspect", item.id)))
                if item.data.get("armoury") is not None and world.entity(item.data["armoury"]).data.get("seat") == here:
                    choices.append(Choice(f"Return {item.name} to the armoury", Action("return_gear", item.id)))
                if FW.return_block(world, me, item.id, here) is None:
                    choices.append(Choice(f"Give {item.name} back to its clan", Action("return_heirloom", item.id)))
            if gear.item_in(world, me, "weapon") is None and gear.weapon_of(world, me) is not None:
                choices.append(Choice("Inspect your weapon", Action("inspect", None)))
            options["gear"] = (choices, Action("back"))
        else:
            choices = [Choice(f"Buy {gear.gear_name(o['slot'], o['form'], o['grade'])} "
                              f"({smithy.price(world, here, o['slot'], o['grade'])} silver)", Action("buy_gear", o["key"]))
                       for o in smithy.stock(world, here)]
            for item in gear.gear_items(world, me):
                if smithy.sell_block(world, me, here, item.id) is None:
                    choices.append(Choice(f"Sell {item.name} ({smithy.sell_price(world, here, item.id)} silver)",
                                          Action("sell_gear", item.id)))
            options["smith"] = (choices, Action("back"))
        return options

    # --- the scene: blades known ----------------------------------------------------------------------------
    def _blade_reactions(self) -> list:
        world, me, here = self.world, self.player.id, self.place.id
        if gear.item_in(world, me, "weapon") is None or self.combat is not None:
            return []
        present = [p.id for p in people_at(world, here, exclude=me)]
        seen = provenance.reactions(world, me, here, present)
        item = gear.item_in(world, me, "weapon").id
        lines = []
        if seen["hates"]:
            commit(world, provenance.hatred_events(world, me, seen["hates"], here, item))
            names = ", ".join(world.entity(h).name for h in seen["hates"])
            lines.append((f"{names} know{'s' if len(seen['hates']) == 1 else ''} the blade you carry, and whose blood is on it.", "red"))
        if seen["demands"] is not None and self._demand is None:
            self._demand = (seen["demands"], item)
            lines.append((f"{world.entity(seen['demands']).name} knows {world.entity(item).name}: "
                          "their sect calls it its own, and wants it back.", "system"))
        if seen["covets"] is not None and seen["covets"] not in self._covet_asked                 and self.challenger is None and self.encounter is None:
            npc = seen["covets"]
            self._covet_asked = self._covet_asked | {npc}
            lines += self._commit(encounters.challenge_events(me, npc, here))
            self.challenger, self._stake = npc, (npc, item)
            lines.append((f"{world.entity(npc).name} wants {world.entity(item).name}, and will fight you for it.", "system"))
        return lines

    def _after_arrival(self) -> list:
        self._beaten, self._demand, self._covet_asked = None, None, frozenset()
        return super()._after_arrival() + self._blade_reactions()

    def _after_look(self) -> list:
        return super()._after_look() + self._blade_reactions()

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is None or len(entry.actors) < 2:
            return lines
        me, opponent = entry.actors[0], entry.actors[1]
        won = data.get("result") == "won"
        if won:
            self._beaten = opponent
        purpose = data.get("purpose") or {}
        stake = purpose.get("weapon")
        if stake is not None and won and stake in self.world.targets(opponent, "owns"):
            lines += self._commit(gear.pass_events(self.world, opponent, me, stake, self.place.id, "won"))
        if self._stake is not None and self._stake[0] == opponent:
            item = self._stake[1]
            if data.get("by") == "opponent" and item in self.world.targets(me, "owns"):
                lines += self._commit(gear.pass_events(self.world, me, opponent, item, self.place.id, "won"))
            self._stake = None
        return lines

    # --- handlers -------------------------------------------------------------------------------------------
    def _do_inventory(self, _target):
        self.submenu = "gear"
        return self._turn(inventory_lines(self.world, self.player.id) + chronicle_lines(self.world, self.player.id))

    def _do_smith(self, _target):
        self.submenu = "smith"
        lines = [(f"The smith's stall ({smithy.smith_name(self.world, self.place.id)})", "heading")]
        if not smithy.stock(self.world, self.place.id):
            lines.append(("Nothing left this season.", "dim"))
        return self._turn(lines)

    def _do_wield(self, item_id):
        world, me = self.world, self.player.id
        item = world.entity(item_id) if isinstance(item_id, int) else None
        slot = item.data["slot"] if item is not None and item.kind == "gear" else "weapon"
        if (why := gear.fits(world, me, item_id, slot)) is not None:
            return self._turn([(why, "system")])
        self.submenu = "gear"
        return self._turn(self._commit(gear.wield_events(world, me, item_id, self.place.id)))

    def _do_put_away(self, slot):
        self.submenu = "gear"
        events = gear.put_away_events(self.world, self.player.id, slot if slot in gear.SLOTS else "weapon", self.place.id)
        return self._turn(self._commit(events) if events else [("You hold nothing of the kind.", "system")])

    def _do_inspect(self, item_id):
        world, me = self.world, self.player.id
        if item_id is None:  # the plain weapon you carry: looking at it makes it a thing with a past
            item_id = gear.materialize(world, me, "weapon")
        if not isinstance(item_id, int) or item_id not in world.targets(me, "owns"):
            return self._turn([("You have no such thing.", "system")])
        self.submenu = "gear"
        return self._turn(item_lines(world, me, world.entity(item_id)))

    def _do_buy_gear(self, key):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "smith"
        if (why := smithy.buy_block(world, me, here, key)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(smithy.buy_events(world, me, here, key)))

    def _do_sell_gear(self, item_id):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "smith"
        if (why := smithy.sell_block(world, me, here, item_id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(smithy.sell_events(world, me, here, item_id)))

    def _do_draw_gear(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        faction, slot = target if isinstance(target, tuple) else (None, None)
        if faction is None or (why := armoury.draw_block(world, me, faction, slot, here)) is not None:
            return self._turn([(why if faction is not None else "There is no armoury here.", "system")])
        return self._turn(self._commit(armoury.draw_events(world, me, faction, slot, here)))

    def _do_return_gear(self, item_id):
        world, me, here = self.world, self.player.id, self.place.id
        item = world.entity(item_id) if isinstance(item_id, int) else None
        if item is None or item_id not in world.targets(me, "owns") or item.data.get("armoury") is None \
                or world.entity(item.data["armoury"]).data.get("seat") != here:
            return self._turn([("You cannot return that here.", "system")])
        return self._turn(self._commit(armoury.return_events(world, me, item_id, here)))

    def _do_return_heirloom(self, item_id):
        world, me, here = self.world, self.player.id, self.place.id
        if (why := FW.return_block(world, me, item_id, here)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(FW.return_events(world, me, item_id, here)))

    def _do_take_gear(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        loser, slot = target if isinstance(target, tuple) else (None, None)
        if loser is None or (why := spoils.take_block(world, me, loser, slot, here)) is not None:
            return self._turn([(why if loser is not None else "There is nothing to take.", "system")])
        return self._turn(self._commit(spoils.take_events(world, me, loser, slot, here)))

    def _do_take_lying(self, item_id):
        world, me, here = self.world, self.player.id, self.place.id
        if item_id not in FW.lying_at(world, here):
            return self._turn([("It is not here.", "system")])
        return self._turn(self._commit(FW.take_lying_events(world, me, item_id, here)))

    def _do_answer_demand(self, hand_over):
        if self._demand is None:
            return self._turn([("No one asks anything of you.", "system")])
        demander, item = self._demand
        self._demand = None
        if item not in self.world.targets(self.player.id, "owns"):
            return self._turn([("You no longer have it.", "system")])
        return self._turn(self._commit(provenance.demand_events(self.world, self.player.id, demander, item,
                                                                self.place.id, bool(hand_over))))

    def _do_answer_challenge(self, accept):
        if not accept and self._stake is not None and self._stake[0] == self.challenger:
            self._stake = None  # declined: they will not ask again while you stay
        return super()._do_answer_challenge(accept)

    def _do_duel_for_weapon(self, target):
        npc, item = target if isinstance(target, tuple) else (None, None)
        if npc is None or item not in self.world.targets(npc, "owns") or self.focus != npc:
            return self._turn([("They do not hold it.", "system")])
        return self._turn(self._start_duel(npc, "duel", purpose={"weapon": item}))
```

`engine/gear_page.py`:
```python
"""The player's gear on screen (phase 5a spec 5-6): the inventory, an item's page, the sheet's line, the Chronicle.

Knowledge vs truth: an item's page names only the owners the player has met or heard of, and only the deeds they
did themselves or believe a tale of; the maker only if they bought or drew it, or believe a tale naming the maker.
"""

import systems.famous as FW
import systems.gear as gear
from systems.beliefs import known_people
from systems.provenance import LEGENDS

HOW_WORDS = {"carried": "carried by", "bought": "bought by", "taken": "taken by", "drawn": "drawn by",
             "inherited": "inherited by", "won": "won by", "given": "given to", "found": "found by",
             "made": "made for", "sold": "sold by", "returned": "returned by", "lost": "lost by"}


def _label(item) -> str:
    grade = gear.GRADES[item.data["grade"]]
    extra = ", famous" if item.data.get("famous") else ""
    extra += ", broken" if item.data.get("broken") else ""
    extra += ", the sect's" if item.data.get("armoury") is not None else ""
    return f"{item.name} ({grade}{extra})"


def history_line(world, viewer: int, item) -> str:
    known = set(known_people(world, viewer)) | {viewer}
    steps = []
    for step in item.data["owners"][-3:]:
        who = "you" if step["person"] == viewer else world.entity(step["person"]).name \
            if step["person"] in known else "someone"
        steps.append(f"{HOW_WORDS.get(step['how'], step['how'])} {who}")
    return "; ".join(steps) or "no history you know"


def inventory_lines(world, player: int) -> list:
    lines = [("Your gear", "heading")]
    weapon, armour = gear.item_in(world, player, "weapon"), gear.item_in(world, player, "armour")
    held = gear.weapon_of(world, player)
    if weapon is not None:
        lines.append((f"  Wielding: {_label(weapon)} - {history_line(world, player, weapon)}", "dim"))
    elif held is not None:
        lines.append((f"  Wielding: {gear.gear_name('weapon', held['form'] or 'blade', held['grade'])} "
                      f"({gear.GRADES[held['grade']]}), plain and unremarked", "dim"))
    else:
        lines.append(("  Wielding: nothing", "dim"))
    worn = gear.armour_of(world, player)
    if armour is not None:
        lines.append((f"  Wearing: {_label(armour)}", "dim"))
    elif worn is not None:
        lines.append((f"  Wearing: plain armour ({gear.GRADES[worn['grade']]})", "dim"))
    else:
        lines.append(("  Wearing: cloth", "dim"))
    others = [i for i in gear.gear_items(world, player) if i.id not in {getattr(weapon, "id", None), getattr(armour, "id", None)}]
    for item in others:
        lines.append((f"  {_label(item)} - {history_line(world, player, item)}", "dim"))
    return lines


def known_deeds(world, viewer: int, item) -> list[dict]:
    told = {fact.source_event for _, fact in world.known_facts_about([viewer], actors=[item.id])
            if fact.predicate in LEGENDS}
    mine = {e.id for e in world.chronicle_about(viewer, limit=200)}
    return [d for d in item.data["deeds"] if d["event"] in told or d["event"] in mine]


def legends_known(world, viewer: int, item) -> list[str]:
    from narrate.gossip_text import rumour_text  # the narration loads after the engine's pages
    return [rumour_text(world, belief.variant, viewer)
            for belief, fact in world.known_facts_about([viewer], actors=[item.id]) if fact.predicate in LEGENDS]


def item_lines(world, viewer: int, item) -> list:
    d = item.data
    what = d["form"] if d["slot"] == "weapon" else gear.ARMOUR_WORDS[d["form"]]
    lines = [(item.name + (f", {d['epithet']}" if d.get("epithet") else ""), "heading"),
             (f"  {'An' if d['grade'] == 0 else 'A'} {gear.GRADES[d['grade']]} {what}" + (" (broken)" if d.get("broken") else ""), "dim")]
    mine = any(s["person"] == viewer and s["how"] in ("bought", "drawn", "made") for s in d["owners"])
    maker = d.get("maker")
    if maker is not None and mine:
        name = maker if isinstance(maker, str) else world.entity(maker).name
        lines.append((f"  Made by {name}", "dim"))
    lines.append((f"  Its hands: {history_line(world, viewer, item)}", "dim"))
    known = set(known_people(world, viewer)) | {viewer}
    for deed in known_deeds(world, viewer, item):
        whom = deed.get("whom")
        name = "you" if whom == viewer else world.entity(whom).name if whom in known else "someone" if whom else ""
        lines.append((f"  It {({'killed': 'slew', 'bested': 'bested', 'won_tournament': 'won a tournament'})[deed['kind']]}"
                      f"{' ' + name if name else ''}.", "dim"))
    for tale in legends_known(world, viewer, item)[:3]:
        lines.append((f"  Known as: {tale}", "dim"))
    return lines


def weapon_words(world, player: int, form: str) -> str:
    """The sheet's note on an art: what the weapon in hand does for it (spec 5); hand arts need none."""
    if form not in gear.WEAPON_FORMS:
        return ""
    item = gear.item_in(world, player, "weapon")
    held = gear.weapon_of(world, player)
    name = item.name if item is not None else ("a plain weapon" if held else "bare hands")
    return f" | {name} x{gear.weapon_mult(world, player, form):.2f}"


def armour_words(world, player: int) -> str:
    share = gear.armour_share(world, player)
    return f"armour takes {share:.0%} off a wound" if share else "no armour"


def chronicle_lines(world, player: int) -> list:
    known = FW.chronicle_known(world, player)
    if known is None:
        return []
    lines = [("", "default"), (f"The Hundred Weapons Chronicle (year {known['year']})", "heading")]
    for rank, item_id in enumerate(known["order"][:10], 1):
        item = world.entity(item_id)
        if item is not None:
            lines.append((f"  {rank}. {item.name} ({gear.GRADES[item.data['grade']]})", "dim"))
    return lines
```

`narrate/grammar/gear.toml`:
```toml
[symbols]
steel_air = ["Steel rings somewhere, far off.", "The edge catches the light.", "Old blood leaves no stain you can see.", "A blade is only as honest as its hand.", "Somewhere a smith's hammer keeps time.", "The grip is worn smooth by other hands."]

[gear_taken_up]
colour = "dim"  # routine: the steel_air may come round again
lines = ["#steel_air#"]

[gear_put_away]
colour = "dim"
lines = ["#steel_air#"]

[gear_passed]
colour = "dim"
lines = ["#steel_air#"]

[gear_bought]
colour = "dim"
lines = ["The smith wraps it in oiled cloth.", "The smith weighs your silver twice.", "#steel_air#"]

[gear_sold]
colour = "dim"
lines = ["The smith turns it over and names a price.", "#steel_air#"]

[armoury_drawn]
colour = "dim"
lines = ["Racks of steel, each blade tagged with a number.", "#steel_air#"]

[armoury_returned]
colour = "dim"
lines = ["#steel_air#"]

[gear_seized]
colour = "red"
lines = ["#steel_air#"]

[heirloom_returned]
colour = "gold"
lines = ["A hall falls quiet as the old blade comes home.", "The clan's elders bow to the blade before they bow to you.", "Someone at the back of the hall weeps openly.", "Incense is lit before the blade has touched the rack.", "The clan head's hands are not quite steady.", "Old names are spoken, and yours after them."]

[blade_demanded]
colour = "dim"
lines = ["#steel_air#"]
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5a_task5.py`:
```python
"""Phase 5a, Task 5: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('engine/commands.py', r'''    "examine body": Action("examine_body"), "examine the body": Action("examine_body"),
''', r'''    "examine body": Action("examine_body"), "examine the body": Action("examine_body"),
    "gear": Action("inventory"), "inventory": Action("inventory"), "i": Action("inventory"),
    "smith": Action("smith"), "unwield": Action("put_away", "weapon"), "sheathe": Action("put_away", "weapon"),
''')
edit('engine/commands.py', r'''    "open": "open_meridian", "use": "use", "declare": "declare_for", "accuse": "accuse",
''', r'''    "open": "open_meridian", "use": "use", "declare": "declare_for", "accuse": "accuse",
    "wield": "wield", "wear": "wield", "inspect": "inspect", "buy": "buy_gear", "sell": "sell_gear",
''')
edit('engine/game.py', r'''from engine.crisis import CrisisMixin
''', r'''from engine.crisis import CrisisMixin
from engine.gear import GearMixin
''')
edit('engine/game.py', r'''    ("  F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu", "system"),
]


class Game(IntrigueMixin, CrisisMixin, SealedMixin, RivalMixin, ChamberMixin, DelveMixin, LineageMixin, MarketMixin, SkyMixin, TournamentMixin, WorldMixin, FactionsMixin, JoiningMixin, RanksMixin, DutiesMixin, PoliticsMixin, LeavingMixin, LawMixin, LandMixin, FoundingMixin, SectMixin, SeasonsMixin, GossipMixin, MasksMixin, InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks):
''', r'''    ("  gear | smith | wield <item> | wear <item> | unwield | inspect <item>: weapons and armour", "system"),
    ("  F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu", "system"),
]


class Game(GearMixin, IntrigueMixin, CrisisMixin, SealedMixin, RivalMixin, ChamberMixin, DelveMixin, LineageMixin, MarketMixin, SkyMixin, TournamentMixin, WorldMixin, FactionsMixin, JoiningMixin, RanksMixin, DutiesMixin, PoliticsMixin, LeavingMixin, LawMixin, LandMixin, FoundingMixin, SectMixin, SeasonsMixin, GossipMixin, MasksMixin, InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks):
''')
edit('engine/sheet.py', r'''
from narrate.base import Line
''', r'''
from engine.gear_page import armour_words, weapon_words
from narrate.base import Line
''')
edit('engine/sheet.py', r'''        (f"Insight {body.insight:.1f} | silver {player.data.get('silver', 0)}", "default"),
''', r'''        (f"Insight {body.insight:.1f} | silver {player.data.get('silver', 0)} | {armour_words(world, player_id)}", "default"),
''')
edit('engine/sheet.py', r'''            f" | {compat_words(compat)} ({compat:.2f}) | completeness {art.known_completeness:.0%}", "default",
''', r'''            f" | {compat_words(compat)} ({compat:.2f}) | completeness {art.known_completeness:.0%}"
            f"{weapon_words(world, player_id, data['form']) if art.category != 'heart_method' else ''}", "default",
''')
edit('engine/sky.py', r'''        return self._turn(lines + sky_crisis_lines(world, me))
''', r'''        from engine.gear_page import chronicle_lines  # phase 5a
        return self._turn(lines + sky_crisis_lines(world, me) + chronicle_lines(world, me))
''')
edit('narrate/brief.py', r'''    facts += intrigue_facts(world, place_id, player_id)
''', r'''    facts += intrigue_facts(world, place_id, player_id)
    from narrate.gear_text import gear_facts  # the famous blades carried here (phase 5a)
    facts += gear_facts(world, place_id, player_id)
''')
edit('narrate/gear_text.py', r'''    return "Gave back a blade a sect called its own." if entry.data["handed"] else "Kept a blade a sect called its own."
''', r'''    return "Gave back a blade a sect called its own." if entry.data["handed"] else "Kept a blade a sect called its own."


HOW_LINES = {"taken": "You take {item}.", "won": "{item} is yours by the fight.", "found": "You take up {item}.",
             "given": "{item} changes hands.", "inherited": "{item} passes to its heir.", "sold": "You sell {item}.",
             "returned": "You give {item} back to the armoury.", "lost": "{item} is left where it fell."}


def gear_facts(world, town: int, player: int) -> list[str]:
    """The famous blades the player knows by their tales, carried by people here (spec 5)."""
    from systems.provenance import known_blades
    from world.gen.materialize import people_at
    present = [p.id for p in people_at(world, town, exclude=player)]
    return [f"{world.entity(p).name} carries {world.entity(i).name}." for p, i in known_blades(world, player, present)]


@outcome("gear_taken_up", body_facts=False)
def _taken_up(world, event):
    item = world.entity(event.data["item"])
    return [f"You {'take up' if item.data['slot'] == 'weapon' else 'put on'} {item.name}."], {}


@summary("gear_taken_up")
def _taken_up_line(world, entry, names, place, other):
    return f"Took up {world.entity(entry.data['item']).name}."


@outcome("gear_put_away", body_facts=False)
def _put_away(world, event):
    return [f"You put away {world.entity(event.data['item']).name}."], {}


@summary("gear_put_away")
def _put_away_line(world, entry, names, place, other):
    return f"Put away {world.entity(entry.data['item']).name}."


@outcome("gear_passed", body_facts=False)
def _passed(world, event):
    item = world.entity(event.data["item"])
    return [HOW_LINES.get(event.data["how"], "{item} changes hands.").format(item=item.name)], {}


@summary("gear_passed")
def _passed_line(world, entry, names, place, other):
    return HOW_LINES.get(entry.data["how"], "{item} changed hands.").format(item=world.entity(entry.data["item"]).name)


@outcome("gear_bought", body_facts=False)
def _bought(world, event):
    from systems.gear import gear_name
    d = event.data
    return [f"You pay {d['price']} silver for {gear_name(d['slot'], d['form'], d['grade'])}."], {}


@summary("gear_bought")
def _bought_line(world, entry, names, place, other):
    return f"Bought gear at {place} for {entry.data['price']} silver."


@outcome("gear_sold", body_facts=False)
def _sold(world, event):
    return [f"{event.data['price']} silver changes hands."], {}


@summary("gear_sold")
def _sold_line(world, entry, names, place, other):
    return f"Sold {world.entity(entry.data['item']).name} at {place}."


@outcome("armoury_drawn", body_facts=False)
def _drawn(world, event):
    d = event.data
    return [f"The armoury's keeper hands you {d['form'] if d['slot'] == 'weapon' else 'armour'} of {world.entity(d['faction']).name}'s stock."], {}


@summary("armoury_drawn")
def _drawn_line(world, entry, names, place, other):
    return f"Drew from the {world.entity(entry.data['faction']).name}'s armoury."


@outcome("armoury_returned", body_facts=False)
def _returned(world, event):
    return ["The keeper takes it back and marks the ledger."], {}


@summary("armoury_returned")
def _returned_line(world, entry, names, place, other):
    return "Returned gear to the armoury."


@outcome("gear_seized", body_facts=False)
def _seized(world, event):
    item = world.entity(event.data["item"])
    return [f"You take {item.name} from {world.entity(event.actors[1]).name}."
            + (" The law will call it robbery." if event.data["lawful"] else "")], {}


@summary("gear_seized")
def _seized_line(world, entry, names, place, other):
    return f"Took {world.entity(entry.data['item']).name} from {other}."


@outcome("heirloom_returned", body_facts=False)
def _heirloom(world, event):
    return [f"{world.entity(event.actors[1]).name} takes {world.entity(event.data['item']).name} in both hands. "
            "The clan will not forget this."], {}


@summary("heirloom_returned")
def _heirloom_line(world, entry, names, place, other):
    return f"Gave {world.entity(entry.data['item']).name} back to its clan."
''')
edit('narrate/grammar/realm.toml', r'''realm_air = ["The air is thick with old qi.", "Dust hangs in the lamplight of no lamp.", "Somewhere water drips on stone.", "The walls are carved with forms no one has practised in a thousand years.", "Your breath comes slow in the dense air.", "Far off, something vast shifts in its sleep."]
''', r'''realm_air = ["The air is thick with old qi.", "Dust hangs in the lamplight of no lamp.", "Somewhere water drips on stone.", "The walls are carved with forms no one has practised in a thousand years.", "Your breath comes slow in the dense air.", "Far off, something vast shifts in its sleep.", "A draught comes from nowhere and smells of iron.", "Your footsteps come back to you a heartbeat late.", "The stone is warm, as if something lay here a moment ago.", "A faint hum rises from the floor and fades.", "Old sword marks score the pillars.", "The dark ahead is darker than it should be.", "Something small skitters out of the lamplight.", "The qi here pulls at your meridians like a tide."]
''')
edit('systems/gear.py', r'''from world.events import Event, effect
''', r'''from world.events import Event, effect, listen
''')
edit('systems/gear.py', r'''import systems.provenance  # noqa: E402,F401  (what a weapon has done: registers its listeners)
''', r'''import systems.provenance  # noqa: E402,F401  (what a weapon has done: registers its listeners)


@listen("succession")
def _heir_takes_up(world, event, event_id: int) -> None:
    """The heir takes up what the one before them wielded and wore, and their plain carried gear (4b, spec 4.4)."""
    old, heir = event.actors
    for slot, rel in SLOTS.items():
        for item in world.targets(old, rel):
            world.unrelate(old, rel, item)
            world.unrelate(heir, rel)
            world.relate(heir, item, rel)
    for item in gear_items(world, heir):
        owners = item.data["owners"]
        if owners and owners[-1]["person"] == old:
            world.update_data(item.id, owners=owners + [{"person": heir, "since": world.time, "how": "inherited"}])
    carried_by_old = world.entity(old).data.get("gear")
    if carried_by_old is not None:
        world.update_data(heir, gear=dict(carried_by_old))
''')
edit('systems/succession_crisis.py', r'''    people = [c["person"] for c in crisis["claimants"]]
''', r'''    people = [c["person"] for c in crisis["claimants"]]
    if not people:
        return  # every claimant struck before the heralds cried it (a failed founder's test): no one to name
''')
print("task 5 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5a_task5.py`
Expected: `task 5 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gear_play.py tests/test_sheet.py tests/test_commands.py`
Expected: `26 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the player's gear - the inventory, the smith, the armoury, spoils, blades known in a scene, an item's page

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: Items with history end to end

The fork guide's section 10, the speed of gear in a fight, the Chronicle and a turn, lazy gear left unmade, and an armed wanderer played at random.

**Files:**
- Create: `tests/test_gear_fuzz.py`
- Create: `tests/test_gear_season.py`
- Modify (by `.patches/5a_task6.py`): `docs/world-events.md`

**Interfaces:**
- Consumes: Everything above.
- Produces:
  - `docs/world-events.md` section 10.
  - `tests/test_gear_fuzz.py`: `test_an_armed_wanderer`.

- [ ] **Step 1: Write the failing tests**

`tests/test_gear_fuzz.py`:
```python
"""An armed wanderer, played at random (phase 5a): buys, draws, takes, wields, sells and fights for famous
blades; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing


@pytest.mark.parametrize("seed", [3, 29])
def test_an_armed_wanderer(tmp_path, seed, monkeypatch):
    import systems.famous as FW
    import systems.provenance as provenance
    from systems import factions as F
    from systems import halls
    monkeypatch.setattr(provenance, "COVET_CHANCE", 0.5)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Blade{seed}", world_seed=seed)
    world = app.game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    halls.staff_at(world, sect, seat)
    me = world.get_meta("player_id")
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    world.update_data(me, silver=5000)
    FW.ensure_famous(world)
    for item in FW.famous_weapons(world):  # the player has heard every tale: every blade is known on sight
        for fact in world.facts(predicate="blade_legend", subject=item):
            from systems.beliefs import believe
            believe(world, me, fact.id, fact.data["variant"], None, 1.0, 1, "gossip")
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
            app.submit(rng.choice(["gear", "smith", "unwield", "look", "rest", "journal", "sky", "standing",
                                   "wield " + rng.choice(("sword", "saber", "spear", "staff", "robe", "mail")),
                                   "inspect " + rng.choice(("sword", "saber", "spear", "staff")), "challenge"]))
        if rng.random() < 0.05:
            app.handle_key("f4", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    assert happened & {"gear_bought", "armoury_drawn", "gear_taken_up", "gear_passed"}, happened
    app.shutdown()
```

`tests/test_gear_season.py`:
```python
import gc
import time
from pathlib import Path

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.famous as FW
import systems.gear as gear
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
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


def average(fn, n=10) -> float:
    """CPU time per call, averaged: Windows' CPU clock ticks in 15.6 ms steps (4e ruling 19)."""
    fn()
    gc.collect()
    start = time.process_time()
    for _ in range(n):
        fn()
    return (time.process_time() - start) / n


def staffed(world):
    for fid in F.ensure_roster(world):
        seat = halls.seat_of(world, fid)
        if seat is not None:
            halls.staff_at(world, fid, seat)


def test_the_fork_guide_covers_items_with_history():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("famous_weapons", "gear.POWER", "materialize", "wields", "DEED_HOOKS", "BREAK_CHANCE",
                 "claimed_by", "check_gear", "weapons_ranked", "armoury"):
        assert word in guide, word


def test_reading_gear_adds_little_to_a_duel(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    art = duel.best_art(world, elder)
    technique = art.technique.id if art else None
    with_gear = average(lambda: duel.fighter_for(world, elder, technique), n=50)
    assert average(lambda: (gear.weapon_mult(world, elder, "sword"), gear.armour_share(world, elder)), n=50) < 0.001
    assert with_gear < 0.02


def test_the_chronicle_survey_stays_cheap(game):
    world = game.world
    staffed(world)
    FW.ensure_famous(world)
    assert FW.famous_weapons(world)
    assert average(lambda: FW.chronicle_events(world, 4)) < 0.02


def test_a_turn_with_a_known_blade_costs_little(game):
    world, me = game.world, game.player.id
    staffed(world)
    FW.ensure_famous(world)
    item = gear.make_item(world, "weapon", "sword", 3, me, "found")
    commit(world, gear.wield_events(world, me, item, game.place.id))
    assert average(lambda: game.perform(Action("look"))) < 0.05


def test_lazy_gear_makes_nothing_for_those_who_never_matter(game):
    world = game.world
    before = len(world.entities("gear"))
    staffed(world)
    for fid in F.ensure_roster(world):
        for person in halls.staff_at(world, fid, halls.seat_of(world, fid)) if halls.seat_of(world, fid) else []:
            gear.weapon_mult(world, person, "sword")
            gear.armour_share(world, person)
    assert len(world.entities("gear")) == before
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gear_fuzz.py tests/test_gear_season.py`
Expected: 1 failed, 6 passed: the fork guide (`AssertionError: famous_weapons`); the speed tests and the fuzz already pass.

- [ ] **Step 3: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5a_task6.py`:
```python
"""Phase 5a, Task 6: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('docs/world-events.md', r'''struck from the claims, and exiles with a return to come.
''', r'''struck from the claims, and exiles with a return to come.

## 10. Items with history (phase 5a)

A weapon or an armour is a `gear` entity: its `slot`, `form`, `grade` (0 iron to 4 divine; `gear.POWER` multiplies an
art of its form, `gear.ARMOUR_SHARE` softens a wound), `maker`, `owners` (who held it and how), `deeds` (its twelve
weightiest), and the marks `famous`, `epithet`, `armoury`, `heirloom_of`, `claimed_by`, `lost_at` and `broken`. A
person `wields` one weapon and `wears` one armour, each an item they own.

**Lazy gear:** an NPC carries only a seeded grade (`gear.seeded`), or their own record (`gear` on the person), until
it matters; `gear.materialize` then makes the item, its history begun. Nothing is made for those who never matter.

**Where the rules live:**
- `systems/gear.py`: grades, what someone carries, items, taking up and putting away, passing hands, breakage
  (`BREAK_CHANCE`, its own roll), the heir's inheritance.
- `systems/provenance.py`: deeds and `DEED_HOOKS`, the legend (`wielded_in`), knowing a blade on sight, and what
  people do about it (covet, hate, demand it back).
- `systems/famous.py`: the famous weapons (`famous_weapons`, seeded once their keeper exists), how they pass at a
  death, heirlooms, epithets, and the Hundred Weapons Chronicle (`weapons_ranked`).
- `systems/smithy.py`, `systems/armoury.py`, `systems/spoils.py`: the smith's stall, a sect's armoury, the fallen's gear.

**The rules:** `check_gear` in `debug/invariants.py` holds one owner per item and an owner that ends its history,
wielding only what one owns (one at a time), deeds that happened, famous weapons listed once, and armouries within
their seed.
''')
print("task 6 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5a_task6.py`
Expected: `task 6 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gear_season.py tests/test_gear_fuzz.py`
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
git commit -m "feat: items with history end to end - the fork guide, speed, and an armed wanderer's fuzz

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Self-review

- **Spec coverage:**
  - §2.1-2.3 grades, weapons, armour, breakage (Task 1); §2.4-2.5 items and lazy gear (Task 1);
  - §3.1-3.2 deeds, legend, recognition (Task 2); §3.3 famous weapons, heirlooms, epithets, the Chronicle (Task 3); §3.4 far away (Task 3, ruling 10);
  - §4.1 the smith, §4.2 the fallen, §4.3 the armoury (Task 4); §4.4 wagers (ruling 7) and lineage (Task 5);
  - §5 the player (Task 5), §6 knowledge (Tasks 2, 5), §7 `check_gear` (Tasks 1, 3, 4), §8 LOD and speed (Tasks 1, 6), §9 testing (every task; the fuzz and speed in Task 6).
- **Dry run:**
  - every task was applied in order to a copy of master; its tests failed as each Step 2 says, then passed;
  - the whole suite passed after every task, and the 500-year soak passed at the end.
