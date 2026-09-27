# Phase 5c: The Alchemy World Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The world practises alchemy around the player: sects keep pill halls and herb gardens, an Alchemists' Guild ranks alchemists by examination, recipes are bought, taught, sold and stolen, physicians and famous doctors heal, NPCs refine and take pills in their seasons, and control pills bind servants to masters, the player among them.

**Architecture:**
- **Numbers until touched.** A sect's hall and garden, an NPC's pills and the world's bindings are counts and seeds on existing entities. Pills, herbs and scrolls become entities only when the player draws, harvests, steals, buys, robs, inherits or is taught them. Every read is pure: a garden or an own sect's hall is brought forward from its last stored season when asked, and stored only when something is taken.
- **Each concern is its own module:** `pill_hall` (halls, gardens, the own sect's buildings), `guild` (ranks and examinations), `recipe_trade` (scrolls), `hall_theft` (theft by night), `physic` (physicians, doctors, healing, contracts), `npc_alchemy` (a lives agenda), `control` (control pills). The player's side is `AlchemyWorldMixin` (`engine/alchemy_world.py`) with its pages in `engine/alchemy_world_page.py`.
- **The Guild is no faction** (ruling 1): a branch in every city and a `guild_rank` on each alchemist.

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-phase5c-alchemy-world-design.md`

## Global Constraints

- **Save format:** no save-format version change. New state lives in:
  - faction data `pill_hall`, `pill_hall_at`, `garden`, and 3c's `buildings` (`herb_garden`, `pill_hall`);
  - person data `guild_rank`, `guild_exam_season`, `harvested`, `surveyed`, `guardian_beaten`, `doctors_seen`, `go_won`, `healings`, `patient`, `contract`, `pills`, `bound_to`, `served_month`;
  - `scroll` entities; the persons `physician:{town}`, `doctor:{bx}:{by}` and `patient:...`;
  - the meta row `bound`.
- **Knowledge vs truth:**
  - a hall and garden are shown to their sect's own, or to a thief after a look by night;
  - a Guild rank is known once its fact is heard; an NPC alchemist's is told when you talk shop with them;
  - a famous doctor is known by the rumour `doctor_seen`, and where they were seen goes stale;
  - nobody is named on screen before the player has met or heard of them (`check_people`).
- **Reads never write:** pages, briefs, choices and blocks never make a person, a pill, a herb or a scroll. The physician is made when first paid; a doctor when first asked after.
- **One effect per event kind:** new modules `@listen` or register hooks. Existing effects are never re-registered.
- **Seeded rolls stay where they were:**
  - new rolls use their own seeded streams (`pill_hall:`, `garden:`, `guild:`, `theft:`, `npc_alchemy:`, `world_bind:` and the like), never the life clock's shared season stream;
  - no occupation, duty kind or recipe is added to a table that seeded choices read (rulings 3, 7, 17).
- **Speed (CPU time, averaged after `gc.collect()`):**
  - a season of 200 NPCs with the alchemy agendas stays within +10% of 5b's season;
  - the pill hall, Guild, clinic and night menus are each under 20 ms;
  - the 500-year soak keeps its limits.
- **Commits:** every commit message ends with the session's Co-Authored-By attribution line.

## Review Focus

1. **Reads never write:** a hall's table, a garden's growth and the menus that show them change nothing, and the physician is made only when paid. Task 1 pins it with `test_reading_a_hall_or_a_garden_writes_nothing`; Task 4 with `test_the_physician_hastens_a_wound_threefold_for_silver`.
2. **No one is named before they are known:** the physician is an actor in what they do, and a doctor is heard of before their name is shown (ruling 11). Task 4 pins it with `test_a_doctor_wanders_their_block_and_is_made_on_the_first_ask`; every fuzz run checks it on each screen.
3. **The worms at a turn's end:** a player unfed for ninety days dies when the turn is done, laid at the master's door. Task 6 pins it with `test_the_bound_are_harmed_each_day_unfed_and_die_after_ninety`; Task 7 with `test_bound_to_a_master_the_sheet_says_so_and_the_worms_kill_the_unfed`.
4. **A season of NPC alchemy stays cheap:** within +10% of 5b's season for 200 NPCs, and the 500-year soak keeps its limits. Task 8 pins it with `test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5bs`.
5. **Random play through the Guild, the halls, theft, healing and the worms:** no crash, no rule broken. Task 8 pins it with `test_a_wandering_physician`.

## Plan-time rulings (deviations from the spec, argued)

1. **The Guild is no faction of the roster.** A faction entity would be staffed, drift and go to war on the world clock, and every rule that reads `member_of` would read it. A person's `guild_rank` (0 once joined) and the fact `guild_rank` carry it all. *Cost if wrong:* the Guild is not listed on the standing page.
2. **A recipe's grade follows its potency:** 4 or less is grade 1, 6 or less grade 2, more grade 3; the control pill is grade 4. An examination for rank r asks a recipe of grade `min(3, ceil(r / 2))`, since the base recipes stop at grade 3. *Cost if wrong:* ranks 7-9 ask a grade-3 recipe and a good roll, no more.
3. **Alchemists are herbalists by trade and the sects' pill masters** (a hall keeper at a seat whose sect keeps a hall). Adding "alchemist" or "physician" to the occupations would reshuffle every seeded person in every world. *Cost if wrong:* none.
4. **Every staffed sect keeps a hall and a garden but a bandit fort** (the spec's "bandit-like clans"). *Cost if wrong:* none.
5. **Gardens and the own sect's hall are brought forward when read.** A garden grows two a season to twelve from its last harvest, and ages over at most the last 40 seasons; the own sect's hall is filled by its alchemists over at most the last 12 seasons, to twelve pills of a grade. Nothing runs each season for them. *Cost if wrong:* none visible.
6. **The founder of the player's own sect draws and harvests without merit,** any grade. *Cost if wrong:* none.
7. **An alchemy duty is asked for by name** ("Ask for an alchemy duty", from a hall's keeper at the seat), not rolled among 3b's kinds: a seventh weight in `KIND_WEIGHTS` would reshuffle every seeded duty. It lasts 30 days and is handed in at the seat. *Cost if wrong:* none.
8. **Night is the fourth watch,** and "Wait for nightfall" gets there. The guard is the strongest of the sect at its seat, else a seeded watchman of realm 1-3. A beaten guardian stays away for a day, since the fight itself takes a watch. *Cost if wrong:* none.
9. **A caught thief commits 3b's `stole`,** so the law, the sect's standing and 5a's words hold; an unseen theft is `robbed_hall`, a fact with no actor. *Cost if wrong:* none.
10. **A sect's secret is sold to the keeper of a sect hostile to it, at its seat,** for three times the Guild's price; `sold_secret` costs 1.5 standing with the betrayed sect once it hears. *Cost if wrong:* none.
11. **The physician is made when first paid and is an actor in what they do;** menus call them "the physician". Asking after a famous doctor records the rumour `doctor_seen`, which the asker and the town hear, so the doctor is known before their name is shown. Both keep `check_people` clean. *Cost if wrong:* none.
12. **A famous doctor's cures:** every poison; every damaged or severed meridian opened; the worst permanent wound made to heal as any other. *Cost if wrong:* none.
13. **Healing another:** a fitting pill always works (healing for a wound, an antidote as strong as the worst poison); two known healing herbs (wood, earth or water, toxicity at most 1) roll `0.3 + 0.1 x alchemy level`, bounded 0.1-0.9. Five healings in a town make its healer (`healings`). *Cost if wrong:* none.
14. **Poison for hire:** bandits and members of dark sects who believe the player poisons offer a contract, once a season with chance 0.3; the mark is someone of the client's town. A hired poisoning traced (chance 0.15) is `poisoned_for_hire`, a crime like 4h's schemes (4h's `poisoner` story names a sect). A poison below grade 4 only sickens. The fee is claimed from the client. *Cost if wrong:* none.
15. **NPC pill-taking uses its own stream,** buys a grade-1 pill for 20 silver when it holds none, and a deviation from residue kills one time in ten. 4a's test of cultivation alone now holds pills aside (`tests/test_lives.py`). *Cost if wrong:* none.
16. **An NPC's pills become things on a rob or kill verdict** (with the manuals, as 2b's loot does), at their stall, or when the player inherits; an NPC heir inherits the count. *Cost if wrong:* none.
17. **The control recipe lives in `systems/data/secret_recipes.toml` (`alchemy.SECRET`),** never in `recipes.toml`: 5b's test pins that table to the base recipes, and keeping it out of `RECIPES` keeps it out of `best_match`. Loading it in `alchemy` itself avoids a circular import. An unorthodox sect's secrets are the control pill and one base recipe. *Cost if wrong:* none.
18. **The player bound serves a seeded task each month** (carry a message to a town, beat a fighter in a real duel, or rob a sect unseen); refusing is not doing it. Days unfed are harmed lazily at the turn's end (`hurt_to`); after ninety the worms kill, and the death is laid at the master's door (`died` with the master as killer), so the kin grieve against them. *Cost if wrong:* none.
19. **An NPC master always feeds their bound while alive** (masters do not wander, so "absent over a season" never arises); those the player binds seek a cure with chance 0.25 a season; freeing another with a grade-5 antidote is `worms_killed`, and the freed are saved. *Cost if wrong:* none.
20. **Forcing a control pill is a crime (`enslaved`) only against the lawful** (5a's `lawful`); a bound NPC of no faction becomes the player's sworn follower (3c). *Cost if wrong:* none.
21. **An NPC alchemist's rank is told when you talk shop with them,** since NPC ranks rise without facts. *Cost if wrong:* none.
22. **New choices fold into submenus:** "Alchemy and medicine..." in conversation, "Around the halls by night..." and "Those bound to you..." in the scene, so the screens 3b-5b fill keep their shape. *Cost if wrong:* none.
23. **`stole` gains a rumour** ("X stole from the Y"), which 5a's armoury theft shares. *Cost if wrong:* none.

## Files

| File | Responsibility |
|---|---|
| `systems/pill_hall.py` | A sect's hall and garden: tables, draws, growth, harvests, the spring restock, the own sect's buildings. |
| `systems/guild.py` | The Guild: joining, examinations, ranks, NPC alchemists, the herbalist's discount. |
| `systems/recipe_trade.py` | Scrolls: reading, the Guild's sales, a sect's secrets, a master's teaching, selling a secret. |
| `systems/hall_theft.py` | Theft by night: the guard, the guardian beast, the loot, a look by night. |
| `systems/physic.py` | The physician, famous doctors, healing others, the healer's town, poison for hire. |
| `systems/npc_alchemy.py` | NPCs refine and take pills; their pills made things when taken. |
| `systems/control.py`, `systems/data/secret_recipes.toml` | Control pills: the bound, feeding, starving, freedom, the three sides. |
| `engine/alchemy_world.py`, `engine/alchemy_world_page.py` | `AlchemyWorldMixin`: choices, menus, handlers; the pages and the sheet's lines. |
| `narrate/alchemy_world_text.py`, `narrate/grammar/alchemy_world.toml` | Outcomes, journal lines, rumours. |

Existing files touched: `systems/sect.py`, `systems/world_clock.py`, `systems/alchemy.py`, `systems/herbs.py`, `systems/attitude.py`, `systems/standing.py`, `systems/duties.py`, `systems/law.py`, `systems/mortality.py`, `systems/pills.py`, `debug/invariants.py`, `engine/game.py`, `engine/commands.py`, `engine/sheet.py`, `engine/alchemy.py`, `narrate/outcomes.py`, `narrate/duty_text.py`, `docs/world-events.md`, and the test `tests/test_lives.py`.

**How each task is laid out:**
1. The tests, as whole new files.
2. The new modules, as whole files.
3. The run that shows what the edits must still do.
4. One patch script, `.patches/5c_taskN.py`, holding the task's edits to existing files (including files made by earlier tasks). Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: Pill halls and herb gardens

Each staffed sect but a bandit fort keeps a pill hall and a herb garden (ruling 4). The hall is a seeded table of pills by grade and effect, drawn from at the seat for `20 x grade` merit up to the grade a rank allows; the pill is made as it is drawn and kept on leaving, and each spring the table is its seed again. The garden is a few herbs of the seat's land that grow two a season to twelve and now and then age a grade; a member takes two a season for merit. Both are read without writing (ruling 5). The player's own sect builds a `herb_garden` and a `pill_hall`; its hall is filled by its alchemist disciples (ruling 3), and its founder takes from both for nothing (ruling 6). `check_alchemy_world` joins the rules.

**Files:**
- Create: `systems/pill_hall.py`
- Create: `tests/test_pill_hall.py`
- Modify (by `.patches/5c_task1.py`): `systems/sect.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: 3b's `factions` (`membership`, `STAFFED`), `membership.set_membership`; 3c's `sect.members`, `sect.built`, `sect.BUILDINGS`; 4a's `lives.current_season`, `world_clock.SEASON_HOOKS`; 5b's `alchemy.make_pill`, `alchemy.recipe_entity`, `herbs.growing`, `herbs.make_herb`; `world.seed.rng_for`.
- Produces:
  - `PH` (systems/pill_hall.py): `SEED`, `EFFECTS`, `BASES`, `NO_HALL`, `PURITY`, `DRAW_MERIT`, `RANK_GRADE`, `ELDER_GRADE`, `GARDEN_HERBS`, `GARDEN_START`, `GROWTH`, `GARDEN_CAP`, `AGE_CHANCE`, `TOP_AGE`, `LOOK_BACK`, `HARVEST_LIMIT`, `HARVEST_MERIT`, `OWN_HALL_CAP`, `OWN_HALL_SEASONS`, `ALCHEMIST_JOBS`; `own(world, faction)`, `keeps_hall(world, faction)`, `keeps_garden(world, faction)`, `seed_of(world, faction)`, `alchemists(world, faction)`, `table(world, faction)`, `best_grade(world, person, faction)`, `cost(world, faction, grade)`, `offers(world, person, faction)`, `draw_block(world, person, faction, grade, kind, place)`, `draw_events(world, person, faction, grade, kind, place)`, `make_hall_pill(world, person, faction, grade, kind, how)`, `season_hook(world, n)`, `garden_seed(world, faction)`, `garden(world, faction)`, `guarded(world, faction)`, `taken_this_season(world, person, faction)`, `harvest_cost(world, faction, grade)`, `harvest_block(world, person, faction, herb, place)`, `harvest_events(world, person, faction, herb, place)`, `take_from_garden(world, faction, herb, season)`; events `garden_harvested`, `pill_drawn`.
  - `sect.BUILDINGS['herb_garden']`, `sect.BUILDINGS['pill_hall']`; `debug.invariants.check_alchemy_world(world)`.

- [ ] **Step 1: Write the tests**

`tests/test_pill_hall.py`:
```python
import pytest

import systems.encounters as encounters
import systems.herbs as H
import systems.lives as lives
import systems.pill_hall as PH
import systems.sect as sect_mod
from debug.invariants import check_alchemy_world
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


def the_sect(world, kind="orthodox_sect"):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)
    return sect, halls.seat_of(world, sect)


def join(game, sect, seat, rank=1, role="disciple", merit=200):
    world, me = game.world, game.player.id
    world.relate(me, sect, "member_of", rank, {"role": role, "hall": 0, "merit": merit, "status": "member",
                                              "secret": False})
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")


def merit(world, me, sect):
    return F.membership(world, me, sect)[1]["merit"]


def test_a_great_sect_stocks_three_grades_and_a_bandit_fort_none(game):
    world = game.world
    sect, _ = the_sect(world)
    stock = PH.table(world, sect)
    by_grade = {}
    for key, count in stock.items():
        by_grade[int(key.split(":")[0])] = by_grade.get(int(key.split(":")[0]), 0) + count
    assert by_grade == PH.SEED["great"]
    assert PH.table(world, sect) == stock  # seeded: the same hall every time it is read
    fort = world.add_entity("faction", "Black Wind Fort", {"type": "bandit_fort", "tier": "minor", "seat": None})
    assert not PH.keeps_hall(world, fort)


def test_rank_caps_the_grade_and_a_draw_costs_merit(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=1)
    assert PH.best_grade(world, me, sect) == 1
    assert all(grade == 1 for grade, _ in PH.offers(world, me, sect))
    grade, kind = PH.offers(world, me, sect)[0]
    assert PH.draw_block(world, me, sect, 2, kind, seat) is not None
    before = PH.table(world, sect)[f"{grade}:{kind}"]
    commit(world, PH.draw_events(world, me, sect, grade, kind, seat))
    assert merit(world, me, sect) == 200 - PH.DRAW_MERIT * grade
    assert PH.table(world, sect).get(f"{grade}:{kind}", 0) == before - 1
    [pill] = [world.entity(i) for i in world.targets(me, "owns") if world.entity(i).kind == "pill"]
    assert pill.data["effect"] == kind and pill.data["grade"] == grade and pill.data["maker"] == sect


def test_an_elder_draws_the_third_grade_and_a_rank_nought_nothing(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=3, role="elder")
    assert PH.best_grade(world, me, sect) == PH.ELDER_GRADE
    join(game, sect, seat, rank=0)
    assert PH.best_grade(world, me, sect) is None
    assert PH.offers(world, me, sect) == []


def test_the_hall_is_drawn_from_only_at_the_seat_and_with_the_merit(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=1, merit=5)
    grade, kind = PH.offers(world, me, sect)[0]
    assert "merit" in PH.draw_block(world, me, sect, grade, kind, seat)
    assert "seat" in PH.draw_block(world, me, sect, grade, kind, seat + 100000)


def test_a_drawn_pill_is_kept_on_leaving(game):
    from systems.membership import set_membership
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=1)
    commit(world, PH.draw_events(world, me, sect, *PH.offers(world, me, sect)[0], seat))
    set_membership(world, me, sect, status="expelled")
    assert any(world.entity(i).kind == "pill" for i in world.targets(me, "owns"))
    assert not world.facts(predicate="stole")


def test_each_spring_a_drawn_hall_is_its_seed_again(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=1)
    commit(world, PH.draw_events(world, me, sect, *PH.offers(world, me, sect)[0], seat))
    assert PH.table(world, sect) != PH.seed_of(world, sect)
    PH.season_hook(world, 3)
    assert PH.table(world, sect) != PH.seed_of(world, sect)
    PH.season_hook(world, 4)
    assert PH.table(world, sect) == PH.seed_of(world, sect)


def test_a_garden_holds_herbs_of_the_seats_land_and_grows_each_season(game):
    world = game.world
    sect, seat = the_sect(world)
    grown = PH.garden(world, sect)
    terrain = world.entity(seat).data["terrain"]
    assert PH.GARDEN_HERBS[0] <= len(grown) <= PH.GARDEN_HERBS[1] or len(grown) == len(H.growing(terrain))
    assert all(terrain in H.props(name)["terrains"] for name in grown)
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {n: [1, 0] for n in grown}})
    world.set_time(world.time + 2 * lives.SEASON)
    assert all(count == 1 + 2 * PH.GROWTH for count, _ in PH.garden(world, sect).values())
    world.set_time(world.time + 20 * lives.SEASON)
    assert all(count == PH.GARDEN_CAP for count, _ in PH.garden(world, sect).values())


def test_a_garden_herb_ages_now_and_then_to_a_hundred_years_at_most(game, monkeypatch):
    world = game.world
    sect, _ = the_sect(world)
    monkeypatch.setattr(PH, "AGE_CHANCE", 1.0)
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {"ginseng": [3, 0]}})
    world.set_time(world.time + 5 * lives.SEASON)
    assert PH.garden(world, sect)["ginseng"][1] == PH.TOP_AGE
    assert PH.guarded(world, sect)


def test_a_member_harvests_two_herbs_a_season_for_merit(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=0, merit=100)
    herb = next(name for name, (count, _) in PH.garden(world, sect).items() if count > 0)
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {herb: [5, 0]}})
    for _ in range(PH.HARVEST_LIMIT):
        assert PH.harvest_block(world, me, sect, herb, seat) is None
        commit(world, PH.harvest_events(world, me, sect, herb, seat))
    assert "a season" in PH.harvest_block(world, me, sect, herb, seat)
    assert merit(world, me, sect) == 100 - 2 * PH.HARVEST_MERIT
    assert PH.garden(world, sect)[herb][0] == 3
    assert len(H.herbs_of(world, me)) == 2
    world.set_time(world.time + lives.SEASON)
    assert PH.harvest_block(world, me, sect, herb, seat) is None


def test_reading_a_hall_or_a_garden_writes_nothing(game):
    world = game.world
    sect, _ = the_sect(world)
    before = world.digest()
    PH.table(world, sect), PH.garden(world, sect), PH.guarded(world, sect)
    assert world.digest() == before


def own_sect(game):
    from systems.founding import enrol
    world, me = game.world, game.player.id
    town = game.place.id
    sect = world.add_entity("faction", "Pine Cloud Hall", {
        "type": "player_sect", "tier": "minor", "home": [0, 0], "seat": town, "path": "righteous", "taboos": [],
        "trial": "spar", "ranks": list(F.LADDERS["orthodox_sect"]), "treasury": 2000, "power": 20, "wealth": 0,
        "buildings": {}, "last_tick": world.time, "founder": me, "dissolved": False, "chronicle": [], "arts": [],
        "forms": [], "branches": []})
    world.relate(me, sect, "member_of", 4, {"role": "leader", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    world.update_data(me, sect=sect)
    brewer = world.add_entity("person", "Old Brewer", {"occupation": "herbalist", "traits": ["kind"], "realm": "mortal",
                                                       "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:brewer")
    world.relate(brewer, town, "located_in")
    enrol(world, brewer, sect, 60)
    return sect, town


def test_the_own_sect_builds_a_garden_and_a_hall(game):
    world, me = game.world, game.player.id
    sect, town = own_sect(game)
    assert not PH.keeps_hall(world, sect) and PH.garden(world, sect) == {}
    for name in ("herb_garden", "pill_hall"):
        assert name in sect_mod.BUILDINGS
        commit(world, sect_mod.build_events(world, me, name, town))
    assert not PH.keeps_hall(world, sect)  # a season to build
    buildings = world.entity(sect).data["buildings"]
    world.update_data(sect, buildings={b: {**v, "built": True} for b, v in buildings.items()})
    assert PH.keeps_hall(world, sect) and PH.keeps_garden(world, sect)
    assert PH.table(world, sect) == {}  # nothing refined yet
    world.set_time(world.time + 3 * lives.SEASON)
    stock = PH.table(world, sect)
    assert stock and all(key.startswith("1:") for key in stock)  # the herbalist refines grade 1
    assert sum(stock.values()) <= PH.OWN_HALL_CAP
    grade, kind = PH.offers(world, me, sect)[0]
    commit(world, PH.draw_events(world, me, sect, grade, kind, town))  # the founder draws for nothing
    assert F.membership(world, me, sect)[1]["merit"] == 0
    assert PH.garden(world, sect)


def test_the_rules_hold_a_garden_and_a_hall_to_their_bounds(game):
    world = game.world
    sect, _ = the_sect(world)
    assert check_alchemy_world(world) == []
    world.update_data(sect, garden={"at": 0, "herbs": {"moonflower": [13, 0]}}, pill_hall={"1:qi": -1})
    problems = " | ".join(check_alchemy_world(world))
    assert "garden" in problems and "pill hall" in problems
```

- [ ] **Step 2: Write the new modules**

`systems/pill_hall.py`:
```python
"""A sect's pill hall and herb garden (phase 5c spec 2): drawn from for merit, restocked, grown and harvested.

The hall is a table of pills by grade and effect, seeded by `pill_hall:{sect}`; a pill is made only when drawn,
and the member keeps it. A great sect stocks grades 1-3, any other 1-2; bandit forts keep no hall. Each spring
the table is its seed again. The garden is a few herbs of the seat's land, each a count that grows each season
and now and then ages a grade. Both are numbers until someone takes from them, and are read without writing:
what a season added is worked out from the seed when asked, and stored only when something is taken.
The player's own sect builds its garden and hall (3c): its hall is filled by its alchemist disciples.
"""

import math

import systems.alchemy as A
import systems.herbs as H
import systems.lives as lives
import systems.world_clock as world_clock
from systems import factions as F
from systems.membership import set_membership
from world.events import Event, effect
from world.gen.materialize import region_of
from world.seed import rng_for

SEED = {"great": {1: 6, 2: 4, 3: 2}, "other": {1: 4, 2: 2}}
EFFECTS = ("qi", "healing", "antidote", "bottleneck")
BASES = {"qi": "earth_qi", "healing": "wood_healing", "antidote": "metal_antidote", "bottleneck": "bottleneck"}
NO_HALL = frozenset({"bandit_fort"})
PURITY = 0.7
DRAW_MERIT = 20            # merit per grade
RANK_GRADE = {1: 1, 2: 2}  # rank 1 draws grade 1, rank 2 grade 2; an elder grade 3
ELDER_GRADE = 3
GARDEN_HERBS = (3, 6)
GARDEN_START = (2, 6)
GROWTH, GARDEN_CAP = 2, 12
AGE_CHANCE, TOP_AGE = 0.01, 2  # to "a hundred years" at most
LOOK_BACK = 40             # seasons of ageing weighed on a read; older ones are long settled
HARVEST_LIMIT = 2
HARVEST_MERIT = 5          # merit per grade + 1
OWN_HALL_CAP = 12          # the player's own hall holds at most this many pills of a grade
OWN_HALL_SEASONS = 12      # seasons of filling weighed on a read
ALCHEMIST_JOBS = frozenset({"herbalist"})


def _tier(world, faction: int) -> str:
    return "great" if world.entity(faction).data.get("tier") == "great" else "other"


def own(world, faction: int) -> bool:
    return world.entity(faction).data.get("type") == "player_sect"


def _built(world, faction: int, name: str) -> bool:
    import systems.sect as sect_mod
    return sect_mod.built(world, faction, name)


def keeps_hall(world, faction: int) -> bool:
    data = world.entity(faction).data
    if data.get("dissolved"):
        return False
    if own(world, faction):
        return _built(world, faction, "pill_hall")
    return data.get("type") in F.STAFFED and data.get("type") not in NO_HALL


def keeps_garden(world, faction: int) -> bool:
    data = world.entity(faction).data
    if data.get("dissolved") or data.get("seat") is None:
        return False
    if own(world, faction):
        return _built(world, faction, "herb_garden")
    return data.get("type") in F.STAFFED and data.get("type") not in NO_HALL


# --- the hall ----------------------------------------------------------------------------------------------

def _key(grade: int, kind: str) -> str:
    return f"{grade}:{kind}"


def seed_of(world, faction: int) -> dict[str, int]:
    """The hall as it stands each spring: {"grade:effect": count}."""
    if own(world, faction):
        return {}
    rng = rng_for(world.world_seed, f"pill_hall:{faction}")
    out: dict[str, int] = {}
    for grade, count in sorted(SEED[_tier(world, faction)].items()):
        for _ in range(count):
            key = _key(grade, rng.choice(EFFECTS))
            out[key] = out.get(key, 0) + 1
    return out


def alchemists(world, faction: int) -> list[int]:
    """The own sect's disciples who refine: herbalists by trade, or those with a Guild rank."""
    import systems.sect as sect_mod
    return [p for p in sect_mod.members(world, faction)
            if world.entity(p).data.get("occupation") in ALCHEMIST_JOBS or world.entity(p).data.get("guild_rank")]


def _filled(world, faction: int, stored: dict, since: int) -> dict[str, int]:
    """The own sect's hall brought forward: each alchemist adds 1-3 pills a season of grade ceil(rank / 2)."""
    now = lives.current_season(world)
    out = dict(stored)
    makers = alchemists(world, faction)
    for n in range(max(since, now - OWN_HALL_SEASONS) + 1, now + 1):
        for person in makers:
            rng = rng_for(world.world_seed, f"own_hall:{faction}:{n}:{person}")
            grade = max(1, math.ceil((world.entity(person).data.get("guild_rank") or 1) / 2))
            key = _key(min(5, grade), rng.choice(EFFECTS))
            held = sum(v for k, v in out.items() if k.startswith(f"{min(5, grade)}:"))
            out[key] = out.get(key, 0) + max(0, min(rng.randint(1, 3), OWN_HALL_CAP - held))
    return {k: v for k, v in out.items() if v > 0}


def table(world, faction: int) -> dict[str, int]:
    """What the hall holds now (read, never written)."""
    data = world.entity(faction).data
    stored = data.get("pill_hall")
    if own(world, faction):
        built = (data.get("buildings") or {}).get("pill_hall") or {}
        since = (data.get("pill_hall_at") if stored is not None else None)
        if since is None:
            since = built.get("done_at", world.time) // lives.SEASON
        return _filled(world, faction, stored or {}, since) if keeps_hall(world, faction) else {}
    return dict(stored) if stored is not None else seed_of(world, faction)


def best_grade(world, person: int, faction: int) -> int | None:
    """The highest grade this member may draw, or None."""
    found = F.membership(world, person, faction)
    if found is None:
        return None
    rank, data = found
    if data.get("status", "member") != "member":
        return None
    if data.get("role") in ("elder", "leader"):
        return ELDER_GRADE if not own(world, faction) else 5
    return RANK_GRADE.get(min(rank, 2))


def cost(world, faction: int, grade: int) -> int:
    return 0 if own(world, faction) else DRAW_MERIT * grade


def _merit(world, person: int, faction: int) -> int:
    return F.membership(world, person, faction)[1].get("merit", 0)


def offers(world, person: int, faction: int) -> list[tuple[int, str]]:
    """(grade, effect) this member could draw now, strongest first."""
    best = best_grade(world, person, faction)
    if best is None or not keeps_hall(world, faction):
        return []
    out = []
    for key, count in table(world, faction).items():
        grade, kind = key.split(":")
        if count > 0 and int(grade) <= best:
            out.append((int(grade), kind))
    return sorted(out, key=lambda o: (-o[0], o[1]))


def draw_block(world, person: int, faction: int, grade: int, kind: str, place) -> str | None:
    if world.entity(faction).data.get("seat") != place or not keeps_hall(world, faction):
        return "The pill hall is at the sect's seat."
    best = best_grade(world, person, faction)
    if best is None:
        return "Only a disciple of rank may draw from the pill hall."
    if grade > best:
        return "Your rank does not reach that grade."
    if table(world, faction).get(_key(grade, kind), 0) <= 0:
        return "The hall has none of those left."
    if _merit(world, person, faction) < cost(world, faction, grade):
        return f"That costs {cost(world, faction, grade)} merit."
    return None


def draw_events(world, person: int, faction: int, grade: int, kind: str, place) -> list[Event]:
    return [Event("pill_drawn", (person,), place, {"faction": faction, "grade": grade, "effect": kind,
                                                   "merit": cost(world, faction, grade),
                                                   "season": lives.current_season(world)})]


@effect("pill_drawn")
def _drawn(world, event) -> None:
    person, d = event.actors[0], event.data
    stocked = table(world, d["faction"])
    key = _key(d["grade"], d["effect"])
    stocked[key] = stocked.get(key, 0) - 1
    world.update_data(d["faction"], pill_hall={k: v for k, v in stocked.items() if v > 0}, pill_hall_at=d["season"])
    if d["merit"]:
        set_membership(world, person, d["faction"], merit=_merit(world, person, d["faction"]) - d["merit"])
    make_hall_pill(world, person, d["faction"], d["grade"], d["effect"], "drawn")


def make_hall_pill(world, person: int, faction: int, grade: int, kind: str, how: str) -> int:
    """A pill out of a sect's hall, made as it leaves (drawn, or stolen)."""
    pill = A.make_pill(world, person, A.recipe_entity(world, BASES[kind]), grade, PURITY)
    world.update_data(pill, maker=faction, how=how)
    return pill


def season_hook(world, n: int) -> list:
    """Each spring a drawn-from hall is its seed again (spec 2.1); the own sect's hall is filled, not restocked."""
    if n % 4:
        return []
    for faction in world.entities_after("faction", "pill_hall", 0):
        if not own(world, faction.id):
            world.update_data(faction.id, pill_hall=None)
    return []


world_clock.SEASON_HOOKS.append(season_hook)


# --- the garden ----------------------------------------------------------------------------------------------

def _terrain(world, faction: int) -> str | None:
    seat = world.entity(faction).data.get("seat")
    return region_of(world, seat).data["terrain"] if seat is not None else None


def garden_seed(world, faction: int) -> dict[str, list[int]]:
    """The garden as first planted: {herb: [count, grade]}."""
    terrain = _terrain(world, faction)
    growing = H.growing(terrain) if terrain else []
    if not growing:
        return {}
    rng = rng_for(world.world_seed, f"garden:{faction}")
    names = rng.sample(growing, min(len(growing), rng.randint(*GARDEN_HERBS)))
    return {name: [rng.randint(*GARDEN_START), 1 if rng.random() < 0.1 else 0] for name in sorted(names)}


def _planted(world, faction: int) -> int:
    """The season the garden was first planted: the own sect's when built, any other's when the sect arose."""
    entity = world.entity(faction)
    if own(world, faction):
        return ((entity.data.get("buildings") or {}).get("herb_garden") or {}).get("done_at", world.time) // lives.SEASON
    return entity.created_at // lives.SEASON


def garden(world, faction: int) -> dict[str, list[int]]:
    """What grows now: {herb: [count, grade]}, brought forward from the last harvest (read, never written)."""
    if not keeps_garden(world, faction):
        return {}
    stored = world.entity(faction).data.get("garden")
    herbs = {k: list(v) for k, v in (stored["herbs"] if stored else garden_seed(world, faction)).items()}
    since = stored["at"] if stored else _planted(world, faction)
    now = lives.current_season(world)
    seasons = max(0, now - since)
    for name, (count, grade) in herbs.items():
        for n in range(max(since, now - LOOK_BACK) + 1, now + 1):
            if grade < TOP_AGE and rng_for(world.world_seed, f"garden:{faction}:{name}:{n}").random() < AGE_CHANCE:
                grade += 1
        herbs[name] = [min(GARDEN_CAP, count + GROWTH * seasons), grade]
    return herbs


def guarded(world, faction: int) -> bool:
    """A garden holding a hundred-year herb keeps a guardian beast (spec 2.4)."""
    return any(grade >= TOP_AGE and count > 0 for count, grade in garden(world, faction).values())


def taken_this_season(world, person: int, faction: int) -> int:
    found = (world.entity(person).data.get("harvested") or {}).get(str(faction))
    return found["count"] if found and found["season"] == lives.current_season(world) else 0


def harvest_cost(world, faction: int, grade: int) -> int:
    return 0 if own(world, faction) else HARVEST_MERIT * (grade + 1)


def harvest_block(world, person: int, faction: int, herb: str, place) -> str | None:
    if world.entity(faction).data.get("seat") != place or not keeps_garden(world, faction):
        return "The herb garden is at the sect's seat."
    found = F.membership(world, person, faction)
    if found is None or found[1].get("status", "member") != "member":
        return "Only the sect's own may take from its garden."
    if taken_this_season(world, person, faction) >= HARVEST_LIMIT:
        return f"You may take only {HARVEST_LIMIT} herbs a season."
    growing = garden(world, faction).get(herb)
    if not growing or growing[0] <= 0:
        return "None of that grows there now."
    if _merit(world, person, faction) < harvest_cost(world, faction, growing[1]):
        return f"That costs {harvest_cost(world, faction, growing[1])} merit."
    return None


def harvest_events(world, person: int, faction: int, herb: str, place) -> list[Event]:
    grade = garden(world, faction)[herb][1]
    return [Event("garden_harvested", (person,), place, {"faction": faction, "herb": herb, "grade": grade,
                                                          "merit": harvest_cost(world, faction, grade),
                                                          "season": lives.current_season(world)})]


def take_from_garden(world, faction: int, herb: str, season: int) -> None:
    """One herb less, and the garden as it stands now remembered (a harvest, a theft)."""
    herbs = garden(world, faction)
    herbs[herb][0] = max(0, herbs[herb][0] - 1)
    world.update_data(faction, garden={"at": season, "herbs": herbs})


@effect("garden_harvested")
def _harvested(world, event) -> None:
    person, d = event.actors[0], event.data
    take_from_garden(world, d["faction"], d["herb"], d["season"])
    taken = dict(world.entity(person).data.get("harvested") or {})
    before = taken.get(str(d["faction"]))
    count = before["count"] if before and before["season"] == d["season"] else 0
    taken[str(d["faction"])] = {"season": d["season"], "count": count + 1}
    world.update_data(person, harvested=taken)
    if d["merit"]:
        set_membership(world, person, d["faction"], merit=_merit(world, person, d["faction"]) - d["merit"])
    H.make_herb(world, d["herb"], d["grade"], person, "harvested")
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_pill_hall.py`
Expected: `1 error`: collection stops: the tests import `check_alchemy_world`, which Step 4 adds.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5c_task1.py`:
```python
"""Phase 5c, Task 1: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/sect.py', r'''             "guest_hall": (100, 5), "walls": (300, 15)}''', r'''             "guest_hall": (100, 5), "walls": (300, 15), "herb_garden": (250, 10), "pill_hall": (300, 15)}''')
edit('systems/world_clock.py', r'''import systems.poison_path  # noqa: E402,F401  phase 5b: the poison path, venomous beasts, tempering baths
''', r'''import systems.poison_path  # noqa: E402,F401  phase 5b: the poison path, venomous beasts, tempering baths
import systems.pill_hall  # noqa: E402,F401  phase 5c: sects' pill halls and herb gardens
''')
edit('debug/invariants.py', r'''    problems += check_alchemy(world)
''', r'''    problems += check_alchemy(world)
    problems += check_alchemy_world(world)
''')
edit('debug/invariants.py', r'''def check_toxins(world) -> list[str]:''', r'''def check_alchemy_world(world) -> list[str]:
    """Gardens of herbs of the table within 0-12, halls never below nothing (phase 5c)."""
    from systems.herbs import HERBS
    from systems.pill_hall import GARDEN_CAP
    out = []
    for faction in world.entities_after("faction", "garden", 0):
        for name, (count, grade) in faction.data["garden"]["herbs"].items():
            if name not in HERBS or not 0 <= count <= GARDEN_CAP or not 0 <= grade <= 3:
                out.append(f"the garden of {faction.name} holds {count} of {name} (grade {grade})")
    for faction in world.entities_after("faction", "pill_hall", 0):
        if any(count < 0 for count in faction.data["pill_hall"].values()):
            out.append(f"the pill hall of {faction.name} holds less than nothing")
    return out


def check_toxins(world) -> list[str]:''')
print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5c_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_pill_hall.py`
Expected: `12 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1292 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: pill halls and herb gardens - drawn for merit, restocked each spring, grown and harvested, and built by the player's own sect"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 2: The Alchemists' Guild and recipe scrolls

The Guild keeps a branch in every city. Joining is free; an examination for the next rank asks a known recipe of the grade it needs (ruling 2), a fee of `50 x rank`, and one refining roll, once a season. A rank passed is the fact `guild_rank`: whoever has heard it thinks `0.05 x rank` better of the alchemist, and the herbalist sells 3% cheaper a rank. NPC alchemists carry a seeded rank (ruling 3). Recipe scrolls are items: the Guild sells its base recipes up to the reader's rank at `100 x grade^2` and buys any scroll back at half; a sect's hall gives its one or two secret recipes to members of rank 2 for `50 x grade` merit; an alchemist who likes the player teaches one of theirs; a sect's secret sold to its rival fetches triple, and the sect holds it against the seller (ruling 10). `alchemy.SECRET` and `recipe_base` make room for recipes that no experiment finds (Task 6 fills it).

**Files:**
- Create: `systems/guild.py`
- Create: `systems/recipe_trade.py`
- Create: `tests/test_guild.py`
- Modify (by `.patches/5c_task2.py`): `systems/alchemy.py`, `systems/herbs.py`, `systems/attitude.py`, `systems/standing.py`, `systems/world_clock.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: 5b's `alchemy` (`known_recipes`, `refine_chance`, `recipe_entity`, `mastery`, `DISCOVERED_MASTERY`), `herbs.price`; 3a's `facts.record_fact`, `beliefs.knowledge_of`, `attitude.attitude`; 3b's `standing.standing`, `factions.stance`; Task 1's `pill_hall.keeps_hall`.
- Produces:
  - `G` (systems/guild.py): `MAX_RANK`, `EXAM_FEE`, `HERB_DISCOUNT`, `RESPECT`, `NPC_RANKS`, `ORDINALS`, `ALCHEMIST_JOBS`; `recipe_grade(key)`, `needed_grade(rank)`, `title(rank)`, `branch_here(world, place)`, `rank_of(world, person)`, `is_pill_master(world, person)`, `is_alchemist(world, person)`, `discount(world, person)`, `join_block(world, person, place)`, `join_events(world, person, place)`, `exam_recipe(world, person, rank)`, `exam_block(world, person, place)`, `exam_events(world, person, place)`, `known_rank(world, knower, subject)`; events `guild_exam`, `guild_joined`.
  - `RT` (systems/recipe_trade.py): `PRICE`, `SELL_SHARE`, `RIVAL_SHARE`, `SECRET_MERIT`, `SECRET_RANK`, `SECRETS`, `TEACH_ATTITUDE`, `NPC_RECIPES`, `SOURCES`; `price(key)`, `make_scroll(world, owner, key, source, faction)`, `scrolls_of(world, person)`, `read_block(world, person, item_id)`, `read_events(world, person, item_id, place)`, `guild_offers(world, person)`, `buy_block(world, person, key, place)`, `buy_events(world, person, key, place)`, `sell_price(world, item_id)`, `sell_block(world, person, item_id, place)`, `sell_events(world, person, item_id, place)`, `secret_recipes(world, faction)`, `secret_cost(key)`, `secret_block(world, person, faction, key, place)`, `secret_events(world, person, faction, key, place)`, `npc_recipes(world, person)`, `teach_offers(world, person, npc)`, `teach_block(world, person, npc, key)`, `teach_events(world, person, npc, key, place)`, `rivals_of(world, faction)`, `secret_sale_block(world, person, item_id, buyer, place)`, `secret_sale_events(world, person, item_id, buyer, place)`; events `recipe_taught`, `scroll_bought`, `scroll_read`, `scroll_sold`, `secret_scroll_given`, `secret_sold`.
  - `alchemy.SECRET`, `alchemy.recipe_base(key)`; `herbs.price(world, town, name, grade, buyer=None)`; an attitude term for a known Guild rank; a standing term for `sold_secret`.

- [ ] **Step 1: Write the tests**

`tests/test_guild.py`:
```python
import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.guild as G
import systems.herbs as H
import systems.lives as lives
import systems.recipe_trade as RT
from debug.invariants import check_alchemy_world
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.attitude import attitude
from systems.creation import CreationChoice
from systems.purse import silver_of
from systems.standing import standing
from world.events import Event, Witness, commit


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


def a_city(world):
    from world.gen.materialize import ensure_town
    from world.gen.region import region_spec
    from world.gen.town import town_spec
    for x in range(-3, 4):
        for y in range(-3, 4):
            for i in range(region_spec(world.world_seed, x, y).town_count):
                if town_spec(world.world_seed, x, y, i).kind == "city":
                    return ensure_town(world, x, y, i)
    raise AssertionError("no city near")


def go(game, place):
    world, me = game.world, game.player.id
    world.unrelate(me, "located_in")
    world.relate(me, place, "located_in")


def someone(game, tag, place=None, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:guild:{tag}")
    game.world.relate(pid, place or game.place.id, "located_in")
    return pid


def test_the_guild_keeps_its_branches_in_the_cities(game):
    world, me = game.world, game.player.id
    city = a_city(world)
    assert G.join_block(world, me, city) is None
    if world.entity(game.place.id).data["kind"] != "city":
        assert "cities" in G.join_block(world, me, game.place.id)
    commit(world, G.join_events(world, me, city))
    assert world.entity(me).data["guild_rank"] == 0
    assert "already" in G.join_block(world, me, city)


def test_an_examination_asks_a_recipe_of_its_grade_a_fee_and_a_roll(game, monkeypatch):
    world, me = game.world, game.player.id
    city = a_city(world)
    commit(world, G.join_events(world, me, city))
    assert "recipe of grade 1" in G.exam_block(world, me, city)
    world.relate(me, A.recipe_entity(world, "calming"), "knows_recipe", 0.5)
    assert G.exam_block(world, me, city) is None
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (1.0, 1.0))
    commit(world, G.exam_events(world, me, city))
    assert world.entity(me).data["guild_rank"] == 1 and silver_of(world, me) == 5000 - G.EXAM_FEE
    assert "once a season" in G.exam_block(world, me, city)
    world.set_time(world.time + lives.SEASON)
    assert G.exam_block(world, me, city) is None  # the second rank still asks grade 1
    commit(world, G.exam_events(world, me, city))
    world.set_time(world.time + lives.SEASON)
    assert "recipe of grade 2" in G.exam_block(world, me, city)  # calming is grade 1


def test_a_failed_examination_keeps_the_rank_and_the_fee(game, monkeypatch):
    world, me = game.world, game.player.id
    city = a_city(world)
    commit(world, G.join_events(world, me, city))
    world.relate(me, A.recipe_entity(world, "calming"), "knows_recipe", 0.1)
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (0.0, 0.0))
    commit(world, G.exam_events(world, me, city))
    assert world.entity(me).data["guild_rank"] == 0 and silver_of(world, me) == 5000 - G.EXAM_FEE
    assert not world.facts(predicate="guild_rank")


def test_a_rank_is_news_and_those_who_heard_it_think_better_of_you(game, monkeypatch):
    world, me = game.world, game.player.id
    city, home = a_city(world), game.place.id
    go(game, city)
    listener = someone(game, "listener", city)
    before = attitude(world, listener, me).score
    commit(world, G.join_events(world, me, city))
    world.relate(me, A.recipe_entity(world, "calming"), "knows_recipe", 0.5)
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (1.0, 1.0))
    commit(world, G.exam_events(world, me, city))
    assert G.known_rank(world, listener, me) == 1
    assert attitude(world, listener, me).score == pytest.approx(before + G.RESPECT * 1 * 0.85, abs=0.01)
    if home != city:  # the news has not yet reached another town
        assert G.known_rank(world, someone(game, "far", home), me) is None


def test_the_herbalist_sells_cheaper_to_the_guilds_own(game):
    world, me = game.world, game.player.id
    town = game.place.id
    offer = H.stock(world, town)[0]
    plain = H.price(world, town, offer["herb"], offer["grade"])
    world.update_data(me, guild_rank=5)
    cheaper = H.price(world, town, offer["herb"], offer["grade"], me)
    assert cheaper < plain and abs(cheaper - plain * (1 - 5 * G.HERB_DISCOUNT)) <= 1
    commit(world, H.buy_events(world, me, town, offer["key"]))
    assert silver_of(world, me) == 5000 - H.price(world, town, offer["herb"], offer["grade"], me)


def test_npc_alchemists_carry_a_seeded_rank(game):
    world = game.world
    brewer = someone(game, "brewer", occupation="herbalist")
    seller = someone(game, "seller")
    rank = G.rank_of(world, brewer)
    assert G.NPC_RANKS[0] <= rank <= G.NPC_RANKS[1] and G.rank_of(world, brewer) == rank
    assert G.rank_of(world, seller) is None
    assert G.title(5) == "a fifth-rank alchemist"


def test_a_sects_pill_master_is_an_alchemist(game):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [keeper] = halls.staff_at(world, sect, seat, roles=("keeper",))
    assert G.is_pill_master(world, keeper) and G.rank_of(world, keeper) is not None


def test_a_scroll_read_teaches_its_recipe_and_is_kept(game):
    world, me = game.world, game.player.id
    scroll = RT.make_scroll(world, me, "cleansing", "guild")
    assert RT.read_block(world, me, scroll) is None
    commit(world, RT.read_events(world, me, scroll, game.place.id))
    assert A.mastery(world, me, A.recipe_entity(world, "cleansing")) == A.DISCOVERED_MASTERY
    assert scroll in world.targets(me, "owns")
    assert "already" in RT.read_block(world, me, scroll)


def test_the_guild_sells_scrolls_up_to_the_readers_rank_and_buys_them_back_at_half(game):
    world, me = game.world, game.player.id
    city = a_city(world)
    assert RT.guild_offers(world, me) == []
    world.update_data(me, guild_rank=0)
    assert RT.guild_offers(world, me) == []  # an unranked member buys nothing yet
    world.update_data(me, guild_rank=1)
    offers = RT.guild_offers(world, me)
    assert offers and all(G.recipe_grade(k) == 1 for k in offers)
    key = offers[0]
    assert RT.buy_block(world, me, key, city) is None
    commit(world, RT.buy_events(world, me, key, city))
    [scroll] = RT.scrolls_of(world, me)
    assert silver_of(world, me) == 5000 - RT.price(key) and scroll.data["source"] == "guild"
    commit(world, RT.sell_events(world, me, scroll.id, city))
    assert silver_of(world, me) == 5000 - RT.price(key) // 2 and not RT.scrolls_of(world, me)


def test_a_sects_hall_gives_its_secret_scrolls_to_its_ranked_for_merit(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    secrets = RT.secret_recipes(world, sect)
    assert RT.SECRETS[0] <= len(secrets) <= RT.SECRETS[1] and RT.secret_recipes(world, sect) == secrets
    world.relate(me, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 500, "status": "member",
                                            "secret": False})
    assert "second rank" in RT.secret_block(world, me, sect, secrets[0], seat)
    world.relate(me, sect, "member_of", 2, {"role": "disciple", "hall": 0, "merit": 500, "status": "member",
                                            "secret": False})
    assert RT.secret_block(world, me, sect, secrets[0], seat) is None
    commit(world, RT.secret_events(world, me, sect, secrets[0], seat))
    [scroll] = RT.scrolls_of(world, me)
    assert scroll.data["faction"] == sect and scroll.data["source"] == "sect"
    assert F.membership(world, me, sect)[1]["merit"] == 500 - RT.secret_cost(secrets[0])
    assert "already" in RT.secret_block(world, me, sect, secrets[0], seat)


def test_an_alchemist_who_likes_you_teaches_a_recipe_for_silver(game):
    world, me = game.world, game.player.id
    brewer = someone(game, "teacher", occupation="herbalist")
    key = RT.npc_recipes(world, brewer)[0]
    assert "well enough" in RT.teach_block(world, me, brewer, key)
    commit(world, [Event("helped", (me, brewer), game.place.id, {}, witnesses=(Witness(brewer, "grateful", 1.0),))])
    assert RT.teach_block(world, me, brewer, key) is None
    commit(world, RT.teach_events(world, me, brewer, key, game.place.id))
    assert any(s.data["key"] == key and s.data["source"] == "master" for s in RT.scrolls_of(world, me))


def test_a_secret_sold_to_a_rival_fetches_triple_and_the_sect_hates_the_seller(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    rival = RT.rivals_of(world, sect)[0]
    rival_seat = halls.seat_of(world, rival)
    seat = halls.seat_of(world, sect)
    scroll = RT.make_scroll(world, me, RT.secret_recipes(world, sect)[0], "stolen", sect)
    assert RT.secret_sale_block(world, me, scroll, rival, rival_seat) is None
    assert RT.secret_sale_block(world, me, scroll, sect, seat) is not None
    before = standing(world, sect, me).score
    commit(world, RT.secret_sale_events(world, me, scroll, rival, rival_seat))
    assert silver_of(world, me) == 5000 + RT.price(world.entity(scroll).data["key"]) * RT.RIVAL_SHARE
    [fact] = world.facts(predicate="sold_secret")
    from systems.beliefs import believe
    believe(world, seat, fact.id, fact.variant, None, 1.0, 1, "gossip")
    assert standing(world, sect, me).score < before - 1


def test_the_rules_hold_ranks_within_nought_to_nine_and_scrolls_to_one_owner(game):
    world, me = game.world, game.player.id
    scroll = RT.make_scroll(world, me, "cleansing", "guild")
    assert check_alchemy_world(world) == []
    world.update_data(me, guild_rank=10)
    other = someone(game, "holder")
    world.relate(other, scroll, "owns")
    problems = " | ".join(check_alchemy_world(world))
    assert "rank" in problems and "owner" in problems
```

- [ ] **Step 2: Write the new modules**

`systems/guild.py`:
```python
"""The Alchemists' Guild (phase 5c spec 3): ranks 1-9 won by examination at its branch in every city.

The Guild is no faction of the roster (ruling 1): it is a branch in each city and a rank on each alchemist,
`guild_rank` on the person (0 once joined, None before). An examination for the next rank asks a known recipe of
the grade the rank needs, a fee, and one refining roll; it may be sat once a season. A rank passed is a fact
(`guild_rank`) that spreads like any other: who has heard it thinks better of the alchemist, and the herbalist
sells cheaper to the Guild's own. NPC alchemists (herbalists by trade and the sects' pill masters) carry a
seeded rank until something first writes one.
"""

import math

import systems.alchemy as A
import systems.lives as lives
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import Event, effect, listen
from world.seed import rng_for

MAX_RANK = 9
EXAM_FEE = 50              # silver per rank sat
HERB_DISCOUNT = 0.03       # off the herbalist's price, per rank
RESPECT = 0.05             # attitude per rank, from anyone who knows it
NPC_RANKS = (1, 4)         # a seeded NPC alchemist's rank
ORDINALS = ("", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth")
ALCHEMIST_JOBS = frozenset({"herbalist"})


def recipe_grade(key: str) -> int:
    """How hard a recipe is: its pills' grade from the Guild's herbs (ruling 2)."""
    base = A.recipe_base(key)
    if "grade" in base:
        return base["grade"]
    return 1 if base["potency"] <= 4 else 2 if base["potency"] <= 6 else 3


def needed_grade(rank: int) -> int:
    """The grade of recipe an examination for this rank asks (ruling 2: the base recipes top out at 3)."""
    return min(3, math.ceil(rank / 2))


def title(rank: int) -> str:
    return f"a {ORDINALS[rank]}-rank alchemist" if rank else "an unranked member of the Guild"


def branch_here(world, place) -> bool:
    entity = world.entity(place) if place is not None else None
    return entity is not None and entity.kind == "town" and entity.data.get("kind") == "city"


def rank_of(world, person: int) -> int | None:
    """A person's Guild rank: written once joined or examined, else seeded for an NPC alchemist, else None."""
    entity = world.entity(person)
    if "guild_rank" in entity.data:
        return entity.data["guild_rank"]
    if entity.data.get("is_player") or not is_alchemist(world, person):
        return None
    return rng_for(world.world_seed, f"guild:{lives.key(entity)}").randint(*NPC_RANKS)


def is_pill_master(world, person: int) -> bool:
    """The keeper of a sect's pill hall, standing at its seat (spec 3)."""
    from systems.pill_hall import keeps_hall
    here = world.targets(person, "located_in")
    for fid, _, data in F.memberships(world, person):
        if data.get("role") == "keeper" and data.get("status", "member") == "member" and keeps_hall(world, fid) \
                and here == [world.entity(fid).data.get("seat")]:
            return True
    return False


def is_alchemist(world, person: int) -> bool:
    entity = world.entity(person)
    if entity is None or entity.kind != "person" or entity.data.get("beast"):
        return False
    return entity.data.get("occupation") in ALCHEMIST_JOBS or is_pill_master(world, person)


def discount(world, person: int | None) -> float:
    rank = world.entity(person).data.get("guild_rank") if person is not None else None
    return 1.0 - HERB_DISCOUNT * (rank or 0)


# --- joining ------------------------------------------------------------------------------------------------

def join_block(world, person: int, place) -> str | None:
    if not branch_here(world, place):
        return "The Guild keeps its branches in the cities."
    if world.entity(person).data.get("guild_rank") is not None:
        return "You are one of the Guild already."
    return None


def join_events(world, person: int, place) -> list[Event]:
    return [Event("guild_joined", (person,), place, {})]


@effect("guild_joined")
def _joined(world, event) -> None:
    world.update_data(event.actors[0], guild_rank=0)


# --- examinations ------------------------------------------------------------------------------------------

def exam_recipe(world, person: int, rank: int) -> int | None:
    """The recipe the candidate would refine for this rank: the one they know best of the grade it asks."""
    fit = [(m, r) for r, m in A.known_recipes(world, person)
           if recipe_grade(world.entity(r).data["key"]) >= needed_grade(rank)]
    return max(fit)[1] if fit else None


def exam_block(world, person: int, place) -> str | None:
    rank = world.entity(person).data.get("guild_rank")
    if not branch_here(world, place):
        return "The Guild keeps its branches in the cities."
    if rank is None:
        return "Join the Guild first."
    if rank >= MAX_RANK:
        return "There is no higher rank."
    if world.entity(person).data.get("guild_exam_season") == lives.current_season(world):
        return "The examiners sit once a season."
    if exam_recipe(world, person, rank + 1) is None:
        return f"The {ORDINALS[rank + 1]} rank asks a recipe of grade {needed_grade(rank + 1)}."
    if silver_of(world, person) < EXAM_FEE * (rank + 1):
        return f"The fee is {EXAM_FEE * (rank + 1)} silver."
    return None


def exam_events(world, person: int, place) -> list[Event]:
    rank = world.entity(person).data["guild_rank"] + 1
    recipe = exam_recipe(world, person, rank)
    season = lives.current_season(world)
    passed = rng_for(world.world_seed, f"guild_exam:{person}:{season}").random() < A.refine_chance(world, person, recipe)
    return [Event("guild_exam", (person,), place, {"rank": rank, "recipe": recipe, "passed": passed,
                                                   "fee": EXAM_FEE * rank, "season": season})]


@effect("guild_exam")
def _exam(world, event) -> None:
    person, d = event.actors[0], event.data
    changes = {"silver": silver_of(world, person) - d["fee"], "guild_exam_season": d["season"]}
    if d["passed"]:
        changes["guild_rank"] = d["rank"]
    world.update_data(person, **changes)


@listen("guild_exam")
def _ranked_news(world, event, event_id: int) -> None:
    if not event.data["passed"]:
        return
    person, rank = event.actors[0], event.data["rank"]
    variant = make_variant("guild_rank", person, None, place=place_name(world, event.place))
    variant.update(rank=rank)
    record_fact(world, person, "guild_rank", None, place=event.place, source_event=event_id, weight=1.0 + 0.2 * rank,
                variant=variant)


def known_rank(world, knower: int, subject: int) -> int | None:
    """The highest Guild rank this knower has heard of for the subject, or None (spec 8)."""
    from systems.beliefs import knowledge_of
    heard = [b.variant.get("rank", 0) for b, f in knowledge_of(world, knower)
             if f.predicate == "guild_rank" and b.variant.get("actor") == subject]
    return max(heard) if heard else None
```

`systems/recipe_trade.py`:
```python
"""Recipes as lore (phase 5c spec 4): scrolls bought, given, taught, stolen, read and sold.

A scroll is an item (`kind = "scroll"`) naming a recipe and where it came from (`guild`, `sect`, `master` or
`stolen`; a sect's secret scroll also names its sect). Reading one teaches the recipe; the scroll is kept. The
Guild sells its base recipes up to the reader's rank and buys any scroll back at half; each sect's hall keeps one
or two secret recipes for its ranked members; an NPC alchemist who likes you teaches one of theirs; a sect's secret
sold to its rival fetches triple, and the sect hates the seller once it hears of it.
"""

import systems.alchemy as A
import systems.guild as G
from systems import factions as F
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.purse import silver_of
from world.events import Event, effect, listen
from world.seed import rng_for

PRICE = 100                # silver x grade squared, at the Guild
SELL_SHARE, RIVAL_SHARE = 0.5, 3  # half at the Guild; triple from a sect's rival
SECRET_MERIT = 50          # merit x grade, for a sect's secret scroll
SECRET_RANK = 2
SECRETS = (1, 2)
TEACH_ATTITUDE = 0.5
NPC_RECIPES = (1, 3)
SOURCES = ("guild", "sect", "master", "stolen")


def price(key: str) -> int:
    return PRICE * G.recipe_grade(key) ** 2


def make_scroll(world, owner: int, key: str, source: str, faction: int | None = None) -> int:
    recipe = A.recipe_entity(world, key)
    item = world.add_entity("scroll", f"a scroll of the {world.entity(recipe).name}",
                            {"recipe": recipe, "key": key, "source": source, "faction": faction})
    world.relate(owner, item, "owns")
    return item


def scrolls_of(world, person: int) -> list:
    return [e for e in (world.entity(i) for i in world.targets(person, "owns")) if e is not None and e.kind == "scroll"]


def _owned_scroll(world, person: int, item_id) -> bool:
    item = world.entity(item_id) if isinstance(item_id, int) else None
    return item is not None and item.kind == "scroll" and item_id in world.targets(person, "owns")


# --- reading ------------------------------------------------------------------------------------------------

def read_block(world, person: int, item_id) -> str | None:
    if not _owned_scroll(world, person, item_id):
        return "You have no such scroll."
    if A.mastery(world, person, world.entity(item_id).data["recipe"]) is not None:
        return "You know that recipe already."
    return None


def read_events(world, person: int, item_id: int, place) -> list[Event]:
    return [Event("scroll_read", (person,), place, {"item": item_id, "recipe": world.entity(item_id).data["recipe"]})]


@effect("scroll_read")
def _read(world, event) -> None:
    person, recipe = event.actors[0], event.data["recipe"]
    if A.mastery(world, person, recipe) is None:
        world.relate(person, recipe, "knows_recipe", A.DISCOVERED_MASTERY)


# --- the Guild's scrolls ---------------------------------------------------------------------------------------

def guild_offers(world, person: int) -> list[str]:
    """The base recipes the Guild will sell this member: of a grade their rank reaches, not yet known."""
    rank = world.entity(person).data.get("guild_rank")
    if rank is None:
        return []
    top = G.needed_grade(rank) if rank else 0
    known = {world.entity(r).data["key"] for r, _ in A.known_recipes(world, person)}
    return [k for k in sorted(A.RECIPES) if G.recipe_grade(k) <= top and k not in known]


def buy_block(world, person: int, key: str, place) -> str | None:
    if not G.branch_here(world, place):
        return "The Guild keeps its branches in the cities."
    if key not in guild_offers(world, person):
        return "The Guild will not sell you that."
    if silver_of(world, person) < price(key):
        return f"That scroll costs {price(key)} silver."
    return None


def buy_events(world, person: int, key: str, place) -> list[Event]:
    return [Event("scroll_bought", (person,), place, {"key": key, "price": price(key)})]


@effect("scroll_bought")
def _bought(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    make_scroll(world, person, d["key"], "guild")


def sell_price(world, item_id: int) -> int:
    return max(1, int(price(world.entity(item_id).data["key"]) * SELL_SHARE))


def sell_block(world, person: int, item_id, place) -> str | None:
    if not _owned_scroll(world, person, item_id):
        return "You have no such scroll."
    if not G.branch_here(world, place):
        return "The Guild keeps its branches in the cities."
    return None


def sell_events(world, person: int, item_id: int, place) -> list[Event]:
    return [Event("scroll_sold", (person,), place, {"item": item_id, "price": sell_price(world, item_id)})]


@effect("scroll_sold")
def _sold(world, event) -> None:
    person, d = event.actors[0], event.data
    world.unrelate(person, "owns", d["item"])
    world.update_data(person, silver=silver_of(world, person) + d["price"])
    world.update_data(d["item"], sold_to="guild")


# --- a sect's secret recipes -------------------------------------------------------------------------------------

def secret_recipes(world, faction: int) -> list[str]:
    """The one or two recipes this sect's hall keeps to itself, seeded from the base recipes."""
    rng = rng_for(world.world_seed, f"secret:{faction}")
    return sorted(rng.sample(sorted(A.RECIPES), rng.randint(*SECRETS)))


def secret_cost(key: str) -> int:
    return SECRET_MERIT * G.recipe_grade(key)


def secret_block(world, person: int, faction: int, key: str, place) -> str | None:
    from systems.pill_hall import keeps_hall
    if world.entity(faction).data.get("seat") != place or not keeps_hall(world, faction):
        return "The sect's secrets are kept in its pill hall."
    found = F.membership(world, person, faction)
    if found is None or found[1].get("status", "member") != "member" or found[0] < SECRET_RANK:
        return "Only a disciple of the second rank or higher is trusted with them."
    if key not in secret_recipes(world, faction):
        return "The hall keeps no such recipe."
    if any(s.data["key"] == key and s.data.get("faction") == faction for s in scrolls_of(world, person)):
        return "You hold that scroll already."
    if found[1].get("merit", 0) < secret_cost(key):
        return f"That scroll costs {secret_cost(key)} merit."
    return None


def secret_events(world, person: int, faction: int, key: str, place) -> list[Event]:
    return [Event("secret_scroll_given", (person,), place, {"faction": faction, "key": key,
                                                             "merit": secret_cost(key)})]


@effect("secret_scroll_given")
def _given(world, event) -> None:
    person, d = event.actors[0], event.data
    merit = F.membership(world, person, d["faction"])[1].get("merit", 0)
    set_membership(world, person, d["faction"], merit=merit - d["merit"])
    make_scroll(world, person, d["key"], "sect", d["faction"])


# --- a master's teaching -----------------------------------------------------------------------------------------

def npc_recipes(world, person: int) -> list[str]:
    """What an NPC alchemist knows, seeded from their rank."""
    rank = G.rank_of(world, person)
    if rank is None:
        return []
    top = max(1, G.needed_grade(rank))
    pool = sorted(k for k in A.RECIPES if G.recipe_grade(k) <= top)
    rng = rng_for(world.world_seed, f"npc_recipes:{person}")
    return sorted(rng.sample(pool, min(len(pool), rng.randint(*NPC_RECIPES))))


def teach_offers(world, person: int, npc: int) -> list[str]:
    known = {world.entity(r).data["key"] for r, _ in A.known_recipes(world, person)}
    return [k for k in npc_recipes(world, npc) if k not in known]


def teach_block(world, person: int, npc: int, key: str) -> str | None:
    if not G.is_alchemist(world, npc):
        return "They are no alchemist."
    if attitude(world, npc, apparent_to(world, npc, person)).score < TEACH_ATTITUDE:
        return "They do not know you well enough to teach you."
    if key not in teach_offers(world, person, npc):
        return "They teach nothing like that."
    if silver_of(world, person) < price(key):
        return f"They ask {price(key)} silver."
    return None


def teach_events(world, person: int, npc: int, key: str, place) -> list[Event]:
    return [Event("recipe_taught", (person, npc), place, {"key": key, "price": price(key)})]


@effect("recipe_taught")
def _taught(world, event) -> None:
    person, npc = event.actors
    d = event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    world.update_data(npc, silver=silver_of(world, npc) + d["price"])
    make_scroll(world, person, d["key"], "master")


# --- selling a sect's secret to its rival --------------------------------------------------------------------------

def rivals_of(world, faction: int) -> list[int]:
    return [f for f in F.ensure_roster(world) if f != faction and F.stance(world, f, faction) <= F.HOSTILE]


def secret_sale_block(world, person: int, item_id, buyer: int, place) -> str | None:
    if not _owned_scroll(world, person, item_id):
        return "You have no such scroll."
    sect = world.entity(item_id).data.get("faction")
    if sect is None:
        return "No sect would pay for that."
    if buyer not in rivals_of(world, sect):
        return "They are no enemy of that sect."
    if world.entity(buyer).data.get("seat") != place:
        return "Sell it at their seat."
    return None


def secret_sale_events(world, person: int, item_id: int, buyer: int, place) -> list[Event]:
    sect = world.entity(item_id).data["faction"]
    return [Event("secret_sold", (person,), place, {"item": item_id, "sect": sect, "buyer": buyer,
                                                    "price": price(world.entity(item_id).data["key"]) * RIVAL_SHARE})]


@effect("secret_sold")
def _secret_sold(world, event) -> None:
    person, d = event.actors[0], event.data
    world.unrelate(person, "owns", d["item"])
    world.update_data(person, silver=silver_of(world, person) + d["price"])
    world.update_data(d["item"], sold_to=d["buyer"])


@listen("secret_sold")
def _betrayal(world, event, event_id: int) -> None:
    person, sect = event.actors[0], event.data["sect"]
    record_fact(world, person, "sold_secret", sect, place=event.place, source_event=event_id, weight=2.0,
                variant=make_variant("sold_secret", person, sect, place=place_name(world, event.place)))
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_guild.py`
Expected: `9 failed, 4 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5c_task2.py`:
```python
"""Phase 5c, Task 2: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/alchemy.py', r'''RECIPES = tomllib.loads((Path(__file__).parent / "data" / "recipes.toml").read_text(encoding="utf-8"))
''', r'''RECIPES = tomllib.loads((Path(__file__).parent / "data" / "recipes.toml").read_text(encoding="utf-8"))
SECRET: dict[str, dict] = {}  # recipes never found by experiment, only learnt (phase 5c: the control pill)
''')
edit('systems/alchemy.py', r'''# --- recipes as knowledge ----------------------------------------------------------------------------------
''', r'''# --- recipes as knowledge ----------------------------------------------------------------------------------

def recipe_base(key: str) -> dict:
    """A base recipe's needs, or a secret one's (5c)."""
    return RECIPES[key] if key in RECIPES else SECRET[key]

''')
edit('systems/alchemy.py', r'''    rng = rng_for(world.world_seed, path)
    base = RECIPES[key]''', r'''    rng = rng_for(world.world_seed, path)
    base = recipe_base(key)''')
edit('systems/alchemy.py', r'''    needs = met(RECIPES[world.entity(recipe).data["key"]], combine(''', r'''    needs = met(recipe_base(world.entity(recipe).data["key"]), combine(''')
edit('systems/alchemy.py', r'''    base = RECIPES[world.entity(recipe).data["key"]]
    herbs = sorted(''', r'''    base = recipe_base(world.entity(recipe).data["key"])
    herbs = sorted(''')
edit('systems/herbs.py', r'''def price(world, town: int, name: str, grade: int) -> int:
    terrain = region_of(world, town).data["terrain"]
    factor = 1.0 if terrain in props(name)["terrains"] else LACKED
    return max(1, round(props(name)["price"] * AGE_PRICE[grade] * factor * event_factor(world, town, "herbs")
                        * drift(world, town, "herbs")))''', r'''def price(world, town: int, name: str, grade: int, buyer: int | None = None) -> int:
    from systems.guild import discount  # phase 5c: the Guild's own buy cheaper
    terrain = region_of(world, town).data["terrain"]
    factor = 1.0 if terrain in props(name)["terrains"] else LACKED
    return max(1, round(props(name)["price"] * AGE_PRICE[grade] * factor * event_factor(world, town, "herbs")
                        * drift(world, town, "herbs") * discount(world, buyer)))''')
edit('systems/herbs.py', r'''    if silver_of(world, person) < price(world, town, offer["herb"], offer["grade"]):''', r'''    if silver_of(world, person) < price(world, town, offer["herb"], offer["grade"], person):''')
edit('systems/herbs.py', r'''                                                    "price": price(world, town, offer["herb"], offer["grade"])})]''', r'''                                                    "price": price(world, town, offer["herb"], offer["grade"], person)})]''')
edit('systems/attitude.py', r'''        if fact.predicate == "member_of":  # enemies by association (phase 3b spec 3.4)''', r'''        if fact.predicate == "guild_rank":  # phase 5c: an alchemist's rank, the highest one heard
            value = 0.05 * belief.variant.get("rank", 0) * belief.confidence
            if value > best.get(-1, (0.0, None))[0]:
                best[-1] = (value, "they respect a ranked alchemist")
            continue
        if fact.predicate == "member_of":  # enemies by association (phase 3b spec 3.4)''')
edit('systems/standing.py', r'''        if fact.predicate == "stole" and target == faction_id:
            value, reason = -1.0, "you stole from our armoury"''', r'''        if fact.predicate == "stole" and target == faction_id:
            value, reason = -1.0, "you stole from our armoury"
        if fact.predicate == "sold_secret" and target == faction_id:  # phase 5c: a secret recipe sold to a rival
            value, reason = -1.5, "you sold our secrets"''')
edit('systems/world_clock.py', r'''import systems.pill_hall  # noqa: E402,F401  phase 5c: sects' pill halls and herb gardens
''', r'''import systems.pill_hall  # noqa: E402,F401  phase 5c: sects' pill halls and herb gardens
import systems.guild  # noqa: E402,F401  phase 5c: the Alchemists' Guild
import systems.recipe_trade  # noqa: E402,F401  phase 5c: recipe scrolls bought, given, taught and sold
''')
edit('debug/invariants.py', r'''    for faction in world.entities_after("faction", "pill_hall", 0):
        if any(count < 0 for count in faction.data["pill_hall"].values()):
            out.append(f"the pill hall of {faction.name} holds less than nothing")
    return out''', r'''    for faction in world.entities_after("faction", "pill_hall", 0):
        if any(count < 0 for count in faction.data["pill_hall"].values()):
            out.append(f"the pill hall of {faction.name} holds less than nothing")
    for person in world.entities_after("person", "guild_rank", -1):
        if not 0 <= person.data["guild_rank"] <= 9:
            out.append(f"{person.name} (#{person.id}) holds Guild rank {person.data['guild_rank']}")
    for scroll in world.entities("scroll"):
        owners = world.sources(scroll.id, "owns")
        if len(owners) > 1:
            out.append(f"{scroll.name} (#{scroll.id}) has {len(owners)} owners")
        recipe = world.entity(scroll.data.get("recipe") or 0)
        if recipe is None or recipe.kind != "recipe":
            out.append(f"{scroll.name} (#{scroll.id}) names no recipe")
    return out''')
print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5c_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_guild.py`
Expected: `13 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1305 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the Alchemists' Guild - ranks won by examination, recipe scrolls bought, given, taught, read and sold"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 3: Alchemy duties and theft by night

A pill hall's keeper gives an alchemy duty when asked (ruling 7): bring two to four herbs of a kind that grows on the sect's land, or refine one pill of a recipe the player knows, within a month, handed in at the seat for 3b's merit. By night (the fourth watch) a thief at a sect's seat may take herbs from its garden, pills from its hall or one of its secret scrolls, on `0.5 + 0.1 x (realm - the guard's realm)`; a hundred-year herb keeps a guardian beast that must be beaten first (ruling 8). Caught, the thief commits 3b's `stole`; unseen, the sect knows only that someone came (ruling 9). A look by night shows a thief what a hall holds.

**Files:**
- Create: `systems/hall_theft.py`
- Create: `tests/test_hall_theft.py`
- Modify (by `.patches/5c_task3.py`): `systems/duties.py`, `systems/world_clock.py`

**Interfaces:**
- Consumes: 3b's `duties` (`issue_events`, `progress`, `done_events`), `halls.staff_at`; 2b's `encounters.make_roamer`, `encounter_events`; Tasks 1-2's `pill_hall` and `recipe_trade`.
- Produces:
  - `T` (systems/hall_theft.py): `NIGHT`, `BASE`, `PER_REALM`, `BOUNDS`, `HERBS_TAKEN`, `PILLS_TAKEN`, `WATCHMAN`, `THEFT_WEIGHT`, `TARGETS`, `GUARDIAN_GONE`; `night(world)`, `nightfall_events(world, person, place)`, `guard_of(world, faction)`, `chance(world, thief, faction)`, `at_seat(world, faction, place)`, `knows_hall(world, person, faction)`, `look_block(world, person, faction, place)`, `look_events(world, person, faction, place)`, `needs_guardian(world, person, faction)`, `guardian_events(world, person, faction, place)`, `steal_block(world, person, faction, target, place)`, `steal_events(world, person, faction, target, place)`; events `hall_surveyed`, `hall_theft`, `waited_for_night`.
  - `duties.ALCHEMY_DAYS`, `duties.BRING`, `duties.alchemy_task(world, rng, player, faction)`, `duties.alchemy_items(world, player, d)`; a duty of kind `alchemy`.

- [ ] **Step 1: Write the tests**

`tests/test_hall_theft.py`:
```python
import pytest

import systems.alchemy as A
import systems.duties as duties
import systems.encounters as encounters
import systems.hall_theft as T
import systems.herbs as H
import systems.lives as lives
import systems.pill_hall as PH
import systems.recipe_trade as RT
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.standing import standing
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


def the_sect(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    return sect, halls.seat_of(world, sect)


def go(game, place):
    world, me = game.world, game.player.id
    world.unrelate(me, "located_in")
    world.relate(me, place, "located_in")


def to_night(world):
    while not T.night(world):
        world.set_time(world.time + 1)


def to_day(world):
    while T.night(world):
        world.set_time(world.time + 1)


# --- alchemy duties ------------------------------------------------------------------------------------------

def member(game, sect, seat):
    game.world.relate(game.player.id, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 0,
                                                            "status": "member", "secret": False})
    go(game, seat)


def test_an_alchemy_duty_asks_herbs_of_the_sects_land_and_is_done_when_they_are_brought(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    member(game, sect, seat)
    [keeper] = halls.staff_at(world, sect, seat, roles=("keeper",))
    commit(world, duties.issue_events(world, me, sect, keeper, seat, kind="alchemy"))
    duty = duties.open_duty(world, me)
    d = duty.data
    assert d["task"] == "bring" and duties.BRING[0] <= d["count"] <= duties.BRING[1]
    assert world.entity(seat).data["terrain"] in H.props(d["herb"])["terrains"]
    assert d["deadline"] == world.time + duties.ALCHEMY_DAYS * 4
    assert duties.progress(world, me) is None
    herbs = [H.make_herb(world, d["herb"], 0, me) for _ in range(d["count"])]
    assert duties.progress(world, me) == "done"
    commit(world, duties.done_events(world, me, seat))
    assert F.membership(world, me, sect)[1]["merit"] == 10 * d["difficulty"]
    assert not any(h in world.targets(me, "owns") for h in herbs)


def test_a_refining_duty_asks_a_pill_made_after_it_was_given(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    member(game, sect, seat)
    recipe = A.recipe_entity(world, "calming")
    world.relate(me, recipe, "knows_recipe", 0.5)
    old = A.make_pill(world, me, recipe, 1, 0.8)
    [keeper] = halls.staff_at(world, sect, seat, roles=("keeper",))
    for n in range(8):  # the seeded choice of task: find a refining duty
        world.update_data(me, duties_taken=n, duty=None)
        commit(world, duties.issue_events(world, me, sect, keeper, seat, kind="alchemy"))
        if duties.open_duty(world, me).data["task"] == "refine":
            break
    d = duties.open_duty(world, me).data
    assert d["task"] == "refine" and d["recipe"] == recipe
    assert duties.progress(world, me) is None  # a pill made before the duty does not count
    world.set_time(world.time + 1)
    A.make_pill(world, me, recipe, 1, 0.8)
    assert duties.progress(world, me) == "done"
    commit(world, duties.done_events(world, me, seat))
    assert old in world.targets(me, "owns")


# --- theft ------------------------------------------------------------------------------------------------

def test_theft_is_by_night_at_the_seat(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_day(world)
    assert "dark" in T.steal_block(world, me, sect, "hall", seat)
    commit(world, T.nightfall_events(world, me, seat))
    assert T.night(world)
    assert T.steal_block(world, me, sect, "hall", seat) is None
    assert T.steal_block(world, me, sect, "hall", game.place.id + 100000) is not None


def test_the_chance_weighs_the_thiefs_realm_against_the_guards(game):
    world, me = game.world, game.player.id
    sect, _ = the_sect(world)
    guard, realm = T.guard_of(world, sect)
    assert guard is not None
    world.update_data(me, realm="mortal")
    assert T.chance(world, me, sect) == max(0.1, min(0.9, 0.5 - 0.1 * realm))
    world.update_data(me, realm="life-and-death")
    assert T.chance(world, me, sect) == 0.9


def test_an_unseen_theft_of_the_hall_takes_two_pills_and_leaves_a_deed_without_a_doer(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_night(world)
    monkeypatch.setattr(T, "BOUNDS", (1.0, 1.0))
    before = sum(PH.table(world, sect).values())
    commit(world, T.steal_events(world, me, sect, "hall", seat))
    pills = [world.entity(i) for i in world.targets(me, "owns") if world.entity(i).kind == "pill"]
    assert len(pills) == T.PILLS_TAKEN and all(p.data["how"] == "stolen" for p in pills)
    assert sum(PH.table(world, sect).values()) == before - T.PILLS_TAKEN
    [fact] = world.facts(predicate="robbed_hall")
    assert fact.variant["actor"] is None and fact.variant["target"] == sect
    assert not world.facts(predicate="stole")


def test_a_caught_thief_is_a_criminal_the_sect_hates_and_takes_nothing(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_night(world)
    monkeypatch.setattr(T, "BOUNDS", (0.0, 0.0))
    before = PH.table(world, sect)
    commit(world, T.steal_events(world, me, sect, "hall", seat))
    assert PH.table(world, sect) == before and not any(world.entity(i).kind == "pill" for i in world.targets(me, "owns"))
    [fact] = world.facts(predicate="stole")
    assert fact.object == sect
    assert standing(world, sect, me).score < 0
    guard, _ = T.guard_of(world, sect)
    assert any(m.feeling == "hatred" for m in world.memories(guard, about=me))


def test_a_garden_theft_takes_the_oldest_herbs_first(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_night(world)
    monkeypatch.setattr(T, "BOUNDS", (1.0, 1.0))
    herbs = sorted(PH.garden(world, sect))
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {herbs[0]: [5, 0], herbs[1]: [1, 1]}})
    commit(world, T.steal_events(world, me, sect, "garden", seat))
    taken = sorted(H.herb_info(h) for h in H.herbs_of(world, me))
    assert taken == sorted([(herbs[1], 1), (herbs[0], 0), (herbs[0], 0)])
    assert PH.garden(world, sect)[herbs[0]][0] == 3 and PH.garden(world, sect)[herbs[1]][0] == 0


def test_a_hundred_year_herb_is_guarded_by_a_beast_that_must_be_beaten_first(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_night(world)
    name = sorted(PH.garden(world, sect))[0]
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {name: [4, 2]}})
    assert "guards" in T.steal_block(world, me, sect, "garden", seat)
    [met] = T.guardian_events(world, me, sect, seat)
    beast = met.actors[1]
    assert world.entity(beast).data["beast"] and world.entity(beast).data["guardian_of"] == sect
    commit(world, [Event("duel_ended", (me, beast), seat, {"result": "won", "mode": "encounter", "verdict": "kill",
                                                             "by": "player", "silver": 0, "crippled": None,
                                                             "loot": [], "insight": 0.0, "life_and_death": False,
                                                             "fragment": None, "purpose": None, "killed": True,
                                                             "left_for_dead": False, "duel": None, "reason": "broken"})])
    commit(world, T.nightfall_events(world, me, seat))  # the fight took a watch: the next dark will do
    assert T.steal_block(world, me, sect, "garden", seat) is None


def test_a_secret_scroll_can_be_stolen(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_night(world)
    monkeypatch.setattr(T, "BOUNDS", (1.0, 1.0))
    commit(world, T.steal_events(world, me, sect, "scroll", seat))
    [scroll] = RT.scrolls_of(world, me)
    assert scroll.data["source"] == "stolen" and scroll.data["faction"] == sect
    assert scroll.data["key"] in RT.secret_recipes(world, sect)


def test_a_thief_knows_a_hall_only_after_a_look(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    assert not T.knows_hall(world, me, sect)
    to_night(world)
    assert T.look_block(world, me, sect, seat) is None
    commit(world, T.look_events(world, me, sect, seat))
    assert T.knows_hall(world, me, sect)
    assert "know" in T.look_block(world, me, sect, seat)
```

- [ ] **Step 2: Write the new modules**

`systems/hall_theft.py`:
```python
"""Stealing from a sect's garden or pill hall (phase 5c spec 2.4), by night, at its seat.

The chance is `0.5 + 0.1 x (the thief's realm - the guard's realm)`, bounded 0.1-0.9; the guard is the strongest
of the sect standing at its seat, or a seeded watchman. A garden holding a hundred-year herb keeps a guardian
beast, fought first. Caught, the thief is known for it (the 3b crime `stole`) and the goods go back; unseen, the
sect knows only that someone came. A thief sees what a garden or a hall holds only after a look by night.
"""

import systems.encounters as encounters
import systems.herbs as H
import systems.lives as lives
import systems.pill_hall as PH
import systems.recipe_trade as RT
from systems import factions as F
from systems import halls
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from world.events import Event, Witness, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

NIGHT = 3                  # the fourth watch of the day
BASE, PER_REALM, BOUNDS = 0.5, 0.1, (0.1, 0.9)
HERBS_TAKEN, PILLS_TAKEN = 3, 2
WATCHMAN = (1, 3)          # a seeded guard's realm, where no one of the sect stands
THEFT_WEIGHT = 1.5
TARGETS = ("garden", "hall", "scroll")
GUARDIAN_GONE = 4          # watches a beaten guardian stays away: the fight itself takes one


def night(world) -> bool:
    return world.time % 4 == NIGHT


def nightfall_events(world, person: int, place) -> list[Event]:
    return [Event("waited_for_night", (person,), place, {"watches": (NIGHT - world.time % 4) % 4 or 4})]


@effect("waited_for_night")
def _waited(world, event) -> None:
    from systems.time import advance
    advance(world, event.data["watches"])


def guard_of(world, faction: int) -> tuple[int | None, int]:
    """(the guard, their realm): the strongest of the sect at its seat, else a seeded watchman (None)."""
    seat = world.entity(faction).data.get("seat")
    staff = [p for p in halls.staff_at(world, faction, seat)] if seat is not None else []
    staff = [p for p in staff if not world.entity(p).data.get("is_player")]
    if staff:
        best = min(staff, key=lambda p: (-realm_index(world.entity(p).data.get("realm", "mortal")), p))
        return best, realm_index(world.entity(best).data.get("realm", "mortal"))
    return None, rng_for(world.world_seed, f"watchman:{faction}").randint(*WATCHMAN)


def chance(world, thief: int, faction: int) -> float:
    realm = realm_index(world.entity(thief).data.get("realm", "mortal"))
    return max(BOUNDS[0], min(BOUNDS[1], BASE + PER_REALM * (realm - guard_of(world, faction)[1])))


def at_seat(world, faction: int, place) -> bool:
    return world.entity(faction).data.get("seat") == place


def knows_hall(world, person: int, faction: int) -> bool:
    """A sect's hall and garden are known to its own, and to a thief who has looked (spec 8)."""
    found = F.membership(world, person, faction)
    if found is not None and found[1].get("status", "member") == "member":
        return True
    return faction in (world.entity(person).data.get("surveyed") or [])


# --- a look by night ------------------------------------------------------------------------------------------

def look_block(world, person: int, faction: int, place) -> str | None:
    if not at_seat(world, faction, place) or not (PH.keeps_hall(world, faction) or PH.keeps_garden(world, faction)):
        return "There is nothing of theirs to look at here."
    if not night(world):
        return "Wait for the dark."
    if knows_hall(world, person, faction):
        return "You know what they keep."
    return None


def look_events(world, person: int, faction: int, place) -> list[Event]:
    return [Event("hall_surveyed", (person,), place, {"faction": faction})]


@effect("hall_surveyed")
def _surveyed(world, event) -> None:
    person = event.actors[0]
    world.update_data(person, surveyed=(world.entity(person).data.get("surveyed") or []) + [event.data["faction"]])


# --- the guardian beast ---------------------------------------------------------------------------------------

def needs_guardian(world, person: int, faction: int) -> bool:
    """The garden's guardian stands between the thief and a hundred-year herb, until beaten (for a day)."""
    beaten = world.entity(person).data.get("guardian_beaten") or {}
    return PH.guarded(world, faction) and not (beaten.get("faction") == faction
                                               and world.time < beaten.get("until", 0))


def guardian_events(world, person: int, faction: int, place) -> list[Event]:
    """The guardian comes out of the dark: a beast encounter with it (the engine runs the fight)."""
    region = region_of(world, place)
    beast = encounters.make_roamer(world, region, "beast", encounters._free_roamer_slot(world, region), 0.7)
    world.update_data(beast, guardian_of=faction)
    return encounters.encounter_events(person, beast, place, "beast", 0)


@listen("duel_ended")
def _guardian_beaten(world, event, event_id: int) -> None:
    player, opponent = event.actors
    faction = world.entity(opponent).data.get("guardian_of")
    if faction is not None and event.data.get("result") == "won":
        world.update_data(player, guardian_beaten={"faction": faction, "until": world.time + GUARDIAN_GONE})


# --- the theft ------------------------------------------------------------------------------------------------

def steal_block(world, person: int, faction: int, target: str, place) -> str | None:
    if target not in TARGETS or not at_seat(world, faction, place):
        return "There is nothing of theirs to take here."
    if not night(world):
        return "Wait for the dark."
    if target == "garden":
        if not any(count > 0 for count, _ in PH.garden(world, faction).values()):
            return "Their garden is bare."
        if needs_guardian(world, person, faction):
            return "Something guards the garden."
    elif target == "hall":
        if not any(v > 0 for v in PH.table(world, faction).values()):
            return "Their pill hall is empty."
    elif not PH.keeps_hall(world, faction):
        return "They keep no pill hall."
    return None


def _loot(world, faction: int, target: str) -> list:
    """What a thief carries off: the oldest herbs, the strongest pills, or a secret scroll."""
    if target == "garden":
        growing = sorted(((grade, name) for name, (count, grade) in PH.garden(world, faction).items() if count > 0),
                         reverse=True)
        out = []
        for grade, name in growing:
            count = PH.garden(world, faction)[name][0]
            out += [[name, grade]] * min(count, HERBS_TAKEN - len(out))
            if len(out) >= HERBS_TAKEN:
                break
        return out
    if target == "hall":
        stocked = sorted(((int(k.split(":")[0]), k.split(":")[1], v) for k, v in PH.table(world, faction).items()
                          if v > 0), key=lambda s: (-s[0], s[1]))
        out = []
        for grade, kind, count in stocked:
            out += [[grade, kind]] * min(count, PILLS_TAKEN - len(out))
        return out[:PILLS_TAKEN]
    return [RT.secret_recipes(world, faction)[0]]


def steal_events(world, person: int, faction: int, target: str, place) -> list[Event]:
    roll = rng_for(world.world_seed, f"theft:{person}:{faction}:{world.time}").random()
    success = roll < chance(world, person, faction)
    guard, _ = guard_of(world, faction)
    witnesses = (Witness(guard, "hatred", 0.8),) if not success and guard is not None else ()
    return [Event("hall_theft", (person,) + ((guard,) if guard is not None else ()), place,
                  {"faction": faction, "target": target, "caught": not success,
                   "loot": _loot(world, faction, target) if success else [],
                   "season": lives.current_season(world)}, witnesses=witnesses)]


@effect("hall_theft")
def _theft(world, event) -> None:
    person, d = event.actors[0], event.data
    if d["caught"]:
        return
    faction = d["faction"]
    if d["target"] == "garden":
        for name, grade in d["loot"]:
            PH.take_from_garden(world, faction, name, d["season"])
            H.make_herb(world, name, grade, person, "stolen")
    elif d["target"] == "hall":
        stocked = PH.table(world, faction)
        for grade, kind in d["loot"]:
            stocked[f"{grade}:{kind}"] -= 1
            PH.make_hall_pill(world, person, faction, grade, kind, "stolen")
        world.update_data(faction, pill_hall={k: v for k, v in stocked.items() if v > 0}, pill_hall_at=d["season"])
    else:
        RT.make_scroll(world, person, d["loot"][0], "stolen", faction)


@listen("hall_theft")
def _theft_news(world, event, event_id: int) -> None:
    person, d = event.actors[0], event.data
    where = place_name(world, event.place)
    if d["caught"]:  # the 3b crime, as the armoury's theft is (5a)
        record_fact(world, person, "stole", d["faction"], place=event.place, source_event=event_id,
                    weight=THEFT_WEIGHT, variant=make_variant("stole", person, d["faction"], place=where))
    else:  # someone came in the night: a deed without a doer
        variant = make_variant("robbed_hall", None, d["faction"], place=where)
        variant.update(what=d["target"])
        record_fact(world, d["faction"], "robbed_hall", None, place=event.place, source_event=event_id, weight=1.0,
                    variant=variant)
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_hall_theft.py`
Expected: `2 failed, 8 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5c_task3.py`:
```python
"""Phase 5c, Task 3: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/duties.py', r'''REST_KINDS = frozenset({"rested", "cultivated", "practised"})
''', r'''REST_KINDS = frozenset({"rested", "cultivated", "practised"})
ALCHEMY_DAYS = 30          # phase 5c: herbs brought or a pill refined, within a month
BRING = (2, 4)


def alchemy_task(world, rng, player: int, faction: int) -> dict:
    """Bring N herbs of a kind that grows on the sect's land, or refine one pill of a recipe the player knows."""
    import systems.alchemy as A
    import systems.herbs as H
    known = [r for r, _ in A.known_recipes(world, player)]
    seat = world.entity(faction).data["seat"]
    if known and rng.random() < 0.5:
        return {"task": "refine", "recipe": rng.choice(known), "town": seat}
    growing = H.growing(world.entity(seat).data["terrain"]) or sorted(H.HERBS)
    return {"task": "bring", "herb": rng.choice(growing), "count": rng.randint(*BRING), "town": seat}


def alchemy_items(world, player: int, d: dict) -> list[int]:
    """What the player would hand in for an alchemy duty now, or nothing if they have not enough."""
    if d.get("task") == "bring":
        import systems.herbs as H
        found = [h.id for h in H.herbs_of(world, player) if H.herb_info(h)[0] == d["herb"]]
        return found[:d["count"]] if len(found) >= d["count"] else []
    import systems.pills as P
    made = [p.id for p in P.pills_of(world, player) if p.data.get("recipe") == d["recipe"]
            and p.data.get("maker") == player and p.created_at > d["issued_at"]]
    return made[:1]
''')
edit('systems/duties.py', r'''    elif kind == "guard":
        data.update(town=halls.seat_of(world, faction), days=5 * data["difficulty"])''', r'''    elif kind == "guard":
        data.update(town=halls.seat_of(world, faction), days=5 * data["difficulty"])
    elif kind == "alchemy":  # phase 5c: only where the sect keeps a pill hall
        data.update(alchemy_task(world, rng, player, faction))''')
edit('systems/duties.py', r'''    days = data["days"] + 7 if kind == "guard" else _road_days(world, here, data) + 7''', r'''    days = data["days"] + 7 if kind == "guard" else ALCHEMY_DAYS if kind == "alchemy" \
        else _road_days(world, here, data) + 7''')
edit('systems/duties.py', r'''    if world.time > d["deadline"]:
        return "failed"
    if d["kind"] in ("deliver", "escort")''', r'''    if world.time > d["deadline"]:
        return "failed"
    if d["kind"] == "alchemy" and d["town"] in world.targets(player, "located_in") and alchemy_items(world, player, d):
        return "done"
    if d["kind"] in ("deliver", "escort")''')
edit('systems/duties.py', r'''    return [Event("duty_done", (player,), place, {"duty": duty.id, "faction": d["faction"], "kind": d["kind"],
                                                  "merit": 10 * d["difficulty"], "silver": 5 * d["difficulty"],
                                                  "release": d.get("release", False)}, witnesses=witnesses)]''', r'''    items = alchemy_items(world, player, d) if d["kind"] == "alchemy" else []
    return [Event("duty_done", (player,), place, {"duty": duty.id, "faction": d["faction"], "kind": d["kind"],
                                                  "merit": 10 * d["difficulty"], "silver": 5 * d["difficulty"],
                                                  "release": d.get("release", False), "items": items},
                  witnesses=witnesses)]''')
edit('systems/duties.py', r'''    world.update_data(player, silver=int(world.entity(player).data.get("silver", 0)) + d["silver"], duty=None)
    world.update_data(d["duty"], status="done")''', r'''    world.update_data(player, silver=int(world.entity(player).data.get("silver", 0)) + d["silver"], duty=None)
    world.update_data(d["duty"], status="done")
    for item in d.get("items") or []:  # phase 5c: the herbs or the pill handed in
        world.unrelate(player, "owns", item)
        world.update_data(item, used=True)''')
edit('systems/world_clock.py', r'''import systems.recipe_trade  # noqa: E402,F401  phase 5c: recipe scrolls bought, given, taught and sold
''', r'''import systems.recipe_trade  # noqa: E402,F401  phase 5c: recipe scrolls bought, given, taught and sold
import systems.hall_theft  # noqa: E402,F401  phase 5c: gardens and halls robbed by night
''')
print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5c_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_hall_theft.py`
Expected: `10 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1315 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: alchemy duties, and a sect's garden and hall robbed by night - the guard, the guardian beast, and a deed without a doer"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 4: Physicians, famous doctors, the healer and the poisoner for hire

Every town has a physician, made the first time they are paid (ruling 11): a wound treated heals three times as fast, a poison of grade 3 or less is cured, and five silver names what is in the blood. A famous doctor wanders each block of 4 x 2 regions; asking after one in a town tells where they were last seen, and they cure any poison, broken meridians, a permanent wound (ruling 12) or, from Task 6, a control pill, on their whim: gold, a thousand-year herb, the orthodox only, or a game of go. The player treats the sick with a fitting pill or two healing herbs and a roll (ruling 13); five healings make a town's healer, who is sometimes brought someone sick. An unorthodox soul who believes the player poisons may offer silver for a poisoning (ruling 14).

**Files:**
- Create: `systems/physic.py`
- Create: `tests/test_physic.py`
- Modify (by `.patches/5c_task4.py`): `systems/world_clock.py`, `systems/attitude.py`, `systems/law.py`

**Interfaces:**
- Consumes: 5b's `toxins` (`poison`, `add_poison`, `cure`, `LETHAL_GRADE`), `pills`, `herbs`, `alchemy.level`; 3c's `founding.make_person`; 4h's `scheming.poisons_of`, `poison_grade`; 3a's `attitude`, `beliefs`; 3b's `reputation`.
- Produces:
  - `PY` (systems/physic.py): `TREAT_PRICE`, `CURE_PRICE`, `READ_PRICE`, `CURE_GRADE`, `FASTER`, `BLOCK`, `EPITHETS`, `WHIMS`, `DOCTOR_GOLD`, `DOCTOR_CURES`, `CURE_HOOKS`, `HEAL_ROLL`, `HEAL_PER_LEVEL`, `HEAL_BOUNDS`, `HEALING_ELEMENTS`, `HEALER_AT`, `PATIENT_CHANCE`, `UNFIT`, `POISON_FAME`, `CONTRACT_OFFER`, `CONTRACT_PAY`, `CONTRACT_DAYS`, `FIND_CHANCE`; `physician_path(town)`, `physician(world, town)`, `treatable(body, now)`, `treat_price(severity)`, `cure_price(grade)`, `clinic_block(world, place)`, `treat_block(world, person, injury_id, place)`, `treat_events(world, person, injury_id, place)`, `curable(body)`, `cure_block(world, person, place)`, `cure_events(world, person, place)`, `read_block(world, person, place)`, `read_events(world, person, place)`, `block_of(x, y)`, `doctor_path(block)`, `doctor_spec(world, block)`, `seen_at(world, block, season)`, `ask_events(world, person, place)`, `ensure_doctor(world, block, town)`, `doctors_here(world, place)`, `doctor_cures(world, person)`, `terms_block(world, person, doctor, place)`, `thousand_year_herb(world, person)`, `orthodox(world, person, place)`, `go_events(world, person, doctor, place)`, `doctor_events(world, person, doctor, what, place)`, `ailment(world, npc)`, `remedy(world, person, npc)`, `heal_block(world, person, npc, place)`, `heal_chance(world, person)`, `heal_events(world, person, npc, place)`, `healer_of(world, person)`, `patient_events(world, person, town)`, `unorthodox(world, npc)`, `knows_you_poison(world, npc, person)`, `contract_offer(world, npc, person)`, `contract_events(world, person, offer, place)`, `contract_poison_block(world, person, target, place)`, `contract_poison_events(world, person, target, place)`, `fee_block(world, person, client)`, `fee_events(world, person, client, place)`, `contract_lapsed(world, person)`, `void_events(world, person, place)`; events `asked_doctor`, `body_read`, `contract_paid`, `contract_poisoned`, `contract_taken`, `contract_void`, `doctor_cured`, `go_played`, `healed`, `patient_brought`, `physician_cured`, `physician_treated`.
  - `attitude.JUDGEMENT['healed']`, `['poisoned_for_hire']`; `law.SCHEMES` gains `poisoned_for_hire`.

- [ ] **Step 1: Write the tests**

`tests/test_physic.py`:
```python
import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.herbs as H
import systems.lives as lives
import systems.physic as PY
import systems.toxins as X
from engine.game import Game
from systems import factions as F
from systems.attitude import attitude
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.law import SCHEMES
from systems.purse import silver_of
from world.body import add_injury
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


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:physic:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def hurt(world, person, severity=3, permanent=False):
    body = load_body(world, person)
    injury = add_injury(body, "left arm", "cut", severity, world.time, "a test", permanent=permanent)
    save_body(world, person, body)
    return injury.id


# --- the town physician ---------------------------------------------------------------------------------------

def test_the_physician_hastens_a_wound_threefold_for_silver(game):
    world, me, town = game.world, game.player.id, game.place.id
    injury = hurt(world, me, 3)
    left = next(i for i in load_body(world, me).injuries if i.id == injury).heals_at - world.time
    assert world.entity_by_seed(PY.physician_path(town)) is None
    assert PY.treat_block(world, me, injury, town) is None
    assert world.entity_by_seed(PY.physician_path(town)) is None  # asking makes no one
    commit(world, PY.treat_events(world, me, injury, town))
    after = next(i for i in load_body(world, me).injuries if i.id == injury).heals_at - world.time
    assert after == max(1, left // PY.FASTER)
    assert silver_of(world, me) == 5000 - PY.treat_price(3)
    doctor = world.entity_by_seed(PY.physician_path(town))
    assert doctor.data["occupation"] == "physician" and town in world.targets(doctor.id, "located_in")
    assert silver_of(world, doctor.id) >= PY.treat_price(3)  # paid, and met


def test_a_permanent_wound_is_beyond_the_physician(game):
    world, me, town = game.world, game.player.id, game.place.id
    injury = hurt(world, me, 5, permanent=True)
    assert PY.treat_block(world, me, injury, town) is not None


def test_the_physician_cures_a_weak_poison_but_not_a_strong_one(game):
    world, me, town = game.world, game.player.id, game.place.id
    X.poison(world, me, 2, 20, "a hidden needle")
    assert PY.cure_block(world, me, town) is None
    commit(world, PY.cure_events(world, me, town))
    assert not load_body(world, me).poisons and silver_of(world, me) == 5000 - PY.cure_price(2)
    X.poison(world, me, 5, 20, "a hidden needle")
    assert "no poison of yours" in PY.cure_block(world, me, town)


def test_reading_the_body_names_its_poisons(game):
    world, me, town = game.world, game.player.id, game.place.id
    X.poison(world, me, 3, 20, "a hidden needle")
    assert not load_body(world, me).poisons[0]["named"]
    commit(world, PY.read_events(world, me, town))
    assert load_body(world, me).poisons[0]["named"] and silver_of(world, me) == 5000 - PY.READ_PRICE


# --- famous doctors ---------------------------------------------------------------------------------------------

def test_a_doctor_wanders_their_block_and_is_made_on_the_first_ask(game):
    world, me, town = game.world, game.player.id, game.place.id
    here = world.entity(town).data
    block = PY.block_of(here["x"], here["y"])
    spec = PY.doctor_spec(world, block)
    assert spec == PY.doctor_spec(world, block) and spec["whim"] in PY.WHIMS
    assert spec["title"].startswith("the ") and " Doctor of " in spec["title"]
    assert world.entity_by_seed(PY.doctor_path(block)) is None
    commit(world, PY.ask_events(world, me, town))
    doctor = world.entity_by_seed(PY.doctor_path(block))
    assert doctor.name == spec["name"] and doctor.data["doctor"]["whim"] == spec["whim"]
    x, y, i = PY.seen_at(world, block, lives.current_season(world))
    where = world.targets(doctor.id, "located_in")[0]
    assert (world.entity(where).data["x"], world.entity(where).data["y"], world.entity(where).data["index"]) == (x, y, i)
    seen = world.entity(me).data["doctors_seen"][PY.doctor_path(list(block))]
    assert seen["season"] == lives.current_season(world)
    from systems.beliefs import known_people
    assert doctor.id in known_people(world, me)  # heard of, so named


def a_doctor(game, whim):
    world = game.world
    doctor = someone(game, f"doctor-{whim}", occupation="famous doctor", realm="first-rate",
                     doctor={"title": "the Test Doctor", "whim": whim, "home": [0, 0], "block": [0, 0]})
    return doctor


def test_a_doctor_cures_what_no_physician_can_on_their_terms(game):
    world, me, town = game.world, game.player.id, game.place.id
    doctor = a_doctor(game, "gold")
    X.poison(world, me, 5, 40, "a hidden needle")
    hurt(world, me, 5, permanent=True)
    body = load_body(world, me)
    body.meridians["Lung"].state = "severed"
    save_body(world, me, body)
    assert set(PY.doctor_cures(world, me)) >= {"poison", "meridian", "injury"}
    assert PY.terms_block(world, me, doctor, town) is None
    for what in ("poison", "meridian", "injury"):
        commit(world, PY.doctor_events(world, me, doctor, what, town))
    body = load_body(world, me)
    assert not body.poisons and body.meridians["Lung"].state == "open"
    assert not any(i.permanent for i in body.injuries)
    assert silver_of(world, me) == 5000 - 3 * PY.DOCTOR_GOLD


def test_the_whims_of_doctors(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    task = a_doctor(game, "task")
    assert "thousand-year" in PY.terms_block(world, me, task, town)
    H.make_herb(world, "ginseng", 3, me)
    assert PY.terms_block(world, me, task, town) is None
    righteous = a_doctor(game, "righteous")
    assert PY.terms_block(world, me, righteous, town) is None
    cult = next(f for f in F.ensure_roster(world) if world.entity(f).data["type"] == "demonic_cult")
    world.relate(me, cult, "member_of", 0, {"role": "member", "status": "member"})
    assert "orthodox" in PY.terms_block(world, me, righteous, town)
    odd = a_doctor(game, "eccentric")
    assert "go" in PY.terms_block(world, me, odd, town)
    body = load_body(world, me)
    body.physique["comprehension"] = 20
    save_body(world, me, body)
    commit(world, PY.go_events(world, me, odd, town))
    assert PY.terms_block(world, me, odd, town) is None


# --- the player as healer ---------------------------------------------------------------------------------------

def test_a_healing_pill_treats_the_wounded_and_they_are_grateful(game):
    world, me, town = game.world, game.player.id, game.place.id
    sick = someone(game, "sick")
    assert PY.heal_block(world, me, sick, town) == "Nothing ails them."
    hurt(world, sick, 3)
    assert "nothing fit" in PY.heal_block(world, me, sick, town)
    pill = A.make_pill(world, me, A.recipe_entity(world, "wood_healing"), 1, 0.8)
    assert PY.heal_block(world, me, sick, town) is None
    commit(world, PY.heal_events(world, me, sick, town))
    assert PY.ailment(world, sick) is None and pill not in world.targets(me, "owns")
    assert any(m.feeling == "grateful" for m in world.memories(sick, about=me))
    [fact] = world.facts(predicate="healed")
    assert fact.subject == me and fact.object == sick


def test_an_antidote_must_be_as_strong_as_the_poison(game):
    world, me, town = game.world, game.player.id, game.place.id
    sick = someone(game, "poisoned")
    X.poison(world, sick, 3, 40, "a bad well")
    A.make_pill(world, me, A.recipe_entity(world, "metal_antidote"), 2, 0.8)
    assert "nothing fit" in PY.heal_block(world, me, sick, town)
    A.make_pill(world, me, A.recipe_entity(world, "metal_antidote"), 3, 0.8)
    commit(world, PY.heal_events(world, me, sick, town))
    assert PY.ailment(world, sick) is None and sick not in (world.get_meta("poisoned") or [])


def test_herbs_treat_on_a_roll_of_the_alchemy_level(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    sick = someone(game, "herbs")
    hurt(world, sick, 2)
    for _ in range(2):
        H.make_herb(world, "willow bark", 0, me)
    assert "nothing fit" in PY.heal_block(world, me, sick, town)  # herbs one does not know are no remedy
    H.learn(world, me, ["willow bark"])
    monkeypatch.setattr(PY, "HEAL_BOUNDS", (0.0, 0.0))
    commit(world, PY.heal_events(world, me, sick, town))
    assert PY.ailment(world, sick) == "wound" and not H.herbs_of(world, me)


def test_five_healings_make_a_towns_healer_who_is_brought_the_sick(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    for n in range(PY.HEALER_AT):
        sick = someone(game, f"patient{n}")
        hurt(world, sick, 1)
        A.make_pill(world, me, A.recipe_entity(world, "wood_healing"), 1, 0.8)
        commit(world, PY.heal_events(world, me, sick, town))
    assert PY.healer_of(world, me) == [town]
    monkeypatch.setattr(PY, "PATIENT_CHANCE", 1.0)
    [brought] = PY.patient_events(world, me, town)
    commit(world, [brought])
    patient = world.entity(me).data["patient"]
    assert PY.ailment(world, patient) is not None and town in world.targets(patient, "located_in")


def test_the_hostile_will_not_be_treated(game):
    from world.events import Event, Witness
    world, me, town = game.world, game.player.id, game.place.id
    sick = someone(game, "hater")
    hurt(world, sick, 2)
    A.make_pill(world, me, A.recipe_entity(world, "wood_healing"), 1, 0.8)
    commit(world, [Event("slight", (me, sick), town, {}, witnesses=(Witness(sick, "hatred", 1.0),))])
    assert "will not" in PY.heal_block(world, me, sick, town)


# --- poison for hire ----------------------------------------------------------------------------------------------

def a_client(game, monkeypatch):
    world, me = game.world, game.player.id
    client = someone(game, "client", occupation="bandit", traits=["cunning", "greedy"])
    mark = someone(game, "mark")
    monkeypatch.setattr(PY, "CONTRACT_OFFER", 1.0)
    return client, mark


def test_only_the_unorthodox_who_know_you_poison_offer_a_contract(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    client, mark = a_client(game, monkeypatch)
    assert PY.contract_offer(world, client, me) is None
    from systems.beliefs import believe
    fact = record_fact(world, me, "poison_body", None, place=town, variant=make_variant("poison_body", me, None))
    believe(world, client, fact, make_variant("poison_body", me, None), None, 1.0, 0, "witness")
    offer = PY.contract_offer(world, client, me)
    assert offer["client"] == client and offer["target"] != client
    honest = someone(game, "honest")
    believe(world, honest, fact, make_variant("poison_body", me, None), None, 1.0, 0, "witness")
    assert PY.contract_offer(world, honest, me) is None


def test_a_hired_poisoning_kills_with_a_strong_poison_and_is_paid_for(game, monkeypatch):
    from systems.scheming import buy_poison_events  # noqa: F401  (the vial's effect)
    world, me, town = game.world, game.player.id, game.place.id
    client, mark = a_client(game, monkeypatch)
    offer = {"client": client, "target": mark, "silver": 200}
    commit(world, PY.contract_events(world, me, offer, town))
    assert "no poison" in PY.contract_poison_block(world, me, mark, town)
    vial = world.add_entity("treasure", "a vial of black lotus", {"kind": "poison", "value": 50, "used": False})
    world.relate(me, vial, "owns")
    assert PY.fee_block(world, me, client) == "The job is not done."
    assert PY.contract_poison_block(world, me, mark, town) is None
    monkeypatch.setattr(PY, "FIND_CHANCE", 1.0)
    commit(world, PY.contract_poison_events(world, me, mark, town))
    assert world.entity(mark).data.get("dead")
    assert world.facts(predicate="poisoned_for_hire") and "poisoned_for_hire" in SCHEMES  # traced: a crime
    world.update_data(client, silver=500)
    assert PY.fee_block(world, me, client) is None
    commit(world, PY.fee_events(world, me, client, town))
    assert silver_of(world, me) == 5200 and world.entity(me).data["contract"] is None


def test_a_contract_lapses_with_its_deadline(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    client, mark = a_client(game, monkeypatch)
    commit(world, PY.contract_events(world, me, {"client": client, "target": mark, "silver": 100}, town))
    assert not PY.contract_lapsed(world, me)
    world.set_time(world.time + PY.CONTRACT_DAYS * 4 + 1)
    assert PY.contract_lapsed(world, me)
    commit(world, PY.void_events(world, me, town))
    assert world.entity(me).data["contract"] is None


def test_those_who_hear_of_a_healing_think_better_of_the_healer(game):
    world, me, town = game.world, game.player.id, game.place.id
    sick = someone(game, "healed")
    hurt(world, sick, 2)
    onlooker = someone(game, "onlooker")
    before = attitude(world, onlooker, me).score
    A.make_pill(world, me, A.recipe_entity(world, "wood_healing"), 1, 0.8)
    commit(world, PY.heal_events(world, me, sick, town))
    assert attitude(world, onlooker, me).score > before
```

- [ ] **Step 2: Write the new modules**

`systems/physic.py`:
```python
"""Physicians, famous doctors, the healer and the poisoner for hire (phase 5c spec 5.1-5.3).

Every town has a physician (a seeded person, made the first time they are paid): they treat a wound for silver
so it heals three times as fast, cure a weak poison, and for five silver read the body and name its poisons.
Famous doctors, one to each block of eight regions, wander; asking after one in a town tells where they were
last seen. They cure what no physician can, on their own terms. The player may treat the sick, with a fitting
pill or with herbs and a roll, and five healings in a town make them its healer; an unorthodox soul who believes
the player knows poison may offer silver for a poisoning.
"""

import systems.alchemy as A
import systems.herbs as H
import systems.lives as lives
import systems.pills as P
import systems.toxins as X
from systems import factions as F
from systems.attitude import attitude, is_bandit
from systems.beliefs import apparent_to, knowledge_of
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.founding import make_person
from systems.purse import silver_of
from systems.reputation import reputation
from world.body import body_of, heal_watches, settle
from world.events import Event, Witness, effect, listen
from world.gen.materialize import ensure_town, people_at, region_label, town_label
from world.gen.names import person_name
from world.gen.region import region_spec
from world.seed import rng_for

TREAT_PRICE, CURE_PRICE, READ_PRICE = 10, 20, 5  # x severity squared, x grade squared, flat
CURE_GRADE = 3             # the strongest poison a town physician can cure
FASTER = 3
BLOCK = (4, 2)             # a famous doctor's wandering ground: four regions by two
EPITHETS = ("Ghost", "Divine", "Poison-Eating", "Needle", "Hundred-Herb", "Crane-Hand", "Sleepless", "Laughing")
WHIMS = ("gold", "task", "righteous", "eccentric")
DOCTOR_GOLD = 1000
DOCTOR_CURES = ("poison", "meridian", "injury")
CURE_HOOKS: dict = {}      # what else a famous doctor cures: name -> (block(world, person), apply(world, person))
HEAL_ROLL, HEAL_PER_LEVEL, HEAL_BOUNDS = 0.3, 0.1, (0.1, 0.9)
HEALING_ELEMENTS = frozenset({"wood", "earth", "water"})
HEALER_AT = 5
PATIENT_CHANCE = 0.2
UNFIT = frozenset({"hostile", "hateful"})
POISON_FAME = frozenset({"poison_body", "poisoner", "poisoned_for_hire"})
CONTRACT_OFFER = 0.3       # chance a fitting soul offers, once a season
CONTRACT_PAY = (100, 400)
CONTRACT_DAYS = 60
FIND_CHANCE = 0.15         # a hired poisoning traced to its poisoner


def _pay(world, person: int, amount: int, to: int | None = None) -> None:
    world.update_data(person, silver=silver_of(world, person) - amount)
    if to is not None:
        world.update_data(to, silver=silver_of(world, to) + amount)


# --- the town physician -------------------------------------------------------------------------------------

def physician_path(town: int) -> str:
    return f"physician:{town}"


def physician(world, town: int) -> int:
    """The town's physician, made the first time they are paid (never for a menu: reads never write)."""
    found = world.entity_by_seed(physician_path(town))
    if found is not None:
        return found.id
    return make_person(world, physician_path(town), town, occupation="physician", age=rng_for(
        world.world_seed, f"{physician_path(town)}/age").randint(40, 70))


def treatable(body, now: int) -> list:
    return sorted((i for i in body.injuries if not i.permanent and i.heals_at and i.heals_at > now),
                  key=lambda i: (-i.severity, i.id))


def treat_price(severity: int) -> int:
    return TREAT_PRICE * severity ** 2


def cure_price(grade: int) -> int:
    return CURE_PRICE * grade ** 2


def clinic_block(world, place) -> str | None:
    entity = world.entity(place)
    return None if entity is not None and entity.kind == "town" else "There is no physician here."


def treat_block(world, person: int, injury_id: int, place) -> str | None:
    if clinic_block(world, place):
        return clinic_block(world, place)
    injury = next((i for i in treatable(load_body(world, person), world.time) if i.id == injury_id), None)
    if injury is None:
        return "There is nothing there a physician can hasten."
    if silver_of(world, person) < treat_price(injury.severity):
        return f"The physician asks {treat_price(injury.severity)} silver."
    return None


def treat_events(world, person: int, injury_id: int, place) -> list[Event]:
    injury = next(i for i in treatable(load_body(world, person), world.time) if i.id == injury_id)
    return [Event("physician_treated", (person, physician(world, place)), place, {"injury": injury_id, "location": injury.location,
                                                          "price": treat_price(injury.severity)})]


@effect("physician_treated")
def _treated(world, event) -> None:
    person, d = event.actors[0], event.data
    _pay(world, person, d["price"], event.actors[1])
    body = load_body(world, person)
    for injury in body.injuries:
        if injury.id == d["injury"] and injury.heals_at and injury.heals_at > world.time:
            injury.heals_at = world.time + max(1, (injury.heals_at - world.time) // FASTER)
    save_body(world, person, body)


def curable(body) -> int | None:
    """The worst poison a town physician can cure in this body, or None."""
    grades = [p["grade"] for p in body.poisons if p["grade"] <= CURE_GRADE]
    return max(grades) if grades else None


def cure_block(world, person: int, place) -> str | None:
    if clinic_block(world, place):
        return clinic_block(world, place)
    body = load_body(world, person)
    grade = curable(body)
    if grade is None:
        return "The physician can cure no poison of yours." if body.poisons else "There is no poison in you."
    if silver_of(world, person) < cure_price(grade):
        return f"The physician asks {cure_price(grade)} silver."
    return None


def cure_events(world, person: int, place) -> list[Event]:
    grade = curable(load_body(world, person))
    return [Event("physician_cured", (person, physician(world, place)), place, {"grade": grade,
                                                                                 "price": cure_price(grade)})]


@effect("physician_cured")
def _cured(world, event) -> None:
    person, d = event.actors[0], event.data
    _pay(world, person, d["price"], event.actors[1])
    X.cure(world, person, d["grade"])


def read_block(world, person: int, place) -> str | None:
    if clinic_block(world, place):
        return clinic_block(world, place)
    if silver_of(world, person) < READ_PRICE:
        return f"The physician asks {READ_PRICE} silver."
    return None


def read_events(world, person: int, place) -> list[Event]:
    return [Event("body_read", (person, physician(world, place)), place, {"price": READ_PRICE})]


@effect("body_read")
def _read(world, event) -> None:
    person = event.actors[0]
    _pay(world, person, event.data["price"], event.actors[1])
    body = load_body(world, person)
    body.poisons = [{**p, "named": True} for p in body.poisons]
    save_body(world, person, body)


# --- famous doctors -------------------------------------------------------------------------------------------

def block_of(x: int, y: int) -> tuple[int, int]:
    return x // BLOCK[0], y // BLOCK[1]


def doctor_path(block) -> str:
    return f"doctor:{block[0]}:{block[1]}"


def doctor_spec(world, block) -> dict:
    """A block's famous doctor, from the seed: name, title, whim and home region."""
    rng = rng_for(world.world_seed, f"{doctor_path(block)}/spec")
    home = (block[0] * BLOCK[0] + rng.randrange(BLOCK[0]), block[1] * BLOCK[1] + rng.randrange(BLOCK[1]))
    surname, given = person_name(rng_for(world.world_seed, doctor_path(block)))  # as make_person names them
    return {"name": f"{surname} {given}", "title": f"the {rng.choice(EPITHETS)} Doctor of {region_label(world, *home)}",
            "whim": rng.choice(WHIMS), "home": list(home), "block": list(block)}


def seen_at(world, block, season: int) -> tuple[int, int, int]:
    """(x, y, town index) where the block's doctor is this season: they wander their block."""
    rng = rng_for(world.world_seed, f"{doctor_path(block)}:{season}")
    x, y = block[0] * BLOCK[0] + rng.randrange(BLOCK[0]), block[1] * BLOCK[1] + rng.randrange(BLOCK[1])
    return x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count)


def ask_events(world, person: int, place) -> list[Event]:
    here = world.entity(place).data
    block = block_of(here["x"], here["y"])
    season = lives.current_season(world)
    x, y, i = seen_at(world, block, season)
    return [Event("asked_doctor", (person,), place, {"block": list(block), "season": season, "at": [x, y, i],
                                                     "town": town_label(world, x, y, i)})]


@effect("asked_doctor")
def _asked(world, event) -> None:
    """The doctor of this block is made the first time anyone asks, and is where they were last seen."""
    person, d = event.actors[0], event.data
    town = ensure_town(world, *d["at"])
    doctor = ensure_doctor(world, tuple(d["block"]), town)
    world.unrelate(doctor, "located_in")
    world.relate(doctor, town, "located_in")
    seen = dict(world.entity(person).data.get("doctors_seen") or {})
    seen[doctor_path(d["block"])] = {"town": d["town"], "season": d["season"], "doctor": doctor}
    world.update_data(person, doctors_seen=seen)


@listen("asked_doctor")
def _seen_news(world, event, event_id: int) -> None:
    """Where a famous doctor was seen is a rumour: the asker hears it, and so does the town (spec 8)."""
    doctor = world.entity(world.entity(event.actors[0]).data["doctors_seen"][doctor_path(event.data["block"])]["doctor"])
    variant = make_variant("doctor_seen", doctor.id, None, place=event.data["town"])
    variant.update(title=doctor.data["doctor"]["title"])
    record_fact(world, doctor.id, "doctor_seen", None, place=event.place, source_event=event_id, weight=0.5,
                variant=variant)


def ensure_doctor(world, block, town: int) -> int:
    found = world.entity_by_seed(doctor_path(block))
    if found is not None:
        return found.id
    spec = doctor_spec(world, block)
    return make_person(world, doctor_path(block), town, occupation="famous doctor", realm="first-rate",
                       age=rng_for(world.world_seed, f"{doctor_path(block)}/age").randint(55, 95),
                       doctor={k: spec[k] for k in ("title", "whim", "home", "block")})


def doctors_here(world, place) -> list[int]:
    return [p.id for p in people_at(world, place) if p.data.get("doctor") and not p.data.get("dead")]


def doctor_cures(world, person: int) -> list[str]:
    """What a famous doctor could cure in this person now."""
    body = load_body(world, person)
    out = []
    if body.poisons:
        out.append("poison")
    if any(m.state in ("damaged", "severed") for m in body.meridians.values()):
        out.append("meridian")
    if any(i.permanent for i in body.injuries):
        out.append("injury")
    for name, (block, _) in sorted(CURE_HOOKS.items()):
        if block(world, person):
            out.append(name)
    return out


def terms_block(world, person: int, doctor: int, place) -> str | None:
    """Whether the doctor will treat this person on their terms (spec 5.2)."""
    whim = world.entity(doctor).data["doctor"]["whim"]
    if whim == "gold" and silver_of(world, person) < DOCTOR_GOLD:
        return f"The doctor asks {DOCTOR_GOLD} silver."
    if whim == "task" and not thousand_year_herb(world, person):
        return "The doctor asks a thousand-year herb."
    if whim == "righteous" and not orthodox(world, person, place):
        return "The doctor treats only the orthodox."
    if whim == "eccentric" and doctor not in (world.entity(person).data.get("go_won") or []):
        return "The doctor treats only one who beats them at go."
    return None


def thousand_year_herb(world, person: int) -> int | None:
    return next((h.id for h in H.herbs_of(world, person) if H.herb_info(h)[1] >= 3), None)


def orthodox(world, person: int, place) -> bool:
    dark = any(world.entity(f).data.get("type") in F.DARK and d.get("status", "member") == "member"
               for f, _, d in F.memberships(world, person))
    return not dark and reputation(world, place, apparent_to(world, place, person)).path != "ruthless"


def go_events(world, person: int, doctor: int, place) -> list[Event]:
    """A game of go with the eccentric doctor: comprehension against their wit, once a day."""
    wit = load_body(world, person).physique.get("comprehension", 5)
    roll = rng_for(world.world_seed, f"go:{doctor}:{person}:{world.time // 4}").random()
    return [Event("go_played", (person, doctor), place, {"won": roll < wit / 20})]


@effect("go_played")
def _go(world, event) -> None:
    person, doctor = event.actors
    if event.data["won"]:
        world.update_data(person, go_won=(world.entity(person).data.get("go_won") or []) + [doctor])


def doctor_events(world, person: int, doctor: int, what: str, place) -> list[Event]:
    whim = world.entity(doctor).data["doctor"]["whim"]
    return [Event("doctor_cured", (person, doctor), place, {
        "what": what, "whim": whim, "price": DOCTOR_GOLD if whim == "gold" else 0,
        "herb": thousand_year_herb(world, person) if whim == "task" else None})]


@effect("doctor_cured")
def _doctor_cured(world, event) -> None:
    person, doctor = event.actors
    d = event.data
    if d["price"]:
        _pay(world, person, d["price"], doctor)
    if d["herb"] is not None:
        H.spend(world, person, [d["herb"]])
    if d["what"] in CURE_HOOKS:
        CURE_HOOKS[d["what"]][1](world, person)
        return
    body = load_body(world, person)
    if d["what"] == "poison":
        body.poisons = []
        body.flags = [f for f in body.flags if f != X.POISONED_TO_DEATH]
    elif d["what"] == "meridian":
        for meridian in body.meridians.values():
            if meridian.state in ("damaged", "severed"):
                meridian.state, meridian.heals_at = "open", None
    elif d["what"] == "injury":
        worst = max((i for i in body.injuries if i.permanent), key=lambda i: (i.severity, -i.id), default=None)
        if worst is not None:
            worst.permanent, worst.heals_at = False, world.time + heal_watches(worst.severity, body)
    save_body(world, person, body)
    if d["what"] == "poison":
        X._forget_if_clean(world, person, body)


# --- the player as healer ---------------------------------------------------------------------------------------

def ailment(world, npc: int) -> str | None:
    """What ails someone, from their stored body (never rolled for asking): poison, or a wound, or None."""
    entity = world.entity(npc)
    stored = body_of(entity)
    if stored is None or entity.data.get("dead") or entity.data.get("beast"):
        return None
    body = settle(stored, world.time)
    if body.poisons:
        return "poison"
    return "wound" if treatable(body, world.time) else None


def remedy(world, person: int, npc: int) -> tuple[str, list[int]] | None:
    """How the player would treat them: ("pill", [pill]) or ("herbs", [two herbs]), or None."""
    what = ailment(world, npc)
    if what is None:
        return None
    body = settle(body_of(world.entity(npc)), world.time)
    for pill in P.pills_of(world, person):
        kind, grade = P.effect_of(pill), P.grade_of(pill)
        if what == "wound" and kind == "healing":
            return "pill", [pill.id]
        if what == "poison" and kind == "antidote" and grade >= max(p["grade"] for p in body.poisons):
            return "pill", [pill.id]
    herbs = [h.id for h in H.herbs_of(world, person) if H.known(world, person, H.herb_info(h)[0])
             and H.props(H.herb_info(h)[0])["element"] in HEALING_ELEMENTS
             and H.props(H.herb_info(h)[0])["toxicity"] <= 1]
    return ("herbs", herbs[:2]) if len(herbs) >= 2 else None


def heal_block(world, person: int, npc: int, place) -> str | None:
    if place not in world.targets(npc, "located_in"):
        return "They are not here."
    if ailment(world, npc) is None:
        return "Nothing ails them."
    if attitude(world, npc, apparent_to(world, npc, person)).word in UNFIT:
        return "They will not let you near them."
    if remedy(world, person, npc) is None:
        return "You have nothing fit to treat them with."
    return None


def heal_chance(world, person: int) -> float:
    return max(HEAL_BOUNDS[0], min(HEAL_BOUNDS[1], HEAL_ROLL + HEAL_PER_LEVEL * A.level(world, person)))


def heal_events(world, person: int, npc: int, place) -> list[Event]:
    how, items = remedy(world, person, npc)
    roll = rng_for(world.world_seed, f"heal:{person}:{npc}:{world.time}").random()
    success = how == "pill" or roll < heal_chance(world, person)
    witnesses = (Witness(npc, "grateful", 0.3),) if success else ()
    return [Event("healed", (person, npc), place, {"how": how, "items": items, "ailment": ailment(world, npc),
                                                    "success": success}, witnesses=witnesses)]


@effect("healed")
def _healed(world, event) -> None:
    person, npc = event.actors
    d = event.data
    if d["how"] == "pill":
        world.unrelate(person, "owns", d["items"][0])
        world.update_data(d["items"][0], used=True)
    else:
        H.spend(world, person, d["items"])
    if not d["success"]:
        return
    body = load_body(world, npc)
    if d["ailment"] == "poison":
        body.poisons, body.flags = [], [f for f in body.flags if f != X.POISONED_TO_DEATH]
    else:
        for injury in body.injuries:
            if not injury.permanent and injury.heals_at and injury.heals_at > world.time:
                injury.heals_at = world.time
    save_body(world, npc, body)
    X._forget_if_clean(world, npc, body)
    if event.place is not None and world.entity(event.place).kind == "town":
        counts = dict(world.entity(person).data.get("healings") or {})
        counts[str(event.place)] = counts.get(str(event.place), 0) + 1
        world.update_data(person, healings=counts)


@listen("healed")
def _healed_news(world, event, event_id: int) -> None:
    if not event.data["success"]:
        return
    person, npc = event.actors
    record_fact(world, person, "healed", npc, place=event.place, source_event=event_id, weight=1.0,
                variant=make_variant("healed", person, npc, place=place_name(world, event.place)))


def healer_of(world, person: int) -> list[int]:
    """The towns where the player has healed five: each calls them its healer."""
    return sorted(int(t) for t, n in (world.entity(person).data.get("healings") or {}).items() if n >= HEALER_AT)


def patient_events(world, person: int, town: int) -> list[Event]:
    """A known healer is sometimes brought someone sick (spec 5.3): made on the spot, hurt or poisoned."""
    if town not in healer_of(world, person):
        return []
    day = world.time // 4
    if world.entity_by_seed(f"patient:{person}:{town}:{day}") is not None:
        return []  # one brought a day
    rng = rng_for(world.world_seed, f"patient:{person}:{town}:{day}")
    if rng.random() >= PATIENT_CHANCE:
        return []
    return [Event("patient_brought", (person,), town, {"path": f"patient:{person}:{town}:{day}",
                                                       "poisoned": rng.random() < 0.3})]


@effect("patient_brought")
def _patient(world, event) -> None:
    d = event.data
    sick = make_person(world, d["path"], event.place)
    body = load_body(world, sick)
    if d["poisoned"]:
        X.add_poison(world, sick, body, 2, 12, "a bad well")
    else:
        from world.body import add_injury
        add_injury(body, "torso", "internal", 2, world.time, "a fever")
    save_body(world, sick, body)
    world.update_data(event.actors[0], patient=sick)


# --- poison for hire --------------------------------------------------------------------------------------------

def unorthodox(world, npc: int) -> bool:
    entity = world.entity(npc)
    return is_bandit(entity) or any(world.entity(f).data.get("type") in F.DARK and d.get("status", "member") == "member"
                                    for f, _, d in F.memberships(world, npc))


def knows_you_poison(world, npc: int, person: int) -> bool:
    seen = apparent_to(world, npc, person)
    return any(f.predicate in POISON_FAME and b.variant.get("actor") in (person, seen)
               for b, f in knowledge_of(world, npc))


def contract_offer(world, npc: int, person: int) -> dict | None:
    """A poisoning this client would pay for, once a season: a mark in their town, and the silver."""
    if world.entity(person).data.get("contract") or not unorthodox(world, npc) or not knows_you_poison(world, npc, person):
        return None
    season = lives.current_season(world)
    rng = rng_for(world.world_seed, f"contract:{npc}:{person}:{season}")
    if rng.random() >= CONTRACT_OFFER:
        return None
    town = next(iter(world.targets(npc, "located_in")), None)
    marks = sorted(p.id for p in people_at(world, town) if p.id not in (npc, person) and lives.simulated(p)) \
        if town is not None else []
    if not marks:
        return None
    return {"client": npc, "target": rng.choice(marks), "silver": rng.randint(*CONTRACT_PAY)}


def contract_events(world, person: int, offer: dict, place) -> list[Event]:
    return [Event("contract_taken", (person, offer["client"], offer["target"]), place,
                  {"silver": offer["silver"], "deadline": world.time + CONTRACT_DAYS * 4})]


@effect("contract_taken")
def _taken(world, event) -> None:
    person, client, target = event.actors
    world.update_data(person, contract={"client": client, "target": target, "silver": event.data["silver"],
                                        "deadline": event.data["deadline"], "done": False})


def contract_poison_block(world, person: int, target: int, place) -> str | None:
    from systems.scheming import poisons_of
    contract = world.entity(person).data.get("contract")
    if not contract or contract["target"] != target or contract["done"]:
        return "No one pays you to poison them."
    if place not in world.targets(target, "located_in"):
        return "They are not here."
    if not poisons_of(world, person):
        return "You carry no poison."
    return None


def contract_poison_events(world, person: int, target: int, place) -> list[Event]:
    from systems.scheming import poison_grade, poisons_of
    vial = max(poisons_of(world, person), key=lambda i: (poison_grade(world.entity(i)), -i))
    grade = poison_grade(world.entity(vial))
    found = rng_for(world.world_seed, f"contract_found:{person}:{target}").random() < FIND_CHANCE
    events = [Event("contract_poisoned", (person, target), place, {"vial": vial, "grade": grade, "found": found})]
    if grade >= X.LETHAL_GRADE:
        events.append(Event("died", (target, target), place, {"cause": "illness", "world": True,
                                                              "poisoned_by": person}))
    return events


@effect("contract_poisoned")
def _poisoned(world, event) -> None:
    person, target = event.actors
    d = event.data
    world.unrelate(person, "owns", d["vial"])
    world.update_data(d["vial"], used=True)
    if d["grade"] < X.LETHAL_GRADE:
        X.poison(world, target, d["grade"], d["grade"] * P.POISON_STRENGTH, "a poisoned cup")
    contract = world.entity(person).data.get("contract")
    if contract and contract["target"] == target:
        world.update_data(person, contract={**contract, "done": True})


@listen("contract_poisoned")
def _traced(world, event, event_id: int) -> None:
    if not event.data["found"]:
        return
    person, target = event.actors
    record_fact(world, person, "poisoned_for_hire", target, place=event.place, source_event=event_id, weight=3.0,
                variant=make_variant("poisoned_for_hire", person, target, place=place_name(world, event.place)))


def fee_block(world, person: int, client: int) -> str | None:
    contract = world.entity(person).data.get("contract")
    if not contract or contract["client"] != client:
        return "They owe you nothing."
    if not contract["done"]:
        return "The job is not done."
    return None


def fee_events(world, person: int, client: int, place) -> list[Event]:
    contract = world.entity(person).data["contract"]
    return [Event("contract_paid", (person, client), place, {"silver": min(contract["silver"],
                                                                           silver_of(world, client))})]


@effect("contract_paid")
def _fee(world, event) -> None:
    person, client = event.actors
    world.update_data(client, silver=silver_of(world, client) - event.data["silver"])
    world.update_data(person, silver=silver_of(world, person) + event.data["silver"], contract=None)


def contract_lapsed(world, person: int) -> bool:
    """A contract past its deadline, or whose client or mark died by other hands, is void."""
    contract = world.entity(person).data.get("contract")
    if not contract:
        return False
    client, target = world.entity(contract["client"]), world.entity(contract["target"])
    if client is None or client.data.get("dead"):
        return True
    if not contract["done"] and (world.time > contract["deadline"] or target is None or target.data.get("dead")):
        return True
    return False


def void_events(world, person: int, place) -> list[Event]:
    return [Event("contract_void", (person,), place, {})]


@effect("contract_void")
def _void(world, event) -> None:
    world.update_data(event.actors[0], contract=None)
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_physic.py`
Expected: `2 failed, 14 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5c_task4.py`:
```python
"""Phase 5c, Task 4: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.hall_theft  # noqa: E402,F401  phase 5c: gardens and halls robbed by night
''', r'''import systems.hall_theft  # noqa: E402,F401  phase 5c: gardens and halls robbed by night
import systems.physic  # noqa: E402,F401  phase 5c: physicians, famous doctors, healers and poisoners for hire
''')
edit('systems/attitude.py', r'''    "poison_body": -0.4,  # phase 5b: folk keep away from a body that is poison
''', r'''    "poison_body": -0.4,  # phase 5b: folk keep away from a body that is poison
    "healed": 0.3,  # phase 5c: a healer is thought well of
''')
edit('systems/law.py', r'''SCHEMES = frozenset({"poisoner", "spymaster", "framer", "forger", "puppet_master", "murdered"})  # 4h: 100 silver''', r'''SCHEMES = frozenset({"poisoner", "spymaster", "framer", "forger", "puppet_master", "murdered",
                     "poisoned_for_hire"})  # 4h: 100 silver; 5c: a hired poisoning traced''')
edit('systems/attitude.py', r'''    "healed": 0.3,  # phase 5c: a healer is thought well of
''', r'''    "healed": 0.3,  # phase 5c: a healer is thought well of
    "poisoned_for_hire": -1.0,
''')
print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5c_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_physic.py`
Expected: `16 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1331 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: physicians and famous doctors, the player as healer, and poison for hire"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 5: NPC alchemy

A lives agenda with its own seeded stream (ruling 15). Alchemists refine one to three pills a season of grade `ceil(rank / 2)`, kept as a count (`pills`), and rise a rank one season in ten. Anyone of realm 1 or more with silver takes a pill three seasons in ten: half a year of cultivation and `3 x grade` residue, which past 60 risks a deviation. The pills become things only when the player robs or kills the one who carries them, buys at their stall, or inherits them (ruling 16). 4a's test of cultivation alone now holds pills aside.

**Files:**
- Create: `systems/npc_alchemy.py`
- Create: `tests/test_npc_alchemy.py`
- Modify (by `.patches/5c_task5.py`): `systems/world_clock.py`, `debug/invariants.py`, `tests/test_lives.py`

**Interfaces:**
- Consumes: 4a's `lives` (`AGENDAS`, `_grown`, `key`, `home`), `systems.agendas`; Task 1's `pill_hall.make_hall_pill`, `EFFECTS`; Task 2's `guild` (`rank_of`, `is_pill_master`, `is_alchemist`); 4b's `kin.kin_of`.
- Produces:
  - `N` (systems/npc_alchemy.py): `REFINE`, `RISE_CHANCE`, `TAKE_CHANCE`, `PILL_YEARS`, `RESIDUE_PER_GRADE`, `DEVIATION_AT`, `DEVIATION_CHANCE`, `DEADLY`, `BUY_PRICE`, `STALL_PRICE`, `MAX_HELD`; `held(entity)`, `season_events(world, person, n, rng)`, `materialize(world, holder, taker, how, count)`, `stall_price(grade)`, `stall_offers(world, npc)`, `stall_block(world, person, npc, grade)`, `stall_events(world, person, npc, grade, place)`; events `npc_alchemy`, `npc_pill_bought`.
  - a rule on NPCs' `pills` in `check_alchemy_world`.

- [ ] **Step 1: Write the tests**

`tests/test_npc_alchemy.py`:
```python
import pytest

import systems.encounters as encounters
import systems.guild as G
import systems.lives as lives
import systems.npc_alchemy as N
import systems.pills as P
from engine.game import Game
from systems.bodies import load_body
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


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal", "age": 30,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:npcalc:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def seasons(world, person, count):
    """Live this person's next seasons, one at a time, through the life clock."""
    start = lives.lived_to(world, person)
    world.set_time(max(world.time, (start + count) * lives.SEASON))
    lives.catch_up(world, person)


def test_an_alchemist_refines_each_season_and_keeps_a_count_not_things(game):
    world = game.world
    brewer = someone(game, "brewer", occupation="herbalist")
    before = world.last_rowid("entities")
    seasons(world, brewer, 4)
    pills = N.held(world.entity(brewer))
    grade = max(1, -(-G.rank_of(world, brewer) // 2))
    assert pills and all(g <= grade for g in pills)
    assert sum(pills.values()) >= 4 or sum(pills.values()) == N.MAX_HELD
    made = [world.entity(i) for i in range(before + 1, world.last_rowid("entities") + 1) if world.entity(i)]
    assert not any(e.kind == "pill" for e in made)  # no entities made


def test_an_alchemists_rank_rises_now_and_then(game, monkeypatch):
    world = game.world
    brewer = someone(game, "riser", occupation="herbalist")
    start = G.rank_of(world, brewer)
    monkeypatch.setattr(N, "RISE_CHANCE", 1.0)
    seasons(world, brewer, 2)
    assert world.entity(brewer).data["guild_rank"] == min(G.MAX_RANK, start + 2)


def test_a_fighter_with_silver_takes_pills_for_years_and_residue(game, monkeypatch):
    world = game.world
    fighter = someone(game, "fighter", realm="third-rate", silver=500)
    body = load_body(world, fighter)
    monkeypatch.setattr(N, "TAKE_CHANCE", 1.0)
    before = world.entity(fighter).data["body"]["energy_years"]
    seasons(world, fighter, 1)
    after = world.entity(fighter).data["body"]
    assert after["residue"] > 0 and silver_of(world, fighter) == 500 - N.BUY_PRICE
    assert after["energy_years"] >= before + N.PILL_YEARS or after["bottleneck"]
    assert body is not None


def test_a_mortal_takes_no_pills(game, monkeypatch):
    world = game.world
    mortal = someone(game, "mortal", silver=500)
    monkeypatch.setattr(N, "TAKE_CHANCE", 1.0)
    seasons(world, mortal, 2)
    assert silver_of(world, mortal) == 500


def test_a_body_full_of_residue_may_deviate(game, monkeypatch):
    world = game.world
    fighter = someone(game, "full", realm="third-rate", silver=500)
    body = dict(world.entity(fighter).data.get("body") or {})
    load_body(world, fighter)
    stored = dict(world.entity(fighter).data["body"])
    stored["residue"] = 90.0
    world.update_data(fighter, body=stored)
    monkeypatch.setattr(N, "TAKE_CHANCE", 1.0)
    monkeypatch.setattr(N, "DEVIATION_CHANCE", 1.0)
    monkeypatch.setattr(N, "DEADLY", 0.0)
    seasons(world, fighter, 1)
    assert any(i.cause == "a qi deviation" for i in load_body(world, fighter).injuries)
    assert body is not None


def test_a_robbed_alchemists_pills_become_things(game):
    world, me = game.world, game.player.id
    brewer = someone(game, "robbed", occupation="herbalist", pills={"2": 2, "1": 1})
    commit(world, [Event("duel_ended", (me, brewer), game.place.id, {
        "result": "won", "mode": "duel", "verdict": "rob", "by": "player", "silver": 0, "crippled": None,
        "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None, "purpose": None, "killed": False,
        "left_for_dead": False, "duel": None, "reason": "yielded"})])
    pills = P.pills_of(world, me)
    assert sorted(P.grade_of(p) for p in pills) == [1, 2, 2] and all(p.data["how"] == "taken" for p in pills)
    assert N.held(world.entity(brewer)) == {}


def test_an_alchemists_stall_sells_their_pills(game):
    world, me = game.world, game.player.id
    brewer = someone(game, "stall", occupation="herbalist", pills={"1": 1})
    assert N.stall_offers(world, brewer) == [1]
    assert N.stall_block(world, me, brewer, 1) is None
    commit(world, N.stall_events(world, me, brewer, 1, game.place.id))
    assert silver_of(world, me) == 5000 - N.stall_price(1) and len(P.pills_of(world, me)) == 1
    assert N.stall_offers(world, brewer) == []


def test_pills_pass_to_the_heir(game):
    from systems.agendas import _pair
    world = game.world
    brewer = someone(game, "old", occupation="herbalist", pills={"1": 3})
    child = someone(game, "child")
    _pair(world, brewer, child, "child")
    commit(world, [Event("died", (brewer, brewer), game.place.id, {"cause": "age", "world": True})])
    assert N.held(world.entity(child)) == {1: 3}


def test_the_life_clock_runs_the_alchemy_agenda(game):
    assert N.season_events in lives.AGENDAS
    from systems.agendas import apprentice_events
    assert lives.AGENDAS.index(apprentice_events) < lives.AGENDAS.index(N.season_events)


def test_the_rules_hold_an_npcs_pills_to_real_grades(game):
    from debug.invariants import check_alchemy_world
    world = game.world
    someone(game, "odd", occupation="herbalist", pills={"1": 2})
    assert check_alchemy_world(world) == []
    someone(game, "bad", occupation="herbalist", pills={"7": 1})
    assert "pills" in " | ".join(check_alchemy_world(world))
```

- [ ] **Step 2: Write the new modules**

`systems/npc_alchemy.py`:
```python
"""NPC alchemy (phase 5c spec 5.4): a lives agenda, one seeded roll per person per season, no entities made.

Alchemists (herbalists by trade and the sects' pill masters) refine 1-3 pills a season of grade ceil(rank / 2),
kept as a count on the person (`pills`: {grade: count}), and now and then rise a Guild rank. Anyone of realm 1 or
more with silver may take a pill in a season: half a year of cultivation, and residue that, past 60, risks a
deviation. The pills become things only when the player takes them: robbed or taken from the slain, bought at an
alchemist's stall, or inherited.
"""

import math

import systems.agendas  # noqa: F401  the life clock's own agendas come first, whatever is imported first
import systems.guild as G
import systems.lives as lives
import systems.pill_hall as PH
from systems.bodies import load_body
from systems.purse import silver_of
from systems.realms import realm_index
from world.body import add_injury, to_dict
from world.events import Event, effect, listen
from world.seed import rng_for

REFINE = (1, 3)
RISE_CHANCE = 0.1
TAKE_CHANCE = 0.3
PILL_YEARS = 0.5
RESIDUE_PER_GRADE = 3
DEVIATION_AT, DEVIATION_CHANCE, DEADLY = 60, 0.02, 0.1
BUY_PRICE = 20             # an NPC buys a pill for this x grade, when they have none of their own
STALL_PRICE = 30           # the player buys at an alchemist's stall for this x grade squared
MAX_HELD = 12


def held(entity) -> dict[int, int]:
    return {int(k): v for k, v in (entity.data.get("pills") or {}).items() if v > 0}


def season_events(world, person: int, n: int, rng) -> list[Event]:
    """This season's refining and pill-taking for one NPC, from its own seeded stream (not the life clock's)."""
    entity = world.entity(person)
    mine = rng_for(world.world_seed, f"npc_alchemy:{lives.key(entity)}:{n}")
    data: dict = {"season": n, "refined": 0, "grade": 0, "rank": None, "took": None, "deviation": False,
                  "dies": False, "bought": 0}
    occupation = entity.data.get("occupation")
    alchemist = occupation in G.ALCHEMIST_JOBS or (occupation == "hall keeper" and G.is_pill_master(world, person))
    if alchemist:
        rank = G.rank_of(world, person) or 1
        data["grade"] = min(5, max(1, math.ceil(rank / 2)))
        data["refined"] = mine.randint(*REFINE)
        if rank < G.MAX_RANK and mine.random() < RISE_CHANCE:
            data["rank"] = rank + 1
    if realm_index(entity.data.get("realm", "mortal")) >= 1 and mine.random() < TAKE_CHANCE:
        own = held(entity)
        if own or data["refined"]:
            data["took"] = max(own) if own else data["grade"]
        elif silver_of(world, person) >= BUY_PRICE:
            data["took"], data["bought"] = 1, BUY_PRICE
        if data["took"]:
            residue = float((entity.data.get("body") or {}).get("residue", 0.0))
            if residue >= DEVIATION_AT and mine.random() < DEVIATION_CHANCE:
                data["deviation"] = True
                data["dies"] = mine.random() < DEADLY
    if not data["refined"] and not data["took"] and data["rank"] is None:
        return []
    events = [Event("npc_alchemy", (person,), lives.home(world, person), data)]
    if data["dies"] and lives.home(world, person) is not None:
        events.append(Event("died", (person, person), lives.home(world, person), {"cause": "deviation", "world": True}))
    return events


lives.AGENDAS.append(season_events)


@effect("npc_alchemy")
def _season(world, event) -> None:
    person, d = event.actors[0], event.data
    entity = world.entity(person)
    pills = held(entity)
    changes: dict = {}
    if d["refined"]:
        pills[d["grade"]] = min(MAX_HELD, pills.get(d["grade"], 0) + d["refined"])
    if d["rank"] is not None:
        changes["guild_rank"] = d["rank"]
    if d["took"]:
        if pills.get(d["took"]):
            pills[d["took"]] -= 1
        if d["bought"]:
            changes["silver"] = silver_of(world, person) - d["bought"]
        body = dict(entity.data.get("body") or to_dict(load_body(world, person)))
        body["energy_years"], body["bottleneck"] = lives._grown(body, PILL_YEARS)
        body["residue"] = min(100.0, float(body.get("residue", 0.0)) + RESIDUE_PER_GRADE * d["took"])
        changes["body"] = body
    changes["pills"] = {str(k): v for k, v in pills.items() if v > 0}
    world.update_data(person, **changes)
    if d["deviation"] and not d["dies"]:
        body = load_body(world, person)
        add_injury(body, "torso", "internal", 3, world.time, "a qi deviation")
        from systems.bodies import save_body
        save_body(world, person, body)


# --- the pills made things ----------------------------------------------------------------------------------

def materialize(world, holder: int, taker: int, how: str, count: int | None = None) -> list[int]:
    """Some of an NPC's pills become pills the taker carries: the strongest first."""
    entity = world.entity(holder)
    pills = held(entity)
    made = []
    for grade in sorted(pills, reverse=True):
        while pills[grade] > 0 and (count is None or len(made) < count):
            pills[grade] -= 1
            rng = rng_for(world.world_seed, f"npc_pill:{holder}:{grade}:{pills[grade]}")
            made.append(PH.make_hall_pill(world, taker, holder, grade, rng.choice(PH.EFFECTS), how))
    world.update_data(holder, pills={str(k): v for k, v in pills.items() if v > 0})
    return made


@listen("duel_ended")
def _robbed(world, event, event_id: int) -> None:
    """What a robbed or slain NPC carried goes with their manuals to the victor (spec 5.4)."""
    player, opponent = event.actors
    if event.data.get("by") == "player" and event.data.get("verdict") in ("rob", "kill") \
            and held(world.entity(opponent)):
        materialize(world, opponent, player, "taken")


@listen("died")
def _inherited(world, event, event_id: int) -> None:
    dead = event.actors[-1]
    entity = world.entity(dead)
    if entity is None or not held(entity):
        return
    from systems.kin import kin_of
    heir = next((k for k, _ in kin_of(world, dead) if not world.entity(k).data.get("dead")), None)
    if heir is None:
        return
    if world.entity(heir).data.get("is_player"):
        materialize(world, dead, heir, "inherited")
        return
    pills = held(world.entity(heir))
    for grade, count in held(entity).items():
        pills[grade] = min(MAX_HELD, pills.get(grade, 0) + count)
    world.update_data(heir, pills={str(k): v for k, v in pills.items()})
    world.update_data(dead, pills={})


# --- an alchemist's stall -------------------------------------------------------------------------------------

def stall_price(grade: int) -> int:
    return STALL_PRICE * grade ** 2


def stall_offers(world, npc: int) -> list[int]:
    """The grades an alchemist has pills of to sell."""
    return sorted(held(world.entity(npc)), reverse=True) if G.is_alchemist(world, npc) else []


def stall_block(world, person: int, npc: int, grade: int) -> str | None:
    if grade not in stall_offers(world, npc):
        return "They have no such pills."
    if silver_of(world, person) < stall_price(grade):
        return f"They ask {stall_price(grade)} silver."
    return None


def stall_events(world, person: int, npc: int, grade: int, place) -> list[Event]:
    return [Event("npc_pill_bought", (person, npc), place, {"grade": grade, "price": stall_price(grade)})]


@effect("npc_pill_bought")
def _bought(world, event) -> None:
    person, npc = event.actors
    d = event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    world.update_data(npc, silver=silver_of(world, npc) + d["price"])
    pills = held(world.entity(npc))
    pills[d["grade"]] -= 1
    rng = rng_for(world.world_seed, f"npc_pill:{npc}:{d['grade']}:{pills[d['grade']]}")
    world.update_data(npc, pills={str(k): v for k, v in pills.items() if v > 0})
    PH.make_hall_pill(world, person, npc, d["grade"], rng.choice(PH.EFFECTS), "bought")
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_npc_alchemy.py`
Expected: `1 failed, 9 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5c_task5.py`:
```python
"""Phase 5c, Task 5: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.physic  # noqa: E402,F401  phase 5c: physicians, famous doctors, healers and poisoners for hire
''', r'''import systems.physic  # noqa: E402,F401  phase 5c: physicians, famous doctors, healers and poisoners for hire
import systems.npc_alchemy  # noqa: E402,F401  phase 5c: NPCs refine and take pills in their seasons
''')
edit('debug/invariants.py', r'''    for scroll in world.entities("scroll"):''', r'''    for person in world.entities_after("person", "pills", 0):
        if any(int(k) not in range(1, 6) or v < 0 for k, v in person.data["pills"].items()):
            out.append(f"{person.name} (#{person.id}) carries pills of no grade or fewer than none")
    for scroll in world.entities("scroll"):''')
edit('tests/test_lives.py', r'''    monkeypatch.setattr(lives, "breakthrough_chance", lambda body, met: 0.0)
    clerk = person(game, "test:clerk", occupation="innkeeper")''', r'''    monkeypatch.setattr(lives, "breakthrough_chance", lambda body, met: 0.0)
    monkeypatch.setattr("systems.npc_alchemy.TAKE_CHANCE", 0.0)  # phase 5c: cultivation alone, no pills
    clerk = person(game, "test:clerk", occupation="innkeeper")''')
print("task 5 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5c_task5.py`
Expected: `task 5 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_npc_alchemy.py`
Expected: `10 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1341 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: NPC alchemy - alchemists refine and rise, fighters take pills, and the pills become things only when taken"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 6: Control pills

The control pill is a secret recipe, in `systems/data/secret_recipes.toml` (ruling 17), kept by the halls of unorthodox sects alone. The bound carry `bound_to`; an NPC master feeds them while alive (ruling 19), and each day unfed does internal harm until, past ninety, the worms kill, laid at the master's door (ruling 18). Freedom is the master's death, a grade-5 antidote, a famous doctor, or forcing the worms out at realm 5. An unorthodox master of realm 3 who spares the player after a real duel may bind them (a quarter of the time); a month's service feeds the pill. The player binds a beaten foe with a control pill, a crime against the lawful (ruling 20), and must feed them monthly; those they bind seek a cure. The world's unorthodox masters bind a few of their own, told in rumours. The meta row `bound` lists the bound NPCs.

**Files:**
- Create: `systems/control.py`
- Create: `systems/data/secret_recipes.toml`
- Create: `tests/test_control.py`
- Modify (by `.patches/5c_task6.py`): `systems/world_clock.py`, `systems/mortality.py`, `systems/pills.py`, `systems/recipe_trade.py`, `systems/law.py`, `systems/attitude.py`, `systems/alchemy.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Task 2's `alchemy.SECRET`, `recipe_trade.secret_recipes`; Task 4's `physic` (`CURE_HOOKS`, `unorthodox`); Task 5's agenda order; 4b's `mortality.death_events`; 5a's `spoils.beaten_by`, `spoils.lawful`; 5b's `pills`.
- Produces:
  - `C` (systems/control.py): `MONTH`, `STARVE_SEVERITY`, `STARVE_DAYS`, `FREE_GRADE`, `FORCE_REALM`, `FORCE_QI`, `FORCE_CHANCE`, `BIND_REALM`, `BIND_CHANCE`, `CURE_SEEK`, `WORLD_BIND`, `WORLD_MAX`, `SERVICES`; `bound(world, person)`, `servants_of(world, master)`, `bind(world, person, master)`, `free(world, person)`, `days_starved(world, person)`, `starve(world, person)`, `death_events(world, person)`, `fed(world, master)`, `season_hook(world, n)`, `antidote_frees(world, person, grade)`, `force_block(world, person)`, `force_events(world, person, place)`, `binds(world, npc)`, `service(world, person)`, `service_done(world, person)`, `served_events(world, person, place)`, `control_pills(world, person)`, `force_feed_block(world, person, npc, place)`, `force_feed_events(world, person, npc, place)`, `feed_block(world, person, npc)`, `feed_events(world, person, npc, place)`, `antidote_for(world, person)`, `free_block(world, person, npc, place)`, `free_events(world, person, npc, place)`, `world_events(world, person, n, rng)`; events `control_forced`, `control_freed`, `npc_bound`, `servant_fed`, `service_rendered`, `worms_forced`, `worms_killed`.
  - `mortality.CAUSES['control_pill']`; `law.SCHEMES` gains `enslaved`; a grade-5 antidote frees; `alchemy.LAST_WORDS['control']`; the bound index in `check_alchemy_world`.

- [ ] **Step 1: Write the tests**

`tests/test_control.py`:
```python
import pytest

import systems.alchemy as A
import systems.control as C
import systems.encounters as encounters
import systems.lives as lives
import systems.physic as PY
import systems.pills as P
import systems.recipe_trade as RT
from debug.invariants import check_alchemy_world
from engine.game import Game
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.law import SCHEMES
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


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal", "age": 30,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:control:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def a_master(game, tag="master"):
    return someone(game, tag, occupation="bandit", realm="first-rate", traits=["cunning", "greedy"])


def duel_end(world, a, b, place, **data):
    base = {"result": "won", "mode": "duel", "verdict": "spare", "by": "player", "silver": 0, "crippled": None,
            "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None, "purpose": None, "killed": False,
            "left_for_dead": False, "duel": None, "reason": "yielded"}
    return Event("duel_ended", (a, b), place, {**base, **data})


def control_pill(world, me):
    return A.make_pill(world, me, A.recipe_entity(world, "control"), 4, 0.6)


def test_the_control_recipe_is_secret_and_kept_only_by_unorthodox_halls(game):
    world = game.world
    assert "control" not in A.RECIPES
    assert A.best_match(A.combine(["black lotus", "black lotus", "corpse flower"]))[0] != "control"
    recipe = A.recipe_entity(world, "control")
    assert world.entity(recipe).data["effect"] == "control" and "Corpse-Worm Pill" in world.entity(recipe).name
    for fid in F.ensure_roster(world):
        kind = world.entity(fid).data["type"]
        assert ("control" in RT.secret_recipes(world, fid)) == (kind in F.DARK)
    assert "control" not in RT.guild_offers(world, game.player.id)


def test_the_bound_are_harmed_each_day_unfed_and_die_after_ninety(game):
    world = game.world
    master, victim = a_master(game), someone(game, "victim")
    C.bind(world, victim, master)
    world.update_data(master, is_player=True)  # a master who does not feed them
    world.set_time(world.time + C.MONTH + 3 * WATCHES_PER_DAY)
    C.starve(world, victim)
    assert len([i for i in load_body(world, victim).injuries if i.cause == "the worms of a control pill"]) == 3
    C.starve(world, victim)
    assert len([i for i in load_body(world, victim).injuries if i.cause == "the worms of a control pill"]) == 3
    assert C.death_events(world, victim) == []
    world.set_time(world.time + C.STARVE_DAYS * WATCHES_PER_DAY)
    [death] = C.death_events(world, victim)
    assert death.data["cause"] == "control_pill" and death.actors == (master, victim)


def test_an_npc_master_feeds_their_bound_and_a_dead_ones_bound_go_free(game):
    world = game.world
    master, victim = a_master(game), someone(game, "fed")
    C.bind(world, victim, master)
    world.set_time(world.time + 2 * lives.SEASON)
    commit(world, C.season_hook(world, 2))
    assert C.bound(world, victim)["fed_until"] > world.time and C.days_starved(world, victim) == 0
    killer = someone(game, "killer")
    commit(world, [Event("died", (killer, master), game.place.id, {"cause": "killed", "world": True})])
    assert C.bound(world, victim) is None and victim not in (world.get_meta("bound") or [])
    assert any(m.feeling == "grateful" for m in world.memories(victim, about=killer))


def test_a_grade_five_antidote_or_a_famous_doctor_frees_the_bound(game):
    world, me = game.world, game.player.id
    master = a_master(game)
    C.bind(world, me, master)
    pill = A.make_pill(world, me, A.recipe_entity(world, "metal_antidote"), 5, 0.9)
    commit(world, P.swallow_events(world, me, game.place.id, pill))
    assert C.bound(world, me) is None
    C.bind(world, me, master)
    assert "control" in PY.doctor_cures(world, me)
    doctor = someone(game, "doctor", doctor={"title": "the Test Doctor", "whim": "righteous", "home": [0, 0],
                                             "block": [0, 0]})
    commit(world, PY.doctor_events(world, me, doctor, "control", game.place.id))
    assert C.bound(world, me) is None


def test_a_transcendent_master_forces_the_worms_out(game, monkeypatch):
    world, me = game.world, game.player.id
    C.bind(world, me, a_master(game))
    assert "transcendent" in C.force_block(world, me)
    body = load_body(world, me)
    body.realm, body.energy_years, body.qi = 5, 70.0, 200.0
    save_body(world, me, body)
    assert C.force_block(world, me) is None
    monkeypatch.setattr(C, "FORCE_CHANCE", 1.0)
    commit(world, C.force_events(world, me, game.place.id))
    assert C.bound(world, me) is None


def test_the_player_spared_by_an_unorthodox_master_may_wake_bound(game, monkeypatch):
    world, me = game.world, game.player.id
    master = a_master(game)
    monkeypatch.setattr(C, "BIND_CHANCE", 1.0)
    commit(world, [duel_end(world, me, master, game.place.id, result="lost", by="opponent", mode="spar")])
    assert C.bound(world, me) is None  # never in a spar
    commit(world, [duel_end(world, me, master, game.place.id, result="lost", by="opponent")])
    assert C.bound(world, me)["master"] == master
    assert me not in (world.get_meta("bound") or [])  # the player is watched turn by turn, not listed


def test_a_months_service_feeds_the_pill(game):
    world, me = game.world, game.player.id
    master = a_master(game)
    C.bind(world, me, master)
    task = C.service(world, me)
    assert task["kind"] in C.SERVICES and C.service(world, me) == task
    assert not C.service_done(world, me)
    if task["kind"] == "steal":
        commit(world, [Event("hall_theft", (me,), game.place.id, {"faction": 1, "target": "hall", "caught": False,
                                                                  "loot": [], "season": 0})])
    elif task["kind"] == "beat":
        foe = someone(game, "foe")
        commit(world, [duel_end(world, me, foe, game.place.id)])
    else:
        from world.gen.materialize import ensure_town
        world.unrelate(me, "located_in")
        world.relate(me, ensure_town(world, *task["at"]), "located_in")
    assert C.service_done(world, me)
    before = C.bound(world, me)["fed_until"]
    commit(world, C.served_events(world, me, game.place.id))
    assert C.bound(world, me)["fed_until"] == before + C.MONTH
    assert not C.service_done(world, me)  # one service a month


def test_the_player_binds_a_beaten_foe_who_hates_them_and_must_feed_them(game):
    world, me, here = game.world, game.player.id, game.place.id
    foe = someone(game, "foe")
    assert "not beaten" in C.force_feed_block(world, me, foe, here)
    commit(world, [duel_end(world, me, foe, here)])
    assert "no control pill" in C.force_feed_block(world, me, foe, here)
    control_pill(world, me)
    assert C.force_feed_block(world, me, foe, here) is None
    commit(world, C.force_feed_events(world, me, foe, here))
    assert C.bound(world, foe)["master"] == me and foe in world.get_meta("bound")
    assert any(m.feeling == "hatred" for m in world.memories(foe, about=me))
    [fact] = world.facts(predicate="enslaved")
    assert fact.object == foe and "enslaved" in SCHEMES
    assert "no control pill" in C.feed_block(world, me, foe)
    control_pill(world, me)
    before = C.bound(world, foe)["fed_until"]
    commit(world, C.feed_events(world, me, foe, here))
    assert C.bound(world, foe)["fed_until"] == before + C.MONTH


def test_those_the_player_binds_may_find_a_cure(game, monkeypatch):
    world, me = game.world, game.player.id
    foe = someone(game, "seeker")
    C.bind(world, foe, me)
    monkeypatch.setattr(C, "CURE_SEEK", 1.0)
    commit(world, C.season_hook(world, 1))
    assert C.bound(world, foe) is None
    assert world.facts(predicate="freed")


def test_an_unorthodox_master_binds_someone_of_their_town_now_and_then(game, monkeypatch):
    world = game.world
    master = a_master(game, "world master")
    victim = someone(game, "townsman")
    monkeypatch.setattr(C, "WORLD_BIND", 1.0)
    events = C.world_events(world, master, 1, None)
    assert events and events[0].actors[0] == master
    commit(world, events)
    bound = events[0].actors[1]
    assert C.bound(world, bound)["master"] == master
    assert world.facts(predicate="enslaved")
    assert victim is not None


def test_another_is_freed_with_a_grade_five_antidote_and_is_saved(game):
    world, me, here = game.world, game.player.id, game.place.id
    master, victim = a_master(game), someone(game, "held")
    C.bind(world, victim, master)
    assert "grade-5" in C.free_block(world, me, victim, here)
    A.make_pill(world, me, A.recipe_entity(world, "metal_antidote"), 5, 0.9)
    commit(world, C.free_events(world, me, victim, here))
    assert C.bound(world, victim) is None
    assert any(m.feeling == "saved" for m in world.memories(victim, about=me))


def test_the_rules_hold_the_bound_to_living_people(game):
    world = game.world
    master, victim = a_master(game), someone(game, "rule")
    C.bind(world, victim, master)
    assert check_alchemy_world(world) == []
    world.update_data(master, dead=True)
    assert "bound" in " | ".join(check_alchemy_world(world))
```

- [ ] **Step 2: Write the new modules**

`systems/control.py`:
```python
"""Control pills (phase 5c spec 6): a worm in the belly, and a master who holds the only antidote.

The bound carry `bound_to = {master, since, fed_until}`. A master feeds the antidote each month; an NPC master
always does, unless dead. Past `fed_until` each day does internal harm, and after ninety the worms wake. Freedom
is the master's death, a grade-5 antidote, a famous doctor, or forcing the worms out at realm 5. The player may be
bound (spared by an unorthodox master after a real duel), may bind (a control pill forced on the beaten), and the
world's unorthodox masters bind a few of their own. The meta row `bound` lists the NPCs bound, so only they are
looked at each season. The recipe is secret: only an unorthodox sect's hall keeps it, and no experiment finds it.
"""

import systems.alchemy as A
import systems.lives as lives
import systems.npc_alchemy  # noqa: F401  its agenda runs before the world's binding
import systems.physic as PY
import systems.world_clock as world_clock
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from world.body import WATCHES_PER_DAY, add_injury
from world.events import Event, Witness, effect, listen
from world.gen.materialize import people_at, town_label
from world.gen.region import region_spec
from world.seed import rng_for

MONTH = 30 * WATCHES_PER_DAY
STARVE_SEVERITY, STARVE_DAYS = 2, 90
FREE_GRADE = 5             # an antidote this strong kills the worms
FORCE_REALM, FORCE_QI, FORCE_CHANCE = 5, 30.0, 0.5
BIND_REALM, BIND_CHANCE = 3, 0.25   # an unorthodox master spares the player, and binds them
CURE_SEEK = 0.25           # a season's chance that one the player binds finds a cure
WORLD_BIND, WORLD_MAX = 0.02, 2     # an unorthodox master of realm 3 binds someone in a season, up to two
SERVICES = ("message", "beat", "steal")


def bound(world, person: int) -> dict | None:
    entity = world.entity(person)
    return entity.data.get("bound_to") if entity is not None else None


def servants_of(world, master: int) -> list[int]:
    return [p for p in world.get_meta("bound") or [] if (bound(world, p) or {}).get("master") == master
            and not world.entity(p).data.get("dead")]


def _index(world, person: int, on: bool) -> None:
    if world.entity(person).data.get("is_player"):
        return
    listed = [p for p in world.get_meta("bound") or [] if p != person]
    world.set_meta("bound", listed + ([person] if on else []))


def bind(world, person: int, master: int) -> None:
    world.update_data(person, bound_to={"master": master, "since": world.time, "fed_until": world.time + MONTH,
                                        "hurt_to": world.time + MONTH})
    _index(world, person, True)


def free(world, person: int) -> None:
    world.update_data(person, bound_to=None)
    _index(world, person, False)


def days_starved(world, person: int) -> float:
    b = bound(world, person)
    return max(0.0, (world.time - b["fed_until"]) / WATCHES_PER_DAY) if b else 0.0


def starve(world, person: int) -> None:
    """The days past feeding, each an internal wound, brought up to now (lazily, on the day each fell)."""
    b = bound(world, person)
    if not b or world.time <= b["fed_until"]:
        return
    start = max(b["fed_until"], b.get("hurt_to", b["fed_until"]))
    days = int((world.time - start) // WATCHES_PER_DAY)
    if days <= 0:
        return
    body = load_body(world, person)
    for day in range(1, days + 1):
        add_injury(body, "torso", "internal", STARVE_SEVERITY, start + day * WATCHES_PER_DAY, "the worms of a control pill")
    save_body(world, person, body)
    world.update_data(person, bound_to={**b, "hurt_to": start + days * WATCHES_PER_DAY})


def death_events(world, person: int) -> list[Event]:
    """Past ninety days unfed the worms wake: the death they bring, laid at the master's door."""
    b = bound(world, person)
    entity = world.entity(person)
    if not b or entity.data.get("dead") or days_starved(world, person) <= STARVE_DAYS:
        return []
    master = b["master"] if world.entity(b["master"]) is not None else person
    if entity.data.get("is_player"):
        from systems.mortality import death_events as dying
        return dying(world, person, "control_pill", master)
    return [Event("died", (master, person), lives.home(world, person), {"cause": "control_pill", "world": True})]


def fed(world, master: int) -> bool:
    """An NPC master feeds their bound always, while alive (spec 6)."""
    entity = world.entity(master)
    return entity is not None and not entity.data.get("dead") and not entity.data.get("is_player")


def season_hook(world, n: int) -> list[Event]:
    """The bound NPCs: fed by their living NPC masters, freed by a dead one, starved by a careless player; those the
    player binds may find a cure."""
    events = []
    for person in list(world.get_meta("bound") or []):
        entity = world.entity(person)
        b = bound(world, person)
        if entity is None or entity.data.get("dead") or not b:
            _index(world, person, False)
            continue
        master = world.entity(b["master"])
        if master is None or master.data.get("dead"):
            events.append(Event("control_freed", (person,), lives.home(world, person), {"how": "master_dead"}))
            continue
        if fed(world, b["master"]):
            world.update_data(person, bound_to={**b, "fed_until": world.time + MONTH, "hurt_to": world.time + MONTH})
            continue
        if rng_for(world.world_seed, f"cure_seek:{person}:{n}").random() < CURE_SEEK:
            events.append(Event("control_freed", (person,), lives.home(world, person), {"how": "doctor"}))
            continue
        starve(world, person)
        events += death_events(world, person)
    return events


world_clock.SEASON_HOOKS.append(season_hook)


@effect("control_freed")
def _freed(world, event) -> None:
    free(world, event.actors[0])


@listen("control_freed")
def _freed_news(world, event, event_id: int) -> None:
    person = event.actors[0]
    record_fact(world, person, "freed", None, place=event.place, source_event=event_id, weight=1.0,
                variant=make_variant("freed", person, None, place=place_name(world, event.place)))


@listen("died")
def _master_dies(world, event, event_id: int) -> None:
    """Nothing more is owed to a dead master: their bound are free, and grateful to whoever killed them."""
    killer, dead = event.actors[0], event.actors[-1]
    if world.entity(dead).data.get("bound_to"):
        world.update_data(dead, bound_to=None)
        _index(world, dead, False)
    player = world.get_meta("player_id")
    freed = servants_of(world, dead) + ([player] if isinstance(player, int)
                                        and (bound(world, player) or {}).get("master") == dead else [])
    for person in freed:
        free(world, person)
        if killer != dead and person != killer:
            world.add_memory(person, event_id, "grateful", 0.8, False, ignore_existing=True)


# --- the worms fought ---------------------------------------------------------------------------------------

def antidote_frees(world, person: int, grade: int) -> None:
    """A grade-5 antidote swallowed kills the worms (spec 6)."""
    if grade >= FREE_GRADE and bound(world, person):
        free(world, person)


def force_block(world, person: int) -> str | None:
    if not bound(world, person):
        return "No worms sleep in you."
    body = load_body(world, person)
    if body.realm < FORCE_REALM:
        return "Only a transcendent master can force the worms out."
    if body.qi < FORCE_QI:
        return "Your qi is too low to drive them out."
    return None


def force_events(world, person: int, place) -> list[Event]:
    roll = rng_for(world.world_seed, f"force_worms:{person}:{world.time}").random()
    return [Event("worms_forced", (person,), place, {"cleared": roll < FORCE_CHANCE})]


@effect("worms_forced")
def _forced(world, event) -> None:
    person = event.actors[0]
    body = load_body(world, person)
    body.qi = max(0.0, body.qi - FORCE_QI)
    save_body(world, person, body)
    if event.data["cleared"]:
        free(world, person)


PY.CURE_HOOKS["control"] = (lambda world, person: bool(bound(world, person)), free)


# --- the player bound -----------------------------------------------------------------------------------------

def binds(world, npc: int) -> bool:
    return PY.unorthodox(world, npc) and realm_index(world.entity(npc).data.get("realm", "mortal")) >= BIND_REALM


@listen("duel_ended")
def _spared_and_bound(world, event, event_id: int) -> None:
    """After a real duel lost to an unorthodox master who spares them, the player may wake with the worms."""
    player, opponent = event.actors
    d = event.data
    if d.get("result") != "lost" or d.get("by") != "opponent" or d.get("mode") not in ("duel", "encounter") \
            or d.get("verdict") not in ("spare", "rob") or bound(world, player) or not binds(world, opponent):
        return
    if rng_for(world.world_seed, f"bound:{event_id}").random() < BIND_CHANCE:
        bind(world, player, opponent)


def service(world, person: int) -> dict | None:
    """This month's service the master demands (seeded): carry a message, beat a fighter, or steal from a sect."""
    b = bound(world, person)
    if not b:
        return None
    month = world.time // MONTH
    rng = rng_for(world.world_seed, f"service:{person}:{b['master']}:{month}")
    kind = rng.choice(SERVICES)
    out = {"kind": kind, "month": month}
    if kind == "message":
        here = world.entity(lives.home(world, person) or 0)
        x = (here.data["x"] if here is not None and here.kind == "town" else 0) + rng.randint(-2, 2)
        y = (here.data["y"] if here is not None and here.kind == "town" else 0) + rng.randint(-2, 2)
        i = rng.randrange(region_spec(world.world_seed, x, y).town_count)
        out.update(at=[x, y, i], town=town_label(world, x, y, i))
    return out


def service_done(world, person: int) -> bool:
    """Whether this month's service is done: the town reached, a fighter beaten, or a sect robbed unseen."""
    task = service(world, person)
    if task is None or (world.entity(person).data.get("served_month") == task["month"]):
        return False
    since = task["month"] * MONTH
    if task["kind"] == "message":
        here = world.entity(lives.home(world, person) or 0)
        return here is not None and here.kind == "town" and [here.data["x"], here.data["y"], here.data["index"]] \
            == task["at"]
    for entry in world.chronicle_about(person, limit=40):
        if entry.time < since:
            break
        if task["kind"] == "beat" and entry.kind == "duel_ended" and entry.data.get("result") == "won" \
                and entry.data.get("mode") in ("duel", "encounter") and entry.actors[0] == person:
            return True
        if task["kind"] == "steal" and entry.kind == "hall_theft" and not entry.data.get("caught"):
            return True
    return False


def served_events(world, person: int, place) -> list[Event]:
    task = service(world, person)
    return [Event("service_rendered", (person, bound(world, person)["master"]), place, {"kind": task["kind"],
                                                                                      "month": task["month"]})]


@effect("service_rendered")
def _served(world, event) -> None:
    person = event.actors[0]
    b = bound(world, person)
    until = max(b["fed_until"], world.time) + MONTH
    world.update_data(person, bound_to={**b, "fed_until": until, "hurt_to": until}, served_month=event.data["month"])


# --- the player as master -------------------------------------------------------------------------------------

def control_pills(world, person: int) -> list[int]:
    import systems.pills as P
    return [p.id for p in P.pills_of(world, person) if P.effect_of(p) == "control"]


def force_feed_block(world, person: int, npc: int, place) -> str | None:
    from systems.spoils import beaten_by
    entity = world.entity(npc)
    if entity is None or entity.data.get("dead") or place not in world.targets(npc, "located_in"):
        return "They are not here."
    if entity.data.get("beast"):
        return "A beast is bound by nothing."
    if not beaten_by(world, person, npc):
        return "You have not beaten them."
    if bound(world, npc):
        return "They are bound already."
    if not control_pills(world, person):
        return "You carry no control pill."
    return None


def force_feed_events(world, person: int, npc: int, place) -> list[Event]:
    from systems.spoils import lawful
    return [Event("control_forced", (person, npc), place, {"pill": control_pills(world, person)[0],
                                                           "lawful": lawful(world, npc, place)},
                  witnesses=(Witness(npc, "hatred", 1.0, True),))]


@effect("control_forced")
def _force_fed(world, event) -> None:
    person, npc = event.actors
    world.unrelate(person, "owns", event.data["pill"])
    world.update_data(event.data["pill"], used=True)
    bind(world, npc, person)
    if not F.memberships(world, npc) and not world.entity(npc).data.get("sworn_to"):
        world.update_data(npc, sworn_to=person)  # the bound obey (3c's followers)


@listen("control_forced")
def _enslaved(world, event, event_id: int) -> None:
    if not event.data["lawful"]:
        return
    person, npc = event.actors
    record_fact(world, person, "enslaved", npc, place=event.place, source_event=event_id, weight=2.0,
                variant=make_variant("enslaved", person, npc, place=place_name(world, event.place)))


def feed_block(world, person: int, npc: int) -> str | None:
    if (bound(world, npc) or {}).get("master") != person:
        return "They are not bound to you."
    if not control_pills(world, person):
        return "You carry no control pill to send them."
    return None


def feed_events(world, person: int, npc: int, place) -> list[Event]:
    return [Event("servant_fed", (person, npc), place, {"pill": control_pills(world, person)[0]})]


@effect("servant_fed")
def _fed(world, event) -> None:
    person, npc = event.actors
    world.unrelate(person, "owns", event.data["pill"])
    world.update_data(event.data["pill"], used=True)
    b = bound(world, npc)
    until = max(b["fed_until"], world.time) + MONTH
    world.update_data(npc, bound_to={**b, "fed_until": until, "hurt_to": until})


# --- freeing another -------------------------------------------------------------------------------------------

def antidote_for(world, person: int) -> int | None:
    import systems.pills as P
    return next((p.id for p in P.pills_of(world, person) if P.effect_of(p) == "antidote"
                 and P.grade_of(p) >= FREE_GRADE), None)


def free_block(world, person: int, npc: int, place) -> str | None:
    if not bound(world, npc) or bound(world, npc)["master"] == person:
        return "No one holds them."
    if place not in world.targets(npc, "located_in"):
        return "They are not here."
    if antidote_for(world, person) is None:
        return "Only a grade-5 antidote kills the worms."
    return None


def free_events(world, person: int, npc: int, place) -> list[Event]:
    return [Event("worms_killed", (person, npc), place, {"pill": antidote_for(world, person)},
                  witnesses=(Witness(npc, "saved", 1.0),))]


@effect("worms_killed")
def _killed(world, event) -> None:
    person, npc = event.actors
    world.unrelate(person, "owns", event.data["pill"])
    world.update_data(event.data["pill"], used=True)
    free(world, npc)


@listen("worms_killed")
def _killed_news(world, event, event_id: int) -> None:
    person, npc = event.actors
    record_fact(world, person, "freed", npc, place=event.place, source_event=event_id, weight=1.5,
                variant=make_variant("freed", person, npc, place=place_name(world, event.place)))


# --- the world's masters ------------------------------------------------------------------------------------

def world_events(world, person: int, n: int, rng) -> list[Event]:
    """An unorthodox master of realm 3 binds someone of their town now and then, two at most (a lives agenda)."""
    if not binds(world, person) or len(servants_of(world, person)) >= WORLD_MAX:
        return []
    mine = rng_for(world.world_seed, f"world_bind:{lives.key(world.entity(person))}:{n}")
    if mine.random() >= WORLD_BIND:
        return []
    town = lives.home(world, person)
    victims = sorted(p.id for p in people_at(world, town) if p.id != person and lives.simulated(p)
                     and not p.data.get("bound_to")) if town is not None else []
    if not victims:
        return []
    return [Event("npc_bound", (person, mine.choice(victims)), town, {"season": n})]


lives.AGENDAS.append(world_events)


@effect("npc_bound")
def _npc_bound(world, event) -> None:
    master, victim = event.actors
    bind(world, victim, master)


@listen("npc_bound")
def _npc_bound_news(world, event, event_id: int) -> None:
    master, victim = event.actors
    record_fact(world, master, "enslaved", victim, place=event.place, source_event=event_id, weight=1.5,
                variant=make_variant("enslaved", master, victim, place=place_name(world, event.place)))
```

`systems/data/secret_recipes.toml`:
```toml
# Secret recipes (phase 5c spec 4.1, 6): learnt only from a scroll, never found by experiment (they are left out of
# `best_match`). The control pill is kept by the halls of unorthodox sects alone. `grade` is the recipe's grade.

[control]
effect = "control"
element = "poison"
polarity = "yin"
potency = 8
toxic = 8
grade = 4
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_control.py`
Expected: `4 failed, 8 passed`: the tests that need Step 4's edits fail.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5c_task6.py`:
```python
"""Phase 5c, Task 6: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('systems/world_clock.py', r'''import systems.npc_alchemy  # noqa: E402,F401  phase 5c: NPCs refine and take pills in their seasons
''', r'''import systems.npc_alchemy  # noqa: E402,F401  phase 5c: NPCs refine and take pills in their seasons
import systems.control  # noqa: E402,F401  phase 5c: control pills, their masters and their bound
''')
edit('systems/mortality.py', r'''          "founder_test": "in the founder's test", "poisoned": "of poison"}''', r'''          "founder_test": "in the founder's test", "poisoned": "of poison",
          "control_pill": "to the worms of a control pill"}''')
edit('systems/pills.py', r'''    if kind == "antidote":
        toxins.cure(world, person, d["grade"])''', r'''    if kind == "antidote":
        toxins.cure(world, person, d["grade"])
        from systems.control import antidote_frees  # phase 5c: a grade-5 antidote kills a control pill's worms
        antidote_frees(world, person, d["grade"])''')
edit('systems/recipe_trade.py', r'''    rng = rng_for(world.world_seed, f"secret:{faction}")
    return sorted(rng.sample(sorted(A.RECIPES), rng.randint(*SECRETS)))''', r'''    rng = rng_for(world.world_seed, f"secret:{faction}")
    keys = sorted(rng.sample(sorted(A.RECIPES), rng.randint(*SECRETS)))
    if world.entity(faction).data.get("type") in F.DARK:  # the control pill: an unorthodox sect's alone (Task 6)
        return ["control"] + keys[:1]
    return keys''')
edit('systems/law.py', r'''                     "poisoned_for_hire"})  # 4h: 100 silver; 5c: a hired poisoning traced''', r'''                     "poisoned_for_hire", "enslaved"})  # 4h: 100 silver; 5c: a hired poisoning, a control pill''')
edit('systems/attitude.py', r'''    "poisoned_for_hire": -1.0,
''', r'''    "poisoned_for_hire": -1.0,
    "enslaved": -0.8,  # phase 5c: a control pill forced on someone
''')
edit('debug/invariants.py', r'''    effects = SWALLOWED | {"venom", "tempering"}''', r'''    effects = SWALLOWED | {"venom", "tempering", "control"}''')
edit('debug/invariants.py', r'''    for scroll in world.entities("scroll"):''', r'''    for person in world.get_meta("bound") or []:
        entity = world.entity(person)
        b = entity.data.get("bound_to") if entity is not None else None
        if not b or entity.data.get("is_player"):
            out.append(f"the bound index lists #{person}, bound to no one")
        elif world.entity(b["master"]) is None or world.entity(b["master"]).kind != "person":
            out.append(f"{entity.name} (#{person}) is bound to #{b['master']}, no person")
        elif world.entity(b["master"]).data.get("dead") or entity.data.get("dead"):
            out.append(f"{entity.name} (#{person}) is still bound, though one of them is dead")
    for scroll in world.entities("scroll"):''')
edit('systems/alchemy.py', r'''SECRET: dict[str, dict] = {}  # recipes never found by experiment, only learnt (phase 5c: the control pill)
''', r'''SECRET = tomllib.loads((Path(__file__).parent / "data" / "secret_recipes.toml").read_text(encoding="utf-8"))
''')
edit('systems/alchemy.py', r'''              "tempering": "Tempering Draught"}''', r'''              "tempering": "Tempering Draught", "control": "Corpse-Worm Pill"}''')
print("task 6 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5c_task6.py`
Expected: `task 6 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_control.py`
Expected: `12 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1353 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: control pills - the bound, their masters, the worms, and the ways out"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 7: The player's alchemy world

`AlchemyWorldMixin` puts it all in the player's hands. In a town: the physician; in a city: the Guild; at one's own sect's seat: its pill hall and garden; at any seat with a hall: "Around the halls by night..." (wait, look, steal); for a master: "Those bound to you...". In conversation, one "Alchemy and medicine..." submenu (ruling 22) holds treating, a doctor's cures and go, a master's recipes and pills, a contract and its poisoning and fee, freeing the bound, and selling a secret to a rival's keeper; the hall keeper gives alchemy duties; a beaten foe can be bound from the scene. At a turn's end the worms and the month's service are weighed, and a void contract dropped. The sheet shows a Guild rank, a healer's towns and the worms; the alchemy page lists scrolls. Every new deed has its outcome, journal line, grammar and rumour (ruling 23), and the typed words and help reach them.

**Files:**
- Create: `engine/alchemy_world.py`
- Create: `engine/alchemy_world_page.py`
- Create: `narrate/alchemy_world_text.py`
- Create: `narrate/grammar/alchemy_world.toml`
- Create: `tests/test_alchemy_world_play.py`
- Modify (by `.patches/5c_task7.py`): `engine/game.py`, `engine/commands.py`, `engine/sheet.py`, `engine/alchemy.py`, `narrate/outcomes.py`, `narrate/duty_text.py`

**Interfaces:**
- Consumes: Everything above; 5b's `AlchemyMixin`; 5a's `GearMixin._beaten`; 3b's `_faction_options`.
- Produces:
  - `engine/alchemy_world.py` (engine/alchemy_world.py): `WORLD_MENUS`, `TALK_MENU`, `STEAL_WORDS`.
  - `engine/alchemy_world_page.py` (engine/alchemy_world_page.py): `recipe_label(world, key)`, `hall_lines(world, viewer, faction)`, `guild_lines(world, player)`, `clinic_lines(world, player, town)`, `night_lines(world, player, factions)`, `scroll_lines(world, player)`, `sheet_alchemy_world_lines(world, player)`.
  - `narrate/alchemy_world_text.py`: outcomes, journal lines, and the rumours `doctor_seen`, `guild_rank`, `robbed_hall`, `healed`, `poisoned_for_hire`, `enslaved`, `freed`, `sold_secret`, `stole`.

- [ ] **Step 1: Write the tests**

`tests/test_alchemy_world_play.py`:
```python
import pytest

import systems.alchemy as A
import systems.control as C
import systems.encounters as encounters
import systems.guild as G
import systems.hall_theft as T
import systems.physic as PY
import systems.recipe_trade as RT
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.outcomes import SUMMARIES
from systems import factions as F
from systems import halls
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import WATCHES_PER_DAY, add_injury
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


def labels(turn):
    return [c.label for c in turn.all_choices]


def pick(turn, verb):
    return next(c.action for c in turn.all_choices if c.action.verb == verb)


def go(game, place):
    world, me = game.world, game.player.id
    world.unrelate(me, "located_in")
    world.relate(me, place, "located_in")


def the_sect(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    return sect, halls.seat_of(world, sect)


def a_city(world):
    from world.gen.materialize import ensure_town
    from world.gen.region import region_spec
    from world.gen.town import town_spec
    for x in range(-3, 4):
        for y in range(-3, 4):
            for i in range(region_spec(world.world_seed, x, y).town_count):
                if town_spec(world.world_seed, x, y, i).kind == "city":
                    return ensure_town(world, x, y, i)
    raise AssertionError("no city near")


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal", "age": 30,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:awplay:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_a_member_draws_and_harvests_from_the_sects_hall_and_garden(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    world.relate(me, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 300, "status": "member",
                                            "secret": False})
    go(game, seat)
    turn = game.perform(Action("look"))
    assert "Your sect's pill hall and garden" in labels(turn)
    turn = game.perform(Action("pill_hall"))
    page = " | ".join(t for t, _ in turn.lines)
    assert "Pill hall:" in page and "Herb garden:" in page
    game.perform(pick(turn, "draw_pill"))
    assert any(world.entity(i).kind == "pill" for i in world.targets(me, "owns"))
    turn = game.perform(Action("pill_hall"))
    game.perform(pick(turn, "harvest"))
    assert any(world.entity(i).kind == "herb" for i in world.targets(me, "owns"))


def test_the_guild_is_joined_and_sat_in_a_city_and_its_scrolls_read(game, monkeypatch):
    world, me = game.world, game.player.id
    go(game, a_city(world))
    turn = game.perform(Action("look"))
    assert "The Alchemists' Guild" in labels(turn)
    turn = game.perform(Action("guild"))
    game.perform(pick(turn, "guild_join"))
    assert world.entity(me).data["guild_rank"] == 0
    world.relate(me, A.recipe_entity(world, "calming"), "knows_recipe", 0.5)
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (1.0, 1.0))
    turn = game.perform(Action("guild"))
    game.perform(pick(turn, "guild_exam"))
    assert world.entity(me).data["guild_rank"] == 1
    turn = game.perform(Action("guild"))
    game.perform(pick(turn, "buy_scroll"))
    turn = game.perform(Action("alchemy"))
    assert "Scrolls you carry:" in " | ".join(t for t, _ in turn.lines)
    known = len(A.known_recipes(world, me))
    game.perform(pick(turn, "read_scroll"))
    assert len(A.known_recipes(world, me)) == known + 1
    assert any("Alchemists' Guild: a first-rank alchemist" in t for t, _ in sheet_lines(world, me))


def test_the_physician_treats_and_tells_of_famous_doctors(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    add_injury(body, "left arm", "cut", 3, world.time, "a test")
    save_body(world, me, body)
    turn = game.perform(Action("look"))
    assert "Visit the physician" in labels(turn)
    turn = game.perform(Action("clinic"))
    game.perform(pick(turn, "physician_treat"))
    turn = game.perform(Action("clinic"))
    turn = game.perform(pick(turn, "ask_doctor"))
    assert any("was last seen in" in t for t, _ in turn.lines)
    turn = game.perform(Action("clinic"))
    assert any("was last seen in" in t for t, _ in turn.lines)


def test_by_night_a_thief_waits_looks_and_steals(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    while T.night(world):
        world.set_time(world.time + 1)
    turn = game.perform(Action("night"))
    turn = game.perform(pick(turn, "nightfall"))
    assert T.night(world)
    turn = game.perform(Action("night"))
    turn = game.perform(pick(turn, "survey"))
    assert any("Pill hall:" in t for t, _ in turn.lines)
    monkeypatch.setattr(T, "BOUNDS", (1.0, 1.0))
    turn = game.perform(Action("night"))
    steal = next(c.action for c in turn.all_choices if c.action.verb == "steal" and c.action.target[1] == "hall")
    game.perform(steal)
    assert any(world.entity(i).kind == "pill" for i in world.targets(me, "owns"))


def test_the_guardian_of_a_garden_comes_out_of_the_dark(game):
    import systems.lives as lives
    world = game.world
    sect, seat = the_sect(world)
    go(game, seat)
    while not T.night(world):
        world.set_time(world.time + 1)
    name = sorted(__import__("systems.pill_hall", fromlist=["x"]).garden(world, sect))[0]
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {name: [4, 2]}})
    game.perform(Action("steal", (sect, "garden")))
    assert game.encounter is not None


def test_a_sick_npc_is_treated_through_the_talk_menu(game):
    world, me = game.world, game.player.id
    sick = someone(game, "sick")
    body = load_body(world, sick)
    add_injury(body, "torso", "cut", 2, world.time, "a test")
    save_body(world, sick, body)
    A.make_pill(world, me, A.recipe_entity(world, "wood_healing"), 1, 0.8)
    turn = game.perform(Action("talk", sick))
    assert "Alchemy and medicine..." in labels(turn)
    turn = game.perform(Action("remedies"))
    turn = game.perform(pick(turn, "heal"))
    assert PY.ailment(world, sick) is None


def test_bound_to_a_master_the_sheet_says_so_and_the_worms_kill_the_unfed(game):
    world, me = game.world, game.player.id
    master = someone(game, "master", occupation="bandit", realm="first-rate")
    C.bind(world, me, master)
    text = " | ".join(t for t, _ in sheet_lines(world, me))
    assert f"Bound to {world.entity(master).name} by a control pill" in text
    world.set_time(world.time + C.MONTH + (C.STARVE_DAYS + 1) * WATCHES_PER_DAY)
    game.perform(Action("look"))
    assert world.entity(me).data.get("dying") or world.entity(me).data.get("dead")


def test_a_beaten_foe_is_bound_from_the_scene(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    commit(world, [Event("duel_ended", (me, foe), game.place.id, {
        "result": "won", "mode": "duel", "verdict": "spare", "by": "player", "silver": 0, "crippled": None,
        "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None, "purpose": None, "killed": False,
        "left_for_dead": False, "duel": None, "reason": "yielded"})])
    game._beaten = foe
    A.make_pill(world, me, A.recipe_entity(world, "control"), 4, 0.6)
    turn = game.perform(Action("look"))
    game.perform(pick(turn, "force_control"))
    assert C.bound(world, foe)["master"] == me
    A.make_pill(world, me, A.recipe_entity(world, "control"), 4, 0.6)
    turn = game.perform(Action("bound_menu"))
    game.perform(pick(turn, "feed_servant"))
    assert C.bound(world, foe)["fed_until"] > world.time + C.MONTH


def test_an_alchemy_duty_is_asked_of_the_hall_keeper(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    world.relate(me, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 0, "status": "member",
                                            "secret": False})
    go(game, seat)
    keeper = halls.keeper_at(world, sect, seat)
    game.perform(Action("talk", keeper))
    turn = game.perform(Action("faction_menu"))
    assert "Ask for an alchemy duty" in labels(turn)
    turn = game.perform(pick(turn, "alchemy_duty"))
    assert any("to the seat" in t for t, _ in turn.lines)


def test_typed_words_reach_the_alchemy_world(game):
    turn = game.perform(Action("look"))
    for word, verb in (("guild", "guild"), ("clinic", "clinic"), ("doctors", "ask_doctor"), ("night", "night"),
                       ("pill hall", "pill_hall"), ("bound", "bound_menu"), ("read", "read_scroll")):
        assert parse(word, turn.choices, turn.extra).verb == verb


def test_help_names_the_alchemy_world(game):
    assert any("guild | clinic | doctors" in t for t, _ in game.perform(Action("help")).lines)


def test_every_alchemy_world_deed_has_a_journal_line():
    for kind in ("pill_drawn", "garden_harvested", "secret_scroll_given", "guild_joined", "guild_exam",
                 "scroll_bought", "scroll_sold", "scroll_read", "recipe_taught", "secret_sold", "physician_treated",
                 "physician_cured", "body_read", "asked_doctor", "go_played", "doctor_cured", "waited_for_night",
                 "hall_surveyed", "hall_theft", "healed", "patient_brought", "contract_taken", "contract_poisoned",
                 "contract_paid", "contract_void", "npc_pill_bought", "service_rendered", "worms_forced",
                 "control_forced", "servant_fed", "worms_killed", "control_freed"):
        assert kind in SUMMARIES, kind


def test_rumours_of_the_alchemy_world_read_as_sentences(game):
    from narrate.gossip_text import rumour_text
    from systems.facts import make_variant
    world, me = game.world, game.player.id
    sect, _ = the_sect(world)
    ranked = make_variant("guild_rank", me, None)
    ranked.update(rank=5)
    assert rumour_text(world, ranked, me) == "You are now a fifth-rank alchemist."
    robbed = make_variant("robbed_hall", None, sect)
    robbed.update(what="garden")
    assert rumour_text(world, robbed, me) == f"Someone robbed the {world.entity(sect).name}'s herb garden in the night."
    assert rumour_text(world, make_variant("stole", me, sect), me) == f"You stole from the {world.entity(sect).name}."
    assert RT.price("calming") == 100 and G.title(1) == "a first-rank alchemist"
```

- [ ] **Step 2: Write the new modules**

`engine/alchemy_world.py`:
```python
"""The alchemy world in the engine (phase 5c spec 7): a sect's pill hall and garden, the Guild, the clinic and the
famous doctors, theft by night, healing, poison for hire, and control pills from all three sides."""

import systems.control as C
import systems.duties as duties
import systems.encounters as encounters
import systems.guild as G
import systems.hall_theft as T
import systems.npc_alchemy as N
import systems.physic as PY
import systems.pill_hall as PH
import systems.recipe_trade as RT
from engine.actions import Action, Choice
from engine.alchemy_world_page import clinic_lines, guild_lines, hall_lines, night_lines, recipe_label, scroll_lines
from systems import factions as F
from systems import halls
from systems.bodies import load_body

WORLD_MENUS = ("pill_hall", "guild", "clinic", "night", "bound")
TALK_MENU = "remedies"
STEAL_WORDS = {"garden": "herbs from the {name}'s garden", "hall": "pills from the {name}'s pill hall",
               "scroll": "a secret scroll from the {name}'s pill hall"}


class AlchemyWorldMixin:
    # --- where things are -------------------------------------------------------------------------------------
    def _seats_here(self) -> list[int]:
        return [f for f in self.world.entity(self.place.id).data.get("seats", [])
                if not self.world.entity(f).data.get("dissolved")]

    def _my_halls(self) -> list[int]:
        """Sects seated here whose hall or garden the player may use: their own."""
        me = self.player.id
        return [f for f in self._seats_here() if (PH.keeps_hall(self.world, f) or PH.keeps_garden(self.world, f))
                and (F.membership(self.world, me, f) or (0, {}))[1].get("status") == "member"]

    def _robbable(self) -> list[int]:
        return [f for f in self._seats_here() if PH.keeps_hall(self.world, f) or PH.keeps_garden(self.world, f)]

    # --- choices -----------------------------------------------------------------------------------------------
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, here = self.world, self.player.id, self.place.id
        if self.world.entity(here).kind != "town":
            return extras
        if self._my_halls():
            extras.append(Choice("Your sect's pill hall and garden", Action("pill_hall")))
        if G.branch_here(world, here):
            extras.append(Choice("The Alchemists' Guild", Action("guild")))
        extras.append(Choice("Visit the physician", Action("clinic")))
        if self._robbable():
            extras.append(Choice("Around the halls by night...", Action("night")))
        if C.servants_of(world, me):
            extras.append(Choice("Those bound to you...", Action("bound_menu")))
        if C.force_block(world, me) is None:
            extras.append(Choice("Force the worms out with your qi", Action("force_worms")))
        beaten = getattr(self, "_beaten", None)
        if beaten is not None and C.force_feed_block(world, me, beaten, here) is None:
            extras.append(Choice(f"Force a control pill on {world.entity(beaten).name}", Action("force_control", beaten)))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if self._remedies(npc):
            extras.append(Choice("Alchemy and medicine...", Action("remedies")))
        return extras

    def _remedies(self, npc) -> list:
        """What the player can do with this person, alchemy-wise (the talk submenu)."""
        world, me, here = self.world, self.player.id, self.place.id
        out = []
        if PY.heal_block(world, me, npc.id, here) is None:
            out.append(Choice(f"Offer to treat {npc.name}", Action("heal", npc.id)))
        if npc.data.get("doctor"):
            for what in PY.doctor_cures(world, me):
                out.append(Choice(f"Ask them to cure your {what}", Action("doctor_cure", (npc.id, what))))
            if npc.data["doctor"]["whim"] == "eccentric" and npc.id not in (world.entity(me).data.get("go_won") or []):
                out.append(Choice("Play them at go", Action("play_go", npc.id)))
        if G.is_alchemist(world, npc.id):
            for key in RT.teach_offers(world, me, npc.id):
                if RT.teach_block(world, me, npc.id, key) is None:
                    out.append(Choice(f"Learn their {recipe_label(world, key)} ({RT.price(key)} silver)",
                                      Action("learn_recipe", (npc.id, key))))
            for grade in N.stall_offers(world, npc.id):
                out.append(Choice(f"Buy a grade-{grade} pill ({N.stall_price(grade)} silver)",
                                  Action("buy_npc_pill", (npc.id, grade))))
        offer = PY.contract_offer(world, npc.id, me)
        if offer is not None:
            out.append(Choice(f"Take their silver to poison {world.entity(offer['target']).name} ({offer['silver']})",
                              Action("take_contract", npc.id)))
        if PY.contract_poison_block(world, me, npc.id, here) is None:
            out.append(Choice(f"Slip poison into {npc.name}'s cup", Action("contract_poison", npc.id)))
        if PY.fee_block(world, me, npc.id) is None:
            out.append(Choice("Claim your fee for the poisoning", Action("claim_fee", npc.id)))
        if C.free_block(world, me, npc.id, here) is None:
            out.append(Choice(f"Kill the worms in {npc.name} with your antidote", Action("free_bound", npc.id)))
        for fid, _, d in F.memberships(world, npc.id):
            if d.get("role") != "keeper" or d.get("status", "member") != "member":
                continue
            for scroll in RT.scrolls_of(world, me):
                if RT.secret_sale_block(world, me, scroll.id, fid, here) is None:
                    sect = world.entity(scroll.data["faction"]).name
                    price = RT.price(scroll.data["key"]) * RT.RIVAL_SHARE
                    out.append(Choice(f"Sell them the {sect}'s secret ({price} silver)",
                                      Action("sell_secret", (npc.id, scroll.id, fid))))
        return out

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        world, me, here = self.world, self.player.id, self.place.id
        if duties.open_duty(world, me) is not None:
            return options
        for fid in halls.recruits_for(world, npc.id):
            found = F.membership(world, me, fid)
            if found and found[1].get("status", "member") == "member" and halls.keeper_at(world, fid, here) == npc.id \
                    and PH.keeps_hall(world, fid) and world.entity(fid).data.get("seat") == here:
                options.append(Choice("Ask for an alchemy duty", Action("alchemy_duty", fid)))
        return options

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        world, me, here = self.world, self.player.id, self.place.id
        if self.focus is not None:
            if self.submenu == TALK_MENU:
                options[TALK_MENU] = (self._remedies(world.entity(self.focus)), Action("talk_menu"))
            return options
        if self.submenu == "alchemy" and "alchemy" in options:  # scrolls are read from the alchemy page
            choices, back = options["alchemy"]
            reads = [Choice(f"Read {s.name}", Action("read_scroll", s.id)) for s in RT.scrolls_of(world, me)
                     if RT.read_block(world, me, s.id) is None]
            options["alchemy"] = (reads + choices, back)
        if self.submenu not in WORLD_MENUS:
            return options
        choices = []
        if self.submenu == "pill_hall":
            for fid in self._my_halls():
                name = world.entity(fid).name
                for grade, kind in PH.offers(world, me, fid):
                    cost = PH.cost(world, fid, grade)
                    choices.append(Choice(f"Draw a grade-{grade} {kind} pill from the {name} ({cost} merit)",
                                          Action("draw_pill", (fid, grade, kind))))
                for herb, (count, grade) in sorted(PH.garden(world, fid).items()):
                    if count > 0 and PH.harvest_block(world, me, fid, herb, here) is None:
                        choices.append(Choice(f"Harvest {herb} from the {name}'s garden "
                                              f"({PH.harvest_cost(world, fid, grade)} merit)", Action("harvest", (fid, herb))))
                if not PH.own(world, fid):
                    for key in RT.secret_recipes(world, fid):
                        if RT.secret_block(world, me, fid, key, here) is None:
                            choices.append(Choice(f"Ask for the {name}'s secret scroll ({RT.secret_cost(key)} merit)",
                                                  Action("secret_scroll", (fid, key))))
        elif self.submenu == "guild":
            if G.join_block(world, me, here) is None:
                choices.append(Choice("Join the Guild", Action("guild_join")))
            if G.exam_block(world, me, here) is None:
                rank = world.entity(me).data["guild_rank"] + 1
                choices.append(Choice(f"Sit the examination for the {G.ORDINALS[rank]} rank "
                                      f"({G.EXAM_FEE * rank} silver)", Action("guild_exam")))
            for key in RT.guild_offers(world, me):
                if RT.buy_block(world, me, key, here) is None:
                    choices.append(Choice(f"Buy a scroll of {recipe_label(world, key)} ({RT.price(key)} silver)",
                                          Action("buy_scroll", key)))
            for scroll in RT.scrolls_of(world, me):
                choices.append(Choice(f"Sell {scroll.name} ({RT.sell_price(world, scroll.id)} silver)",
                                      Action("sell_scroll", scroll.id)))
        elif self.submenu == "clinic":
            for injury in PY.treatable(load_body(world, me), world.time):
                choices.append(Choice(f"Have your {injury.location} treated ({PY.treat_price(injury.severity)} silver)",
                                      Action("physician_treat", injury.id)))
            if PY.cure_block(world, me, here) is None:
                grade = PY.curable(load_body(world, me))
                choices.append(Choice(f"Have your poison cured ({PY.cure_price(grade)} silver)", Action("physician_cure")))
            if PY.read_block(world, me, here) is None and load_body(world, me).poisons:
                choices.append(Choice(f"Have your body read ({PY.READ_PRICE} silver)", Action("read_body")))
            choices.append(Choice("Ask after famous doctors", Action("ask_doctor")))
        elif self.submenu == "night":
            if not T.night(world):
                choices.append(Choice("Wait for nightfall", Action("nightfall")))
            for fid in self._robbable():
                name = world.entity(fid).name
                if T.look_block(world, me, fid, here) is None:
                    choices.append(Choice(f"Look over the {name}'s hall and garden", Action("survey", fid)))
                for target, words in STEAL_WORDS.items():
                    why = T.steal_block(world, me, fid, target, here)
                    if why is None or why == "Something guards the garden.":
                        choices.append(Choice(f"Steal {words.format(name=name)}", Action("steal", (fid, target))))
        elif self.submenu == "bound":
            for servant in C.servants_of(world, me):
                if C.feed_block(world, me, servant) is None:
                    choices.append(Choice(f"Send {world.entity(servant).name} the month's antidote",
                                          Action("feed_servant", servant)))
        options[self.submenu] = (choices, Action("back"))
        return options

    # --- the world around ---------------------------------------------------------------------------------------
    def _after_arrival(self) -> list:
        lines = super()._after_arrival()
        world, me, here = self.world, self.player.id, self.place.id
        if world.entity(here).kind == "town":
            brought = PY.patient_events(world, me, here)
            if brought:
                lines += self._commit(brought)
        return lines

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        bound = C.bound(self.world, self.player.id)
        if entry is not None and bound and bound["since"] >= entry.time and bound["master"] == entry.actors[1]:
            lines.append((f"You wake with a bitter taste. {self.world.entity(entry.actors[1]).name} has fed you "
                          "a control pill: serve, or the worms wake.", "red"))
        return lines

    def _after_turn(self, turn):
        """After the whole deed: the worms of an unfed control pill, the month's service, a void contract."""
        turn = super()._after_turn(turn)
        world, me = self.world, self.player.id
        if self.player.data.get("dying") or self.player.data.get("dead"):
            return turn
        lines = []
        if C.bound(world, me):
            if C.service_done(world, me):
                lines += self._commit(C.served_events(world, me, self.place.id))
            C.starve(world, me)
            deaths = C.death_events(world, me)
            if deaths:
                return self._turn(list(turn.lines) + self._commit(deaths) + self._death_lines())
        if PY.contract_lapsed(world, me):
            lines += self._commit(PY.void_events(world, me, self.place.id))
        return self._turn(list(turn.lines) + lines) if lines else turn

    # --- handlers: the sect's hall and garden -----------------------------------------------------------------------
    def _do_pill_hall(self, _target):
        self.submenu = "pill_hall"
        lines = []
        for fid in self._my_halls():
            lines += hall_lines(self.world, self.player.id, fid)
        return self._turn(lines or [("You belong to no sect that keeps a hall here.", "system")])

    def _do_draw_pill(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        faction, grade, kind = target if isinstance(target, tuple) and len(target) == 3 else (None, 0, "")
        self.submenu = "pill_hall"
        if faction is None or (why := PH.draw_block(world, me, faction, grade, kind, here)) is not None:
            return self._turn([(why if faction is not None else "There is no such pill.", "system")])
        return self._turn(self._commit(PH.draw_events(world, me, faction, grade, kind, here)))

    def _do_harvest(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        faction, herb = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        self.submenu = "pill_hall"
        if faction is None or (why := PH.harvest_block(world, me, faction, herb, here)) is not None:
            return self._turn([(why if faction is not None else "Nothing like that grows here.", "system")])
        return self._turn(self._commit(PH.harvest_events(world, me, faction, herb, here)))

    def _do_secret_scroll(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        faction, key = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        self.submenu = "pill_hall"
        if faction is None or (why := RT.secret_block(world, me, faction, key, here)) is not None:
            return self._turn([(why if faction is not None else "The hall keeps no such scroll.", "system")])
        return self._turn(self._commit(RT.secret_events(world, me, faction, key, here)))

    # --- handlers: the Guild and scrolls ----------------------------------------------------------------------------
    def _do_guild(self, _target):
        if not G.branch_here(self.world, self.place.id):
            return self._turn([("The Guild keeps its branches in the cities.", "system")])
        self.submenu = "guild"
        return self._turn(guild_lines(self.world, self.player.id))

    def _do_guild_join(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "guild"
        if (why := G.join_block(world, me, here)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(G.join_events(world, me, here)))

    def _do_guild_exam(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "guild"
        if (why := G.exam_block(world, me, here)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(G.exam_events(world, me, here)))

    def _do_buy_scroll(self, key):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "guild"
        if not isinstance(key, str) or (why := RT.buy_block(world, me, key, here)) is not None:
            return self._turn([(why if isinstance(key, str) else "The Guild sells no such scroll.", "system")])
        return self._turn(self._commit(RT.buy_events(world, me, key, here)))

    def _do_sell_scroll(self, item):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "guild"
        if (why := RT.sell_block(world, me, item, here)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(RT.sell_events(world, me, item, here)))

    def _do_read_scroll(self, item):
        world, me = self.world, self.player.id
        if item is None:  # typed: the first scroll one has not yet learnt
            item = next((s.id for s in RT.scrolls_of(world, me) if RT.read_block(world, me, s.id) is None), None)
        self.submenu = "alchemy"
        if item is None or (why := RT.read_block(world, me, item)) is not None:
            return self._turn([(why if item is not None else "You have no scroll to read.", "system")])
        return self._turn(self._commit(RT.read_events(world, me, item, self.place.id)))

    def _do_alchemy(self, target):
        turn = super()._do_alchemy(target)
        turn.lines += scroll_lines(self.world, self.player.id)
        return turn

    # --- handlers: the clinic and the doctors -------------------------------------------------------------------------
    def _do_clinic(self, _target):
        if (why := PY.clinic_block(self.world, self.place.id)) is not None:
            return self._turn([(why, "system")])
        self.submenu = "clinic"
        return self._turn(clinic_lines(self.world, self.player.id, self.place.id))

    def _clinic_deed(self, why, events):
        self.submenu = "clinic"
        if why is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(events()))

    def _do_physician_treat(self, injury):
        world, me, here = self.world, self.player.id, self.place.id
        return self._clinic_deed(PY.treat_block(world, me, injury, here),
                                 lambda: PY.treat_events(world, me, injury, here))

    def _do_physician_cure(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        return self._clinic_deed(PY.cure_block(world, me, here), lambda: PY.cure_events(world, me, here))

    def _do_read_body(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        return self._clinic_deed(PY.read_block(world, me, here), lambda: PY.read_events(world, me, here))

    def _do_ask_doctor(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        return self._clinic_deed(PY.clinic_block(world, here), lambda: PY.ask_events(world, me, here))

    # --- handlers: by night --------------------------------------------------------------------------------------------
    def _do_night(self, _target):
        if not self._robbable():
            return self._turn([("No sect keeps a hall here.", "system")])
        self.submenu = "night"
        return self._turn(night_lines(self.world, self.player.id, self._robbable()))

    def _do_nightfall(self, _target):
        self.submenu = "night"
        if T.night(self.world):
            return self._turn([("It is dark already.", "system")])
        return self._turn(self._commit(T.nightfall_events(self.world, self.player.id, self.place.id)))

    def _do_survey(self, faction):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "night"
        if faction not in self._robbable() or (why := T.look_block(world, me, faction, here)) is not None:
            return self._turn([(why if faction in self._robbable() else "There is nothing to look at.", "system")])
        lines = self._commit(T.look_events(world, me, faction, here))
        return self._turn(lines + hall_lines(world, me, faction))

    def _do_steal(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        faction, what = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        if faction not in self._robbable():
            return self._turn([("There is nothing of theirs to take here.", "system")])
        why = T.steal_block(world, me, faction, what, here)
        if why == "Something guards the garden.":  # the guardian comes out of the dark (spec 2.4)
            met = T.guardian_events(world, me, faction, here)
            lines = self._commit(met)
            self.encounter = encounters.encounter_state(met[0])
            return self._turn(lines)
        self.submenu = "night"
        if why is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(T.steal_events(world, me, faction, what, here)))

    # --- handlers: in conversation -------------------------------------------------------------------------------------
    def _do_remedies(self, _target):
        if self.focus is None or not self._remedies(self.world.entity(self.focus)):
            return self._turn([("There is nothing of that kind to do with them.", "system")])
        self.submenu = TALK_MENU
        npc = self.world.entity(self.focus)
        rank = G.rank_of(self.world, npc.id) if G.is_alchemist(self.world, npc.id) else None
        told = [(f"{npc.name} is {G.title(rank)}.", "dim")] if rank else []  # their rank, told when you talk shop
        return self._turn(told + [("What will you do?", "system")])

    def _talk_deed(self, npc, why, events):
        if self.focus != npc:
            return self._turn([("They are not the one you are speaking with.", "system")])
        if why is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(events()))

    def _do_heal(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        return self._talk_deed(npc, PY.heal_block(world, me, npc, here), lambda: PY.heal_events(world, me, npc, here))

    def _do_doctor_cure(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        doctor, what = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        if doctor is None or not world.entity(doctor).data.get("doctor") or what not in PY.doctor_cures(world, me):
            return self._turn([("They cannot help you with that.", "system")])
        return self._talk_deed(doctor, PY.terms_block(world, me, doctor, here),
                               lambda: PY.doctor_events(world, me, doctor, what, here))

    def _do_play_go(self, doctor):
        world, me, here = self.world, self.player.id, self.place.id
        if doctor is None or not world.entity(doctor).data.get("doctor"):
            return self._turn([("They do not play.", "system")])
        return self._talk_deed(doctor, None, lambda: PY.go_events(world, me, doctor, here))

    def _do_learn_recipe(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, key = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        return self._talk_deed(npc, RT.teach_block(world, me, npc, key) if npc else "They teach nothing.",
                               lambda: RT.teach_events(world, me, npc, key, here))

    def _do_buy_npc_pill(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, grade = target if isinstance(target, tuple) and len(target) == 2 else (None, 0)
        return self._talk_deed(npc, N.stall_block(world, me, npc, grade) if npc else "They sell no pills.",
                               lambda: N.stall_events(world, me, npc, grade, here))

    def _do_take_contract(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        offer = PY.contract_offer(world, npc, me) if npc is not None else None
        return self._talk_deed(npc, None if offer else "They offer you nothing.",
                               lambda: PY.contract_events(world, me, offer, here))

    def _do_contract_poison(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        return self._talk_deed(npc, PY.contract_poison_block(world, me, npc, here),
                               lambda: PY.contract_poison_events(world, me, npc, here))

    def _do_claim_fee(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        return self._talk_deed(npc, PY.fee_block(world, me, npc), lambda: PY.fee_events(world, me, npc, here))

    def _do_free_bound(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        return self._talk_deed(npc, C.free_block(world, me, npc, here), lambda: C.free_events(world, me, npc, here))

    def _do_sell_secret(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, item, buyer = target if isinstance(target, tuple) and len(target) == 3 else (None, None, None)
        return self._talk_deed(npc, RT.secret_sale_block(world, me, item, buyer, here) if npc else "They buy nothing.",
                               lambda: RT.secret_sale_events(world, me, item, buyer, here))

    def _do_alchemy_duty(self, faction):
        world, me, here = self.world, self.player.id, self.place.id
        if self.focus is None or halls.keeper_at(world, faction, here) != self.focus or not PH.keeps_hall(world, faction):
            return self._turn([("Only the keeper of a pill hall gives alchemy duties.", "system")])
        if duties.open_duty(world, me) is not None:
            return self._turn([("Finish your current duty first.", "system")])
        self.submenu = None
        return self._turn(self._commit(duties.issue_events(world, me, faction, self.focus, here, kind="alchemy")))

    # --- handlers: control pills ---------------------------------------------------------------------------------------
    def _do_force_control(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        if not isinstance(npc, int) or (why := C.force_feed_block(world, me, npc, here)) is not None:
            return self._turn([(why if isinstance(npc, int) else "There is no one to bind.", "system")])
        return self._turn(self._commit(C.force_feed_events(world, me, npc, here)))

    def _do_bound_menu(self, _target):
        world, me = self.world, self.player.id
        servants = C.servants_of(world, me)
        if not servants:
            return self._turn([("No one is bound to you.", "system")])
        self.submenu = "bound"
        lines = [("Bound to you by the worms:", "heading")]
        for servant in servants:
            days = max(0, round((C.bound(world, servant)["fed_until"] - world.time) / 4))
            lines.append((f"  {world.entity(servant).name}: fed for {days} more day(s)", "dim"))
        return self._turn(lines)

    def _do_feed_servant(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "bound"
        if not isinstance(npc, int) or (why := C.feed_block(world, me, npc)) is not None:
            return self._turn([(why if isinstance(npc, int) else "No one is bound to you.", "system")])
        return self._turn(self._commit(C.feed_events(world, me, npc, here)))

    def _do_force_worms(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        if (why := C.force_block(world, me)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(C.force_events(world, me, here)))
```

`engine/alchemy_world_page.py`:
```python
"""The alchemy world's pages (phase 5c spec 7-8): a hall and garden as known, the Guild, the clinic, the dark, the
scrolls one carries, and the sheet's lines (a Guild rank, a healer's name, the worms)."""

import systems.control as C
import systems.guild as G
import systems.hall_theft as T
import systems.physic as PY
import systems.pill_hall as PH
import systems.recipe_trade as RT
from systems.bodies import load_body
from systems.time import format_season_year


def recipe_label(world, key: str) -> str:
    """A recipe's world name once it has one, else its plain kind (asking never names it)."""
    found = world.entity_by_seed(f"recipe:{key}")
    return found.name if found is not None else key.replace("_", " ")


def hall_lines(world, viewer: int, faction: int) -> list:
    """What a sect's hall and garden hold, only for one who knows them (spec 8)."""
    name = world.entity(faction).name
    if not T.knows_hall(world, viewer, faction):
        return [(f"You do not know what the {name} keeps.", "dim")]
    lines = [(f"The {name}", "heading")]
    if PH.keeps_hall(world, faction):
        stock = sorted(PH.table(world, faction).items())
        held = ", ".join(f"{count} grade-{key.split(':')[0]} {key.split(':')[1]}" for key, count in stock if count > 0)
        lines.append((f"  Pill hall: {held or 'empty'}", "dim"))
        if not PH.own(world, faction):
            secrets = ", ".join(recipe_label(world, k) for k in RT.secret_recipes(world, faction))
            lines.append((f"  Its secret recipes: {secrets}", "dim"))
    if PH.keeps_garden(world, faction):
        grown = ", ".join(f"{count} {herb} ({'a hundred years' if grade >= 2 else 'ten years' if grade else 'young'})"
                          for herb, (count, grade) in sorted(PH.garden(world, faction).items()) if count > 0)
        lines.append((f"  Herb garden: {grown or 'bare'}", "dim"))
        if PH.guarded(world, faction):
            lines.append(("  Something large sleeps among the oldest herbs.", "dim"))
    return lines


def guild_lines(world, player: int) -> list:
    rank = world.entity(player).data.get("guild_rank")
    lines = [("The Alchemists' Guild", "heading")]
    if rank is None:
        lines.append(("  You are not of the Guild. Joining costs nothing.", "dim"))
    else:
        lines.append((f"  You are {G.title(rank)}.", "dim"))
        if rank < G.MAX_RANK:
            lines.append((f"  The {G.ORDINALS[rank + 1]} rank asks a recipe of grade {G.needed_grade(rank + 1)} and "
                          f"{G.EXAM_FEE * (rank + 1)} silver.", "dim"))
    return lines


def clinic_lines(world, player: int, town: int) -> list:
    lines = [(f"The physician's clinic in {world.entity(town).name}", "heading")]
    seen = world.entity(player).data.get("doctors_seen") or {}
    for key, found in sorted(seen.items()):
        doctor = world.entity(found["doctor"])
        if doctor is None or doctor.data.get("dead"):
            continue
        when = format_season_year(found["season"] * 360)
        lines.append((f"  {doctor.name}, {doctor.data['doctor']['title']}, was last seen in {found['town']} "
                      f"({when}).", "dim"))
    return lines


def night_lines(world, player: int, factions: list[int]) -> list:
    lines = [("The dark is a thief's friend." if T.night(world) else "It is too light to steal.", "dim")]
    for fid in factions:
        if T.knows_hall(world, player, fid):
            lines += hall_lines(world, player, fid)
        lines.append((f"  Against the {world.entity(fid).name}: a {round(100 * T.chance(world, player, fid))}% chance "
                      "to go unseen.", "dim"))
    return lines


def scroll_lines(world, player: int) -> list:
    scrolls = RT.scrolls_of(world, player)
    if not scrolls:
        return []
    return [("Scrolls you carry:", "heading")] + [(f"  {s.name}", "dim") for s in scrolls]


def sheet_alchemy_world_lines(world, player: int) -> list:
    """The sheet's lines: a Guild rank, the towns that call you healer, the worms in you, those bound to you."""
    entity = world.entity(player)
    lines = []
    rank = entity.data.get("guild_rank")
    if rank is not None:
        lines.append((f"Alchemists' Guild: {G.title(rank)}", "default"))
    towns = PY.healer_of(world, player)
    if towns:
        lines.append(("Known as the healer of " + ", ".join(world.entity(t).name for t in towns), "default"))
    bound = C.bound(world, player)
    if bound:
        master = world.entity(bound["master"]).name
        days = (bound["fed_until"] - world.time) / 4
        state = f"fed for {max(0, round(days))} more day(s)" if days >= 0 else f"unfed for {round(-days)} day(s)"
        task = C.service(world, player)
        what = {"message": f"carry a message to {task.get('town')}", "beat": "beat a fighter in a real duel",
                "steal": "rob a sect's garden or hall unseen"}[task["kind"]]
        lines.append((f"Bound to {master} by a control pill: {state}. This month's service: {what}.", "red"))
    servants = C.servants_of(world, player)
    if servants:
        lines.append(("Bound to you: " + ", ".join(world.entity(s).name for s in servants), "default"))
    body = load_body(world, player)
    if body.poisons and any(not p.get("named") for p in body.poisons):
        lines.append(("A physician could read your body and name what poisons you.", "dim"))
    return ([("", "default"), ("Alchemy:", "heading")] + lines) if lines else []
```

`narrate/alchemy_world_text.py`:
```python
"""What the player is told of halls, gardens, the Guild, the clinic, theft, healing, contracts and the worms
(phase 5c spec 7)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import EXTRA_PHRASES, SPECIAL_PHRASES, who

import systems.guild as G


def _name(world, entity_id) -> str:
    entity = world.entity(entity_id) if isinstance(entity_id, int) else None
    return entity.name if entity else "someone"


def _where(v) -> str:
    return f" in {v['place']}" if v.get("place") else ""


# --- rumours ---------------------------------------------------------------------------------------------------

def _guild_rank(world, v, viewer) -> str:
    be = "are" if v.get("actor") == viewer else "is"
    return cap(f"{who(world, v.get('actor'), viewer)} {be} now {G.title(v.get('rank', 0))}.")


def _robbed_hall(world, v, viewer) -> str:
    what = {"garden": "herb garden", "hall": "pill hall", "scroll": "pill hall"}.get(v.get("what"), "hall")
    return f"Someone robbed the {_name(world, v.get('target'))}'s {what} in the night."


def _healed(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} healed {who(world, v.get('target'), viewer)}{_where(v)}.")


def _hired(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} poisoned {who(world, v.get('target'), viewer)} for "
               f"silver{_where(v)}.")


def _enslaved(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} fed {who(world, v.get('target'), viewer)} a control "
               f"pill{_where(v)}.")


def _freed(world, v, viewer) -> str:
    if v.get("target") is None:
        be = "are" if v.get("actor") == viewer else "is"
        return cap(f"{who(world, v.get('actor'), viewer)} {be} free of a control pill's worms.")
    return cap(f"{who(world, v.get('actor'), viewer)} freed {who(world, v.get('target'), viewer)} from a control "
               "pill's worms.")


def _doctor_seen(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)}, {v.get('title', 'a famous doctor')}, was seen{_where(v)}.")


SPECIAL_PHRASES.update({"doctor_seen": _doctor_seen, "guild_rank": _guild_rank, "robbed_hall": _robbed_hall, "healed": _healed,
                        "poisoned_for_hire": _hired, "enslaved": _enslaved, "freed": _freed})
EXTRA_PHRASES["sold_secret"] = "{actor} sold the secrets of the {target} to its enemies."
EXTRA_PHRASES["stole"] = "{actor} stole from the {target}."


# --- the sect's hall and garden -----------------------------------------------------------------------------------

@outcome("pill_drawn", body_facts=False)
def _drawn(world, event):
    d = event.data
    paid = f" for {d['merit']} merit" if d["merit"] else ""
    return [f"The hall keeper hands you a grade-{d['grade']} {d['effect']} pill{paid}."], {}


@summary("pill_drawn")
def _drawn_line(world, entry, names, place, other):
    return f"Drew a pill from the {_name(world, entry.data['faction'])}'s hall."


@outcome("garden_harvested", body_facts=False)
def _harvested(world, event):
    return [f"You cut a stem of {event.data['herb']} from the sect's garden."], {}


@summary("garden_harvested")
def _harvested_line(world, entry, names, place, other):
    return f"Harvested {entry.data['herb']} from the {_name(world, entry.data['faction'])}'s garden."


@outcome("secret_scroll_given", body_facts=False)
def _given(world, event):
    return ["An elder unlocks a lacquered box and hands you a scroll: the sect's own recipe, not to leave its walls."], {}


@summary("secret_scroll_given")
def _given_line(world, entry, names, place, other):
    return f"Was trusted with a secret recipe of the {_name(world, entry.data['faction'])}."


# --- the Guild and scrolls -----------------------------------------------------------------------------------------

@outcome("guild_joined", body_facts=False)
def _joined(world, event):
    return ["Your name goes into the Guild's register, below ten thousand others."], {}


@summary("guild_joined")
def _joined_line(world, entry, names, place, other):
    return "Joined the Alchemists' Guild."


@outcome("guild_exam", body_facts=False)
def _exam(world, event):
    d = event.data
    if d["passed"]:
        return [f"The examiners weigh your pill and nod: you are {G.title(d['rank'])}."], {}
    return [f"Your pill cracks under the examiners' eyes. The {d['fee']} silver is not returned."], {}


@summary("guild_exam")
def _exam_line(world, entry, names, place, other):
    return f"Passed the Guild's examination for the {G.ORDINALS[entry.data['rank']]} rank." \
        if entry.data["passed"] else "Failed a Guild examination."


@outcome("scroll_bought", body_facts=False)
def _scroll_bought(world, event):
    return [f"The Guild's clerk counts {event.data['price']} silver and hands you a sealed scroll."], {}


@summary("scroll_bought")
def _scroll_bought_line(world, entry, names, place, other):
    return "Bought a recipe scroll from the Guild."


@outcome("scroll_sold", body_facts=False)
def _scroll_sold(world, event):
    return [f"The Guild buys the scroll back for {event.data['price']} silver."], {}


@summary("scroll_sold")
def _scroll_sold_line(world, entry, names, place, other):
    return "Sold a recipe scroll to the Guild."


@outcome("scroll_read", body_facts=False)
def _scroll_read(world, event):
    return [f"You read the scroll twice through, and know the {_name(world, event.data['recipe'])}."], {}


@summary("scroll_read")
def _scroll_read_line(world, entry, names, place, other):
    return f"Learnt the {_name(world, entry.data['recipe'])} from a scroll."


@outcome("recipe_taught", body_facts=False)
def _taught(world, event):
    return [f"{cap(_name(world, event.actors[1]))} writes the recipe out for you, slowly, for {event.data['price']} "
            "silver."], {}


@summary("recipe_taught")
def _taught_line(world, entry, names, place, other):
    return f"Was taught a recipe by {other}."


@outcome("secret_sold", body_facts=False)
def _secret_sold(world, event):
    return [f"The {_name(world, event.data['buyer'])} pays {event.data['price']} silver for the "
            f"{_name(world, event.data['sect'])}'s secret. They will not keep your name out of it."], {}


@summary("secret_sold")
def _secret_sold_line(world, entry, names, place, other):
    return f"Sold a secret of the {_name(world, entry.data['sect'])}."


# --- the clinic and the doctors --------------------------------------------------------------------------------------

@outcome("physician_treated", body_facts=False)
def _treated(world, event):
    return [f"The physician cleans and binds your {event.data['location']}: it will heal three times as fast."], {}


@summary("physician_treated")
def _treated_line(world, entry, names, place, other):
    return f"Had a wound treated in {place}."


@outcome("physician_cured", body_facts=False)
def _cured(world, event):
    return [f"A bitter draught and a night's sweat: the poison is gone, for {event.data['price']} silver."], {}


@summary("physician_cured")
def _cured_line(world, entry, names, place, other):
    return f"Had a poison cured in {place}."


@outcome("body_read", body_facts=False)
def _read(world, event):
    return ["The physician takes your pulse at both wrists and names what is in your blood."], {}


@summary("body_read")
def _read_line(world, entry, names, place, other):
    return "Had a physician read your body."


@outcome("asked_doctor", body_facts=False)
def _asked(world, event):
    d = event.data
    from systems.physic import doctor_spec
    spec = doctor_spec(world, tuple(d["block"]))
    return [f"The physician lowers their voice: {spec['name']}, {spec['title']}, was last seen in {d['town']}."], {}


@summary("asked_doctor")
def _asked_line(world, entry, names, place, other):
    return f"Heard where a famous doctor was last seen: {entry.data['town']}."


@outcome("go_played", body_facts=False)
def _go(world, event):
    if event.data["won"]:
        return ["You win by half a stone. The doctor laughs and says they will treat you."], {}
    return ["The doctor's stones close around yours. \"Come back when you can see further,\" they say."], {}


@summary("go_played")
def _go_line(world, entry, names, place, other):
    return f"{'Beat' if entry.data['won'] else 'Lost to'} {other} at go."


@outcome("doctor_cured", body_facts=False)
def _doctor_cured(world, event):
    what = {"poison": "every poison in you", "meridian": "your broken meridians", "injury": "an old, deep wound",
            "control": "the worms of the control pill"}.get(event.data["what"], "what ailed you")
    return [f"{cap(_name(world, event.actors[1]))} works for a day and a night, and {what} is gone."], {}


@summary("doctor_cured")
def _doctor_cured_line(world, entry, names, place, other):
    return f"Was cured of {entry.data['what']} by {other}."


# --- by night -------------------------------------------------------------------------------------------------

@outcome("waited_for_night", body_facts=False)
def _waited(world, event):
    return ["You wait out the light in a quiet corner until the lanterns go out."], {}


@summary("waited_for_night")
def _waited_line(world, entry, names, place, other):
    return f"Waited for nightfall in {place}."


@outcome("hall_surveyed", body_facts=False)
def _surveyed(world, event):
    return [f"You go over the {_name(world, event.data['faction'])}'s wall and look, and touch nothing."], {}


@summary("hall_surveyed")
def _surveyed_line(world, entry, names, place, other):
    return f"Looked over the {_name(world, entry.data['faction'])}'s hall by night."


@outcome("hall_theft", body_facts=False)
def _theft(world, event):
    d = event.data
    if d["caught"]:
        return [f"A lantern swings round: you are seen, and flee with nothing. The {_name(world, d['faction'])} "
                "will know your face."], {}
    return [f"In and out unseen, with {len(d['loot'])} thing(s) of the {_name(world, d['faction'])}'s."], {}


@summary("hall_theft")
def _theft_line(world, entry, names, place, other):
    return f"{'Was caught stealing' if entry.data['caught'] else 'Stole'} from the " \
        f"{_name(world, entry.data['faction'])}."


# --- healing and poisoning ---------------------------------------------------------------------------------------

@outcome("healed", body_facts=False)
def _healed_outcome(world, event):
    name = cap(_name(world, event.actors[1]))
    if event.data["success"]:
        return [f"{name}'s colour comes back. They thank you, and do not forget it."], {}
    return [f"Your herbs do nothing for {name}."], {}


@summary("healed")
def _healed_line(world, entry, names, place, other):
    return f"Treated {other}." if entry.data["success"] else f"Failed to treat {other}."


@outcome("patient_brought", body_facts=False)
def _patient(world, event):
    return ["Word has gone round that you heal: someone is carried to you, grey-faced."], {}


@summary("patient_brought")
def _patient_line(world, entry, names, place, other):
    return f"Was brought someone sick in {place}."


@outcome("contract_taken", body_facts=False)
def _contract(world, event):
    return [f"You take {event.data['silver']} silver's worth of work: {_name(world, event.actors[2])} is to die."], {}


@summary("contract_taken")
def _contract_line(world, entry, names, place, other):
    return f"Agreed to poison {names[2] if len(names) > 2 else 'someone'} for {other}."


@outcome("contract_poisoned", body_facts=False)
def _poisoned(world, event):
    return [f"The powder goes into {_name(world, event.actors[1])}'s cup, and you are gone before they drink."], {}


@summary("contract_poisoned")
def _poisoned_line(world, entry, names, place, other):
    return f"Poisoned {other} for silver."


@outcome("contract_paid", body_facts=False)
def _paid(world, event):
    return [f"{cap(_name(world, event.actors[1]))} pays {event.data['silver']} silver and does not meet your eye."], {}


@summary("contract_paid")
def _paid_line(world, entry, names, place, other):
    return f"Was paid for a poisoning by {other}."


@outcome("contract_void", body_facts=False)
def _void(world, event):
    return ["The poisoning you were paid for will not happen now; the offer is void."], {}


@summary("contract_void")
def _void_line(world, entry, names, place, other):
    return "A contract to poison came to nothing."


@outcome("npc_pill_bought", body_facts=False)
def _pill_bought(world, event):
    return [f"You buy a grade-{event.data['grade']} pill for {event.data['price']} silver."], {}


@summary("npc_pill_bought")
def _pill_bought_line(world, entry, names, place, other):
    return f"Bought a pill from {other}."


# --- the worms ------------------------------------------------------------------------------------------------

@outcome("service_rendered", body_facts=False)
def _served(world, event):
    return [f"Word comes from {_name(world, event.actors[1])}: the service is done, and a month's antidote is "
            "left where you will find it."], {}


@summary("service_rendered")
def _served_line(world, entry, names, place, other):
    return f"Served {other} for a month's antidote."


@outcome("worms_forced", body_facts=False)
def _forced(world, event):
    if event.data["cleared"]:
        return ["You drive your qi through the belly and the worms die in a black flux. You are free."], {}
    return ["The worms twist away from your qi. They are still there."], {}


@summary("worms_forced")
def _forced_line(world, entry, names, place, other):
    return "Forced out a control pill's worms." if entry.data["cleared"] else "Tried to force out the worms."


@outcome("control_forced", body_facts=False)
def _control_forced(world, event):
    return [f"You force the pill down {_name(world, event.actors[1])}'s throat. From now on they need you "
            "every month."], {}


@summary("control_forced")
def _control_forced_line(world, entry, names, place, other):
    return f"Fed {other} a control pill."


@outcome("servant_fed", body_facts=False)
def _servant_fed(world, event):
    return [f"The month's antidote goes to {_name(world, event.actors[1])}."], {}


@summary("servant_fed")
def _servant_fed_line(world, entry, names, place, other):
    return f"Sent {other} the antidote."


@outcome("worms_killed", body_facts=False)
def _worms_killed(world, event):
    return [f"Your antidote kills the worms in {_name(world, event.actors[1])}. They weep."], {}


@summary("worms_killed")
def _worms_killed_line(world, entry, names, place, other):
    return f"Freed {other} from a control pill."


@outcome("control_freed", body_facts=False)
def _control_freed(world, event):
    return ["The worms are dead; no one's antidote is needed now."], {}


@summary("control_freed")
def _control_freed_line(world, entry, names, place, other):
    return "Was freed of a control pill."
```

`narrate/grammar/alchemy_world.toml`:
```toml
# The alchemy world (phase 5c): halls and gardens, the Guild, the clinic, the dark, and the worms.

[symbols]
hall_air = ["Jars line the shelves, each sealed with red wax.", "The pill hall smells of cinnabar and old smoke.", "A disciple sweeps ash from beneath the furnaces.", "Bees work the garden rows in the sun.", "The ledger scratches as the keeper writes.", "Water ticks in a bamboo pipe among the herbs."]
guild_air = ["The Guild's hall is quiet as a library.", "A brass bell marks the examiners' hour.", "Clerks in grey pass scrolls hand to hand.", "Nine ranks of names hang carved on the wall.", "Someone argues about a recipe in a low voice.", "Incense and ink, and under them, sulphur."]
clinic_air = ["Needles lie in rows on a clean cloth.", "Dried roots hang from the rafters.", "A patient groans behind a screen.", "The clinic smells of vinegar and ginger.", "A mortar grinds somewhere in the back.", "Pulse charts are pinned to the wall."]
night_air = ["A dog barks once and falls quiet.", "The moon goes behind a cloud.", "Tiles shift underfoot.", "A watchman's lantern bobs along the far wall.", "Crickets stop, then start again.", "The wind covers your footsteps."]
worm_air = ["Something turns over in your belly.", "A cold ache settles under the ribs.", "You taste iron at the back of your throat.", "Your hands are steady; your gut is not.", "The night is long for those who need an antidote.", "A dull pulse beats where no pulse should."]

[pill_drawn]
colour = "dim"
lines = ["#hall_air#"]

[garden_harvested]
colour = "dim"
lines = ["#hall_air#"]

[secret_scroll_given]
colour = "dim"
lines = ["#hall_air#"]

[guild_joined]
colour = "dim"
lines = ["#guild_air#"]

[guild_exam]
colour = "dim"
lines = ["#guild_air#"]

[scroll_bought]
colour = "dim"
lines = ["#guild_air#"]

[scroll_sold]
colour = "dim"
lines = ["#guild_air#"]

[scroll_read]
colour = "dim"
lines = ["#guild_air#"]

[recipe_taught]
colour = "dim"
lines = ["#guild_air#"]

[secret_sold]
colour = "dim"
lines = ["#guild_air#"]

[npc_pill_bought]
colour = "dim"
lines = ["#guild_air#"]

[physician_treated]
colour = "dim"
lines = ["#clinic_air#"]

[physician_cured]
colour = "dim"
lines = ["#clinic_air#"]

[body_read]
colour = "dim"
lines = ["#clinic_air#"]

[asked_doctor]
colour = "dim"
lines = ["#clinic_air#"]

[go_played]
colour = "dim"
lines = ["#clinic_air#"]

[doctor_cured]
colour = "dim"
lines = ["#clinic_air#"]

[healed]
colour = "dim"
lines = ["#clinic_air#"]

[patient_brought]
colour = "dim"
lines = ["#clinic_air#"]

[waited_for_night]
colour = "dim"
lines = ["#night_air#"]

[hall_surveyed]
colour = "dim"
lines = ["#night_air#"]

[hall_theft]
colour = "dim"
lines = ["#night_air#"]

[contract_taken]
colour = "dim"
lines = ["#night_air#"]

[contract_poisoned]
colour = "dim"
lines = ["#night_air#"]

[contract_paid]
colour = "dim"
lines = ["#night_air#"]

[contract_void]
colour = "dim"
lines = ["#night_air#"]

[service_rendered]
colour = "dim"
lines = ["#worm_air#"]

[worms_forced]
colour = "dim"
lines = ["#worm_air#"]

[control_forced]
colour = "dim"
lines = ["#worm_air#"]

[servant_fed]
colour = "dim"
lines = ["#worm_air#"]

[worms_killed]
colour = "dim"
lines = ["#worm_air#"]

[control_freed]
colour = "dim"
lines = ["#worm_air#"]
```

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_alchemy_world_play.py`
Expected: `13 failed`: the engine has no handlers for the new verbs until Step 4 puts the mixin into `Game`.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5c_task7.py`:
```python
"""Phase 5c, Task 7: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('engine/game.py', r'''from engine.alchemy import AlchemyMixin
''', r'''from engine.alchemy import AlchemyMixin
from engine.alchemy_world import AlchemyWorldMixin
''')
edit('engine/game.py', r'''class Game(AlchemyMixin, GearMixin,''', r'''class Game(AlchemyWorldMixin, AlchemyMixin, GearMixin,''')
edit('engine/game.py', r'''    ("  alchemy | gather | herbalist | taste <herb> | refine <recipe> | swallow | seal | force out: herbs, pills, poison",
     "system"),''', r'''    ("  alchemy | gather | herbalist | taste <herb> | refine <recipe> | swallow | seal | force out: herbs, pills, poison",
     "system"),
    ("  guild | clinic | doctors | pill hall | night | bound | read <scroll> | treat <name>: the alchemy world",
     "system"),''')
edit('engine/commands.py', r'''    "light furnace": Action("experiment"), "experiment": Action("experiment"), "empty furnace": Action("empty_furnace"),''', r'''    "light furnace": Action("experiment"), "experiment": Action("experiment"), "empty furnace": Action("empty_furnace"),
    "guild": Action("guild"), "clinic": Action("clinic"), "physician": Action("clinic"), "doctors": Action("ask_doctor"),
    "ask after doctors": Action("ask_doctor"), "pill hall": Action("pill_hall"), "garden": Action("pill_hall"),
    "night": Action("night"), "nightfall": Action("nightfall"), "wait for night": Action("nightfall"),
    "bound": Action("bound_menu"), "read": Action("read_scroll"), "remedies": Action("remedies"),''')
edit('engine/commands.py', r'''    "taste": "taste", "refine": "refine", "add": "add_herb", "temper": "bathe",''', r'''    "taste": "taste", "refine": "refine", "add": "add_herb", "temper": "bathe",
    "read": "read_scroll", "draw": "draw_pill", "harvest": "harvest", "steal": "steal", "treat": ("heal", "physician_treat"),
    "feed": "feed_servant",''')
edit('engine/sheet.py', r'''    from engine.crisis_page import sheet_crisis_lines  # phase 4g
    lines += sheet_crisis_lines(world, player_id)''', r'''    from engine.crisis_page import sheet_crisis_lines  # phase 4g
    lines += sheet_crisis_lines(world, player_id)
    from engine.alchemy_world_page import sheet_alchemy_world_lines  # phase 5c
    lines += sheet_alchemy_world_lines(world, player_id)''')
edit('engine/alchemy.py', r'''({H.price(world, here, o['herb'], o['grade'])} "''', r'''({H.price(world, here, o['herb'], o['grade'], me)} "''')
edit('narrate/outcomes.py', r'''import narrate.alchemy_text  # noqa: E402,F401
''', r'''import narrate.alchemy_text  # noqa: E402,F401
import narrate.alchemy_world_text  # noqa: E402,F401
''')
edit('narrate/duty_text.py', r'''         "gather": "Find out what you can about {target}", "guard": "Stand guard at the seat for {days} days"}''', r'''         "gather": "Find out what you can about {target}", "guard": "Stand guard at the seat for {days} days",
         "alchemy": "{alchemy}"}


def _alchemy(world, d) -> str:
    """An alchemy duty's task in words (phase 5c)."""
    if d.get("task") == "bring":
        return f"Bring {d['count']} {d['herb']} to the seat"
    if d.get("task") == "refine":
        return f"Refine a {world.entity(d['recipe']).name} and bring it to the seat"
    return ""''')
edit('narrate/duty_text.py', r'''    task = VERBS[d["kind"]].format(target=target, town=town, region=region, amount=d.get("amount", 0), days=d["days"])''', r'''    task = VERBS[d["kind"]].format(target=target, town=town, region=region, amount=d.get("amount", 0), days=d["days"],
                                   alchemy=_alchemy(world, d))''')
print("task 7 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5c_task7.py`
Expected: `task 7 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_alchemy_world_play.py`
Expected: `13 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1366 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the player's alchemy world - the hall, the Guild, the clinic, the dark, remedies in conversation, and the worms"
```

The message ends with the session's Co-Authored-By attribution line.

---

### Task 8: The alchemy world end to end

The fork guide's section 12, the speed of a season of NPC alchemy and of the new menus, and a wandering physician played at random.

**Files:**
- Create: `tests/test_alchemy_world_fuzz.py`
- Create: `tests/test_alchemy_world_season.py`
- Modify (by `.patches/5c_task8.py`): `docs/world-events.md`

**Interfaces:**
- Consumes: Everything above.
- Produces:
  - `docs/world-events.md` section 12; `tests/test_alchemy_world_fuzz.py`: `test_a_wandering_physician`.

- [ ] **Step 1: Write the tests**

`tests/test_alchemy_world_fuzz.py`:
```python
"""A wandering physician, played at random (phase 5c): joins the Guild, draws from a hall, steals by night, heals,
is bound and freed; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing

WORDS = ["pill hall", "guild", "clinic", "doctors", "night", "nightfall", "bound", "read", "remedies", "alchemy",
         "look", "rest", "journal", "swallow", "treat", "steal", "draw", "harvest"]


@pytest.mark.parametrize("seed", [5, 29])
def test_a_wandering_physician(tmp_path, seed):
    import systems.alchemy as A
    import systems.control as C
    from systems import factions as F
    from systems import halls
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Physician{seed}", world_seed=seed)
    world = app.game.world
    me = world.get_meta("player_id")
    world.update_data(me, silver=5000, guild_rank=1)
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.relate(me, sect, "member_of", 2, {"role": "disciple", "hall": 0, "merit": 2000, "status": "member",
                                            "secret": False})
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, A.recipe_entity(world, "calming"), "knows_recipe", 0.5)
    for key, grade in (("wood_healing", 2), ("wood_healing", 2), ("metal_antidote", 5), ("control", 4)):
        A.make_pill(world, me, A.recipe_entity(world, key), grade, 0.8)
    master = halls.staff_at(world, sect, seat, roles=("disciple",))[0]
    C.bind(world, me, master)  # bound from the start: the worms, the service and the antidote all come into play
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
    done = happened & {"pill_drawn", "garden_harvested", "secret_scroll_given", "physician_treated", "asked_doctor",
                       "waited_for_night", "hall_surveyed", "hall_theft", "healed", "scroll_read", "pill_taken",
                       "servant_fed", "service_rendered"}
    assert len(done) >= 3, done
    app.shutdown()
```

`tests/test_alchemy_world_season.py`:
```python
import gc
import time
from pathlib import Path

import pytest

import systems.control as C
import systems.encounters as encounters
import systems.lives as lives
import systems.npc_alchemy as N
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice

JOBS = ("herbalist", "wandering swordsman", "tea seller", "innkeeper")


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


def test_the_fork_guide_covers_the_alchemy_world():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("pill_hall", "garden", "guild_rank", "scroll", "secret_recipes.toml", "physician", "doctors_seen",
                 "CURE_HOOKS", "bound_to", "`bound`", "pills", "check_alchemy_world"):
        assert word in guide, word


def crowd(world, town, tag, n=200):
    out = []
    for i in range(n):
        pid = world.add_entity("person", f"Crowd {tag} {i}", {
            "occupation": JOBS[i % len(JOBS)], "traits": ["curious"], "age": 30, "silver": 200,
            "realm": "third-rate" if i % 2 else "mortal", "portrait": {"hair": 0, "face": 0, "robe": 0}},
            f"test:crowd:{tag}:{i}")
        world.relate(pid, town, "located_in")
        lives.lived_to(world, pid)
        out.append(pid)
    return out


def test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5bs(game, monkeypatch):
    world = game.world
    everything = list(lives.AGENDAS)
    ours = [N.season_events, C.world_events]
    before = [a for a in everything if a not in ours]
    crowds = [crowd(world, game.place.id, n) for n in range(6)]
    world.set_time(world.time + lives.SEASON)
    timings = {"5b": [], "5c": []}
    for n, people in enumerate(crowds):  # alternating, the best of three each: the machine's noise is not ours
        which = "5b" if n % 2 == 0 else "5c"
        monkeypatch.setattr(lives, "AGENDAS", before if which == "5b" else everything)
        gc.collect()
        start = time.process_time()
        for person in people:
            lives.catch_up(world, person)
        timings[which].append(time.process_time() - start)
    assert min(timings["5c"]) <= 1.10 * min(timings["5b"]) + 0.016, timings  # one tick of Windows' CPU clock


def at_the_seat(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.relate(me, sect, "member_of", 2, {"role": "disciple", "hall": 0, "merit": 10000, "status": "member",
                                            "secret": False})
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")


def a_city(world):
    from world.gen.materialize import ensure_town
    from world.gen.region import region_spec
    from world.gen.town import town_spec
    for x in range(-3, 4):
        for y in range(-3, 4):
            for i in range(region_spec(world.world_seed, x, y).town_count):
                if town_spec(world.world_seed, x, y, i).kind == "city":
                    return ensure_town(world, x, y, i)
    raise AssertionError("no city near")


def test_the_hall_guild_and_clinic_menus_are_quick(game):
    import systems.alchemy as A
    world, me = game.world, game.player.id
    at_the_seat(game)
    for verb in ("pill_hall", "clinic", "night"):
        assert average(lambda: game.perform(Action(verb))) < 0.02, verb
    world.unrelate(me, "located_in")
    world.relate(me, a_city(world), "located_in")
    world.update_data(me, guild_rank=3)
    world.relate(me, A.recipe_entity(world, "mending"), "knows_recipe", 0.5)
    assert average(lambda: game.perform(Action("guild"))) < 0.02
```

- [ ] **Step 2: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 3: Run the tests to see what the edits must still do**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_alchemy_world_fuzz.py tests/test_alchemy_world_season.py`
Expected: `1 failed, 4 passed`: the fork guide has no section 12 yet; the speed tests and the fuzz already pass.

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/5c_task8.py`:
```python
"""Phase 5c, Task 8: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('docs/world-events.md', r'''**The rules:** `check_alchemy` in `debug/invariants.py` holds herbs of the table, well-made pills and masteries
within 0-1; `check_body` keeps residue and venom within 0-100 and poisons well formed; `check_toxins` keeps the
poisoned index to NPCs.
''', r'''**The rules:** `check_alchemy` in `debug/invariants.py` holds herbs of the table, well-made pills and masteries
within 0-1; `check_body` keeps residue and venom within 0-100 and poisons well formed; `check_toxins` keeps the
poisoned index to NPCs.

## 12. The alchemy world (phase 5c)

**Halls and gardens** are numbers on the faction, read without writing. A sect's `pill_hall` is
`{"grade:effect": count}`, stored only once something is drawn (until then it is the seed `pill_hall:{sect}`), and
set back to its seed each spring. Its `garden` is `{"at": season, "herbs": {name: [count, grade]}}`, stored only
when something is taken; `pill_hall.garden` brings it forward from `at` (growth, ageing). The player's own sect
builds a `herb_garden` and a `pill_hall` (3c's `BUILDINGS`); its hall is filled by its alchemist disciples, worked
out from `pill_hall_at` when read.

**The Guild** is no faction: a person's `guild_rank` (0 once joined; an NPC alchemist's is seeded until first
written) and the fact `guild_rank`, whose variant carries the `rank`. **Scrolls** are entities (`kind =
"scroll"`: `recipe`, `key`, `source`, and a sect's `faction`). Secret recipes live in
`systems/data/secret_recipes.toml` (`alchemy.SECRET`), never in `recipes.toml`, so `best_match` never finds them.

**The clinic and the doctors:** a town's physician is the person `physician:{town}`, made when first paid. A
famous doctor is `doctor:{bx}:{by}` for each block of 4 x 2 regions, made when first asked after; the asker's
`doctors_seen` remembers where. `physic.CURE_HOOKS` lets a later system add what a doctor cures (the control pill
does). A player's `healings` counts healings by town; five make them its healer.

**NPC alchemy** is a lives agenda: an NPC's `pills` is `{grade: count}`, made into pill entities only when the
player robs, strips, buys or inherits them.

**Control pills:** the bound carry `bound_to = {master, since, fed_until, hurt_to}`; the meta row `bound` lists the
bound NPCs (never the player, who is watched turn by turn), so only they are looked at each season.

**Where the rules live:** `systems/pill_hall.py`, `systems/hall_theft.py`, `systems/guild.py`,
`systems/recipe_trade.py`, `systems/physic.py`, `systems/npc_alchemy.py`, `systems/control.py`; the player's side
in `engine/alchemy_world.py` and `engine/alchemy_world_page.py`.

**The rules:** `check_alchemy_world` in `debug/invariants.py` holds gardens to herbs of the table within 0-12, halls
to no less than nothing, Guild ranks within 0-9, NPCs' pills to real grades, every scroll to one owner and a
recipe, and the bound index to the living bound of living people.
''')
print("task 8 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/5c_task8.py`
Expected: `task 8 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_alchemy_world_fuzz.py tests/test_alchemy_world_season.py`
Expected: `5 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1371 passed, 1 deselected` (the slow soak is deselected).

- [ ] **Step 7: Run the 500-year soak**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: the alchemy world end to end - the fork guide, speed, and a wandering physician's fuzz"
```

The message ends with the session's Co-Authored-By attribution line.

---

## Self-review

- **Spec coverage:**
  - §2.1 the pill hall, §2.3 the garden and the own sect's garden and hall (Task 1); §2.2 alchemy duties and §2.4 theft (Task 3);
  - §3 the Guild and §4 scrolls, secrets and their sale (Task 2; the control recipe in Task 6);
  - §5.1 the physician, §5.2 famous doctors, §5.3 the healer and poison for hire (Task 4); §5.4 NPC alchemy (Task 5);
  - §6 control pills from all three sides (Task 6); §7 the player (Task 7);
  - §8 knowledge (Tasks 1-4, 7; rulings 11, 21); §9 `check_alchemy_world` (Tasks 1, 2, 5, 6); §10 level of detail and speed (rulings 5, 15; Task 8); §11 testing (every task; the fuzz and speed in Task 8).
- **Dry run:**
  - every task was applied in order to a copy of master at 82bdb6a: its new files, the run of Step 3 as it says, its edits, then the green run;
  - the whole suite passed after every task, and the 500-year soak passed at the end.
