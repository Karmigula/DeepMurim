# Phase 3b: Factions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Factions live in the world as real NPCs. The player can join one, pass its trial, rise through its ranks by doing duties, learn its arts, get caught up in its politics, carry its enmities, face the law, and leave or betray it.

**Architecture:** Factions are entities. Membership is a `member_of` relation. Faction knowledge is the gossip pool of the faction's seat and branch towns (3a beliefs), so standing, taboos and bounties come from what the faction has *heard*.

Each area has its own system module and its own engine mixin, so no task rewrites another task's file:

| Area | System | Engine mixin | Narration | Grammar |
|---|---|---|---|---|
| halls | `systems/halls.py` | `FactionsMixin` | `faction_text.py` | `factions.toml` |
| joining | `systems/membership.py` | `JoiningMixin` | `faction_text.py` | `factions.toml` |
| ranks | `systems/ranks.py` | `RanksMixin` | `faction_text.py` | `factions.toml` |
| duties | `systems/duties.py` | `DutiesMixin` | `duty_text.py` | `duties.toml` |
| politics | `systems/politics.py` | `PoliticsMixin` | `politics_text.py` | `politics.toml` |
| leaving | `systems/leaving.py` | `LeavingMixin` | `politics_text.py` | `politics.toml` |
| law | `systems/law.py` | `LawMixin` | `law_text.py` | `law.toml` |

New encounters and challenges plug into two small registries added to `systems/encounters.py`: `ROAD_HOOKS` and `HUNTER_HOOKS`.

**Tech Stack:** Python 3.12, SQLite (save format v2, unchanged), pygame-ce (unchanged), pytest.

**Spec:** `docs/superpowers/specs/2026-09-23-phase3b-factions-design.md`. It builds on the 3a spec, `docs/superpowers/specs/2026-09-23-phase3a-social-rumours-design.md`.

## Global Constraints

- The schema stays at version 2. There are no new tables; factions, duties and bounties use entities, relations, facts and beliefs.
- What a faction knows comes only from beliefs: the pools of its seat and branch towns (3a `world.known_facts(town)`). Standing, taboos and bounties never read `facts.is_true`.
- Masked deeds count for the persona. Subject resolution goes through `systems/beliefs.py` (`true_identity`, `apparent_to`) exactly as in 3a.
- A menu shows at most 9 choices. Extras fold into `Turn.extra`. Faction actions live in a *Faction matters...* submenu.
- Every new event kind gets a grammar table with at least 6 distinct expansions (`tests/test_repeat.py` enforces this), an outcome builder, and a journal summary.
- Every new grammar symbol name is prefixed with its file's area (`faction_`, `duty_`, `politics_`, `law_`), because symbols share one namespace.
- Briefs keep at most 6 facts, at most 1,200 characters, and no ids.
- Each seeded roll uses `rng_for(world.world_seed, <path>)`, with the paths named in the spec or in the task.
- Time is counted in watches, 4 per day.
- Test command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.

## Review Focus

1. **A faction member dies.** Killing your sponsor, a hall keeper, or a duty's debtor or target must not leave an open duty, trial or summons that can never finish. It fails cleanly. Task 6 pins this with `test_a_dead_target_fails_the_duty`.
2. **Travelling during an open trial or duty.** Deadlines pass while you travel or rest for a season, and the failure is announced once, not every turn. Task 6 pins this with `test_an_overdue_duty_fails_once`.
3. **Loading a save made during a summons or arrest.** The pending state must come back and still gate actions. Task 7 pins this with `test_a_summons_survives_a_reload`, and Task 9 with `test_an_arrest_survives_a_reload`.
4. **Old 3a saves.** Towns have no `factions_ready` flag, and the world has no roster. Loading creates the roster and settles the current town. Task 2 pins this with `test_an_old_save_gets_factions_on_load`.
5. **A crowded conversation menu.** With the faction entry added, the main conversation menu still shows 9 at most and folds the rest. Task 2 pins this with `test_the_conversation_menu_stays_within_nine`.

## Plan-time rulings (deviations from the spec, argued)

1. **Faction knowledge** is only the seat and branch towns' pools, not members' personal beliefs. That keeps it one query per town. *Cost if wrong:* a deed that only a member witnessed reaches the faction one gossip hop later.
2. **Delivery and escort duties** pay their merit on arrival, not at the next hall visit, which saves a pending-merit state. *Cost if wrong:* rewards arrive earlier than the spec intended.
3. **A sealed letter** is duty data, not an item entity. *Cost if wrong:* the letter can't be stolen or lost.
4. **Person labels:** the "Here:" list tags staff and natural members of factions that have a hall in this town (they wear insignia). A member met elsewhere is not tagged. *Cost if wrong:* a little less labelling than the spec describes.
5. **Beggars, guild and imperial branches** need a natural member in the town: a beggar, a merchant or a constable. No extra staff are created for them, so ordinary towns stay the same size. *Cost if wrong:* some towns have no hall for those factions.
6. **Deny at judgement** is always offered, because showing it only for false charges would leak the truth. Its chance uses the spec's formula, which already rewards a contradicting witness. *Cost if wrong:* a guilty player can gamble on denial.
7. **Release by final duty** issues an ordinary duty flagged `release`. Completing it releases you.
8. **Guard-duty raids** use a seeded raider NPC, a member of a hostile faction created in the seat town, fought in `duel` mode.
9. **A 3a latent crash:** the journal summary for `encounter_resolved` with how `backed_off` raised `KeyError`. Task 1 fixes it, with a test.

---

### Task 1: The faction roster, minor factions and stances

**Files:**
- Create: `systems/factions.py`
- Modify (via `.patches/3b_task1.py`): `engine/game.py` (create the roster on new and load), `narrate/road_text.py` (the `backed_off` journal summary)
- Test: `tests/test_factions.py`

**Interfaces:**
- Consumes: `world.gen.materialize.ensure_town`, `world.gen.region.region_spec`, `world.gen.names.person_name`, `systems.techniques.FORMS`.
- Produces (all in `systems.factions`):
  - Tables: `LADDERS`, `PATHS`, `MARTIAL`, `STAFFED`, `BRANCHING`, `NATURAL`, `BASE_REALM`, `ROSTER`, `HOSTILE = -0.5`.
  - Roster and places: `ensure_roster(world) -> list[int]`, `minor_factions(world, region_entity) -> list[int]`, `gap(a, b) -> int`.
  - Stances: `base_stance(type_a, type_b) -> float`, `stance(world, a, b) -> float`.
  - Members: `memberships(world, person) -> list[(faction_id, rank, data)]`, `membership(world, person, faction) -> (rank, data) | None`, `members_of(world, faction) -> list[int]`.
  - Descriptions: `is_martial(world, faction) -> bool`, `title(world, faction, rank) -> str`.
- Faction entity data: `{type, tier, home: [x, y], seat, path, ranks, power, wealth, treasury, forms, arts, branches}`, with seed path `world/faction:{i}` (great) or `{region_path}/minor:{i}`. `world.get_meta("roster")` is the list of great faction ids.

- [ ] **Step 1: Write the failing test** — `tests/test_factions.py`
```python
from collections import Counter

import pytest

from engine.game import Action, Game
from systems import factions as F
from systems.creation import CreationChoice
from world.db import World
from world.events import Event, commit
from world.gen.materialize import ensure_region, region_of


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "w.world", 11)
    yield w
    w.close()


def test_every_world_has_ten_great_factions(world):
    ids = F.ensure_roster(world)
    kinds = Counter(world.entity(i).data["type"] for i in ids)
    assert kinds == Counter({"orthodox_sect": 3, "demonic_cult": 1, "unorthodox_clan": 1, "martial_clan": 1,
                             "beggars": 1, "merchant_guild": 1, "imperial": 1, "alliance": 1})
    names = [world.entity(i).name for i in ids]
    assert len(set(names)) == 10
    assert F.ensure_roster(world) == ids


def test_the_roster_is_seeded(tmp_path):
    rosters = []
    for n in range(2):
        w = World.create(tmp_path / f"r{n}.world", 42)
        rosters.append([(w.entity(i).name, tuple(w.entity(i).data["home"])) for i in F.ensure_roster(w)])
        w.close()
    assert rosters[0] == rosters[1]


def test_a_sect_is_near_the_start_and_the_capital_powers_share_a_home(world):
    factions = [world.entity(i) for i in F.ensure_roster(world)]
    first_sect = next(f for f in factions if f.data["type"] == "orthodox_sect")
    assert F.gap(first_sect.data["home"], (0, 0)) <= 2
    capital = {tuple(f.data["home"]) for f in factions if f.data["type"] in ("beggars", "merchant_guild", "imperial", "alliance")}
    assert len(capital) == 1 and F.gap(next(iter(capital)), (0, 0)) <= 3
    assert all(F.gap(f.data["home"], (0, 0)) <= 6 for f in factions)
    assert first_sect.data["ranks"][0] == "outer disciple" and first_sect.data["path"] == "righteous"


def test_stances_are_symmetric_and_follow_the_old_feuds(world):
    ids = F.ensure_roster(world)
    by_type = {}
    for i in ids:
        by_type.setdefault(world.entity(i).data["type"], []).append(i)
    sect, cult = by_type["orthodox_sect"][0], by_type["demonic_cult"][0]
    assert F.stance(world, sect, cult) == F.stance(world, cult, sect) == -0.8
    assert F.stance(world, sect, by_type["orthodox_sect"][1]) == 0.6
    assert F.stance(world, sect, by_type["alliance"][0]) == 0.8
    assert F.stance(world, by_type["imperial"][0], cult) == -0.6
    assert F.stance(world, sect, by_type["beggars"][0]) == 0.0
    assert F.stance(world, sect, sect) == 1.0


def test_minor_factions_are_seeded_per_region(world):
    F.ensure_roster(world)
    seen = []
    for x in range(-3, 4):
        region = world.entity(ensure_region(world, x, 0))
        minors = F.minor_factions(world, region)
        assert len(minors) <= 2 and F.minor_factions(world, world.entity(region.id)) == minors
        for fid in minors:
            data = world.entity(fid).data
            assert data["tier"] == "minor" and data["type"] in ("school", "bandit_fort", "local_clan")
            assert region_of(world, data["seat"]).id == region.id
            seen.append(fid)
    assert seen
    forts = [f for f in seen if world.entity(f).data["type"] == "bandit_fort"]
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    for fort in forts:
        assert F.stance(world, fort, sect) == -0.5


def test_a_new_game_has_its_roster_and_a_bandit_backing_off_reads_in_the_journal(tmp_path):
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    game.start()
    assert len(game.world.get_meta("roster")) == 10
    bandit = game.world.add_entity("person", "Ma Bo", {"occupation": "bandit", "realm": "mortal"})
    commit(game.world, [Event("encounter_resolved", (game.player.id, bandit), game.place.id,
                              {"how": "backed_off", "kind": "bandit"})])
    assert any("Ma Bo" in text for text, _ in game.perform(Action("journal")).lines)
    game.close()
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_factions.py -q -p no:cacheprovider`
Expected: the collection error `ImportError: cannot import name 'factions' from 'systems'`, or `ModuleNotFoundError`.

- [ ] **Step 3: Write the roster** — `systems/factions.py`
```python
"""Factions in the world (phase 3b spec 3): the great roster, minor factions, stances and members.

A faction is an entity; membership is the `member_of` relation (person -> faction,
value = rank, data = {role, merit, hall, sponsor, secret, joined_at, status, ...}).
"""

from systems.techniques import FORMS
from world.gen.materialize import ensure_town
from world.gen.names import person_name
from world.gen.region import region_spec
from world.seed import rng_for

LADDERS = {
    "orthodox_sect": ("outer disciple", "inner disciple", "core disciple", "elder", "sect leader"),
    "school": ("outer disciple", "inner disciple", "core disciple", "elder", "sect leader"),
    "demonic_cult": ("blood servant", "cult follower", "blood envoy", "cult elder", "cult master"),
    "unorthodox_clan": ("apprentice", "poisoner", "master poisoner", "elder", "valley master"),
    "martial_clan": ("retainer", "sworn retainer", "household guard", "clan elder", "clan head"),
    "local_clan": ("retainer", "sworn retainer", "household guard", "clan elder", "clan head"),
    "beggars": ("one-pouch beggar", "three-pouch beggar", "five-pouch beggar", "seven-pouch elder", "nine-pouch chief"),
    "merchant_guild": ("associate", "factor", "senior factor", "master", "guild head"),
    "imperial": ("constable", "senior constable", "inspector", "commander", "bureau chief"),
    "alliance": ("envoy", "warden", "senior warden", "elder", "alliance master"),
    "bandit_fort": ("lackey", "bandit", "lieutenant", "second", "chief"),
}
PATHS = {"orthodox_sect": "righteous", "school": "righteous", "imperial": "righteous", "alliance": "righteous",
         "demonic_cult": "ruthless", "unorthodox_clan": "ruthless", "bandit_fort": "ruthless"}
MARTIAL = frozenset({"orthodox_sect", "school", "demonic_cult", "unorthodox_clan", "bandit_fort"})
STAFFED = frozenset({"orthodox_sect", "school", "demonic_cult", "unorthodox_clan", "martial_clan", "local_clan",
                     "bandit_fort"})
BRANCHING = frozenset({"orthodox_sect", "demonic_cult", "unorthodox_clan", "martial_clan"})
NATURAL = {"constable": "imperial", "beggar": "beggars", "merchant": "merchant_guild"}
FAVOURED = {
    "orthodox_sect": ("sword", "palm", "fist"), "school": ("fist", "sword"), "demonic_cult": ("palm", "saber"),
    "unorthodox_clan": ("palm", "finger"), "martial_clan": ("saber", "spear"), "local_clan": ("saber", "staff"),
    "beggars": ("staff", "palm"), "merchant_guild": ("saber",), "imperial": ("saber", "spear"),
    "alliance": ("sword",), "bandit_fort": ("saber",),
}
BASE_REALM = {"orthodox_sect": 1, "demonic_cult": 1, "unorthodox_clan": 1, "imperial": 1}
ROSTER = (("orthodox_sect", 3), ("demonic_cult", 1), ("unorthodox_clan", 1), ("martial_clan", 1),
          ("beggars", 1), ("merchant_guild", 1), ("imperial", 1), ("alliance", 1))
CAPITAL_TYPES = frozenset({"beggars", "merchant_guild", "imperial", "alliance"})
HOME_RADIUS, FIRST_SECT_RADIUS, CAPITAL_RADIUS = 6, 2, 3
HOSTILE = -0.5
DARK = frozenset({"demonic_cult", "unorthodox_clan"})

SECT_A = ("Azure", "Pure", "Iron", "Jade", "White", "Green", "Golden", "Heavenly")
SECT_B = ("Cloud", "Summit", "Sword", "Pine", "Lotus", "Crane", "Peak", "Spring")
CULT_A = ("Blood", "Night", "Heaven-Devouring", "Black", "Crimson", "Shadow")
CULT_B = ("Lotus", "Moon", "Demon", "Serpent", "Flame")
POISON_A = ("Ten Thousand", "Five", "Black", "Hundred")
POISON_B = ("Valley", "Clan", "Hall")
GUILD_A = ("Golden River", "Jade Road", "Silk Road", "Grand Canal", "Salt Harbour")
SCHOOL_B = ("Fist", "Blade", "Staff", "Willow", "Stone")
FORT_A = ("Black Wind", "Red Cliff", "Tiger Head", "Wolf Fang")
FORT_B = ("Fort", "Stronghold", "Camp")
NAMERS = {
    "orthodox_sect": lambda rng: f"{rng.choice(SECT_A)} {rng.choice(SECT_B)} Sect",
    "demonic_cult": lambda rng: f"{rng.choice(CULT_A)} {rng.choice(CULT_B)} Cult",
    "unorthodox_clan": lambda rng: f"{rng.choice(POISON_A)} Poison {rng.choice(POISON_B)}",
    "martial_clan": lambda rng: f"{person_name(rng)[0]} Clan",
    "local_clan": lambda rng: f"{person_name(rng)[0]} Clan",
    "beggars": lambda rng: "Beggars' Sect",
    "merchant_guild": lambda rng: f"{rng.choice(GUILD_A)} Merchant Guild",
    "imperial": lambda rng: "Imperial Martial Bureau",
    "alliance": lambda rng: "Orthodox Martial Alliance",
    "school": lambda rng: f"{rng.choice(SECT_A)} {rng.choice(SCHOOL_B)} School",
    "bandit_fort": lambda rng: f"{rng.choice(FORT_A)} {rng.choice(FORT_B)}",
}


def gap(a, b) -> int:
    """Regions between two (x, y) homes (Chebyshev)."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def base_stance(a: str, b: str) -> float:
    pair = {a, b}
    if a == b == "orthodox_sect":
        return 0.6
    if pair == {"orthodox_sect", "alliance"}:
        return 0.8
    if pair & {"orthodox_sect", "alliance"} and pair & DARK and len(pair) == 2:
        return -0.8
    if pair == {"imperial", "demonic_cult"}:
        return -0.6
    if pair == {"imperial", "orthodox_sect"}:
        return 0.2
    if pair == {"demonic_cult", "unorthodox_clan"}:
        return 0.2
    if "bandit_fort" in pair and pair & {"orthodox_sect", "school", "imperial"}:
        return -0.5
    return 0.0


def _name(rng, kind: str, used: set) -> str:
    for _ in range(30):
        name = NAMERS[kind](rng)
        if name not in used:
            used.add(name)
            return name
    name = f"{NAMERS[kind](rng)} of the {len(used)}th Gate"
    used.add(name)
    return name


def _make(world, rng, kind: str, tier: str, home, path: str, used: set) -> int:
    wealth = rng.randint(30, 90)
    data = {"type": kind, "tier": tier, "home": list(home), "seat": None, "path": PATHS.get(kind, "neutral"),
            "ranks": list(LADDERS[kind]), "power": rng.randint(40, 90), "wealth": wealth, "treasury": wealth * 10,
            "forms": [f for f in FAVOURED[kind] if f in FORMS] or list(FORMS[:1]), "arts": [], "branches": []}
    return world.add_entity("faction", _name(rng, kind, used), data, path)


def _capital(world) -> tuple[int, int]:
    """The most populous region near the start: where the empire and the great guilds sit."""
    options = [(x, y) for x in range(-CAPITAL_RADIUS, CAPITAL_RADIUS + 1) for y in range(-CAPITAL_RADIUS, CAPITAL_RADIUS + 1)]
    return min(options, key=lambda c: (-region_spec(world.world_seed, *c).town_count, abs(c[0]) + abs(c[1]), c))


def _set_stances(world, ids: list[int], others: list[int]) -> None:
    for a in ids:
        for b in others:
            if a == b:
                continue
            value = base_stance(world.entity(a).data["type"], world.entity(b).data["type"])
            if value:
                world.relate(a, b, "stance", value)
                world.relate(b, a, "stance", value)


def ensure_roster(world) -> list[int]:
    """The world's ten great factions, created once from the world seed."""
    found = world.get_meta("roster")
    if found:
        return list(found)
    rng = rng_for(world.world_seed, "world/factions")
    capital = _capital(world)
    used: set = set()
    ids: list[int] = []
    first_sect = True
    with world.transaction():
        for kind, count in ROSTER:
            for _ in range(count):
                if kind in CAPITAL_TYPES:
                    home = capital
                elif kind == "orthodox_sect" and first_sect:
                    home, first_sect = (rng.randint(-FIRST_SECT_RADIUS, FIRST_SECT_RADIUS),
                                        rng.randint(-FIRST_SECT_RADIUS, FIRST_SECT_RADIUS)), False
                else:
                    home = (rng.randint(-HOME_RADIUS, HOME_RADIUS), rng.randint(-HOME_RADIUS, HOME_RADIUS))
                ids.append(_make(world, rng, kind, "great", home, f"world/faction:{len(ids)}", used))
        _set_stances(world, ids, ids)
        world.set_meta("roster", ids)
    return ids


def minor_factions(world, region) -> list[int]:
    """0-2 small local factions of a region, seeded and created the first time it is settled."""
    if region.data.get("minors_ready"):
        return list(region.data.get("minors", []))
    roster = ensure_roster(world)
    rng = rng_for(world.world_seed, f"{region.seed_path}/minor")
    x, y = region.data["x"], region.data["y"]
    ids: list[int] = []
    with world.transaction():
        for i in range(rng.choice((0, 1, 1, 2))):
            kind = rng.choice(("school", "bandit_fort", "local_clan"))
            seat = ensure_town(world, x, y, rng.randrange(region.data["town_count"]))
            fid = _make(world, rng, kind, "minor", (x, y), f"{region.seed_path}/minor:{i}", set())
            world.update_data(fid, seat=seat)
            ids.append(fid)
        _set_stances(world, ids, roster + ids)
        world.update_data(region.id, minors_ready=True, minors=ids)
    return ids


def stance(world, a: int, b: int) -> float:
    if a == b:
        return 1.0
    for other, value, _ in world.relations_from(a, "stance"):
        if other == b:
            return value
    return 0.0


def memberships(world, person_id) -> list[tuple[int, int, dict]]:
    if not isinstance(person_id, int):
        return []
    return [(fid, int(rank), data) for fid, rank, data in world.relations_from(person_id, "member_of")]


def membership(world, person_id, faction_id) -> tuple[int, dict] | None:
    return next(((rank, data) for fid, rank, data in memberships(world, person_id) if fid == faction_id), None)


def members_of(world, faction_id: int) -> list[int]:
    """Living members in good standing."""
    out = []
    for person in world.sources(faction_id, "member_of"):
        entity = world.entity(person)
        found = membership(world, person, faction_id)
        if entity is not None and not entity.data.get("dead") and found and found[1].get("status", "member") == "member":
            out.append(person)
    return out


def is_martial(world, faction_id: int) -> bool:
    return world.entity(faction_id).data["type"] in MARTIAL


def title(world, faction_id: int, rank: int) -> str:
    ranks = world.entity(faction_id).data["ranks"]
    return ranks[max(0, min(rank, len(ranks) - 1))]
```

- [ ] **Step 4: Edit the existing files** — `.patches/3b_task1.py`
```python
"""Task 1 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


GAME = "engine/game.py"
edit(GAME, "from systems.bodies import load_body\n", "from systems.bodies import load_body\nfrom systems.factions import ensure_roster\n")
edit(GAME, '''        populate(world, town)
        game = cls(world, narrator)''', '''        populate(world, town)
        ensure_roster(world)
        game = cls(world, narrator)''')
edit(GAME, '''        game = cls(world, narrator)
        if "body" not in player.data:''', '''        game = cls(world, narrator)
        ensure_roster(world)  # a save from before factions (phase 3b)
        if "body" not in player.data:''')
edit("narrate/road_text.py", '''            "fled": f"Fled from {other}.", "fight": f"Fought {other} on the road."}[entry.data["how"]]''',
     '''            "fled": f"Fled from {other}.", "fight": f"Fought {other} on the road.",
            "backed_off": f"{cap(other)} backed off from you on the road."}.get(entry.data["how"], f"Met {other} on the road.")''')
print("task 1 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task1.py && .venv/Scripts/python.exe -m pytest tests/test_factions.py -q -p no:cacheprovider`
Expected: `task 1 edits applied`, then `6 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: ten great factions, minor factions and their stances"`

---

### Task 2: Seats, halls, staff and natural members in towns

**Files:**
- Create: `systems/halls.py`, `engine/factions.py`, `assets/art/gate.art`, `assets/art/hall.art`
- Modify (via `.patches/3b_task2.py`):
  - `engine/hooks.py`, `engine/game.py` (settle on new, travel and load; presence tags and hall lines; scene hall art; mixin order)
  - `render/art.py` (hall overlay)
  - `tests/test_game.py` (busy-town count ruling)
- Test: `tests/test_halls.py`

**Interfaces:**
- Consumes: Task 1 (`ensure_roster`, `minor_factions`, `memberships`, `membership`, `gap`, tables).
- Produces:
  - `systems.halls`:
    - `settle_town(world, town_id)` (idempotent through `town.data["factions_ready"]`; it also calls `populate`).
    - `seat_of(world, faction) -> int`, which creates and settles the seat when needed.
    - `staff_at(world, faction, town, roles=None) -> list[int]`, `keeper_at(world, faction, town) -> int | None`, `elders(world, faction) -> dict[int, int]` (hall to elder).
    - `recruits_for(world, npc) -> list[int]` (the factions this NPC can speak for), `halls_here(world, town) -> list[int]`, `faction_tag(world, person, town) -> str | None`.
  - Staff `member_of` data is `{role in leader|elder|keeper|disciple|member, hall: 0|1|None, merit: 0, status: "member", secret: False}`.
  - Town data gains `halls` (faction ids with a hall there, seats included), `seats` and `factions_ready`. Faction data `seat` and `branches` fill in as towns settle.
  - `engine.hooks.GameHooks`: `_faction_options(npc) -> list[Choice]`, `_presence_tag(person) -> str`, `_presence_extras() -> list[Line]`, `_scene_extras() -> dict`.
  - `engine.factions.FactionsMixin`: the verb `faction_menu`, the submenu `"faction"` (from `_faction_options`), presence tags and hall lines, the scene `hall` overlay, and `_restore` settling the town.
  - `render.art.compose_scene(..., hall=None)`.

- [ ] **Step 1: Write the failing test** — `tests/test_halls.py`
```python
import sqlite3

import pytest

from engine.actions import Action
from engine.game import Game
from render.art import compose_scene, load_art
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.gen.materialize import ensure_town, people_at


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def first_sect(world):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")


def move_to(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def test_a_seat_has_a_leader_two_elders_a_keeper_and_disciples(game):
    sect = first_sect(game.world)
    seat = halls.seat_of(game.world, sect)
    assert game.world.entity(sect).data["seat"] == seat
    roles = sorted(F.membership(game.world, p, sect)[1]["role"] for p in halls.staff_at(game.world, sect, seat))
    assert roles == ["disciple"] * 4 + ["elder", "elder", "keeper", "leader"]
    assert sorted(halls.elders(game.world, sect)) == [0, 1]
    assert sect in halls.halls_here(game.world, seat)
    leader = halls.staff_at(game.world, sect, seat, roles=("leader",))[0]
    assert F.membership(game.world, leader, sect)[0] == 4
    halls.settle_town(game.world, seat)
    assert len(halls.staff_at(game.world, sect, seat)) == 8


def test_constables_beggars_and_merchants_join_their_factions_naturally(game):
    for x in range(-2, 3):
        town = ensure_town(game.world, x, 1, 0)
        halls.settle_town(game.world, town)
        for person in people_at(game.world, town):
            kind = F.NATURAL.get(person.data.get("occupation"))
            if kind:
                assert any(game.world.entity(fid).data["type"] == kind for fid, _, _ in F.memberships(game.world, person.id))


def test_the_start_town_is_settled_from_the_first_turn(game):
    assert game.world.entity(game.place.id).data["factions_ready"]


def test_a_seat_town_says_so_tags_its_people_and_shows_its_gate(game):
    sect = first_sect(game.world)
    seat = halls.seat_of(game.world, sect)
    move_to(game, seat)
    turn = game.perform(Action("look"))
    name = game.world.entity(sect).name
    text = [t for t, _ in turn.lines]
    assert f"The {name} keeps its seat here." in text
    assert any(f"({name})" in t for t in text if t.startswith("Here:"))
    assert turn.art["hall"] == "gate"


def test_the_faction_menu_needs_someone_to_talk_to(game):
    sect = first_sect(game.world)
    seat = halls.seat_of(game.world, sect)
    move_to(game, seat)
    keeper = halls.keeper_at(game.world, sect, seat)
    assert sect in halls.recruits_for(game.world, keeper)
    turn = game.perform(Action("faction_menu"))  # not talking to anyone
    assert turn.lines[-1] == ("There is no one to discuss that with.", "system")


def test_the_conversation_menu_stays_within_nine(game):
    sect = first_sect(game.world)
    move_to(game, halls.seat_of(game.world, sect))
    for npc in people_at(game.world, game.place.id, exclude=game.player.id):
        turn = game.perform(Action("talk", npc.id))
        assert len(turn.choices) <= 9 and turn.choices[-1].action == Action("farewell")
        game.perform(Action("farewell"))


def test_the_hall_art_exists_and_fits():
    for name in ("gate", "hall"):
        art = load_art(name)
        assert art and max(len(r) for r in art) <= 20 and len(art) <= 8
    assert compose_scene("mountains", "town", 1, 40, 18, hall="gate")


def test_an_old_save_gets_factions_on_load(tmp_path):
    path = tmp_path / "old.world"
    g = Game.new(path, "Old", world_seed=5)
    g.close()
    conn = sqlite3.connect(path)
    conn.execute("delete from meta where key = 'roster'")
    conn.execute("delete from relations where kind in ('stance', 'member_of')")
    conn.execute("delete from entities where kind = 'faction'")
    conn.execute("update entities set data = json_remove(data, '$.factions_ready', '$.halls', '$.seats') where kind = 'town'")
    conn.execute("update entities set data = json_remove(data, '$.minors_ready', '$.minors') where kind = 'region'")
    conn.commit()
    conn.close()
    g = Game.load(path)
    g.start()
    assert len(g.world.get_meta("roster")) == 10
    assert g.world.entity(g.place.id).data["factions_ready"]
    g.close()
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_halls.py -q -p no:cacheprovider`
Expected: the collection error `ImportError: cannot import name 'halls' from 'systems'`.

- [ ] **Step 3: Write halls** — `systems/halls.py`
```python
"""Where factions live in a town (phase 3b spec 3.1, 3.3): seats, branch halls, staff, natural members."""

from systems import factions as F
from systems.realms import REALMS
from world.gen.materialize import ensure_town, people_at, populate, region_of
from world.gen.names import person_name
from world.gen.npc import PORTRAIT_PARTS, TRAITS
from world.seed import rng_for

SEAT_STAFF = (("leader", 4, None), ("elder", 3, 0), ("elder", 3, 1), ("keeper", 2, None),
              ("disciple", 0, 0), ("disciple", 0, 1), ("disciple", 1, 0), ("disciple", 1, 1))
CAPITAL_STAFF = (("leader", 4, None), ("keeper", 2, None))
BRANCH_STAFF = (("keeper", 2, None), ("disciple", 0, 0), ("disciple", 1, 1))
REALM_BONUS = {"leader": 2, "elder": 1, "keeper": 0, "disciple": 0}
DARK_TRAITS = ("cunning", "hot-tempered", "proud")
BRANCH_RADIUS, BRANCH_CHANCE = 2, 0.35
NATURAL_OCCUPATION = {kind: job for job, kind in F.NATURAL.items()}
RECRUITERS = frozenset({"leader", "elder", "keeper"})


def _hire(world, faction, town_id: int, staff) -> None:
    kind = faction.data["type"]
    for i, (role, rank, hall) in enumerate(staff):
        path = f"{faction.seed_path}/member:{town_id}:{i}"
        if world.entity_by_seed(path) is not None:
            continue
        rng = rng_for(world.world_seed, path)
        surname, given = person_name(rng)
        realm = REALMS[min(len(REALMS) - 1, F.BASE_REALM.get(kind, 0) + REALM_BONUS[role])].label
        first = rng.choice(DARK_TRAITS) if faction.data["path"] == "ruthless" else rng.choice(TRAITS)
        traits = list(dict.fromkeys([first, rng.choice(TRAITS)]))
        occupation = "hall keeper" if role == "keeper" else F.title(world, faction.id, rank)
        data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": rng.randint(18, 70),
                "occupation": occupation, "traits": traits, "realm": realm,
                "portrait": {part: rng.randrange(count) for part, count in PORTRAIT_PARTS.items()}}
        person = world.add_entity("person", f"{surname} {given}", data, path)
        world.relate(person, town_id, "located_in")
        world.relate(person, faction.id, "member_of", rank,
                     {"role": role, "hall": hall, "merit": 0, "status": "member", "secret": False})


def _natural_present(world, town_id: int, kind: str) -> bool:
    job = NATURAL_OCCUPATION.get(kind)
    return job is not None and any(p.data.get("occupation") == job for p in people_at(world, town_id))


def _has_branch(world, faction, town) -> bool:
    kind = faction.data["type"]
    if kind in F.BRANCHING:
        near = F.gap(faction.data["home"], (town.data["x"], town.data["y"])) <= BRANCH_RADIUS
        return near and rng_for(world.world_seed, f"branch:{faction.id}:{town.id}").random() < BRANCH_CHANCE
    return kind in NATURAL_OCCUPATION and _natural_present(world, town.id, kind)


def _enrol_natural(world, town_id: int, roster: list[int]) -> None:
    by_type = {world.entity(fid).data["type"]: fid for fid in roster}
    for person in people_at(world, town_id):
        kind = F.NATURAL.get(person.data.get("occupation"))
        if kind in by_type and F.membership(world, person.id, by_type[kind]) is None \
                and not person.data.get("is_player"):
            world.relate(person.id, by_type[kind], "member_of", 0,
                         {"role": "member", "hall": None, "merit": 0, "status": "member", "secret": False})


def settle_town(world, town_id: int) -> None:
    """Put every faction that lives here into the town: seat, branch hall, staff, natural members. Once."""
    town = world.entity(town_id)
    if town is None or town.kind != "town" or town.data.get("factions_ready"):
        return
    populate(world, town_id)
    roster = F.ensure_roster(world)
    minors = F.minor_factions(world, region_of(world, town_id))
    here, seats = [], []
    with world.transaction():
        for fid in roster + minors:
            faction = world.entity(fid)
            kind = faction.data["type"]
            if faction.data["tier"] == "minor":
                is_seat = faction.data["seat"] == town_id
            else:
                is_seat = tuple(faction.data["home"]) == (town.data["x"], town.data["y"]) and town.data["index"] == 0
            if is_seat:
                here.append(fid)
                seats.append(fid)
                world.update_data(fid, seat=town_id)
                staff = SEAT_STAFF if kind in F.STAFFED else () if kind == "alliance" else CAPITAL_STAFF
                _hire(world, world.entity(fid), town_id, staff)
            elif _has_branch(world, faction, town):
                here.append(fid)
                world.update_data(fid, branches=[*faction.data["branches"], town_id])
                if kind in F.STAFFED:
                    _hire(world, world.entity(fid), town_id, BRANCH_STAFF)
        _enrol_natural(world, town_id, roster)
        world.update_data(town_id, factions_ready=True, halls=here, seats=seats)


def seat_of(world, faction_id: int) -> int:
    """The faction's seat town, created and settled if nobody has been there yet."""
    faction = world.entity(faction_id)
    seat = faction.data.get("seat")
    if seat is None:
        x, y = faction.data["home"]
        seat = ensure_town(world, x, y, 0)
    settle_town(world, seat)
    return world.entity(faction_id).data["seat"] or seat


def halls_here(world, town_id: int) -> list[int]:
    town = world.entity(town_id)
    return list(town.data.get("halls", [])) if town is not None else []


def staff_at(world, faction_id: int, town_id: int, roles=None) -> list[int]:
    out = []
    for person in people_at(world, town_id):
        found = F.membership(world, person.id, faction_id)
        if found and found[1].get("status", "member") == "member" and found[1].get("role") != "member" \
                and (roles is None or found[1].get("role") in roles):
            out.append(person.id)
    return out


def keeper_at(world, faction_id: int, town_id: int) -> int | None:
    """Who keeps this faction's hall here: its hall keeper, else a natural member standing in."""
    keepers = staff_at(world, faction_id, town_id, roles=("keeper",))
    if keepers:
        return keepers[0]
    if faction_id not in halls_here(world, town_id):
        return None
    natural = [p.id for p in people_at(world, town_id)
               if (F.membership(world, p.id, faction_id) or (0, {}))[1].get("role") == "member"
               and not p.data.get("is_player")]
    return natural[0] if natural else None


def elders(world, faction_id: int) -> dict[int, int]:
    seat = seat_of(world, faction_id)
    out = {}
    for person in staff_at(world, faction_id, seat, roles=("elder",)):
        out[F.membership(world, person, faction_id)[1]["hall"]] = person
    return out


def recruits_for(world, npc_id: int) -> list[int]:
    """Factions this person can speak for here: staff above disciple, or the keeper of a natural hall."""
    town = next(iter(world.targets(npc_id, "located_in")), None)
    out = []
    for fid, _, data in F.memberships(world, npc_id):
        if data.get("status", "member") != "member":
            continue
        if data.get("role") in RECRUITERS or (town is not None and keeper_at(world, fid, town) == npc_id):
            out.append(fid)
    return out


def faction_tag(world, person_id: int, town_id: int) -> str | None:
    """The faction someone visibly belongs to here (staff and hall members wear its insignia)."""
    for fid in halls_here(world, town_id):
        found = F.membership(world, person_id, fid)
        if found and found[1].get("status", "member") == "member":
            return world.entity(fid).name
    return None
```

- [ ] **Step 4: Write the factions mixin** — `engine/factions.py`
```python
"""Factions in the engine (phase 3b spec 9): halls in towns, and the Faction matters... submenu."""

from engine.actions import Action, Choice
from systems import halls


class FactionsMixin:
    def _restore(self) -> None:
        super()._restore()
        halls.settle_town(self.world, self.place.id)

    def _presence_tag(self, person) -> str:
        tag = halls.faction_tag(self.world, person.id, self.place.id)
        return f" ({tag})" if tag else super()._presence_tag(person)

    def _presence_extras(self) -> list:
        lines = super()._presence_extras()
        town = self.world.entity(self.place.id)
        for fid in halls.halls_here(self.world, self.place.id):
            name = self.world.entity(fid).name
            where = "its seat" if fid in town.data.get("seats", []) else "a hall"
            lines.append((f"The {name} keeps {where} here.", "dim"))
        return lines

    def _scene_extras(self) -> dict:
        extras = super()._scene_extras()
        town = self.world.entity(self.place.id)
        if town.data.get("seats"):
            extras["hall"] = "gate"
        elif town.data.get("halls"):
            extras["hall"] = "hall"
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if self._faction_options(npc):
            extras.insert(0, Choice("Faction matters...", Action("faction_menu")))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None and self.submenu == "faction":
            options["faction"] = (self._faction_options(self.world.entity(self.focus)), Action("talk_menu"))
        return options

    def _do_faction_menu(self, _target):
        if self.focus is None:
            return self._turn([("There is no one to discuss that with.", "system")])
        if not self._faction_options(self.world.entity(self.focus)):
            return self._turn([("They have no faction business with you.", "system")])
        self.submenu = "faction"
        return self._turn([("What is your business?", "system")])
```

- [ ] **Step 5: Draw the hall art** — `assets/art/gate.art`
```
{red}  ___________
 /___/_|_\___\
{brown}   |  | |  |
{brown}   |  | |  |
```

- [ ] **Step 6: Draw the branch hall art** — `assets/art/hall.art`
```
{red}  ______
 /______\
{brown}  | [] |
{brown}  |____|
```

- [ ] **Step 7: Edit the existing files** — `.patches/3b_task2.py`
```python
"""Task 2 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("engine/hooks.py", '''    def _status_suffix(self) -> str:
        return ""
''', '''    def _status_suffix(self) -> str:
        return ""

    def _faction_options(self, npc) -> list:
        """Choices for the Faction matters... submenu with this person (phase 3b)."""
        return []

    def _presence_tag(self, person) -> str:
        """A short note after someone's name in the Here: line."""
        return ""

    def _presence_extras(self) -> list:
        """Lines after the Here: line (faction halls in this town)."""
        return []

    def _scene_extras(self) -> dict:
        """Extra keys for the town scene art (a hall overlay)."""
        return {}
''')

GAME = "engine/game.py"
edit(GAME, "from systems.factions import ensure_roster\n", "from systems.factions import ensure_roster\nfrom systems.halls import settle_town\n")
edit(GAME, "from engine.gossip import GossipMixin\n", "from engine.factions import FactionsMixin\nfrom engine.gossip import GossipMixin\n")
edit(GAME, "class Game(GossipMixin, MasksMixin,", "class Game(FactionsMixin, GossipMixin, MasksMixin,")
edit(GAME, '''        populate(world, town)
        ensure_roster(world)
        game = cls(world, narrator)''', '''        populate(world, town)
        ensure_roster(world)
        settle_town(world, town)
        game = cls(world, narrator)''')
edit(GAME, '''        populate(self.world, self.place.id)
        self._last_look = (self.place.id, self.world.time)''', '''        populate(self.world, self.place.id)
        settle_town(self.world, self.place.id)
        self._last_look = (self.place.id, self.world.time)''')
edit(GAME, '''            described.append(f"{person.name} the {person.data.get('occupation', 'stranger')}{known}")
        return [("Here: " + ", ".join(described) + ".", "dim")]''', '''            tag = self._presence_tag(person)
            described.append(f"{person.name} the {person.data.get('occupation', 'stranger')}{tag}{known}")
        return [("Here: " + ", ".join(described) + ".", "dim")] + self._presence_extras()''')
edit(GAME, '''        return {"type": "scene", "terrain": place.data["terrain"], "settlement": place.data["kind"], "watch": self.world.time % 4}''',
     '''        return {"type": "scene", "terrain": place.data["terrain"], "settlement": place.data["kind"],
                "watch": self.world.time % 4, "hall": None, **self._scene_extras()}''')

ART = "render/art.py"
edit(ART, '''def compose_scene(terrain: str, settlement: str, watch: int, w: int, h: int) -> Art:
    canvas = blank(w, h)
    sky = load_art(f"sky_{watch}")
    stamp(canvas, sky, 0, (w - art_width(sky)) // 2)
    for layer in (load_art(f"terrain_{terrain}"), load_art(f"settlement_{settlement}")):
        stamp(canvas, layer, h - len(layer), (w - art_width(layer)) // 2)
    return canvas''', '''def compose_scene(terrain: str, settlement: str, watch: int, w: int, h: int, hall: str | None = None) -> Art:
    canvas = blank(w, h)
    sky = load_art(f"sky_{watch}")
    stamp(canvas, sky, 0, (w - art_width(sky)) // 2)
    for layer in (load_art(f"terrain_{terrain}"), load_art(f"settlement_{settlement}")):
        stamp(canvas, layer, h - len(layer), (w - art_width(layer)) // 2)
    if hall:
        overlay = load_art(hall)
        stamp(canvas, overlay, max(0, h - len(overlay) - 5), 1)
    return canvas''')
edit(ART, '''        return compose_scene(request["terrain"], request["settlement"], request["watch"], w, h)''',
     '''        return compose_scene(request["terrain"], request["settlement"], request["watch"], w, h, request.get("hall"))''')

# Ruling: faction staff now live in some towns, so the start town can hold more than its seeded residents.
edit("tests/test_game.py", '''    assert len(people) == g.world.entity(g.place.id).data["npc_count"]''',
     '''    from systems.halls import halls_here, staff_at
    staff = sum(len(staff_at(g.world, fid, g.place.id)) for fid in halls_here(g.world, g.place.id))
    assert len(people) == g.world.entity(g.place.id).data["npc_count"] + staff''')
edit("tests/test_game.py", '''        assert [c.action for c in sub.choices if c.action.verb == "talk"] == [c.action for c in people]''',
     '''        assert [c.action for c in sub.choices if c.action.verb == "talk"] == [c.action for c in people][:8]''')
print("task 2 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task2.py && .venv/Scripts/python.exe -m pytest tests/test_halls.py -q -p no:cacheprovider`
Expected: `task 2 edits applied`, then `8 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: faction seats, halls, staff and natural members in towns"`

---

### Task 3: How a faction sees you, and enemies by association

**Files:**
- Create: `systems/standing.py`
- Modify (via `.patches/3b_task3.py`): `systems/attitude.py` (association term), `narrate/gossip_text.py` (a phrase for `member_of`, and an `EXTRA_PHRASES` registry), `engine/factions.py` (the first faction-menu option: *Ask how the X regards you*)
- Test: `tests/test_standing.py`

**Interfaces:**
- Consumes: Task 1 (`stance`, `memberships`, `membership`, `is_martial`, `HOSTILE`), 3a `systems.beliefs.true_identity`, and `systems.reputation.path_value`.
- Produces:
  - `systems.standing`:
    - `Standing(score, word, reasons: tuple[str, ...])`.
    - `knowledge(world, faction) -> list[(Belief, Fact)]` (the surest version per fact, from seat and branch pools).
    - `seen_ids(world, faction, subject, know=None) -> set[int]`.
    - `believed_factions(world, faction, subject, know=None) -> set[int]`.
    - `standing(world, faction, subject) -> Standing`.
    - `word_for(score) -> str`, giving honoured, welcome, neutral, distrusted or enemy.
  - `systems.attitude`: a term for enemies by association.
  - `narrate.gossip_text.EXTRA_PHRASES: dict[predicate, template]`, with template keys `{actor}`, `{target}`, `{be}`. It handles `member_of`.

- [ ] **Step 1: Write the failing test** — `tests/test_standing.py`
```python
import pytest

from engine.game import Game
from narrate.gossip_text import rumour_text
from systems import factions as F
from systems import halls
from systems.attitude import attitude
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.standing import standing


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def person(game, name, town, occupation="innkeeper"):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {"occupation": occupation, "traits": ["curious", "lazy"],
                                                 "realm": "mortal", "surname": surname, "given": given})
    game.world.relate(pid, town, "located_in")
    return pid


def deed(game, actor, predicate, target, town, **story):
    return record_fact(game.world, actor, predicate, target, place=town,
                       variant=make_variant(predicate, actor, target, place=game.world.entity(town).name, **story))


def test_a_stranger_is_neutral(game):
    sect = of_type(game.world, "orthodox_sect")
    assert standing(game.world, sect, game.player.id).word == "neutral"


def test_righteous_sects_hate_cruelty_and_cults_admire_it(game):
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    for fid in (sect, cult):
        seat = halls.seat_of(game.world, fid)
        for name in ("Wang Li", "Hu Mei"):
            deed(game, game.player.id, "killed", person(game, name, seat), seat)
    assert standing(game.world, sect, game.player.id).word in ("distrusted", "enemy")
    assert standing(game.world, cult, game.player.id).score > 0


def test_harming_one_of_ours_is_remembered_with_a_reason(game):
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    disciple = halls.staff_at(game.world, sect, seat, roles=("disciple",))[0]
    deed(game, game.player.id, "crippled", disciple, seat)
    result = standing(game.world, sect, game.player.id)
    assert result.score < 0 and "you harmed one of ours" in result.reasons


def test_being_known_as_a_cultist_makes_the_orthodox_your_enemies(game):
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    seat = halls.seat_of(game.world, sect)
    deed(game, game.player.id, "member_of", cult, seat)
    result = standing(game.world, sect, game.player.id)
    assert result.score <= -2 and f"you are of the {game.world.entity(cult).name}" in result.reasons
    disciple = halls.staff_at(game.world, sect, seat, roles=("disciple",))[0]
    feeling = attitude(game.world, disciple, game.player.id)
    assert feeling.word in ("wary", "hostile") and feeling.reason == f"you are of the {game.world.entity(cult).name}"


def test_masked_deeds_stay_with_the_mask(game):
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    deed(game, persona, "killed", person(game, "Wang Li", seat), seat, masked=True)
    assert standing(game.world, sect, game.player.id).word == "neutral"
    assert standing(game.world, sect, persona).score < 0
    deed(game, persona, "is", game.player.id, seat)
    assert standing(game.world, sect, game.player.id).score < 0


def test_expelled_members_are_enemies(game):
    sect = of_type(game.world, "orthodox_sect")
    game.world.relate(game.player.id, sect, "member_of", 0, {"role": "member", "status": "expelled"})
    assert standing(game.world, sect, game.player.id).word == "enemy"


def test_a_recruiter_says_how_their_faction_regards_you(game):
    from engine.actions import Action
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, seat, "located_in")
    keeper = halls.keeper_at(game.world, sect, seat)
    game.perform(Action("talk", keeper))
    turn = game.perform(Action("faction_menu"))
    view = next(c for c in turn.choices if c.action == Action("faction_view", sect))
    name = game.world.entity(sect).name
    assert view.label == f"Ask how the {name} regards you"
    text = [t for t, _ in game.perform(view.action).lines]
    assert any(f"the {name} holds you neutral" in line for line in text)


def test_membership_reads_as_a_rumour(game):
    sect = of_type(game.world, "orthodox_sect")
    name = game.world.entity(sect).name
    assert rumour_text(game.world, make_variant("member_of", game.player.id, sect), game.player.id) == f"You are of the {name}."
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_standing.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.standing'`.

- [ ] **Step 3: Write standing** — `systems/standing.py`
```python
"""How a faction sees someone (phase 3b spec 3.4): from what its towns have heard, never from truth."""

from dataclasses import dataclass

from systems import factions as F
from systems.beliefs import true_identity
from systems.reputation import path_value

HARMFUL = frozenset({"killed", "crippled", "robbed", "left_for_dead", "defeated"})
GONE = frozenset({"expelled", "deserter", "spy"})


@dataclass(frozen=True)
class Standing:
    score: float
    word: str
    reasons: tuple[str, ...]


def word_for(score: float) -> str:
    if score >= 3:
        return "honoured"
    if score >= 1:
        return "welcome"
    if score > -1:
        return "neutral"
    if score > -3:
        return "distrusted"
    return "enemy"


def knowledge(world, faction_id: int) -> list:
    """What the faction's seat and branch towns believe: the surest version of each fact."""
    faction = world.entity(faction_id)
    towns = [t for t in [faction.data.get("seat"), *faction.data.get("branches", [])] if t]
    best: dict = {}
    for town in towns:
        for belief, fact in world.known_facts(town):
            if fact.id not in best or belief.confidence > best[fact.id][0].confidence:
                best[fact.id] = (belief, fact)
    return list(best.values())


def seen_ids(world, faction_id: int, subject: int, know=None) -> set[int]:
    """Who the faction takes `subject` to be: the player plus any persona it knows is them."""
    know = knowledge(world, faction_id) if know is None else know
    true_id = true_identity(world, subject)
    if subject != true_id:
        return {subject}
    return {true_id} | {f.subject for _, f in know if f.predicate == "is" and f.object == true_id}


def believed_factions(world, faction_id: int, subject: int, know=None) -> set[int]:
    know = knowledge(world, faction_id) if know is None else know
    seen = seen_ids(world, faction_id, subject, know)
    return {f.object for b, f in know if f.predicate == "member_of" and b.variant.get("actor") in seen}


def _factions_of(world, person) -> list[int]:
    return [fid for fid, _, data in F.memberships(world, person) if data.get("status", "member") == "member"]


def standing(world, faction_id: int, subject: int) -> Standing:
    faction = world.entity(faction_id)
    path = faction.data["path"]
    know = knowledge(world, faction_id)
    seen = seen_ids(world, faction_id, subject, know)
    terms: list[tuple[float, str]] = []
    for belief, fact in know:
        if belief.variant.get("actor") not in seen or fact.predicate in ("is", "member_of"):
            continue
        target = belief.variant.get("target")
        value, reason = 0.0, None
        if fact.predicate in HARMFUL and isinstance(target, int):
            theirs = _factions_of(world, target)
            if faction_id in theirs or any(F.stance(world, faction_id, g) >= 0.5 for g in theirs):
                value, reason = -1.0, "you harmed one of ours"
            elif any(F.stance(world, faction_id, g) <= F.HOSTILE for g in theirs):
                value, reason = 0.5, "you struck at our enemies"
        doctrine = path_value(world, fact.predicate, target)
        if path == "righteous" and doctrine:
            value += doctrine
            reason = reason or ("your righteous deeds" if doctrine > 0 else "your cruelty")
        elif path == "ruthless" and doctrine:
            value -= 0.5 * doctrine
            reason = reason or ("your ruthlessness" if doctrine < 0 else "your soft heart")
        value *= fact.weight * belief.confidence
        if value:
            terms.append((value, reason))
    for other in believed_factions(world, faction_id, subject, know):
        if other != faction_id and F.is_martial(world, other) and F.stance(world, faction_id, other) <= F.HOSTILE:
            terms.append((-2.0, f"you are of the {world.entity(other).name}"))
    true_id = true_identity(world, subject)
    mine = F.membership(world, true_id, faction_id) if subject == true_id else None
    if mine and mine[1].get("status", "member") == "member":
        terms.append((1.0, "you are one of us"))
    elif mine and mine[1].get("status") in GONE:
        terms.append((-3.0, "you betrayed them"))
    score = round(sum(v for v, _ in terms), 3)
    reasons = tuple(r for _, r in sorted(terms, key=lambda t: -abs(t[0]))[:2])
    return Standing(score, word_for(score), reasons)
```

- [ ] **Step 4: Edit attitude and rumour text** — `.patches/3b_task3.py`
```python
"""Task 3 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


ATT = "systems/attitude.py"
edit(ATT, '''from systems.beliefs import appears_as, identities, knowledge_of, true_identity
''', '''from systems.beliefs import appears_as, identities, knowledge_of, true_identity
from systems.factions import HOSTILE, memberships, stance
''')
edit(ATT, '''    best: dict[int, tuple[float, str | None]] = {}
    for belief, fact in knowledge_of(world, npc_id):
        if belief.variant.get("actor") not in seen or fact.object == npc_id:
            continue  # things done to them are already in their memories''', '''    best: dict[int, tuple[float, str | None]] = {}
    mine = [fid for fid, _, d in memberships(world, npc_id) if d.get("status", "member") == "member"]
    for belief, fact in knowledge_of(world, npc_id):
        if belief.variant.get("actor") not in seen or fact.object == npc_id:
            continue  # things done to them are already in their memories
        if fact.predicate == "member_of":  # enemies by association (phase 3b spec 3.4)
            worst = min((stance(world, f, fact.object) for f in mine), default=0.0)
            if worst <= HOSTILE and fact.id not in best:
                best[fact.id] = (-abs(worst) * belief.confidence, f"you are of the {world.entity(fact.object).name}")
            continue''')

GT = "narrate/gossip_text.py"
edit(GT, '''REALM_DEEDS = frozenset({"defeated", "killed", "crippled", "robbed", "spared", "left_for_dead"})
''', '''REALM_DEEDS = frozenset({"defeated", "killed", "crippled", "robbed", "spared", "left_for_dead"})
# Later systems add their own story shapes here: {actor}, {target} and {be} ("are" for you, else "is").
EXTRA_PHRASES = {"member_of": "{actor} {be} of the {target}."}
''')
edit(GT, '''    if predicate == "is":
        return cap(f"{actor} is really {target}.")''', '''    if predicate == "is":
        return cap(f"{actor} is really {target}.")
    if predicate in EXTRA_PHRASES:
        be = "are" if actor == "you" else "is"
        return cap(EXTRA_PHRASES[predicate].format(actor=actor, target=target or "someone", be=be))''')
FAC = "engine/factions.py"
edit(FAC, '''from engine.actions import Action, Choice
from systems import halls
''', '''from engine.actions import Action, Choice
from narrate.outcomes import cap
from systems import halls
from systems.beliefs import apparent_to
from systems.standing import standing
''')
edit(FAC, '''    def _do_faction_menu(self, _target):''', '''    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        for fid in halls.recruits_for(self.world, npc.id):
            name = self.world.entity(fid).name
            options.append(Choice(f"Ask how the {name} regards you", Action("faction_view", fid)))
        return options

    def _do_faction_view(self, faction_id):
        if self.focus is None or faction_id not in halls.recruits_for(self.world, self.focus):
            return self._turn([("They cannot speak for that faction.", "system")])
        view = standing(self.world, faction_id, apparent_to(self.world, self.focus, self.player.id))
        why = f" ({'; '.join(view.reasons)})" if view.reasons else ""
        speaker = cap(self.world.entity(self.focus).name)
        name = self.world.entity(faction_id).name
        return self._turn([(f"{speaker} tells you that the {name} holds you {view.word}{why}.", "dim")])

    def _do_faction_menu(self, _target):''')
print("task 3 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task3.py && .venv/Scripts/python.exe -m pytest tests/test_standing.py -q -p no:cacheprovider`
Expected: `task 3 edits applied`, then `8 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: faction standing from what its towns heard; enemies by association"`

---
### Task 4: Joining: eligibility, trials, secret joining, leaving the rolls

**Files:**
- Create: `systems/membership.py`, `engine/joining.py`, `narrate/faction_text.py`, `narrate/grammar/factions.toml`
- Modify (via `.patches/3b_task4.py`): `engine/game.py` (mixin order), `narrate/outcomes.py` (register narration)
- Test: `tests/test_joining.py`

**Interfaces:**
- Consumes: Tasks 1–3 (`F.*`, `halls.*`, `standing`, `believed_factions`), 3a `apparent_to`, `believe`, `record_fact`, `make_variant`, `apparent`, `place_name`, `reputation`, and `payment_events`.
- Produces:
  - `systems.membership`:
    - Constants: `TRIALS`, `FEE = 50`, `TRIBUTE = 30`, `EARS = 3`, `BLOOD_DAYS = 30`, `LEFT` (status → (event kind, fact weight)).
    - Checks: `open_martial(world, player) -> int | None`, `clean_record(world, town, player) -> bool`, `refusal(world, player, faction, town) -> str | None`, `secret_possible(world, player, faction, town) -> bool`, `trial_done(world, player) -> True | False | None`.
    - Events: `trial_events(world, player, recruiter, faction, place, secret=False)`, `joined_events(world, player, recruiter, faction, place, secret)`, `trial_failed_events(player, place, faction)`, `left_events(world, person, faction, place, status)`.
    - `set_membership(world, person, faction, rank=None, **changes)`.
    - Effects `trial_begun`, `joined`, `trial_failed`, `expelled`, `deserted`, `spy_exposed` and `released`, each with a fact listener.
  - Player data: `trial = {faction, kind, recruiter, secret, since, target, town, deadline}` or None.
  - The `joined` actors are `(player, recruiter[, sponsor])`. The `trial_begun` actors are `(player, recruiter[, target])`.
  - `engine.joining.JoiningMixin`: the verbs `join`, `join_secret` and `tribute`, plus `_trial_progress()` (runs after commit, look and arrival) and `_after_duel` handling of `purpose={"join": faction}`.

- [ ] **Step 1: Write the failing test** — `tests/test_joining.py`
```python
import pytest

import systems.duel as duel
import systems.telling as telling
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls, membership
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.purse import silver_of
from systems.standing import believed_factions
from world.events import commit
from world.gen.materialize import ensure_town
from world.gen.region import region_spec


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def move_to(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def town_with_hall(game, faction):
    for x in range(-3, 4):
        for y in range(-3, 4):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                town = ensure_town(game.world, x, y, i)
                halls.settle_town(game.world, town)
                if faction in halls.halls_here(game.world, town) and halls.keeper_at(game.world, faction, town):
                    return town
    raise AssertionError("no hall found")


def at_hall(game, kind, seat=True):
    faction = of_type(game.world, kind)
    town = halls.seat_of(game.world, faction) if seat else town_with_hall(game, faction)
    move_to(game, town)
    keeper = halls.keeper_at(game.world, faction, town)
    game.perform(Action("talk", keeper))
    return faction, town, keeper


def lines(turn):
    return [text for text, _ in turn.lines]


def test_the_alliance_takes_no_one_and_members_are_not_asked_twice(game):
    alliance = of_type(game.world, "alliance")
    assert membership.refusal(game.world, game.player.id, alliance, game.place.id).startswith("The Alliance")
    sect = of_type(game.world, "orthodox_sect")
    game.world.relate(game.player.id, sect, "member_of", 0, {"role": "member", "status": "member"})
    assert membership.refusal(game.world, game.player.id, sect, game.place.id) == "You are already one of them."


def test_a_sect_tests_you_with_a_spar_and_takes_you_in(game):
    sect, seat, keeper = at_hall(game, "orthodox_sect")
    turn = game.perform(Action("faction_menu"))
    assert Action("join", sect) in [c.action for c in turn.choices]
    game.perform(Action("join", sect))
    assert game.combat is not None and game.combat.mode == "test" and game.combat.purpose == {"join": sect}
    lines_ = game._finish_duel({"mode": "test", "result": "passed", "purpose": {"join": sect}})
    rank, data = F.membership(game.world, game.player.id, sect)
    assert rank == 0 and data["status"] == "member" and data["sponsor"] in halls.elders(game.world, sect).values()
    assert any("outer disciple" in text for text, _ in lines_)
    assert game.player.data.get("trial") is None
    assert sect in believed_factions(game.world, sect, game.player.id)


def test_failing_the_spar_ends_the_trial(game):
    sect, seat, keeper = at_hall(game, "orthodox_sect")
    game.perform(Action("join", sect))
    game._finish_duel({"mode": "test", "result": "failed", "purpose": {"join": sect}})
    assert F.membership(game.world, game.player.id, sect) is None and game.player.data.get("trial") is None


def test_a_dark_name_is_turned_away(game):
    sect, seat, keeper = at_hall(game, "orthodox_sect")
    victim = game.world.add_entity("person", "Hu Mei", {"realm": "mortal", "occupation": "innkeeper"})
    record_fact(game.world, game.player.id, "robbed", victim, place=seat,
                variant=make_variant("robbed", game.player.id, victim, place=game.world.entity(seat).name))
    assert "Your name is too dark for them." in lines(game.perform(Action("join", sect)))


def test_a_cult_demands_blood(game):
    cult, seat, keeper = at_hall(game, "demonic_cult")
    game.perform(Action("join", cult))
    trial = game.player.data["trial"]
    assert trial["kind"] == "blood" and trial["target"]
    target = trial["target"]
    move_to(game, game.world.targets(target, "located_in")[0])
    [sid] = commit(game.world, duel.start_events(game.world, game.player.id, target, game.place.id, "duel"))
    d = duel.Duel.from_event(sid, game.world.chronicle_entry(sid))
    d.stage, d.harm = "verdict", {"player": 0.0, "opponent": 90.0}
    game._commit(duel.verdict_events(game.world, d, "kill"))
    assert F.membership(game.world, game.player.id, cult)[1]["status"] == "member"


def test_the_beggars_want_three_rumours(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 1.0)
    beggars, town, keeper = at_hall(game, "beggars", seat=False)
    game.perform(Action("join", beggars))
    assert game.player.data["trial"]["kind"] == "ears"
    for n in range(3):
        a = game.world.add_entity("person", f"Zhou Ta{n}", {"realm": "mortal"})
        fid = record_fact(game.world, a, "robbed", game.player.id, place=None, variant=make_variant("robbed", a, game.player.id))
        game.world.upsert_belief(game.player.id, fid, make_variant("robbed", a, game.player.id), None, 1.0, 0, "witness")
        key = next(b.variant_key for b in game.world.beliefs(game.player.id) if b.fact_id == fid)
        game.perform(Action("tell", (fid, key)))
    assert F.membership(game.world, game.player.id, beggars)[1]["status"] == "member"


def test_a_clan_sends_you_on_an_errand(game):
    clan, seat, keeper = at_hall(game, "martial_clan")
    game.perform(Action("join", clan))
    trial = game.player.data["trial"]
    assert trial["kind"] == "service" and trial["town"] != seat
    move_to(game, trial["town"])
    game.perform(Action("look"))
    assert F.membership(game.world, game.player.id, clan)[1]["status"] == "member"


def test_the_guild_takes_a_fee(game):
    guild, town, keeper = at_hall(game, "merchant_guild", seat=False)
    game.world.update_data(game.player.id, silver=60)
    game.perform(Action("join", guild))
    assert silver_of(game.world, game.player.id) == 10 and game.player.data["trial"]["kind"] == "escort"


def test_the_bureau_takes_only_proven_fighters(game):
    bureau, town, keeper = at_hall(game, "imperial", seat=False)
    assert "proven fighters" in lines(game.perform(Action("join", bureau)))[-1]
    game.world.update_data(game.player.id, realm="third-rate")
    game.perform(Action("talk", keeper))
    game.perform(Action("join", bureau))
    assert F.membership(game.world, game.player.id, bureau)[0] == 0


def test_a_second_sect_only_in_secret(game):
    first = of_type(game.world, "demonic_cult")
    game.world.relate(game.player.id, first, "member_of", 0, {"role": "member", "status": "member", "secret": False})
    sect, seat, keeper = at_hall(game, "orthodox_sect")
    choices = [c.action for c in game.perform(Action("faction_menu")).choices]
    assert Action("join_secret", sect) in choices
    assert "You already belong" in lines(game.perform(Action("join", sect)))[-1]
    game.perform(Action("join_secret", sect))
    game._finish_duel({"mode": "test", "result": "passed", "purpose": {"join": sect}})
    assert F.membership(game.world, game.player.id, sect)[1]["secret"] is True
    assert sect in believed_factions(game.world, sect, game.player.id)
    assert sect not in believed_factions(game.world, first, game.player.id)


def test_an_overdue_trial_fails(game):
    cult, seat, keeper = at_hall(game, "demonic_cult")
    game.perform(Action("join", cult))
    game.world.set_time(game.player.data["trial"]["deadline"] + 1)
    turn = game.perform(Action("look"))
    assert game.player.data.get("trial") is None
    assert any("failed" in text for text in lines(turn))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_joining.py -q -p no:cacheprovider`
Expected: the collection error `ImportError: cannot import name 'membership' from 'systems'`.

- [ ] **Step 3: Write membership** — `systems/membership.py`
```python
"""Joining factions (phase 3b spec 4, 7): who may join, trials, joining, and leaving the rolls."""

from systems import factions as F
from systems import halls
from systems.beliefs import CONF_DECAY, apparent_to, believe
from systems.facts import apparent, make_variant, place_name, record_fact
from systems.purse import payment_events
from systems.realms import realm_index
from systems.reputation import reputation
from systems.standing import believed_factions, standing
from world.events import Event, effect, listen
from world.gen.materialize import ensure_town, people_at, region_of
from world.gen.region import region_spec
from world.seed import rng_for

TRIALS = {"orthodox_sect": "spar", "school": "spar", "demonic_cult": "blood", "unorthodox_clan": "blood",
          "martial_clan": "service", "local_clan": "service", "beggars": "ears", "merchant_guild": "escort",
          "imperial": None, "bandit_fort": "chief"}
FEE, TRIBUTE, EARS = 50, 30, 3
BLOOD_DAYS = 30
WATCHES_PER_DAY = 4
LEFT = {"expelled": ("expelled", 2.0), "deserter": ("deserted", 2.0), "spy": ("spy_exposed", 2.5),
        "released": ("released", 0.5)}


def set_membership(world, person: int, faction: int, rank: int | None = None, **changes) -> None:
    current_rank, data = F.membership(world, person, faction)
    world.relate(person, faction, "member_of", current_rank if rank is None else rank, {**data, **changes})


def open_martial(world, player: int) -> int | None:
    for fid, _, data in F.memberships(world, player):
        if data.get("status", "member") == "member" and not data.get("secret") and F.is_martial(world, fid):
            return fid
    return None


def clean_record(world, town_id: int, player: int) -> bool:
    """No dark name here (Task 9 replaces this with the town's bounty)."""
    return reputation(world, town_id, apparent_to(world, town_id, player)).path != "ruthless"


def refusal(world, player: int, faction: int, town: int) -> str | None:
    """Why this faction won't begin taking the player in now, or None."""
    data = world.entity(faction).data
    kind = data["type"]
    if kind == "alliance":
        return "The Alliance takes no members; it is a council of sects."
    found = F.membership(world, player, faction)
    if found and found[1].get("status", "member") == "member":
        return "You are already one of them."
    if found:
        return "They will not have you back."
    if world.entity(player).data.get("trial"):
        return "You are already undergoing a trial."
    known_as = apparent_to(world, town, player)
    if standing(world, faction, known_as).word in ("distrusted", "enemy"):
        return "They do not trust you."
    if data["path"] == "righteous" and reputation(world, town, known_as).path == "ruthless":
        return "Your name is too dark for them."
    first = open_martial(world, player)
    if kind in F.MARTIAL and first not in (None, faction):
        return f"You already belong to the {world.entity(first).name}."
    if kind == "imperial" and (realm_index(world.entity(player).data.get("realm", "mortal")) < 1
                               or not clean_record(world, town, player)):
        return "The Bureau takes only proven fighters with clean names."
    return None


def secret_possible(world, player: int, faction: int, town: int) -> bool:
    """A second martial faction, joined in secret, if it has not heard of the first."""
    first = open_martial(world, player)
    if not F.is_martial(world, faction) or first in (None, faction) or F.membership(world, player, faction):
        return False
    if world.entity(player).data.get("trial"):
        return False
    known_as = apparent_to(world, town, player)
    if standing(world, faction, known_as).word in ("distrusted", "enemy"):
        return False
    return first not in believed_factions(world, faction, known_as)


def _blood_target(world, player: int, faction: int) -> int:
    """Someone of the faction's home region the cult wants dead (seeded)."""
    region = region_of(world, halls.seat_of(world, faction))
    members = set(F.members_of(world, faction))
    candidates = []
    for i in range(region.data["town_count"]):
        town = ensure_town(world, region.data["x"], region.data["y"], i)
        halls.settle_town(world, town)
        candidates += [p.id for p in people_at(world, town, exclude=player)
                       if p.id not in members and not p.data.get("beast") and not p.data.get("dead")]
    return rng_for(world.world_seed, f"trial:{faction}:{player}").choice(sorted(candidates))


def _errand(world, player: int, faction: int, place: int) -> tuple[int, int]:
    """A town 1-2 regions away to be reached, and how many regions that is."""
    here = world.entity(place).data
    rng = rng_for(world.world_seed, f"trial-road:{faction}:{player}")
    dx, dy = rng.choice([(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3) if (dx, dy) != (0, 0)])
    x, y = here["x"] + dx, here["y"] + dy
    town = ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))
    return town, max(abs(dx), abs(dy))


def trial_events(world, player: int, recruiter: int, faction: int, place: int, secret: bool = False) -> list[Event]:
    kind = TRIALS[world.entity(faction).data["type"]]
    trial = {"faction": faction, "kind": kind, "recruiter": recruiter, "secret": secret,
             "since": world.last_rowid("chronicle"), "target": None, "town": None, "deadline": None}
    actors = (player, recruiter)
    events: list[Event] = []
    if kind == "blood":
        target = _blood_target(world, player, faction)
        trial.update(target=target, deadline=world.time + BLOOD_DAYS * WATCHES_PER_DAY)
        actors = (player, recruiter, target)
    elif kind in ("service", "escort"):
        town, regions = _errand(world, player, faction, place)
        trial.update(town=town, deadline=world.time + (3 * regions + 7) * WATCHES_PER_DAY)
        if kind == "escort":
            events += payment_events(player, recruiter, place, FEE, "guild fee")
    return events + [Event("trial_begun", actors, place, trial)]


@effect("trial_begun")
def _trial_begun(world, event) -> None:
    world.update_data(event.actors[0], trial=dict(event.data))


def trial_done(world, player: int):
    """True when the open trial is passed, False when it has failed, None while it goes on."""
    trial = world.entity(player).data.get("trial")
    if not trial:
        return None
    kind = trial["kind"]
    if kind == "blood":
        target = world.entity(trial["target"])
        if target is not None and target.data.get("dead"):
            by_me = any(e.kind == "died" and e.actors[0] == player for e in world.chronicle_about(target.id, limit=10))
            return by_me
    if trial.get("deadline") is not None and world.time > trial["deadline"]:
        return False
    if kind in ("service", "escort"):
        return True if trial["town"] in world.targets(player, "located_in") else None
    if kind == "ears":
        told = [e for e in world.chronicle_about(player, limit=300)
                if e.kind == "told" and e.id > trial["since"] and len(e.actors) > 1
                and e.actors[1] == trial["recruiter"] and e.data.get("accepted")]
        return True if len(told) >= EARS else None
    return None


def joined_events(world, player: int, recruiter: int, faction: int, place: int, secret: bool) -> list[Event]:
    found = F.membership(world, recruiter, faction)
    hall = found[1].get("hall") if found and found[1].get("hall") is not None \
        else rng_for(world.world_seed, f"hall:{faction}:{player}").randrange(2)
    sponsor = halls.elders(world, faction).get(hall) if world.entity(faction).data["type"] in F.STAFFED else None
    actors = (player, recruiter) + ((sponsor,) if sponsor not in (None, recruiter) else ())
    return [Event("joined", actors, place, {"faction": faction, "secret": secret, "hall": hall, "sponsor": sponsor})]


@effect("joined")
def _joined(world, event) -> None:
    d = event.data
    world.relate(event.actors[0], d["faction"], "member_of", 0, {
        "role": "member", "hall": d["hall"], "sponsor": d["sponsor"], "merit": 0, "secret": d["secret"],
        "joined_at": world.time, "status": "member", "judged": [], "stipend_at": world.time})
    world.update_data(event.actors[0], trial=None)


@listen("joined")
def _joined_fact(world, event, event_id: int) -> None:
    player, recruiter = event.actors[0], event.actors[1]
    d = event.data
    me = apparent(event, player)
    story = make_variant("member_of", me, d["faction"], place=place_name(world, event.place), masked=me != player)
    fact = record_fact(world, me, "member_of", d["faction"], place=event.place, variant=story,
                       source_event=event_id, weight=1.0, spread=not d["secret"])
    if d["secret"]:  # only the recruiter and the seat's own counsel know
        believe(world, recruiter, fact, story, player, 1.0, 0, "witness")
        seat = world.entity(d["faction"]).data.get("seat")
        if seat:
            believe(world, seat, fact, story, recruiter, CONF_DECAY, 1, "told")


def trial_failed_events(player: int, place: int, faction: int) -> list[Event]:
    return [Event("trial_failed", (player,), place, {"faction": faction})]


@effect("trial_failed")
def _trial_failed(world, event) -> None:
    world.update_data(event.actors[0], trial=None)


def left_events(world, person: int, faction: int, place: int, status: str) -> list[Event]:
    kind = LEFT[status][0]
    return [Event(kind, (person,), place, {"faction": faction, "status": status})]


def _left(world, event) -> None:
    set_membership(world, event.actors[0], event.data["faction"], status=event.data["status"])


def _left_fact(world, event, event_id: int) -> None:
    person = event.actors[0]
    me = apparent(event, person)
    kind, weight = LEFT[event.data["status"]]
    record_fact(world, me, kind, event.data["faction"], place=event.place, source_event=event_id, weight=weight,
                variant=make_variant(kind, me, event.data["faction"], place=place_name(world, event.place),
                                     masked=me != person))


for _kind, _ in LEFT.values():
    effect(_kind)(_left)
    listen(_kind)(_left_fact)
```

- [ ] **Step 4: Write the joining mixin** — `engine/joining.py`
```python
"""Joining factions in the engine (phase 3b spec 4)."""

from engine.actions import Action, Choice
from systems import halls, membership
from systems.purse import payment_events, silver_of


class JoiningMixin:
    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        me, town = self.player.id, self.place.id
        trial = self.player.data.get("trial")
        for fid in halls.recruits_for(self.world, npc.id):
            name = self.world.entity(fid).name
            if trial and trial["faction"] == fid:
                if trial["kind"] == "chief":
                    options.append(Choice(f"Pay tribute ({membership.TRIBUTE} silver)", Action("tribute", fid)))
                continue
            found = membership.F.membership(self.world, me, fid)
            if found or self.world.entity(fid).data["type"] == "alliance":
                continue
            options.append(Choice(f"Ask to join the {name}", Action("join", fid)))
            if membership.secret_possible(self.world, me, fid, town):
                options.append(Choice(f"Ask to join the {name} in secret", Action("join_secret", fid)))
        return options

    def _do_join(self, faction_id, secret: bool = False):
        npc = self.focus
        if npc is None or faction_id not in halls.recruits_for(self.world, npc):
            return self._turn([("They cannot take you in.", "system")])
        me, town = self.player.id, self.place.id
        if secret:
            if not membership.secret_possible(self.world, me, faction_id, town):
                return self._turn([("They would see through you.", "system")])
        elif (why := membership.refusal(self.world, me, faction_id, town)) is not None:
            return self._turn([(why, "system")])
        kind = membership.TRIALS[self.world.entity(faction_id).data["type"]]
        if kind == "escort" and silver_of(self.world, me) < membership.FEE:
            return self._turn([(f"The guild's fee is {membership.FEE} silver.", "system")])
        self.submenu = None
        if kind is None:
            return self._turn(self._commit(membership.joined_events(self.world, me, npc, faction_id, town, secret)))
        lines = self._commit(membership.trial_events(self.world, me, npc, faction_id, town, secret))
        if kind in ("spar", "chief"):
            roles = ("disciple",) if kind == "spar" else ("leader",)
            opponent = next(iter(halls.staff_at(self.world, faction_id, town, roles=roles)), npc)
            mode = "test" if kind == "spar" else "duel"
            return self._turn(lines + self._start_duel(opponent, mode, purpose={"join": faction_id}))
        return self._turn(lines)

    def _do_join_secret(self, faction_id):
        return self._do_join(faction_id, secret=True)

    def _do_tribute(self, faction_id):
        trial = self.player.data.get("trial")
        if self.focus is None or not trial or trial["faction"] != faction_id or trial["kind"] != "chief":
            return self._turn([("There is no tribute to pay.", "system")])
        if silver_of(self.world, self.player.id) < membership.TRIBUTE:
            return self._turn([(f"You don't have {membership.TRIBUTE} silver.", "system")])
        events = payment_events(self.player.id, self.focus, self.place.id, membership.TRIBUTE, "tribute")
        events += membership.joined_events(self.world, self.player.id, trial["recruiter"], faction_id, self.place.id,
                                           trial["secret"])
        self.submenu = None
        return self._turn(self._commit(events))

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        faction = (data.get("purpose") or {}).get("join")
        trial = self.player.data.get("trial")
        if faction and trial and trial["faction"] == faction:
            me, place = self.player.id, self.place.id
            if data["result"] in ("passed", "won"):
                events = membership.joined_events(self.world, me, trial["recruiter"], faction, place, trial["secret"])
            else:
                events = membership.trial_failed_events(me, place, faction)
            lines += self._commit(events)
        return lines

    def _trial_progress(self) -> list:
        state = membership.trial_done(self.world, self.player.id)
        if state is None:
            return []
        trial = self.player.data["trial"]
        me, place = self.player.id, self.place.id
        if state:
            return self._commit(membership.joined_events(self.world, me, trial["recruiter"], trial["faction"], place,
                                                         trial["secret"]))
        return self._commit(membership.trial_failed_events(me, place, trial["faction"]))

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        if any(e.kind in ("joined", "trial_failed", "trial_begun") for e in events):
            return lines
        return lines + self._trial_progress()

    def _after_look(self) -> list:
        return super()._after_look() + self._trial_progress()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._trial_progress()
```

- [ ] **Step 5: Write the faction narration** — `narrate/faction_text.py`
```python
"""What the player is told about joining and leaving factions."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import cap, outcome, summary
from systems import factions as F

EXTRA_PHRASES.update({
    "expelled": "{actor} {be} cast out of the {target}.",
    "deserted": "{actor} deserted the {target}.",
    "spy_exposed": "{actor} {be} unmasked as a spy in the {target}.",
    "released": "{actor} left the {target} with its blessing.",
})
LEFT_LINES = {"expelled": "You are cast out of the {name}.", "deserted": "You desert the {name}.",
              "spy_exposed": "You are exposed as a spy of the {name}!", "released": "The {name} releases you."}
LEFT_SUMMARY = {"expelled": "Cast out of the {name}.", "deserted": "Deserted the {name}.",
                "spy_exposed": "Exposed as a spy of the {name}.", "released": "Released by the {name}."}


def _faction(world, data) -> str:
    return world.entity(data["faction"]).name


def _days(world, deadline) -> int:
    return max(1, (deadline - world.time) // 4)


@outcome("trial_begun", body_facts=False)
def _trial(world, event):
    d, name = event.data, _faction(world, event.data)
    kind = d["kind"]
    if kind == "spar":
        line = "Very well. Show us what you can do against one of our disciples."
    elif kind == "blood":
        target = world.entity(d["target"])
        town = world.entity(world.targets(d["target"], "located_in")[0]).name
        line = f"Prove your resolve: {target.name} of {town} must die within {_days(world, d['deadline'])} days."
    elif kind in ("service", "escort"):
        what = "Carry our word" if kind == "service" else "See a caravan safely"
        line = f"{what} to {world.entity(d['town']).name} within {_days(world, d['deadline'])} days."
    elif kind == "ears":
        line = "Bring me three things I have not heard."
    else:
        line = "Beat our chief, or pay tribute."
    return [f"The {name} will test you. {line}"], {}


@outcome("joined", body_facts=False)
def _joined(world, event):
    d, name = event.data, _faction(world, event.data)
    out = [f"You are now {F.title(world, d['faction'], 0)} of the {name}."]
    if d["sponsor"]:
        out.append(f"You join {world.entity(d['sponsor']).name}'s hall.")
    if d["secret"]:
        out.append("Your joining is kept secret.")
    return out, {}


@outcome("trial_failed", body_facts=False)
def _failed(world, event):
    return [f"You have failed the trial of the {_faction(world, event.data)}."], {}


def _left_outcome(world, event):
    return [LEFT_LINES[event.kind].format(name=_faction(world, event.data))], {}


def _left_summary(world, entry, names, place, other):
    return LEFT_SUMMARY[entry.kind].format(name=_faction(world, entry.data))


for _kind in LEFT_LINES:
    outcome(_kind, body_facts=False)(_left_outcome)
    summary(_kind)(_left_summary)


@summary("trial_begun")
def _trial_line(world, entry, names, place, other):
    return f"Began the trial of the {_faction(world, entry.data)}."


@summary("joined")
def _joined_line(world, entry, names, place, other):
    return f"Joined the {_faction(world, entry.data)}."


@summary("trial_failed")
def _failed_line(world, entry, names, place, other):
    return f"Failed the trial of the {_faction(world, entry.data)}."
```

- [ ] **Step 6: Write the faction grammar** — `narrate/grammar/factions.toml`
```toml
[symbols]
faction_hall = ["Incense drifts through the hall.", "The banners stir above you.", "Disciples stop to watch.", "A bell sounds somewhere deeper in.", "The floorboards creak under old boots."]
faction_weigh = ["They look you over for a long moment.", "Their eyes measure you.", "A brush scratches in a ledger.", "Someone murmurs your name.", "They say nothing at first."]
faction_welcome = ["Hands clasp in the old salute.", "A robe is set in your arms.", "Your name goes into the book.", "Someone claps you on the shoulder.", "A cup is poured for you."]
faction_shame = ["Doors close behind you.", "Backs turn as you pass.", "Your name is struck from the book.", "No one meets your eye.", "The banners hang still."]

[trial_begun]
colour = "npc"
lines = ["#faction_hall# #faction_weigh#", "#faction_weigh# #faction_hall#"]

[joined]
colour = "gold"
lines = ["#faction_welcome# #faction_hall#", "#faction_hall# #faction_welcome#"]

[trial_failed]
colour = "default"
lines = ["#faction_shame# #faction_weigh#", "#faction_weigh# #faction_shame#"]

[expelled]
colour = "default"
lines = ["#faction_shame# #faction_hall#", "#faction_hall# #faction_shame#"]

[deserted]
colour = "default"
lines = ["#faction_shame# #faction_weigh#", "#faction_weigh# #faction_shame#"]

[spy_exposed]
colour = "default"
lines = ["#faction_shame# #faction_weigh#", "#faction_hall# #faction_shame#"]

[released]
colour = "default"
lines = ["#faction_hall# #faction_weigh#", "#faction_weigh# #faction_hall#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3b_task4.py`
```python
"""Task 4 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


GAME = "engine/game.py"
edit(GAME, "from engine.gossip import GossipMixin\n", "from engine.gossip import GossipMixin\nfrom engine.joining import JoiningMixin\n")
edit(GAME, "class Game(FactionsMixin, GossipMixin,", "class Game(FactionsMixin, JoiningMixin, GossipMixin,")
edit("narrate/outcomes.py", "import narrate.social_text  # noqa: E402,F401\n",
     "import narrate.social_text  # noqa: E402,F401\nimport narrate.faction_text  # noqa: E402,F401\n")
print("task 4 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task4.py && .venv/Scripts/python.exe -m pytest tests/test_joining.py -q -p no:cacheprovider`
Expected: `task 4 edits applied`, then `11 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass, including the fuzz tests, which can now wander into halls and trials.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: joining factions through their trials, open or in secret"`

---

### Task 5: Ranks, promotion, stipends, sect arts, the library, gifts

**Files:**
- Create: `systems/ranks.py`, `engine/ranks.py`, `narrate/ranks_text.py`, `narrate/grammar/ranks.toml`
- Modify (via `.patches/3b_task5.py`): `engine/game.py` (mixin order), `narrate/outcomes.py`
- Test: `tests/test_ranks.py`

**Interfaces:**
- Consumes: Task 4 (`set_membership`, `F.membership`), `halls.recruits_for`, `halls.keeper_at`, 3a `attitude` and `apparent_to`, and 2b `teach`, `create_technique`, `generate`, `create_manual` and `known_arts`.
- Produces:
  - `systems.ranks`:
    - Constants: `MERIT_NEEDED = (30, 90, 250)`, `REALM_NEEDED = (0, 1, 2)`, `TOP_RANK = 3`, `STIPEND_DAYS = 30`, `STIPEND_PER_RANK = 10`.
    - Rank and stipend: `promotion_block(world, player, faction) -> str | None`, `promoted_events(...)`, `stipend_due(world, player, faction) -> int`, `stipend_events(...)`.
    - Arts and library: `sect_arts(world, faction) -> list[int]`, `teachable(world, player, faction) -> list[int]`, `taught_events(...)`, `library_manual(world, player, faction) -> int | None`, `library_events(...)`.
    - Gifts: `gift_price(world, player, faction) -> int`, `gift_events(...)`.
  - Events: `promoted`, `stipend`, `sect_taught`, `library_lent`, `gift`.
  - `engine.ranks.RanksMixin`: the verbs `promote`, `stipend`, `learn_sect_art`, `library` and `gift`.

- [ ] **Step 1: Write the failing test** — `tests/test_ranks.py`
```python
import pytest

from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls, ranks
from systems.creation import CreationChoice
from systems.items import manuals_of
from systems.membership import set_membership
from systems.purse import silver_of
from systems.techniques import known_arts


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def member_at_seat(game, rank=0, merit=0):
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, seat, "located_in")
    sponsor = halls.elders(game.world, sect)[0]
    game.world.relate(game.player.id, sect, "member_of", rank, {
        "role": "member", "hall": 0, "sponsor": sponsor, "merit": merit, "secret": False, "joined_at": 0,
        "status": "member", "judged": [], "stipend_at": game.world.time})
    return sect, seat, sponsor


def texts(turn):
    return [t for t, _ in turn.lines]


def test_promotion_needs_merit(game):
    sect, seat, sponsor = member_at_seat(game)
    assert ranks.promotion_block(game.world, game.player.id, sect) == "You need 30 merit; you have 0."
    set_membership(game.world, game.player.id, sect, merit=30)
    game.perform(Action("talk", sponsor))
    turn = game.perform(Action("faction_menu"))
    assert Action("promote", sect) in [c.action for c in turn.choices]
    turn = game.perform(Action("promote", sect))
    assert F.membership(game.world, game.player.id, sect)[0] == 1
    assert any("inner disciple" in t for t in texts(turn))


def test_the_high_ranks_need_a_realm_and_a_friendly_sponsor(game):
    sect, seat, sponsor = member_at_seat(game, rank=1, merit=90)
    assert "Third-rate" in ranks.promotion_block(game.world, game.player.id, sect)
    game.world.update_data(game.player.id, realm="second-rate")
    set_membership(game.world, game.player.id, sect, rank=2, merit=250)
    assert ranks.promotion_block(game.world, game.player.id, sect) == "Your sponsor does not favour you enough."
    game.world.update_data(game.player.id, silver=500)
    game.perform(Action("talk", sponsor))
    for _ in range(3):
        game.perform(Action("gift", sect))
    assert ranks.promotion_block(game.world, game.player.id, sect) is None
    set_membership(game.world, game.player.id, sect, rank=3)
    assert "as far as anyone can" in ranks.promotion_block(game.world, game.player.id, sect)


def test_a_stipend_every_thirty_days(game):
    sect, seat, sponsor = member_at_seat(game, rank=2)
    assert ranks.stipend_due(game.world, game.player.id, sect) == 0
    game.world.set_time(game.world.time + ranks.STIPEND_DAYS * 4)
    assert ranks.stipend_due(game.world, game.player.id, sect) == 20
    before = silver_of(game.world, game.player.id)
    game.perform(Action("talk", halls.keeper_at(game.world, sect, seat)))
    game.perform(Action("stipend", sect))
    assert silver_of(game.world, game.player.id) == before + 20
    assert ranks.stipend_due(game.world, game.player.id, sect) == 0


def test_elders_teach_the_arts_your_rank_allows(game):
    sect, seat, sponsor = member_at_seat(game)
    arts = ranks.sect_arts(game.world, sect)
    assert len(arts) == 3 and ranks.sect_arts(game.world, sect) == arts
    assert ranks.teachable(game.world, game.player.id, sect) == arts[:1]
    game.perform(Action("talk", sponsor))
    game.perform(Action("learn_sect_art", sect))
    assert arts[0] in {a.technique.id for a in known_arts(game.world, game.player.id)}
    assert ranks.teachable(game.world, game.player.id, sect) == []


def test_the_library_lends_a_manual_to_inner_disciples(game):
    sect, seat, sponsor = member_at_seat(game, rank=1)
    game.perform(Action("talk", halls.keeper_at(game.world, sect, seat)))
    game.perform(Action("library", sect))
    assert any(m.technique.id in ranks.sect_arts(game.world, sect) for m in manuals_of(game.world, game.player.id))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ranks.py -q -p no:cacheprovider`
Expected: the collection error `ImportError: cannot import name 'ranks' from 'systems'`.

- [ ] **Step 3: Write ranks** — `systems/ranks.py`
```python
"""Rising in a faction (phase 3b spec 4, 5): promotion, stipends, sect arts, the library, gifts."""

from systems import factions as F
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import apparent, make_variant, place_name, record_fact
from systems.items import create_manual, manuals_of
from systems.membership import set_membership
from systems.purse import payment_events
from systems.realms import REALMS, realm_index
from systems.techniques import create_technique, generate, known_arts, teach
from world.events import Event, Witness, effect, listen
from world.seed import rng_for

MERIT_NEEDED = (30, 90, 250)
REALM_NEEDED = (0, 1, 2)
TOP_RANK = 3
STIPEND_DAYS, STIPEND_PER_RANK = 30, 10
WATCHES_PER_DAY = 4


def promotion_block(world, player: int, faction: int) -> str | None:
    """What stands between the player and the next rank, or None."""
    rank, data = F.membership(world, player, faction)
    if rank >= TOP_RANK:
        return "You have risen as far as anyone can without leading them."
    if data.get("merit", 0) < MERIT_NEEDED[rank]:
        return f"You need {MERIT_NEEDED[rank]} merit; you have {data.get('merit', 0)}."
    if realm_index(world.entity(player).data.get("realm", "mortal")) < REALM_NEEDED[rank]:
        return f"You must reach {REALMS[REALM_NEEDED[rank]].name} first."
    sponsor = data.get("sponsor")
    if rank == 2 and sponsor and attitude(world, sponsor, apparent_to(world, sponsor, player)).score < 0.3:
        return "Your sponsor does not favour you enough."
    return None


def promoted_events(world, player: int, faction: int, elder: int, place: int) -> list[Event]:
    rank = F.membership(world, player, faction)[0] + 1
    return [Event("promoted", (player, elder), place, {"faction": faction, "rank": rank})]


@effect("promoted")
def _promoted(world, event) -> None:
    set_membership(world, event.actors[0], event.data["faction"], rank=event.data["rank"], stipend_at=world.time)


@listen("promoted")
def _promoted_fact(world, event, event_id: int) -> None:
    me = apparent(event, event.actors[0])
    record_fact(world, me, "promoted", event.data["faction"], place=event.place, source_event=event_id, weight=0.5,
                variant=make_variant("promoted", me, event.data["faction"], place=place_name(world, event.place),
                                     masked=me != event.actors[0]))


def stipend_due(world, player: int, faction: int) -> int:
    rank, data = F.membership(world, player, faction)
    if rank < 1 or world.time - data.get("stipend_at", 0) < STIPEND_DAYS * WATCHES_PER_DAY:
        return 0
    return STIPEND_PER_RANK * rank


def stipend_events(world, player: int, faction: int, keeper: int, place: int) -> list[Event]:
    return [Event("stipend", (player, keeper), place, {"faction": faction, "amount": stipend_due(world, player, faction)})]


@effect("stipend")
def _stipend(world, event) -> None:
    player, faction = event.actors[0], event.data["faction"]
    world.update_data(player, silver=int(world.entity(player).data.get("silver", 0)) + event.data["amount"])
    set_membership(world, player, faction, stipend_at=world.time)


def sect_arts(world, faction: int) -> list[int]:
    """The faction's signature arts (3 for great, 2 for minor), made on first need."""
    entity = world.entity(faction)
    if entity.data.get("arts"):
        return list(entity.data["arts"])
    rng = rng_for(world.world_seed, f"{entity.seed_path}/arts")
    count = 3 if entity.data["tier"] == "great" else 2
    forms = entity.data["forms"]
    arts = []
    with world.transaction():
        for i in range(count):
            name, art = generate(rng, "martial", form=forms[i % len(forms)], grade=2 + i)
            arts.append(create_technique(world, name, art))
        world.update_data(faction, arts=arts)
    return arts


def teachable(world, player: int, faction: int) -> list[int]:
    rank = F.membership(world, player, faction)[0]
    known = {a.technique.id for a in known_arts(world, player)}
    arts = sect_arts(world, faction)
    return [a for i, a in enumerate(arts) if i <= rank and a not in known][:1]


def taught_events(world, player: int, elder: int, faction: int, place: int, technique: int) -> list[Event]:
    return [Event("sect_taught", (player, elder), place,
                  {"faction": faction, "technique": technique, "name": world.entity(technique).name})]


@effect("sect_taught")
def _taught(world, event) -> None:
    teach(world, event.actors[0], event.data["technique"], source="sect", teacher=event.actors[1])


def library_manual(world, player: int, faction: int) -> int | None:
    """A sect art the player may borrow as a manual: inner rank and up, not yet held or known."""
    rank = F.membership(world, player, faction)[0]
    if rank < 1:
        return None
    held = {m.technique.id for m in manuals_of(world, player)} | {a.technique.id for a in known_arts(world, player)}
    return next((a for i, a in enumerate(sect_arts(world, faction)) if i <= rank and a not in held), None)


def library_events(world, player: int, faction: int, place: int, technique: int) -> list[Event]:
    return [Event("library_lent", (player,), place,
                  {"faction": faction, "technique": technique, "name": world.entity(technique).name})]


@effect("library_lent")
def _lent(world, event) -> None:
    create_manual(world, event.actors[0], event.data["technique"], 1.0)


def gift_price(world, player: int, faction: int) -> int:
    return 20 * (F.membership(world, player, faction)[0] + 1)


def gift_events(world, player: int, elder: int, faction: int, place: int) -> list[Event]:
    amount = gift_price(world, player, faction)
    return payment_events(player, elder, place, amount, "gift") + [
        Event("gift", (player, elder), place, {"faction": faction, "amount": amount},
              witnesses=(Witness(elder, "grateful", 0.4),))]
```

- [ ] **Step 4: Write the ranks mixin** — `engine/ranks.py`
```python
"""Rising in a faction, in the engine (phase 3b spec 5)."""

from engine.actions import Action, Choice
from systems import factions as F
from systems import halls, ranks
from systems.purse import silver_of


class RanksMixin:
    def _my_faction_here(self, faction_id) -> bool:
        found = F.membership(self.world, self.player.id, faction_id)
        return bool(found and found[1].get("status", "member") == "member"
                    and self.focus is not None and faction_id in halls.recruits_for(self.world, self.focus))

    def _role(self, npc_id, faction_id) -> str | None:
        found = F.membership(self.world, npc_id, faction_id)
        return found[1].get("role") if found else None

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        me, town = self.player.id, self.place.id
        for fid in halls.recruits_for(self.world, npc.id):
            found = F.membership(self.world, me, fid)
            if not found or found[1].get("status", "member") != "member":
                continue
            role = self._role(npc.id, fid)
            if role in ("elder", "leader"):
                options.append(Choice("Ask for promotion", Action("promote", fid)))
                if ranks.teachable(self.world, me, fid):
                    options.append(Choice("Learn a sect art", Action("learn_sect_art", fid)))
                if role == "elder":
                    options.append(Choice(f"Offer a gift ({ranks.gift_price(self.world, me, fid)} silver)", Action("gift", fid)))
            if halls.keeper_at(self.world, fid, town) == npc.id:
                if ranks.stipend_due(self.world, me, fid):
                    options.append(Choice(f"Collect your stipend ({ranks.stipend_due(self.world, me, fid)} silver)",
                                          Action("stipend", fid)))
                if self.world.entity(fid).data.get("seat") == town and ranks.library_manual(self.world, me, fid):
                    options.append(Choice("Study in the library", Action("library", fid)))
        return options

    def _do_promote(self, faction_id):
        if not self._my_faction_here(faction_id) or self._role(self.focus, faction_id) not in ("elder", "leader"):
            return self._turn([("Only an elder can raise you.", "system")])
        if (why := ranks.promotion_block(self.world, self.player.id, faction_id)) is not None:
            return self._turn([(why, "system")])
        self.submenu = None
        return self._turn(self._commit(ranks.promoted_events(self.world, self.player.id, faction_id, self.focus, self.place.id)))

    def _do_stipend(self, faction_id):
        if not self._my_faction_here(faction_id) or not ranks.stipend_due(self.world, self.player.id, faction_id):
            return self._turn([("Nothing is owed to you yet.", "system")])
        self.submenu = None
        return self._turn(self._commit(ranks.stipend_events(self.world, self.player.id, faction_id, self.focus, self.place.id)))

    def _do_learn_sect_art(self, faction_id):
        arts = ranks.teachable(self.world, self.player.id, faction_id) if self._my_faction_here(faction_id) else []
        if not arts or self._role(self.focus, faction_id) not in ("elder", "leader"):
            return self._turn([("There is nothing they will teach you yet.", "system")])
        self.submenu = None
        return self._turn(self._commit(ranks.taught_events(self.world, self.player.id, self.focus, faction_id,
                                                           self.place.id, arts[0])))

    def _do_library(self, faction_id):
        manual = ranks.library_manual(self.world, self.player.id, faction_id) if self._my_faction_here(faction_id) else None
        if manual is None or self.world.entity(faction_id).data.get("seat") != self.place.id:
            return self._turn([("The library has nothing for you.", "system")])
        self.submenu = None
        return self._turn(self._commit(ranks.library_events(self.world, self.player.id, faction_id, self.place.id, manual)))

    def _do_gift(self, faction_id):
        if not self._my_faction_here(faction_id) or self._role(self.focus, faction_id) != "elder":
            return self._turn([("Gifts go to an elder.", "system")])
        price = ranks.gift_price(self.world, self.player.id, faction_id)
        if silver_of(self.world, self.player.id) < price:
            return self._turn([(f"You don't have {price} silver.", "system")])
        return self._turn(self._commit(ranks.gift_events(self.world, self.player.id, self.focus, faction_id, self.place.id)))
```

- [ ] **Step 5: Write the ranks narration** — `narrate/ranks_text.py`
```python
"""What the player is told about rising in a faction."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import cap, outcome, summary
from systems import factions as F

EXTRA_PHRASES["promoted"] = "{actor} rose in the {target}."


def _name(world, data) -> str:
    return world.entity(data["faction"]).name


@outcome("promoted", body_facts=False)
def _promoted(world, event):
    d = event.data
    return [f"You are raised to {F.title(world, d['faction'], d['rank'])} of the {_name(world, d)}."], {}


@outcome("stipend", body_facts=False)
def _stipend(world, event):
    return [f"You collect {event.data['amount']} silver from the {_name(world, event.data)}."], {}


@outcome("sect_taught", body_facts=False)
def _taught(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} teaches you the {event.data['name']}."], {}


@outcome("library_lent", body_facts=False)
def _lent(world, event):
    return [f"You are lent a manual of the {event.data['name']}."], {}


@outcome("gift", body_facts=False)
def _gift(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} accepts your gift of {event.data['amount']} silver."], {}


@summary("promoted")
def _promoted_line(world, entry, names, place, other):
    return f"Raised to {F.title(world, entry.data['faction'], entry.data['rank'])} of the {_name(world, entry.data)}."


@summary("stipend")
def _stipend_line(world, entry, names, place, other):
    return f"Collected a stipend from the {_name(world, entry.data)}."


@summary("sect_taught")
def _taught_line(world, entry, names, place, other):
    return f"Learned the {entry.data['name']} from {other}."


@summary("library_lent")
def _lent_line(world, entry, names, place, other):
    return f"Borrowed a manual of the {entry.data['name']}."


@summary("gift")
def _gift_line(world, entry, names, place, other):
    return f"Gave {other} a gift."
```

- [ ] **Step 6: Write the ranks grammar** — `narrate/grammar/ranks.toml`
```toml
[symbols]
ranks_rite = ["A bell rings three times.", "Incense is lit before the founders' tablets.", "Your new sash is tied for you.", "The elders nod as one.", "Your name is read aloud."]
ranks_after = ["Some of the disciples bow a little lower now.", "A rival looks away.", "The hall feels a little smaller.", "Someone murmurs congratulations.", "You feel the weight of the rank."]
ranks_coin = ["A small purse changes hands.", "The keeper counts the coins twice.", "Silver clinks into your palm.", "The ledger is signed.", "It is not much, but it is yours."]
ranks_lesson = ["They show you the opening stance.", "The first form is slow and exact.", "They correct your elbow twice.", "Breath and step, breath and step.", "You repeat it until it is yours."]

[promoted]
colour = "gold"
lines = ["#ranks_rite# #ranks_after#", "#ranks_after# #ranks_rite#"]

[stipend]
colour = "default"
lines = ["#ranks_coin# #ranks_after#", "#ranks_coin#"]

[sect_taught]
colour = "default"
lines = ["#ranks_lesson# #ranks_after#", "#ranks_lesson#"]

[library_lent]
colour = "default"
lines = ["#ranks_lesson# #ranks_coin#", "#ranks_lesson#"]

[gift]
colour = "default"
lines = ["#ranks_coin# #ranks_after#", "#ranks_after# #ranks_coin#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3b_task5.py`
```python
"""Task 5 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


GAME = "engine/game.py"
edit(GAME, "from engine.joining import JoiningMixin\n", "from engine.joining import JoiningMixin\nfrom engine.ranks import RanksMixin\n")
edit(GAME, "class Game(FactionsMixin, JoiningMixin,", "class Game(FactionsMixin, JoiningMixin, RanksMixin,")
edit("narrate/outcomes.py", "import narrate.faction_text  # noqa: E402,F401\n",
     "import narrate.faction_text  # noqa: E402,F401\nimport narrate.ranks_text  # noqa: E402,F401\n")
print("task 5 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task5.py && .venv/Scripts/python.exe -m pytest tests/test_ranks.py -q -p no:cacheprovider`
Expected: `task 5 edits applied`, then `5 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: promotion, stipends, sect arts, the library and gifts"`

---

### Task 6: Duties

**Files:**
- Create: `systems/duties.py`, `engine/duties.py`, `narrate/duty_text.py`, `narrate/grammar/duties.toml`
- Modify (via `.patches/3b_task6.py`):
  - `systems/encounters.py` (`ROAD_HOOKS`, plus the random encounter split out as `random_encounter`)
  - `engine/game.py` (mixin order), `narrate/outcomes.py`
- Test: `tests/test_duties.py`

**Interfaces:**
- Consumes: Tasks 1–5 (`F.*`, `halls.*`, `set_membership`), and 2b/3a `make_roamer`, `_free_roamer_slot`, `region_danger`, `encounter_events`, `ENCOUNTER_CHANCE`, `afraid` and `apparent_to`.
- Produces:
  - `systems.duties`:
    - Constants: `KINDS`, `KIND_WEIGHTS`, `RAID_CHANCE = 0.3`.
    - Reading duties: `open_duty(world, player) -> Entity | None`, `progress(world, player) -> "done" | "failed" | None`.
    - Duty events: `issue_events(world, player, faction, keeper, place, kind=None, release=False)`, `done_events(world, player, place, reason)`, `failed_events(world, player, place, reason)`.
    - Road and debts: `hunt_encounter(world, player, town, rng) -> list[Event] | None` (a road hook), `escort_encounter(world, player, town, rng) -> list[Event] | None` (a road hook), `pays_willingly(world, debtor, player) -> bool`, `debt_events(player, debtor, place, duty)`.
    - Guard duty: `raid_due(world, player, event_id, event) -> bool`, `raider(world, duty, town) -> int`.
  - Duty entity data: `{faction, holder, kind, target, town, region, deadline, difficulty, status, issued_at, days, guarded, release}`. Player data: `duty` (the open duty id) and `duties_taken`.
  - Events: `duty_issued`, `duty_done`, `duty_failed`, `debt_paid`, `raid`.
  - `systems.encounters`: `ROAD_HOOKS: list[callable(world, player, town, rng) -> list[Event] | None]` (tried first), and `random_encounter(world, player, town, rng) -> list[Event]`.
  - `engine.duties.DutiesMixin`: the verbs `duty`, `abandon_duty` and `demand`. Progress is checked after commit, look and arrival. `_after_duel` handles the purposes `collect` and `raid`.

- [ ] **Step 1: Write the failing test** — `tests/test_duties.py`
```python
import pytest

import systems.duties as duties
import systems.encounters as encounters
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event, commit
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def move_to(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def member(game, kind="orthodox_sect"):
    faction = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == kind)
    seat = halls.seat_of(game.world, faction)
    move_to(game, seat)
    game.world.relate(game.player.id, faction, "member_of", 0, {
        "role": "member", "hall": 0, "sponsor": halls.elders(game.world, faction).get(0), "merit": 0, "secret": False,
        "joined_at": 0, "status": "member", "judged": [], "stipend_at": 0})
    return faction, seat, halls.keeper_at(game.world, faction, seat)


def issue(game, faction, keeper, kind):
    game._commit(duties.issue_events(game.world, game.player.id, faction, keeper, game.place.id, kind=kind))
    return duties.open_duty(game.world, game.player.id)


def merit(game, faction):
    return F.membership(game.world, game.player.id, faction)[1]["merit"]


def test_a_keeper_hands_out_duties_that_fit_the_faction(game):
    faction, seat, keeper = member(game)
    game.perform(Action("talk", keeper))
    turn = game.perform(Action("faction_menu"))
    assert Action("duty", faction) in [c.action for c in turn.choices]
    game.perform(Action("duty", faction))
    duty = duties.open_duty(game.world, game.player.id)
    assert duty.data["kind"] in ("hunt", "deliver", "gather", "guard") and duty.data["deadline"] > game.world.time


def test_a_delivery_is_done_on_arrival(game):
    faction, seat, keeper = member(game)
    duty = issue(game, faction, keeper, "deliver")
    move_to(game, duty.data["town"])
    game.perform(Action("look"))
    assert duties.open_duty(game.world, game.player.id) is None and merit(game, faction) == 10


def test_a_hunt_target_waits_on_the_road_and_beating_it_ends_the_duty(game):
    faction, seat, keeper = member(game)
    duty = issue(game, faction, keeper, "hunt")
    x, y = duty.data["region"]
    town = ensure_town(game.world, x, y, 0)
    events = encounters.road_encounter_events(game.world, game.player.id, game.world.entity(town))
    assert events[0].kind == "encounter" and events[0].actors[1] == duty.data["target"]
    ended = {"duel": None, "mode": "encounter", "result": "won", "reason": "broken", "verdict": "spare", "by": "player",
             "silver": 0, "crippled": None, "loot": [], "insight": 1.0, "life_and_death": False, "fragment": None,
             "purpose": {}}
    game._commit([Event("duel_ended", (game.player.id, duty.data["target"]), game.place.id, ended)])
    assert duties.open_duty(game.world, game.player.id) is None and merit(game, faction) == 10


def test_an_honest_debtor_pays_up(game):
    faction, seat, keeper = member(game, "merchant_guild")
    duty = issue(game, faction, keeper, "collect")
    debtor = duty.data["target"]
    game.world.update_data(debtor, traits=["honest", "lazy"])
    move_to(game, game.world.targets(debtor, "located_in")[0])
    game.perform(Action("talk", debtor))
    game.perform(Action("demand", duty.id))
    assert duties.open_duty(game.world, game.player.id) is None


def test_learning_about_the_target_completes_a_gathering(game):
    faction, seat, keeper = member(game, "beggars")
    duty = issue(game, faction, keeper, "gather")
    target = duty.data["target"]
    fid = record_fact(game.world, target, "robbed", 12345, place=None, variant=make_variant("robbed", target, 12345))
    game.world.upsert_belief(game.player.id, fid, make_variant("robbed", target, 12345), None, 0.6, 2, "told")
    game.perform(Action("look"))
    assert duties.open_duty(game.world, game.player.id) is None


def test_guarding_the_seat_by_resting_there(game, monkeypatch):
    monkeypatch.setattr(duties, "RAID_CHANCE", 0.0)
    faction, seat, keeper = member(game)
    duty = issue(game, faction, keeper, "guard")
    for _ in range(duty.data["days"] // 7 + 1):
        game.perform(Action("rest", 7))
    assert duties.open_duty(game.world, game.player.id) is None


def test_a_raid_on_the_seat_starts_a_fight(game, monkeypatch):
    monkeypatch.setattr(duties, "RAID_CHANCE", 1.0)
    faction, seat, keeper = member(game)
    issue(game, faction, keeper, "guard")
    game.perform(Action("rest", 1))  # one day: the watch is not yet over when the raiders come
    assert game.combat is not None and game.combat.purpose.get("raid")


def test_an_overdue_duty_fails_once(game):
    faction, seat, keeper = member(game)
    duty = issue(game, faction, keeper, "deliver")
    game.world.set_time(duty.data["deadline"] + 1)
    game.perform(Action("look"))
    game.perform(Action("look"))
    failures = [e for e in game.world.chronicle_about(game.player.id, limit=20) if e.kind == "duty_failed"]
    assert len(failures) == 1 and duties.open_duty(game.world, game.player.id) is None


def test_a_dead_target_fails_the_duty(game):
    faction, seat, keeper = member(game, "merchant_guild")
    duty = issue(game, faction, keeper, "collect")
    stranger = game.world.add_entity("person", "Other Killer", {"realm": "mortal"})
    commit(game.world, [Event("died", (stranger, duty.data["target"]), game.place.id, {"cause": "killed"})])
    game.perform(Action("look"))
    assert duties.open_duty(game.world, game.player.id) is None
    assert game.world.entity(duty.id).data["status"] == "failed"


def test_abandoning_a_duty_costs_merit(game):
    faction, seat, keeper = member(game)
    game.world.relate(game.player.id, faction, "member_of", 0, {**F.membership(game.world, game.player.id, faction)[1], "merit": 25})
    issue(game, faction, keeper, "deliver")
    game.perform(Action("talk", keeper))
    game.perform(Action("abandon_duty", faction))
    assert merit(game, faction) == 15
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_duties.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.duties'`.

- [ ] **Step 3: Write duties** — `systems/duties.py`
```python
"""Duties (phase 3b spec 5): issued by a hall keeper, done in the world, rewarded in merit."""

import systems.encounters as encounters
from systems import factions as F
from systems import halls
from systems.attitude import afraid
from systems.beliefs import apparent_to
from systems.membership import set_membership
from world.events import Event, Witness, effect
from world.gen.materialize import ensure_region, ensure_town, people_at
from world.gen.region import region_spec
from world.seed import rng_for

KINDS = ("hunt", "deliver", "escort", "collect", "gather", "guard")
KIND_WEIGHTS = {
    "orthodox_sect": (3, 2, 0, 0, 1, 2), "school": (3, 2, 0, 0, 1, 2), "alliance": (3, 2, 0, 0, 1, 2),
    "demonic_cult": (3, 1, 0, 2, 1, 1), "unorthodox_clan": (3, 1, 0, 2, 1, 1), "bandit_fort": (3, 1, 0, 2, 1, 1),
    "martial_clan": (2, 2, 1, 2, 0, 2), "local_clan": (2, 2, 1, 2, 0, 2),
    "beggars": (0, 3, 0, 0, 3, 0), "merchant_guild": (1, 2, 3, 3, 1, 0), "imperial": (3, 1, 0, 1, 1, 2),
}
RAID_CHANCE = 0.3
WATCHES_PER_DAY = 4
REST_KINDS = frozenset({"rested", "cultivated", "practised"})


def open_duty(world, player: int):
    duty = world.entity(world.entity(player).data.get("duty") or 0)
    return duty if duty is not None and duty.data.get("status") == "open" else None


def _near(rng, here, radius: int) -> tuple[int, int, int]:
    dx, dy = rng.choice([(a, b) for a in range(-radius, radius + 1) for b in range(-radius, radius + 1) if (a, b) != (0, 0)])
    return here["x"] + dx, here["y"] + dy, max(abs(dx), abs(dy))


def _resident(world, rng, town: int, exclude: set) -> int | None:
    halls.settle_town(world, town)
    people = sorted(p.id for p in people_at(world, town) if p.id not in exclude and not p.data.get("is_player")
                    and not p.data.get("dead") and not p.data.get("beast") and not F.memberships(world, p.id))
    return rng.choice(people) if people else None


def _hostile_member(world, rng, faction: int) -> int | None:
    others = [f for f in F.ensure_roster(world) if f != faction and F.stance(world, faction, f) <= F.HOSTILE]
    others = others or [f for f in F.ensure_roster(world) if f != faction and F.is_martial(world, f)]
    if not others:
        return None
    rival = rng.choice(others)
    staff = halls.staff_at(world, rival, halls.seat_of(world, rival), roles=("disciple",))
    return rng.choice(staff) if staff else None


def issue_events(world, player: int, faction: int, keeper: int, place: int, kind: str | None = None,
                 release: bool = False) -> list[Event]:
    n = world.entity(player).data.get("duties_taken", 0)
    rng = rng_for(world.world_seed, f"duty:{faction}:{player}:{n}")
    ftype = world.entity(faction).data["type"]
    kind = kind or rng.choices(KINDS, weights=KIND_WEIGHTS[ftype])[0]
    here = world.entity(place).data
    rank = F.membership(world, player, faction)[0]
    data = {"faction": faction, "holder": player, "kind": kind, "target": None, "town": None, "region": None,
            "difficulty": min(3, rank + 1), "status": "open", "issued_at": world.time, "days": 0, "guarded": 0,
            "release": release, "n": n}
    regions = 1
    if kind == "hunt":
        x, y, regions = _near(rng, here, 2)
        region = world.entity(ensure_region(world, x, y))
        slot = encounters._free_roamer_slot(world, region)
        danger = encounters.region_danger(world.world_seed, x, y)
        data.update(region=[x, y], target=encounters.make_roamer(world, region, rng.choice(("bandit", "beast")), slot, danger))
    elif kind in ("deliver", "escort"):
        x, y, regions = _near(rng, here, 3 if kind == "deliver" else 2)
        data["town"] = ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))
    elif kind == "collect":
        x, y, regions = _near(rng, here, 2)
        town = ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))
        data.update(town=town, target=_resident(world, rng, town, {player}), amount=20 * data["difficulty"])
    elif kind == "gather":
        data["target"] = _hostile_member(world, rng, faction)
    elif kind == "guard":
        data.update(town=halls.seat_of(world, faction), days=5 * data["difficulty"])
    if kind in ("collect", "gather") and data["target"] is None:  # nobody fitting: carry a letter instead
        return issue_events(world, player, faction, keeper, place, kind="deliver", release=release)
    days = data["days"] + 7 if kind == "guard" else 3 * regions + 7
    data["deadline"] = world.time + days * WATCHES_PER_DAY
    target = data["target"] if kind in ("collect", "gather") else None
    return [Event("duty_issued", (player, keeper) + ((target,) if target else ()), place, data)]


@effect("duty_issued")
def _issued(world, event) -> None:
    d = dict(event.data)
    duty = world.add_entity("duty", f"{d['kind']} for #{d['faction']}", d)
    player = event.actors[0]
    world.update_data(player, duty=duty, duties_taken=d["n"] + 1)


def progress(world, player: int):
    """'done', 'failed' or None for the open duty, from the state of the world."""
    duty = open_duty(world, player)
    if duty is None:
        return None
    d = duty.data
    target = world.entity(d["target"]) if d.get("target") else None
    if d["kind"] == "hunt" and target is not None:
        for entry in world.chronicle_about(target.id, limit=20):
            if entry.kind == "duel_ended" and entry.time >= d["issued_at"] and entry.actors[0] == player \
                    and entry.data.get("result") == "won":
                needs_kill = world.entity(d["faction"]).data["path"] == "ruthless"
                if not needs_kill or entry.data.get("verdict") == "kill":
                    return "done"
    if target is not None and target.data.get("dead"):
        return "failed"
    if world.time > d["deadline"]:
        return "failed"
    if d["kind"] in ("deliver", "escort") and d["town"] in world.targets(player, "located_in"):
        return "done"
    if d["kind"] == "collect" and d.get("paid"):
        return "done"
    if d["kind"] == "gather":
        if any(b.learned_at >= d["issued_at"] and d["target"] in (b.variant.get("actor"), b.variant.get("target"))
               for b in world.beliefs(player)):
            return "done"
    if d["kind"] == "guard" and d["guarded"] >= d["days"]:
        return "done"
    return None


def done_events(world, player: int, place: int, reason: str = "done") -> list[Event]:
    duty = open_duty(world, player)
    d = duty.data
    sponsor = F.membership(world, player, d["faction"])[1].get("sponsor")
    witnesses = (Witness(sponsor, "respect", 0.3),) if sponsor else ()
    return [Event("duty_done", (player,), place, {"duty": duty.id, "faction": d["faction"], "kind": d["kind"],
                                                  "merit": 10 * d["difficulty"], "silver": 5 * d["difficulty"],
                                                  "release": d.get("release", False)}, witnesses=witnesses)]


def failed_events(world, player: int, place: int, reason: str = "late") -> list[Event]:
    duty = open_duty(world, player)
    d = duty.data
    sponsor = F.membership(world, player, d["faction"])[1].get("sponsor")
    witnesses = (Witness(sponsor, "annoyed", 0.3),) if sponsor else ()
    return [Event("duty_failed", (player,), place, {"duty": duty.id, "faction": d["faction"], "kind": d["kind"],
                                                    "reason": reason}, witnesses=witnesses)]


@effect("duty_done")
def _done(world, event) -> None:
    player, d = event.actors[0], event.data
    _, data = F.membership(world, player, d["faction"])
    set_membership(world, player, d["faction"], merit=data.get("merit", 0) + d["merit"])
    world.update_data(player, silver=int(world.entity(player).data.get("silver", 0)) + d["silver"], duty=None)
    world.update_data(d["duty"], status="done")


@effect("duty_failed")
def _failed(world, event) -> None:
    player, d = event.actors[0], event.data
    _, data = F.membership(world, player, d["faction"])
    set_membership(world, player, d["faction"], merit=max(0, data.get("merit", 0) - 10))
    world.update_data(player, duty=None)
    world.update_data(d["duty"], status="failed")


def hunt_encounter(world, player: int, town, rng):
    """A hunt's quarry waits on the roads of its region."""
    duty = open_duty(world, player)
    if duty is None or duty.data["kind"] != "hunt":
        return None
    if [town.data["x"], town.data["y"]] != duty.data["region"]:
        return None
    target = world.entity(duty.data["target"])
    if target is None or target.data.get("dead"):
        return None
    kind = target.data.get("roamer_kind", "bandit")
    return encounters.encounter_events(player, target.id, town.id, kind, 5 if kind == "bandit" else 0)


def escort_encounter(world, player: int, town, rng):
    """A caravan draws twice the trouble: a second chance at a road encounter."""
    duty = open_duty(world, player)
    if duty is None or duty.data["kind"] != "escort":
        return None
    second = rng_for(world.world_seed, f"escort:{player}:{world.time}")
    danger = encounters.region_danger(world.world_seed, town.data["x"], town.data["y"])
    if second.random() >= danger * encounters.ENCOUNTER_CHANCE:
        return None
    return encounters.random_encounter(world, player, town, second)


def pays_willingly(world, debtor: int, player: int) -> bool:
    traits = set(world.entity(debtor).data.get("traits", ()))
    return bool(traits & {"honest", "kind"}) or afraid(world, debtor, apparent_to(world, debtor, player))


def debt_events(player: int, debtor: int, place: int, duty: int, amount: int) -> list[Event]:
    return [Event("debt_paid", (player, debtor), place, {"duty": duty, "amount": amount})]


@effect("debt_paid")
def _paid(world, event) -> None:
    world.update_data(event.data["duty"], paid=True)


def raid_due(world, player: int, event_id: int, event) -> bool:
    duty = open_duty(world, player)
    if duty is None or duty.data["kind"] != "guard" or event.kind not in REST_KINDS or event.place != duty.data["town"]:
        return False
    return rng_for(world.world_seed, f"raid:{duty.id}:{event_id}").random() < RAID_CHANCE


def raider(world, duty, town: int) -> int:
    """A seeded raider of a faction hostile to the duty's, standing in the seat."""
    rng = rng_for(world.world_seed, f"raider:{duty.id}:{world.time}")
    enemy = _hostile_member(world, rng, duty.data["faction"])
    if enemy is not None:
        world.unrelate(enemy, "located_in")
        world.relate(enemy, town, "located_in")
        return enemy
    person = world.add_entity("person", "a masked raider", {"realm": world.entity(duty.data["holder"]).data.get("realm", "mortal"),
                                                            "occupation": "raider", "traits": ["hot-tempered", "proud"]})
    world.relate(person, town, "located_in")
    return person


def guarded_events(world, player: int, event) -> None:
    """Count days spent resting at the seat toward a guard duty (called by the engine)."""
    duty = open_duty(world, player)
    if duty is not None and duty.data["kind"] == "guard" and event.kind in REST_KINDS and event.place == duty.data["town"]:
        world.update_data(duty.id, guarded=duty.data["guarded"] + int(event.data.get("days", 0)))


encounters.ROAD_HOOKS.extend([hunt_encounter, escort_encounter])
```

- [ ] **Step 4: Write the duties mixin** — `engine/duties.py`
```python
"""Duties in the engine (phase 3b spec 5)."""

import systems.duties as duties
from engine.actions import Action, Choice
from systems import factions as F
from systems import halls
from world.events import Event


class DutiesMixin:
    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        me, town = self.player.id, self.place.id
        duty = duties.open_duty(self.world, me)
        for fid in halls.recruits_for(self.world, npc.id):
            found = F.membership(self.world, me, fid)
            if not found or found[1].get("status", "member") != "member" or halls.keeper_at(self.world, fid, town) != npc.id:
                continue
            if duty is None:
                options.append(Choice("Ask for a duty", Action("duty", fid)))
            elif duty.data["faction"] == fid:
                options.append(Choice("Abandon your duty", Action("abandon_duty", fid)))
        return options

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        duty = duties.open_duty(self.world, self.player.id)
        if duty is not None and duty.data["kind"] == "collect" and duty.data["target"] == npc.id and not duty.data.get("paid"):
            extras.insert(0, Choice("Demand the debt", Action("demand", duty.id)))
        return extras

    def _do_duty(self, faction_id):
        found = F.membership(self.world, self.player.id, faction_id)
        if self.focus is None or not found or halls.keeper_at(self.world, faction_id, self.place.id) != self.focus:
            return self._turn([("Only the hall keeper assigns duties.", "system")])
        if duties.open_duty(self.world, self.player.id) is not None:
            return self._turn([("Finish your current duty first.", "system")])
        self.submenu = None
        return self._turn(self._commit(duties.issue_events(self.world, self.player.id, faction_id, self.focus, self.place.id)))

    def _do_abandon_duty(self, faction_id):
        duty = duties.open_duty(self.world, self.player.id)
        if duty is None or duty.data["faction"] != faction_id:
            return self._turn([("You have no duty to abandon.", "system")])
        self.submenu = None
        return self._turn(self._commit(duties.failed_events(self.world, self.player.id, self.place.id, "abandoned")))

    def _do_demand(self, duty_id):
        duty = duties.open_duty(self.world, self.player.id)
        if duty is None or duty.id != duty_id or self.focus != duty.data["target"]:
            return self._turn([("They owe your faction nothing.", "system")])
        debtor = self.focus
        if duties.pays_willingly(self.world, debtor, self.player.id):
            return self._turn(self._commit(duties.debt_events(self.player.id, debtor, self.place.id, duty.id, duty.data["amount"])))
        return self._turn(self._start_duel(debtor, "duel", purpose={"collect": duty.id}))

    def _duty_progress(self) -> list:
        state = duties.progress(self.world, self.player.id)
        if state == "done":
            return self._commit(duties.done_events(self.world, self.player.id, self.place.id))
        if state == "failed":
            return self._commit(duties.failed_events(self.world, self.player.id, self.place.id))
        return []

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        if any(e.kind in ("duty_issued", "duty_done", "duty_failed") for e in events):
            return lines
        raid = None
        for event_id, event in zip(ids, events):
            duties.guarded_events(self.world, self.player.id, event)
            if raid is None and self.combat is None and duties.raid_due(self.world, self.player.id, event_id, event):
                raid = duties.open_duty(self.world, self.player.id)
        lines += self._duty_progress()
        if raid is not None and duties.open_duty(self.world, self.player.id) is not None:
            enemy = duties.raider(self.world, raid, self.place.id)
            lines += self._commit([Event("raid", (self.player.id, enemy), self.place.id, {"duty": raid.id})])
            lines += self._start_duel(enemy, "duel", purpose={"raid": raid.id})
        return lines

    def _after_look(self) -> list:
        return super()._after_look() + self._duty_progress()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._duty_progress()

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        duty = duties.open_duty(self.world, self.player.id)
        if duty is None:
            return lines
        if purpose.get("collect") == duty.id and data["result"] == "won":
            lines += self._commit(duties.debt_events(self.player.id, duty.data["target"], self.place.id, duty.id,
                                                     duty.data["amount"]))
        elif purpose.get("raid") == duty.id and data["result"] in ("lost", "fled"):
            lines += self._commit(duties.failed_events(self.world, self.player.id, self.place.id, "raided"))
        return lines
```

- [ ] **Step 5: Write the duty narration** — `narrate/duty_text.py`
```python
"""What the player is told about duties."""

from narrate.outcomes import cap, outcome, summary

VERBS = {"hunt": "Hunt down {target} in the {region}", "deliver": "Carry a sealed letter to {town}",
         "escort": "Escort a caravan to {town}", "collect": "Collect {amount} silver owed by {target} of {town}",
         "gather": "Find out what you can about {target}", "guard": "Stand guard at the seat for {days} days"}


def _faction(world, data) -> str:
    return world.entity(data["faction"]).name


@outcome("duty_issued", body_facts=False)
def _issued(world, event):
    d = event.data
    target = world.entity(d["target"]).name if d.get("target") else "someone"
    town = world.entity(d["town"]).name if d.get("town") else "the seat"
    region = world.entity(world.targets(d["target"], "located_in")[0]).name if d["kind"] == "hunt" else ""
    days = max(1, (d["deadline"] - world.time) // 4)
    task = VERBS[d["kind"]].format(target=target, town=town, region=region, amount=d.get("amount", 0), days=d["days"])
    return [f"Your duty for the {_faction(world, d)}: {task}, within {days} days."], {}


@outcome("duty_done", body_facts=False)
def _done(world, event):
    d = event.data
    return [f"Your duty for the {_faction(world, d)} is done: {d['merit']} merit and {d['silver']} silver."], {}


@outcome("duty_failed", body_facts=False)
def _failed(world, event):
    why = {"abandoned": "You abandon", "raided": "The raiders break through; you have failed",
           "late": "You have failed"}.get(event.data["reason"], "You have failed")
    return [f"{why} your duty for the {_faction(world, event.data)}."], {}


@outcome("debt_paid", body_facts=False)
def _paid(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} pays the {event.data['amount']} silver owed."], {}


@outcome("raid", body_facts=False)
def _raid(world, event):
    return [f"Raiders strike at the seat! {cap(world.entity(event.actors[1]).name)} comes at you."], {}


@summary("duty_issued")
def _issued_line(world, entry, names, place, other):
    return f"Took a duty for the {_faction(world, entry.data)}."


@summary("duty_done")
def _done_line(world, entry, names, place, other):
    return f"Finished a duty for the {_faction(world, entry.data)}."


@summary("duty_failed")
def _failed_line(world, entry, names, place, other):
    return f"Failed a duty for the {_faction(world, entry.data)}."


@summary("debt_paid")
def _paid_line(world, entry, names, place, other):
    return f"Collected a debt from {other}."


@summary("raid")
def _raid_line(world, entry, names, place, other):
    return f"Fought off {other} at the seat."
```

- [ ] **Step 6: Write the duty grammar** — `narrate/grammar/duties.toml`
```toml
[symbols]
duty_order = ["The keeper runs a finger down the ledger.", "A slip of paper is pressed into your hand.", "The keeper lowers their voice.", "It is written, sealed and handed over.", "The keeper does not look up from the ledger."]
duty_charge = ["Do not dawdle.", "The hall is counting on you.", "Come back with it done.", "Mind the roads.", "Do it quietly."]
duty_well = ["The ledger is marked.", "A nod of approval.", "Word of it will reach the elders.", "The keeper almost smiles.", "It is noted."]
duty_ill = ["The ledger is marked in red.", "The keeper sighs.", "Word of it will reach the elders.", "A cold silence.", "It is noted, and not kindly."]
duty_alarm = ["A shout goes up at the gate.", "Steel rings in the courtyard.", "Someone is on the wall.", "The bell clangs wildly.", "Dust rises at the gate."]

[duty_issued]
colour = "npc"
lines = ["#duty_order# #duty_charge#", "#duty_charge# #duty_order#"]

[duty_done]
colour = "gold"
lines = ["#duty_well# #duty_charge#", "#duty_well#"]

[duty_failed]
colour = "default"
lines = ["#duty_ill# #duty_charge#", "#duty_ill#"]

[debt_paid]
colour = "npc"
lines = ["#duty_well# #duty_charge#", "#duty_well#"]

[raid]
colour = "default"
lines = ["#duty_alarm# #duty_charge#", "#duty_alarm#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3b_task6.py`
```python
"""Task 6 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


ENC = "systems/encounters.py"
edit(ENC, '''AVENGER_RANGE = 3           # regions from their home
''', '''AVENGER_RANGE = 3           # regions from their home
ROAD_HOOKS: list = []       # fn(world, player, town, rng) -> events or None; tried before the normal roll (phase 3b)
''')
edit(ENC, '''    rng = rng_for(world.world_seed, f"road:{player}:{world.time}")
    if rng.random() >= danger * ENCOUNTER_CHANCE:
        return _avenger_events(world, player, town, rng)
    kinds = ''', '''    rng = rng_for(world.world_seed, f"road:{player}:{world.time}")
    for hook in ROAD_HOOKS:
        found = hook(world, player, town, rng)
        if found:
            return found
    if rng.random() >= danger * ENCOUNTER_CHANCE:
        return _avenger_events(world, player, town, rng)
    return random_encounter(world, player, town, rng)


def random_encounter(world, player: int, town, rng) -> list[Event]:
    """A bandit, beast or wanderer of the region steps onto the road."""
    region = region_of(world, town.id)
    danger = region_danger(world.world_seed, region.data["x"], region.data["y"])
    kinds = ''')

GAME = "engine/game.py"
edit(GAME, "from engine.ranks import RanksMixin\n", "from engine.ranks import RanksMixin\nfrom engine.duties import DutiesMixin\n")
edit(GAME, "class Game(FactionsMixin, JoiningMixin, RanksMixin,", "class Game(FactionsMixin, JoiningMixin, RanksMixin, DutiesMixin,")
edit("narrate/outcomes.py", "import narrate.ranks_text  # noqa: E402,F401\n",
     "import narrate.ranks_text  # noqa: E402,F401\nimport narrate.duty_text  # noqa: E402,F401\n")
print("task 6 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task6.py && .venv/Scripts/python.exe -m pytest tests/test_duties.py -q -p no:cacheprovider`
Expected: `task 6 edits applied`, then `10 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: faction duties - hunt, deliver, escort, collect, gather, guard"`

---
### Task 7: Politics: the rival, framing, taboos, summons and judgement

**Files:**
- Create: `systems/politics.py`, `engine/politics.py`, `narrate/politics_text.py`, `narrate/grammar/politics.toml`
- Modify (via `.patches/3b_task7.py`): `engine/game.py` (mixin order), `narrate/outcomes.py`
- Test: `tests/test_politics.py`

**Interfaces:**
- Consumes: Tasks 1–6 (`F.*`, `halls.*`, `standing.knowledge`, `standing.seen_ids`, `set_membership`, `left_events`, `duties._hostile_member`), 3a `attitude`, `is_bandit` and `apparent_to`, and `realm_index`.
- Produces:
  - `systems.politics`:
    - Constants: `FRAME_CHANCE = 0.15`, `PUNISH_MERIT = 30`, `DENY_BASE = 0.4`.
    - Rival and framing: `rival_of(world, player, faction) -> int | None`, `frame(world, player, faction, duty_id) -> bool` (commits the rival's lie itself, unnarrated).
    - Taboos: `taboo_broken(world, faction, predicate, target) -> bool`, `breaches(world, player, faction) -> list[Fact]`.
    - Judgement: `accuser(world, player, faction) -> int`, `summons_events(world, player, town) -> list[Event]`, `deny_chance(world, player, summons, town) -> float`, `judged_events(world, player, place, outcome, demote=False)`, `exposed_events(world, player, place)`.
  - Player data: `rivals: {faction: id}`, `summons = {faction, fact, accuser}` or None, `exposable = {faction, fact, rival}` or None.
  - Events: `summoned`, `judged` (outcome punished, cleared or expelled), `rival_exposed`. There is a listener on `joined` (picks the rival) and one on `duty_done` (maybe framing).
  - `engine.politics.PoliticsMixin`: the verbs `judgement` (accept, combat, deny, refuse) and `expose`. A pending summons gates actions and survives reload, because it lives in player data.

- [ ] **Step 1: Write the failing test** — `tests/test_politics.py`
```python
import pytest

import systems.encounters as encounters
import systems.politics as politics
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm_rivals(monkeypatch):
    """The rival is a grudge challenger; keep random call-outs from pre-empting a summons in these tests."""
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)


def joined_sect(game):
    """Join the first orthodox sect through its real joining event (so the rival is picked)."""
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, seat, "located_in")
    from systems.membership import joined_events
    game._commit(joined_events(game.world, game.player.id, halls.keeper_at(game.world, sect, seat), sect, seat, False))
    return sect, seat


def innocent_robbed(game, seat):
    victim = next(p for p in halls.people_at(game.world, seat) if not F.memberships(game.world, p.id)
                  and not p.data.get("is_player"))
    return record_fact(game.world, game.player.id, "robbed", victim.id, place=seat,
                       variant=make_variant("robbed", game.player.id, victim.id, place=game.world.entity(seat).name))


def test_joining_a_great_sect_gives_you_a_proud_rival(game):
    sect, seat = joined_sect(game)
    rival = politics.rival_of(game.world, game.player.id, sect)
    assert rival in halls.staff_at(game.world, sect, seat, roles=("disciple",))
    assert "proud" in game.world.entity(rival).data["traits"]
    assert any(m.feeling == "annoyed" for m in game.world.memories(rival, about=game.player.id))


def test_breaking_a_taboo_brings_a_summons(game):
    sect, seat = joined_sect(game)
    fact = innocent_robbed(game, seat)
    assert [f.id for f in politics.breaches(game.world, game.player.id, sect)] == [fact]
    turn = game.perform(Action("look"))
    assert game.player.data["summons"]["fact"] == fact
    assert [c.action.target for c in turn.choices] == ["accept", "combat", "deny", "refuse"]
    assert game.perform(Action("rest", 1)).lines[-1][1] == "system"  # nothing else until you answer


def test_deeds_before_joining_are_not_judged(game):
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    innocent_robbed(game, seat)
    game.world.set_time(game.world.time + 1)
    joined_sect(game)
    assert politics.breaches(game.world, game.player.id, sect) == []


def test_accepting_punishment_costs_merit_and_can_demote(game):
    sect, seat = joined_sect(game)
    game.world.relate(game.player.id, sect, "member_of", 1, {**F.membership(game.world, game.player.id, sect)[1], "merit": 10})
    innocent_robbed(game, seat)
    game.perform(Action("look"))
    game.perform(Action("judgement", "accept"))
    rank, data = F.membership(game.world, game.player.id, sect)
    assert (rank, data["merit"]) == (0, 0) and game.player.data.get("summons") is None


def test_refusing_judgement_means_expulsion(game):
    sect, seat = joined_sect(game)
    innocent_robbed(game, seat)
    game.perform(Action("look"))
    game.perform(Action("judgement", "refuse"))
    assert F.membership(game.world, game.player.id, sect)[1]["status"] == "expelled"


def test_trial_by_combat_against_the_accuser(game):
    sect, seat = joined_sect(game)
    innocent_robbed(game, seat)
    game.perform(Action("look"))
    game.perform(Action("judgement", "combat"))
    assert game.combat is not None and game.combat.opponent == game.player.data["summons"]["accuser"]
    game._finish_duel({"mode": "duel", "result": "won", "purpose": {"judgement": game.player.data["summons"]["fact"]}})
    assert game.player.data.get("summons") is None and F.membership(game.world, game.player.id, sect)[1]["status"] == "member"


def test_a_framing_can_be_denied_and_the_rival_exposed(game, monkeypatch):
    monkeypatch.setattr(politics, "FRAME_CHANCE", 1.0)
    monkeypatch.setattr(politics, "deny_chance", lambda *args, **kwargs: 1.0)
    sect, seat = joined_sect(game)
    rival = politics.rival_of(game.world, game.player.id, sect)
    game._commit([Event("duty_issued", (game.player.id, halls.keeper_at(game.world, sect, seat)), seat, {
        "faction": sect, "holder": game.player.id, "kind": "deliver", "target": None, "town": seat, "region": None,
        "difficulty": 1, "status": "open", "issued_at": game.world.time, "days": 0, "guarded": 0, "release": False,
        "n": 0, "deadline": game.world.time + 40})])
    game.perform(Action("look"))  # the delivery is done here, and the rival strikes
    lie = game.world.facts(is_true=False)[0]
    assert lie.data["liar"] == rival
    game.perform(Action("look"))
    assert game.player.data["summons"]["fact"] == lie.id
    turn = game.perform(Action("judgement", "deny"))
    assert any(game.world.entity(rival).name in text for text, _ in turn.lines)
    sponsor = F.membership(game.world, game.player.id, sect)[1]["sponsor"]
    game.perform(Action("talk", sponsor))
    game.perform(Action("expose", sect))
    assert F.membership(game.world, rival, sect)[1]["status"] == "expelled"
    assert F.membership(game.world, game.player.id, sect)[1]["merit"] >= 20


def test_a_summons_survives_a_reload(game, tmp_path):
    sect, seat = joined_sect(game)
    innocent_robbed(game, seat)
    game.perform(Action("look"))
    path = game.world.path
    game.close()
    again = Game.load(path)
    turn = again.look()
    assert [c.action.verb for c in turn.choices] == ["judgement"] * 4
    again.close()
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_politics.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.politics'`.

- [ ] **Step 3: Write politics** — `systems/politics.py`
```python
"""Politics inside a faction (phase 3b spec 6): the rival, framing, taboos, summons and judgement.

A taboo is judged from what the faction has heard (its towns' gossip), never
from the truth: a framed member is summoned exactly like a guilty one.
"""

from systems import factions as F
from systems import halls
from systems.attitude import attitude, is_bandit
from systems.beliefs import apparent_to
from systems.duties import _hostile_member
from systems.facts import make_variant, place_name, record_fact
from systems.membership import left_events, set_membership
from systems.realms import realm_index
from systems.standing import knowledge, seen_ids
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

FRAME_CHANCE = 0.15
PUNISH_MERIT = 30
DENY_BASE = 0.4
HARMFUL = frozenset({"killed", "crippled", "robbed", "left_for_dead", "defeated"})
RIGHTEOUS_TYPES = frozenset({"orthodox_sect", "school", "alliance"})


def rival_of(world, player: int, faction: int) -> int | None:
    return (world.entity(player).data.get("rivals") or {}).get(str(faction))


@listen("joined")
def _pick_rival(world, event, event_id: int) -> None:
    player, faction = event.actors[0], event.data["faction"]
    data = world.entity(faction).data
    if data["tier"] != "great" or data["type"] not in F.STAFFED or rival_of(world, player, faction):
        return
    disciples = halls.staff_at(world, faction, halls.seat_of(world, faction), roles=("disciple",))
    if not disciples:
        return
    rival = rng_for(world.world_seed, f"rival:{faction}:{player}").choice(sorted(disciples))
    traits = world.entity(rival).data.get("traits", [])
    world.update_data(rival, traits=list(dict.fromkeys(["proud", *traits]))[:2])
    world.add_memory(rival, event_id, "annoyed", 0.5, ignore_existing=True)
    rivals = dict(world.entity(player).data.get("rivals") or {})
    rivals[str(faction)] = rival
    world.update_data(player, rivals=rivals)


def taboo_broken(world, faction: int, predicate: str, target) -> bool:
    kind = world.entity(faction).data["type"]
    victim = world.entity(target) if isinstance(target, int) else None
    theirs = [fid for fid, _, d in F.memberships(world, target) if d.get("status", "member") == "member"] if victim else []
    innocent = victim is not None and victim.kind == "person" and not is_bandit(victim) \
        and not victim.data.get("beast") and realm_index(victim.data.get("realm", "mortal")) == 0
    dark = victim is not None and victim.kind == "faction" and victim.data["type"] in F.DARK
    if kind in RIGHTEOUS_TYPES or kind == "imperial":
        if predicate in ("killed", "robbed") and innocent:
            return True
        if predicate == "member_of" and dark:
            return True
        return kind == "imperial" and predicate == "crippled"
    if kind in F.DARK:
        return predicate == "spared" and any(F.stance(world, faction, g) <= F.HOSTILE for g in theirs)
    if kind in ("martial_clan", "local_clan"):
        return predicate in HARMFUL and faction in theirs
    if kind == "beggars":
        return predicate in HARMFUL and victim is not None and victim.data.get("occupation") == "beggar"
    if kind == "merchant_guild":
        return predicate == "robbed" and victim is not None and victim.data.get("occupation") == "merchant"
    return False


def breaches(world, player: int, faction: int) -> list:
    """Taboos the faction has heard the player broke since joining, not yet judged."""
    found = F.membership(world, player, faction)
    if not found or found[1].get("status", "member") != "member":
        return []
    data = found[1]
    judged = set(data.get("judged", []))
    know = knowledge(world, faction)
    seen = seen_ids(world, faction, player, know)
    out = []
    for belief, fact in know:
        if fact.id in judged or belief.variant.get("actor") not in seen or fact.time < data.get("joined_at", 0):
            continue
        if taboo_broken(world, faction, fact.predicate, belief.variant.get("target")):
            out.append(fact)
    return sorted(out, key=lambda f: f.id)


def accuser(world, player: int, faction: int) -> int | None:
    """The elder of the other hall, else the leader, else a hall keeper."""
    hall = F.membership(world, player, faction)[1].get("hall")
    elders = halls.elders(world, faction) if world.entity(faction).data["type"] in F.STAFFED else {}
    other = elders.get(1 - hall) if isinstance(hall, int) else None
    if other:
        return other
    seat = halls.seat_of(world, faction)
    leaders = halls.staff_at(world, faction, seat, roles=("leader",))
    return leaders[0] if leaders else halls.keeper_at(world, faction, seat)


def summons_events(world, player: int, town: int) -> list[Event]:
    """Being in a hall town of a faction that has heard of an unjudged breach: be summoned."""
    if world.entity(player).data.get("summons"):
        return []
    for fid in halls.halls_here(world, town):
        found = F.membership(world, player, fid)
        if not found or found[1].get("status", "member") != "member":
            continue
        pending = breaches(world, player, fid)
        judge = accuser(world, player, fid)
        if pending and judge:
            fact = pending[0]
            return [Event("summoned", (player, judge), town,
                          {"faction": fid, "fact": fact.id, "predicate": fact.predicate, "accuser": judge})]
    return []


@effect("summoned")
def _summoned(world, event) -> None:
    d = event.data
    world.update_data(event.actors[0], summons={"faction": d["faction"], "fact": d["fact"], "accuser": d["accuser"]})


def _contradicted(world, player: int, fact, town: int) -> bool:
    """Someone here who would know first-hand it did not happen: the named victim, with no memory of it."""
    target = fact.variant.get("target")
    if not isinstance(target, int) or target not in {p.id for p in people_at(world, town)}:
        return False
    return not any(m.event.kind in ("duel_ended", "exchange") for m in world.memories(target, about=player))


def deny_chance(world, player: int, summons: dict, town: int) -> float:
    faction = summons["faction"]
    sponsor = F.membership(world, player, faction)[1].get("sponsor")
    favour = attitude(world, sponsor, apparent_to(world, sponsor, player)).score if sponsor else 0.0
    hostility = attitude(world, summons["accuser"], apparent_to(world, summons["accuser"], player)).score
    witness = 0.4 if _contradicted(world, player, world.fact(summons["fact"]), town) else 0.0
    return max(0.0, min(1.0, DENY_BASE + 0.25 * favour - 0.25 * hostility + witness))


def judged_events(world, player: int, place: int, outcome: str, demote: bool = False) -> list[Event]:
    summons = world.entity(player).data["summons"]
    events = [Event("judged", (player, summons["accuser"]), place, {**summons, "outcome": outcome, "demote": demote})]
    if outcome == "expelled":
        events += left_events(world, player, summons["faction"], place, "expelled")
    return events


@effect("judged")
def _judged(world, event) -> None:
    player, d = event.actors[0], event.data
    rank, data = F.membership(world, player, d["faction"])
    changes = {"judged": [*data.get("judged", []), d["fact"]]}
    if d["outcome"] == "punished":
        merit = data.get("merit", 0)
        demote = merit < PUNISH_MERIT and rank > 0  # can't pay the full price in merit: pay in rank
        set_membership(world, player, d["faction"], rank=rank - 1 if demote else rank,
                       merit=max(0, merit - PUNISH_MERIT), **changes)
    else:
        set_membership(world, player, d["faction"], **changes)
    exposable = None
    if d["outcome"] == "cleared":
        fact = world.fact(d["fact"])
        liar = fact.data.get("liar") if fact is not None else None
        if liar and liar == rival_of(world, player, d["faction"]):  # the elder knows who told them
            exposable = {"faction": d["faction"], "fact": d["fact"], "rival": liar}
    world.update_data(player, summons=None, exposable=exposable)


@listen("duty_done")
def _maybe_framed(world, event, event_id: int) -> None:
    player, faction = event.actors[0], event.data["faction"]
    if rng_for(world.world_seed, f"frame:{event.data['duty']}").random() < FRAME_CHANCE:
        frame(world, player, faction, event.data["duty"])


def frame(world, player: int, faction: int, duty_id: int) -> bool:
    """The rival tells the other hall's elder an invented breach (an unnarrated, offstage lie)."""
    rival = rival_of(world, player, faction)
    if rival is None or world.entity(rival).data.get("dead"):
        return False
    judge = accuser(world, player, faction)
    seat = halls.seat_of(world, faction)
    rng = rng_for(world.world_seed, f"frame-target:{duty_id}")
    if world.entity(faction).data["path"] == "ruthless":
        predicate, target = "spared", _hostile_member(world, rng, faction)
    else:
        pool = sorted(p.id for p in people_at(world, seat) if not F.memberships(world, p.id) and not p.data.get("is_player"))
        predicate, target = "robbed", (rng.choice(pool) if pool else None)
    if judge is None or target is None:
        return False
    story = make_variant(predicate, player, target, place=place_name(world, seat))
    commit(world, [Event("told", (rival, judge), seat,
                         {"fact": None, "variant": story, "invented": True, "accepted": True, "speaker": rival},
                         witnesses=(Witness(judge, "engaged", 0.1),))])
    return True


def exposed_events(world, player: int, place: int) -> list[Event]:
    ex = world.entity(player).data["exposable"]
    return [Event("rival_exposed", (player, ex["rival"]), place, ex, witnesses=(Witness(ex["rival"], "wronged", 0.8),))]


@effect("rival_exposed")
def _exposed(world, event) -> None:
    player, rival, d = event.actors[0], event.actors[1], event.data
    set_membership(world, rival, d["faction"], status="expelled")
    _, data = F.membership(world, player, d["faction"])
    set_membership(world, player, d["faction"], merit=data.get("merit", 0) + 20)
    world.update_data(player, exposable=None)


@listen("rival_exposed")
def _exposed_fact(world, event, event_id: int) -> None:
    player, rival = event.actors
    record_fact(world, rival, "lied_about", player, place=event.place, source_event=event_id,
                variant=make_variant("lied_about", rival, player, place=place_name(world, event.place)))
```

- [ ] **Step 4: Write the politics mixin** — `engine/politics.py`
```python
"""Politics in the engine (phase 3b spec 6): summons, judgement, and exposing the rival."""

import random

import systems.politics as politics
from engine.actions import Action, Choice
from systems import factions as F
from world.seed import rng_for

JUDGE_VERBS = frozenset({"judgement", "help", "journal", "unknown", "ambiguous", "standing"})
JUDGE_LABELS = (("accept", "Accept the punishment"), ("combat", "Demand trial by combat"),
                ("deny", "Deny the charge"), ("refuse", "Refuse to answer"))


class PoliticsMixin:
    def _summons(self):
        return self.player.data.get("summons") if self.combat is None and self.encounter is None else None

    def _gate(self, action):
        if self._summons() and action.verb not in JUDGE_VERBS:
            name = self.world.entity(self._summons()["faction"]).name
            return self._turn([(f"The {name} is waiting for your answer.", "system")])
        return super()._gate(action)

    def _special_choices(self):
        if self._summons():
            return [Choice(label, Action("judgement", key)) for key, label in JUDGE_LABELS], []
        return super()._special_choices()

    def _summon_check(self) -> list:
        if self.combat is not None or self.encounter is not None or self.challenger is not None:
            return []
        events = politics.summons_events(self.world, self.player.id, self.place.id)
        return self._commit(events) if events else []

    def _after_look(self) -> list:
        return super()._after_look() + self._summon_check()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._summon_check()

    def _do_judgement(self, choice):
        summons = self._summons()
        if not summons:
            return self._turn([("No one has summoned you.", "system")])
        me, place = self.player.id, self.place.id
        if choice == "accept":
            return self._turn(self._commit(politics.judged_events(self.world, me, place, "punished")))
        if choice == "refuse":
            return self._turn(self._commit(politics.judged_events(self.world, me, place, "expelled")))
        if choice == "combat":
            return self._turn(self._start_duel(summons["accuser"], "duel", purpose={"judgement": summons["fact"]}))
        if choice == "deny":
            roll = rng_for(self.world.world_seed, f"deny:{summons['fact']}:{me}").random()
            outcome = "cleared" if roll < politics.deny_chance(self.world, me, summons, place) else "expelled"
            return self._turn(self._commit(politics.judged_events(self.world, me, place, outcome)))
        return self._turn([("Accept, fight, deny or refuse?", "system")])

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        fact = (data.get("purpose") or {}).get("judgement")
        summons = self.player.data.get("summons")
        if fact and summons and summons["fact"] == fact:
            outcome = "cleared" if data["result"] == "won" else "punished"
            lines += self._commit(politics.judged_events(self.world, self.player.id, self.place.id, outcome))
        return lines

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        ex = self.player.data.get("exposable")
        if ex and F.membership(self.world, self.player.id, ex["faction"])[1].get("sponsor") == npc.id:
            options.insert(0, Choice(f"Expose {self.world.entity(ex['rival']).name}", Action("expose", ex["faction"])))
        return options

    def _do_expose(self, faction_id):
        ex = self.player.data.get("exposable")
        if not ex or ex["faction"] != faction_id or self.focus is None:
            return self._turn([("You have nothing to expose.", "system")])
        self.submenu = None
        return self._turn(self._commit(politics.exposed_events(self.world, self.player.id, self.place.id)))
```

- [ ] **Step 5: Write the politics narration** — `narrate/politics_text.py`
```python
"""What the player is told about summons, judgement and rivals."""

from narrate.outcomes import cap, outcome, summary

CHARGES = {"robbed": "robbing", "killed": "killing", "crippled": "crippling", "spared": "sparing",
           "member_of": "consorting with", "defeated": "attacking", "left_for_dead": "maiming"}


def _faction(world, data) -> str:
    return world.entity(data["faction"]).name


def _charge(world, data) -> str:
    fact = world.fact(data["fact"])
    target = fact.variant.get("target") if fact is not None else None
    whom = world.entity(target).name if isinstance(target, int) and world.entity(target) else "someone"
    return f"{CHARGES.get(data.get('predicate') or (fact.predicate if fact else ''), 'wrongdoing')} {whom}"


@outcome("summoned", body_facts=False)
def _summoned(world, event):
    d = event.data
    return [f"{cap(world.entity(event.actors[1]).name)} summons you before the {_faction(world, d)}.",
            f"You stand accused of {_charge(world, d)}."], {}


@outcome("judged", body_facts=False)
def _judged(world, event):
    d = event.data
    line = {"punished": "You are punished: your merit is docked.", "cleared": "The charge is set aside.",
            "expelled": "Judgement goes against you."}[d["outcome"]]
    out = [line]
    fact = world.fact(d["fact"])
    liar = fact.data.get("liar") if fact is not None else None
    if d["outcome"] == "cleared" and liar:
        out.append(f"{cap(world.entity(event.actors[1]).name)} lets slip that it was {world.entity(liar).name} who spread it.")
    return out, {}


@outcome("rival_exposed", body_facts=False)
def _exposed(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} is exposed as a liar and cast out.", "Your standing rises."], {}


@summary("summoned")
def _summoned_line(world, entry, names, place, other):
    return f"Summoned by the {_faction(world, entry.data)}."


@summary("judged")
def _judged_line(world, entry, names, place, other):
    return f"Judged by the {_faction(world, entry.data)}: {entry.data['outcome']}."


@summary("rival_exposed")
def _exposed_line(world, entry, names, place, other):
    return f"Exposed {other} as a liar."
```

- [ ] **Step 6: Write the politics grammar** — `narrate/grammar/politics.toml`
```toml
[symbols]
politics_court = ["The hall falls silent.", "Elders sit in a hard row.", "Every eye is on you.", "Incense smoke hangs still.", "A gong sounds once."]
politics_weigh = ["Words are weighed.", "Someone coughs.", "A rival watches from the side.", "A brush waits over the ledger.", "The accuser does not blink."]
politics_close = ["The matter is closed.", "It is done.", "The elders rise.", "The ledger is shut.", "No one speaks after."]

[summoned]
colour = "npc"
lines = ["#politics_court# #politics_weigh#", "#politics_weigh# #politics_court#"]

[judged]
colour = "default"
lines = ["#politics_weigh# #politics_close#", "#politics_close# #politics_court#"]

[rival_exposed]
colour = "gold"
lines = ["#politics_court# #politics_close#", "#politics_close# #politics_weigh#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3b_task7.py`
```python
"""Task 7 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


GAME = "engine/game.py"
edit(GAME, "from engine.duties import DutiesMixin\n", "from engine.duties import DutiesMixin\nfrom engine.politics import PoliticsMixin\n")
edit(GAME, "RanksMixin, DutiesMixin,", "RanksMixin, DutiesMixin, PoliticsMixin,")
edit("narrate/outcomes.py", "import narrate.duty_text  # noqa: E402,F401\n",
     "import narrate.duty_text  # noqa: E402,F401\nimport narrate.politics_text  # noqa: E402,F401\n")
print("task 7 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task7.py && .venv/Scripts/python.exe -m pytest tests/test_politics.py -q -p no:cacheprovider`
Expected: `task 7 edits applied`, then `8 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: rivals, framing, taboos and judgement"`

---

### Task 8: Leaving: release, desertion, hunters and spies

**Files:**
- Create: `systems/leaving.py`, `engine/leaving.py`
- Modify (via `.patches/3b_task8.py`):
  - `systems/encounters.py` (`HUNTER_HOOKS`, untalkable hunters)
  - `narrate/road_text.py` (hunter encounter lines), `narrate/grammar/roads.toml`
  - `engine/game.py` (mixin order)
- Test: `tests/test_leaving.py`

**Interfaces:**
- Consumes: Tasks 1–7 (`left_events`, `set_membership`, `standing.believed_factions`, `duties.issue_events`, `halls.*`, `ROAD_HOOKS`), and `encounters.make_roamer`, `_free_roamer_slot`, `encounter_events`, `region_danger`.
- Produces:
  - `systems.leaving`:
    - Constants: `NEVER_RELEASE`, `RELEASE_PER_RANK = 50`, `HUNTER_CHANCE = 0.2`, `HUNT_RANGE = 2`.
    - Release: `release_price(world, player, faction) -> int`, `release_events(world, player, faction, keeper, place)`.
    - Hunters: `gone_from(world, player) -> list[int]` (factions that expelled the player or that the player deserted or spied on), `town_hunters(world, player) -> set[int]` (a `HUNTER_HOOKS` entry), `hunter_encounter(world, player, town, rng)` (a `ROAD_HOOKS` entry).
    - Spies: `spy_checks(world, player, place) -> list[Event]`.
    - A listener on `expelled`, `deserted` and `spy_exposed` gives every materialized staff member a `wronged` memory.
  - `systems.encounters`: `HUNTER_HOOKS: list[callable(world, player) -> set[int]]`. `talk_succeeds` is False for `sect_hunter` and `bounty_hunter`.
  - `engine.leaving.LeavingMixin`: the verbs `release` (pay), `release_duty` and `desert`. Spy checks run on look and arrival. A release completes when a duty flagged `release` is done.

- [ ] **Step 1: Write the failing test** — `tests/test_leaving.py`
```python
import pytest

import systems.encounters as encounters
import systems.leaving as leaving
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.purse import silver_of
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def member_of(game, kind, rank=0, secret=False):
    faction = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == kind)
    seat = halls.seat_of(game.world, faction)
    game.world.relate(game.player.id, faction, "member_of", rank, {
        "role": "member", "hall": 0, "sponsor": None, "merit": 0, "secret": secret, "joined_at": 0,
        "status": "member", "judged": [], "stipend_at": 0})
    return faction, seat


def go(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def test_an_orthodox_sect_releases_you_for_a_price(game):
    sect, seat = member_of(game, "orthodox_sect", rank=1)
    go(game, seat)
    game.world.update_data(game.player.id, silver=200)
    game.perform(Action("talk", halls.keeper_at(game.world, sect, seat)))
    game.perform(Action("release", sect))
    assert F.membership(game.world, game.player.id, sect)[1]["status"] == "released"
    assert silver_of(game.world, game.player.id) == 100


def test_a_cult_never_releases_anyone(game):
    cult, seat = member_of(game, "demonic_cult")
    go(game, seat)
    game.perform(Action("talk", halls.keeper_at(game.world, cult, seat)))
    turn = game.perform(Action("faction_menu"))
    actions = {c.action.verb for c in turn.choices}
    assert "release" not in actions and "desert" in actions


def test_deserters_are_hated_and_hunted(game, monkeypatch):
    cult, seat = member_of(game, "demonic_cult")
    go(game, seat)
    keeper = halls.keeper_at(game.world, cult, seat)
    game.perform(Action("talk", keeper))
    game.perform(Action("desert", cult))
    assert F.membership(game.world, game.player.id, cult)[1]["status"] == "deserter"
    assert any(m.feeling == "wronged" for m in game.world.memories(keeper, about=game.player.id))
    assert keeper in leaving.town_hunters(game.world, game.player.id)
    monkeypatch.setattr(leaving, "HUNTER_CHANCE", 1.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    x, y = game.world.entity(cult).data["home"]
    events = encounters.road_encounter_events(game.world, game.player.id, game.world.entity(ensure_town(game.world, x, y, 0)))
    assert events and events[0].data["kind"] == "sect_hunter"
    assert not encounters.talk_succeeds(game.world, events[0].actors[1], game.player.id, "sect_hunter")


def test_a_release_by_final_duty(game):
    sect, seat = member_of(game, "orthodox_sect")
    go(game, seat)
    game.perform(Action("talk", halls.keeper_at(game.world, sect, seat)))
    game.perform(Action("release_duty", sect))
    duty = game.world.entity(game.player.data["duty"])
    assert duty.data["release"] is True
    go(game, duty.data["town"]) if duty.data.get("town") else None
    game.world.update_data(duty.id, kind="deliver", town=game.place.id)
    game.perform(Action("look"))
    assert F.membership(game.world, game.player.id, sect)[1]["status"] == "released"


def test_a_spy_is_found_out_when_word_reaches_the_first_faction(game):
    sect, seat = member_of(game, "orthodox_sect")
    cult, cult_seat = member_of(game, "demonic_cult", secret=True)
    go(game, seat)
    assert game.world.entity(game.player.id).data.get("summons") is None
    record_fact(game.world, game.player.id, "member_of", cult, place=seat,
                variant=make_variant("member_of", game.player.id, cult, place=game.world.entity(seat).name))
    turn = game.perform(Action("look"))
    assert F.membership(game.world, game.player.id, sect)[1]["status"] == "spy"
    assert any("spy" in text for text, _ in turn.lines)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_leaving.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.leaving'`.

- [ ] **Step 3: Write leaving** — `systems/leaving.py`
```python
"""Leaving a faction (phase 3b spec 7): release, desertion, hunters, and spies found out."""

import systems.encounters as encounters
from systems import factions as F
from systems import halls
from systems.membership import left_events
from systems.purse import payment_events
from systems.standing import believed_factions
from world.events import listen
from world.gen.materialize import ensure_region
from world.seed import rng_for

NEVER_RELEASE = frozenset({"demonic_cult", "unorthodox_clan", "bandit_fort"})
RELEASE_PER_RANK = 50
HUNTER_CHANCE = 0.2
HUNT_RANGE = 2
GONE = frozenset({"expelled", "deserter", "spy"})


def release_price(world, player: int, faction: int) -> int:
    return RELEASE_PER_RANK * (F.membership(world, player, faction)[0] + 1)


def release_events(world, player: int, faction: int, keeper: int, place: int) -> list:
    return payment_events(player, keeper, place, release_price(world, player, faction), "release") + \
        left_events(world, player, faction, place, "released")


def gone_from(world, player: int) -> list[int]:
    return [fid for fid, _, data in F.memberships(world, player) if data.get("status") in GONE]


def _staff_everywhere(world, faction: int) -> list[int]:
    data = world.entity(faction).data
    out = []
    for town in [data.get("seat"), *data.get("branches", [])]:
        if town:
            out += halls.staff_at(world, faction, town)
    return out


def _wrong_them(world, event, event_id: int) -> None:
    for person in _staff_everywhere(world, event.data["faction"]):
        world.add_memory(person, event_id, "wronged", 0.8, ignore_existing=True)


for _kind in ("expelled", "deserted", "spy_exposed"):
    listen(_kind)(_wrong_them)


def town_hunters(world, player: int) -> set[int]:
    """Members of factions the player betrayed: in town they call the player out like avengers."""
    out: set[int] = set()
    for faction in gone_from(world, player):
        out |= set(F.members_of(world, faction))
    return out


def hunter_encounter(world, player: int, town, rng):
    """A disciple sent after a deserter or spy, on the roads near the faction's home."""
    for faction in gone_from(world, player):
        home = world.entity(faction).data["home"]
        if F.gap(home, (town.data["x"], town.data["y"])) > HUNT_RANGE:
            continue
        if rng_for(world.world_seed, f"hunter:{faction}:{player}:{world.time}").random() >= HUNTER_CHANCE:
            continue
        pool = halls.staff_at(world, faction, halls.seat_of(world, faction), roles=("disciple", "elder"))
        if not pool:
            continue
        hunter = rng_for(world.world_seed, f"hunter-who:{faction}:{world.time}").choice(sorted(pool))
        return encounters.encounter_events(player, hunter, town.id, "sect_hunter", 0,
                                           {"faction_name": world.entity(faction).name})
    return None


def spy_checks(world, player: int, place: int) -> list:
    """A faction that hears the player belongs to a rival martial faction casts them out as a spy."""
    mine = [fid for fid, _, data in F.memberships(world, player) if data.get("status", "member") == "member"]
    events = []
    for faction in mine:
        kind = world.entity(faction).data["type"]
        if kind not in F.MARTIAL and kind != "imperial":
            continue
        heard = believed_factions(world, faction, player)
        for other in mine:
            if other == faction or other not in heard:
                continue
            other_kind = world.entity(other).data["type"]
            if (kind in F.MARTIAL and other_kind in F.MARTIAL) or (kind == "imperial" and other_kind in F.DARK):
                events += left_events(world, player, faction, place, "spy")
                break
    return events


encounters.HUNTER_HOOKS.append(town_hunters)
encounters.ROAD_HOOKS.append(hunter_encounter)
```

- [ ] **Step 4: Write the leaving mixin** — `engine/leaving.py`
```python
"""Leaving factions in the engine (phase 3b spec 7)."""

import systems.duties as duties
import systems.leaving as leaving
from engine.actions import Action, Choice
from systems import factions as F
from systems import halls
from systems.membership import left_events
from systems.purse import silver_of


class LeavingMixin:
    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        me = self.player.id
        for fid in halls.recruits_for(self.world, npc.id):
            found = F.membership(self.world, me, fid)
            if not found or found[1].get("status", "member") != "member":
                continue
            if self.world.entity(fid).data["type"] not in leaving.NEVER_RELEASE:
                price = leaving.release_price(self.world, me, fid)
                options.append(Choice(f"Ask for release ({price} silver)", Action("release", fid)))
                if duties.open_duty(self.world, me) is None:
                    options.append(Choice("Ask for release by a final duty", Action("release_duty", fid)))
            options.append(Choice(f"Desert the {self.world.entity(fid).name}", Action("desert", fid)))
        return options

    def _member_here(self, faction_id) -> bool:
        found = F.membership(self.world, self.player.id, faction_id)
        return bool(found and found[1].get("status", "member") == "member" and self.focus is not None
                    and faction_id in halls.recruits_for(self.world, self.focus))

    def _do_release(self, faction_id):
        if not self._member_here(faction_id) or self.world.entity(faction_id).data["type"] in leaving.NEVER_RELEASE:
            return self._turn([("They will not release you.", "system")])
        price = leaving.release_price(self.world, self.player.id, faction_id)
        if silver_of(self.world, self.player.id) < price:
            return self._turn([(f"Release costs {price} silver.", "system")])
        self.submenu = None
        return self._turn(self._commit(leaving.release_events(self.world, self.player.id, faction_id, self.focus, self.place.id)))

    def _do_release_duty(self, faction_id):
        if not self._member_here(faction_id) or self.world.entity(faction_id).data["type"] in leaving.NEVER_RELEASE:
            return self._turn([("They will not release you.", "system")])
        if duties.open_duty(self.world, self.player.id) is not None:
            return self._turn([("Finish your current duty first.", "system")])
        self.submenu = None
        return self._turn(self._commit(duties.issue_events(self.world, self.player.id, faction_id, self.focus,
                                                           self.place.id, release=True)))

    def _do_desert(self, faction_id):
        found = F.membership(self.world, self.player.id, faction_id)
        if not found or found[1].get("status", "member") != "member":
            return self._turn([("You are not one of them.", "system")])
        self.submenu, self.focus = None, None
        return self._turn(self._commit(left_events(self.world, self.player.id, faction_id, self.place.id, "deserter")))

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        for event in events:
            if event.kind == "duty_done" and event.data.get("release"):
                lines += self._commit(left_events(self.world, self.player.id, event.data["faction"], self.place.id, "released"))
        return lines

    def _spy_check(self) -> list:
        events = leaving.spy_checks(self.world, self.player.id, self.place.id)
        return self._commit(events) if events else []

    def _after_look(self) -> list:
        return super()._after_look() + self._spy_check()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._spy_check()
```

- [ ] **Step 5: Edit the existing files** — `.patches/3b_task8.py`
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
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8").rstrip("\n") + "\n" + text, encoding="utf-8", newline="\n")


ENC = "systems/encounters.py"
edit(ENC, '''ROAD_HOOKS: list = []       # fn(world, player, town, rng) -> events or None; tried before the normal roll (phase 3b)
''', '''ROAD_HOOKS: list = []       # fn(world, player, town, rng) -> events or None; tried before the normal roll (phase 3b)
HUNTER_HOOKS: list = []     # fn(world, player) -> ids who, in town, call the player out like avengers (phase 3b)
UNTALKABLE = frozenset({"sect_hunter", "bounty_hunter"})
''')
edit(ENC, '''    avengers = set(avengers_for(world, player))''',
     '''    avengers = set(avengers_for(world, player)).union(*(hook(world, player) for hook in HUNTER_HOOKS))''')
edit(ENC, '''    entity = world.entity(person)
    if entity.data.get("beast"):
        return False
    rng = rng_for(world.world_seed, f"roadtalk:{person}:{world.time}")''', '''    entity = world.entity(person)
    if entity.data.get("beast") or kind in UNTALKABLE:
        return False
    rng = rng_for(world.world_seed, f"roadtalk:{person}:{world.time}")''')

RT = "narrate/road_text.py"
edit(RT, '''        "avenger": f'{cap(name)} steps into the road. "You killed my {d.get("role") or "kin"}."',
    }[d["kind"]]''', '''        "avenger": f'{cap(name)} steps into the road. "You killed my {d.get("role") or "kin"}."',
        "sect_hunter": f"{cap(name)}, sent by the {d.get('faction_name', 'sect')}, steps into the road.",
        "bounty_hunter": f"{cap(name)}, a bounty hunter, blocks the road. There is a price on your head.",
    }[d["kind"]]''')
append("narrate/grammar/roads.toml", '''
["encounter.sect_hunter"]
colour = "default"
lines = ["#roadside# #bravado#", "#bravado# #roadside#"]

["encounter.bounty_hunter"]
colour = "default"
lines = ["#roadside# #bravado#", "#bravado# #roadside#"]
''')

GAME = "engine/game.py"
edit(GAME, "from engine.politics import PoliticsMixin\n", "from engine.politics import PoliticsMixin\nfrom engine.leaving import LeavingMixin\n")
edit(GAME, "DutiesMixin, PoliticsMixin,", "DutiesMixin, PoliticsMixin, LeavingMixin,")
print("task 8 edits applied")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task8.py && .venv/Scripts/python.exe -m pytest tests/test_leaving.py -q -p no:cacheprovider`
Expected: `task 8 edits applied`, then `5 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 7: Commit**

Run: `git add -A && git commit -m "feat: release, desertion, hunters and spies"`

---

### Task 9: Law: bounties, arrest and bounty hunters

**Files:**
- Create: `systems/law.py`, `engine/law.py`, `narrate/law_text.py`, `narrate/grammar/law.toml`
- Modify (via `.patches/3b_task9.py`): `systems/membership.py` (imperial eligibility uses the bounty), `engine/game.py` (mixin order), `narrate/outcomes.py`
- Test: `tests/test_law.py`

**Interfaces:**
- Consumes: 3a `true_identity`, `identities`, `is_bandit` and `flee_succeeds`, Task 1 (`F.DARK`, `F.gap`, `ensure_roster`, `members_of`), Task 6 (`ROAD_HOOKS`), and `make_roamer`, `_free_roamer_slot`, `region_danger`, `encounter_events`.
- Produces:
  - `systems.law`:
    - Constants: `FINE_PER = 20`, `WANTED = 30`, `HUNTED = 50`, `ARREST_CHANCE = 0.4`, `HUNTER_CHANCE = 0.2`.
    - Bounties: `crimes(world, town, subject) -> list[(fact_id, weight)]`, `bounty(world, town, subject) -> int` (0 below `WANTED`).
    - Arrest: `constable_here(world, town, player) -> int | None`, `arrest_events(world, player, town) -> list[Event]`, `fine_events`, `jail_events`, `escape_events`.
    - Road: `bounty_hunter_encounter(world, player, town, rng)` (a `ROAD_HOOKS` entry).
  - Player data: `atoned` (fact ids), and `arrest = {constable, bounty, facts}` or None.
  - Events: `arrest`, `fined`, `jailed`, `escaped_arrest`.
  - `engine.law.LawMixin`: the verb `arrest` (pay, jail, fight, flee). It gates actions and survives reload.

- [ ] **Step 1: Write the failing test** — `tests/test_law.py`
```python
import pytest

import systems.encounters as encounters
import systems.law as law
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.membership import refusal
from systems.purse import silver_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def killed_here(game, n=1):
    for i in range(n):
        victim = game.world.add_entity("person", f"Hu Mei{i}", {"realm": "mortal", "occupation": "innkeeper"})
        record_fact(game.world, game.player.id, "killed", victim, place=game.place.id,
                    variant=make_variant("killed", game.player.id, victim, place=game.place.name))


def constable(game):
    bureau = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "imperial")
    pid = game.world.add_entity("person", "Law Bao", {"realm": "third-rate", "occupation": "constable",
                                                      "traits": ["honest", "proud"]})
    game.world.relate(pid, game.place.id, "located_in")
    game.world.relate(pid, bureau, "member_of", 0, {"role": "member", "status": "member"})
    return pid


def test_a_killing_puts_a_price_on_your_head_in_towns_that_heard(game):
    assert law.bounty(game.world, game.place.id, game.player.id) == 0
    killed_here(game)
    assert law.bounty(game.world, game.place.id, game.player.id) == round(20 * 3 * 0.85)


def test_robbing_a_bandit_is_no_crime(game):
    bandit = game.world.add_entity("person", "Ma Bo", {"realm": "mortal", "occupation": "bandit"})
    record_fact(game.world, game.player.id, "robbed", bandit, place=game.place.id,
                variant=make_variant("robbed", game.player.id, bandit))
    assert law.bounty(game.world, game.place.id, game.player.id) == 0


def test_a_constable_arrests_and_a_fine_settles_it(game, monkeypatch):
    monkeypatch.setattr(law, "ARREST_CHANCE", 1.0)
    killed_here(game)
    constable(game)
    turn = game.perform(Action("look"))
    assert game.player.data["arrest"] and [c.action.verb for c in turn.choices] == ["arrest"] * 4
    game.world.update_data(game.player.id, silver=100)
    game.perform(Action("arrest", "pay"))
    assert silver_of(game.world, game.player.id) == 100 - 51
    assert law.bounty(game.world, game.place.id, game.player.id) == 0 and game.player.data.get("arrest") is None


def test_serving_time_passes_days(game, monkeypatch):
    monkeypatch.setattr(law, "ARREST_CHANCE", 1.0)
    killed_here(game)
    constable(game)
    game.perform(Action("look"))
    before = game.world.time
    game.perform(Action("arrest", "jail"))
    assert game.world.time >= before + (51 // 5) * 4 and law.bounty(game.world, game.place.id, game.player.id) == 0


def test_an_arrest_survives_a_reload(game, monkeypatch):
    monkeypatch.setattr(law, "ARREST_CHANCE", 1.0)
    killed_here(game)
    constable(game)
    game.perform(Action("look"))
    path = game.world.path
    game.close()
    again = Game.load(path)
    assert [c.action.verb for c in again.look().choices] == ["arrest"] * 4
    again.close()


def test_bounty_hunters_wait_on_the_roads(game, monkeypatch):
    monkeypatch.setattr(law, "HUNTER_CHANCE", 1.0)
    killed_here(game, n=2)
    events = law.bounty_hunter_encounter(game.world, game.player.id, game.world.entity(game.place.id), None)
    assert events and events[0].data["kind"] == "bounty_hunter"


def test_the_bureau_refuses_the_wanted(game):
    bureau = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "imperial")
    game.world.update_data(game.player.id, realm="third-rate")
    assert refusal(game.world, game.player.id, bureau, game.place.id) is None
    killed_here(game)
    assert refusal(game.world, game.player.id, bureau, game.place.id) is not None  # distrusted, or not clean
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_law.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.law'`.

- [ ] **Step 3: Write the law** — `systems/law.py`
```python
"""The law (phase 3b spec 8): bounties from what a town believes, arrest, and bounty hunters."""

import systems.encounters as encounters
from systems import factions as F
from systems.attitude import is_bandit
from systems.beliefs import identities, true_identity
from systems.purse import payment_events
from systems.realms import REALMS, realm_index
from systems.time import advance
from world.events import Event, effect
from world.gen.materialize import people_at, region_of
from world.seed import rng_for

FINE_PER, WANTED, HUNTED = 20, 30, 50
ARREST_CHANCE, HUNTER_CHANCE = 0.4, 0.2
ALLIANCE_RANGE = 3
WATCHES_PER_DAY = 4


def _alliance_doubles(world, town_id: int) -> bool:
    town = world.entity(town_id).data
    return any(world.entity(f).data["type"] == "orthodox_sect"
               and F.gap(world.entity(f).data["home"], (town["x"], town["y"])) <= ALLIANCE_RANGE
               for f in F.ensure_roster(world))


def crimes(world, town_id: int, subject: int) -> list[tuple[int, float]]:
    """The crimes this town believes of `subject`, not yet atoned: (fact id, weight x confidence)."""
    true_id = true_identity(world, subject)
    seen = identities(world, town_id, true_id) if subject == true_id else {subject}
    atoned = set(world.entity(true_id).data.get("atoned", []))
    best: dict = {}
    for belief, fact in world.known_facts(town_id):
        if belief.variant.get("actor") not in seen or fact.id in atoned:
            continue
        if fact.id not in best or belief.confidence > best[fact.id][0].confidence:
            best[fact.id] = (belief, fact)
    out = []
    doubled = None
    for belief, fact in best.values():
        target = world.entity(belief.variant.get("target")) if isinstance(belief.variant.get("target"), int) else None
        weight = 0.0
        if fact.predicate in ("killed", "robbed") and target is not None and target.kind == "person" \
                and not is_bandit(target) and not target.data.get("beast"):
            weight = fact.weight
        elif fact.predicate == "crippled":
            weight = fact.weight
        elif fact.predicate == "member_of" and target is not None and target.kind == "faction" \
                and target.data["type"] in F.DARK:
            doubled = _alliance_doubles(world, town_id) if doubled is None else doubled
            weight = 1.5 * (2 if doubled else 1)
        if weight:
            out.append((fact.id, weight * belief.confidence))
    return out


def bounty(world, town_id: int, subject: int) -> int:
    amount = round(FINE_PER * sum(w for _, w in crimes(world, town_id, subject)))
    return amount if amount >= WANTED else 0


def constable_here(world, town_id: int, player: int) -> int | None:
    bureau = next((f for f in F.ensure_roster(world) if world.entity(f).data["type"] == "imperial"), None)
    members = set(F.members_of(world, bureau)) if bureau else set()
    return next((p.id for p in people_at(world, town_id, exclude=player) if p.id in members), None)


def arrest_events(world, player: int, town_id: int) -> list[Event]:
    if world.entity(player).data.get("arrest"):
        return []
    amount = bounty(world, town_id, player)
    officer = constable_here(world, town_id, player) if amount else None
    if officer is None:
        return []
    if rng_for(world.world_seed, f"arrest:{town_id}:{world.time}").random() >= ARREST_CHANCE:
        return []
    facts = [fid for fid, _ in crimes(world, town_id, player)]
    return [Event("arrest", (player, officer), town_id, {"bounty": amount, "facts": facts})]


@effect("arrest")
def _arrest(world, event) -> None:
    world.update_data(event.actors[0], arrest={"constable": event.actors[1], **event.data})


def _atone(world, player: int, facts: list[int]) -> None:
    atoned = list(world.entity(player).data.get("atoned", []))
    world.update_data(player, atoned=atoned + [f for f in facts if f not in atoned], arrest=None)


def fine_events(world, player: int, place: int) -> list[Event]:
    a = world.entity(player).data["arrest"]
    return payment_events(player, a["constable"], place, a["bounty"], "fine") + [
        Event("fined", (player, a["constable"]), place, {"bounty": a["bounty"], "facts": a["facts"]})]


def jail_events(world, player: int, place: int) -> list[Event]:
    a = world.entity(player).data["arrest"]
    return [Event("jailed", (player, a["constable"]), place, {"days": max(1, a["bounty"] // 5), "facts": a["facts"]})]


def escape_events(world, player: int, place: int) -> list[Event]:
    a = world.entity(player).data["arrest"]
    return [Event("escaped_arrest", (player, a["constable"]), place, {})]


@effect("fined")
def _fined(world, event) -> None:
    _atone(world, event.actors[0], event.data["facts"])


@effect("jailed")
def _jailed(world, event) -> None:
    _atone(world, event.actors[0], event.data["facts"])
    advance(world, event.data["days"] * WATCHES_PER_DAY)


@effect("escaped_arrest")
def _escaped(world, event) -> None:
    world.update_data(event.actors[0], arrest=None)


def bounty_hunter_encounter(world, player: int, town, rng):
    """With a price of HUNTED or more on the player here, a hunter may be waiting on the road."""
    if bounty(world, town.id, player) < HUNTED:
        return None
    if rng_for(world.world_seed, f"bounty:{player}:{world.time}").random() >= HUNTER_CHANCE:
        return None
    region = region_of(world, town.id)
    slot = encounters._free_roamer_slot(world, region)
    danger = encounters.region_danger(world.world_seed, region.data["x"], region.data["y"])
    hunter = encounters.make_roamer(world, region, "wanderer", slot, danger)
    stronger = min(len(REALMS) - 1, realm_index(world.entity(player).data.get("realm", "mortal")) + 1)
    world.update_data(hunter, realm=REALMS[stronger].label, occupation="bounty hunter")
    return encounters.encounter_events(player, hunter, town.id, "bounty_hunter", 0)


encounters.ROAD_HOOKS.append(bounty_hunter_encounter)
```

- [ ] **Step 4: Write the law mixin** — `engine/law.py`
```python
"""The law in the engine (phase 3b spec 8): arrest as a gated moment, like a challenge."""

import systems.encounters as encounters
import systems.law as law
from engine.actions import Action, Choice

LAW_VERBS = frozenset({"arrest", "help", "journal", "unknown", "ambiguous", "standing"})


class LawMixin:
    def _arrest(self):
        return self.player.data.get("arrest") if self.combat is None and self.encounter is None else None

    def _gate(self, action):
        if self._arrest() and action.verb not in LAW_VERBS:
            return self._turn([("A constable has you by the arm. Answer the charge first.", "system")])
        return super()._gate(action)

    def _special_choices(self):
        a = self._arrest()
        if a:
            return [Choice(f"Pay the fine ({a['bounty']} silver)", Action("arrest", "pay")),
                    Choice(f"Serve time ({max(1, a['bounty'] // 5)} days)", Action("arrest", "jail")),
                    Choice("Fight your way free", Action("arrest", "fight")),
                    Choice("Try to flee", Action("arrest", "flee"))], []
        return super()._special_choices()

    def _law_check(self) -> list:
        if self.combat is not None or self.encounter is not None or self.challenger is not None:
            return []
        events = law.arrest_events(self.world, self.player.id, self.place.id)
        return self._commit(events) if events else []

    def _after_look(self) -> list:
        return super()._after_look() + self._law_check()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._law_check()

    def _do_arrest(self, choice):
        a = self._arrest()
        if not a:
            return self._turn([("No one is arresting you.", "system")])
        me, place = self.player.id, self.place.id
        if choice == "pay":
            if law.silver_of(self.world, me) < a["bounty"]:
                return self._turn([(f"You don't have {a['bounty']} silver.", "system")])
            return self._turn(self._commit(law.fine_events(self.world, me, place)))
        if choice == "jail":
            return self._turn(self._commit(law.jail_events(self.world, me, place)))
        if choice == "flee" and encounters.flee_succeeds(self.world, me, a["constable"]):
            return self._turn(self._commit(law.escape_events(self.world, me, place)))
        if choice in ("fight", "flee"):
            lines = self._commit(law.escape_events(self.world, me, place))
            return self._turn(lines + self._start_duel(a["constable"], "duel", purpose={"arrest": True}))
        return self._turn([("Pay, serve, fight or flee?", "system")])
```

- [ ] **Step 5: Write the law narration** — `narrate/law_text.py`
```python
"""What the player is told about the law."""

from narrate.outcomes import cap, outcome, summary


@outcome("arrest", body_facts=False)
def _arrest(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} bars your way: there is a price of "
            f"{event.data['bounty']} silver on your head here."], {}


@outcome("fined", body_facts=False)
def _fined(world, event):
    return [f"You pay the fine of {event.data['bounty']} silver. The charges are settled."], {}


@outcome("jailed", body_facts=False)
def _jailed(world, event):
    return [f"You spend {event.data['days']} days in a cell. The charges are settled."], {}


@outcome("escaped_arrest", body_facts=False)
def _escaped(world, event):
    return [f"You break away from {world.entity(event.actors[1]).name}."], {}


@summary("arrest")
def _arrest_line(world, entry, names, place, other):
    return f"Arrested by {other} in {place}."


@summary("fined")
def _fined_line(world, entry, names, place, other):
    return f"Paid a fine of {entry.data['bounty']} silver."


@summary("jailed")
def _jailed_line(world, entry, names, place, other):
    return f"Spent {entry.data['days']} days in a cell."


@summary("escaped_arrest")
def _escaped_line(world, entry, names, place, other):
    return f"Broke away from {other}."
```

- [ ] **Step 6: Write the law grammar** — `narrate/grammar/law.toml`
```toml
[symbols]
law_grip = ["A hand closes on your arm.", "A badge is held up before your face.", "Iron manacles clink.", "The crowd draws back.", "A whistle shrills."]
law_after = ["Onlookers whisper.", "Someone spits in the dust.", "The street goes quiet.", "A child points.", "Doors close along the street."]
law_cell = ["Straw and damp stone.", "The days crawl by.", "A guard sings off-key at night.", "Rats scratch in the dark.", "Light comes through a single slit."]

[arrest]
colour = "default"
lines = ["#law_grip# #law_after#", "#law_after# #law_grip#"]

[fined]
colour = "default"
lines = ["#law_after# #law_grip#", "#law_after#"]

[jailed]
colour = "default"
lines = ["#law_cell# #law_after#", "#law_cell#"]

[escaped_arrest]
colour = "default"
lines = ["#law_after# #law_grip#", "#law_grip#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3b_task9.py`
```python
"""Task 9 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


MEM = "systems/membership.py"
edit(MEM, '''def clean_record(world, town_id: int, player: int) -> bool:
    """No dark name here (Task 9 replaces this with the town's bounty)."""
    return reputation(world, town_id, apparent_to(world, town_id, player)).path != "ruthless"''',
     '''def clean_record(world, town_id: int, player: int) -> bool:
    """No price on the player's head in this town (phase 3b spec 8)."""
    from systems.law import bounty  # the law module comes after membership in the import graph
    return bounty(world, town_id, apparent_to(world, town_id, player)) == 0''')
edit("systems/law.py", "from systems.purse import payment_events\n", "from systems.purse import payment_events, silver_of  # noqa: F401  (used by the engine)\n")

GAME = "engine/game.py"
edit(GAME, "from engine.leaving import LeavingMixin\n", "from engine.leaving import LeavingMixin\nfrom engine.law import LawMixin\n")
edit(GAME, "PoliticsMixin, LeavingMixin,", "PoliticsMixin, LeavingMixin, LawMixin,")
edit("narrate/outcomes.py", "import narrate.politics_text  # noqa: E402,F401\n",
     "import narrate.politics_text  # noqa: E402,F401\nimport narrate.law_text  # noqa: E402,F401\n")
print("task 9 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task9.py && .venv/Scripts/python.exe -m pytest tests/test_law.py -q -p no:cacheprovider`
Expected: `task 9 edits applied`, then `7 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: bounties, arrest and bounty hunters"`

---

### Task 10: The standing page (F6) and faction facts for the narrator

**Files:**
- Create: `engine/standing_page.py`
- Modify (via `.patches/3b_task10.py`): `engine/game.py` (the verb `standing`), `engine/commands.py`, `app.py` (F6), `narrate/brief.py` (faction facts)
- Test: `tests/test_standing_page.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `engine.standing_page.known_factions(world, player, town) -> list[int]`.
  - `engine.standing_page.standing_lines(world, player, town) -> list[Line]`.
  - `engine.standing_page.faction_facts(world, player, other) -> list[str]`, which gives at most 2 facts.
  - The game verb `standing`, reached by the typed `standing` or `factions` and by F6. It returns the page as the turn's lines.

- [ ] **Step 1: Write the failing test** — `tests/test_standing_page.py`
```python
import pytest

from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from engine.standing_page import faction_facts, known_factions, standing_lines
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def join_first_sect(game):
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.relate(game.player.id, sect, "member_of", 1, {
        "role": "member", "hall": 0, "sponsor": halls.elders(game.world, sect)[0], "merit": 40, "secret": False,
        "joined_at": 0, "status": "member", "judged": [], "stipend_at": 0})
    return sect, seat


def test_only_known_factions_are_listed(game):
    known = known_factions(game.world, game.player.id, game.place.id)
    assert set(known) == set(halls.halls_here(game.world, game.place.id))
    sect, _ = join_first_sect(game)
    assert sect in known_factions(game.world, game.player.id, game.place.id)


def test_the_page_shows_rank_merit_and_how_factions_see_you(game):
    sect, _ = join_first_sect(game)
    text = [t for t, _ in standing_lines(game.world, game.player.id, game.place.id)]
    name = game.world.entity(sect).name
    assert "Your factions:" in text
    assert any(t.startswith(f"  {name}: inner disciple, 40 merit") for t in text)
    assert any(t.startswith(f"  {name}: welcome") for t in text)


def test_typing_standing_and_f6_show_the_page(game, tmp_path):
    turn = game.perform(Action("standing"))
    assert turn.lines[0] == ("Your standing", "heading")
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Paged", world_seed=11)
    app.handle_key("f6", "")
    assert any("Your standing" in text for text, _ in app.log)
    app.shutdown()


def test_briefs_mention_your_rank(game):
    sect, seat = join_first_sect(game)
    facts = faction_facts(game.world, game.player.id, None)
    assert facts == [f"You are an inner disciple of the {game.world.entity(sect).name}."]
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_standing_page.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'engine.standing_page'`.

- [ ] **Step 3: Write the page** — `engine/standing_page.py`
```python
"""The standing page (F6, phase 3b spec 9): memberships, duties, how known factions see you, bounties."""

import systems.duties as duties
import systems.law as law
from narrate.base import Line
from systems import factions as F
from systems import halls
from systems.beliefs import apparent_to
from systems.standing import standing

WATCHES_PER_DAY = 4


def known_factions(world, player: int, town: int) -> list[int]:
    """Factions the player belongs to, has heard of, has met staff of, or sees a hall of here."""
    ids = [fid for fid, _, _ in F.memberships(world, player)]
    ids += halls.halls_here(world, town)
    for belief in world.beliefs(player):
        target = belief.variant.get("target")
        if isinstance(target, int) and (entity := world.entity(target)) is not None and entity.kind == "faction":
            ids.append(target)
    for other in world.acquaintances(player):
        ids += [fid for fid, _, data in F.memberships(world, other) if data.get("status", "member") == "member"]
    return list(dict.fromkeys(i for i in ids if world.entity(i) is not None and world.entity(i).kind == "faction"))


def _article(text: str) -> str:
    return ("an " if text[:1] in "aeiou" else "a ") + text


def faction_facts(world, player: int, other) -> list[str]:
    """Up to two short facts for a brief: the player's rank, and the other person's faction."""
    facts = []
    for fid, rank, data in F.memberships(world, player):
        if data.get("status", "member") == "member":
            facts.append(f"You are {_article(F.title(world, fid, rank))} of the {world.entity(fid).name}.")
            break
    if other is not None and not other.data.get("is_player"):
        town = next(iter(world.targets(other.id, "located_in")), None)
        tag = halls.faction_tag(world, other.id, town) if town else None
        if tag:
            facts.append(f"{other.name} is of the {tag}.")
    return facts[:2]


def standing_lines(world, player: int, town: int) -> list[Line]:
    lines: list[Line] = [("Your standing", "heading"), ("Your factions:", "heading")]
    mine = [(fid, rank, data) for fid, rank, data in F.memberships(world, player)]
    if not mine:
        lines.append(("  none", "dim"))
    for fid, rank, data in mine:
        name = world.entity(fid).name
        status = data.get("status", "member")
        if status != "member":
            lines.append((f"  {name}: {status}", "red"))
            continue
        sponsor = world.entity(data["sponsor"]).name if data.get("sponsor") else "none"
        secret = " (secret)" if data.get("secret") else ""
        lines.append((f"  {name}: {F.title(world, fid, rank)}, {data.get('merit', 0)} merit, sponsor {sponsor}{secret}", "dim"))
    duty = duties.open_duty(world, player)
    if duty is not None:
        days = max(0, (duty.data["deadline"] - world.time) // WATCHES_PER_DAY)
        lines.append((f"  Open duty: {duty.data['kind']} for the {world.entity(duty.data['faction']).name}, {days} days left", "dim"))
    trial = world.entity(player).data.get("trial")
    if trial:
        lines.append((f"  Trial: the {world.entity(trial['faction']).name} ({trial['kind']})", "dim"))
    lines += [("", "default"), ("How factions see you:", "heading")]
    for fid in known_factions(world, player, town):
        view = standing(world, fid, apparent_to(world, town, player))
        why = f" ({view.reasons[0]})" if view.reasons else ""
        lines.append((f"  {world.entity(fid).name}: {view.word}{why}", "dim"))
    lines += [("", "default"), ("Bounties:", "heading")]
    here = law.bounty(world, town, apparent_to(world, town, player))
    lines.append((f"  Here: {here} silver" if here else "  none here", "red" if here else "dim"))
    rivals = world.entity(player).data.get("rivals") or {}
    if rivals:
        lines += [("", "default"), ("Rivals:", "heading")]
        for fid, rival in rivals.items():
            lines.append((f"  {world.entity(rival).name} of the {world.entity(int(fid)).name}", "dim"))
    return lines
```

- [ ] **Step 4: Edit the existing files** — `.patches/3b_task10.py`
```python
"""Task 10 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


GAME = "engine/game.py"
edit(GAME, "from engine.law import LawMixin\n", "from engine.law import LawMixin\nfrom engine.standing_page import standing_lines\n")
edit(GAME, '''    def _do_help(self, _target) -> Turn:''', '''    def _do_standing(self, _target) -> Turn:
        return self._turn(standing_lines(self.world, self.player.id, self.place.id))

    def _do_help(self, _target) -> Turn:''')
edit(GAME, '''    ("  news | ask about <name> | tell | rumours | wear mask | remove mask", "system"),''',
     '''    ("  news | ask about <name> | tell | rumours | wear mask | remove mask | standing (F6)", "system"),''')
edit("engine/commands.py", '''    "tell": Action("tell_menu"),''', '''    "tell": Action("tell_menu"), "standing": Action("standing"), "factions": Action("standing"),''')
edit("app.py", '''        elif key == "f4":''', '''        elif key == "f6":
            self.submit("standing")
        elif key == "f4":''')
BRIEF = "narrate/brief.py"
edit(BRIEF, '''    if event.kind in OUTCOME_BUILDERS:
        more, extra = OUTCOME_BUILDERS[event.kind](world, event)''', '''    from engine.standing_page import faction_facts  # the page owns the wording (phase 3b)
    facts = facts + [f for f in faction_facts(world, player.id, other) if f not in facts]
    if event.kind in OUTCOME_BUILDERS:
        more, extra = OUTCOME_BUILDERS[event.kind](world, event)''')
print("task 10 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task10.py && .venv/Scripts/python.exe -m pytest tests/test_standing_page.py -q -p no:cacheprovider`
Expected: `task 10 edits applied`, then `4 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass, and briefs still hold at most 6 facts (they are cut at `MAX_FACTS`).

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: the standing page (F6) and faction facts for the narrator"`

---

### Task 11: Faction rules, a sect-life fuzz run, speed, docs

**Files:**
- Modify (via `.patches/3b_task11.py`): `debug/invariants.py`, `tests/test_fuzz.py`, `docs/debugging.md`
- Test: `tests/test_faction_rules.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `debug.invariants.check_factions(world) -> list[str]`, called from `check_world`. The `check_people` rule gains faction names. Adds the fuzz test `test_a_sect_life`.

- [ ] **Step 1: Write the failing test** — `tests/test_faction_rules.py`
```python
import time

import pytest

from debug.invariants import check_factions, check_people, check_world
from engine.actions import Action, Turn
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.gen.materialize import ensure_town
from world.gen.region import region_spec


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def test_a_clean_world_breaks_no_faction_rule(game):
    assert check_factions(game.world) == []


def test_two_open_martial_memberships_are_caught(game):
    ids = [i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] in ("orthodox_sect", "demonic_cult")]
    for fid in ids[:2]:
        game.world.relate(game.player.id, fid, "member_of", 0, {"role": "member", "status": "member", "secret": False, "merit": 0})
    assert any("martial" in p for p in check_factions(game.world))


def test_a_lopsided_stance_is_caught(game):
    a, b = F.ensure_roster(game.world)[:2]
    game.world.relate(a, b, "stance", 0.9)
    assert any("stance" in p for p in check_factions(game.world))


def test_naming_an_unheard_of_faction_is_caught(game):
    far = next(i for i in F.ensure_roster(game.world)
               if i not in halls.halls_here(game.world, game.place.id) and game.world.entity(i).data["type"] == "demonic_cult")
    turn = Turn([(f"The {game.world.entity(far).name} sends its regards.", "npc")], [], {}, "")
    assert any("faction" in p for p in check_people(game, turn))


def test_a_world_full_of_factions_stays_quick(game):
    for x in range(-2, 3):
        for y in range(-2, 3):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                halls.settle_town(game.world, ensure_town(game.world, x, y, i))
    assert len(game.world.entities("faction")) >= 12
    check_world(game.world)
    start = time.perf_counter()
    turn = game.perform(Action("look"))
    check_world(game.world)
    check_people(game, turn)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.15, f"a turn and its checks took {elapsed * 1000:.0f} ms"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_faction_rules.py -q -p no:cacheprovider`
Expected: the collection error `ImportError: cannot import name 'check_factions' from 'debug.invariants'`.

- [ ] **Step 3: Edit the rules, the fuzz test and the docs** — `.patches/3b_task11.py`
```python
"""Task 11 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


INV = "debug/invariants.py"
edit(INV, '''    problems += check_knowledge(world)
''', '''    problems += check_knowledge(world)
    problems += check_factions(world)
''')
edit(INV, '''def check_people(game, turn) -> list[str]:''', '''def check_factions(world) -> list[str]:
    """Memberships, ranks, merit, duties and stances stay consistent (phase 3b spec 10)."""
    from systems import factions as F  # factions import the knowledge layer, which imports this module's peers
    out = []
    player = world.get_meta("player_id")
    for faction in world.entities("faction"):
        for other, value, _ in world.relations_from(faction.id, "stance"):
            if not -1 <= value <= 1 or abs(F.stance(world, other, faction.id) - value) > 1e-9:
                out.append(f"stance between #{faction.id} and #{other} is lopsided or out of range")
    for person_id in [player] if player is not None else []:
        rows = F.memberships(world, person_id)
        open_martial = [fid for fid, _, d in rows if d.get("status", "member") == "member" and not d.get("secret")
                        and world.entity(fid).data["type"] in F.MARTIAL]
        if len(open_martial) > 1:
            out.append(f"the player openly belongs to {len(open_martial)} martial factions")
        for fid, rank, data in rows:
            if world.entity(fid) is None or world.entity(fid).kind != "faction":
                out.append(f"membership points at #{fid}, which is no faction")
            if not 0 <= rank <= 3:
                out.append(f"the player holds rank {rank} in #{fid}")
            if data.get("merit", 0) < 0:
                out.append(f"negative merit in #{fid}")
    for duty in world.entities("duty"):
        if duty.data.get("status") != "open":
            continue
        holder = world.entity(duty.data["holder"])
        if holder is None or holder.data.get("dead") or holder.data.get("duty") != duty.id:
            out.append(f"open duty #{duty.id} has no living holder")
        target = duty.data.get("target")
        if target is not None and world.entity(target) is None:
            out.append(f"open duty #{duty.id} points at missing #{target}")
    return out


def check_people(game, turn) -> list[str]:''')
edit(INV, '''    for kind in ("person", "persona"):
        for entity in world.entities(kind):
            name = entity.name.lower()
            if name in known or len(name) < 4:
                continue
            if re.search(rf"(?<![\\w-]){re.escape(name)}(?![\\w-])", text):
                out.append(f"{entity.name} (#{entity.id}) is named on screen but the player never heard of them")
    return out''', '''    for kind in ("person", "persona"):
        for entity in world.entities(kind):
            name = entity.name.lower()
            if name in known or len(name) < 4:
                continue
            if re.search(rf"(?<![\\w-]){re.escape(name)}(?![\\w-])", text):
                out.append(f"{entity.name} (#{entity.id}) is named on screen but the player never heard of them")
    from engine.standing_page import known_factions  # the page decides which factions the player knows
    town = here[0] if here else None
    heard = set(known_factions(world, player_id, town)) if town is not None else set()
    heard_names = {world.entity(f).name.lower() for f in heard}  # minor factions far apart can share a name
    for faction in world.entities("faction"):
        if faction.name.lower() not in heard_names and faction.name.lower() in text:
            out.append(f"the faction {faction.name} is named on screen but the player never heard of it")
    return out''')

FUZZ = "tests/test_fuzz.py"
Path(FUZZ).write_text(Path(FUZZ).read_text(encoding="utf-8") + '''

@pytest.mark.parametrize("seed", [8, 17])
def test_a_sect_life(tmp_path, seed, monkeypatch):
    """Join a sect, take duties, rise, travel, fight, get framed or arrested: every rule holds."""
    from systems import halls
    from systems import factions as F
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 1.5)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Disciple{seed}", world_seed=seed)
    world, me = app.game.world, app.game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    with world.transaction():
        world.unrelate(me, "located_in")
        world.relate(me, seat, "located_in")
        world.update_data(me, silver=300)
    app.submit("look")
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["kill", "1", "2", "3", "4"]))
        elif game.player.data.get("summons") or game.player.data.get("arrest"):
            app.submit(rng.choice(["1", "2", "3", "4"]))
        elif game.focus is not None:
            app.submit(rng.choice(["1", "2", "3", "4", "5", "6", "7", "8", "9", "bye"]))
        else:
            app.submit(rng.choice(["1", "2", "3", "4", "look", "standing", "rest", "go north", "go south",
                                   "go east", "go west", "journal"]))
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()
''', encoding="utf-8", newline="\n")

edit("docs/debugging.md", '''- **Names on screen:**''', '''- **Factions (phase 3b):** stances are symmetric and in -1..1; the player openly belongs to at most one martial faction, holds rank 0-3 and never negative merit; every open duty has a living holder whose duty it is, and a target that exists. Faction names on screen are ones the player knows (a membership, a hall here, a rumour, or staff they have met).
- **Names on screen:**''')
print("task 11 edits applied")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3b_task11.py && .venv/Scripts/python.exe -m pytest tests/test_faction_rules.py -q -p no:cacheprovider`
Expected: `task 11 edits applied`, then `5 passed`.

Run: `.venv/Scripts/python.exe -m pytest tests/test_fuzz.py -q -p no:cacheprovider`
Expected: every fuzz test passes, including `test_a_sect_life[8]` and `[17]`. If a rule fires, treat each violation as a bug and find its cause with systematic debugging. Do not loosen the rule.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "test: faction rules, sect-life fuzz, speed with many factions"`

---

## Self-review

**Spec coverage:**

| Spec section | Where it is built |
|---|---|
| §2 storage (no schema change) | Everywhere: entities, relations, facts and beliefs only |
| §3.1 roster, homes, seats, branches, stances | Tasks 1 and 2 |
| §3.2 minor factions | Task 1, with seats in Task 2 |
| §3.3 members (staff and natural) | Task 2 |
| §3.4 standing, and the attitude term for enemies by association | Task 3 |
| §4 joining, eligibility, trials, secret joining, arts and library | Task 4, with arts and library in Task 5 |
| §5 ranks, promotion, stipend, duties | Task 5 (ranks) and Task 6 (duties) |
| §6.1 halls and sponsor, gifts | Tasks 2, 4 and 5 |
| §6.2 rival and framing | Task 7 |
| §6.3 taboos and judgement | Task 7 |
| §6.4 exposing the rival | Task 7 |
| §7 release, desertion, spying, side ties | Task 8 (side ties are allowed by `open_martial` and `refusal` in Task 4) |
| §8 law | Task 9 |
| §9 F6 page, scenes, conversation, briefs, events | Tasks 2 and 10 for screens; each task narrates its own events |
| §10 debug rules | Task 11 |
| §11 tests | Every task, with fuzz and speed in Task 11 |

**Differences from the spec (beyond the plan-time rulings above):**
- A cult's blood-proof target is a resident of the cult's home region, not a hostile faction's member within 2 regions. It is simpler, and just as sinister.
- A guild escort trial is "reach the town"; the escort *duty* also doubles road encounters.
- Duties complete by themselves when their condition is met. There is no report step. This extends ruling 2 to all duty kinds.
- The rival's identity becomes known through judgement: a successful denial lets the elder reveal who spread the charge, which unlocks *Expose*. This reads the elder's knowledge (the liar told them), not ground truth.
- Faction knowledge excludes members' personal beliefs (ruling 1). NPC-to-NPC enemies by association runs through 3a attitude.

**Dry run:** before handing this plan over, all 11 tasks' files and patch scripts were applied in order to a scratch copy of `4b115eb`, and the full suite ran: 427 passed (348 existing + 79 new), including the 4 new fuzz runs. That run found and fixed:
- test helpers that assumed every faction has elders;
- a Task 2 test that stopped being true once Task 3 added the menu;
- the busy-town test assuming at most 8 people (a ruling in the Task 2 patch);
- the rival's grudge call-outs pre-empting summons in the politics tests (the tests now disable random challenges);
- far-apart minor factions sharing a name, which tripped the faction-name rule (it now compares names);
- standing-page lines using the prose colour.

**Type consistency:**
- Membership data keys: `role, hall, sponsor, merit, secret, joined_at, status, judged, stipend_at`.
- `left_events(world, person, faction, place, status)`.
- `issue_events(world, player, faction, keeper, place, kind=None, release=False)`.
- Encounter hooks are `(world, player, town, rng)`.
- `standing(world, faction, subject) -> Standing`.
- The faction-menu hook is `_faction_options(npc) -> list[Choice]`, chained through every mixin.

**Review Focus coverage:**
- Item 1: `test_a_dead_target_fails_the_duty` (Task 6).
- Item 2: `test_an_overdue_duty_fails_once` (Task 6).
- Item 3: `test_a_summons_survives_a_reload` (Task 7) and `test_an_arrest_survives_a_reload` (Task 9).
- Item 4: `test_an_old_save_gets_factions_on_load` (Task 2).
- Item 5: `test_the_conversation_menu_stays_within_nine` (Task 2).
