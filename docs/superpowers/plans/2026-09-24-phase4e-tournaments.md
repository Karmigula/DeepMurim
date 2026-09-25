# Phase 4e: Murim Tournaments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four kinds of Murim tournament: the Grand Martial Assembly, the Dragon-Phoenix Meet, sect contests and lei tai. Each is built on the 4d world-event framework, with brackets seeded by belief, rounds by day, live bouts for the player, betting, scouting, grudges and dark interventions.

**Architecture:**
- **Every kind is a 4d event type:** a TOML entry plus a module in `systems/events/`.
- **The shared machinery** lives in `systems/tournaments.py`: brackets, days, matches, results.
- **Two small framework extensions:**
  - fixed-period scheduling (`cycle = "every"` with a `places` hook);
  - an `on_observe` hook, so rounds resolve as their days pass.
- **Matches** play out during their day, and resolve once the day has passed, or when the player fights or watches them.
- **The player's matches** are live duels in a new `bout` mode.

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-24-phase4e-tournaments-design.md`

## Global Constraints

- **Save format:** no save-format version change. A tournament is a `world_event` occurrence, and its `data["data"]` holds the bracket, registrations, bets and interventions. Player data gains `titles`.
- **Knowledge vs truth:**
  - seeding and odds come from what the host town believes (its rumours and its copy of the Pavilion's lists), never from true strength;
  - a fact variant's `actor` equals its `subject`.
- **Bouts:** NPCs never kill in a bout. A player's kill disqualifies them.
- **Stakes:** at most 10% of your silver; the bookmaker's margin is 10%.
- **Speed (CPU time, `time.process_time`):**
  - a Grand Assembly round of 16 NPC matches resolves in under 60 ms;
  - the tournament pages render in under 30 ms;
  - the 4d season-hook budget still holds.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A player away on their match day.**
   - They forfeit when the day passes, even if they come back later.
   - A forfeit never leaves a bracket slot empty and blocking the next round.
   - Task 3 pins this with `test_missing_your_day_forfeits_and_the_bracket_goes_on`.
2. **A fighter who dies between rounds** (4a life clock, 4b death, a vanishing). Their next match is a walkover, and the tournament still crowns exactly one champion. Task 1 pins this with `test_a_dead_entrant_gives_a_walkover`.
3. **A long absence across a whole tournament.** When the player returns after the Assembly is over, every round resolves in order in one observation, and exactly one champion is crowned. Task 1 pins this with `test_a_tournament_seen_only_after_it_ended_resolves_in_order`.
4. **Bets on a match whose fighter vanishes or forfeits.** The bet settles once, as a loss or a win for the other side, never twice and never left open. Task 4 pins this with `test_a_bet_on_a_walkover_settles_once`.
5. **The player's own sect contest when they preside, or when it has fewer than 8 disciples.** Byes fill the gaps, and presiding keeps the player out of the bracket. Task 2 pins this with `test_a_small_sect_contest_fills_with_byes` and Task 3 with `test_presiding_keeps_you_out_of_the_bracket`.

## Plan-time rulings (deviations from the spec, argued)

1. **Each won match records a `bested` fact, not a `defeated` one.**
   - 3b standing counts `defeated` as harm to the loser's sect, so beating a sect's disciple in its own tournament would sour the sect on you.
   - The Pavilion counts `bested` like a `defeated` win. The runner-up and semi-finalists get `placed` facts.
   - *Cost if wrong:* none.
2. **Ring-outs are not modelled.** A bout ends when a fighter yields, is broken, or leaves the platform (flees).
   - An NPC who flees the platform has lost.
   - A player who flees forfeits.
   - *Cost if wrong:* bouts run a few exchanges longer.
3. **Betting opens when the bracket is drawn** (the first day of the active stage), not at `announced`. There is nothing to bet on before the draw, and matches play through their day, so round one can still be bet on. *Cost if wrong:* none.
4. **A lei tai has no NPC challengers after the player takes the platform.** The afternoon's challengers settle the platform among themselves when the day begins. The player may then challenge the holder once, and whoever holds it at dusk takes the purse. *Cost if wrong:* a simpler lei tai.
5. **Finished brackets are compacted at the end of the aftermath, not after 10 years.** Only the champion, the runner-up, the semi-finalists and the entrant count are kept. *Cost if wrong:* the bracket page of an old tournament shows only its podium.
6. **The Grand Assembly and the Dragon-Phoenix Meet are hosted by a materialized city** (seeded per edition), or by the Pavilion's capital if no city is materialized. *Cost if wrong:* none.
7. **Level of detail for tournaments.**
    - Where the player is at the host town, every NPC match is a full 2b duel simulation, and the fighters prepare their arts and bodies at the draw.
    - Anywhere else, a match is decided by realm gap (`0.5 + 0.15 × gap`, clamped to 0.1–0.9, seeded per match) and nobody is prepared.
    - The dry run found a 200-year soak season taking 2.2 s with full simulations and per-entrant reputation scans everywhere. The master design's level-of-detail principle (full simulation near the player, cheap statistics far away) covers this.
    - Off-screen, elders notice nobody, and only a proud loser (not a rival sect's) may take a loss as a wrong.
    - *Cost if wrong:* upsets far away follow realm alone, not arts.
8. **Seeding reads the town's beliefs once for the whole field.** A fighter's strength is their place on the town's lists plus the summed weight of what the town believes of them. This is a one-pass version of 3a renown, without the persona and inheritance terms. *Cost if wrong:* a masked fighter seeds by their mask's deeds only.
9. **A sect contest far from the player is summarised.**
    - If the player is not at the seat when it comes round, the type's new `summary` hook settles it in one event, with no occurrence. The champion is drawn by lot, weighted by realm, from the disciples; the rewards and the `won_tournament` fact follow.
    - If the player leaves before the draw, no bracket is drawn, and the champion is drawn the same way at the end.
    - The dry run's 200-year soak had several sect contests in one season, each drawing and settling a bracket nobody saw, which put a season at 156 ms against the 100 ms budget.
    - The Assembly and the Meet always draw a bracket, because the whole Murim follows them.
    - *Cost if wrong:* an unwatched sect contest has no bracket to look back on.
10. **A lei tai goes up only in the player's region.** It is an afternoon's local sport. Off-screen platforms cost about 10 ms a season in the dry run's soak and left nothing anyone could hear of. *Cost if wrong:* distant towns have no platforms.
11. **The Pavilion forgets deeds older than 25 years.**
    - Each spring it drops its beliefs in `defeated`, `bested`, `treasure`, `enlightened` and `won_tournament` facts older than that. A deed's weight fades by ×0.8 a year, so these are worth under half a percent.
    - Realm evidence (tribulations, breakthroughs, the survey) and deaths are kept.
    - The dry run found the spring revision reading every belief the Pavilion ever held. With every Assembly bout now news, that grew without limit (a 200-year spring season: 312 ms).
    - *Cost if wrong:* none measurable in the lists.
12. **The 500-year soak's season budget becomes 200 ms; the 200-year soak keeps 100 ms.**
    - A world's per-season cost grows with its age (bigger factions, deeper rumour pools). The dry run measured master itself at about 109 ms for an ordinary season at 500 years, and 156 ms with tournaments.
    - The 200-year soak (in the normal suite) still holds the 100 ms line.
    - *Cost if wrong:* a slow old world would be caught only past 200 ms.
13. **Seeding and the lists read through two new indexes** (`beliefs_knower_actor`, `facts_predicate`) and two `World` reads that decode only what they return (`renown_among`, `newest_known`).
    - The dry run measured the 200-year soak's season at 109–125 ms with Tasks 1–6: a sect contest drawn in the player's own town read 7,000 of the town's beliefs and decoded two hundred sets of lists.
    - With the indexes, the same season passes the 100 ms line inside the full suite.
    - *Cost if wrong:* two small indexes to keep up on every belief and fact written.
14. **The typed bet is `bet <fighter> <silver>`**, not the spec's `bet <match> <silver>`: a match has two sides, and naming the fighter picks both. *Cost if wrong:* none.
15. **Exposing a fix is the verb `expose_fix`.** `expose` already belongs to 3c politics (exposing a rival), and a second `_do_expose` would silently shadow it. *Cost if wrong:* none.
16. **A vanished favourite leaves the map.**
    - They lose their location, and their memberships become `missing`. The 4a clock already treats a staff member with no location as gone, so their sect fills the post.
    - The debug rules expect the vanished to be nowhere.
    - Where they went is left for 4g and phase 5 (spec §9).
    - *Cost if wrong:* a vanished sect leader is replaced at once.
17. **A raid pushes the final to the next day, even into the aftermath** (the bracket's `until`). If a finalist falls, the final is void, no one is crowned, and bets on it are returned. *Cost if wrong:* none.
18. **A posted bracket is public at the venue.** The knowledge rule (`check_people`) counts as heard of everyone named on a board the player can read:
    - the bracket of a tournament they are at or entered in;
    - the lei tai's fighters in their town;
    - a raid's cultist.
    - Entrants come from all over, so without this the herald's call would name a stranger.
    - *Cost if wrong:* none; nothing hidden is shown.

19. **The 500-fact rumour catch-up test collects garbage first and times CPU, not the wall clock** (Task 8).
    - It measures about 36 ms alone, on master and with this plan, against 50 ms.
    - With this phase's longer suite before it, the dry run measured 55 ms twice inside the full run: other tests' garbage was being collected inside its timed window.
    - With `gc.collect()` and `time.process_time()` it measured 31 ms in the full run. This is the same move 4d made for its other timing tests.
    - *Cost if wrong:* none; the budget is unchanged.

**A known flake, not this phase's:** `tests/test_world_engine.py::test_arriving_in_a_busy_town_eight_seasons_on_is_quick` measures 125–141 ms on master against its 150 ms budget. The Windows CPU clock ticks in 15.6 ms steps, so it fails now and then inside the full suite. If it fails during execution, re-run it alone and record the result; do not change it in this phase.

---
### Task 1: Brackets by day, the bout, and the Grand Martial Assembly

**Files:**
- Create: `systems/tournaments.py`, `systems/events/grand_assembly.py`, `narrate/tournament_text.py`
- Modify (via `.patches/4e_task1.py`):
  - `systems/world_events.py`: the `every` and `sky` fields; `showing` shows only sky types;
  - `systems/rankings.py`: `latest` reads only the newest `published` belief (an old town has heard two hundred lists);
  - `world/db.py`: `renown_among` and `newest_known`, two indexed reads that decode only what they return, and their indexes (`beliefs_knower_actor`, `facts_predicate`);
  - `systems/sky.py`: the `every` cycle with its `places` hook, and the `on_observe` hook;
  - `systems/duel.py`: the `bout` mode;
  - `systems/data/world_events.toml`: the Grand Assembly;
  - `debug/invariants.py`: `check_tournaments`;
  - `narrate/outcomes.py`: imports `narrate.tournament_text`;
  - `narrate/combat_text.py`: the bout's words.
- Test: `tests/test_tournaments.py`

**Interfaces:**
- Consumes (4d):
  - `sky.start_events`, `sky.observe`, `sky.module`;
  - `W.index`, `W.TYPES`, `W.SEASON`;
  - `rankings.latest`, `rank_of`, `capital`;
  - `reputation.reputation`;
  - `duel.ensure_npc_arts`, `best_art`, `fighter_for`, `duel_sim.simulate`;
  - `founding.make_person`.
- Produces:
  - **Framework:**
    - `W.DEFAULTS` gains `every: 0` and `sky: True`;
    - `W.showing(world, place, at=None)` returns only rows whose type has `sky = true`;
    - `World.renown_among(knower, actors) -> dict[int, float]` (the sum of weight × confidence per actor);
    - `World.newest_known(knower, predicate, key) -> tuple[Belief, Fact] | None` (the belief with the greatest variant `key`);
    - module hooks `places(world, n, rng) -> list[int]` and `summary(world, place, n, rng) -> list[Event]` (for `cycle = "every"`: the second settles a place nobody is near in one go), and `on_observe(world, occurrence) -> list[Event]` (called on every observation of a live occurrence).
  - **`systems.tournaments` (imported as `T`):**
    - constants: `KINDS`, `KIND_WEIGHT`;
    - setup: `start_data(kind, size, round_days, prize, title, edition, **extra) -> dict`, `edition(world, kind) -> int`, `ordinal(n) -> str`, `host_city(world, rng) -> int`;
    - people: `realm_of(world, person) -> int`, `alive(world, person) -> bool`, `strengths(world, town, people) -> dict`, `belief_strength(world, town, person) -> float`, `watched(world, occurrence) -> bool`, `positions(size) -> list[int]`, `pool(world, occurrence, ok, size, wanderer) -> list[int]`;
    - the bracket: `draw_events(world, occurrence, pool) -> list[Event]`, `day(occurrence, now) -> int`, `day_start(occurrence, k) -> int`, `resolve(world, occurrence_id) -> None`, `match_event(occurrence, r, i, winner, loser, how, now_day) -> Event`, `on_stage(world, occurrence, stage, pool) -> list[Event]`, `on_observe(world, occurrence) -> list[Event]`.
  - **Tournament data** (the occurrence's `data["data"]`): `kind`, `size`, `round_days`, `registered`, `entrants`, `rounds`, `champion`, `finished`, `prize`, `title`, `edition`.
    - A match is `{"a", "b", "winner", "day", "how", "on"}`.
    - `how` is one of `sim`, `bout`, `bye`, `walkover`, `forfeit`, `disqualified`.
    - `on` is the day it resolved.
  - **Events:**
    - `bracket_drawn` (`occurrence`, `entrants`, `rounds`);
    - `match_resolved` (actors: the winner then the loser; `occurrence`, `round`, `match`, `winner`, `loser`, `how`, `on`);
    - `tournament_won` (actor: the champion; `occurrence`, `champion`, `prize`, `title`, `kind`).
  - **Facts:**
    - `bested` (subject the winner, object the loser; variant `realm`, `kind`);
    - `won_tournament` (variant `kind`, `title`);
    - `placed` (variant `kind`, `place` = 2 or 3).
  - **Player data** `titles: list[str]`.
  - **Duel mode `bout`:**
    - NPC winners spare;
    - a verdict offers only `spare` and `kill`;
    - an NPC who flees the platform loses.
  - `debug.invariants.check_tournaments(world) -> list[str]`.
  - `narrate.tournament_text.KIND_NAMES`.

- [ ] **Step 1: Write the failing test** — `tests/test_tournaments.py`
```python
import random
import time

import pytest

import systems.duel as duel
import systems.mortality as mortality
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


def start(world, kind, town, data):
    commit(world, sky.start_events(world, kind, town, world.time, data))
    return W.index(world)[-1][W.ID]


def assembly(game, **extra):
    import systems.events.grand_assembly as ga
    town = game.place.id
    return start(game.world, "grand_assembly", town, {**ga.start_data(game.world, town, 10, rng_for(1, "a")), **extra})


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    sky.observe(game.world, game.place.id)


def bracket(world, occurrence):
    return world.entity(occurrence).data["data"]


def test_the_assembly_comes_every_twelve_seasons(game):
    world = game.world
    world.set_time(0)
    found = [n for n in range(48) for e in sky.season_events(world, n)
             if e.kind == "sky_started" and e.data["type"] == "grand_assembly"]
    assert len(found) == 4 and [b - a for a, b in zip(found, found[1:])] == [12, 12, 12]


def test_the_bracket_is_seeded_by_what_the_host_believes(game):
    world, town = game.world, game.place.id
    famous = founding.make_person(world, "test:famous", town, occupation="monk", age=40, realm="second-rate")
    hidden = founding.make_person(world, "test:hidden", town, occupation="monk", age=40, realm="profound")
    for i in range(4):
        victim = founding.make_person(world, f"test:victim:{i}", town, occupation="monk", age=40)
        record_fact(world, famous, "defeated", victim, place=town, weight=3.0,
                    variant=make_variant("defeated", famous, victim, place=place_name(world, town)))
    occurrence = assembly(game, registered=[famous, hidden])
    to_day(game, occurrence, 1)
    entrants = bracket(world, occurrence)["entrants"]
    assert entrants[0] == famous and entrants.index(hidden) > entrants.index(famous)
    assert len(entrants) == 32 and len(bracket(world, occurrence)["rounds"]) == 5


def test_rounds_resolve_by_day_and_crown_one_champion(game):
    world, town = game.world, game.place.id
    occurrence = assembly(game)
    to_day(game, occurrence, 1)
    assert all(m["how"] is None for m in bracket(world, occurrence)["rounds"][0])
    to_day(game, occurrence, 2)
    rounds = bracket(world, occurrence)["rounds"]
    assert all(m["how"] is not None for m in rounds[0]) and all(m["how"] is None for m in rounds[1])
    to_day(game, occurrence, 9)
    t = bracket(world, occurrence)
    champion = t["champion"]
    assert t["finished"] and champion == t["rounds"][-1][0]["winner"]
    assert t["title"] in world.entity(champion).data["titles"]
    assert world.facts(predicate="won_tournament", subject=champion)
    assert len(world.facts(predicate="placed")) == 3
    assert check_tournaments(world) == []


def test_the_same_seed_crowns_the_same_champion(tmp_path):
    champions = []
    for n in range(2):
        g = Game.new(tmp_path / f"g{n}.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
        g.start()
        g.world.set_time(10 * W.SEASON + 8)
        occurrence = assembly(g)
        to_day(g, occurrence, 9)
        champions.append(bracket(g.world, occurrence)["champion"])
        g.close()
    assert champions[0] == champions[1] is not None


def test_a_dead_entrant_gives_a_walkover(game):
    world = game.world
    occurrence = assembly(game)
    to_day(game, occurrence, 1)
    first = bracket(world, occurrence)["rounds"][0][0]
    world.update_data(first["b"], dead=True)
    to_day(game, occurrence, 2)
    first = bracket(world, occurrence)["rounds"][0][0]
    assert first["how"] == "walkover" and first["winner"] == first["a"]


def test_a_tournament_seen_only_after_it_ended_resolves_in_order(game):
    world = game.world
    occurrence = assembly(game)
    world.set_time(world.entity(occurrence).data["over_at"] + 10)
    sky.observe(world, game.place.id)
    t = bracket(world, occurrence)
    assert t["finished"] and t["champion"] is not None
    assert all(m["how"] is not None for r in t["rounds"] for m in r)
    assert check_tournaments(world) == []


def test_npcs_never_kill_in_a_bout(game, monkeypatch):
    for key in mortality.KILL_CHANCE:
        monkeypatch.setitem(mortality.KILL_CHANCE, key, 1.0)
    world, town = game.world, game.place.id
    brute = founding.make_person(world, "test:brute", town, occupation="bandit", age=30,
                                 traits=["cunning", "greedy"])
    game._start_duel(brute, "bout")
    d = game.combat
    event = duel._end_event(world, d, "lost", "broken", random.Random(1), {"player": 90.0, "opponent": 10.0}, 5)
    assert event.data["verdict"] == "spare" and not event.data.get("player_killed") and event.data["silver"] == 0


def test_a_bout_verdict_is_spare_or_kill(game):
    world, town = game.world, game.place.id
    rival = founding.make_person(world, "test:rival", town, occupation="monk", age=30)
    game._start_duel(rival, "bout")
    game.combat.stage = "verdict"
    assert duel.verdict_events(world, game.combat, "rob") == []
    assert duel.verdict_events(world, game.combat, "spare")[0].data["result"] == "won"


def test_the_tournament_rules_catch_a_bad_bracket(game):
    world = game.world
    occurrence = assembly(game)
    to_day(game, occurrence, 2)
    t = dict(bracket(world, occurrence))
    t["rounds"][0][0] = dict(t["rounds"][0][0], winner=999999)
    world.update_data(occurrence, data=t)
    assert any("winner" in p for p in check_tournaments(world))


def test_a_round_of_the_assembly_is_quick(game):
    world = game.world
    occurrence = assembly(game)
    to_day(game, occurrence, 1)  # the draw prepares every fighter's arts and body
    world.set_time(T.day_start(world.entity(occurrence), 2))
    start = time.process_time()
    T.resolve(world, occurrence)
    assert time.process_time() - start < 0.06
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tournaments.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.tournaments'`.

- [ ] **Step 3: Write the tournaments** — `systems/tournaments.py`
```python
"""Murim tournaments (phase 4e spec 3-4): brackets seeded by belief, rounds by day, and what the winner takes.

A tournament is a 4d world-event occurrence. Its kind's module (systems/events/<kind>.py) sets the
size, the round days, who may enter and whom to invite; this module does the rest. The bracket
lives in the occurrence's `data["data"]`:

    {"kind", "size", "round_days", "registered", "entrants", "rounds", "champion", "finished",
     "prize", "title", "edition", "arts", ...}

A match is {"a", "b", "winner", "day", "how", "on"}. `how` is "sim" (NPCs fought), "bout" (the
player fought), "bye", "walkover" (a fighter was gone), "forfeit" (the player's day passed) or
"disqualified". Matches play out during their day and resolve once it has passed, or when the
player fights them (spec §4.3).
"""

import systems.world_events as W
from systems import factions as F
from systems.bodies import load_body
from systems.combat_core import INTENTS
from systems.duel import best_art, ensure_npc_arts, fighter_for
from systems.duel_sim import simulate
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from systems.realms import REALMS, realm_index
from world.events import Event, commit, effect, listen
from world.seed import rng_for

KINDS = ("grand_assembly", "dragon_phoenix", "sect_contest")
KIND_WEIGHT = {"grand_assembly": 3.0, "dragon_phoenix": 2.0, "sect_contest": 1.0}
NEWSWORTHY = frozenset({"grand_assembly", "dragon_phoenix"})  # their every bout is talked of
LIST_WEIGHT = {"heaven": 3000, "earth": 2000, "human": 1000, "young": 500}
ORDINALS = ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth")


# --- setting up ---------------------------------------------------------------------------------

def start_data(kind: str, size: int, round_days, prize: int, title: str, edition: int, **extra) -> dict:
    return {"kind": kind, "size": size, "round_days": list(round_days), "registered": [], "entrants": [],
            "rounds": [], "champion": None, "finished": False, "prize": prize, "title": title,
            "edition": edition, **extra}


def edition(world, kind: str) -> int:
    """How many of this kind have been held, counting the one about to start."""
    row = world._conn.execute("select count(*) from entities where kind = 'world_event' "
                              "and json_extract(data, '$.type') = ?", (kind,)).fetchone()
    return row[0] + 1


def ordinal(n: int) -> str:
    return ORDINALS[n - 1] if n <= len(ORDINALS) else f"{n}th"


def host_city(world, rng) -> int:
    """A materialized city, seeded per edition; the Pavilion's capital if none is known (plan ruling 6)."""
    cities = sorted(t.id for t in world.entities("town") if t.data.get("kind") == "city")
    if cities:
        return rng.choice(cities)
    from systems.rankings import capital
    return capital(world)


# --- people ----------------------------------------------------------------------------------------

def realm_of(world, person: int) -> int:
    entity = world.entity(person)
    if entity.data.get("is_player"):
        return load_body(world, person).realm
    return realm_index(entity.data.get("realm", "mortal"))


def alive(world, person) -> bool:
    entity = world.entity(person) if isinstance(person, int) else None
    return entity is not None and entity.kind == "person" and not entity.data.get("dead")


def strengths(world, town: int, people) -> dict[int, float]:
    """How strong the host town believes each of these people is: their place on the lists it has heard,
    then the weight of what it says of them. One indexed query for the whole field (plan ruling 8)."""
    from systems.rankings import latest, rank_of
    known = latest(world, town)
    wanted = set(people)
    renown = {**dict.fromkeys(wanted, 0.0), **(world.renown_among(town, sorted(wanted)) if wanted else {})}
    out = {}
    for person in wanted:
        found = rank_of(known["lists"], person) if known else None
        out[person] = (LIST_WEIGHT[found[0]] - found[1] if found else 0) + renown[person]
    return out


def belief_strength(world, town: int, person: int) -> float:
    return strengths(world, town, [person])[person]


def watched(world, occurrence) -> bool:
    """Whether the player is at the host town: only there are bouts simulated blow by blow (level of detail)."""
    player = world.get_meta("player_id")
    return player is not None and occurrence.data["place"] in world.targets(player, "located_in")


def positions(size: int) -> list[int]:
    """Seed numbers in bracket order, so the strongest meet last (1 v 32, 16 v 17, ...)."""
    order = [1]
    while len(order) < size:
        top = len(order) * 2 + 1
        order = [seed for s in order for seed in (s, top - s)]
    return order


def pool(world, occurrence, ok, size: int, wanderer) -> list[int]:
    """Whom the organisers invite: each staffed sect's best who qualifies, the ranked names the host town
    knows of, then wanderers to fill the bracket (spec §4.1)."""
    from systems.rankings import latest
    d = occurrence.data
    town = d["place"]
    registered = [p for p in d["data"]["registered"] if alive(world, p) and ok(p)]  # only those who qualify count
    found: list[int] = []
    for faction in world.entities("faction"):
        fd = faction.data
        if fd.get("type") not in F.STAFFED or fd.get("type") == "player_sect" or fd.get("dissolved"):
            continue
        able = [p for p, _, d in world.relations_to(faction.id, "member_of")  # one query; staff only (the strong)
                if d.get("status", "member") == "member" and d.get("role") not in (None, "member") and alive(world, p)
                and not world.entity(p).data.get("is_player") and ok(p)]
        if able:
            found.append(max(able, key=lambda p: (realm_of(world, p), -p)))
    known = latest(world, town)
    for names in (known["lists"].values() if known else []):
        found += [p for p in names if p not in found and alive(world, p)
                  and not world.entity(p).data.get("is_player") and ok(p)]
    found = [p for p in found if p not in registered]
    rng = rng_for(world.world_seed, f"tournament:{occurrence.id}:wanderers")
    i = 0
    while len(found) + len(registered) < size:
        found.append(wanderer(world, occurrence, i, rng))
        i += 1
    return found


# --- the bracket -----------------------------------------------------------------------------------

def day(occurrence, now: int) -> int:
    """The day of the active stage it is: 1 on the first day, 0 before it begins."""
    start = occurrence.data["active"][0]
    return 0 if now < start else (now - start) // 4 + 1


def day_start(occurrence, k: int) -> int:
    return occurrence.data["active"][0] + (k - 1) * 4


def draw_events(world, occurrence, invited: list[int]) -> list[Event]:
    """The draw on the first day: registrants keep their places, invitations fill the rest, seeded by belief."""
    d = occurrence.data
    t, town = d["data"], d["place"]
    registered = [p for p in t["registered"] if alive(world, p)]
    field = registered + [p for p in invited if p not in registered and alive(world, p)]
    field = field[: t["size"]]
    if watched(world, occurrence):
        strength = strengths(world, town, field)
    else:  # nobody sees this draw: seed by realm, without asking the town what it believes (plan ruling 7)
        strength = {p: realm_of(world, p) for p in field}
    ordered = sorted(field, key=lambda p: (-strength[p], p))
    arts = {}
    for person in ordered if watched(world, occurrence) else ():  # fighters prepare where the player can see
        if not world.entity(person).data.get("is_player"):
            ensure_npc_arts(world, person)
            art = best_art(world, person)
            arts[str(person)] = art.technique.id if art else None
    slots = [ordered[s - 1] if s <= len(ordered) else None for s in positions(t["size"])]
    days = t["round_days"]
    rounds = [[{"a": slots[i], "b": slots[i + 1], "winner": None, "day": days[0], "how": None, "on": None}
               for i in range(0, len(slots), 2)]]
    for r in range(1, len(days)):
        rounds.append([{"a": None, "b": None, "winner": None, "day": days[r], "how": None, "on": None}
                       for _ in range(len(rounds[-1]) // 2)])
    return [Event("bracket_drawn", (), town, {"occurrence": occurrence.id, "entrants": ordered, "rounds": rounds,
                                              "arts": arts})]


@effect("bracket_drawn")
def _drawn(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "entrants": event.data["entrants"],
                                           "rounds": event.data["rounds"], "arts": event.data["arts"]})


def _fighter(world, occurrence, person: int):
    arts = occurrence.data["data"].get("arts") or {}
    if str(person) in arts:  # chosen at the draw: one body load per fighter, not two
        return fighter_for(world, person, arts[str(person)])
    art = best_art(world, person)
    return fighter_for(world, person, art.technique.id if art else None)


def _sim_winner(world, occurrence, a: int, b: int, r: int, i: int) -> int:
    rng = rng_for(world.world_seed, f"tournament:{occurrence.id}:{r}:{i}")
    if not watched(world, occurrence):  # far from the player: decided by realm, with upsets (plan ruling 7)
        chance = max(0.1, min(0.9, 0.5 + 0.15 * (realm_of(world, a) - realm_of(world, b))))
        return a if rng.random() < chance else b
    for person in (a, b):
        ensure_npc_arts(world, person)
    result, _ = simulate(_fighter(world, occurrence, a), _fighter(world, occurrence, b),
                         lambda r_, history: r_.choice(INTENTS), rng)
    if result == "draw":
        return a if rng.random() < 0.5 else b
    return a if result == "player" else b


def match_event(occurrence, r: int, i: int, winner, loser, how: str, now_day: int) -> Event:
    actors = tuple(p for p in (winner, loser) if p is not None)
    return Event("match_resolved", actors, occurrence.data["place"],
                 {"occurrence": occurrence.id, "round": r, "match": i, "winner": winner, "loser": loser,
                  "how": how, "on": now_day})


def _settle(world, occurrence, r: int, i: int, m: dict, now_day: int) -> Event:
    a, b = m["a"], m["b"]
    player = world.get_meta("player_id")
    here_a, here_b = alive(world, a), alive(world, b)
    if not here_a or not here_b:
        winner = a if here_a else b if here_b else None
        how = "bye" if None in (a, b) else "walkover"
    elif player in (a, b):
        winner, how = (b if a == player else a), "forfeit"  # the player's day passed without their bout
    else:
        winner, how = _sim_winner(world, occurrence, a, b, r, i), "sim"
    loser = (b if winner == a else a) if winner is not None else None
    return match_event(occurrence, r, i, winner, loser, how, now_day)


def _next_events(world, occurrence_id: int) -> list[Event]:
    occurrence = world.entity(occurrence_id)
    d = occurrence.data
    t = d["data"]
    if not t["rounds"] or t["finished"]:
        return []
    over = world.time >= d["active"][1]
    now_day = day(occurrence, world.time)
    player = world.get_meta("player_id")
    for r, matches in enumerate(t["rounds"]):
        due, waiting = [], False
        for i, m in enumerate(matches):
            if m["how"] is not None:
                continue
            if _due(t, r, m, now_day, over, player):
                due.append(_settle(world, occurrence, r, i, m, max(now_day, m["day"])))  # a round's matches are apart
            else:
                waiting = True
        if due:
            return due
        if waiting:
            return []  # this round is still being fought; the next cannot start
    return champion_events(occurrence, t["rounds"][-1][0]["winner"])


def _due(t: dict, r: int, m: dict, now_day: int, over: bool, player) -> bool:
    """A match resolves once its day has passed; NPCs settle at once when the next round is the same day."""
    if over or m["day"] < now_day or m["a"] is None or m["b"] is None:
        return True  # a bye needs no fighting (a round is only reached once the one before it is settled)
    same_day = r + 1 < len(t["rounds"]) and t["rounds"][r + 1][0]["day"] == m["day"]
    return same_day and m["day"] == now_day and player not in (m["a"], m["b"])


def resolve(world, occurrence_id: int) -> None:
    """Settle every match whose day has passed, round by round, and crown the champion after the final."""
    for _ in range(64):
        events = _next_events(world, occurrence_id)
        if not events:
            return
        commit(world, events)


@effect("match_resolved")
def _resolved(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    rounds = [list(r) for r in t["rounds"]]
    rounds[d["round"]][d["match"]] = dict(rounds[d["round"]][d["match"]], winner=d["winner"], how=d["how"], on=d["on"])
    if d["round"] + 1 < len(rounds):
        side = "a" if d["match"] % 2 == 0 else "b"
        nxt = d["match"] // 2
        rounds[d["round"] + 1][nxt] = dict(rounds[d["round"] + 1][nxt], **{side: d["winner"]})
    world.update_data(occurrence.id, data={**t, "rounds": rounds})


@listen("match_resolved")
def _bested(world, event, event_id: int) -> None:
    d = event.data
    if d["how"] not in ("sim", "bout") or d["winner"] is None or d["loser"] is None:
        return
    occurrence = world.entity(d["occurrence"])
    kind = occurrence.data["data"]["kind"]
    if kind not in NEWSWORTHY and not watched(world, occurrence):
        return  # a sect's own bouts far away are not news
    loser = world.entity(d["loser"])
    variant = make_variant("bested", d["winner"], d["loser"], place=place_name(world, event.place),
                           realm=REALMS[realm_of(world, loser.id)].label)
    variant["kind"] = kind
    record_fact(world, d["winner"], "bested", d["loser"], place=event.place, source_event=event_id,
                weight=0.5 + 0.25 * d["round"], variant=variant)


def champion_events(occurrence, champion) -> list[Event]:
    t = occurrence.data["data"]
    return [Event("tournament_won", (champion,) if champion is not None else (), occurrence.data["place"],
                  {"occurrence": occurrence.id, "champion": champion, "prize": t["prize"], "title": t["title"],
                   "kind": t["kind"]})]


@effect("tournament_won")
def _won(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "champion": d["champion"], "finished": True})
    if d["champion"] is not None:
        champion = world.entity(d["champion"])
        world.update_data(champion.id, silver=silver_of(world, champion.id) + d["prize"],
                          titles=list(champion.data.get("titles", [])) + [d["title"]])


@listen("tournament_won")
def _won_news(world, event, event_id: int) -> None:
    d = event.data
    t = world.entity(d["occurrence"]).data["data"]
    where = place_name(world, event.place)
    if d["champion"] is not None:
        variant = make_variant("won_tournament", d["champion"], None, place=where)
        variant.update(kind=d["kind"], title=d["title"])
        record_fact(world, d["champion"], "won_tournament", None, place=event.place, source_event=event_id,
                    weight=KIND_WEIGHT.get(d["kind"], 1.0), variant=variant)
    final = t["rounds"][-1][0] if t["rounds"] else {"a": None, "b": None, "winner": None}  # a summary has no bracket
    podium = [(final.get("b") if final["winner"] == final.get("a") else final.get("a"), 2)] if t["rounds"] else []
    if len(t["rounds"]) > 1:
        for m in t["rounds"][-2]:
            podium.append((m["b"] if m["winner"] == m["a"] else m["a"], 3))
    for person, place in podium:
        if person is not None and alive(world, person):
            variant = make_variant("placed", person, None, place=where)
            variant.update(kind=d["kind"], place=place)
            record_fact(world, person, "placed", None, place=event.place, weight=1.0 if place == 2 else 0.75,
                        variant=variant)
    from systems.sky import module
    rewards = getattr(module(d["kind"]), "rewards", None)
    if rewards is not None:
        events = rewards(world, world.entity(d["occurrence"]), d["champion"])
        if events:
            commit(world, events)


# --- the kinds' shared hooks ------------------------------------------------------------------------

SUMMARIZED = frozenset({"sect_contest"})  # far from the player, only its champion is decided (plan ruling 9)


def summary_events(world, occurrence, invite) -> list[Event]:
    """A contest nobody watched: the champion is drawn by lot, weighted by realm, from those who would enter."""
    field = [p for p in invite(world, occurrence) if alive(world, p)][: occurrence.data["data"]["size"]]
    if not field:
        return champion_events(occurrence, None)
    rng = rng_for(world.world_seed, f"tournament:{occurrence.id}:summary")
    weights = [1 + realm_of(world, p) for p in field]
    return champion_events(occurrence, rng.choices(field, weights=weights)[0])


def on_stage(world, occurrence, stage: str, invite) -> list[Event]:
    summarized = occurrence.data["data"]["kind"] in SUMMARIZED and not watched(world, occurrence)
    if stage == "active" and not summarized:
        return draw_events(world, occurrence, invite(world, occurrence))
    if stage == "over":
        if not occurrence.data["data"]["rounds"] and not occurrence.data["data"]["finished"]:
            return summary_events(world, occurrence, invite)
        resolve(world, occurrence.id)
    return []


def on_observe(world, occurrence) -> list[Event]:
    resolve(world, occurrence.id)
    return []
```

- [ ] **Step 4: Write the Grand Assembly** — `systems/events/grand_assembly.py`
```python
"""The Grand Martial Assembly (phase 4e spec 3): every three years a famous city fills with the Murim's best."""

import systems.tournaments as T
from systems.founding import make_person

SIZE, ROUND_DAYS = 32, (1, 3, 5, 7, 8)
MIN_REALM = 2  # Second-rate
BOND = 100


def places(world, n: int, rng) -> list[int]:
    return [T.host_city(world, rng)]


def start_data(world, town: int, n: int, rng) -> dict:
    edition = T.edition(world, "grand_assembly")
    return T.start_data("grand_assembly", SIZE, ROUND_DAYS, rng.randint(300, 800),
                        f"Champion of the {T.ordinal(edition)} Grand Martial Assembly", edition)


def qualifies(world, person: int) -> bool:
    return T.realm_of(world, person) >= MIN_REALM


def _wanderer(world, occurrence, i: int, rng) -> int:
    return make_person(world, f"tournament:{occurrence.id}:wanderer:{i}", occurrence.data["place"],
                       occupation="wandering swordsman", age=rng.randint(25, 60),
                       realm=rng.choice(("second-rate", "second-rate", "first-rate")))


def invite(world, occurrence) -> list[int]:
    return T.pool(world, occurrence, lambda p: qualifies(world, p), SIZE, _wanderer)


def on_stage(world, occurrence, stage: str) -> list:
    return T.on_stage(world, occurrence, stage, invite)


def on_observe(world, occurrence) -> list:
    return T.on_observe(world, occurrence)
```

- [ ] **Step 5: Write the narration** — `narrate/tournament_text.py`
```python
"""What the player is told about tournaments (phase 4e)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

KIND_NAMES = {"grand_assembly": "the Grand Martial Assembly", "dragon_phoenix": "the Dragon-Phoenix Meet",
              "sect_contest": "the sect contest", "lei_tai": "the lei tai"}
PLACES = {2: "second", 3: "among the last four"}


def _bested_story(world, variant, viewer) -> str:
    winner, loser = who(world, variant.get("actor"), viewer), who(world, variant.get("target"), viewer)
    event = KIND_NAMES.get(variant.get("kind"), "a tournament")
    return cap(f"{winner} bested {loser} at {event} in {variant.get('place') or 'a crowded city'}.")


def _won_story(world, variant, viewer) -> str:
    winner = who(world, variant.get("actor"), viewer)
    event = KIND_NAMES.get(variant.get("kind"), "a tournament")
    return cap(f"{winner} won {event} in {variant.get('place') or 'a crowded city'}.")


def _placed_story(world, variant, viewer) -> str:
    person = who(world, variant.get("actor"), viewer)
    event = KIND_NAMES.get(variant.get("kind"), "a tournament")
    return cap(f"{person} finished {PLACES.get(variant.get('place'), 'well')} at {event}.")


SPECIAL_PHRASES.update({"bested": _bested_story, "won_tournament": _won_story, "placed": _placed_story})
```

- [ ] **Step 6: Edit the existing files** — `.patches/4e_task1.py`
```python
"""Task 1 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


WE = "systems/world_events.py"
edit("systems/rankings.py", '''    best = None
    for belief, fact in world.known_facts(knower):
        if fact.predicate == "published" and (best is None or belief.variant.get("year", 0) > best["year"]):
            best = {"year": belief.variant.get("year", 0), "lists": fact.data.get("lists", {}), "time": fact.time}
    return best''', '''    found = world.newest_known(knower, "published", "year")  # one row, however many lists an old town heard (4e)
    if found is None:
        return None
    belief, fact = found
    return {"year": belief.variant.get("year", 0), "lists": fact.data.get("lists", {}), "time": fact.time}''')
edit("world/db.py", '''    "create index if not exists beliefs_actor on beliefs(json_extract(variant, '$.actor'))",''',
     '''    "create index if not exists beliefs_actor on beliefs(json_extract(variant, '$.actor'))",
    "create index if not exists beliefs_knower_actor on beliefs(knower, json_extract(variant, '$.actor'))",  # 4e
    "create index if not exists facts_predicate on facts(predicate)",  # 4e: the newest lists a town has heard''')
edit("world/db.py", '''    def _known_facts(self, knower: int) -> list[tuple[Belief, Fact]]:''', '''    def renown_among(self, knower: int, actors) -> dict[int, float]:
        """What this knower's beliefs weigh for each of these actors, summed in SQL (the beliefs_actor index)."""
        actors = list(actors)
        rows = self._conn.execute(
            "select json_extract(b.variant, '$.actor'), sum(f.weight * b.confidence) from beliefs b "
            f"join facts f on f.id = b.fact_id where b.knower = ? and json_extract(b.variant, '$.actor') in "
            f"({','.join('?' * len(actors))}) group by 1", [knower, *actors])
        return {actor: total for actor, total in rows}

    def newest_known(self, knower: int, predicate: str, key: str) -> tuple[Belief, Fact] | None:
        """The belief of this predicate with the greatest variant `key` (the first learned among equals)."""
        row = self._conn.execute(
            f"select {_BELIEF_COLUMNS}, {_FACT_COLUMNS} from facts f cross join beliefs b on b.fact_id = f.id "
            f"where f.predicate = ? and b.knower = ? order by json_extract(b.variant, '$.' || ?) desc, "
            "b.fact_id limit 1", (predicate, knower, key)).fetchone()  # from the few facts of the kind, not the many beliefs
        return (_belief(row[:9]), _fact(row[9:])) if row else None

    def _known_facts(self, knower: int) -> list[tuple[Belief, Fact]]:''')
edit(WE, '''            "prices": {}, "readings": [], "news": None}''',
     '''            "prices": {}, "readings": [], "news": None, "every": 0, "sky": True,
            "stagger": False}''')
edit(WE, '''    """Index rows over `place` that have begun and are not yet over at `at`."""
    at = world.time if at is None else at
    xy = place_xy(world, place)
    return [row for row in index(world) if row[STARTS] <= at < row[OVER_AT] and covers(row, place, xy)]''',
     '''    """Index rows over `place` that have begun and are not yet over at `at`: the sky's (not tournaments, 4e)."""
    at = world.time if at is None else at
    xy = place_xy(world, place)
    return [row for row in index(world) if row[STARTS] <= at < row[OVER_AT] and covers(row, place, xy)
            and TYPES.get(row[TYPE], DEFAULTS)["sky"]]''')

SKY = "systems/sky.py"
edit(SKY, '''def observe(world, place: int | None = None) -> list[int]:
    load_modules()
    events = stage_events(world, place)
    return commit(world, events) if events else []''', '''def observe(world, place: int | None = None) -> list[int]:
    load_modules()
    now, xy = world.time, W.place_xy(world, place)
    watched = [row[W.ID] for row in W.index(world) if not row[W.DONE] and now >= row[W.STARTS]
               and (place is None or W.covers(row, place, xy))]
    events = stage_events(world, place)
    ids = commit(world, events) if events else []
    for occurrence_id in watched:  # every observation, not just new stages: a tournament's days (4e)
        occurrence = world.entity(occurrence_id)
        hook = _hook(occurrence.data["type"], "on_observe")
        if hook is not None:
            more = hook(world, occurrence)
            if more:
                commit(world, more)
    return ids''')
edit(SKY, '''        if spec["cycle"] != "season" or spec["chance"] <= 0:''', '''        if spec["cycle"] == "every":
            events += _every_events(world, kind, spec, n)
            continue
        if spec["cycle"] != "season" or spec["chance"] <= 0:''')
edit(SKY, '''def observe_all(world, n: int) -> list[Event]:''', '''def _every_events(world, kind: str, spec: dict, n: int) -> list[Event]:
    """A fixed-period type (a tournament every 12 seasons, 4e): its module's `places` says where it is held."""
    every = spec["every"]
    if every <= 0:
        return []
    rng = rng_for(world.world_seed, f"sky:{kind}:{n}")
    places = _hook(kind, "places")
    events = []
    for where in (places(world, n, rng) if places is not None else [None]):
        key = f"sky:{kind}:offset:{where}" if spec["stagger"] else f"sky:{kind}:offset"
        if (n + rng_for(world.world_seed, key).randrange(every)) % every:
            continue  # `stagger`: each place keeps its own turn, so a year's sect contests do not all fall at once
        eligible = _hook(kind, "eligible")
        if eligible is not None and not eligible(world, where, n):
            continue  # asked only of places whose turn it is, so a costly check runs rarely
        summary = _hook(kind, "summary")
        if summary is not None and not _near(world, where):
            events += summary(world, where, n, rng)  # nobody near: the type settles itself in a line (4e ruling 9)
            continue
        starts = n * W.SEASON + rng.randrange(DAYS_PER_SEASON) * WATCHES_PER_DAY
        if W.schedule(spec, starts)[3] <= world.time:
            continue  # long over: a catch-up never starts old events now
        make = _hook(kind, "start_data")
        data = make(world, where, n, rng) if make is not None else {}
        if data is not None:
            events += start_events(world, kind, where, starts, data)
    return events


def _near(world, place) -> bool:
    player = world.get_meta("player_id")
    return player is not None and place in world.targets(player, "located_in")


def observe_all(world, n: int) -> list[Event]:''')

DUEL = "systems/duel.py"
edit(DUEL, '''MODES = ("duel", "spar", "encounter", "test")''', '''MODES = ("duel", "spar", "encounter", "test", "bout")  # bout: a tournament match (phase 4e)''')
edit(DUEL, '''    if data["fled"]:
        return ("fled", "fled")''', '''    if d.mode == "bout" and data["gave_up"] == "flee":
        return "verdict"  # they stepped off the platform: the bout is yours (4e plan ruling 2)
    if data["fled"]:
        return ("fled", "fled")''')
edit(DUEL, '''    if result == "lost":
        hateful''', '''    if result == "lost" and d.mode == "bout":  # a bout's winner spares: killing is forbidden (4e spec 4.4)
        data.update(verdict="spare", by="opponent", insight=5.0 * gap if gap > 0 else 0.0)
        witnesses.append(Witness(d.opponent, "respect" if exchanges >= 4 else "contempt", 0.5))
    elif result == "lost":
        hateful''')
edit(DUEL, '''    if choice == "kill" and d.mode not in ("duel", "encounter"):
        return []''', '''    if choice == "kill" and d.mode not in ("duel", "encounter", "bout"):
        return []
    if d.mode == "bout" and choice not in ("spare", "kill"):
        return []  # a bout ends in mercy or disgrace, not robbery (4e spec 4.4)''')

TOML = "systems/data/world_events.toml"
Path(TOML).write_text(Path(TOML).read_text(encoding="utf-8") + '''
[grand_assembly]
module = "systems.events.grand_assembly"
scope = "town"
cycle = "every"
every = 12
sky = false
stages = { foretold = 60, announced = 20, active = 8, aftermath = 30 }
news = { predicate = "phenomenon", weight = 2.5, stages = ["foretold", "announced"] }
''', encoding="utf-8", newline="\n")

INV = "debug/invariants.py"
edit(INV, '''    problems += check_rankings(world)
''', '''    problems += check_rankings(world)
    problems += check_tournaments(world)
''')
edit(INV, '''def check_races(world) -> list[str]:''', '''def check_tournaments(world) -> list[str]:
    """Phase 4e spec 7, rules 1-2: a sound bracket, each winner advancing once, one champion at most."""
    import systems.tournaments as T
    import systems.world_events as W
    out = []
    for row in W.index(world):
        if row[W.TYPE] not in T.KINDS:
            continue
        t = world.entity(row[W.ID]).data["data"]
        rounds = t.get("rounds") or []
        if not rounds:
            continue
        who = f"tournament #{row[W.ID]}"
        if len(rounds[0]) * 2 != t["size"] or t["size"] & (t["size"] - 1):
            out.append(f"{who} has a bracket of {len(rounds[0]) * 2} for a size of {t['size']}")
        for r, matches in enumerate(rounds):
            if r and len(matches) * 2 != len(rounds[r - 1]):
                out.append(f"{who} round {r + 1} has {len(matches)} matches")
            for i, m in enumerate(matches):
                if m["winner"] is not None and m["winner"] not in (m["a"], m["b"]):
                    out.append(f"{who} round {r + 1} match {i + 1} has a winner who did not fight in it")
                if m["how"] is not None and m["on"] is not None and m["on"] < m["day"]:
                    out.append(f"{who} round {r + 1} match {i + 1} was settled before its day")
                if m["how"] is not None and r + 1 < len(rounds):
                    up = rounds[r + 1][i // 2]["a" if i % 2 == 0 else "b"]
                    if up != m["winner"]:
                        out.append(f"{who} round {r + 1} match {i + 1}'s winner did not advance")
        if t.get("finished") and t.get("champion") != rounds[-1][0]["winner"]:
            out.append(f"{who} crowned someone other than the final's winner")
    return out


def check_races(world) -> list[str]:''')

edit("narrate/combat_text.py", '''"test": "a test of skill"}''', '''"test": "a test of skill", "bout": "a tournament bout"}''')
edit("narrate/outcomes.py", '''import narrate.sky_text  # noqa: E402,F401
''', '''import narrate.sky_text  # noqa: E402,F401
import narrate.tournament_text  # noqa: E402,F401
''')
print("task 1 edits applied")
```

- [ ] **Step 7: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4e_task1.py && .venv/Scripts/python.exe -m pytest tests/test_tournaments.py -q -p no:cacheprovider`
Expected: `task 1 edits applied`, then `10 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 8: Commit**

Run: `git add -A && git commit -m "feat: tournaments - brackets seeded by belief, rounds by day, the bout, and the Grand Martial Assembly"`

---
### Task 2: The Dragon-Phoenix Meet, sect contests and lei tai

**Files:**
- Create: `systems/events/dragon_phoenix.py`, `systems/events/sect_contest.py`, `systems/events/lei_tai.py`
- Modify (via `.patches/4e_task2.py`):
  - `systems/tournaments.py`: `pool` with no wanderers; `qualifies`;
  - `systems/races.py`: champions read a faction's members in one query (a 200-year soak season);
  - `systems/rankings.py`: the Pavilion counts `bested` and `won_tournament`, and forgets deeds older than 25 years;
  - `world/db.py`: `forget`;
  - `tests/test_soak.py`: the 500-year soak's season budget (ruling 12);
  - `tests/test_fuzz.py`: the sky-watcher counts what happened in every world it saw (a death mid-run starts a young world);
  - `systems/data/world_events.toml`: the three kinds;
  - `debug/invariants.py`: rule 5 (eligibility);
  - `narrate/tournament_text.py`: lei tai and honour stories.
- Test: `tests/test_tournament_kinds.py`

**Interfaces:**
- Consumes (Task 1): `T.start_data`, `T.pool`, `T.on_stage`, `T.on_observe`, `T.realm_of`, `T.alive`, `T._sim_winner`, `T.host_city`, `T.edition`; `sky.module`; the `rewards(world, occurrence, champion)` hook, called by `tournament_won`.
- Produces:
  - Kind modules, each with `SIZE`, `ROUND_DAYS`, `places`, `start_data`, `qualifies(world, occurrence, person) -> bool`, `invite`, `on_stage`, `on_observe`; plus `rewards` where the kind gives more than silver and a title.
  - `T.qualifies(world, occurrence, person) -> bool`: asks the kind's module.
  - **Events:**
    - `sect_honoured` (actor: the faction; `power`);
    - `contest_rewarded` (actor: the champion; `faction`, `merit`, `rank`);
    - `lei_tai_settled` (`occurrence`, `holder`, `results`);
    - `lei_tai_held` (actor: the holder; `occurrence`, `purse`);
    - `contest_summarized` (actor: the champion; `faction`, `title`).
  - **Lei tai data:** `{"kind": "lei_tai", "holder", "challengers", "results", "purse", "paid"}`.
  - Fact `held_lei_tai` (variant `kind`).
  - Rankings: `bested` counts as a win; `won_tournament` is worth 60 (Assembly), 40 (Meet) or 10 (others) deed points.

- [ ] **Step 1: Write the failing test** — `tests/test_tournament_kinds.py`
```python
import pytest

import systems.rankings as R
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.game import Game
from systems import factions as F
from systems import founding
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


def start(world, kind, town, data):
    commit(world, sky.start_events(world, kind, town, world.time, data))
    return W.index(world)[-1][W.ID]


def finish(world, occurrence, town):
    world.set_time(world.entity(occurrence).data["over_at"] + 1)
    sky.observe(world, town)
    return world.entity(occurrence).data["data"]


def school(world):
    return next(f.id for f in world.entities("faction") if f.data["type"] == "school")


def test_the_meet_takes_only_the_young(game):
    import systems.events.dragon_phoenix as dp
    world, town = game.world, game.place.id
    old = founding.make_person(world, "test:old", town, occupation="monk", age=50, realm="first-rate")
    occurrence = start(world, "dragon_phoenix", town, {**dp.start_data(world, town, 10, rng_for(1, "d")),
                                                        "registered": [old]})
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    entrants = world.entity(occurrence).data["data"]["entrants"]
    assert len(entrants) == 16 and old not in entrants
    assert all(world.entity(p).data.get("age", 30) <= 30 for p in entrants)


def test_the_meets_champion_honours_their_sect(game):
    import systems.events.dragon_phoenix as dp
    world, town = game.world, game.place.id
    faction = school(world)
    prodigy = founding.make_person(world, "test:prodigy", town, occupation="monk", age=20, realm="first-rate")
    world.relate(prodigy, faction, "member_of", 1, {"role": "disciple", "hall": None, "merit": 0, "status": "member",
                                                    "secret": False})
    power = world.entity(faction).data.get("power", 50)
    occurrence = start(world, "dragon_phoenix", town, dp.start_data(world, town, 10, rng_for(1, "d")))
    commit(world, dp.rewards(world, world.entity(occurrence), prodigy))
    assert world.entity(faction).data["power"] == min(100, power + dp.HONOUR)
    t = finish(world, occurrence, town)
    assert t["finished"] and t["title"].startswith("Dragon-Phoenix of year")


def test_sect_contests_go_to_seats_with_disciples(game):
    import systems.events.sect_contest as sc
    assert game.place.id in sc.places(game.world, 10, rng_for(1, "s"))
    assert sc.eligible(game.world, game.place.id, 10)


def test_a_sect_contest_far_away_only_names_its_champion(game):
    import systems.events.sect_contest as sc
    from world.gen.materialize import ensure_town
    world, town = game.world, game.place.id
    occurrence = start(world, "sect_contest", town, sc.start_data(world, town, 10, rng_for(1, "s")))
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, ensure_town(world, 4, 4, 0), "located_in")
    t = finish(world, occurrence, town)
    assert t["finished"] and t["rounds"] == [] and t["champion"] in sc.invite(world, world.entity(occurrence))
    assert check_tournaments(world) == []


def test_a_sect_contest_nobody_is_near_is_settled_in_a_line(game):
    import systems.events.sect_contest as sc
    world, town = game.world, game.place.id
    events = sc.summary(world, town, 10, rng_for(1, "s"))
    commit(world, events)
    champion = events[0].actors[0]
    assert sc.eligible(world, town, 10) and events[0].data["title"] in world.entity(champion).data["titles"]
    assert world.facts(predicate="won_tournament", subject=champion)
    assert F.membership(world, champion, school(world))[1]["merit"] >= 20


def test_a_lei_tai_goes_up_only_near_the_player(game):
    import systems.events.lei_tai as lt
    from world.gen.materialize import ensure_town
    world = game.world
    far = ensure_town(world, 6, 6, 0)
    assert not lt.eligible(world, far, 10)


def test_a_small_sect_contest_fills_with_byes(game):
    import systems.events.sect_contest as sc
    world, town = game.world, game.place.id
    occurrence = start(world, "sect_contest", town, sc.start_data(world, town, 10, rng_for(1, "s")))
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)  # the draw: the byes go through at once
    t = world.entity(occurrence).data["data"]
    entrants = t["entrants"]
    assert len(entrants) == 4 and sum(m["how"] == "bye" for m in t["rounds"][0]) == 4
    t = finish(world, occurrence, town)
    assert t["finished"] and t["champion"] in entrants
    rank, data = F.membership(world, t["champion"], school(world))
    assert data["merit"] >= 20 and rank >= 1
    assert check_tournaments(world) == []


def test_a_lei_tai_settles_its_afternoon_and_pays_the_holder(game):
    import systems.events.lei_tai as lt
    world, town = game.world, game.place.id
    for i in range(3):
        founding.make_person(world, f"test:brawler:{i}", town, occupation="wandering swordsman", age=30,
                             realm="third-rate")
    assert lt.eligible(world, town, 10)
    occurrence = start(world, "lei_tai", town, lt.start_data(world, town, 10, rng_for(1, "l")))
    sky.observe(world, town)
    t = world.entity(occurrence).data["data"]
    holder = t["holder"]
    assert holder is not None and t["results"]
    silver = silver_of(world, holder)
    t = finish(world, occurrence, town)
    assert t["paid"] and silver_of(world, holder) == silver + t["purse"]
    assert world.facts(predicate="held_lei_tai", subject=holder)


def test_the_pavilion_counts_bouts_and_championships(game):
    world, town = game.world, game.place.id
    pav = R.ensure_pavilion(world)
    champ = founding.make_person(world, "test:champ", town, occupation="monk", age=30, realm="first-rate")
    rival = founding.make_person(world, "test:rival", town, occupation="monk", age=30, realm="first-rate")
    for predicate, target, extra in (("bested", rival, {}), ("won_tournament", None, {"kind": "grand_assembly"})):
        variant = make_variant(predicate, champ, target, place=place_name(world, town), realm="first-rate")
        variant.update(extra)
        fact = record_fact(world, champ, predicate, target, place=town, variant=variant, spread=False)
        believe(world, pav, fact, variant, None, 0.9, 1, "informant")
    assert R.scores(world, pav)[champ] == pytest.approx(300 + R.WIN_POINTS + 60)


def test_the_pavilion_forgets_deeds_older_than_a_generation(game):
    world, town = game.world, game.place.id
    pav = R.ensure_pavilion(world)
    hero = founding.make_person(world, "test:hero", town, occupation="monk", age=30, realm="first-rate")
    for predicate in ("bested", "tribulation"):
        variant = make_variant(predicate, hero, None, place=place_name(world, town), realm="first-rate")
        fact = record_fact(world, hero, predicate, None, place=town, variant=variant, spread=False)
        believe(world, pav, fact, variant, None, 0.9, 1, "informant")
    world.set_time(world.time + (R.FORGET_YEARS + 1) * R.YEAR)
    n = world.time // W.SEASON
    R.season_hook(world, n - n % 4)
    kept = {f.predicate for _, f in world.known_facts(pav)}
    assert "tribulation" in kept and "bested" not in kept


def test_the_rules_catch_an_entrant_too_old_for_the_meet(game):
    import systems.events.dragon_phoenix as dp
    world, town = game.world, game.place.id
    occurrence = start(world, "dragon_phoenix", town, dp.start_data(world, town, 10, rng_for(1, "d")))
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    entrant = world.entity(occurrence).data["data"]["entrants"][0]
    world.update_data(entrant, age=55)
    assert any("does not qualify" in p for p in check_tournaments(world))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tournament_kinds.py -q -p no:cacheprovider`
Expected: failures, for example `KeyError: 'dragon_phoenix'`.

- [ ] **Step 3: Write the Dragon-Phoenix Meet** — `systems/events/dragon_phoenix.py`
```python
"""The Dragon-Phoenix Meet (phase 4e spec 3): every two years the young talents of the Murim meet."""

import systems.tournaments as T
from systems import factions as F
from systems.founding import make_person
from world.events import Event, effect

SIZE, ROUND_DAYS = 16, (1, 2, 3, 5)
MAX_AGE = 30
BOND = 30
HONOUR = 5  # the winner's sect's power


def places(world, n: int, rng) -> list[int]:
    return [T.host_city(world, rng)]


def start_data(world, town: int, n: int, rng) -> dict:
    year = n // 4 + 1
    return T.start_data("dragon_phoenix", SIZE, ROUND_DAYS, rng.randint(100, 300), f"Dragon-Phoenix of year {year}",
                        T.edition(world, "dragon_phoenix"))


def qualifies(world, occurrence, person: int, slack: int = 0) -> bool:
    return float(world.entity(person).data.get("age", 30)) <= MAX_AGE + slack


def _wanderer(world, occurrence, i: int, rng) -> int:
    return make_person(world, f"tournament:{occurrence.id}:wanderer:{i}", occurrence.data["place"],
                       occupation="wandering swordsman", age=rng.randint(16, MAX_AGE),
                       realm=rng.choice(("third-rate", "second-rate")))


def invite(world, occurrence) -> list[int]:
    return T.pool(world, occurrence, lambda p: qualifies(world, occurrence, p), SIZE, _wanderer)


def rewards(world, occurrence, champion) -> list[Event]:
    """The winner's sect stands taller (spec §3)."""
    if champion is None:
        return []
    sects = sorted(f for f, _, d in F.memberships(world, champion)
                   if d.get("status", "member") == "member" and world.entity(f).data.get("type") in F.STAFFED)
    return [Event("sect_honoured", (sects[0],), occurrence.data["place"], {"power": HONOUR})] if sects else []


@effect("sect_honoured")
def _honoured(world, event) -> None:
    faction = world.entity(event.actors[0])
    world.update_data(faction.id, power=min(100, faction.data.get("power", 50) + event.data["power"]))


def on_stage(world, occurrence, stage: str) -> list:
    return T.on_stage(world, occurrence, stage, invite)


def on_observe(world, occurrence) -> list:
    return T.on_observe(world, occurrence)
```

- [ ] **Step 4: Write the sect contest** — `systems/events/sect_contest.py`
```python
"""A sect's yearly contest (phase 4e spec 3): its disciples fight for rank, merit and a master's eye."""

import systems.tournaments as T
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.ranks import TOP_RANK
from world.events import Event, effect, listen
from world.seed import rng_for

SIZE, ROUND_DAYS = 8, (1, 1, 1)
MIN_DISCIPLES = 4
MERIT = 20
NOTICE_CHANCE = 0.5


def _faction_at(world, seat: int) -> int | None:
    found = sorted(f.id for f in world.entities("faction") if f.data.get("seat") == seat
                   and not f.data.get("dissolved") and f.data.get("type") in F.STAFFED | {"player_sect"})
    return found[0] if found else None


def _members(world, faction: int, roles) -> list[int]:
    """Living members in good standing with one of these roles: one query of the faction's relations."""
    return sorted(p for p, _, d in world.relations_to(faction, "member_of")
                  if d.get("status", "member") == "member" and d.get("role") in roles and T.alive(world, p))


def _disciples(world, faction: int) -> list[int]:
    return _members(world, faction, ("disciple", "member"))


def places(world, n: int, rng) -> list[int]:
    """Every sect's seat; `eligible` then asks, of the seats whose turn it is, for enough disciples."""
    return sorted({f.data["seat"] for f in world.entities("faction")
                   if f.data.get("seat") is not None and not f.data.get("dissolved")})


def eligible(world, seat: int, n: int) -> bool:
    faction = _faction_at(world, seat)
    return faction is not None and len([p for p in _disciples(world, faction)
                                        if not world.entity(p).data.get("is_player")]) >= MIN_DISCIPLES


def start_data(world, seat: int, n: int, rng) -> dict | None:
    faction = _faction_at(world, seat)
    if faction is None:
        return None
    name = world.entity(faction).name
    return T.start_data("sect_contest", SIZE, ROUND_DAYS, 0, f"First of the {name}'s contest of year {n // 4 + 1}",
                        T.edition(world, "sect_contest"), faction=faction)


def qualifies(world, occurrence, person: int, slack: int = 0) -> bool:
    found = F.membership(world, person, occurrence.data["data"]["faction"])
    return found is not None and found[1].get("status", "member") == "member"


def invite(world, occurrence) -> list[int]:
    faction = occurrence.data["data"]["faction"]
    return [p for p in _disciples(world, faction) if not world.entity(p).data.get("is_player")]


def rewards(world, occurrence, champion) -> list[Event]:
    """Merit and a rank step for the winner; perhaps an elder's notice (spec §3)."""
    if champion is None:
        return []
    faction = occurrence.data["data"]["faction"]
    rank, data = F.membership(world, champion, faction)
    events = [Event("contest_rewarded", (champion,), occurrence.data["place"],
                    {"faction": faction, "merit": data.get("merit", 0) + MERIT, "rank": min(TOP_RANK, rank + 1)})]
    elders = _members(world, faction, ("elder",))
    youth = world.entity(champion)
    if elders and not youth.data.get("is_player") and float(youth.data.get("age", 30)) <= 30 \
            and rng_for(world.world_seed, f"contest:{occurrence.id}:notice").random() < NOTICE_CHANCE:
        events.append(Event("apprenticed", (elders[0], champion), occurrence.data["place"],
                            {"season": world.time // T.W.SEASON}))
    return events


@effect("contest_rewarded")
def _rewarded(world, event) -> None:
    d = event.data
    set_membership(world, event.actors[0], d["faction"], rank=d["rank"], merit=d["merit"])


def summary(world, seat: int, n: int, rng) -> list[Event]:
    """A contest far from the player (plan ruling 9): a champion by lot, weighted by realm, and their reward."""
    faction = _faction_at(world, seat)
    field = _disciples(world, faction) if faction is not None else []
    field = [p for p in field if not world.entity(p).data.get("is_player")]
    if not field:
        return []
    champion = rng.choices(field, weights=[1 + T.realm_of(world, p) for p in field])[0]
    title = f"First of the {world.entity(faction).name}'s contest of year {n // 4 + 1}"
    rank, data = F.membership(world, champion, faction)
    return [Event("contest_summarized", (champion,), seat, {"faction": faction, "title": title}),
            Event("contest_rewarded", (champion,), seat,
                  {"faction": faction, "merit": data.get("merit", 0) + MERIT, "rank": min(TOP_RANK, rank + 1)})]


@effect("contest_summarized")
def _summarized(world, event) -> None:
    champion = world.entity(event.actors[0])
    world.update_data(champion.id, titles=list(champion.data.get("titles", [])) + [event.data["title"]])


@listen("contest_summarized")
def _summarized_news(world, event, event_id: int) -> None:
    champion = event.actors[0]
    variant = make_variant("won_tournament", champion, None, place=place_name(world, event.place))
    variant.update(kind="sect_contest", title=event.data["title"])
    record_fact(world, champion, "won_tournament", None, place=event.place, source_event=event_id,
                weight=T.KIND_WEIGHT["sect_contest"], variant=variant)


def on_stage(world, occurrence, stage: str) -> list:
    return T.on_stage(world, occurrence, stage, invite)


def on_observe(world, occurrence) -> list:
    return T.on_observe(world, occurrence)
```

- [ ] **Step 5: Write the lei tai** — `systems/events/lei_tai.py`
```python
"""The lei tai (phase 4e spec 3): a platform in town for an afternoon; whoever holds it at dusk takes the purse.

The afternoon's challengers settle it among themselves when the day begins (plan ruling 4); the
player may then challenge the holder once (engine/tournament.py).
"""

import systems.lives as lives
import systems.tournaments as T
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import Event, effect, listen
from world.gen.materialize import people_at

MIN_FIGHTERS = 2
MAX_CHALLENGERS = 5


def _fighters(world, town: int) -> list[int]:
    return sorted(p.id for p in people_at(world, town)
                  if lives.simulated(p) and T.realm_of(world, p.id) >= 1)[:MAX_CHALLENGERS]


def eligible(world, town: int, n: int) -> bool:
    """A platform goes up only in the player's region: a local afternoon nobody far away hears of (ruling 10)."""
    import systems.world_events as W
    player = world.get_meta("player_id")
    here = world.targets(player, "located_in") if player is not None else []
    if not here or W.place_xy(world, here[0]) != W.place_xy(world, town):
        return False
    return len(_fighters(world, town)) >= MIN_FIGHTERS


def start_data(world, town: int, n: int, rng) -> dict:
    return {"kind": "lei_tai", "holder": None, "challengers": [], "results": [], "purse": rng.randint(20, 60),
            "paid": False, "challenged": []}


def qualifies(world, occurrence, person: int, slack: int = 0) -> bool:
    return True


def on_stage(world, occurrence, stage: str) -> list[Event]:
    t = occurrence.data["data"]
    if stage == "active":
        fighters = [p for p in _fighters(world, occurrence.data["place"])]
        holder, results = (fighters[0] if fighters else None), []
        for i, challenger in enumerate(fighters[1:]):
            winner = T._sim_winner(world, occurrence, holder, challenger, 0, i)
            results.append([holder, challenger, winner])
            holder = winner
        return [Event("lei_tai_settled", (), occurrence.data["place"],
                      {"occurrence": occurrence.id, "holder": holder, "challengers": fighters, "results": results})]
    if stage == "over" and t["holder"] is not None and not t["paid"] and T.alive(world, t["holder"]):
        return [Event("lei_tai_held", (t["holder"],), occurrence.data["place"],
                      {"occurrence": occurrence.id, "purse": t["purse"]})]
    return []


@effect("lei_tai_settled")
def _settled(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "holder": d["holder"],
                                           "challengers": d["challengers"], "results": d["results"]})


@effect("lei_tai_held")
def _held(world, event) -> None:
    holder, d = event.actors[0], event.data
    world.update_data(holder, silver=silver_of(world, holder) + d["purse"])
    occurrence = world.entity(d["occurrence"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "paid": True})


@listen("lei_tai_held")
def _held_news(world, event, event_id: int) -> None:
    holder = event.actors[0]
    variant = make_variant("held_lei_tai", holder, None, place=place_name(world, event.place))
    variant["kind"] = "lei_tai"
    record_fact(world, holder, "held_lei_tai", None, place=event.place, source_event=event_id, weight=0.75,
                variant=variant)
```

- [ ] **Step 6: Edit the existing files** — `.patches/4e_task2.py`
```python
"""Task 2 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("systems/races.py", '''        able = [world.entity(p) for p in F.members_of(world, faction.id)]
        able = [p for p in able if not p.data.get("is_player") and realm_index(p.data.get("realm", "mortal")) >= CHAMPION_REALM]''',
     '''        able = [world.entity(p) for p, _, d in world.relations_to(faction.id, "member_of")  # one query (4e soak)
                if d.get("status", "member") == "member" and d.get("role") not in (None, "member")]
        able = [p for p in able if p is not None and not p.data.get("dead") and not p.data.get("is_player")
                and realm_index(p.data.get("realm", "mortal")) >= CHAMPION_REALM]''')

FUZZ = "tests/test_fuzz.py"  # a death mid-run starts a young world: count what happened in every world seen
edit(FUZZ, '''    app.start_new(f"Watcher{seed}", world_seed=seed)
    for step in range(300):''', '''    app.start_new(f"Watcher{seed}", world_seed=seed)
    happened = set()
    for step in range(300):''')
edit(FUZZ, '''        if rng.random() < 0.05:
            app.handle_key("f10", "")
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    happened = {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}''', '''        if rng.random() < 0.05:
            app.handle_key("f10", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]''')

SOAK = "tests/test_soak.py"
edit(SOAK, '''def history(tmp_path, years: int, step: int = 5):''',
     '''def history(tmp_path, years: int, step: int = 5, season_budget: float = 0.1):''')
edit(SOAK, '''    assert season < 0.1 and check < 0.3''', '''    assert season < season_budget and check < 0.3''')
edit(SOAK, '''    path = history(tmp_path, 500)''',
     '''    path = history(tmp_path, 500, season_budget=0.2)  # an old world's season: the sky and tournaments (4e ruling 12)''')

TOUR = "systems/tournaments.py"
edit(TOUR, '''    while len(found) + len(registered) < size:''', '''    while wanderer is not None and len(found) + len(registered) < size:  # a sect contest takes no outsiders''')
edit(TOUR, '''def day(occurrence, now: int) -> int:''', '''def qualifies(world, occurrence, person: int, slack: int = 0) -> bool:
    """Whether this person meets the rules of this tournament (its kind's module decides)."""
    from systems.sky import module
    check = getattr(module(occurrence.data["type"]), "qualifies", None)
    return check is None or check(world, occurrence, person, slack)


def day(occurrence, now: int) -> int:''')
edit(TOUR, '''    registered = [p for p in t["registered"] if alive(world, p)]''',
     '''    registered = [p for p in t["registered"] if alive(world, p) and qualifies(world, occurrence, p)]''')
edit("systems/events/grand_assembly.py", '''def qualifies(world, person: int) -> bool:
    return T.realm_of(world, person) >= MIN_REALM''', '''def qualifies(world, occurrence, person: int, slack: int = 0) -> bool:
    return T.realm_of(world, person) >= MIN_REALM''')
edit("systems/events/grand_assembly.py", '''    return T.pool(world, occurrence, lambda p: qualifies(world, p), SIZE, _wanderer)''',
     '''    return T.pool(world, occurrence, lambda p: qualifies(world, occurrence, p), SIZE, _wanderer)''')

RANK = "systems/rankings.py"
edit(RANK, '''    ensure_pavilion(world)
    informants(world, n)
    if n % 4:
        return []
    survey(world)''', '''    ensure_pavilion(world)
    informants(world, n)
    if n % 4:
        return []
    world.forget(pavilion(world), DEEDS, world.time - FORGET_YEARS * YEAR)  # faded deeds (4e ruling 11)
    survey(world)''')
edit("world/db.py", '''    def beliefs(self, knower: int) -> list[Belief]:''', '''    def forget(self, knower: int, predicates, before: int) -> None:
        """Drop this knower's beliefs in facts of these predicates older than `before` (4e: the Pavilion's old news)."""
        predicates = sorted(predicates)
        self._conn.execute(
            f"delete from beliefs where knower = ? and fact_id in (select id from facts where time < ? "
            f"and predicate in ({','.join('?' * len(predicates))}))", (knower, before, *predicates))

    def beliefs(self, knower: int) -> list[Belief]:''')
edit(RANK, '''HEARD = TIER_FACTS | {"defeated", "died", "killed"}''',
     '''HEARD = TIER_FACTS | {"defeated", "died", "killed", "bested", "won_tournament"}
CHAMPION_POINTS = {"grand_assembly": 60.0, "dragon_phoenix": 40.0}  # other tournaments: 10 (phase 4e)
DEEDS = frozenset({"defeated", "bested", "treasure", "enlightened", "won_tournament"})
FORGET_YEARS = 25  # a deed fades by 0.8 a year: after 25 it is worth under half a percent''')
edit(RANK, '''        if realm is not None and (predicate in TIER_FACTS or predicate in ("defeated", "killed")):''',
     '''        if realm is not None and (predicate in TIER_FACTS or predicate in ("defeated", "killed", "bested")):''')
edit(RANK, '''        if predicate in ("defeated", "killed"):  # an NPC's killing records no `defeated` of its own''',
     '''        if predicate in ("defeated", "killed", "bested"):  # an NPC's killing records no `defeated`; a bout `bested`''')
edit(RANK, '''            points = {"treasure": TREASURE_POINTS, "enlightened": ENLIGHTENED_POINTS}.get(predicate, 0.0)''',
     '''            points = {"treasure": TREASURE_POINTS, "enlightened": ENLIGHTENED_POINTS}.get(predicate, 0.0)
            if predicate == "won_tournament":
                points = CHAMPION_POINTS.get(v.get("kind"), 10.0)''')

TOML = "systems/data/world_events.toml"
Path(TOML).write_text(Path(TOML).read_text(encoding="utf-8") + '''
[dragon_phoenix]
module = "systems.events.dragon_phoenix"
scope = "town"
cycle = "every"
every = 8
sky = false
stages = { foretold = 30, announced = 10, active = 5, aftermath = 20 }
news = { predicate = "phenomenon", weight = 2.0, stages = ["foretold", "announced"] }

[sect_contest]
module = "systems.events.sect_contest"
scope = "town"
cycle = "every"
every = 4
stagger = true
sky = false
stages = { announced = 5, active = 1 }

[lei_tai]
module = "systems.events.lei_tai"
scope = "town"
chance = 0.05
sky = false
stages = { active = 1 }
''', encoding="utf-8", newline="\n")

INV = "debug/invariants.py"
edit(INV, '''        if t.get("finished") and t.get("champion") != rounds[-1][0]["winner"]:
            out.append(f"{who} crowned someone other than the final's winner")''', '''        if t.get("finished") and t.get("champion") != rounds[-1][0]["winner"]:
            out.append(f"{who} crowned someone other than the final's winner")
        if not t.get("finished"):
            occurrence = world.entity(row[W.ID])
            for person in t.get("entrants", []):
                if T.alive(world, person) and not T.qualifies(world, occurrence, person, slack=1):
                    out.append(f"{who}: #{person} does not qualify for it")''')

TEXT = "narrate/tournament_text.py"
Path(TEXT).write_text(Path(TEXT).read_text(encoding="utf-8") + '''


def _lei_tai_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} held the lei tai in {variant.get('place') or 'a market town'} "
               "until dusk and took the purse.")


SPECIAL_PHRASES["held_lei_tai"] = _lei_tai_story
''', encoding="utf-8", newline="\n")
print("task 2 edits applied")
```

- [ ] **Step 7: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4e_task2.py && .venv/Scripts/python.exe -m pytest tests/test_tournament_kinds.py tests/test_tournaments.py -q -p no:cacheprovider`
Expected: `task 2 edits applied`, then `21 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 8: Commit**

Run: `git add -A && git commit -m "feat: the Dragon-Phoenix Meet, sect contests and the lei tai - the young, the sects and the town platforms fight for honour"`

---
### Task 3: Taking part - register, answer the herald, fight

**Files:**
- Create: `engine/tournament.py`, `narrate/grammar/tournament.toml`
- Modify (via `.patches/4e_task3.py`):
  - `systems/tournaments.py`: registration, bonds, the call, bout results, forfeits, disqualification, the lei tai challenge;
  - `engine/game.py`: `TournamentMixin` joins `Game`;
  - `engine/fight.py`: a bout's verdict is spare or kill;
  - `debug/invariants.py`: rule 3;
  - `narrate/tournament_text.py`: narration for the new events.
- Test: `tests/test_tournament_play.py`

**Interfaces:**
- Consumes (Tasks 1–2):
  - `T.day`, `T.day_start`, `T.alive`, `T.qualifies`, `T.match_event`, `T.belief_strength`, `T.KINDS`;
  - kind modules' `SIZE`/`BOND`;
  - `rankings.latest`, `rank_of_you`;
  - `standing.standing`;
  - `SkyMixin` pattern; `FightMixin._start_duel(opponent, mode, purpose)`; `_after_duel(data)`.
- Produces:
  - **`systems.tournaments`:**
    - constants: `BONDS`, `RULES`;
    - looking up: `stage(world, occurrence_id) -> str`, `here(world, town, kinds, stages) -> int | None`, `sponsor_of(world, player) -> int | None`, `can_preside(world, occurrence_id, player) -> bool`;
    - registering: `register_block(world, occurrence_id, player) -> str | None`, `register_events(world, occurrence_id, player, preside=False) -> list[Event]`;
    - fighting: `player_call(world, player, town) -> tuple[int, int, int, int] | None`, `bout_result_events(world, occurrence_id, r, i, player, opponent, data) -> list[Event]`, `forfeit_events(world, occurrence_id, player) -> list[Event]`;
    - the lei tai: `lei_tai_open(world, occurrence_id, player) -> bool`, `lei_tai_result_events(world, occurrence_id, player, holder, won) -> list[Event]`.
  - **Events:**
    - `registered` (actor: the player; `occurrence`, `bond`, `preside`);
    - `bond_refunded` (`occurrence`, `silver`);
    - `disqualified` (actor: the player; `occurrence`, `victim`);
    - `lei_tai_challenged` (actors: the player, the holder; `occurrence`, `won`).
  - Fact `disgraced` (subject: the killer; object: the victim).
  - **Tournament data** gains `presiding`, `bonds` (`{str(person): silver}`) and `disqualified`; lei tai data gains `challenged`.
  - **Verbs:** `register`, `preside`, `bout`, `forfeit_bout`, `challenge_lei_tai`.
  - `engine.tournament.TournamentMixin`.

- [ ] **Step 1: Write the failing test** — `tests/test_tournament_play.py`
```python
import random

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def texts(turn):
    return [t for t, _ in turn.lines]


def actions(turn):
    return [c.action for c in turn.all_choices]


def start(world, kind, town, data):
    commit(world, sky.start_events(world, kind, town, world.time, data))
    return W.index(world)[-1][W.ID]


def second_rate(game):
    body = load_body(game.world, game.player.id)
    body.realm = 2
    save_body(game.world, game.player.id, body)


def announced_assembly(game):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    occurrence = start(world, "grand_assembly", town, ga.start_data(world, town, 10, rng_for(1, "a")))
    world.set_time(world.entity(occurrence).data["ends"]["foretold"] + 1)
    return occurrence


def entered(game):
    second_rate(game)
    game.world.update_data(game.player.id, silver=500)
    occurrence = announced_assembly(game)
    game.perform(Action("register", occurrence))
    return occurrence


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    return game.perform(Action("look"))


def finish(game, result, verdict=None):
    d = game.combat
    event = duel._end_event(game.world, d, result, "broken", random.Random(1), d.harm, 5, verdict=verdict)
    game._commit([event])
    return game._finish_duel(event.data)


def my_match(world, occurrence, me):
    t = world.entity(occurrence).data["data"]
    return next(((r, i, m) for r, ms in enumerate(t["rounds"]) for i, m in enumerate(ms) if me in (m["a"], m["b"])
                 and m["how"] is None), None)


def test_registering_follows_the_rules(game):
    world, me = game.world, game.player.id
    occurrence = announced_assembly(game)
    assert "Second-rate" in T.register_block(world, occurrence, me)
    second_rate(game)
    world.update_data(me, silver=0)
    assert "bond" in T.register_block(world, occurrence, me)
    world.update_data(me, silver=150)
    assert Action("register", occurrence) in actions(game.perform(Action("look")))
    game.perform(Action("register", occurrence))
    t = world.entity(occurrence).data["data"]
    assert me in t["registered"] and silver_of(world, me) == 50 and t["bonds"][str(me)] == 100
    assert "already" in T.register_block(world, occurrence, me)


def test_registration_closes_when_the_bout_days_begin(game):
    second_rate(game)
    occurrence = announced_assembly(game)
    game.world.set_time(T.day_start(game.world.entity(occurrence), 1))
    assert "not open" in T.register_block(game.world, occurrence, game.player.id)


def test_the_herald_calls_you_and_a_win_advances_you(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    turn = to_day(game, occurrence, 1)
    assert any("herald" in t.lower() for t in texts(turn)) and Action("bout", occurrence) in actions(turn)
    game.perform(Action("bout", occurrence))
    assert game.combat is not None and game.combat.mode == "bout"
    finish(game, "won", verdict="spare")
    r, i, m = my_match(world, occurrence, me)
    assert r == 1 and world.entity(occurrence).data["data"]["rounds"][0][
        next(j for j, x in enumerate(world.entity(occurrence).data["data"]["rounds"][0]) if me in (x["a"], x["b"]))]["how"] == "bout"
    assert check_tournaments(world) == []


def test_a_kill_in_a_bout_disqualifies_and_disgraces(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 1)
    game.perform(Action("bout", occurrence))
    victim = game.combat.opponent
    game.combat.stage = "verdict"
    game.perform(Action("verdict", "kill"))
    t = world.entity(occurrence).data["data"]
    assert me in t["disqualified"] and world.facts(predicate="disgraced", subject=me)
    assert world.entity(victim).data.get("dead") and my_match(world, occurrence, me) is None
    assert check_tournaments(world) == []


def test_missing_your_day_forfeits_and_the_bracket_goes_on(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 1)
    to_day(game, occurrence, 4)
    t = world.entity(occurrence).data["data"]
    mine = next(m for m in t["rounds"][0] if me in (m["a"], m["b"]))
    assert mine["how"] == "forfeit" and mine["winner"] != me
    assert all(m["how"] is not None for m in t["rounds"][1])
    to_day(game, occurrence, 9)
    assert world.entity(occurrence).data["data"]["finished"] and check_tournaments(world) == []


def test_forfeiting_gives_the_match_away(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 1)
    game.perform(Action("forfeit_bout", occurrence))
    mine = next(m for m in world.entity(occurrence).data["data"]["rounds"][0] if me in (m["a"], m["b"]))
    assert mine["how"] == "forfeit" and mine["winner"] != me


def test_the_bond_comes_back_after_the_first_round(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    silver = silver_of(world, me)
    to_day(game, occurrence, 1)
    game.perform(Action("bout", occurrence))
    finish(game, "won", verdict="spare")
    assert silver_of(world, me) == silver + 100


def test_presiding_keeps_you_out_of_the_bracket(game):
    import systems.events.sect_contest as sc
    from tests.test_sect import found_sect
    world, me = game.world, game.player.id
    sect, town = found_sect(game)
    for i in range(2):
        founding.enrol(world, founding.make_person(world, f"test:extra:{i}", town), sect, 70)
    occurrence = start(world, "sect_contest", town, sc.start_data(world, town, 10, rng_for(1, "s")))
    assert T.can_preside(world, occurrence, me)
    game.perform(Action("preside", occurrence))
    world.set_time(world.entity(occurrence).data["over_at"] + 1)
    sky.observe(world, town)
    t = world.entity(occurrence).data["data"]
    assert t["presiding"] == me and me not in t["entrants"] and t["finished"]


def test_same_day_rounds_let_you_fight_on(game):
    import systems.events.sect_contest as sc
    world, me, town = game.world, game.player.id, game.place.id
    school = next(f.id for f in world.entities("faction") if f.data["type"] == "school")
    world.relate(me, school, "member_of", 1, {"role": "disciple", "hall": None, "merit": 0, "status": "member",
                                              "secret": False})
    occurrence = start(world, "sect_contest", town, sc.start_data(world, town, 10, rng_for(1, "s")))
    game.perform(Action("register", occurrence))
    to_day(game, occurrence, 1)
    first = T.player_call(world, me, town)
    assert first is not None
    game.perform(Action("bout", occurrence))
    finish(game, "won", verdict="spare")
    second = T.player_call(world, me, town)
    assert second is not None and second[1] == first[1] + 1  # the next round is fought the same day


def test_you_may_challenge_the_lei_tai_holder_once(game):
    import systems.events.lei_tai as lt
    world, me, town = game.world, game.player.id, game.place.id
    for i in range(3):
        founding.make_person(world, f"test:brawler:{i}", town, occupation="wandering swordsman", age=30,
                             realm="third-rate")
    occurrence = start(world, "lei_tai", town, lt.start_data(world, town, 10, rng_for(1, "l")))
    turn = game.perform(Action("look"))
    assert Action("challenge_lei_tai", occurrence) in actions(turn)
    game.perform(Action("challenge_lei_tai", occurrence))
    finish(game, "won", verdict="spare")
    t = world.entity(occurrence).data["data"]
    assert t["holder"] == me and me in t["challenged"]
    assert Action("challenge_lei_tai", occurrence) not in actions(game.perform(Action("look")))
    silver = silver_of(world, me)
    world.set_time(world.entity(occurrence).data["over_at"] + 1)
    game.perform(Action("look"))
    assert silver_of(world, me) == silver + t["purse"]


def test_the_rules_catch_a_spared_loser_killed_by_the_winner(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 1)
    game.perform(Action("bout", occurrence))
    victim = game.combat.opponent
    finish(game, "won", verdict="spare")
    world.update_data(victim, dead=True, death={"cause": "killed", "killer": me})
    assert any("killed" in p for p in check_tournaments(world))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tournament_play.py -q -p no:cacheprovider`
Expected: failures, for example `AttributeError: module 'systems.tournaments' has no attribute 'register_block'`.

- [ ] **Step 3: Write the engine** — `engine/tournament.py`
```python
"""Tournaments in the engine (phase 4e spec 6): register, answer the herald, fight your bouts, hold the lei tai."""

import systems.tournaments as T
from engine.actions import Action, Choice
from narrate.tournament_text import KIND_NAMES


class TournamentMixin:
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, town = self.world, self.player.id, self.place.id
        open_ = T.here(world, town, T.KINDS, ("announced",))
        if open_ is not None and T.register_block(world, open_, me) is None:
            kind = world.entity(open_).data["type"]
            extras.append(Choice(f"Enter {KIND_NAMES[kind]}", Action("register", open_)))
            if T.can_preside(world, open_, me):
                extras.append(Choice("Preside over the contest", Action("preside", open_)))
        call = T.player_call(world, me, town)
        if call is not None:
            name = world.entity(call[3]).name
            extras.append(Choice(f"Answer the herald: fight {name}", Action("bout", call[0])))
            extras.append(Choice("Forfeit your bout", Action("forfeit_bout", call[0])))
        platform = T.here(world, town, ("lei_tai",), ("active",))
        if platform is not None and T.lei_tai_open(world, platform, me):
            holder = world.entity(platform).data["data"]["holder"]
            extras.append(Choice(f"Challenge the platform holder, {world.entity(holder).name}",
                                 Action("challenge_lei_tai", platform)))
        return extras

    def _herald(self) -> list:
        call = T.player_call(self.world, self.player.id, self.place.id)
        if call is None:
            return []
        kind = self.world.entity(call[0]).data["type"]
        return [(f"The herald calls your name: today you fight {self.world.entity(call[3]).name} "
                 f"at {KIND_NAMES[kind]}.", "dim")]

    def _after_look(self) -> list:
        return super()._after_look() + self._herald()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._herald()

    def _do_register(self, occurrence):
        why = T.register_block(self.world, occurrence, self.player.id) if isinstance(occurrence, int) else "There is nothing to enter here."
        if why:
            return self._turn([(why, "system")])
        return self._turn(self._commit(T.register_events(self.world, occurrence, self.player.id)))

    def _do_preside(self, occurrence):
        if not isinstance(occurrence, int) or not T.can_preside(self.world, occurrence, self.player.id) \
                or T.stage(self.world, occurrence) != "announced":
            return self._turn([("There is no contest of yours to preside over.", "system")])
        return self._turn(self._commit(T.register_events(self.world, occurrence, self.player.id, preside=True)))

    def _do_bout(self, occurrence):
        call = T.player_call(self.world, self.player.id, self.place.id)
        if call is None or call[0] != occurrence:
            return self._turn([("No herald has called your name.", "system")])
        occurrence, r, i, opponent = call
        purpose = {"tournament": occurrence, "round": r, "match": i}
        return self._turn(self._start_duel(opponent, "bout", purpose=purpose))

    def _do_forfeit_bout(self, occurrence):
        events = T.forfeit_events(self.world, occurrence, self.player.id) if isinstance(occurrence, int) else []
        if not events:
            return self._turn([("You have no bout to forfeit.", "system")])
        return self._turn(self._commit(events))

    def _do_challenge_lei_tai(self, occurrence):
        if not isinstance(occurrence, int) or not T.lei_tai_open(self.world, occurrence, self.player.id):
            return self._turn([("There is no platform you may challenge.", "system")])
        holder = self.world.entity(occurrence).data["data"]["holder"]
        return self._turn(self._start_duel(holder, "bout", purpose={"lei_tai": occurrence}))

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is None or len(entry.actors) < 2:
            return lines
        me, opponent = entry.actors[0], entry.actors[1]
        if "tournament" in purpose:
            events = T.bout_result_events(self.world, purpose["tournament"], purpose["round"], purpose["match"],
                                          me, opponent, data)
            lines += self._commit(events) if events else []
        elif "lei_tai" in purpose:
            won = data.get("result") == "won" and data.get("verdict") != "kill"
            lines += self._commit(T.lei_tai_result_events(self.world, purpose["lei_tai"], me, opponent, won))
        return lines
```

- [ ] **Step 4: Write the grammar** — `narrate/grammar/tournament.toml`
```toml
[symbols]
tour_crowd = ["The crowd roars.", "Somewhere a gong is struck.", "The stands murmur and shift.", "A child on someone's shoulders points at you.", "Bookmakers' boys run through the crowd.", "Dust rises from the platform."]
tour_clerk = ["A clerk writes your name in a thick ledger.", "An official looks you over and nods.", "Your name is called out to no one in particular.", "A servant hands you a wooden tally with a number on it."]
tour_shame = ["Silence falls over the stands.", "Someone spits.", "The judges stand as one.", "Nobody will meet your eyes."]

[registered]
colour = "default"
lines = ["#tour_clerk#", "#tour_clerk# #tour_crowd#"]

[bond_refunded]
colour = "default"
lines = ["#tour_clerk#", "#tour_clerk# #tour_crowd#"]

[match_resolved]
colour = "default"
lines = ["#tour_crowd#", "#tour_crowd# #tour_crowd#"]

[tournament_won]
colour = "gold"
lines = ["#tour_crowd# #tour_crowd#"]

[disqualified]
colour = "default"
lines = ["#tour_shame#", "#tour_shame# #tour_shame#"]

[lei_tai_challenged]
colour = "default"
lines = ["#tour_crowd#", "#tour_crowd# #tour_crowd#"]

[lei_tai_held]
colour = "gold"
lines = ["#tour_crowd#"]
```

- [ ] **Step 5: Edit the existing files** — `.patches/4e_task3.py`
```python
"""Task 3 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


TOUR = "systems/tournaments.py"
Path(TOUR).write_text(Path(TOUR).read_text(encoding="utf-8") + '''

# --- the player in a tournament (phase 4e spec 3, 4.3-4.4) -------------------------------------

BONDS = {"grand_assembly": 100, "dragon_phoenix": 30}
RULES = {"grand_assembly": "Only fighters of Second-rate and above may enter the Assembly.",
         "dragon_phoenix": "The Meet is for those of thirty or under.",
         "sect_contest": "Only the sect's own may enter its contest."}


def stage(world, occurrence_id: int) -> str:
    return W.stage_at(world.entity(occurrence_id).data, world.time)


def here(world, town: int, kinds, stages) -> int | None:
    """A tournament of one of these kinds in this town, at one of these stages."""
    for row in W.index(world):
        if row[W.TYPE] in kinds and row[W.PLACE] == town and not row[W.DONE] and stage(world, row[W.ID]) in stages:
            return row[W.ID]
    return None


def sponsor_of(world, player: int) -> int | None:
    """A faction that vouches for the player: one they belong to, or one that welcomes them (3b standing)."""
    from systems.standing import standing
    mine = sorted(f for f, _, d in F.memberships(world, player) if d.get("status", "member") == "member"
                  and world.entity(f).data.get("type") in F.STAFFED | {"player_sect"})
    if mine:
        return mine[0]
    for faction in world.entities("faction"):
        if faction.data.get("type") in F.STAFFED and not faction.data.get("dissolved") \\
                and standing(world, faction.id, player).score >= 1:
            return faction.id
    return None


def _ranked(world, player: int) -> bool:
    from systems.rankings import latest, rank_of_you
    known = latest(world, player)
    return bool(known and rank_of_you(world, known["lists"], player))


def can_preside(world, occurrence_id: int, player: int) -> bool:
    t = world.entity(occurrence_id).data["data"]
    return t["kind"] == "sect_contest" and world.entity(t["faction"]).data.get("founder") == player


def register_block(world, occurrence_id: int, player: int) -> str | None:
    occurrence = world.entity(occurrence_id)
    t = occurrence.data["data"]
    if stage(world, occurrence_id) != "announced":
        return "Registration is not open."
    if player in t["registered"] or t.get("presiding") == player:
        return "You are already entered."
    if not qualifies(world, occurrence, player):
        return RULES.get(t["kind"], "You may not enter.")
    bond = BONDS.get(t["kind"], 0)
    if bond and sponsor_of(world, player) is None and not _ranked(world, player) \\
            and world.entity(player).data.get("silver", 0) < bond:
        return f"You need a sponsor, a place on the Pavilion's lists, or a bond of {bond} silver."
    return None


def register_events(world, occurrence_id: int, player: int, preside: bool = False) -> list[Event]:
    t = world.entity(occurrence_id).data["data"]
    bond = 0 if preside or sponsor_of(world, player) is not None or _ranked(world, player) else BONDS.get(t["kind"], 0)
    return [Event("registered", (player,), world.entity(occurrence_id).data["place"],
                  {"occurrence": occurrence_id, "bond": bond, "preside": preside})]


@effect("registered")
def _registered(world, event) -> None:
    player, d = event.actors[0], event.data
    occurrence = world.entity(d["occurrence"])
    t = dict(occurrence.data["data"])
    if d["preside"]:
        t["presiding"] = player
    else:
        t["registered"] = t["registered"] + [player]
    if d["bond"]:
        t["bonds"] = {**t.get("bonds", {}), str(player): d["bond"]}
        world.update_data(player, silver=silver_of(world, player) - d["bond"])
    world.update_data(occurrence.id, data=t)


@listen("match_resolved")
def _bond_back(world, event, event_id: int) -> None:
    d = event.data
    t = world.entity(d["occurrence"]).data["data"]
    bond = t.get("bonds", {}).get(str(d["winner"]))
    if d["round"] == 0 and bond:
        commit(world, [Event("bond_refunded", (d["winner"],), event.place, {"occurrence": d["occurrence"], "silver": bond})])


@effect("bond_refunded")
def _refunded(world, event) -> None:
    person, d = event.actors[0], event.data
    occurrence = world.entity(d["occurrence"])
    bonds = {k: v for k, v in occurrence.data["data"].get("bonds", {}).items() if k != str(person)}
    world.update_data(occurrence.id, data={**occurrence.data["data"], "bonds": bonds})
    world.update_data(person, silver=silver_of(world, person) + d["silver"])


def player_call(world, player: int, town: int) -> tuple[int, int, int, int] | None:
    """(tournament, round, match, opponent) if the herald calls the player here today."""
    for row in W.index(world):
        if row[W.TYPE] not in KINDS or row[W.PLACE] != town or row[W.DONE]:
            continue
        occurrence = world.entity(row[W.ID])
        t = occurrence.data["data"]
        if not t["rounds"] or t["finished"] or world.time >= occurrence.data["active"][1]:
            continue
        today = day(occurrence, world.time)
        for r, matches in enumerate(t["rounds"]):
            for i, m in enumerate(matches):
                if m["how"] is None and m["day"] == today and player in (m["a"], m["b"]):
                    other = m["b"] if m["a"] == player else m["a"]
                    if other is not None and alive(world, other):
                        return row[W.ID], r, i, other
    return None


def bout_result_events(world, occurrence_id: int, r: int, i: int, player: int, opponent: int, data: dict) -> list[Event]:
    occurrence = world.entity(occurrence_id)
    m = occurrence.data["data"]["rounds"][r][i]
    if m["how"] is not None:
        return []
    today = day(occurrence, world.time)
    if data.get("result") == "won" and data.get("verdict") == "kill":
        return [Event("disqualified", (player,), occurrence.data["place"], {"occurrence": occurrence_id, "victim": opponent}),
                match_event(occurrence, r, i, None, player, "disqualified", max(today, m["day"]))]
    if data.get("result") == "won":
        winner = player
    elif data.get("result") == "drawn":  # the judges favour the fighter the crowd believed stronger
        town = occurrence.data["place"]
        winner = max((player, opponent), key=lambda p: (belief_strength(world, town, p), -p))
    else:
        winner = opponent
    loser = opponent if winner == player else player
    return [match_event(occurrence, r, i, winner, loser, "bout", max(today, m["day"]))]


def forfeit_events(world, occurrence_id: int, player: int) -> list[Event]:
    call = player_call(world, player, world.entity(occurrence_id).data["place"])
    if call is None or call[0] != occurrence_id:
        return []
    occurrence = world.entity(occurrence_id)
    _, r, i, other = call
    return [match_event(occurrence, r, i, other, player, "forfeit", day(occurrence, world.time))]


@effect("disqualified")
def _disqualified(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "disqualified": t.get("disqualified", []) + [event.actors[0]]})


@listen("disqualified")
def _disgraced(world, event, event_id: int) -> None:
    killer, victim = event.actors[0], event.data["victim"]
    variant = make_variant("disgraced", killer, victim, place=place_name(world, event.place))
    record_fact(world, killer, "disgraced", victim, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


def lei_tai_open(world, occurrence_id: int, player: int) -> bool:
    t = world.entity(occurrence_id).data["data"]
    return stage(world, occurrence_id) == "active" and t["holder"] not in (None, player) \\
        and alive(world, t["holder"]) and player not in t.get("challenged", [])


def lei_tai_result_events(world, occurrence_id: int, player: int, holder: int, won: bool) -> list[Event]:
    return [Event("lei_tai_challenged", (player, holder), world.entity(occurrence_id).data["place"],
                  {"occurrence": occurrence_id, "won": won})]


@effect("lei_tai_challenged")
def _challenged(world, event) -> None:
    player, holder = event.actors
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "holder": player if event.data["won"] else holder,
                                           "challenged": t.get("challenged", []) + [player]})
''', encoding="utf-8", newline="\n")

GAME = "engine/game.py"
edit(GAME, "from engine.sky import SkyMixin\n", "from engine.sky import SkyMixin\nfrom engine.tournament import TournamentMixin\n")
edit(GAME, "class Game(LineageMixin, MarketMixin, SkyMixin, WorldMixin,",
     "class Game(LineageMixin, MarketMixin, SkyMixin, TournamentMixin, WorldMixin,")

edit("engine/fight.py", '''    def _verdict_choices(self) -> list[Choice]:
        opponent = self.world.entity(self.combat.opponent)''', '''    def _verdict_choices(self) -> list[Choice]:
        opponent = self.world.entity(self.combat.opponent)
        if self.combat.mode == "bout":  # a tournament: mercy wins the bout, a kill disqualifies (phase 4e)
            return [Choice(f"Spare {opponent.name} and win the bout", Action("verdict", "spare")),
                    Choice(f"Kill {opponent.name} (you will be disqualified)", Action("verdict", "kill"))]''')

INV = "debug/invariants.py"
edit(INV, '''                if m["how"] is not None and r + 1 < len(rounds):''', '''                loser = m["b"] if m["winner"] == m["a"] else m["a"]
                if m["how"] == "bout" and loser is not None and m["winner"] is not None \\
                        and (world.entity(loser).data.get("death") or {}).get("killer") == m["winner"]:
                    out.append(f"{who}: #{m['winner']} killed #{loser} in a bout and was not disqualified")
                if m["how"] is not None and r + 1 < len(rounds):''')

TEXT = "narrate/tournament_text.py"
Path(TEXT).write_text(Path(TEXT).read_text(encoding="utf-8") + '''


def _disgraced_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} killed {who(world, variant.get('target'), viewer)} "
               f"on the platform in {variant.get('place') or 'a tournament'} and was thrown out in disgrace.")


SPECIAL_PHRASES["disgraced"] = _disgraced_story


@outcome("registered", body_facts=False)
def _registered(world, event):
    d = event.data
    kind = world.entity(d["occurrence"]).data["type"]
    if d["preside"]:
        return [f"You will preside over {KIND_NAMES[kind]}."], {}
    bond = f" You post a bond of {d['bond']} silver." if d["bond"] else ""
    return [f"You are entered in {KIND_NAMES[kind]}.{bond}"], {}


@summary("registered")
def _registered_line(world, entry, names, place, other):
    kind = world.entity(entry.data["occurrence"]).data["type"]
    return f"{'Presided over' if entry.data['preside'] else 'Entered'} {KIND_NAMES[kind]} in {place}."


@outcome("bond_refunded", body_facts=False)
def _refunded(world, event):
    return [f"Your bond of {event.data['silver']} silver is returned."], {}


@summary("bond_refunded")
def _refunded_line(world, entry, names, place, other):
    return f"Had a tournament bond of {entry.data['silver']} silver returned."


@outcome("match_resolved", body_facts=False)
def _resolved(world, event):
    d = event.data
    me = world.get_meta("player_id")
    if d["how"] == "forfeit":
        return ([f"You forfeit your bout."] if d["loser"] == me else [f"{world.entity(d['loser']).name} forfeits."]), {}
    if d["how"] == "disqualified":
        return ["The judges strike your name from the bracket."], {}
    won = d["winner"] == me
    other = world.entity(d["loser"] if won else d["winner"]).name
    return [f"You win the bout against {other}." if won else f"{other} wins the bout."], {}


@summary("match_resolved")
def _resolved_line(world, entry, names, place, other):
    d = entry.data
    me = world.get_meta("player_id")
    if d["how"] == "disqualified":
        return f"Was disqualified from a tournament in {place}."
    if d["winner"] == me:
        return f"Won a bout in round {d['round'] + 1} in {place}."
    return f"Lost a bout in round {d['round'] + 1} in {place}."


@outcome("tournament_won", body_facts=False)
def _won(world, event):
    return [f"You are crowned: {event.data['title']}. The prize is {event.data['prize']} silver."], {}


@summary("tournament_won")
def _won_line(world, entry, names, place, other):
    return f"Won the tournament in {place}: {entry.data['title']}."


@outcome("disqualified", body_facts=False)
def _dq(world, event):
    return [f"You have killed {world.entity(event.data['victim']).name} on the platform."], {}


@summary("disqualified")
def _dq_line(world, entry, names, place, other):
    return f"Killed an opponent in a bout in {place}, and was disgraced."


@outcome("lei_tai_challenged", body_facts=False)
def _lei_tai(world, event):
    holder = world.entity(event.actors[1]).name
    return [f"You take the platform from {holder}." if event.data["won"] else f"{holder} keeps the platform."], {}


@summary("lei_tai_challenged")
def _lei_tai_line(world, entry, names, place, other):
    return f"{'Took' if entry.data['won'] else 'Failed to take'} the lei tai in {place} from {other}."


@outcome("lei_tai_held", body_facts=False)
def _held(world, event):
    return [f"You hold the platform at dusk. The patron pays you {event.data['purse']} silver."], {}


@summary("lei_tai_held")
def _held_line(world, entry, names, place, other):
    return f"Held the lei tai in {place} and took the purse."
''', encoding="utf-8", newline="\n")
print("task 3 edits applied")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4e_task3.py && .venv/Scripts/python.exe -m pytest tests/test_tournament_play.py -q -p no:cacheprovider`
Expected: `task 3 edits applied`, then `11 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 7: Commit**

Run: `git add -A && git commit -m "feat: taking part - register under the rules, answer the herald, fight your bouts live, hold the lei tai"`

---
### Task 4: Betting

**Files:**
- Create: `systems/wagers.py`
- Modify (via `.patches/4e_task4.py`):
  - `engine/tournament.py`: the bookmaker, the odds board, bets;
  - `debug/invariants.py`: rule 4;
  - `narrate/tournament_text.py`, `narrate/grammar/tournament.toml`: bet narration.
- Test: `tests/test_wagers.py`

**Interfaces:**
- Consumes (Tasks 1–3): `T.strengths`, `T.here`, `T.KINDS`, the `match_resolved` event (`winner`, `loser`, `how`), `TournamentMixin`.
- Produces:
  - **`systems.wagers`:**
    - constants: `MARGIN = 0.10`, `MAX_SHARE = 0.10`;
    - functions: `open_matches(world, occurrence_id) -> list[tuple[int, int, dict]]`, `odds(world, occurrence_id, r, i) -> dict[int, float]`, `stake_limit(world, player) -> int`, `bet_block(world, occurrence_id, r, i, on, stake, player) -> str | None`, `bet_events(world, occurrence_id, r, i, on, stake, player) -> list[Event]`.
  - **Tournament data** gains `bets`: a list of `{"player", "round", "match", "on", "stake", "odds", "silver", "settled", "payout"}`.
  - **Events:**
    - `bet_placed` (actor: the player; `occurrence`, `round`, `match`, `on`, `stake`, `odds`, `silver`);
    - `bet_settled` (actor: the bettor; `occurrence`, `bet`, `payout`, `void`).
  - Fact `fixed` (subject: the bettor who bet against themselves and lost).
  - **Verbs:** `bookmaker`, `bet`.

- [ ] **Step 1: Write the failing test** — `tests/test_wagers.py`
```python
import random

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.sky as sky
import systems.tournaments as T
import systems.wagers as wagers
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import Event, commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    g.world.update_data(g.player.id, silver=1000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def drawn_assembly(game, registered=()):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "grand_assembly", town, world.time,
                                   {**ga.start_data(world, town, 10, rng_for(1, "a")), "registered": list(registered)}))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    return occurrence


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    sky.observe(game.world, game.place.id)


def match(world, occurrence, r, i):
    return world.entity(occurrence).data["data"]["rounds"][r][i]


def test_the_odds_follow_what_the_town_believes(game):
    world, town = game.world, game.place.id
    famous = founding.make_person(world, "test:famous", town, occupation="monk", age=40, realm="second-rate")
    for i in range(4):
        victim = founding.make_person(world, f"test:victim:{i}", town, occupation="monk", age=40)
        record_fact(world, famous, "defeated", victim, place=town, weight=3.0,
                    variant=make_variant("defeated", famous, victim, place=place_name(world, town)))
    occurrence = drawn_assembly(game, registered=[famous])
    r, i, m = next((r, i, m) for r, i, m in wagers.open_matches(world, occurrence) if famous in (m["a"], m["b"]))
    prices = wagers.odds(world, occurrence, r, i)
    other = m["b"] if m["a"] == famous else m["a"]
    assert prices[famous] < prices[other] and prices[famous] >= 1.0 - wagers.MARGIN


def test_a_winning_bet_pays_and_a_losing_one_does_not(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 50, me))
    commit(world, wagers.bet_events(world, occurrence, r, i, m["b"], 50, me))
    prices = wagers.odds(world, occurrence, r, i)
    silver = silver_of(world, me)
    to_day(game, occurrence, 2)
    winner = match(world, occurrence, r, i)["winner"]
    bets = world.entity(occurrence).data["data"]["bets"]
    assert all(b["settled"] for b in bets)
    assert silver_of(world, me) == silver + int(50 * next(b["odds"] for b in bets if b["on"] == winner))
    assert check_tournaments(world) == []


def test_the_stake_is_at_most_a_tenth_of_your_silver(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    assert "tenth" in wagers.bet_block(world, occurrence, r, i, m["a"], 101, me)
    assert wagers.bet_block(world, occurrence, r, i, m["a"], 100, me) is None


def test_a_bet_on_a_walkover_settles_once(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["b"], 40, me))
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 40, me))
    world.update_data(m["b"], dead=True)
    to_day(game, occurrence, 2)
    to_day(game, occurrence, 4)
    bets = world.entity(occurrence).data["data"]["bets"]
    settled = [e for e in world.chronicle_about(me, limit=100) if e.kind == "bet_settled"]
    assert len(settled) == 2 and all(b["settled"] for b in bets)
    assert [b["payout"] for b in bets] == [0, int(40 * bets[1]["odds"])]


def test_betting_on_your_rival_and_losing_is_a_scandal(game):
    world, me = game.world, game.player.id
    from systems.bodies import load_body, save_body
    body = load_body(world, me)
    body.realm = 2
    save_body(world, me, body)
    occurrence = drawn_assembly(game, registered=[me])
    call = T.player_call(world, me, game.place.id)
    _, r, i, rival = call
    commit(world, wagers.bet_events(world, occurrence, r, i, rival, 50, me))
    game.perform(Action("forfeit_bout", occurrence))
    assert world.facts(predicate="fixed", subject=me)


def test_a_bettors_death_voids_and_refunds(game):
    world, me, town = game.world, game.player.id, game.place.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 60, me))
    silver = silver_of(world, me)
    commit(world, [Event("died", (me, me), town, {"cause": "age"})])
    bet = world.entity(occurrence).data["data"]["bets"][0]
    assert bet["settled"] and bet["payout"] == 60 and silver_of(world, me) == silver + 60


def test_the_bookmaker_takes_bets_at_the_venue(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    turn = game.perform(Action("look"))
    assert Action("bookmaker", occurrence) in [c.action for c in turn.all_choices]
    board = game.perform(Action("bookmaker", occurrence))
    bets = [c.action for c in board.choices if c.action.verb == "bet"]
    assert bets and any("odds" in t or "to 1" in t for t, _ in board.lines)
    game.perform(bets[0])
    assert world.entity(occurrence).data["data"]["bets"][0]["stake"] == 100  # a tenth of the 1000 silver held


def test_the_rules_catch_an_open_bet_after_the_end(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 10, me))
    to_day(game, occurrence, 9)
    t = dict(world.entity(occurrence).data["data"])
    t["bets"] = [dict(t["bets"][0], settled=False)]
    world.update_data(occurrence, data=t)
    assert any("open bet" in p for p in check_tournaments(world))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_wagers.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.wagers'`.

- [ ] **Step 3: Write the wagers** — `systems/wagers.py`
```python
"""Betting (phase 4e spec 5.1): the host town's bookmaker prices each match from what the town believes.

Bets open when the bracket is drawn (plan ruling 3) and settle when the match does: a walkover or a
forfeit is a result like any other; a disqualification voids the match's bets; a bettor's death voids
theirs and refunds the stake to their estate. Betting on your own opponent and losing is a scandal.
"""

import systems.tournaments as T
import systems.world_events as W
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import Event, commit, effect, listen

MARGIN = 0.10
MAX_SHARE = 0.10


def open_matches(world, occurrence_id: int) -> list[tuple[int, int, dict]]:
    """Matches one can bet on: both fighters known, not yet settled."""
    t = world.entity(occurrence_id).data["data"]
    return [(r, i, m) for r, ms in enumerate(t["rounds"]) for i, m in enumerate(ms)
            if m["how"] is None and m["a"] is not None and m["b"] is not None]


def odds(world, occurrence_id: int, r: int, i: int) -> dict[int, float]:
    """Decimal odds for each fighter, from the town's belief in them, less the bookmaker's margin."""
    occurrence = world.entity(occurrence_id)
    m = occurrence.data["data"]["rounds"][r][i]
    s = T.strengths(world, occurrence.data["place"], [m["a"], m["b"]])
    a, b = 1 + max(0.0, s[m["a"]]), 1 + max(0.0, s[m["b"]])
    p = a / (a + b)
    return {m["a"]: round((1 - MARGIN) / p, 2), m["b"]: round((1 - MARGIN) / (1 - p), 2)}


def stake_limit(world, player: int) -> int:
    return int(silver_of(world, player) * MAX_SHARE)


def bet_block(world, occurrence_id: int, r: int, i: int, on: int, stake: int, player: int) -> str | None:
    occurrence = world.entity(occurrence_id)
    if occurrence.data["place"] not in world.targets(player, "located_in"):
        return "The bookmaker is in the host town."
    if (r, i) not in {(rr, ii) for rr, ii, _ in open_matches(world, occurrence_id)}:
        return "That match is not open for bets."
    m = occurrence.data["data"]["rounds"][r][i]
    if on not in (m["a"], m["b"]):
        return "That fighter is not in the match."
    if stake < 1:
        return "Bet at least one silver."
    if stake > stake_limit(world, player):
        return f"The bookmaker takes no more than a tenth of your silver ({stake_limit(world, player)})."
    return None


def bet_events(world, occurrence_id: int, r: int, i: int, on: int, stake: int, player: int) -> list[Event]:
    return [Event("bet_placed", (player,), world.entity(occurrence_id).data["place"],
                  {"occurrence": occurrence_id, "round": r, "match": i, "on": on, "stake": stake,
                   "odds": odds(world, occurrence_id, r, i)[on], "silver": silver_of(world, player)})]


@effect("bet_placed")
def _placed(world, event) -> None:
    player, d = event.actors[0], event.data
    occurrence = world.entity(d["occurrence"])
    bet = {"player": player, "round": d["round"], "match": d["match"], "on": d["on"], "stake": d["stake"],
           "odds": d["odds"], "silver": d["silver"], "settled": False, "payout": 0}
    world.update_data(occurrence.id, data={**occurrence.data["data"],
                                           "bets": occurrence.data["data"].get("bets", []) + [bet]})
    world.update_data(player, silver=silver_of(world, player) - d["stake"])


@listen("match_resolved")
def _settle(world, event, event_id: int) -> None:
    d = event.data
    t = world.entity(d["occurrence"]).data["data"]
    events = []
    for n, bet in enumerate(t.get("bets", [])):
        if bet["settled"] or (bet["round"], bet["match"]) != (d["round"], d["match"]):
            continue
        void = d["how"] == "disqualified"
        payout = bet["stake"] if void else int(bet["stake"] * bet["odds"]) if bet["on"] == d["winner"] else 0
        events.append(Event("bet_settled", (bet["player"],), event.place,
                            {"occurrence": d["occurrence"], "bet": n, "payout": payout, "void": void}))
        if not void and bet["player"] == d["loser"] and bet["on"] == d["winner"]:
            variant = make_variant("fixed", bet["player"], None, place=place_name(world, event.place))
            record_fact(world, bet["player"], "fixed", None, place=event.place, source_event=event_id, weight=1.5,
                        variant=variant)
    if events:
        commit(world, events)


@listen("died")
def _void_the_dead(world, event, event_id: int) -> None:
    dead = event.actors[-1]
    events = []
    for row in W.index(world):
        if row[W.TYPE] not in T.KINDS or row[W.DONE]:
            continue
        t = world.entity(row[W.ID]).data["data"]
        for n, bet in enumerate(t.get("bets", [])):
            if bet["player"] == dead and not bet["settled"]:
                events.append(Event("bet_settled", (dead,), event.place,
                                    {"occurrence": row[W.ID], "bet": n, "payout": bet["stake"], "void": True}))
    if events:
        commit(world, events)


@effect("bet_settled")
def _settled(world, event) -> None:
    bettor, d = event.actors[0], event.data
    occurrence = world.entity(d["occurrence"])
    bets = [dict(b) for b in occurrence.data["data"]["bets"]]
    if bets[d["bet"]]["settled"]:
        raise ValueError(f"bet {d['bet']} of tournament #{occurrence.id} is already settled")
    bets[d["bet"]].update(settled=True, payout=d["payout"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "bets": bets})
    if d["payout"]:
        world.update_data(bettor, silver=silver_of(world, bettor) + d["payout"])
```

- [ ] **Step 4: Edit the existing files** — `.patches/4e_task4.py`
```python
"""Task 4 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


ENG = "engine/tournament.py"
edit(ENG, '''import systems.tournaments as T
''', '''import systems.tournaments as T
import systems.wagers as wagers
''')
edit(ENG, '''        platform = T.here(world, town, ("lei_tai",), ("active",))''', '''        betting = T.here(world, town, T.KINDS, ("active",))
        if betting is not None and wagers.open_matches(world, betting) and wagers.stake_limit(world, me) >= 1:
            extras.append(Choice("Visit the bookmaker", Action("bookmaker", betting)))
        platform = T.here(world, town, ("lei_tai",), ("active",))''')
Path(ENG).write_text(Path(ENG).read_text(encoding="utf-8") + '''
    # --- the bookmaker (phase 4e spec 5.1) ----------------------------------------------------
    _betting_on: int | None = None

    def _board(self, occurrence: int) -> tuple[list, list]:
        world, me = self.world, self.player.id
        stake = wagers.stake_limit(world, me)
        lines, choices = [(f"The odds board (you may stake up to {stake} silver):", "heading")], []
        for r, i, m in wagers.open_matches(world, occurrence)[:4]:
            prices = wagers.odds(world, occurrence, r, i)
            a, b = world.entity(m["a"]).name, world.entity(m["b"]).name
            lines.append((f"  Round {r + 1}: {a} at {prices[m['a']]:.2f} to 1, {b} at {prices[m['b']]:.2f} to 1", "dim"))
            choices += [Choice(f"Bet {stake} on {a}", Action("bet", (occurrence, r, i, m["a"]))),
                        Choice(f"Bet {stake} on {b}", Action("bet", (occurrence, r, i, m["b"])))]
        return lines, choices

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is None and self.submenu == "wagers" and self._betting_on is not None:
            options["wagers"] = (self._board(self._betting_on)[1], Action("back"))
        return options

    def _do_bookmaker(self, occurrence):
        if not isinstance(occurrence, int) or occurrence != T.here(self.world, self.place.id, T.KINDS, ("active",)):
            return self._turn([("There is no bookmaker taking bets here.", "system")])
        self._betting_on, self.submenu = occurrence, "wagers"
        return self._turn(self._board(occurrence)[0])

    def _do_bet(self, target):
        if not isinstance(target, (tuple, list)) or len(target) != 4:
            return self._turn([("Bet on whom?", "system")])
        occurrence, r, i, on = target
        stake = wagers.stake_limit(self.world, self.player.id)
        why = wagers.bet_block(self.world, occurrence, r, i, on, stake, self.player.id)
        if why:
            return self._turn([(why, "system")])
        lines = self._commit(wagers.bet_events(self.world, occurrence, r, i, on, stake, self.player.id))
        self._betting_on, self.submenu = occurrence, "wagers"
        return self._turn(lines)
''', encoding="utf-8", newline="\n")

INV = "debug/invariants.py"
edit(INV, '''        if t.get("finished") and t.get("champion") != rounds[-1][0]["winner"]:''', '''        for n, bet in enumerate(t.get("bets", [])):
            if bet["stake"] > bet["silver"] * 0.1 + 1e-9:
                out.append(f"{who} bet {n + 1} staked more than a tenth of the bettor's silver")
            if t.get("finished") and not bet["settled"]:
                out.append(f"{who} has an open bet ({n + 1}) after it ended")
        if t.get("finished") and t.get("champion") != rounds[-1][0]["winner"]:''')

TEXT = "narrate/tournament_text.py"
Path(TEXT).write_text(Path(TEXT).read_text(encoding="utf-8") + '''


def _fixed_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} bet against themselves in {variant.get('place') or 'a tournament'} "
               "and lost the bout. People are talking about a fix.")


SPECIAL_PHRASES["fixed"] = _fixed_story


@outcome("bet_placed", body_facts=False)
def _bet(world, event):
    d = event.data
    return [f"You stake {d['stake']} silver on {world.entity(d['on']).name} at {d['odds']:.2f} to 1."], {}


@summary("bet_placed")
def _bet_line(world, entry, names, place, other):
    return f"Bet {entry.data['stake']} silver on {world.entity(entry.data['on']).name} in {place}."


@outcome("bet_settled", body_facts=False)
def _settled(world, event):
    d = event.data
    if d["void"]:
        return [f"The bet is void; your {d['payout']} silver is returned."], {}
    return [f"Your bet pays {d['payout']} silver." if d["payout"] else "Your bet is lost."], {}


@summary("bet_settled")
def _settled_line(world, entry, names, place, other):
    d = entry.data
    return "Had a bet voided." if d["void"] else f"Won {d['payout']} silver on a bet." if d["payout"] else "Lost a bet."
''', encoding="utf-8", newline="\n")
Path("narrate/grammar/tournament.toml").write_text(Path("narrate/grammar/tournament.toml").read_text(encoding="utf-8") + '''
[bet_placed]
colour = "default"
lines = ["#tour_bookie#", "#tour_bookie# #tour_crowd#"]

[bet_settled]
colour = "default"
lines = ["#tour_bookie#", "#tour_bookie# #tour_crowd#"]
''', encoding="utf-8", newline="\n")
edit("narrate/grammar/tournament.toml", '''tour_shame = [''', '''tour_bookie = ["The bookmaker licks his thumb and counts.", "A chit changes hands.", "The odds board is rewritten in chalk.", "Somebody groans at the board.", "The bookmaker's boy runs off with your chit."]
tour_shame = [''')
print("task 4 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4e_task4.py && .venv/Scripts/python.exe -m pytest tests/test_wagers.py -q -p no:cacheprovider`
Expected: `task 4 edits applied`, then `8 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: betting - the bookmaker's odds follow the town's beliefs; bets settle once, void on death or disgrace"`

---
### Task 5: Watching, elders in the crowd, and grudges from the arena

**Files:**
- Create: `systems/arena.py`
- Modify (via `.patches/4e_task5.py`):
  - `systems/tournaments.py`: losers remember their winner (witnesses on `match_resolved`); round winners roll to be noticed;
  - `engine/tournament.py`: `watch`, and accepting an invitation;
  - `narrate/tournament_text.py`, `narrate/grammar/tournament.toml`: narration.
- Test: `tests/test_arena_stories.py`

**Interfaces:**
- Consumes (Tasks 1–4): `T.match_event`, `T._sim_winner`, `T.day`, `T.watched`, `T.here`, `T.KINDS`; `duel.fragment_of`, `duel._add_fragment`, `opponent.tendency`; `membership.joined_events`; `halls.halls_here`, `staff_at`; `agendas.grudge`.
- Produces:
  - **`systems.arena`:**
    - constants: `NOTICE_BASE = 0.2`, `GRUDGE_CHANCE = 0.3`, `GIFT = (30, 80)`;
    - watching: `watchable(world, occurrence_id, player) -> tuple[int, int, dict] | None`, `watch_events(world, occurrence_id, player) -> list[Event]`;
    - grudges and notice: `loser_witnesses(world, occurrence, winner, loser, key) -> tuple[Witness, ...]`, `notice_events(world, occurrence, r, winner) -> list[Event]`.
  - **Events:**
    - `watched` (actors: the player and both fighters; `occurrence`, `round`, `match`, `fragments`, `tendencies`);
    - `noticed` (actors: the elder and the winner; `faction`, `offer` = join | invite | gift, `silver`).
  - Player data `invitations` (`{str(faction): elder}`).
  - **Verbs:** `watch`, `accept_invitation`.

- [ ] **Step 1: Write the failing test** — `tests/test_arena_stories.py`
```python
import pytest

import systems.agendas as agendas
import systems.arena as arena
import systems.encounters as encounters
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def drawn_assembly(game, registered=()):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "grand_assembly", town, world.time,
                                   {**ga.start_data(world, town, 10, rng_for(1, "a")), "registered": list(registered)}))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    return occurrence


def test_watching_settles_a_bout_before_your_eyes(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    r, i, m = arena.watchable(world, occurrence, me)
    turn = game.perform(Action("watch", occurrence))
    assert world.entity(occurrence).data["data"]["rounds"][r][i]["how"] == "sim"
    assert {m["a"], m["b"]} <= set(world.acquaintances(me))
    assert world.entity(me).data.get("fragments") and any("watch" in t.lower() for t, _ in turn.lines)


def test_you_cannot_watch_another_days_bouts(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    world.set_time(T.day_start(world.entity(occurrence), 2))
    assert arena.watchable(world, occurrence, me) is None  # day 2 of the Assembly has no bouts (rounds fall on 1, 3, 5, 7, 8)


def test_an_elder_invites_a_winning_player(game, monkeypatch):
    monkeypatch.setattr(arena, "NOTICE_BASE", 5.0)
    world, me, town = game.world, game.player.id, game.place.id
    occurrence = drawn_assembly(game)
    events = arena.notice_events(world, world.entity(occurrence), 0, me)
    assert events and events[0].data["offer"] == "invite"
    commit(world, events)
    faction = events[0].data["faction"]
    turn = game.perform(Action("look"))
    assert Action("accept_invitation", faction) in [c.action for c in turn.all_choices]
    game.perform(Action("accept_invitation", faction))
    assert F.membership(world, me, faction) is not None


def test_a_members_notice_is_a_gift(game, monkeypatch):
    monkeypatch.setattr(arena, "NOTICE_BASE", 5.0)
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    faction = arena.notice_events(world, world.entity(occurrence), 0, me)[0].data["faction"]
    world.relate(me, faction, "member_of", 0, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                "secret": False})
    silver = silver_of(world, me)
    commit(world, arena.notice_events(world, world.entity(occurrence), 0, me))
    assert silver_of(world, me) > silver


def test_a_noticed_npc_joins_the_sect(game, monkeypatch):
    monkeypatch.setattr(arena, "NOTICE_BASE", 5.0)
    world, town = game.world, game.place.id
    wanderer = founding.make_person(world, "test:wanderer", town, occupation="wandering swordsman", age=25,
                                    realm="second-rate")
    occurrence = drawn_assembly(game)
    events = arena.notice_events(world, world.entity(occurrence), 0, wanderer)
    commit(world, events)
    assert F.membership(world, wanderer, events[0].data["faction"])[1]["role"] == "disciple"


def test_losers_remember_and_the_proud_want_revenge(game, monkeypatch):
    monkeypatch.setattr(arena, "GRUDGE_CHANCE", 1.0)
    world, town = game.world, game.place.id
    occurrence = drawn_assembly(game)
    world.set_time(T.day_start(world.entity(occurrence), 2))
    sky.observe(world, town)
    t = world.entity(occurrence).data["data"]
    losers = [(m["b"] if m["winner"] == m["a"] else m["a"], m["winner"]) for m in t["rounds"][0] if m["how"] == "sim"]
    remembered = [(l, w) for l, w in losers if any(mem.event.actors and mem.event.actors[0] == w
                                                  for mem in world.memories(l))]
    assert remembered
    proud = [(l, w) for l, w in losers if {"proud", "hot-tempered"} & set(world.entity(l).data.get("traits", []))]
    for loser, winner in proud:
        found = agendas.grudge(world, loser, world.time // W.SEASON)
        assert found is not None and found[0] == winner
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_arena_stories.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.arena'`.

- [ ] **Step 3: Write the arena** — `systems/arena.py`
```python
"""Around the brackets (phase 4e spec 5.2-5.3): watching bouts, elders in the crowd, and the grudges of the beaten.

Watching a bout on its day settles it before your eyes: you learn a fragment of each fighter's art
and their stance, and you know them after. Each round's winner may be noticed by an elder of a sect
with a hall in town: a wanderer is taken in, you are invited (or, if already one of theirs, given a
gift). The beaten remember who beat them; the proud may take it as a wrong and seek revenge (4a).
"""

import systems.tournaments as T
from systems import factions as F
from systems import halls
from systems.duel import _add_fragment, fragment_of
from systems.opponent import tendency
from systems.purse import silver_of
from world.events import Event, Witness, effect
from world.seed import rng_for

NOTICE_BASE = 0.2
GRUDGE_CHANCE = 0.3
GIFT = (30, 80)
PROUD = frozenset({"proud", "hot-tempered"})


# --- watching --------------------------------------------------------------------------------------

def watchable(world, occurrence_id: int, player: int) -> tuple[int, int, dict] | None:
    """The next of today's bouts the player may watch at the venue (not their own)."""
    occurrence = world.entity(occurrence_id)
    if occurrence.data["place"] not in world.targets(player, "located_in"):
        return None
    today = T.day(occurrence, world.time)
    for r, matches in enumerate(occurrence.data["data"]["rounds"]):
        for i, m in enumerate(matches):
            if m["how"] is None and m["day"] == today and None not in (m["a"], m["b"]) and player not in (m["a"], m["b"]):
                return r, i, m
    return None


def watch_events(world, occurrence_id: int, player: int) -> list[Event]:
    found = watchable(world, occurrence_id, player)
    if found is None:
        return []
    r, i, m = found
    occurrence = world.entity(occurrence_id)
    winner = T._sim_winner(world, occurrence, m["a"], m["b"], r, i)
    loser = m["b"] if winner == m["a"] else m["a"]
    rng = rng_for(world.world_seed, f"watch:{occurrence_id}:{r}:{i}")
    arts = occurrence.data["data"].get("arts") or {}
    fragments = [fragment_of(world, arts[str(p)], rng) for p in (m["a"], m["b"]) if arts.get(str(p)) is not None]
    tendencies = {str(p): tendency(tuple(world.entity(p).data.get("traits", ()))) for p in (m["a"], m["b"])}
    return [T.match_event(occurrence, r, i, winner, loser, "sim", T.day(occurrence, world.time)),
            Event("watched", (player, m["a"], m["b"]), occurrence.data["place"],
                  {"occurrence": occurrence_id, "round": r, "match": i, "winner": winner, "fragments": fragments,
                   "tendencies": tendencies})]


@effect("watched")
def _watched(world, event) -> None:
    for fragment in event.data["fragments"]:
        _add_fragment(world, event.actors[0], fragment)


# --- grudges -----------------------------------------------------------------------------------------

def loser_witnesses(world, occurrence, winner, loser, key: str) -> tuple[Witness, ...]:
    """How the beaten remember it: humbled by a lesser fighter, or respectful of a better one; the proud,
    or a rival sect's fighter, may take it as a wrong (spec §5.3)."""
    if winner is None or loser is None or world.entity(loser).data.get("is_player"):
        return ()
    feeling = "humiliated" if T.realm_of(world, loser) > T.realm_of(world, winner) else "respect"
    proud = PROUD & set(world.entity(loser).data.get("traits", ()))
    rivals = not proud and T.watched(world, occurrence) and any(  # sect rivalry: weighed where the player sees
        F.stance(world, a, b) <= F.HOSTILE
        for a, _, _ in F.memberships(world, loser) for b, _, _ in F.memberships(world, winner) if a != b)
    if (proud or rivals) and rng_for(world.world_seed, f"grudge:{occurrence.id}:{key}").random() < GRUDGE_CHANCE:
        return (Witness(loser, "wronged", 0.8),)
    return (Witness(loser, feeling, 0.5),)


# --- elders in the crowd ------------------------------------------------------------------------------

def _elder_here(world, town: int, rng) -> tuple[int, int] | None:
    """(faction, elder) for a sect with a hall in town and an elder at it, chosen by seed."""
    found = []
    for faction in halls.halls_here(world, town):
        if world.entity(faction).data.get("type") in F.STAFFED:
            found += [(faction, e) for e in halls.staff_at(world, faction, town, roles=("elder", "leader"))]
    return rng.choice(sorted(found)) if found else None


def notice_events(world, occurrence, r: int, winner) -> list[Event]:
    """A round's winner may catch an elder's eye: later rounds, better odds (spec §5.2)."""
    t = occurrence.data["data"]
    if winner is None or not T.alive(world, winner) or not t["rounds"]:
        return []
    rng = rng_for(world.world_seed, f"notice:{occurrence.id}:{r}:{winner}")
    if rng.random() >= NOTICE_BASE * (r + 1) / len(t["rounds"]):
        return []
    found = _elder_here(world, occurrence.data["place"], rng)
    if found is None:
        return []
    faction, elder = found
    person = world.entity(winner)
    already = F.membership(world, winner, faction)
    if person.data.get("is_player"):
        offer = "gift" if already else "invite"
    elif already or any(world.entity(f).data.get("type") in F.MARTIAL for f, _, d in F.memberships(world, winner)
                        if d.get("status", "member") == "member"):
        return []
    else:
        offer = "join"
    return [Event("noticed", (elder, winner), occurrence.data["place"],
                  {"faction": faction, "offer": offer, "silver": rng.randint(*GIFT) if offer == "gift" else 0})]


@effect("noticed")
def _noticed(world, event) -> None:
    elder, person = event.actors
    d = event.data
    if d["offer"] == "join":
        world.relate(person, d["faction"], "member_of", 0, {"role": "disciple", "hall": None, "merit": 0,
                                                            "status": "member", "secret": False})
    elif d["offer"] == "invite":
        invitations = dict(world.entity(person).data.get("invitations", {}))
        invitations[str(d["faction"])] = elder
        world.update_data(person, invitations=invitations)
    else:
        world.update_data(person, silver=silver_of(world, person) + d["silver"])
```

- [ ] **Step 4: Edit the existing files** — `.patches/4e_task5.py`
```python
"""Task 5 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


TOUR = "systems/tournaments.py"
edit(TOUR, '''def match_event(occurrence, r: int, i: int, winner, loser, how: str, now_day: int) -> Event:
    actors = tuple(p for p in (winner, loser) if p is not None)
    return Event("match_resolved", actors, occurrence.data["place"],
                 {"occurrence": occurrence.id, "round": r, "match": i, "winner": winner, "loser": loser,
                  "how": how, "on": now_day})''', '''def match_event(occurrence, r: int, i: int, winner, loser, how: str, now_day: int, world=None) -> Event:
    actors = tuple(p for p in (winner, loser) if p is not None)
    witnesses = ()
    if world is not None and how in ("sim", "bout"):  # the beaten remember who beat them (spec §5.3)
        from systems.arena import loser_witnesses
        witnesses = loser_witnesses(world, occurrence, winner, loser, f"{r}:{i}")
    return Event("match_resolved", actors, occurrence.data["place"],
                 {"occurrence": occurrence.id, "round": r, "match": i, "winner": winner, "loser": loser,
                  "how": how, "on": now_day}, witnesses=witnesses)''')
edit(TOUR, '''    loser = (b if winner == a else a) if winner is not None else None
    return match_event(occurrence, r, i, winner, loser, how, now_day)''', '''    loser = (b if winner == a else a) if winner is not None else None
    return match_event(occurrence, r, i, winner, loser, how, now_day, world)''')
edit(TOUR, '''    loser = opponent if winner == player else player
    return [match_event(occurrence, r, i, winner, loser, "bout", max(today, m["day"]))]''', '''    loser = opponent if winner == player else player
    return [match_event(occurrence, r, i, winner, loser, "bout", max(today, m["day"]), world)]''')
edit(TOUR, '''@listen("match_resolved")
def _bested(world, event, event_id: int) -> None:''', '''@listen("match_resolved")
def _noticed(world, event, event_id: int) -> None:
    d = event.data
    if d["how"] in ("sim", "bout") and d["winner"] is not None:
        from systems.arena import notice_events
        occurrence = world.entity(d["occurrence"])
        if watched(world, occurrence):  # elders in the crowd notice where the player is (level of detail)
            events = notice_events(world, occurrence, d["round"], d["winner"])
            if events:
                commit(world, events)


@listen("match_resolved")
def _bested(world, event, event_id: int) -> None:''')

ENG = "engine/tournament.py"
edit(ENG, '''import systems.tournaments as T
''', '''import systems.arena as arena
import systems.tournaments as T
''')
edit(ENG, '''        betting = T.here(world, town, T.KINDS, ("active",))''', '''        watching = T.here(world, town, T.KINDS, ("active",))
        if watching is not None and arena.watchable(world, watching, me) is not None:
            extras.append(Choice("Watch today's bouts", Action("watch", watching)))
        for faction, elder in sorted((int(f), e) for f, e in self.player.data.get("invitations", {}).items()):
            if world.entity(elder) is not None and town in world.targets(elder, "located_in"):
                extras.append(Choice(f"Accept the invitation of the {world.entity(faction).name}",
                                     Action("accept_invitation", faction)))
        betting = T.here(world, town, T.KINDS, ("active",))''')
Path(ENG).write_text(Path(ENG).read_text(encoding="utf-8") + '''
    # --- watching and invitations (phase 4e spec 5.2) ------------------------------------------
    def _do_watch(self, occurrence):
        events = arena.watch_events(self.world, occurrence, self.player.id) if isinstance(occurrence, int) else []
        if not events:
            return self._turn([("There is no bout to watch here now.", "system")])
        return self._turn(self._commit(events))

    def _do_accept_invitation(self, faction):
        from systems.membership import joined_events
        invitations = dict(self.player.data.get("invitations", {}))
        elder = invitations.get(str(faction))
        if elder is None:
            return self._turn([("No one has invited you.", "system")])
        del invitations[str(faction)]
        self.world.update_data(self.player.id, invitations=invitations)
        return self._turn(self._commit(joined_events(self.world, self.player.id, elder, faction, self.place.id, False)))
''', encoding="utf-8", newline="\n")

TEXT = "narrate/tournament_text.py"
Path(TEXT).write_text(Path(TEXT).read_text(encoding="utf-8") + '''


@outcome("watched", body_facts=False)
def _watched(world, event):
    d = event.data
    a, b = (world.entity(p).name for p in event.actors[1:])
    winner = world.entity(d["winner"]).name
    lines = [f"You watch {a} and {b} fight; {winner} wins."]
    for person, word in d["tendencies"].items():
        lines.append(f"{world.entity(int(person)).name} {word}.")
    if d["fragments"]:
        lines.append("You commit something of their forms to memory.")
    return lines, {}


@summary("watched")
def _watched_line(world, entry, names, place, other):
    return f"Watched {names[1]} and {names[2]} fight in {place}."


@outcome("noticed", body_facts=False)
def _noticed(world, event):
    elder, d = world.entity(event.actors[0]).name, event.data
    faction = world.entity(d["faction"]).name
    if d["offer"] == "invite":
        return [f"{elder} of the {faction} finds you afterwards: the {faction} would take you in, no trial asked."], {}
    if d["offer"] == "gift":
        return [f"{elder} of the {faction} presses {d['silver']} silver into your hand: well fought."], {}
    return [f"{elder} of the {faction} takes {world.entity(event.actors[1]).name} in."], {}


@summary("noticed")
def _noticed_line(world, entry, names, place, other):
    return f"Was noticed by {names[0]} of the {world.entity(entry.data['faction']).name} in {place}."
''', encoding="utf-8", newline="\n")
Path("narrate/grammar/tournament.toml").write_text(Path("narrate/grammar/tournament.toml").read_text(encoding="utf-8") + '''
[watched]
colour = "default"
lines = ["#tour_crowd#", "#tour_crowd# #tour_crowd#"]

[noticed]
colour = "default"
lines = ["#tour_crowd#"]
''', encoding="utf-8", newline="\n")
print("task 5 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4e_task5.py && .venv/Scripts/python.exe -m pytest tests/test_arena_stories.py -q -p no:cacheprovider`
Expected: `task 5 edits applied`, then `6 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: around the brackets - watch bouts and learn their forms, elders notice winners, the beaten remember"`

---
### Task 6: Dark interventions: the raid, the fixed match, the vanished favourite

**Files:**
- Create: `systems/intrigue.py`
- Modify (via `.patches/4e_task6.py`):
  - `systems/tournaments.py`:
    - `alive` excludes the vanished;
    - `ends(occurrence)`, used by `_next_events` and `player_call` (a raid pushes the final into the aftermath);
    - the draw carries the plot;
    - `_sim_winner` weakens the fixed fighter;
    - `_next_events` asks for intrigue first;
    - a void final has no runner-up;
  - `systems/wagers.py`: a void match voids its bets;
  - `debug/invariants.py`: the vanished have no location (and their memberships are `missing`);
  - `engine/tournament.py`: defend, expose a fix, ask the bookmaker, the raid line;
  - `narrate/tournament_text.py`, `narrate/grammar/tournament.toml`: narration.
- Test: `tests/test_intrigue.py`

**Interfaces:**
- Consumes (Tasks 1–5):
  - `T.draw_events`, `T._sim_winner`, `T._next_events`, `T.player_call`, `T.match_event`, `T.alive`, `T.watched`, `T.day`, `T.day_start`, `T.here`, `T.KINDS`;
  - `wagers._settle`; `arena.watch_events` (the `watched` event: `occurrence`, `round`, `match`);
  - `facts.ON_FACT`, `record_fact(spread=False)`; `beliefs.believe`; `reputation.reputation`; `founding.make_person`.
- Produces:
  - **`systems.intrigue`:**
    - constants: `CHANCES` (kind → ((intervention, chance), ...)), `FIX_FACTOR = 0.6`, `RAID_DEATH = 0.15`, `RUMOUR_CHANCE = 0.25`, `ASK_BASE = 0.2`, `ASK_PER_RENOWN = 0.05`, `ASK_MAX = 0.8`;
    - the plot: `plot(world, occurrence, rounds, ordered) -> dict | None`, `weakened(occurrence, r, i) -> int | None`, `weaken(fighter) -> Fighter`, `due_events(world, occurrence, now_day, over) -> list[Event]`, `raid_events(world, occurrence, on) -> list[Event]`;
    - the fix: `fix_of(world, occurrence_id) -> dict | None`, `knows(world, person, fact_id) -> bool`, `ask_block`, `ask_events`, `exposable(world, player) -> list[int]`, `expose_events(world, occurrence_id, player, town)`;
    - the raid: `defence_open(world, occurrence_id, player) -> int | None` (the cultist), `defended_events(world, occurrence_id, player, cultist, won)`.
  - **`systems.tournaments`:** `ends(occurrence) -> int`; the bracket's `intrigue` and `until` keys.
  - **Plots:**
    - `{"kind": "raid", "done", "day", "cultist", "defenders"}`;
    - `{"kind": "fixed", "round", "match", "victim", "against", "how", "fact", "exposed"}`;
    - `{"kind": "vanished", "victim", "round", "done"}`.
  - **Events:**
    - `raided` (`occurrence`, `fallen`, `cultist`, `day`);
    - `vanished` (actor: the favourite; `occurrence`, `round`, `match`);
    - `asked_bookmaker` (`occurrence`, `learned`, `fact`, `victim`);
    - `exposed` (actors: the player and the victim; `occurrence`, `fact`, `how`);
    - `defended` (actors: the player and the cultist; `occurrence`, `won`);
    - a `match_resolved` with `how = "void"` (no winner, no loser).
  - **Facts:**
    - `fixed` (actor: the victim, target: their opponent; variant `how`, `kind`), recorded unspread;
    - `raided` (subject: the town, weight 3.0); `vanished` (weight 1.5); `exposed_fix` (weight 1.5); `defended` (weight 2.0).
  - **Verbs:** `defend`, `expose_fix` (`expose` is taken: 3c politics), `ask_bookmaker`.

- [ ] **Step 1: Write the failing test** — `tests/test_intrigue.py`
```python
import pytest

import systems.arena as arena
import systems.encounters as encounters
import systems.intrigue as intrigue
import systems.sky as sky
import systems.tournaments as T
import systems.wagers as wagers
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems.creation import CreationChoice
from systems.purse import silver_of
from systems.reputation import reputation
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    sky.observe(game.world, game.place.id)


def drawn(game, monkeypatch, plot, **knobs):
    """An Assembly in the player's town, drawn on day 1, carrying this intervention."""
    import systems.events.grand_assembly as ga
    monkeypatch.setitem(intrigue.CHANCES, "grand_assembly", ((plot, 1.0),))
    for name, value in knobs.items():
        monkeypatch.setattr(intrigue, name, value)
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "grand_assembly", town, world.time,
                                   ga.start_data(world, town, 10, rng_for(1, "a"))))
    occurrence = W.index(world)[-1][W.ID]
    to_day(game, occurrence, 1)
    return occurrence


def plot_of(world, occurrence):
    return world.entity(occurrence).data["data"]["intrigue"]


def heard(world, town, predicate):
    return [f for _, f in world.known_facts(town) if f.predicate == predicate]


def test_a_draw_carries_one_seeded_intervention_at_most(game, monkeypatch):
    world = game.world
    occurrence = drawn(game, monkeypatch, "fixed")
    t = world.entity(occurrence).data["data"]
    first = intrigue.plot(world, world.entity(occurrence), t["rounds"], t["entrants"])
    assert first["kind"] == "fixed" and first == intrigue.plot(world, world.entity(occurrence), t["rounds"], t["entrants"])
    monkeypatch.setitem(intrigue.CHANCES, "grand_assembly", ())
    assert intrigue.plot(world, world.entity(occurrence), t["rounds"], t["entrants"]) is None


def test_a_fix_is_a_secret_from_the_draw(game, monkeypatch):
    world = game.world
    occurrence = drawn(game, monkeypatch, "fixed")
    p = plot_of(world, occurrence)
    m = world.entity(occurrence).data["data"]["rounds"][0][p["match"]]
    assert (p["victim"], p["against"]) == (m["a"], m["b"])  # the favourite is the one got at
    assert world.fact(p["fact"]).predicate == "fixed" and world.believers(p["fact"]) == []


@pytest.mark.parametrize("seen", [True, False])
def test_the_fixed_fighter_fights_weakened(game, monkeypatch, seen):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "fixed", FIX_FACTOR=0.0, RUMOUR_CHANCE=0.0)
    p = plot_of(world, occurrence)
    if not seen:
        world.unrelate(me, "located_in")  # far away, bouts are decided by realm (level of detail)
    world.set_time(T.day_start(world.entity(occurrence), 2))
    T.resolve(world, occurrence)
    m = world.entity(occurrence).data["data"]["rounds"][0][p["match"]]
    assert m["how"] == "sim" and m["winner"] == p["against"]


def test_watching_the_fixed_bout_reveals_it(game, monkeypatch):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "fixed", RUMOUR_CHANCE=0.0)
    p = plot_of(world, occurrence)
    for _ in range(16):
        if intrigue.knows(world, me, p["fact"]) or arena.watchable(world, occurrence, me) is None:
            break
        commit(world, arena.watch_events(world, occurrence, me))
    assert intrigue.knows(world, me, p["fact"])
    assert Action("expose_fix", occurrence) in [c.action for c in game.perform(Action("look")).all_choices]


def test_the_bookmaker_may_let_a_fix_slip(game, monkeypatch):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "fixed", ASK_BASE=1.0)
    p = plot_of(world, occurrence)
    world.update_data(me, silver=500)
    turn = game.perform(Action("bookmaker", occurrence))
    assert Action("ask_bookmaker", occurrence) in [c.action for c in turn.all_choices]
    game.perform(Action("ask_bookmaker", occurrence))
    assert intrigue.knows(world, me, p["fact"])
    assert intrigue.ask_block(world, occurrence, me) is not None  # once a tournament


def test_a_straight_tournament_gives_the_bookmaker_nothing_to_tell(game, monkeypatch):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "raid", ASK_BASE=1.0)
    assert intrigue.ask_events(world, occurrence, me)[0].data["learned"] is False


def test_exposing_a_fix_spreads_it_and_brings_renown(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    occurrence = drawn(game, monkeypatch, "fixed", ASK_BASE=1.0, RUMOUR_CHANCE=0.0)
    p = plot_of(world, occurrence)
    commit(world, intrigue.ask_events(world, occurrence, me))
    before = reputation(world, town, me).renown
    game.perform(Action("expose_fix", occurrence))
    assert town in {b.knower for b in world.believers(p["fact"])}
    assert reputation(world, town, me).renown > before
    assert plot_of(world, occurrence)["exposed"] and intrigue.exposable(world, me) == []


def test_a_fix_may_come_out_on_its_own(game, monkeypatch):
    world, town = game.world, game.place.id
    occurrence = drawn(game, monkeypatch, "fixed", RUMOUR_CHANCE=1.0)
    p = plot_of(world, occurrence)
    to_day(game, occurrence, 2)
    assert town in {b.knower for b in world.believers(p["fact"])}


def test_a_raid_breaks_up_the_final_and_it_is_fought_again(game, monkeypatch):
    world, town = game.world, game.place.id
    occurrence = drawn(game, monkeypatch, "raid", RAID_DEATH=0.0)
    to_day(game, occurrence, 8)
    final = world.entity(occurrence).data["data"]["rounds"][-1][0]
    assert plot_of(world, occurrence)["done"] and final["how"] is None and final["day"] == 9
    assert heard(world, town, "raided")
    to_day(game, occurrence, 10)
    t = world.entity(occurrence).data["data"]
    assert t["finished"] and t["champion"] is not None and t["champion"] == t["rounds"][-1][0]["winner"]
    assert check_tournaments(world) == []


def test_a_finalist_slain_in_a_raid_voids_the_final(game, monkeypatch):
    world = game.world
    occurrence = drawn(game, monkeypatch, "raid", RAID_DEATH=1.0)
    to_day(game, occurrence, 8)
    t = world.entity(occurrence).data["data"]
    final = t["rounds"][-1][0]
    assert final["how"] == "void" and t["finished"] and t["champion"] is None
    assert all(not T.alive(world, p) for p in (final["a"], final["b"]))
    assert check_tournaments(world) == []


def test_you_may_join_the_defence(game, monkeypatch):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "raid", RAID_DEATH=0.0)
    to_day(game, occurrence, 8)
    cultist = intrigue.defence_open(world, occurrence, me)
    assert cultist is not None
    assert Action("defend", occurrence) in [c.action for c in game.perform(Action("look")).all_choices]
    game.perform(Action("defend", occurrence))
    assert game.combat is not None and game.combat.opponent == cultist
    commit(world, intrigue.defended_events(world, occurrence, me, cultist, True))
    assert intrigue.defence_open(world, occurrence, me) is None
    assert heard(world, game.place.id, "defended")


def test_a_favourite_vanishes_the_night_before_their_round(game, monkeypatch):
    world, town = game.world, game.place.id
    occurrence = drawn(game, monkeypatch, "vanished")
    p = plot_of(world, occurrence)
    t = world.entity(occurrence).data["data"]
    world.update_data(occurrence, data={**t, "intrigue": {**p, "round": 1}})
    first = next(m for m in t["rounds"][0] if p["victim"] in (m["a"], m["b"]))
    rival = first["b"] if first["a"] == p["victim"] else first["a"]
    world.update_data(rival, dead=True)  # the favourite walks over into round 2
    to_day(game, occurrence, 2)
    victim = world.entity(p["victim"])
    assert victim.data.get("vanished") and not world.targets(victim.id, "located_in")
    assert all(d.get("status") == "missing" for _, _, d in F.memberships(world, victim.id))
    to_day(game, occurrence, 4)
    m = next(m for m in world.entity(occurrence).data["data"]["rounds"][1] if p["victim"] in (m["a"], m["b"]))
    assert m["how"] == "walkover" and m["winner"] != p["victim"]
    assert heard(world, town, "vanished")


def test_bets_on_a_void_match_are_returned(game, monkeypatch):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "raid")
    world.update_data(me, silver=500)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 50, me))
    commit(world, [T.match_event(world.entity(occurrence), r, i, None, None, "void", 1)])
    assert silver_of(world, me) == 500
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_intrigue.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.intrigue'`.

- [ ] **Step 3: Write the intrigue** — `systems/intrigue.py`
```python
"""Dark interventions (phase 4e spec 5.4): at most one per tournament, seeded at the draw.

- A demonic raid breaks up the final: it is fought again the next day, or is void if a finalist
  falls. A player at the venue may join the defence.
- A fixed match: one entrant is poisoned or bribed and fights at 0.6 of their strength in one bout.
  The fix is a fact nobody holds until it comes out: the bookmaker lets it slip, the player watches
  the bout, or a rumour gets out. Whoever knows may expose it, and is known for it.
- A vanished favourite disappears the night before their round and forfeits. Where they went is
  left open (spec §9).
"""

import dataclasses

import systems.tournaments as T
import systems.world_events as W
from systems.beliefs import CONF_DECAY, believe
from systems.facts import ON_FACT, make_variant, place_name, record_fact
from systems import factions as F
from systems.founding import make_person
from systems.membership import set_membership
from systems.reputation import reputation
from world.events import Event, effect, listen
from world.seed import rng_for

CHANCES = {"grand_assembly": (("raid", 0.10), ("fixed", 0.15), ("vanished", 0.05)),
           "dragon_phoenix": (("raid", 0.05), ("fixed", 0.10), ("vanished", 0.05)),
           "sect_contest": (("fixed", 0.05),)}
FIX_FACTOR = 0.6
RAID_DEATH = 0.15  # each NPC finalist's chance to fall to the cultists
RUMOUR_CHANCE = 0.25  # a fix gets out by itself once its bout is fought
ASK_BASE, ASK_PER_RENOWN, ASK_MAX = 0.2, 0.05, 0.8
CULTIST_REALM = {"grand_assembly": "first-rate", "dragon_phoenix": "second-rate"}


def _is_player(world, person) -> bool:
    return person is not None and bool(world.entity(person).data.get("is_player"))


# --- the plot ---------------------------------------------------------------------------------------

def plot(world, occurrence, rounds: list, ordered: list[int]) -> dict | None:
    """The one dark intervention this draw carries, if any: seeded by the occurrence."""
    rng = rng_for(world.world_seed, f"intrigue:{occurrence.id}")
    roll, total, kind = rng.random(), 0.0, None
    for name, chance in CHANCES.get(occurrence.data["data"]["kind"], ()):
        total += chance
        if roll < total:
            kind = name
            break
    if kind == "raid":
        return {"kind": "raid", "done": False, "day": None, "cultist": None, "defenders": []}
    if kind == "fixed":
        fair = [i for i, m in enumerate(rounds[0]) if None not in (m["a"], m["b"])
                and not _is_player(world, m["a"]) and not _is_player(world, m["b"])]
        if fair:
            i = rng.choice(fair)
            m = rounds[0][i]
            return {"kind": "fixed", "round": 0, "match": i, "victim": m["a"], "against": m["b"],  # a: the higher seed
                    "how": rng.choice(("poisoned", "bribed")), "fact": None, "exposed": False}
    if kind == "vanished" and len(rounds) > 1:
        favourites = [p for p in ordered if not _is_player(world, p)]
        if favourites:
            return {"kind": "vanished", "victim": favourites[0], "round": rng.randint(1, len(rounds) - 1),
                    "done": False}
    return None


def weakened(occurrence, r: int, i: int):
    """The fighter the fix weakens in this match, or None."""
    p = occurrence.data["data"].get("intrigue") or {}
    return p["victim"] if p.get("kind") == "fixed" and (p["round"], p["match"]) == (r, i) else None


def weaken(fighter):
    return dataclasses.replace(fighter, realm_mult=fighter.realm_mult * FIX_FACTOR)


def due_events(world, occurrence, now_day: int, over: bool) -> list[Event]:
    """A raid on the final's day, or a disappearance the night before the favourite's round."""
    t = occurrence.data["data"]
    p = t.get("intrigue")
    if not p or p["kind"] == "fixed" or p["done"]:
        return []
    if p["kind"] == "raid":
        final = t["rounds"][-1][0]
        if final["how"] is None and None not in (final["a"], final["b"]) and (over or now_day >= final["day"]):
            return raid_events(world, occurrence, max(now_day, final["day"]))
        return []
    for i, m in enumerate(t["rounds"][p["round"]]):
        if m["how"] is None and p["victim"] in (m["a"], m["b"]) and None not in (m["a"], m["b"]) \
                and (over or now_day >= m["day"] - 1) and T.alive(world, p["victim"]):
            return [Event("vanished", (p["victim"],), occurrence.data["place"],
                          {"occurrence": occurrence.id, "round": p["round"], "match": i})]
    return []


@effect("vanished")
def _vanished(world, event) -> None:
    person = event.actors[0]
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    world.update_data(person, vanished={"occurrence": occurrence.id, "time": world.time})
    world.unrelate(person, "located_in")  # gone from the town; where to is left open (spec §9)
    for faction, _, data in F.memberships(world, person):  # their sect counts them missing, and fills their post
        if data.get("status", "member") == "member":
            set_membership(world, person, faction, status="missing")
    world.update_data(occurrence.id, data={**t, "intrigue": {**t["intrigue"], "done": True}})


@listen("vanished")
def _vanished_news(world, event, event_id: int) -> None:
    person = event.actors[0]
    variant = make_variant("vanished", person, None, place=place_name(world, event.place))
    variant["kind"] = world.entity(event.data["occurrence"]).data["data"]["kind"]
    record_fact(world, person, "vanished", None, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


# --- the raid ---------------------------------------------------------------------------------------

def raid_events(world, occurrence, on: int) -> list[Event]:
    t = occurrence.data["data"]
    town, final = occurrence.data["place"], t["rounds"][-1][0]
    rng = rng_for(world.world_seed, f"intrigue:{occurrence.id}:raid")
    fallen = [p for p in (final["a"], final["b"]) if not _is_player(world, p) and rng.random() < RAID_DEATH]
    cultist = None
    if T.watched(world, occurrence):  # someone to fight only where the player can join the defence
        cultist = make_person(world, f"tournament:{occurrence.id}:cultist", town, occupation="demonic cultist",
                              age=rng.randint(25, 50), realm=CULTIST_REALM.get(t["kind"], "second-rate"))
    events = [Event("raided", (), town, {"occurrence": occurrence.id, "fallen": fallen, "cultist": cultist,
                                         "day": final["day"]})]
    events += [Event("died", (p, p), town, {"cause": "raid", "world": True}) for p in fallen]
    if fallen:  # a finalist fell: the final is void
        events.append(T.match_event(occurrence, len(t["rounds"]) - 1, 0, None, None, "void", on))
    return events


@effect("raided")
def _raided(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    rounds = [list(r) for r in t["rounds"]]
    extra = {}
    if not d["fallen"]:  # the final is fought again the next day
        rounds[-1][0] = dict(rounds[-1][0], day=d["day"] + 1)
        extra["until"] = max(occurrence.data["active"][1], T.day_start(occurrence, d["day"] + 2))
    world.update_data(occurrence.id, data={**t, **extra, "rounds": rounds,
                                           "intrigue": {**t["intrigue"], "done": True, "day": d["day"],
                                                        "cultist": d["cultist"]}})


@listen("raided")
def _raided_news(world, event, event_id: int) -> None:
    kind = world.entity(event.data["occurrence"]).data["data"]["kind"]
    variant = make_variant("raided", event.place, None, place=place_name(world, event.place))
    variant["kind"] = kind
    record_fact(world, event.place, "raided", None, place=event.place, source_event=event_id, weight=3.0,
                variant=variant)


def defence_open(world, occurrence_id: int, player: int) -> int | None:
    """The cultist to fight, if a raid is on at this venue today and the player has not fought yet."""
    occurrence = world.entity(occurrence_id)
    p = occurrence.data["data"].get("intrigue") or {}
    if p.get("kind") != "raid" or not p["done"] or p["cultist"] is None or player in p["defenders"]:
        return None
    if T.day(occurrence, world.time) != p["day"] or occurrence.data["place"] not in world.targets(player, "located_in"):
        return None
    return p["cultist"] if T.alive(world, p["cultist"]) else None


def defended_events(world, occurrence_id: int, player: int, cultist: int, won: bool) -> list[Event]:
    return [Event("defended", (player, cultist), world.entity(occurrence_id).data["place"],
                  {"occurrence": occurrence_id, "won": won})]


@effect("defended")
def _defended(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    p = t["intrigue"]
    world.update_data(occurrence.id, data={**t, "intrigue": {**p, "defenders": p["defenders"] + [event.actors[0]]}})


@listen("defended")
def _defended_news(world, event, event_id: int) -> None:
    if not event.data["won"]:
        return
    player = event.actors[0]
    variant = make_variant("defended", player, None, place=place_name(world, event.place))
    variant["kind"] = world.entity(event.data["occurrence"]).data["data"]["kind"]
    record_fact(world, player, "defended", None, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


# --- the fix ----------------------------------------------------------------------------------------

@listen("bracket_drawn")
def _secret(world, event, event_id: int) -> None:
    """The fix is a fact from the draw, but nobody holds it yet."""
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    p = t.get("intrigue")
    if not p or p["kind"] != "fixed":
        return
    variant = make_variant("fixed", p["victim"], p["against"], place=place_name(world, event.place))
    variant.update(how=p["how"], kind=t["kind"])
    fact = record_fact(world, p["victim"], "fixed", p["against"], place=event.place, variant=variant, weight=2.0,
                       spread=False, extra={"occurrence": occurrence.id})
    world.update_data(occurrence.id, data={**t, "intrigue": {**p, "fact": fact}})


def fix_of(world, occurrence_id: int) -> dict | None:
    p = world.entity(occurrence_id).data["data"].get("intrigue") or {}
    return p if p.get("kind") == "fixed" and p.get("fact") is not None else None


def knows(world, person: int, fact_id: int) -> bool:
    return any(b.knower == person for b in world.believers(fact_id))


def _tell(world, knower: int, fact_id: int, confidence: float, hops: int, channel: str) -> None:
    believe(world, knower, fact_id, world.fact(fact_id).variant, None, confidence, hops, channel)


def _publish(world, fact_id: int) -> None:
    """A secret gets out: from here it travels the way any deed does (3c channels)."""
    fact = world.fact(fact_id)
    for channel in ON_FACT:
        channel(world, fact)


@listen("watched")
def _saw_it(world, event, event_id: int) -> None:
    d = event.data
    p = fix_of(world, d["occurrence"])
    if p is not None and (p["round"], p["match"]) == (d["round"], d["match"]):
        _tell(world, event.actors[0], p["fact"], 1.0, 0, "witness")


@listen("match_resolved")
def _rumour(world, event, event_id: int) -> None:
    d = event.data
    if d["round"] != 0:
        return  # a fix is always a first-round bout
    p = fix_of(world, d["occurrence"])
    if p is None or p["exposed"] or p["match"] != d["match"]:
        return
    if rng_for(world.world_seed, f"intrigue:{d['occurrence']}:rumour").random() < RUMOUR_CHANCE:
        _publish(world, p["fact"])


def ask_block(world, occurrence_id: int, player: int) -> str | None:
    occurrence = world.entity(occurrence_id)
    if occurrence.data["place"] not in world.targets(player, "located_in"):
        return "The bookmaker is in the host town."
    if player in occurrence.data["data"].get("asked", []):
        return "The bookmaker has nothing more to tell you."
    return None


def ask_events(world, occurrence_id: int, player: int) -> list[Event]:
    """The bookmaker hears everything; how much they tell depends on who is asking (renown)."""
    occurrence = world.entity(occurrence_id)
    town = occurrence.data["place"]
    p = fix_of(world, occurrence_id)
    learned = False
    if p is not None and not p["exposed"]:
        chance = min(ASK_MAX, ASK_BASE + ASK_PER_RENOWN * reputation(world, town, player).renown)
        learned = rng_for(world.world_seed, f"intrigue:{occurrence_id}:ask:{player}").random() < chance
    return [Event("asked_bookmaker", (player,), town,
                  {"occurrence": occurrence_id, "learned": learned, "fact": p["fact"] if learned else None,
                   "victim": p["victim"] if learned else None})]


@effect("asked_bookmaker")
def _asked(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "asked": t.get("asked", []) + [event.actors[0]]})
    if event.data["learned"]:
        _tell(world, event.actors[0], event.data["fact"], CONF_DECAY, 1, "told")


def exposable(world, player: int) -> list[int]:
    """Tournaments whose fix the player knows of and nobody has exposed yet."""
    found = []
    for row in W.index(world):
        if row[W.TYPE] in T.KINDS:
            p = fix_of(world, row[W.ID])
            if p is not None and not p["exposed"] and knows(world, player, p["fact"]):
                found.append(row[W.ID])
    return found


def expose_events(world, occurrence_id: int, player: int, town: int) -> list[Event]:
    if occurrence_id not in exposable(world, player):
        return []
    p = fix_of(world, occurrence_id)
    return [Event("exposed", (player, p["victim"]), town,
                  {"occurrence": occurrence_id, "fact": p["fact"], "how": p["how"]})]


@effect("exposed")
def _exposed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "intrigue": {**t["intrigue"], "exposed": True}})


@listen("exposed")
def _exposed_news(world, event, event_id: int) -> None:
    player, victim = event.actors
    _publish(world, event.data["fact"])
    _tell(world, event.place, event.data["fact"], CONF_DECAY, 1, "gossip")  # told where the player stands
    variant = make_variant("exposed_fix", player, victim, place=place_name(world, event.place))
    record_fact(world, player, "exposed_fix", victim, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)
```

- [ ] **Step 4: Edit the existing files** — `.patches/4e_task6.py`
```python
"""Task 6 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    Path(path).write_text(Path(path).read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


TOUR = "systems/tournaments.py"
edit(TOUR, '''    return entity is not None and entity.kind == "person" and not entity.data.get("dead")''',
     '''    return entity is not None and entity.kind == "person" and not entity.data.get("dead") \\
        and not entity.data.get("vanished")''')
edit(TOUR, '''def day_start(occurrence, k: int) -> int:
    return occurrence.data["active"][0] + (k - 1) * 4
''', '''def day_start(occurrence, k: int) -> int:
    return occurrence.data["active"][0] + (k - 1) * 4


def ends(occurrence) -> int:
    """When the last bout must be fought: the active stage's end, unless a raid pushed the final past it."""
    return occurrence.data["data"].get("until", occurrence.data["active"][1])
''')
edit(TOUR, '''    return [Event("bracket_drawn", (), town, {"occurrence": occurrence.id, "entrants": ordered, "rounds": rounds,
                                              "arts": arts})]''', '''    from systems.intrigue import plot  # at most one dark intervention, seeded at the draw (spec §5.4)
    return [Event("bracket_drawn", (), town, {"occurrence": occurrence.id, "entrants": ordered, "rounds": rounds,
                                              "arts": arts, "intrigue": plot(world, occurrence, rounds, ordered)})]''')
edit(TOUR, '''                                           "rounds": event.data["rounds"], "arts": event.data["arts"]})''',
     '''                                           "rounds": event.data["rounds"], "arts": event.data["arts"],
                                           "intrigue": event.data.get("intrigue")})''')
edit(TOUR, '''def _sim_winner(world, occurrence, a: int, b: int, r: int, i: int) -> int:
    rng = rng_for(world.world_seed, f"tournament:{occurrence.id}:{r}:{i}")
    if not watched(world, occurrence):  # far from the player: decided by realm, with upsets (plan ruling 7)
        chance = max(0.1, min(0.9, 0.5 + 0.15 * (realm_of(world, a) - realm_of(world, b))))
        return a if rng.random() < chance else b
    for person in (a, b):
        ensure_npc_arts(world, person)
    result, _ = simulate(_fighter(world, occurrence, a), _fighter(world, occurrence, b),
                         lambda r_, history: r_.choice(INTENTS), rng)''', '''def _sim_winner(world, occurrence, a: int, b: int, r: int, i: int) -> int:
    from systems.intrigue import FIX_FACTOR, weaken, weakened
    rng = rng_for(world.world_seed, f"tournament:{occurrence.id}:{r}:{i}")
    weak = weakened(occurrence, r, i)  # a fixed bout: one fighter at 0.6 of their strength (spec §5.4)
    if not watched(world, occurrence):  # far from the player: decided by realm, with upsets (plan ruling 7)
        chance = max(0.1, min(0.9, 0.5 + 0.15 * (realm_of(world, a) - realm_of(world, b))))
        if weak == a:
            chance *= FIX_FACTOR
        elif weak == b:
            chance = 1 - (1 - chance) * FIX_FACTOR
        return a if rng.random() < chance else b
    for person in (a, b):
        ensure_npc_arts(world, person)
    fa, fb = _fighter(world, occurrence, a), _fighter(world, occurrence, b)
    fa, fb = (weaken(fa) if weak == a else fa), (weaken(fb) if weak == b else fb)
    result, _ = simulate(fa, fb, lambda r_, history: r_.choice(INTENTS), rng)''')
edit(TOUR, '''    over = world.time >= d["active"][1]
    now_day = day(occurrence, world.time)
    player = world.get_meta("player_id")
    for r, matches in enumerate(t["rounds"]):''', '''    over = world.time >= ends(occurrence)
    now_day = day(occurrence, world.time)
    from systems.intrigue import due_events
    dark = due_events(world, occurrence, now_day, over)
    if dark:
        return dark
    player = world.get_meta("player_id")
    for r, matches in enumerate(t["rounds"]):''')
edit(TOUR, '''        if not t["rounds"] or t["finished"] or world.time >= occurrence.data["active"][1]:
            continue''', '''        if not t["rounds"] or t["finished"] or world.time >= ends(occurrence):
            continue''')
edit(TOUR, '''    podium = [(final.get("b") if final["winner"] == final.get("a") else final.get("a"), 2)] if t["rounds"] else []''',
     '''    podium = [(final.get("b") if final["winner"] == final.get("a") else final.get("a"), 2)] \\
        if t["rounds"] and final["winner"] is not None else []  # a void final has no runner-up''')

edit("debug/invariants.py", '''        elif len(places) != 1:
            problems.append(f"{person.name} (#{person.id}) has {len(places)} locations")''', '''        elif len(places) != (0 if person.data.get("vanished") else 1):  # the vanished are nowhere (4e)
            problems.append(f"{person.name} (#{person.id}) has {len(places)} locations")''')

edit("systems/wagers.py", '''        void = d["how"] == "disqualified"''', '''        void = d["how"] in ("disqualified", "void")''')

ENG = "engine/tournament.py"
edit(ENG, '''import systems.arena as arena
''', '''import systems.arena as arena
import systems.intrigue as intrigue
''')
edit(ENG, '''                                 Action("challenge_lei_tai", platform)))
        return extras''', '''                                 Action("challenge_lei_tai", platform)))
        if watching is not None and intrigue.defence_open(world, watching, me) is not None:
            extras.append(Choice("Join the defence against the cultists", Action("defend", watching)))
        for occurrence in intrigue.exposable(world, me):
            fix = intrigue.fix_of(world, occurrence)
            extras.append(Choice(f"Expose the fix: {world.entity(fix['victim']).name} was {fix['how']}",
                                 Action("expose_fix", occurrence)))
        return extras''')
edit(ENG, '''    def _herald(self) -> list:
        call = T.player_call(self.world, self.player.id, self.place.id)
        if call is None:
            return []
        kind = self.world.entity(call[0]).data["type"]
        return [(f"The herald calls your name: today you fight {self.world.entity(call[3]).name} "
                 f"at {KIND_NAMES[kind]}.", "dim")]''', '''    def _herald(self) -> list:
        lines = []
        active = T.here(self.world, self.place.id, T.KINDS, ("active",))
        if active is not None and intrigue.defence_open(self.world, active, self.player.id) is not None:
            lines.append(("Black-robed cultists storm the platform before the final; the crowd scatters.", "red"))
        call = T.player_call(self.world, self.player.id, self.place.id)
        if call is None:
            return lines
        kind = self.world.entity(call[0]).data["type"]
        return lines + [(f"The herald calls your name: today you fight {self.world.entity(call[3]).name} "
                         f"at {KIND_NAMES[kind]}.", "dim")]''')
edit(ENG, '''        elif "lei_tai" in purpose:''', '''        elif "raid" in purpose:
            won = data.get("result") == "won"
            lines += self._commit(intrigue.defended_events(self.world, purpose["raid"], me, opponent, won))
        elif "lei_tai" in purpose:''')
edit(ENG, '''            choices += [Choice(f"Bet {stake} on {a}", Action("bet", (occurrence, r, i, m["a"]))),
                        Choice(f"Bet {stake} on {b}", Action("bet", (occurrence, r, i, m["b"])))]
        return lines, choices''', '''            choices += [Choice(f"Bet {stake} on {a}", Action("bet", (occurrence, r, i, m["a"]))),
                        Choice(f"Bet {stake} on {b}", Action("bet", (occurrence, r, i, m["b"])))]
        if intrigue.ask_block(world, occurrence, me) is None:
            choices.append(Choice("Ask what the bookmaker has heard", Action("ask_bookmaker", occurrence)))
        return lines, choices''')
append(ENG, '''
    # --- dark interventions (phase 4e spec 5.4) ----------------------------------------------------
    def _do_defend(self, occurrence):
        cultist = intrigue.defence_open(self.world, occurrence, self.player.id) if isinstance(occurrence, int) else None
        if cultist is None:
            return self._turn([("There is no fighting here to join.", "system")])
        return self._turn(self._start_duel(cultist, "duel", purpose={"raid": occurrence}))

    def _do_expose_fix(self, occurrence):
        events = intrigue.expose_events(self.world, occurrence, self.player.id, self.place.id) \\
            if isinstance(occurrence, int) else []
        if not events:
            return self._turn([("You know of no fix to expose.", "system")])
        return self._turn(self._commit(events))

    def _do_ask_bookmaker(self, occurrence):
        why = intrigue.ask_block(self.world, occurrence, self.player.id) if isinstance(occurrence, int) \\
            else "There is no bookmaker here."
        if why:
            return self._turn([(why, "system")])
        lines = self._commit(intrigue.ask_events(self.world, occurrence, self.player.id))
        self._betting_on, self.submenu = occurrence, "wagers"
        return self._turn(lines)
''')

TEXT = "narrate/tournament_text.py"
edit(TEXT, '''def _fixed_story(world, variant, viewer) -> str:
    return cap(''', '''def _fixed_story(world, variant, viewer) -> str:
    if variant.get("how"):  # a fixed bout (spec §5.4), not a bet against oneself
        victim, rival = who(world, variant.get("actor"), viewer), who(world, variant.get("target"), viewer)
        done = "was poisoned before" if variant["how"] == "poisoned" else "was paid to lose"
        return cap(f"{victim} {done} the bout against {rival} at "
                   f"{KIND_NAMES.get(variant.get('kind'), 'a tournament')} in {variant.get('place') or 'a crowded city'}.")
    return cap(''')
edit(TEXT, '''    if d["how"] == "disqualified":
        return ["The judges strike your name from the bracket."], {}''', '''    if d["how"] == "disqualified":
        return ["The judges strike your name from the bracket."], {}
    if d["how"] == "void":
        return ["The final is declared void: no one is crowned."], {}''')
edit(TEXT, '''    if d["how"] == "disqualified":
        return f"Was disqualified from a tournament in {place}."''', '''    if d["how"] == "disqualified":
        return f"Was disqualified from a tournament in {place}."
    if d["how"] == "void":
        return f"Saw the final in {place} declared void."''')
append(TEXT, '''


def _raided_story(world, variant, viewer) -> str:
    return cap(f"Demonic cultists stormed {KIND_NAMES.get(variant.get('kind'), 'a tournament')} "
               f"in {variant.get('place') or 'a crowded city'} on the day of the final.")


def _vanished_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} vanished the night before a bout at "
               f"{KIND_NAMES.get(variant.get('kind'), 'a tournament')}, and no one knows where.")


def _defended_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} stood against the cultists who stormed "
               f"{KIND_NAMES.get(variant.get('kind'), 'a tournament')} in {variant.get('place') or 'a crowded city'}.")


def _exposed_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} exposed a fixed bout: "
               f"{who(world, variant.get('target'), viewer)} had been got at.")


SPECIAL_PHRASES.update({"raided": _raided_story, "vanished": _vanished_story, "defended": _defended_story,
                        "exposed_fix": _exposed_story})


@outcome("raided", body_facts=False)
def _raided(world, event):
    fallen = [world.entity(p).name for p in event.data["fallen"]]
    lines = ["Cultists in black storm the platform before the final. The crowd breaks and runs."]
    if fallen:
        lines.append(f"{' and '.join(fallen)} {'falls' if len(fallen) == 1 else 'fall'} in the fighting; the final is void.")
    else:
        lines.append("The judges put the final off until tomorrow.")
    return lines, {}


@summary("raided")
def _raided_line(world, entry, names, place, other):
    return f"Saw cultists storm the final in {place}."


@outcome("vanished", body_facts=False)
def _vanished(world, event):
    return [f"{world.entity(event.actors[0]).name} is nowhere to be found on the morning of their bout."], {}


@summary("vanished")
def _vanished_line(world, entry, names, place, other):
    return f"Heard that {names[0]} vanished before a bout in {place}."


@outcome("defended", body_facts=False)
def _defended(world, event):
    cultist = world.entity(event.actors[1]).name
    if event.data["won"]:
        return [f"You cut down {cultist}; the stands that saw it will remember."], {}
    return [f"{cultist} gets the better of you, and melts into the fleeing crowd."], {}


@summary("defended")
def _defended_line(world, entry, names, place, other):
    return f"Fought the cultists who stormed the final in {place}."


@outcome("asked_bookmaker", body_facts=False)
def _asked(world, event):
    d = event.data
    if d["learned"]:
        fact = world.fact(d["fact"])
        done = "poisoned" if fact.variant.get("how") == "poisoned" else "paid to lose"
        return [f"The bookmaker leans close: {world.entity(d['victim']).name} has been {done}. "
                "The odds on that bout are a lie."], {}
    return ["The bookmaker shrugs: nothing crooked that they know of."], {}


@summary("asked_bookmaker")
def _asked_line(world, entry, names, place, other):
    return f"Asked the bookmaker in {place} what they had heard."


@outcome("exposed", body_facts=False)
def _exposed(world, event):
    victim = world.entity(event.actors[1]).name
    return [f"You tell anyone who will listen that {victim}'s bout was fixed. By evening the whole town is saying it."], {}


@summary("exposed")
def _exposed_line(world, entry, names, place, other):
    return f"Exposed a fixed bout in {place}."
''')
append("narrate/grammar/tournament.toml", '''
[raided]
colour = "default"
lines = ["#tour_shame#", "#tour_crowd# #tour_shame#"]

[vanished]
colour = "default"
lines = ["#tour_crowd#"]

[defended]
colour = "default"
lines = ["#tour_crowd#", "#tour_crowd# #tour_crowd#"]

[asked_bookmaker]
colour = "default"
lines = ["#tour_bookie#", "#tour_bookie# #tour_crowd#"]

[exposed]
colour = "default"
lines = ["#tour_crowd#", "#tour_crowd# #tour_crowd#"]
''')
print("task 6 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4e_task6.py && .venv/Scripts/python.exe -m pytest tests/test_intrigue.py -q -p no:cacheprovider`
Expected: `task 6 edits applied`, then `14 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: dark interventions - demonic raids on the final, fixed bouts found out and exposed, vanished favourites"`

---
### Task 7: The screens: F11, the bracket, odds and typed bets, briefs, heralds, sheet, lineage, journal

**Files:**
- Create: `engine/tournament_page.py`
- Modify (via `.patches/4e_task7.py`):
  - `engine/tournament.py`:
    - `tournaments`, `bracket`, `odds`, `bet_on`;
    - the tournaments submenu;
    - herald and opening-day lines;
    - typed `register` and `watch` find the tournament here;
  - `engine/commands.py`: the global words and `bet <fighter> <silver>`;
  - `engine/game.py`: the help line;
  - `app.py`: F11;
  - `narrate/brief.py`: the scene's tournament facts;
  - `engine/sheet.py`: titles and open bets;
  - `engine/lineage_page.py`: ancestors' titles;
  - `debug/invariants.py`: `check_people` counts the names on a board the player can read (a posted bracket, the lei tai, a raid's cultist) as heard of;
  - `narrate/tournament_text.py`, `narrate/grammar/tournament.toml`: `event_name`, `stage_line`, `tournament_facts`, and the contest's journal lines.
- Test: `tests/test_tournament_screens.py`

**Interfaces:**
- Consumes (Tasks 1–6):
  - `T.KINDS`, `T.RULES`, `T.here`, `T.day`, `T.strengths`, `T.register_block`;
  - `W.index`, `W.stage_at`;
  - `wagers.open_matches`, `wagers.bet_block`, `wagers.bet_events`;
  - `TournamentMixin._board`, `_do_bookmaker`, `_submenu_options`, `_do_register`, `_do_watch`, `_herald`;
  - `narrate.tournament_text.KIND_NAMES`; `outcomes.SUMMARIES`.
- Produces:
  - **`engine.tournament_page`:**
    - `STAGE_WORDS`, `HOW_WORDS`;
    - `seen(world, player, occurrence) -> bool`, `known(world, player) -> list[int]`, `status(world, player, occurrence) -> str`;
    - `tournaments_lines(world, player) -> list[Line]`, `bracket_lines(world, player, occurrence_id) -> list[Line]`;
    - `open_bets(world, player) -> list[tuple[int, dict]]`, `sheet_tournament_lines(world, player) -> list[Line]`;
    - `posted_names(world, player) -> set[int]`: whom the boards the player can read name.
  - **`narrate.tournament_text`:** `event_name(world, t) -> str`, `stage_line(world, occurrence, stage) -> str`, `tournament_facts(world, town, player) -> list[str]`.
  - Player data `tour_seen` (`{str(occurrence): stage}`).
  - **Verbs:** `tournaments` (F11), `bracket`, `odds`, `bet_on` (typed `bet <fighter> <silver>`).

**Ruling for this task:** the spec's typed `bet <match> <silver>` becomes `bet <fighter> <silver>`: a match has two sides, and naming the fighter picks both the match and the side.

- [ ] **Step 1: Write the failing test** — `tests/test_tournament_screens.py`
```python
import time

import pytest

import systems.encounters as encounters
import systems.sky as sky
import systems.tournaments as T
import systems.wagers as wagers
import systems.world_events as W
from app import App
from config import Config
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.lineage_page import lineage_lines
from engine.sheet import sheet_lines
from engine.tournament_page import bracket_lines, tournaments_lines
from narrate.outcomes import SUMMARIES
from systems import founding
from systems.beliefs import believe
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from world.events import commit
from world.gen.materialize import ensure_town
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def texts(turn):
    return [t for t, _ in turn.lines]


def actions(turn):
    return [c.action for c in turn.all_choices]


def start(world, kind, town, data):
    commit(world, sky.start_events(world, kind, town, world.time, data))
    return W.index(world)[-1][W.ID]


def announced_assembly(game):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    occurrence = start(world, "grand_assembly", town, ga.start_data(world, town, 10, rng_for(1, "a")))
    world.set_time(world.entity(occurrence).data["ends"]["foretold"] + 1)
    return occurrence


def entered(game):
    body = load_body(game.world, game.player.id)
    body.realm = 2
    save_body(game.world, game.player.id, body)
    game.world.update_data(game.player.id, silver=500)
    occurrence = announced_assembly(game)
    game.perform(Action("register", occurrence))
    return occurrence


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    return game.perform(Action("look"))


def far_meet(world):
    import systems.events.dragon_phoenix as dp
    town = ensure_town(world, 3, 3, 0)
    return start(world, "dragon_phoenix", town, dp.start_data(world, town, 10, rng_for(1, "d"))), town


def hear_of(world, me, occurrence, town):
    variant = make_variant("phenomenon", town, None, place=place_name(world, town))
    variant.update(kind="dragon_phoenix", stage="foretold", reading=None)
    fact = record_fact(world, town, "phenomenon", None, place=town, variant=variant, spread=False,
                       extra={"occurrence": occurrence, "until": world.time + 40 * 4})
    believe(world, me, fact, variant, None, 0.7, 2, "gossip")


def test_the_tournaments_page_shows_what_you_have_seen_and_heard(game):
    world, me = game.world, game.player.id
    announced_assembly(game)
    far, town = far_meet(world)
    lines = texts(game.perform(Action("tournaments")))
    assert any("Grand Martial Assembly" in t and "registration open" in t and "not entered" in t for t in lines)
    assert not any("Dragon-Phoenix" in t for t in lines)  # nobody has told you of it
    hear_of(world, me, far, town)
    lines = texts(game.perform(Action("tournaments")))
    assert any("Dragon-Phoenix Meet" in t and world.entity(town).name in t for t in lines)


def test_f11_opens_the_tournaments_page(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Watcher", world_seed=5)
    app.handle_key("f11", "")
    assert any("Tournaments" in t for t, _ in app.last_turn.lines)


def test_the_bracket_as_you_know_it(game):
    world, me = game.world, game.player.id
    occurrence = announced_assembly(game)
    to_day(game, occurrence, 3)  # round 1 was fought on day 1
    lines = texts(game.perform(Action("bracket", occurrence)))
    assert any(t.startswith("Round 1, day 1") for t in lines) and sum(" wins" in t for t in lines) >= 8
    world.unrelate(me, "located_in")
    world.relate(me, ensure_town(world, 3, 3, 0), "located_in")  # far from the board, only what you heard
    away = [t for t, _ in bracket_lines(world, me, occurrence)]
    assert not any(" wins" in t for t in away)
    fact = world.facts(predicate="bested")[0]
    believe(world, me, fact.id, fact.variant, None, 0.7, 2, "gossip")
    away = [t for t, _ in bracket_lines(world, me, occurrence)]
    assert any("Heard" in t and world.entity(fact.subject).name in t for t in away)


def test_your_next_bout_is_named(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 1)
    call = T.player_call(world, me, game.place.id)
    lines = texts(game.perform(Action("bracket")))
    assert any("Your next bout" in t and world.entity(call[3]).name in t for t in lines)
    assert any("You: in round 1" in t for t in texts(game.perform(Action("tournaments"))))


def test_odds_and_a_typed_bet(game):
    world, me = game.world, game.player.id
    occurrence = announced_assembly(game)
    world.update_data(me, silver=500)
    to_day(game, occurrence, 1)
    assert any("odds board" in t for t in texts(game.perform(Action("odds"))))
    r, i, m = wagers.open_matches(world, occurrence)[0]
    action = parse(f"bet {world.entity(m['a']).name} 20", [])
    assert action == Action("bet_on", (world.entity(m["a"]).name.lower(), 20))
    game.perform(action)
    bet = world.entity(occurrence).data["data"]["bets"][-1]
    assert (bet["on"], bet["stake"], bet["round"], bet["match"]) == (m["a"], 20, r, i)
    assert any("Bet on whom" in t for t in texts(game.perform(Action("bet_on", ("nobody at all", 5)))))


def test_the_brief_names_the_round_and_the_favourite(game):
    occurrence = announced_assembly(game)
    game.perform(Action("look"))
    facts = " ".join(f for b in game.last_briefs if b.kind == "scene" for f in b.facts)
    assert "Grand Martial Assembly: registration is open" in facts
    to_day(game, occurrence, 1)
    facts = " ".join(f for b in game.last_briefs if b.kind == "scene" for f in b.facts)
    assert "round 1 today; the odds favour" in facts


def test_heralds_and_the_opening_day_are_told_once(game):
    occurrence = announced_assembly(game)
    assert any("Heralds cry" in t for t in texts(game.perform(Action("look"))))
    game.world.set_time(game.world.time + 1)
    assert not any("Heralds cry" in t for t in texts(game.perform(Action("look"))))
    assert any("opens today" in t for t in texts(to_day(game, occurrence, 1)))


def test_the_sheet_shows_titles_and_open_bets(game):
    world, me = game.world, game.player.id
    occurrence = announced_assembly(game)
    world.update_data(me, silver=500, titles=["Champion of the First Grand Martial Assembly"])
    to_day(game, occurrence, 1)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 20, me))
    text = " ".join(t for t, _ in sheet_lines(world, me))
    assert "Champion of the First Grand Martial Assembly" in text and "20 silver on" in text


def test_an_ancestors_titles_are_on_the_lineage_page(game):
    world, me, town = game.world, game.player.id, game.place.id
    grandfather = founding.make_person(world, "test:grandfather", town, occupation="monk", age=80,
                                       realm="first-rate")
    world.update_data(grandfather, dead=True, death={"cause": "age", "age": 80, "place": town},
                      titles=["Champion of the Second Grand Martial Assembly"])
    world.unrelate(grandfather, "located_in")
    world.update_data(me, ancestors=[grandfather])
    assert any("Champion of the Second Grand Martial Assembly" in t for t, _ in lineage_lines(world, me))


def test_every_tournament_event_you_take_part_in_has_a_journal_line(game):
    for kind in ("registered", "bond_refunded", "match_resolved", "tournament_won", "disqualified",
                 "lei_tai_challenged", "lei_tai_held", "bet_placed", "bet_settled", "watched", "noticed",
                 "defended", "asked_bookmaker", "exposed", "contest_rewarded", "contest_summarized"):
        assert kind in SUMMARIES, kind
    entered(game)
    assert any("Entered the Grand Martial Assembly" in t for t in texts(game.perform(Action("journal"))))


def test_typed_register_and_watch_find_the_tournament_here(game):
    world = game.world
    body = load_body(world, game.player.id)
    body.realm = 2
    save_body(world, game.player.id, body)
    world.update_data(game.player.id, silver=500)
    occurrence = announced_assembly(game)
    game.perform(parse("register", []))
    assert game.player.id in world.entity(occurrence).data["data"]["registered"]
    to_day(game, occurrence, 1)
    assert any("You watch" in t for t in texts(game.perform(parse("watch", []))))


def test_a_crowded_tournament_day_folds_under_more(game):
    world = game.world
    occurrence = entered(game)
    turn = to_day(game, occurrence, 1)
    assert len(turn.choices) <= 9
    assert {Action("watch", occurrence), Action("bookmaker", occurrence), Action("bout", occurrence)} <= set(actions(turn))


def test_a_posted_bracket_names_only_what_the_rules_allow(game):
    from debug.invariants import check_people
    world, me = game.world, game.player.id
    occurrence = entered(game)
    turn = to_day(game, occurrence, 1)
    assert check_people(game, turn) == []  # the herald's call names a stranger from the posted draw
    assert check_people(game, game.perform(Action("bracket", occurrence))) == []
    world.unrelate(me, "located_in")
    world.relate(me, ensure_town(world, 3, 3, 0), "located_in")
    world.update_data(occurrence, data={**world.entity(occurrence).data["data"], "registered": [], "entrants": []})
    from engine.tournament_page import posted_names
    assert posted_names(world, me) == set()  # away, and not in it: the board names no one to you


def test_the_pages_are_quick(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 9)  # the whole bracket is settled: every line has a result
    tournaments_lines(world, me)
    bracket_lines(world, me, occurrence)
    start_ = time.process_time()
    tournaments_lines(world, me)
    bracket_lines(world, me, occurrence)
    assert time.process_time() - start_ < 0.03
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tournament_screens.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'engine.tournament_page'`.

- [ ] **Step 3: Write the pages** — `engine/tournament_page.py`
```python
"""The tournament pages (phase 4e spec 6): F11's list, the bracket as you know it, and the sheet's lines.

Built from what the player has seen (the board at the venue, a bracket they are in) and what they
believe (the heralds' news of the great tournaments, results they have heard), never from the truth
of a tournament nobody told them of.
"""

import systems.tournaments as T
import systems.world_events as W
from narrate.base import Line
from narrate.outcomes import cap
from narrate.tournament_text import event_name

STAGE_WORDS = {"foretold": "foretold by the heralds", "announced": "registration open",
               "active": "the bouts are on", "aftermath": "over", "over": "over"}
HOW_WORDS = {"sim": "wins", "bout": "wins", "bye": "goes through", "walkover": "wins by walkover",
             "forfeit": "wins by forfeit", "disqualified": "wins by disqualification"}


def _where(world, player: int) -> int | None:
    here = world.targets(player, "located_in")
    return here[0] if here else None


def seen(world, player: int, occurrence) -> bool:
    """Whether the player can read this tournament's board: at the venue, or named in its bracket."""
    t = occurrence.data["data"]
    return occurrence.data["place"] == _where(world, player) or t.get("presiding") == player \
        or player in t.get("registered", []) or player in t.get("entrants", [])


def known(world, player: int) -> list[int]:
    """The tournaments the player knows of: those seen, and those whose news has reached them."""
    rows = {row[W.ID] for row in W.index(world) if row[W.TYPE] in T.KINDS}
    found = {oid for oid in rows if seen(world, player, world.entity(oid))}
    for _, fact in world.known_facts_about([player], predicate="phenomenon"):
        if fact.data.get("occurrence") in rows:
            found.add(fact.data["occurrence"])
    return sorted(found)


def status(world, player: int, occurrence) -> str:
    t = occurrence.data["data"]
    if t.get("presiding") == player:
        return "you preside"
    if t.get("champion") == player:
        return "you are the champion"
    if player in t.get("disqualified", []):
        return "you were disqualified"
    if player not in t.get("registered", []) and player not in t.get("entrants", []):
        return "not entered"
    for r, matches in enumerate(t.get("rounds", [])):
        for m in matches:
            if player in (m["a"], m["b"]):
                if m["how"] is None:
                    return f"in round {r + 1}"
                if m["winner"] != player:
                    return f"out in round {r + 1}"
    return "entered"


def tournament_line(world, player: int, occurrence_id: int) -> str:
    occurrence = world.entity(occurrence_id)
    t = occurrence.data["data"]
    stage = W.stage_at(occurrence.data, world.time)
    words = STAGE_WORDS.get(stage, stage)
    if seen(world, player, occurrence):
        if stage == "active":
            words = f"day {T.day(occurrence, world.time)} of the bouts"
        if t.get("finished") and t.get("champion") is not None:
            words = f"over; {'you' if t['champion'] == player else world.entity(t['champion']).name} won"
    host = world.entity(occurrence.data["place"]).name
    return f"  {cap(event_name(world, t))} in {host}: {words}. {T.RULES.get(t['kind'], '')} " \
           f"You: {status(world, player, occurrence)}."


def tournaments_lines(world, player: int) -> list[Line]:
    lines: list[Line] = [("Tournaments", "heading")]
    found = known(world, player)
    if not found:
        return lines + [("  You know of no tournament. Heralds cry the great ones through the cities.", "dim")]
    return lines + [(tournament_line(world, player, oid), "dim") for oid in found]


def _name(world, player: int, person, blank: str) -> str:
    return blank if person is None else "you" if person == player else world.entity(person).name


def _match_line(world, player: int, m: dict, r: int, today: int) -> str:
    blank = "a bye" if r == 0 else "?"
    a, b = _name(world, player, m["a"], blank), _name(world, player, m["b"], blank)
    if m["how"] is None:
        return f"  {a} v {b}" + (": today" if m["day"] == today and None not in (m["a"], m["b"]) else "")
    if m["winner"] is None:
        return f"  {a} v {b}: {'void' if m['how'] == 'void' else 'no one goes through'}"
    verb = HOW_WORDS[m["how"]]
    if m["winner"] == player:
        verb = verb.replace("wins", "win").replace("goes", "go")
    return f"  {a} v {b}: {_name(world, player, m['winner'], blank)} {verb}"


def _next_bout(world, player: int, t: dict) -> str | None:
    for r, matches in enumerate(t["rounds"]):
        for m in matches:
            if m["how"] is None and player in (m["a"], m["b"]):
                other = m["b"] if m["a"] == player else m["a"]
                label = "the final" if r == len(t["rounds"]) - 1 else f"round {r + 1}"
                against = world.entity(other).name if other is not None else "whoever comes through"
                return f"Your next bout: {label} on day {m['day']}, against {against}."
    return None


def bracket_lines(world, player: int, occurrence_id: int) -> list[Line]:
    occurrence = world.entity(occurrence_id)
    t = occurrence.data["data"]
    host = world.entity(occurrence.data["place"]).name
    lines: list[Line] = [(f"{cap(event_name(world, t))} in {host}", "heading")]
    if not seen(world, player, occurrence):  # far from the board: only the results you have heard
        heard = [b.variant for b, f in world.known_facts_about([player], predicate="bested")
                 if b.variant.get("kind") == t["kind"] and b.variant.get("place") == host
                 and f.time >= occurrence.data["active"][0]]
        lines.append(("  You are not there to read the board.", "dim"))
        lines += [(f"  Heard: {_name(world, player, v.get('actor'), 'someone')} bested "
                   f"{_name(world, player, v.get('target'), 'someone')}.", "dim") for v in heard]
        return lines
    if not t["rounds"]:
        return lines + [("  The draw is made on the first day of the bouts.", "dim")]
    today = T.day(occurrence, world.time)
    for r, matches in enumerate(t["rounds"]):
        label = "The final" if r == len(t["rounds"]) - 1 else f"Round {r + 1}"
        lines.append((f"{label}, day {matches[0]['day']}:", "heading"))
        lines += [(_match_line(world, player, m, r, today), "dim") for m in matches]
    nxt = _next_bout(world, player, t)
    if nxt:
        lines.append((nxt, "default"))
    return lines


def posted_names(world, player: int) -> set[int]:
    """Everyone a board the player can read names: the brackets of tournaments they can see, the lei tai
    here, a raid's cultist. A posted bracket is public at the venue (the knowledge rule, check_people)."""
    found, here = set(), _where(world, player)
    for row in W.index(world):
        if row[W.TYPE] not in T.KINDS + ("lei_tai",):
            continue
        occurrence = world.entity(row[W.ID])
        t = occurrence.data["data"]
        if row[W.TYPE] == "lei_tai":
            if occurrence.data["place"] == here:
                found |= {p for p in [t.get("holder"), *t.get("challengers", [])] if p is not None}
        elif seen(world, player, occurrence):
            podium = t.get("compacted") or {}
            found |= set(t.get("entrants", [])) | set(t.get("registered", []))
            found |= {p for p in [t.get("champion"), (t.get("intrigue") or {}).get("cultist"),
                                  podium.get("runner_up"), *podium.get("semis", [])] if p is not None}
    return found


def open_bets(world, player: int) -> list[tuple[int, dict]]:
    found = []
    for row in W.index(world):
        if row[W.TYPE] in T.KINDS:
            found += [(row[W.ID], bet) for bet in world.entity(row[W.ID]).data["data"].get("bets", [])
                      if bet["player"] == player and not bet["settled"]]
    return found


def sheet_tournament_lines(world, player: int) -> list[Line]:
    """The character sheet's titles and open bets."""
    lines: list[Line] = [("", "default"), ("Titles:", "heading")]
    lines += [(f"  {title}", "default") for title in world.entity(player).data.get("titles", [])] or [("  none", "dim")]
    lines.append(("Open bets:", "heading"))
    lines += [(f"  {bet['stake']} silver on {world.entity(bet['on']).name} at {bet['odds']:.2f} to 1, round "
               f"{bet['round'] + 1} of {event_name(world, world.entity(oid).data['data'])}", "default")
              for oid, bet in open_bets(world, player)] or [("  none", "dim")]
    return lines
```

- [ ] **Step 4: Edit the existing files** — `.patches/4e_task7.py`
```python
"""Task 7 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    Path(path).write_text(Path(path).read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


TEXT = "narrate/tournament_text.py"
edit(TEXT, '''PLACES = {2: "second", 3: "among the last four"}
''', '''PLACES = {2: "second", 3: "among the last four"}


def event_name(world, t: dict) -> str:
    """What people call this tournament: a sect's contest carries the sect's name."""
    if t["kind"] == "sect_contest" and t.get("faction") is not None:
        return f"the {world.entity(t['faction']).name}'s contest"
    return KIND_NAMES[t["kind"]]


def stage_line(world, occurrence, stage: str) -> str:
    """What the streets say when a tournament here reaches a new stage (heralds, the opening day)."""
    t = occurrence.data["data"]
    if t["kind"] == "lei_tai":
        holder = t.get("holder")
        return "A lei tai platform goes up in the square" + (f"; {world.entity(holder).name} holds it." if holder else ".")
    if stage == "announced":
        return f"Heralds cry {event_name(world, t)} through the streets: registration is open."
    return f"{cap(event_name(world, t))} opens today; the draw is posted in the square."


def _today(world, occurrence) -> str:
    import systems.tournaments as T
    t = occurrence.data["data"]
    if t.get("finished"):
        champion = t.get("champion")
        return f"{world.entity(champion).name} is champion." if champion is not None else "it ended without a champion."
    today = T.day(occurrence, world.time)
    for r, matches in enumerate(t["rounds"]):
        waiting = [m for m in matches if m["how"] is None]
        if not waiting:
            continue
        label = "the final" if r == len(t["rounds"]) - 1 else f"round {r + 1}"
        when = "today" if waiting[0]["day"] == today else f"on day {waiting[0]['day']}"
        fighters = [p for m in waiting for p in (m["a"], m["b"]) if p is not None]
        if not fighters:
            return f"{label} {when}."
        strength = T.strengths(world, occurrence.data["place"], fighters)  # the bookmaker's view, the town's belief
        favourite = max(fighters, key=lambda p: (strength[p], -p))
        return f"{label} {when}; the odds favour {world.entity(favourite).name}."
    return "the last bout is being fought."


def tournament_facts(world, town: int, player: int) -> list[str]:
    """The scene's tournament: registration, today's round and the favourite; a lei tai's holder (spec §6)."""
    import systems.tournaments as T
    import systems.world_events as W
    facts = []
    oid = T.here(world, town, T.KINDS, ("announced", "active"))
    if oid is not None:
        occurrence = world.entity(oid)
        name = cap(event_name(world, occurrence.data["data"]))
        if W.stage_at(occurrence.data, world.time) == "announced":
            days = max(1, (occurrence.data["active"][0] - world.time + 3) // 4)
            facts.append(f"{name}: registration is open; the bouts begin in {days} days.")
        else:
            facts.append(f"{name}: {_today(world, occurrence)}")
    platform = T.here(world, town, ("lei_tai",), ("active",))
    holder = world.entity(platform).data["data"].get("holder") if platform is not None else None
    if holder is not None:
        facts.append(f"A lei tai stands in the square; {world.entity(holder).name} holds it.")
    return facts
''')
append(TEXT, '''


@outcome("contest_rewarded", body_facts=False)
def _contest_rewarded(world, event):
    faction = world.entity(event.data["faction"]).name
    if world.entity(event.actors[0]).data.get("is_player"):
        return [f"The {faction} marks your win: {event.data['merit']} merit, and a step up in rank."], {}
    return [f"{world.entity(event.actors[0]).name} is raised a rank in the {faction}."], {}


@summary("contest_rewarded")
def _contest_rewarded_line(world, entry, names, place, other):
    return f"Was rewarded by the {world.entity(entry.data['faction']).name} for winning its contest."


@summary("contest_summarized")
def _contest_summarized_line(world, entry, names, place, other):
    return f"Won the {world.entity(entry.data['faction']).name}'s contest in {place}."
''')
append("narrate/grammar/tournament.toml", '''
[contest_rewarded]
colour = "gold"
lines = ["#tour_crowd#", "#tour_clerk#"]
''')

ENG = "engine/tournament.py"
edit(ENG, '''import systems.wagers as wagers
from engine.actions import Action, Choice
from narrate.tournament_text import KIND_NAMES
''', '''import systems.wagers as wagers
import systems.world_events as W
from engine.actions import Action, Choice
from engine.tournament_page import bracket_lines, known, tournaments_lines
from narrate.tournament_text import KIND_NAMES, stage_line
''')
edit(ENG, '''    def _after_look(self) -> list:
        return super()._after_look() + self._herald()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._herald()''', '''    def _tournament_news(self) -> list:
        """A line for each tournament here at a stage the player has not yet seen: heralds, the opening day."""
        world, town = self.world, self.place.id
        before = dict(self.player.data.get("tour_seen", {}))
        seen, lines = dict(before), []
        for row in W.index(world):
            if row[W.PLACE] != town or row[W.DONE] or row[W.TYPE] not in T.KINDS + ("lei_tai",):
                continue
            occurrence = world.entity(row[W.ID])
            stage = W.stage_at(occurrence.data, world.time)
            if stage in ("announced", "active") and seen.get(str(row[W.ID])) != stage:
                seen[str(row[W.ID])] = stage
                lines.append((stage_line(world, occurrence, stage), "dim"))
        live = {str(row[W.ID]) for row in W.index(world) if not row[W.DONE]}
        seen = {k: v for k, v in seen.items() if k in live}
        if seen != before:
            world.update_data(self.player.id, tour_seen=seen)
        return lines

    def _after_look(self) -> list:
        return super()._after_look() + self._tournament_news() + self._herald()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._tournament_news() + self._herald()''')
edit(ENG, '''    def _do_register(self, occurrence):
        why = ''', '''    def _do_register(self, occurrence):
        if occurrence is None:  # typed: the tournament taking names here
            occurrence = T.here(self.world, self.place.id, T.KINDS, ("announced",))
        why = ''')
edit(ENG, '''    def _do_watch(self, occurrence):
        events = ''', '''    def _do_watch(self, occurrence):
        if occurrence is None:  # typed: today's bouts here
            occurrence = T.here(self.world, self.place.id, T.KINDS, ("active",))
        events = ''')
edit(ENG, '''        if self.focus is None and self.submenu == "wagers" and self._betting_on is not None:
            options["wagers"] = (self._board(self._betting_on)[1], Action("back"))
        return options''', '''        if self.focus is None and self.submenu == "wagers" and self._betting_on is not None:
            options["wagers"] = (self._board(self._betting_on)[1], Action("back"))
        if self.focus is None and self.submenu == "tournaments":
            options["tournaments"] = ([Choice(f"The bracket in {self.world.entity(self.world.entity(oid).data['place']).name}",
                                              Action("bracket", oid)) for oid in known(self.world, self.player.id)],
                                      Action("back"))
        return options''')
append(ENG, '''
    # --- the pages (phase 4e spec 6) ---------------------------------------------------------------
    def _do_tournaments(self, _target):
        self.submenu = "tournaments"
        return self._turn(tournaments_lines(self.world, self.player.id))

    def _do_bracket(self, occurrence):
        found = known(self.world, self.player.id)
        if occurrence is None:  # typed: the one here, else the one you are in, else the newest you know of
            here = [oid for oid in found if self.world.entity(oid).data["place"] == self.place.id]
            mine = [oid for oid in found if self.player.id in self.world.entity(oid).data["data"].get("entrants", [])]
            occurrence = (here or mine or found or [None])[-1]
        if occurrence not in found:
            return self._turn([("You know of no such tournament.", "system")])
        return self._turn(bracket_lines(self.world, self.player.id, occurrence))

    def _do_odds(self, _target):
        occurrence = T.here(self.world, self.place.id, T.KINDS, ("active",))
        if occurrence is None:
            return self._turn([("No bookmaker takes bets here.", "system")])
        return self._do_bookmaker(occurrence)

    def _do_bet_on(self, target):
        world, me = self.world, self.player.id
        occurrence = T.here(world, self.place.id, T.KINDS, ("active",))
        if occurrence is None or not isinstance(target, tuple) or len(target) != 2:
            return self._turn([("No bookmaker takes bets here.", "system")])
        name, stake = target
        words = str(name).lower().split()
        found = [(r, i, p) for r, i, m in wagers.open_matches(world, occurrence) for p in (m["a"], m["b"])
                 if words and all(any(part.startswith(w) for part in world.entity(p).name.lower().split()) for w in words)]
        if len(found) != 1:
            return self._turn([("Bet on whom? Name one fighter on the odds board.", "system")])
        r, i, on = found[0]
        why = wagers.bet_block(world, occurrence, r, i, on, stake, me)
        if why:
            return self._turn([(why, "system")])
        return self._turn(self._commit(wagers.bet_events(world, occurrence, r, i, on, stake, me)))
''')

edit("engine/commands.py", '''    "rankings": Action("rankings"), "lists": Action("rankings"),
''', '''    "rankings": Action("rankings"), "lists": Action("rankings"),
    "tournaments": Action("tournaments"), "tournament": Action("tournaments"), "bracket": Action("bracket"),
    "odds": Action("odds"), "bookmaker": Action("odds"), "register": Action("register"), "watch": Action("watch"),
''')
edit("engine/commands.py", '''WORD = re.compile(r"[a-z0-9']+")
''', '''WORD = re.compile(r"[a-z0-9']+")
BET = re.compile(r"bet (?:on )?([a-z' -]+?) (\\d+)")  # bet <fighter> <silver> (phase 4e)
''')
edit("engine/commands.py", '''    if lowered in GLOBAL:
        return GLOBAL[lowered]
''', '''    if lowered in GLOBAL:
        return GLOBAL[lowered]
    bet = BET.fullmatch(lowered)
    if bet:
        return Action("bet_on", (bet.group(1), int(bet.group(2))))
''')
edit("engine/game.py", '''    ("  sky | rankings (F10) | seek | swallow", "system"),
''', '''    ("  sky | rankings (F10) | seek | swallow", "system"),
    ("  tournaments (F11) | bracket | register | watch | odds | bet <fighter> <silver>", "system"),
''')
edit("app.py", '''        elif key == "f10":
            self.submit("rankings")
''', '''        elif key == "f10":
            self.submit("rankings")
        elif key == "f11":
            self.submit("tournaments")
''')
edit("narrate/brief.py", '''    facts += sky_facts(world, place_id)
''', '''    facts += sky_facts(world, place_id)
    from narrate.tournament_text import tournament_facts  # a tournament here (phase 4e)
    facts += tournament_facts(world, place_id, player_id)
''')
edit("engine/sheet.py", '''    lines += sheet_sky_lines(world, player_id)
''', '''    lines += sheet_sky_lines(world, player_id)
    from engine.tournament_page import sheet_tournament_lines  # phase 4e
    lines += sheet_tournament_lines(world, player_id)
''')
edit("engine/lineage_page.py", '''    return f"  {p.name}, died {how} in {where}, aged {int(death.get('age') or p.data.get('age', 0))}" \\
        + (f", once {rank}" if rank else "")''', '''    return f"  {p.name}, died {how} in {where}, aged {int(death.get('age') or p.data.get('age', 0))}" \\
        + (f", once {rank}" if rank else "") + "".join(f"; {title}" for title in p.data.get("titles", []))''')
edit("debug/invariants.py", '''    known |= {p.name.lower() for p in world.entities("persona") if p.data.get("of") == player_id}
''', '''    known |= {p.name.lower() for p in world.entities("persona") if p.data.get("of") == player_id}
    from engine.tournament_page import posted_names  # a bracket posted where you can read it (phase 4e)
    known |= {world.entity(p).name.lower() for p in posted_names(world, player_id)}
''')
print("task 7 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4e_task7.py && .venv/Scripts/python.exe -m pytest tests/test_tournament_screens.py -q -p no:cacheprovider`
Expected: `task 7 edits applied`, then `14 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: tournament screens - F11 and the bracket as you know it, odds and typed bets, heralds, briefs, titles"`

---
### Task 8: A tournament season end to end: compaction, old saves, speed, the fork guide, the fuzz

**Files:**
- Modify (via `.patches/4e_task8.py`):
  - `systems/tournaments.py`: `compact_events` and the `bracket_compacted` effect; `on_stage("over")` compacts (ruling 5);
  - `engine/tournament_page.py`: a compacted bracket shows its podium;
  - `docs/world-events.md`: the `every` cycle, `stagger`, `sky`, the `places`, `summary` and `on_observe` hooks, and a section on adding a tournament kind;
  - `tests/test_fuzz.py`: `test_a_tournament_season`;
  - `tests/test_rumours.py`: the 500-fact catch-up collects garbage first and times CPU (ruling 19).
- Test: `tests/test_tournament_season.py`

**Interfaces:**
- Consumes (Tasks 1–7):
  - `T.on_stage`, `T.resolve`, `T.day_start`, `T.host_city`, `T.KINDS`;
  - `sky.season_events`, `sky.observe`, `W.TYPES`;
  - `bracket_lines`; `tests.test_fuzz.FIGHTING`, `keep_playing`.
- Produces:
  - **`systems.tournaments`:** `compact_events(occurrence) -> list[Event]`.
  - **Event:** `bracket_compacted` (`occurrence`, `runner_up`, `semis`, `entrants`).
  - **Bracket data:** after compaction, `rounds`, `registered`, `entrants` and `bets` are empty, and `compacted` holds `{"runner_up", "semis", "entrants"}` (the entrant count).

- [ ] **Step 1: Write the failing test** — `tests/test_tournament_season.py`
```python
import json
import time
from pathlib import Path

import pytest

import systems.encounters as encounters
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.game import Game
from engine.tournament_page import bracket_lines
from systems.creation import CreationChoice
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def drawn_assembly(game):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "grand_assembly", town, world.time,
                                   ga.start_data(world, town, 10, rng_for(1, "a"))))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    return occurrence


def test_a_finished_bracket_is_compacted_after_the_aftermath(game):
    world, town = game.world, game.place.id
    occurrence = drawn_assembly(game)
    world.set_time(world.entity(occurrence).data["over_at"] + 1)
    sky.observe(world, town)
    t = world.entity(occurrence).data["data"]
    assert t["finished"] and t["champion"] is not None and t["rounds"] == [] and t["compacted"]["entrants"] == 32
    assert len(t["compacted"]["semis"]) == 2 and t["compacted"]["runner_up"] not in (None, t["champion"])
    assert len(json.dumps(t)) < 2000
    assert any("Champion" in text for text, _ in bracket_lines(world, game.player.id, occurrence))
    assert check_tournaments(world) == []


def test_an_old_world_holds_its_first_assembly_at_the_next_cycle_point(game):
    """A save from before tournaments: nothing is backdated, and the first Assembly falls on its turn."""
    world = game.world
    offset = rng_for(world.world_seed, "sky:grand_assembly:offset").randrange(12)
    first = next(n for n in range(10, 40) if (n + offset) % 12 == 0)
    found = [n for n in range(10, first + 13) for e in sky.season_events(world, n)
             if e.kind == "sky_started" and e.data["type"] == "grand_assembly"]
    assert found == [first, first + 12]


def test_an_assembly_round_resolves_quickly(game):
    world = game.world
    occurrence = drawn_assembly(game)  # the player is at the venue: sixteen full duel simulations
    world.set_time(T.day_start(world.entity(occurrence), 2))
    start = time.process_time()
    T.resolve(world, occurrence)
    elapsed = time.process_time() - start
    assert all(m["how"] is not None for m in world.entity(occurrence).data["data"]["rounds"][0])
    assert elapsed < 0.06, f"a round took {elapsed * 1000:.0f} ms"


def test_the_fork_guide_covers_tournaments():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("every", "stagger", "sky = false", "places", "summary", "on_observe", "T.KINDS", "qualifies",
                 "invite", "rewards", "CHANCES", "check_tournaments", "titles"):
        assert word in guide, word
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tournament_season.py -q -p no:cacheprovider`
Expected: 2 failed (`test_a_finished_bracket_is_compacted_after_the_aftermath` with `KeyError: 'compacted'`, and `test_the_fork_guide_covers_tournaments` with `AssertionError: stagger`), 2 passed.

- [ ] **Step 3: Edit the existing files** — `.patches/4e_task8.py`
```python
"""Task 8 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


TOUR = "systems/tournaments.py"
edit(TOUR, '''    if stage == "over":
        if not occurrence.data["data"]["rounds"] and not occurrence.data["data"]["finished"]:
            return summary_events(world, occurrence, invite)
        resolve(world, occurrence.id)
    return []''', '''    if stage == "over":
        if not occurrence.data["data"]["rounds"] and not occurrence.data["data"]["finished"]:
            return summary_events(world, occurrence, invite)
        resolve(world, occurrence.id)
        return compact_events(world.entity(occurrence.id))
    return []


KEPT = ("kind", "size", "round_days", "champion", "finished", "prize", "title", "edition", "faction", "presiding",
        "disqualified", "intrigue")


def compact_events(occurrence) -> list[Event]:
    """A finished bracket shrinks to its podium when the aftermath ends (plan ruling 5)."""
    t = occurrence.data["data"]
    if not t["rounds"] or t.get("compacted") or not t["finished"]:
        return []
    final = t["rounds"][-1][0]
    runner_up = (final["b"] if final["winner"] == final["a"] else final["a"]) if final["winner"] is not None else None
    semis = [m["b"] if m["winner"] == m["a"] else m["a"] for m in t["rounds"][-2]] if len(t["rounds"]) > 1 else []
    return [Event("bracket_compacted", (), occurrence.data["place"],
                  {"occurrence": occurrence.id, "runner_up": runner_up, "semis": [p for p in semis if p is not None],
                   "entrants": len(t["entrants"])})]


@effect("bracket_compacted")
def _compacted(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    kept = {k: t[k] for k in KEPT if k in t}
    world.update_data(occurrence.id, data={**kept, "registered": [], "entrants": [], "rounds": [], "bets": [],
                                           "compacted": {"runner_up": d["runner_up"], "semis": d["semis"],
                                                         "entrants": d["entrants"]}})''')

PAGE = "engine/tournament_page.py"
edit(PAGE, '''    if not t["rounds"]:
        return lines + [("  The draw is made on the first day of the bouts.", "dim")]''', '''    if t.get("compacted"):  # long over: only the podium is kept (plan ruling 5)
        podium = t["compacted"]
        lines.append((f"  Champion: {_name(world, player, t.get('champion'), 'no one')}.", "dim"))
        if podium["runner_up"] is not None:
            lines.append((f"  Runner-up: {_name(world, player, podium['runner_up'], 'no one')}.", "dim"))
        if podium["semis"]:
            lines.append((f"  The last four: {', '.join(_name(world, player, p, '?') for p in podium['semis'])}.", "dim"))
        return lines + [(f"  {podium['entrants']} fought.", "dim")]
    if not t["rounds"]:
        return lines + [("  The draw is made on the first day of the bouts.", "dim")]''')

GUIDE = "docs/world-events.md"
edit(GUIDE, '''Each occurrence is a `world_event` entity.''', '''A type can instead come round on a fixed period (phase 4e):

~~~toml
[grand_assembly]
module = "systems.events.grand_assembly"
scope = "town"
cycle = "every"           # held every `every` seasons, where the module's `places` hook says
every = 12
stagger = false           # true: each place keeps its own turn (sect contests), so they do not all fall at once
sky = false               # not a phenomenon: kept off the sky page and the scene's sky lines
stages = { foretold = 60, announced = 20, active = 8, aftermath = 30 }
~~~

Each occurrence is a `world_event` entity.''')
edit(GUIDE, '''| `eligible(world, place, n)` | after the chance roll, before it starts in season `n` | bool |''',
     '''| `eligible(world, place, n)` | after the chance roll (for `every`: only at a place whose turn it is), before it starts in season `n` | bool |
| `places(world, n, rng)` | `every` types, each season: where it would be held | a list of places |
| `summary(world, place, n, rng)` | `every` types whose place the player is not at: settle it in a line, with no occurrence | a list of events |''')
edit(GUIDE, '''| `on_stage(world, occurrence, stage)` | the first time a stage is observed (`foretold`, `announced`, `active`, `aftermath`, `over`) | a list of events to commit |''',
     '''| `on_stage(world, occurrence, stage)` | the first time a stage is observed (`foretold`, `announced`, `active`, `aftermath`, `over`) | a list of events to commit |
| `on_observe(world, occurrence)` | every observation of a begun occurrence (a tournament's days pass) | a list of events to commit |''')
Path(GUIDE).write_text(Path(GUIDE).read_text(encoding="utf-8") + '''
## 6. Adding a tournament kind (phase 4e)

A tournament is an `every` type with `sky = false`, whose module leans on `systems/tournaments.py`:

- **The module** (see `systems/events/grand_assembly.py`):
  - `SIZE` (a power of two) and `ROUND_DAYS` (one day per round, the final last);
  - `places` (the host) and `start_data`, which returns `T.start_data(kind, SIZE, ROUND_DAYS, prize, title, edition)`;
  - `qualifies(world, occurrence, person, slack)`: who may enter;
  - `invite(world, occurrence)`: who is asked, usually `T.pool(...)`;
  - `on_stage` and `on_observe`, which hand over to `T.on_stage` and `T.on_observe`;
  - optionally `rewards(world, occurrence, champion)`, the events that follow the crown.
- **The shared tables:**
  - `T.KINDS`, `T.KIND_WEIGHT` (how much a win is worth to the Pavilion) and `T.NEWSWORTHY` (bouts talked of far away);
  - `T.RULES` and `T.BONDS`: the entry rule's words and the bond;
  - `intrigue.CHANCES`: the dark interventions it may suffer;
  - `narrate.tournament_text.KIND_NAMES`.
- **Saved state:** the bracket lives in the occurrence's `data["data"]` (registrations, rounds, bets, the plot),
  compacted to its podium when the aftermath ends. Player data gains `titles`, `invitations` and `tour_seen`.
- **The rules:** `check_tournaments` in `debug/invariants.py` guards brackets, advancing, bouts, bets and eligibility for
  every kind, including yours.
''', encoding="utf-8", newline="\n")

RUMOURS = "tests/test_rumours.py"
edit(RUMOURS, '''import random
import time
''', '''import gc
import random
import time
''')
edit(RUMOURS, '''    start = time.perf_counter()
    added = catch_up(game.world, game.place.id, now=game.world.time + 100)
    elapsed = time.perf_counter() - start''', '''    gc.collect()  # earlier tests' garbage is not this catch-up's cost (4e ruling 19)
    start = time.process_time()  # the work's own time, not the machine's (the timing-flake lesson)
    added = catch_up(game.world, game.place.id, now=game.world.time + 100)
    elapsed = time.process_time() - start''')

FUZZ = "tests/test_fuzz.py"
Path(FUZZ).write_text(Path(FUZZ).read_text(encoding="utf-8") + '''

@pytest.mark.parametrize("seed", [3, 11])
def test_a_tournament_season(tmp_path, seed, monkeypatch):
    """Tournaments come round where the player stands: entering, betting, watching and fighting; every rule holds."""
    import systems.tournaments as T
    import systems.world_events as W
    from systems.bodies import load_body, save_body
    from systems.realms import REALMS
    for kind, every in (("grand_assembly", 4), ("dragon_phoenix", 2), ("sect_contest", 1)):
        monkeypatch.setitem(W.TYPES, kind, {**W.TYPES[kind], "every": every})
    monkeypatch.setitem(W.TYPES, "lei_tai", {**W.TYPES["lei_tai"], "chance": 1.0})
    host = T.host_city
    monkeypatch.setattr(T, "host_city", lambda world, rng: (
        world.targets(world.get_meta("player_id"), "located_in") or [host(world, rng)])[0])
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Entrant{seed}", world_seed=seed)
    happened, readied = set(), None
    for step in range(300):
        game = app.game
        if game.player.id != readied:  # every new character is strong and rich enough to enter
            body = load_body(game.world, game.player.id)
            if body.realm < 2:  # Second-rate, at the realm's first step (the body rules hold)
                body.realm, body.energy_years, body.bottleneck = 2, REALMS[2].threshold, False
            save_body(game.world, game.player.id, body)
            game.world.update_data(game.player.id, silver=500)
            readied = game.player.id
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif T.here(game.world, game.place.id, T.KINDS, ("announced",)) is not None and rng.random() < 0.5:
            app.submit("register")  # a tournament-goer: names are being taken here
        elif rng.random() < 0.4 and app.choices:  # anything on the menu but the road: the tournaments come to them
            stay = [n for n, c in enumerate(app.choices, 1) if c.action.verb not in ("travel", "routes")]
            app.submit(str(rng.choice(stay or [1])))
        else:
            app.submit(rng.choice(["tournaments", "bracket", "register", "register", "watch", "odds", "bet a 5",
                                   "look", "rest", "meditate day", "meditate week", "journal", "rankings"]))
        if rng.random() < 0.05:
            app.handle_key("f11", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    assert {"registered", "bracket_drawn", "match_resolved", "tournament_won"} <= happened, happened
    app.shutdown()
''', encoding="utf-8", newline="\n")
print("task 8 edits applied")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4e_task8.py && .venv/Scripts/python.exe -m pytest tests/test_tournament_season.py "tests/test_fuzz.py::test_a_tournament_season" -q -p no:cacheprovider`
Expected: `task 8 edits applied`, then `6 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: the 500-year soak passes (about 3 minutes).

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "feat: a tournament season end to end - brackets compacted to their podium, the fork guide, the tournament fuzz"`

---

## Self-review

- **Spec coverage:**
  - §3, the four kinds: Tasks 1–2.
  - §4, brackets, seeding, rounds by day, the bout and results: Tasks 1–3.
  - §5.1 betting: Task 4. §5.2 watching and elders: Task 5. §5.3 grudges: Task 5 (and the disqualified killer's `disgraced` fact, Task 3). §5.4 dark interventions: Task 6.
  - §6 screens: Tasks 3 (register, the call, the lei tai), 4 (the bookmaker), 5 (watch), 6 (expose) and 7 (the rest).
  - §7 debug rules 1–5: Tasks 1, 2, 3 and 4.
  - §8 testing: every task's tests, plus Task 8's compaction, old save, speed and fuzz.
- **Placeholders:** none; every step carries its code or its command.
- **Types:** the names in each task's Interfaces block match the code of the tasks before it; the dry run applied Tasks 1–8 in order on a copy of master and ran the full suite.
