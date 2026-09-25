# Phase 4g: Succession Crises Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a sect's leader dies and the seat is in doubt, the sect falls into a crisis.
- Claimants rise and camps gather. The will, the leader's token and a deathbed transmission weigh on who is rightful.
- The seat is won by the elders' backing, a trial by combat, or force of arms, and a war that drags on splits the sect.
- The player hears of crises everywhere, plays in their own sects' crises, and can lose a sect they lead to one.

**Architecture:**
- **A crisis** is a 4d world-event occurrence, `succession_crisis`, a trigger type started by the faction clock at the sect's seat. Its camps, claimants, will, token, trial and strife live in the occurrence's `data["data"]`. The faction points at it (`crisis`) until it is settled.
- **The faction clock** asks `leaderless_events` before it fills a leader's seat:
  - `None`: 4a's handover, the chief disciple first;
  - a list: a crisis holds the seat, played in full near the player and settled in a line far away.
- **Strife** runs on after the stages as a faction-clock season hook, and may end in a breakaway faction.
- **The player's part** is a mixin (`CrisisMixin`) over plain rule modules (`crisis_play`, `regency`), in the 3b and 4e style of `*_block` and `*_events`.

**Tech Stack:** Python 3.14, SQLite (event-sourced `World`), `tomllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-25-phase4g-succession-crises-design.md`

## Global Constraints

- **Save format:** no save-format version change.
  - New state lives in faction data (`crisis`, `heir`, `fallen`, `transmitted`, `history`, `parent`, `regent`, `regency_for`, `visited`, `usurped_from`), in the occurrence's `data["data"]`, in one `sect_token` treasure per faction, and in `secluded` Grand Elders.
- **Knowledge vs truth:**
  - pages and briefs name only claimants and backers the player has heard of or met (`known_people`, which now also reads a tale's `people`);
  - a hidden will's holder and a lost token's place are never shown to someone who has not seen them.
- **Reads never write:** a look or a page never starts a crisis or names a chief disciple. The faction clock does. The one engine write is the season the player last stood at a seat they lead (`visited`), at most once a season.
- **The entity cache (4e):** all crisis state is written through `update_data`, never by editing `.data` in place.
- **Speed (CPU time, `time.process_time`, averaged over 10 calls after `gc.collect()`):**
  - the camps: under 10 ms;
  - the Succession block: under 30 ms;
  - a turn at a seat in crisis: under 50 ms;
  - the clock's question with a crisis live: under 5 ms;
  - the 200-year soak keeps its 100 ms season budget, and the 500-year soak its 200 ms.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The player claims the seat, then dies before the contest.**
   - The contest goes on among the living claimants. Nothing waits for a dead claimant.
   - Task 5 pins this with `test_a_claimant_who_dies_before_the_contest_leaves_it_to_the_others`.
2. **A save reloaded in the middle of a crisis.**
   - The camps, the player's choices and the Succession block come back.
   - Task 7 pins this with `test_a_save_reloaded_mid_crisis_keeps_its_camps`.
3. **Two sects seated in one town, both leaderless in the same season.**
   - 4d allows one live occurrence a type and place. The second crisis is settled in a line, never lost, and no seat is left empty for good.
   - Task 3 pins this with `test_two_sects_seated_in_one_town_each_get_their_crisis_or_their_line`.
4. **The trial waits for a player who never comes.**
   - When the aftermath ends, the player's side forfeits.
   - Task 3 pins this with `test_a_trial_the_player_must_fight_waits_and_is_forfeit_if_they_never_come`.
5. **A long catch-up passes a crisis's stages.**
   - A crisis whose stages would already be over when it starts is settled in a line (`begin_events` falls back to the summary), never left half-begun.
   - Task 3 pins the summary with `test_a_crisis_far_from_the_player_is_settled_in_a_line`.

## Plan-time rulings (deviations from the spec, argued)

1. **The 4d stages carry fixed names** (`foretold`, `announced`, `active`, `aftermath`). So:
   - the mourning is `announced`, the canvass is `active`, and the contest is decided as the `aftermath` begins;
   - strife runs on after the stages, a season at a time, on the faction clock;
   - the crisis stays live (the faction's `crisis`, the occurrence's `phase`) until it is settled.
   - *Cost if wrong:* none visible.
2. **The `close` doubt, as the dry run found it must be:**
   - with a fit chief disciple, the seat is in doubt only if an ambitious elder stands a realm above them;
   - with none, it is in doubt when the two best elders (else keepers) are within one realm.
   - Every sect's elders share a realm by construction, so the spec's rule made every leader's death a crisis and broke 4a's handover test.
   - *Cost if wrong:* fewer crises when a chief disciple is named.
3. **Ambition is read from existing traits** (`proud`, `cunning`, `greedy`), as the spec says. No trait is added, and world seeds stay as they are. *Cost if wrong:* none.
4. **An NPC trial is decided by realm with upsets** (4e plan ruling 7), not by the full duel simulation. The player's trial is an ordinary duel. *Cost if wrong:* NPC trials are less varied.
5. **The will is a mark on the crisis, not an item.**
   - Its state and holder live in the crisis's data.
   - It changes hands by a search, a camp's find or a duel "for the will".
   - *Cost if wrong:* it cannot be pickpocketed or traded apart from the crisis.
6. **The leader's token is one treasure per faction, made when its first leader falls,** far away too. The spec had a flag far away. *Cost if wrong:* a few more entities in a long world.
7. **A clash in strife costs the losing camp a backer:** dead at 4a's kill rate, else gone home. NPCs have no injuries to take. *Cost if wrong:* none visible.
8. **The per-region cap on minor factions is 4** (`schism.MAX_MINORS`); the spec named no number. Past it, or past two breakaways from one faction, the losers are exiled. *Cost if wrong:* fewer breakaways in crowded regions.
9. **Far away:**
   - a close contest (the top two weights within 0.5) comes to arms at 0.2;
   - half of those split the sect.
   - The spec gave the 0.2 but not what follows. *Cost if wrong:* breakaways are rare far away.
10. **A founded sect that passes out of the player's line becomes a minor faction of the world:** a school, or an unorthodox clan for the ruthless path, run by the faction clock.
    - This happens when it is usurped, lost in a crisis, or handed on by stepping down.
    - The 3c rules (the founder leads, the seat is the founder's land) cannot hold for an NPC master.
    - *Cost if wrong:* the old sect's 3c buildings and treasury lie idle.
11. **4e's raid hook tells a tournament raid from a 3b guard duty's raid.** The realm heir's fuzz found 4e reading a duty's raider duel as a tournament raid (a `KeyError`). It is pulled into Task 8, as 4f did with rulings 23 and 24. *Cost if wrong:* none.
12. **A holder may keep the seat while it is contested.**
    - This covers the player's own sect, an ambitious regent who will not hand over, and a usurped seat reclaimed.
    - The rule in `check_crises` is that a leader during a crisis must be one of its claimants. The spec said "no leader unless a regent".
    - *Cost if wrong:* none.
13. **A regent holds the post as `leader`;** the faction's `regency_for` names the ward. The spec had a role `regent`. Every system that reads "leader" treats a regent as the leader, as spec 6.5 wants. *Cost if wrong:* none.
14. **Regencies:**
    - A regency goes to the senior elder, ambitious or not.
    - Only an ambitious regent usurps after the second absence, or contests the master's return. A loyal one hands back.
    - The spec said "an ambitious elder declares a regency".
    - *Cost if wrong:* regencies are a little more common and less often a threat.
15. **The player sways only for their own camp** (their declared claimant, or themself as a claimant), not for anyone they choose. *Cost if wrong:* one fewer way to play both sides.
16. **The Grand Elder is placed in the seat's region,** not in a town. They are in no scene and at no tournament, and on the life clock like anyone. *Cost if wrong:* none.
17. **A favour for a voter is a 3b "deliver" duty for their faction.** The sway is spent when it is done, within the canvass. *Cost if wrong:* favours are all letters.
18. **Far from the player, a crisis is summarised when it starts,** in one line of claimants and outcome, not stage by stage. *Cost if wrong:* no mid-crisis rumours from far away.
19. **The frequency of crises, measured:**
    - the 200-year soak's 9 regions saw 7 crises (all far away), and 31 chief disciples were named;
    - leaders far away die only as the life clock catches them up, so crises are rarer than the brainstorm's "a few a decade".
    - *Cost if wrong:* crises feel rare. The doubt rule and the life clock are the knobs.
20. **A will held at the mourning is held by the first claimant it does not name.** *Cost if wrong:* none.
21. **A player who walks out with a breakaway keeps their rank there, as a member.** *Cost if wrong:* none.
22. **The 4b `succession` event records `led`:** the seats the old player held, and whether the heir was of each. The heir's claim needs to know whether the heir was a member before 4b made them the founder. *Cost if wrong:* none.

## Files

| File | Responsibility |
|---|---|
| `systems/claimants.py` | The chief disciple, who claims, who votes, leanings, camps, votes. |
| `systems/succession_crisis.py` | How a leader fell, the doubt, the clock's question, the stages, the contest, the settlement, the summary far away. |
| `systems/testament.py` | The will, the leader's token, deathbed transmission, the Grand Elder. |
| `systems/schism.py` | Strife on the faction clock, breakaways, exile, far strife. |
| `systems/crisis_play.py` | The player: declare, claim, sway, champion, the trial, the chambers, the will, the token. |
| `systems/regency.py` | A sect the player leads: the heir's claim, absence, stepping down; regents for a child. |
| `systems/events/succession_crisis.py` | The 4d hooks. |
| `engine/crisis.py` | `CrisisMixin`: the choices, the talk menu, the handlers, the duels' ends. |
| `engine/crisis_page.py` | The Succession block, the sky page's crises, the sheet's posts. |
| `narrate/crisis_text.py`, `narrate/grammar/crisis.toml` | The tales, the player's deeds, the scene's mourning. |

Existing files touched: `systems/data/world_events.toml`, `systems/world_clock.py`, `debug/invariants.py`, `systems/tournaments.py`, `engine/sky.py`, `narrate/outcomes.py`, `systems/beliefs.py`, `engine/standing_page.py`, `engine/game.py`, `systems/ranks.py`, `systems/succession.py`, `engine/sheet.py`, `engine/commands.py`, `narrate/brief.py`, `engine/tournament.py`, `docs/world-events.md`, and the tests `test_world_clock.py` and `test_ranks.py`.

**How each task is laid out:**
1. The tests, as whole new files.
2. The red run.
3. The new modules, as whole files.
4. One patch script, `.patches/4g_taskN.py`, holding the task's edits to existing files. Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: Claimants and the seat in doubt

The faction names a chief disciple once a year. When a leader dies, how they fell is remembered, and the clock asks whether the seat is in doubt. If it is, a `succession_crisis` begins at the seat (near the player; far away 4a's handover stands until Task 3), the claimants declare, and the heralds cry it.

**Files:**
- Create: `systems/claimants.py`
- Create: `systems/events/succession_crisis.py`
- Create: `systems/succession_crisis.py`
- Create: `tests/test_succession_crisis.py`
- Modify (by `.patches/4g_task1.py`): `systems/data/world_events.toml`, `systems/world_clock.py`, `debug/invariants.py`, `tests/test_world_clock.py`

**Interfaces:**
- Consumes: 4a's `world_clock.succession_events`, `_promotion`; 4d's `sky.start_events`, `W.index`; 3a's `attitude`; `kin_of`.
- Produces:
  - `claimants`: `AMBITIOUS`, `ADULT`, `MAX_CLAIMANTS`, `PROOF_LEAN`, `LOYAL_LEAN`, `ambitious(world, p)`, `role_in(world, p, f)`, `age_of`, `staff(world, f, roles)`, `fit(world, p, f)`, `_best`, `name_chief_events(world, f, n)`, `declare(world, f, leader) -> list[{person, kind}]`, `voters(world, f)`, `proofs(world, crisis, c)`, `lean(world, crisis, voter, c, full=True)`, `named(world, crisis)`, `camps(world, crisis, full=True) -> ({claimant: [backers]}, undecided)`, `votes(world, crisis, backing)`; events `named_chief`.
  - `succession_crisis` (SC): `KIND`, `VIOLENT`, `live(world, f)`, `crisis_of(occurrence)`, `doubt(world, f)`, `near(world, f)`, `leaderless_events(world, f, n) -> list | None`, `begin_events(world, f, n, cause, claimants, leader, force=False)`, `on_stage`, `claimant(crisis, p)`, `standing_claimants(world, crisis)`; events `crisis_heralded`, `crisis_phase`; faction data `crisis`, `heir`, `fallen`.
  - `debug.invariants.check_crises(world)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_succession_crisis.py`:
```python
import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.sky as sky
import systems.succession_crisis as SC
import systems.world_clock as clock
from debug.invariants import check_crises
from engine.game import Game
from systems import factions as F
from systems import founding, halls
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


def a_sect(game, kind="orthodox_sect"):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)
    seat = halls.seat_of(world, sect)
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, seat, "located_in")  # near: its crisis is played in full (spec 2.4)
    return sect, seat


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def kill(world, person, place, cause="age"):
    commit(world, [Event("died", (person, person), place, {"cause": cause, "world": True})])


def a_season(game):
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)


def name_heir(world, sect, person):
    commit(world, [Event("named_chief", (person,), world.entity(sect).data["seat"], {"faction": sect, "season": 0})])


def calm_elders(world, sect, seat):
    for elder in staff(world, sect, seat, "elder"):
        world.update_data(elder, traits=["kind"])


def test_the_chief_disciple_is_named_in_the_first_season_of_each_year(game):
    world = game.world
    sect, seat = a_sect(game)
    assert C.name_chief_events(world, sect, 5) == []
    [named] = C.name_chief_events(world, sect, 4)
    chief = named.actors[0]
    assert C.role_in(world, chief, sect) in ("keeper", "disciple")
    commit(world, [named])
    assert world.entity(sect).data["heir"] == chief
    assert world.facts(predicate="named_chief", subject=chief)
    assert C.name_chief_events(world, sect, 8) == []  # still fit: no new naming


def test_a_player_member_the_leader_favours_is_named_chief_disciple(game):
    world, me = game.world, game.player.id
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    [gift] = commit(world, [Event("gift_given", (me, leader), seat, {})])
    world.add_memory(leader, gift, "grateful", 1.0, True)
    [named] = C.name_chief_events(world, sect, 4)
    assert named.actors == (me,)


def test_a_fit_chief_disciple_takes_the_seat_when_no_ambitious_elder_stands_above(game):
    world = game.world
    sect, seat = a_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    name_heir(world, sect, keeper)
    calm_elders(world, sect, seat)
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    a_season(game)
    assert staff(world, sect, seat, "leader") == [keeper]
    assert SC.live(world, sect) is None and world.entity(sect).data.get("heir") is None


def test_an_ambitious_elder_above_the_chief_disciple_starts_a_crisis(game):
    world = game.world
    sect, seat = a_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    name_heir(world, sect, keeper)
    calm_elders(world, sect, seat)
    proud = staff(world, sect, seat, "elder")[0]
    world.update_data(proud, traits=["proud"])
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    assert SC.doubt(world, sect) == "close"
    a_season(game)
    occurrence = SC.live(world, sect)
    assert occurrence is not None and occurrence.data["type"] == SC.KIND and occurrence.data["place"] == seat
    crisis = SC.crisis_of(occurrence)
    assert crisis["cause"] == "close" and crisis["leader"] == leader and crisis["phase"] == "mourning"
    assert {"person": keeper, "kind": "chief"} in crisis["claimants"]
    assert {"person": proud, "kind": "elder"} in crisis["claimants"]
    assert staff(world, sect, seat, "leader") == []
    assert check_crises(world) == []


def test_the_clock_leaves_the_seat_empty_while_its_crisis_lives(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat, cause="killed")
    a_season(game)
    first = SC.live(world, sect)
    assert first is not None
    n = clock.world_tick(world) + 1
    promotions = clock.succession_events(world, sect, n)  # the clock's next season, asked while the crisis lives
    assert not [e for e in promotions if e.data.get("role") == "leader"]
    assert SC.live(world, sect).id == first.id and staff(world, sect, seat, "leader") == []
    assert check_crises(world) == []


def test_what_puts_a_seat_in_doubt(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    [keeper] = staff(world, sect, seat, "keeper")
    calm_elders(world, sect, seat)
    world.update_data(sect, fallen={"leader": leader, "cause": "killed", "place": seat})
    assert SC.doubt(world, sect) == "violence"
    world.update_data(sect, fallen={"leader": leader, "cause": "age", "place": seat + 1})
    assert SC.doubt(world, sect) == "token"  # died away from the seat: the token is not in the hall
    world.update_data(sect, fallen={"leader": leader, "cause": "age", "place": seat})
    assert SC.doubt(world, sect) == "close"  # no chief disciple, and two elders of a realm
    name_heir(world, sect, keeper)
    assert SC.doubt(world, sect) is None
    world.update_data(keeper, age=12)
    assert SC.doubt(world, sect) == "heir"  # a child cannot hold the seat
    world.update_data(keeper, age=30, sealed_in={"realm": 1, "season": 0})
    assert SC.doubt(world, sect) == "heir"


def test_a_blood_heir_claims_in_a_clan(game):
    world = game.world
    clan, seat = a_sect(game, "martial_clan")
    [leader] = staff(world, clan, seat, "leader")
    child = founding.make_person(world, "test:child", seat, occupation="wandering swordsman", age=20)
    world.relate(leader, child, "kin_of", 0, {"role": "child"})
    claims = C.declare(world, clan, leader)
    assert {"person": child, "kind": "blood"} in claims
    crisis = {"faction": clan, "claimants": claims}
    assert "blood" in C.proofs(world, crisis, {"person": child, "kind": "blood"})


def test_at_most_three_claim_the_seat(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    for i in range(3):
        child = founding.make_person(world, f"test:child:{i}", seat, occupation="wandering swordsman", age=20)
        world.relate(leader, child, "kin_of", 0, {"role": "child"})
        world.relate(child, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 0, "status": "member",
                                                   "secret": False})
    assert len(C.declare(world, sect, leader)) == 3


def test_with_fewer_than_two_claimants_the_seat_is_filled_at_once(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    for elder in staff(world, sect, seat, "elder"):
        kill(world, elder, seat)
    kill(world, leader, seat, cause="killed")
    a_season(game)
    assert SC.live(world, sect) is None
    assert len(staff(world, sect, seat, "leader")) == 1


def test_voters_lean_to_whom_they_like_and_the_loyal_to_the_named(game):
    world = game.world
    sect, seat = a_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    elders = staff(world, sect, seat, "elder")
    name_heir(world, sect, keeper)
    for elder in elders:
        world.update_data(elder, traits=["proud"])
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    a_season(game)
    crisis = SC.crisis_of(SC.live(world, sect))
    backing, undecided = C.camps(world, crisis)
    assert all(backing[e][0] == e for e in elders)  # the claimants back themselves
    assert keeper in backing[keeper]
    branch_keepers = [v for v in C.voters(world, sect) if v not in elders and v != keeper]
    voter = branch_keepers[0] if branch_keepers else None
    if voter is not None:
        world.update_data(voter, traits=["loyal"])
        assert C.lean(world, crisis, voter, {"person": keeper, "kind": "chief"}, full=False) >= C.PROOF_LEAN["chief"] + C.LOYAL_LEAN


def test_the_heralds_cry_the_crisis_with_its_claimants(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat, cause="killed")
    a_season(game)
    sky.observe(world, seat)
    [fact] = world.facts(predicate="crisis")
    crisis = SC.crisis_of(SC.live(world, sect))
    variant = fact.data["variant"]
    assert variant["people"] == [c["person"] for c in crisis["claimants"]] and variant["target"] == sect
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_succession_crisis.py`
Expected: `ModuleNotFoundError: No module named 'systems.claimants'`.

- [ ] **Step 3: Write the new modules**

`systems/claimants.py`:
```python
"""Who may lead a sect in crisis (phase 4g spec 3.2, 4.1, 4.3): the chief disciple, claimants, voters and their leanings.

Leanings are computed, never stored (like 3a attitude): only the player's sways are kept, on the crisis.
"""

from systems import factions as F
from systems.attitude import attitude
from systems.facts import make_variant, place_name, record_fact
from systems.kin import kin_of
from systems.tournaments import alive, realm_of
from world.events import Event, effect, listen

AMBITIOUS = frozenset({"proud", "cunning", "greedy"})  # no new trait: world seeds stay as they are (plan ruling 3)
CLAN_TYPES = frozenset({"martial_clan", "local_clan"})
MAX_CLAIMANTS = 3
ADULT, BLOOD_AGE = 16, 14
NAMING_SEASON = 0  # the chief disciple is named in the first season of each year
PLAYER_FAVOUR = 0.5  # the leader's attitude that names a player member chief disciple
BACKING = 0.2  # a voter backs their best claimant only if they lean this far
REALM_LEAN = 0.2
PROOF_LEAN = {"chief": 0.2, "blood": 0.3, "will": 0.5, "transmission": 0.4, "token": 0.3}  # blood: in clans only
LOYAL_LEAN = 0.2


def ambitious(world, person: int) -> bool:
    return bool(AMBITIOUS & set(world.entity(person).data.get("traits", ())))


def role_in(world, person: int, faction: int) -> str | None:
    found = F.membership(world, person, faction)
    if not found or found[1].get("status", "member") != "member":
        return None
    return found[1].get("role")


def age_of(world, person: int) -> float:
    return float(world.entity(person).data.get("age", 30))


def staff(world, faction: int, roles) -> list[int]:
    """Living members in good standing of these roles, anywhere (one query)."""
    return [p for p, _, d in world.relations_to(faction, "member_of")
            if d.get("status", "member") == "member" and d.get("role") in roles and alive(world, p)]


def fit(world, person, faction: int) -> bool:
    """A named heir who can take the seat: alive, of the faction, not sealed away, grown."""
    return isinstance(person, int) and alive(world, person) and role_in(world, person, faction) is not None \
        and not world.entity(person).data.get("sealed_in") and age_of(world, person) >= ADULT


def _best(world, people: list[int]) -> int | None:
    return min(people, key=lambda p: (-realm_of(world, p), age_of(world, p), p)) if people else None


# --- the chief disciple (spec 3.2) ------------------------------------------------------------

def name_chief_events(world, faction: int, n: int) -> list[Event]:
    """Once a year the faction names its chief disciple, if the post is empty or its holder can no longer hold it."""
    data = world.entity(faction).data
    if n % 4 != NAMING_SEASON or data.get("type") not in F.STAFFED or data.get("dissolved"):
        return []
    held = data.get("heir")
    if held is not None and fit(world, held, faction) and role_in(world, held, faction) in ("keeper", "disciple"):
        return []
    leaders = staff(world, faction, ("leader", "regent"))
    player = world.get_meta("player_id")
    mine = F.membership(world, player, faction) if isinstance(player, int) else None
    chosen = None
    if mine and mine[1].get("status", "member") == "member" and mine[0] >= 2 and mine[1].get("role") != "leader" \
            and leaders and attitude(world, leaders[0], player).score >= PLAYER_FAVOUR:
        chosen = player
    if chosen is None:
        chosen = _best(world, [p for p in staff(world, faction, ("keeper", "disciple"))
                               if not world.entity(p).data.get("is_player")])
    if chosen is None or chosen == held:
        return []
    return [Event("named_chief", (chosen,), data.get("seat"), {"faction": faction, "season": n})]


@effect("named_chief")
def _named(world, event) -> None:
    world.update_data(event.data["faction"], heir=event.actors[0])


@listen("named_chief")
def _named_news(world, event, event_id: int) -> None:
    variant = make_variant("named_chief", event.actors[0], event.data["faction"], place=place_name(world, event.place))
    record_fact(world, event.actors[0], "named_chief", event.data["faction"], place=event.place,
                source_event=event_id, weight=1.5, variant=variant)


# --- claimants (spec 4.1) ---------------------------------------------------------------------

def declare(world, faction: int, leader: int | None) -> list[dict]:
    """Who claims the seat, in order, until there are three: chief disciple, blood heir, ambitious elders."""
    data = world.entity(faction).data
    out: list[dict] = []

    def add(person, kind):
        if person is not None and all(c["person"] != person for c in out) and len(out) < MAX_CLAIMANTS:
            out.append({"person": person, "kind": kind})
    heir = data.get("heir")
    if isinstance(heir, int) and alive(world, heir) and role_in(world, heir, faction) is not None \
            and not world.entity(heir).data.get("sealed_in"):
        add(heir, "chief")
    for kin, role in (kin_of(world, leader) if leader is not None else []):
        if role == "child" and alive(world, kin) and age_of(world, kin) >= BLOOD_AGE \
                and (data["type"] in CLAN_TYPES or role_in(world, kin, faction) is not None):
            add(kin, "blood")
    elders = sorted(staff(world, faction, ("elder",)), key=lambda p: (-realm_of(world, p), p))
    for elder in elders:
        best = max((realm_of(world, c["person"]) for c in out), default=-1)
        if ambitious(world, elder) or realm_of(world, elder) >= best - 1:
            add(elder, "elder")
    return out


# --- voters and leanings (spec 4.3) -----------------------------------------------------------

def voters(world, faction: int) -> list[int]:
    """The elders and hall keepers, at the seat and the branches; the player if a member of rank 2 or more."""
    out = staff(world, faction, ("elder", "keeper"))
    player = world.get_meta("player_id")
    mine = F.membership(world, player, faction) if isinstance(player, int) else None
    if mine and mine[1].get("status", "member") == "member" and mine[0] >= 2 and player not in out:
        out.append(player)
    return sorted(out)


def proofs(world, crisis: dict, claimant: dict) -> list[str]:
    """What speaks for a claimant: the chief disciple's post, blood (in a clan), a read will naming them,
    the late master's transmission, the leader's token in their hands."""
    person, found = claimant["person"], []
    if claimant["kind"] == "chief":
        found.append("chief")
    if claimant["kind"] == "blood" and world.entity(crisis["faction"]).data["type"] in CLAN_TYPES:
        found.append("blood")
    will = crisis.get("will") or {}
    if will.get("state") == "read" and will.get("names") == person:
        found.append("will")
    if crisis.get("transmitted") == person:
        found.append("transmission")
    token = crisis.get("token")
    if token is not None and person in world.sources(token, "owns"):
        found.append("token")
    return found


def proof_lean(world, crisis: dict, claimant: dict) -> float:
    return sum(PROOF_LEAN.get(p, 0.0) for p in proofs(world, crisis, claimant))


def lean(world, crisis: dict, voter: int, claimant: dict, full: bool = True) -> float:
    """How far `voter` leans to `claimant`: attitude (full detail only), realm, proofs, sways, loyalty."""
    person = claimant["person"]
    if voter == person:
        return 9.0  # claimants back themselves
    realms = [realm_of(world, c["person"]) for c in crisis["claimants"]]
    value = REALM_LEAN * (realm_of(world, person) - min(realms))
    value += proof_lean(world, crisis, claimant)
    value += crisis.get("sways", {}).get(str(voter), {}).get(str(person), 0.0)
    if full and not world.entity(voter).data.get("is_player"):
        value += attitude(world, voter, person).score
    if "loyal" in world.entity(voter).data.get("traits", ()) and person == named(world, crisis):
        value += LOYAL_LEAN
    return round(value, 3)


def named(world, crisis: dict) -> int | None:
    """Whom the late leader named: the will's name if it was read (Task 2), else the chief disciple."""
    will = crisis.get("will") or {}
    if will.get("state") == "read":
        return will.get("names")
    return next((c["person"] for c in crisis["claimants"] if c["kind"] == "chief"), None)


def camps(world, crisis: dict, full: bool = True) -> tuple[dict[int, list[int]], list[int]]:
    """({claimant: [backers]}, undecided): each voter backs their best claimant if they lean far enough."""
    backing: dict[int, list[int]] = {c["person"]: [c["person"]] for c in crisis["claimants"]}
    undecided = []
    declared = {int(k): v for k, v in crisis.get("declared", {}).items()}
    for voter in voters(world, crisis["faction"]):
        if voter in backing:
            continue
        if voter in declared and declared[voter] in backing:
            backing[declared[voter]].append(voter)
            continue
        if world.entity(voter).data.get("is_player"):
            undecided.append(voter)
            continue
        leans = [(lean(world, crisis, voter, c, full), c["person"]) for c in crisis["claimants"]]
        best, person = max(leans, key=lambda p: (p[0], -p[1])) if leans else (0.0, None)
        if person is not None and best >= BACKING:
            backing[person].append(voter)
        else:
            undecided.append(voter)
    return backing, undecided


def votes(world, crisis: dict, backing: dict[int, list[int]]) -> dict[int, int]:
    """Each backer counts one vote; the Grand Elder three, for whomever they back or for themself (spec 4.2)."""
    heavy = {crisis.get("grand_elder_backs"), crisis.get("grand_elder")} - {None}
    return {c: len(b) + (2 if c in heavy else 0) for c, b in backing.items()}


@listen("succeeded")
def _seat_filled(world, event, event_id: int) -> None:
    """A new leader: the fallen leader is mourned, and a chief disciple who rose leaves the post empty."""
    d = event.data
    if d["role"] != "leader":
        return
    data = world.entity(d["faction"]).data
    world.update_data(d["faction"], fallen=None, **({"heir": None} if data.get("heir") == event.actors[0] else {}))
```

`systems/events/succession_crisis.py`:
```python
"""A succession crisis (phase 4g spec 2.2): started by the faction clock, never on a calendar."""

import systems.succession_crisis as SC


def on_stage(world, occurrence, stage: str) -> list:
    return SC.on_stage(world, occurrence, stage)
```

`systems/succession_crisis.py`:
```python
"""Succession crises (phase 4g spec 3-4): a leader's death with the seat in doubt becomes a contest.

The faction clock asks `leaderless_events` before it promotes a new leader. With no doubt the 4a
handover stands (the named heir first); with doubt a `succession_crisis` occurrence starts at the seat
and the clock leaves the leader's post empty until the crisis is settled.

The 4d stages carry fixed names: `announced` is the mourning, `active` the canvass, and the contest is
decided when the `aftermath` begins (plan ruling 1).
"""

import systems.claimants as C
import systems.sky as sky
import systems.world_events as W
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.tournaments import alive, realm_of
from world.events import Event, effect, listen

KIND = "succession_crisis"
VIOLENT = frozenset({"killed", "executed", "feud", "clash", "raid"})
PHASES = ("mourning", "canvass", "contest", "strife", "settled")


def live(world, faction: int):
    """The faction's crisis occurrence, if one is not yet settled."""
    found = world.entity(faction).data.get("crisis")
    occurrence = world.entity(found) if found is not None else None
    if occurrence is None or occurrence.data["data"].get("phase") == "settled":
        return None
    return occurrence


def crisis_of(occurrence) -> dict:
    return occurrence.data["data"]


# --- the fallen leader (spec 3.1) -------------------------------------------------------------

@listen("died")
def _fallen(world, event, event_id: int) -> None:
    """How a leader died is what later puts the seat in doubt: remembered on the faction."""
    killer, victim = event.actors[0], event.actors[-1]
    for fid, _, data in F.memberships(world, victim):
        faction = world.entity(fid)
        if data.get("role") == "leader" and faction.data.get("type") in F.STAFFED \
                and not faction.data.get("dissolved"):
            world.update_data(fid, fallen={"leader": victim, "cause": event.data.get("cause"), "place": event.place,
                                           "killer": killer if killer != victim else None, "time": world.time})


def doubt(world, faction: int) -> str | None:
    """Why the seat is in doubt, or None (spec 3.1; the `close` rule as plan ruling 2 sets it)."""
    data = world.entity(faction).data
    fallen = data.get("fallen") or {}
    if fallen.get("cause") in VIOLENT:
        return "violence"
    if fallen and fallen.get("place") is not None and fallen.get("place") != data.get("seat"):
        return "token"
    heir = data.get("heir")
    elders = C.staff(world, faction, ("elder",))
    if isinstance(heir, int):
        if not C.fit(world, heir, faction):
            return "heir"
        if any(C.ambitious(world, e) and realm_of(world, e) > realm_of(world, heir) for e in elders):
            return "close"  # an ambitious elder stands above the chief disciple (plan ruling 2)
        return None
    ranked = sorted((realm_of(world, p) for p in elders or C.staff(world, faction, ("keeper",))), reverse=True)
    if len(ranked) >= 2 and ranked[0] - ranked[1] <= 1:
        return "close"
    return None


# --- the clock's question (spec 3.1) ----------------------------------------------------------

def near(world, faction: int) -> bool:
    """Played in full where the player can reach it (spec 2.4): the seat's region, or a faction of theirs."""
    player = world.get_meta("player_id")
    if not isinstance(player, int):
        return False
    found = F.membership(world, player, faction)
    if found and found[1].get("status", "member") == "member":
        return True
    here = world.targets(player, "located_in")
    seat = world.entity(faction).data.get("seat")
    return bool(here) and seat is not None and W.place_xy(world, here[0]) == W.place_xy(world, seat)


def leaderless_events(world, faction: int, n: int) -> list[Event] | None:
    """None: 4a promotes as it always has. A list: a crisis holds the seat (maybe starting it now)."""
    if live(world, faction) is not None:
        return []
    cause = doubt(world, faction)
    if cause is None:
        return None
    leader = (world.entity(faction).data.get("fallen") or {}).get("leader")
    claimants = C.declare(world, faction, leader)
    if len(claimants) < 2:
        return None  # one claim, or none: no contest (spec 4.1)
    return begin_events(world, faction, n, cause, claimants, leader)


def begin_events(world, faction: int, n: int, cause: str, claimants: list[dict], leader: int | None,
                 force: bool = False) -> list[Event] | None:
    """A crisis starts at the seat, played in full when near (or `force`d: the player's own sect), else settled in a line."""
    seat = world.entity(faction).data["seat"]
    if not force and not near(world, faction):
        return None  # far from the player: 4a's handover, until Task 3 settles it in a line
    crisis = {"faction": faction, "leader": leader, "cause": cause, "claimants": claimants, "declared": {},
              "sways": {}, "champions": {}, "will": None, "token": None, "transmitted": None, "trial": None,
              "strife": None, "outcome": None, "phase": "mourning", "season": n}
    player = world.get_meta("player_id")
    if any(c["person"] == player for c in claimants):
        crisis["declared"] = {str(player): player}
    starts = max(n * W.SEASON, world.time - W.SEASON) if force else n * W.SEASON
    return sky.start_events(world, KIND, seat, starts, crisis) or None  # long over: 4a's handover after all


@listen("sky_started")
def _begun(world, event, event_id: int) -> None:
    if event.data["type"] != KIND:
        return
    row = next(r for r in reversed(W.index(world)) if r[W.TYPE] == KIND and r[W.PLACE] == event.data["place"])
    faction = event.data["data"]["faction"]
    world.update_data(faction, crisis=row[W.ID], fallen=None)


# --- the stages -------------------------------------------------------------------------------

def on_stage(world, occurrence, stage: str) -> list[Event]:
    crisis = crisis_of(occurrence)
    if crisis["phase"] == "settled":
        return []
    if stage == "announced":
        return [Event("crisis_heralded", (), occurrence.data["place"], {"occurrence": occurrence.id})]
    if stage == "active":
        return [Event("crisis_phase", (), occurrence.data["place"], {"occurrence": occurrence.id, "phase": "canvass"})]
    return []


@effect("crisis_phase")
def _phase(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**crisis_of(occurrence), "phase": event.data["phase"]})


@listen("crisis_heralded")
def _heralded(world, event, event_id: int) -> None:
    """The heralds cry it: the seat is empty and these claim it (spec 5)."""
    occurrence = world.entity(event.data["occurrence"])
    crisis = crisis_of(occurrence)
    people = [c["person"] for c in crisis["claimants"]]
    variant = make_variant("crisis", people[0], crisis["faction"], place=place_name(world, event.place))
    variant.update(stage="mourning", people=people, kinds=[c["kind"] for c in crisis["claimants"]])
    record_fact(world, people[0], "crisis", crisis["faction"], place=event.place, source_event=event_id,
                weight=2.0, variant=variant, extra={"occurrence": occurrence.id})


def claimant(crisis: dict, person: int) -> dict | None:
    return next((c for c in crisis["claimants"] if c["person"] == person), None)


def standing_claimants(world, crisis: dict) -> list[dict]:
    """Claimants still able to take the seat: alive and not sealed in a realm."""
    return [c for c in crisis["claimants"] if alive(world, c["person"])
            and not world.entity(c["person"]).data.get("sealed_in")]
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4g_task1.py`:
```python
"""Phase 4g, Task 1: the event type, the faction clock's question, check_crises, the 4a test kept on 4a's rule"""
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


edit('systems/data/world_events.toml', r'''[treasure_light]''', r'''[succession_crisis]
module = "systems.events.succession_crisis"
scope = "town"
cycle = "trigger"
sky = false
stages = { announced = 30, active = 60, aftermath = 20 }

[treasure_light]''')
edit('systems/world_clock.py', r'''import systems.lives as lives
from systems import factions as F''', r'''import systems.claimants as C
import systems.lives as lives
from systems import factions as F''')
edit('systems/world_clock.py', r'''    if any(r == "leader" for r, _, _ in table) and not leaders:
        for pool in ("elder", "keeper", "disciple"):
            heir = _best(world, by_role[pool])
            if heir is not None:
                by_role[pool].remove(heir)
                events.append(_promotion(world, heir, faction, "leader", 4, None))
                break''', r'''    if any(r == "leader" for r, _, _ in table) and not leaders:
        from systems.succession_crisis import leaderless_events  # phase 4g: a seat in doubt waits for its crisis
        held = leaderless_events(world, faction, n)
        chief = world.entity(faction).data.get("heir")
        if held is not None:
            events += held
        elif isinstance(chief, int) and C.fit(world, chief, faction):
            for pool in by_role.values():
                if chief in pool:
                    pool.remove(chief)
            events.append(_promotion(world, chief, faction, "leader", 4, None))  # the chief disciple first (4g)
        else:
            for pool in ("elder", "keeper", "disciple"):
                heir = _best(world, by_role[pool])
                if heir is not None:
                    by_role[pool].remove(heir)
                    events.append(_promotion(world, heir, faction, "leader", 4, None))
                    break''')
edit('systems/world_clock.py', r'''        for faction in wars.clock_factions(world):
            staff = staff_by_town(world, faction)  # one scan serves succession, staffing and power''', r'''        for faction in wars.clock_factions(world):
            commit(world, C.name_chief_events(world, faction, n))  # phase 4g: once a year
            staff = staff_by_town(world, faction)  # one scan serves succession, staffing and power''')
edit('debug/invariants.py', r'''    problems += check_realms(world)
    times''', r'''    problems += check_realms(world)
    problems += check_crises(world)
    times''')
append('debug/invariants.py', r'''

def check_crises(world) -> list[str]:
    """Succession crises (phase 4g spec 8): one live crisis a faction, pointed at, with the seat empty."""
    import systems.claimants as C
    import systems.succession_crisis as SC
    import systems.world_events as W
    out, live = [], {}
    for row in W.index(world):
        if row[W.TYPE] != SC.KIND:
            continue
        occurrence = world.entity(row[W.ID])
        crisis = occurrence.data["data"]
        if crisis["phase"] == "settled":
            continue
        faction = crisis["faction"]
        if faction in live:
            out.append(f"the {world.entity(faction).name} has two live crises")
        live[faction] = occurrence.id
        if world.entity(faction).data.get("crisis") != occurrence.id:
            out.append(f"the {world.entity(faction).name} does not point at its crisis #{occurrence.id}")
        if C.staff(world, faction, ("leader",)):
            out.append(f"the {world.entity(faction).name} has a leader during its crisis")
    for faction in world.entities("faction"):
        pointed = faction.data.get("crisis")
        if pointed is not None and SC.live(world, faction.id) is not None and live.get(faction.id) != pointed:
            out.append(f"the {faction.name} points at #{pointed}, which is no live crisis of theirs")
    return out
''')
edit('tests/test_world_clock.py', r'''def test_a_dead_leader_is_succeeded_and_the_hall_restaffed(game):
    sect = of_type(game.world, "orthodox_sect")''', r'''def test_a_dead_leader_is_succeeded_and_the_hall_restaffed(game, monkeypatch):
    import systems.succession_crisis as SC
    monkeypatch.setattr(SC, "doubt", lambda world, faction: None)  # 4a's handover; 4g's crises are tested apart
    sect = of_type(game.world, "orthodox_sect")''')
print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4g_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_succession_crisis.py tests/test_world_clock.py`
Expected: `23 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: succession crises begin - a chief disciple named each year, a seat in doubt, claimants declared, the heralds' cry

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: The will, the token, the transmission and the Grand Elder

What the late master leaves: the leader's token lies where they fell (or with their killer), a natural death may pour their strength into the chief disciple, a will may be read, hidden or held, and a great sect's Grand Elder may come down the mountain. Each proof now weighs on the voters' leanings.

**Files:**
- Create: `systems/testament.py`
- Create: `tests/test_testament.py`
- Modify (by `.patches/4g_task2.py`): `systems/succession_crisis.py`, `tests/test_succession_crisis.py`, `debug/invariants.py`, `systems/tournaments.py`, `engine/sky.py`

**Interfaces:**
- Consumes: Task 1's `claimants` (`fit`, `ambitious`, `lean`, `MAX_CLAIMANTS`) and `SC` (`crisis_of`, the `sky_started` listener).
- Produces:
  - `testament` (T): `WILL_CHANCE`, `WILL_STATES`, `NATURAL`, `TRANSMIT_CHANCE`, `SEARCH_BASE`, `CAMP_FIND`, `EMERGE_CHANCE`, `TOKEN_PRICE`, `token_of`, `ensure_token`, `holder`, `lies_at`, `put(world, token, owner=None, place=None)`, `at_mourning(world, crisis, rng, far=False) -> crisis`, `ensure_grand_elder(world, f, leader)`, `search_chance`, `camps_search(world, crisis, rng)`, `found_by(will, person)`; events `transmitted`.
  - `SC._searched` at each stage's change; the mourning's work when a crisis begins.

- [ ] **Step 1: Write the failing tests**

`tests/test_testament.py`:
```python
import random

import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.succession_crisis as SC
import systems.testament as T
import systems.tournaments as tournaments
import systems.world_clock as clock
from debug.invariants import check_crises
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.realms import realm_index
from world.events import Event, commit
from world.gen.materialize import people_at


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
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)


def a_sect(game, kind="orthodox_sect"):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)
    seat = halls.seat_of(world, sect)
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, seat, "located_in")  # near: its crisis is played in full (spec 2.4)
    return sect, seat


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def kill(world, person, place, cause="age", killer=None):
    commit(world, [Event("died", (killer or person, person), place, {"cause": cause, "world": True})])


def a_season(game):
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)


def a_crisis(game):
    """A crisis at the orthodox sect: its chief disciple against a proud elder."""
    world = game.world
    sect, seat = a_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["proud"])
    world.update_data(elders[1], traits=["kind"])
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    a_season(game)
    return sect, seat, keeper, elders[0], SC.live(world, sect)


def test_a_leader_who_dies_at_the_seat_leaves_the_token_in_the_hall(game, monkeypatch):
    monkeypatch.setattr(SC, "doubt", lambda world, faction: None)
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    token = T.token_of(world, sect)
    assert world.entity(token).data == {"kind": "sect_token", "faction": sect, "used": False}
    assert T.lies_at(world, token) == seat and T.holder(world, token) is None
    a_season(game)
    [heir] = staff(world, sect, seat, "leader")
    assert T.holder(world, token) == heir and T.lies_at(world, token) is None  # the new leader takes it up
    assert check_crises(world) == []


def test_a_killed_leaders_token_goes_with_the_killer(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    killer = staff(world, sect, seat, "disciple")[0]
    kill(world, leader, seat, cause="killed", killer=killer)
    assert T.holder(world, T.token_of(world, sect)) == killer
    assert SC.doubt(world, sect) == "violence"


def test_a_leader_who_dies_away_leaves_the_token_where_they_fell(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    away = game.place.id if game.place.id != seat else next(t.id for t in world.entities("town") if t.id != seat)
    kill(world, leader, away)
    assert T.lies_at(world, T.token_of(world, sect)) == away
    assert SC.doubt(world, sect) == "token"


def test_a_natural_death_may_pass_the_leaders_strength_to_the_chief_disciple(game, monkeypatch):
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 1.0)
    world = game.world
    sect, seat = a_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    proud = staff(world, sect, seat, "elder")[0]
    world.update_data(proud, traits=["proud"])
    before = realm_index(world.entity(keeper).data["realm"])
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat, cause="illness")
    assert realm_index(world.entity(keeper).data["realm"]) == before + 1
    assert world.facts(predicate="transmitted", subject=leader)
    assert SC.doubt(world, sect) is None  # the elder no longer stands above the heir
    a_season(game)
    assert staff(world, sect, seat, "leader") == [keeper]


def test_the_chief_disciple_takes_up_a_token_left_at_the_seat_when_the_crisis_begins(game):
    world = game.world
    sect, seat, keeper, proud, occurrence = a_crisis(game)
    crisis = SC.crisis_of(occurrence)
    assert T.holder(world, crisis["token"]) == keeper
    assert "token" in C.proofs(world, crisis, SC.claimant(crisis, keeper))
    assert check_crises(world) == []


def test_a_read_will_speaks_for_whom_it_names(game, monkeypatch):
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 1.0, "other": 1.0})
    monkeypatch.setattr(T, "WILL_STATES", (("read", 1.0),))
    world = game.world
    sect, seat, keeper, proud, occurrence = a_crisis(game)
    crisis = SC.crisis_of(occurrence)
    assert crisis["will"] == {"state": "read", "names": keeper, "holder": None}
    assert "will" in C.proofs(world, crisis, SC.claimant(crisis, keeper))
    assert C.named(world, crisis) == keeper


def test_a_hidden_will_is_found_by_a_camp_and_kept_by_one_it_does_not_name(game, monkeypatch):
    world = game.world
    will = {"state": "hidden", "names": 7, "holder": None}
    assert T.found_by(will, 7) == {"state": "read", "names": 7, "holder": None}
    assert T.found_by(will, 8) == {"state": "held", "names": 7, "holder": 8}
    monkeypatch.setattr(T, "CAMP_FIND", 1.0)
    sect, seat, keeper, proud, occurrence = a_crisis(game)
    crisis = {**SC.crisis_of(occurrence), "will": {"state": "hidden", "names": keeper, "holder": None}}
    found = T.camps_search(world, crisis, random.Random(1))["will"]
    assert found["state"] in ("read", "held") and (found["state"] == "read") == (found.get("holder") is None)


def test_a_held_will_is_hidden_by_a_claimant_it_does_not_name(game, monkeypatch):
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 1.0, "other": 1.0})
    monkeypatch.setattr(T, "WILL_STATES", (("held", 1.0),))
    sect, seat, keeper, proud, occurrence = a_crisis(game)
    will = SC.crisis_of(occurrence)["will"]
    assert will["state"] == "held" and will["names"] == keeper and will["holder"] == proud


def test_the_grand_elder_comes_down_the_mountain(game, monkeypatch):
    monkeypatch.setattr(T, "EMERGE_CHANCE", 1.0)
    world = game.world
    sect, seat, keeper, proud, occurrence = a_crisis(game)
    crisis = SC.crisis_of(occurrence)
    elder = crisis["grand_elder"]
    entity = world.entity(elder)
    assert entity.data["secluded"] and entity.data["occupation"] == "grand elder"
    assert elder not in [p.id for p in people_at(world, seat)]  # in seclusion: in no town's scene
    assert tournaments._in_a_realm(world, elder)  # nor at any tournament
    backing, _ = C.camps(world, crisis)
    tally = C.votes(world, crisis, backing)
    if C.ambitious(world, elder):
        assert {"person": elder, "kind": "grand_elder"} in crisis["claimants"] and tally[elder] == 3
    else:
        backed = crisis["grand_elder_backs"]
        assert tally[backed] == len(backing[backed]) + 2
    assert T.ensure_grand_elder(world, sect, None) == elder  # one for the sect, made once
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_testament.py`
Expected: `ModuleNotFoundError: No module named 'systems.testament'`.

- [ ] **Step 3: Write the new modules**

`systems/testament.py`:
```python
"""What the late master leaves (phase 4g spec 3.3, 4.2, 4.4, 4.5): a will, the leader's token, a last transmission,
and the Grand Elder in seclusion who may come down the mountain.

The will is a mark on the crisis (who it names, where it is), not an item (plan ruling 5). The token is a
lasting treasure of its faction, made the first time a leader dies: owned by someone, or lying in a place.
"""

import systems.claimants as C
from systems import factions as F
from systems.attitude import attitude
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.realms import REALMS, realm_index
from systems.tournaments import alive, realm_of
from world.events import Event, commit, effect, listen
from world.gen.materialize import region_of
from world.gen.names import person_name
from world.seed import rng_for

WILL_CHANCE = {"natural": 0.7, "other": 0.3}
WILL_STATES = (("read", 0.5), ("hidden", 0.3), ("held", 0.2))
NATURAL = frozenset({"age", "illness"})
TRANSMIT_CHANCE = 0.3
SEARCH_BASE, SEARCH_PER_REALM, CAMP_FIND = 0.35, 0.1, 0.2
EMERGE_CHANCE = 0.25
GRAND_VOTES = 3
TOKEN_PRICE = 5  # silver per point of the faction's power


# --- the leader's token (spec 4.5) ------------------------------------------------------------

def token_of(world, faction: int) -> int | None:
    found = world.entity_by_seed(f"world:{faction}:token")
    return found.id if found is not None else None


def ensure_token(world, faction: int) -> int:
    found = token_of(world, faction)
    if found is not None:
        return found
    name = world.entity(faction).name
    return world.add_entity("treasure", f"the leader's token of the {name}",
                            {"kind": "sect_token", "faction": faction, "used": False}, f"world:{faction}:token")


def holder(world, token: int) -> int | None:
    owners = world.sources(token, "owns")
    return owners[0] if owners else None


def lies_at(world, token: int) -> int | None:
    places = world.targets(token, "located_in")
    return places[0] if places else None


def put(world, token: int, owner: int | None = None, place: int | None = None) -> None:
    """The token changes hands or is set down: always in exactly one place."""
    for old in world.sources(token, "owns"):
        world.unrelate(old, "owns", token)
    world.unrelate(token, "located_in")
    if owner is not None:
        world.relate(owner, token, "owns")
    elif place is not None:
        world.relate(token, place, "located_in")


# --- the leader's death (spec 3.3, 4.5) -------------------------------------------------------

@listen("died")
def _last_breath(world, event, event_id: int) -> None:
    """The token stays where the leader fell; a natural death may pass the leader's strength to the heir."""
    killer, victim = event.actors[0], event.actors[-1]
    for fid, _, data in F.memberships(world, victim):
        faction = world.entity(fid)
        if data.get("role") != "leader" or faction.data.get("type") not in F.STAFFED or faction.data.get("dissolved"):
            continue
        token = ensure_token(world, fid)
        if holder(world, token) in (None, victim):
            seat = faction.data.get("seat")
            if killer != victim and alive(world, killer):
                put(world, token, owner=killer)
            else:
                put(world, token, place=event.place if event.place is not None else seat)
        heir = faction.data.get("heir")
        rng = rng_for(world.world_seed, f"transmit:{fid}:{victim}")
        if event.data.get("cause") in NATURAL and C.fit(world, heir, fid) \
                and world.targets(heir, "located_in") == [event.place] and rng.random() < TRANSMIT_CHANCE:
            commit(world, [Event("transmitted", (victim, heir), event.place, {"faction": fid})])


@effect("transmitted")
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
    world.update_data(event.data["faction"], transmitted=heir)


@listen("transmitted")
def _transmitted_news(world, event, event_id: int) -> None:
    leader, heir = event.actors
    variant = make_variant("transmitted", leader, heir, place=place_name(world, event.place))
    record_fact(world, leader, "transmitted", heir, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


@listen("succeeded")
def _takes_up_the_token(world, event, event_id: int) -> None:
    """A new leader picks up a token that lies at the seat, or that they hold; a transmission is spent."""
    d = event.data
    if d["role"] != "leader":
        return
    token = token_of(world, d["faction"])
    seat = world.entity(d["faction"]).data.get("seat")
    if token is not None and holder(world, token) is None and lies_at(world, token) == seat:
        put(world, token, owner=event.actors[0])
    world.update_data(d["faction"], transmitted=None)


# --- a crisis begins (spec 4.2, 4.4, 4.5) -----------------------------------------------------

def at_mourning(world, crisis: dict, rng, far: bool = False) -> dict:
    """The will read or not, the token picked up at the seat, the transmission counted, the Grand Elder's choice."""
    faction = crisis["faction"]
    data = world.entity(faction).data
    fallen = data.get("fallen") or {}
    claimants = crisis["claimants"]
    crisis = {**crisis, "transmitted": data.get("transmitted")}
    chance = WILL_CHANCE["natural" if fallen.get("cause") in NATURAL else "other"]
    if rng.random() < chance and claimants:
        chief = next((c["person"] for c in claimants if c["kind"] == "chief"), None)
        names = chief if chief is not None else _favourite(world, crisis["leader"], claimants)
        roll, state = rng.random(), "read"
        for option, share in WILL_STATES:
            if roll < share:
                state = option
                break
            roll -= share
        others = [c["person"] for c in claimants if c["person"] != names]
        if state == "held" and not others:
            state = "hidden"
        crisis["will"] = {"state": state, "names": names, "holder": others[0] if state == "held" else None}
    else:
        crisis["will"] = {"state": "none", "names": None, "holder": None}
    token = ensure_token(world, faction)
    if holder(world, token) is None and lies_at(world, token) is None:
        put(world, token, place=data.get("seat"))  # made now (no leader fell with it): it rests in the hall
    if holder(world, token) is None and lies_at(world, token) == data.get("seat") and claimants:
        chief = next((c["person"] for c in claimants if c["kind"] == "chief"), claimants[0]["person"])
        put(world, token, owner=chief)
    crisis["token"] = token
    return crisis if far else _grand_elder(world, crisis, rng)  # far away no Grand Elder is made (spec 2.4)


def _favourite(world, leader, claimants: list[dict]) -> int | None:
    if leader is None:
        return claimants[0]["person"]
    return max(claimants, key=lambda c: (attitude(world, leader, c["person"]).score, -c["person"]))["person"]


def _grand_elder(world, crisis: dict, rng) -> dict:
    faction = world.entity(crisis["faction"])
    if faction.data.get("tier") != "great" or rng.random() >= EMERGE_CHANCE:
        return crisis
    elder = ensure_grand_elder(world, faction.id, crisis["leader"])
    if C.ambitious(world, elder):
        claimants = list(crisis["claimants"])
        if len(claimants) >= C.MAX_CLAIMANTS:
            claimants = claimants[:-1]
        return {**crisis, "claimants": claimants + [{"person": elder, "kind": "grand_elder"}], "grand_elder": elder}
    best = max(crisis["claimants"], key=lambda c: (C.lean(world, crisis, elder, c, full=False), -c["person"]))
    return {**crisis, "grand_elder": elder, "grand_elder_backs": best["person"]}


def ensure_grand_elder(world, faction: int, leader: int | None) -> int:
    """The elder in closed-door seclusion on the sect's mountain: made once, seeded (spec 4.2)."""
    path = f"world:{faction}:grand_elder"
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    rng = rng_for(world.world_seed, path)
    surname, given = person_name(rng)
    base = realm_index(world.entity(leader).data.get("realm", "mortal")) if leader is not None else 3
    realm = REALMS[min(len(REALMS) - 1, base + 1)].label
    traits = [rng.choice(("proud", "cautious", "loyal", "secretive", "cunning", "kind"))]
    data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": rng.randint(90, 140),
            "occupation": "grand elder", "traits": traits, "realm": realm, "secluded": True,
            "portrait": {"hair": 3, "face": rng.randrange(4), "robe": rng.randrange(4)}}
    person = world.add_entity("person", f"{surname} {given}", data, path)
    seat = world.entity(faction).data["seat"]
    world.relate(person, region_of(world, seat).id, "located_in")  # the back mountain: in no town's scene
    world.relate(person, faction, "member_of", 4, {"role": "grand_elder", "hall": None, "merit": 0,
                                                   "status": "member", "secret": False})
    return person


# --- the hidden will (spec 4.4) ---------------------------------------------------------------

def search_chance(world, person: int) -> float:
    return SEARCH_BASE + SEARCH_PER_REALM * max(0, realm_of(world, person) - 1)


def camps_search(world, crisis: dict, rng) -> dict:
    """At a stage's change, each camp may turn up a hidden will: read if it names them, kept if not."""
    will = crisis.get("will") or {}
    if will.get("state") != "hidden":
        return crisis
    for c in crisis["claimants"]:
        if alive(world, c["person"]) and rng.random() < CAMP_FIND:
            return {**crisis, "will": found_by(will, c["person"])}
    return crisis


def found_by(will: dict, person: int) -> dict:
    if will.get("names") == person:
        return {**will, "state": "read", "holder": None}
    return {**will, "state": "held", "holder": person}
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4g_task2.py`:
```python
"""Phase 4g, Task 2: the testament in the crisis, the token's rules, the Grand Elder kept from tournaments and the token from sale"""
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


edit('systems/succession_crisis.py', r'''import systems.sky as sky
import systems.world_events as W''', r'''import systems.sky as sky
import systems.testament as T
import systems.world_events as W''')
edit('systems/succession_crisis.py', r'''from world.events import Event, effect, listen''', r'''from world.events import Event, effect, listen
from world.seed import rng_for''')
edit('systems/succession_crisis.py', r'''    world.update_data(faction, crisis=row[W.ID], fallen=None)''', r'''    world.update_data(faction, crisis=row[W.ID], fallen=None)
    occurrence = world.entity(row[W.ID])
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:mourning")
    world.update_data(occurrence.id, data=T.at_mourning(world, crisis_of(occurrence), rng))''')
edit('systems/succession_crisis.py', r'''@effect("crisis_phase")
def _phase(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**crisis_of(occurrence), "phase": event.data["phase"]})''', r'''def _searched(world, occurrence, stage: str) -> None:
    """The camps turn the late master's rooms over at each stage's change (spec 4.4)."""
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:search:{stage}")
    world.update_data(occurrence.id, data=T.camps_search(world, crisis_of(occurrence), rng))


@effect("crisis_phase")
def _phase(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**crisis_of(occurrence), "phase": event.data["phase"]})
    _searched(world, world.entity(occurrence.id), event.data["phase"])''')
edit('tests/test_succession_crisis.py', r'''import systems.succession_crisis as SC
''', r'''import systems.succession_crisis as SC
import systems.testament as T
''')
edit('tests/test_succession_crisis.py', r'''    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
''', r'''    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)  # tests that want a transmission ask for one
''')
edit('debug/invariants.py', r'''            out.append(f"the {faction.name} points at #{pointed}, which is no live crisis of theirs")
    return out''', r'''            out.append(f"the {faction.name} points at #{pointed}, which is no live crisis of theirs")
    for token in world.entities("treasure"):
        if token.data.get("kind") == "sect_token":
            places = len(world.sources(token.id, "owns")) + len(world.targets(token.id, "located_in"))
            if places != 1:
                out.append(f"{token.name} is in {places} places")
    return out''')
edit('debug/invariants.py', r'''    for item in world.entities("treasure"):
        owners = world.sources(item.id, "owns")''', r'''    for item in world.entities("treasure"):
        if item.data.get("kind") == "sect_token":
            continue  # owned or lying where its leader fell: one place, as check_crises holds (4g)
        owners = world.sources(item.id, "owns")''')
edit('systems/tournaments.py', r'''    return bool(world.entity(person).data.get("sealed_in")) or any(''', r'''    return bool(world.entity(person).data.get("sealed_in")) or bool(world.entity(person).data.get("secluded")) or any(''')
edit('engine/sky.py', r'''        return [t for t in found if t is not None and t.kind == "treasure"]''', r'''        return [t for t in found if t is not None and t.kind == "treasure"
                and t.data.get("kind") != "sect_token"]  # a sect's token is no treasure to sell (4g)''')
print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4g_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_testament.py tests/test_succession_crisis.py`
Expected: `20 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: what the late master leaves - the leader's token, a deathbed transmission, the will read or hidden or held, the Grand Elder

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: The contest, the settlement, and crises far away

As the aftermath begins the contest is decided: a camp holding more than half of all votes takes the seat, else the two largest camps' champions meet in a trial (the player's trial waits for them, and is forfeit if they never come), and a proud loser may refuse. The winner is promoted, the losers remember, the faction's history gains a line. Far from the player a crisis is settled in a line. The tales name their claimants, and those names count as people the player has heard of.

**Files:**
- Create: `narrate/crisis_text.py`
- Create: `tests/test_crisis_contest.py`
- Modify (by `.patches/4g_task3.py`): `systems/succession_crisis.py`, `narrate/outcomes.py`, `systems/beliefs.py`

**Interfaces:**
- Consumes: Tasks 1-2: `C.camps`, `C.votes`, `C.proofs`, `C._best`, `T.at_mourning(far=True)`, `SC.begin_events`.
- Produces:
  - `SC`: `REFUSE_CHANCE`, `PROUD`, `TRIAL_BOUNDS`, `FAR_PROOF`, `FAR_REALM`, `champion`, `trial_chance(world, a, b)`, `decide_events(world, occurrence)`, `trial_events(world, occurrence, trial, winner, rng)`, `forfeit_events`, `settle_events(world, occurrence, winner, how)`, `_record`, `_told`; events `crisis_trial`, `crisis_refused`, `crisis_settled`, `crisis_lost`, `crisis_summarised`; the crisis's `phase` `contest`, `strife`, `settled`.
  - `narrate/crisis_text.py`: `KIND_WORDS`, `HOW_WORDS`, `names`, `claim_words(kind)`; stories for `crisis`, `named_chief`, `transmitted`.
  - `beliefs.known_people` reads a variant's `people`.

- [ ] **Step 1: Write the failing tests**

`tests/test_crisis_contest.py`:
```python
import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from debug.invariants import check_crises
from engine.game import Game
from narrate.gossip_text import rumour_text
from systems import factions as F
from systems import halls
from systems.beliefs import believe, known_people
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_town


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
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)


def a_sect(game, near=True):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    home = world.entity(seat).data
    where = seat if near else ensure_town(world, home["x"] + 6, home["y"] + 6, 0)
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, where, "located_in")
    return sect, seat


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def kill(world, person, place, cause="age"):
    commit(world, [Event("died", (person, person), place, {"cause": cause, "world": True})])


def a_season(game):
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)


def a_crisis(game, near=True):
    """The orthodox sect's chief disciple against a proud elder above them."""
    world = game.world
    sect, seat = a_sect(game, near)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["proud"])
    world.update_data(elders[1], traits=["kind"], realm="mortal")  # too weak to claim: two claimants, not three
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    a_season(game)
    return sect, seat, keeper, elders[0]


def to_contest(world, occurrence, seat):
    world.set_time(occurrence.data["ends"]["active"])
    sky.observe(world, seat)


def sway_all(world, occurrence, toward):
    crisis = SC.crisis_of(occurrence)
    sways = {str(v): {str(toward): 5.0} for v in C.voters(world, crisis["faction"])}
    world.update_data(occurrence.id, data={**crisis, "sways": sways})


def test_a_camp_with_a_majority_takes_the_seat(game):
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    occurrence = SC.live(world, sect)
    sway_all(world, occurrence, keeper)
    to_contest(world, occurrence, seat)
    assert staff(world, sect, seat, "leader") == [keeper]
    assert SC.live(world, sect) is None and world.entity(sect).data["crisis"] is None
    assert SC.crisis_of(world.entity(occurrence.id))["outcome"] == {"leader": keeper, "how": "backing", "schism": None}
    line = world.entity(sect).data["history"][-1]
    assert line["winner"] == keeper and line["how"] == "backing" and proud in line["claimants"]
    [told] = [f for f in world.facts(predicate="crisis") if f.data["variant"]["stage"] == "settled"]
    assert told.subject == keeper
    assert any(m.feeling == "wronged" for m in world.memories(proud, about=keeper))  # the loser remembers
    assert check_crises(world) == []


def test_without_a_majority_the_two_largest_camps_meet_in_a_trial(game, monkeypatch):
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 0.0)
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: ({keeper: [keeper], proud: [proud]}, [1, 2]))
    occurrence = SC.live(world, sect)
    to_contest(world, occurrence, seat)
    trial = SC.crisis_of(world.entity(occurrence.id))["trial"]
    assert {trial["a"], trial["b"]} == {keeper, proud} and trial["winner"] in (keeper, proud)
    assert staff(world, sect, seat, "leader") == [trial["winner"]]
    assert SC.crisis_of(world.entity(occurrence.id))["outcome"]["how"] == "trial"


def test_a_proud_loser_may_refuse_the_trial(game, monkeypatch):
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 1.0)
    monkeypatch.setattr(SC, "trial_chance", lambda world, a, b: 0.0)  # the second fighter always wins
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: ({keeper: [keeper], proud: [proud]}, [1, 2]))
    occurrence = SC.live(world, sect)
    to_contest(world, occurrence, seat)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["trial"]["winner"] == keeper  # the proud elder ranks first and loses
    assert crisis["phase"] == "strife" and crisis["strife"] == {"a": keeper, "b": proud, "seasons": 0}
    assert staff(world, sect, seat, "leader") == [] and SC.live(world, sect) is not None


def test_a_trial_the_player_must_fight_waits_and_is_forfeit_if_they_never_come(game, monkeypatch):
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 0.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud = a_crisis(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: ({keeper: [keeper], proud: [proud]}, [1, 2]))
    occurrence = SC.live(world, sect)
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "champions": {str(keeper): me}})
    to_contest(world, occurrence, seat)
    trial = SC.crisis_of(world.entity(occurrence.id))["trial"]
    assert trial["pending"] and trial["champions"][str(keeper)] == me
    assert staff(world, sect, seat, "leader") == []
    world.set_time(world.entity(occurrence.id).data["over_at"])
    sky.observe(world, seat)
    assert staff(world, sect, seat, "leader") == [proud]  # the player's side never came


def test_when_every_claimant_has_fallen_the_elders_choose(game):
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    occurrence = SC.live(world, sect)
    kill(world, keeper, seat)
    kill(world, proud, seat)
    to_contest(world, occurrence, seat)
    [leader] = staff(world, sect, seat, "leader")
    assert SC.crisis_of(world.entity(occurrence.id))["outcome"]["how"] == "chosen"


def test_a_crisis_far_from_the_player_is_settled_in_a_line(game):
    world = game.world
    sect, seat, keeper, proud = a_crisis(game, near=False)
    assert SC.live(world, sect) is None
    assert not [row for row in sky.W.index(world) if row[sky.W.TYPE] == SC.KIND]
    [leader] = staff(world, sect, seat, "leader")
    assert leader in (keeper, proud)
    line = world.entity(sect).data["history"][-1]
    assert line["how"] == "far" and line["winner"] == leader
    [told] = world.facts(predicate="crisis")
    assert told.data["variant"]["stage"] == "settled" and set(told.data["variant"]["people"]) == {keeper, proud}
    assert check_crises(world) == []


def test_the_tale_of_a_crisis_names_its_claimants(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud = a_crisis(game)
    sky.observe(world, seat)
    [fact] = world.facts(predicate="crisis")
    text = rumour_text(world, fact.data["variant"], me)
    assert "is without a master" in text and world.entity(keeper).name in text and world.entity(proud).name in text
    believe(world, me, fact.id, fact.data["variant"], None, 0.9, 1, "gossip")
    assert {keeper, proud} <= set(known_people(world, me))  # a tale's names are people the player has heard of


def test_two_sects_seated_in_one_town_each_get_their_crisis_or_their_line(game):
    """Review focus: one live crisis a town (4d); the second is settled in a line, never lost."""
    world = game.world
    sect, seat = a_sect(game)
    cult = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "demonic_cult")
    world.update_data(cult, seat=seat)
    for faction in (sect, cult):
        for leader in C.staff(world, faction, ("leader",)):
            kill(world, leader, seat, cause="killed")
    a_season(game)
    live = [f for f in (sect, cult) if SC.live(world, f) is not None]
    settled = [f for f in (sect, cult) if f not in live]
    assert len(live) <= 1
    for faction in settled:
        if C.staff(world, faction, ("elder",)):
            assert C.staff(world, faction, ("leader",)) or world.entity(faction).data.get("history")
    assert check_crises(world) == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crisis_contest.py`
Expected: 7 of 8 fail (`AttributeError: ... has no attribute 'REFUSE_CHANCE'`, `KeyError: 'history'`, the tale's words); `test_two_sects_seated_in_one_town_each_get_their_crisis_or_their_line` already passes (4a fills the second seat until the summary exists).

- [ ] **Step 3: Write the new modules**

`narrate/crisis_text.py`:
```python
"""What the player is told of succession crises (phase 4g spec 5): the tales, the kinds of claim, how seats were won."""

from narrate.outcomes import cap  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

KIND_WORDS = {"chief": "the chief disciple", "blood": "the late master's blood", "elder": "an elder",
              "grand_elder": "the Grand Elder, down from seclusion", "regent": "a regent", "player": "a claimant"}
HOW_WORDS = {"backing": "with the elders behind them", "trial": "by trial of arms", "unopposed": "unopposed",
             "chosen": "chosen by the elders", "far": "after a bitter contest", "strife": "by force of arms",
             "stepped_down": "named by the old master", "regency": "as regent"}


def names(world, people, viewer: int) -> str:
    said = [who(world, p, viewer) for p in people]
    return said[0] if len(said) == 1 else ", ".join(said[:-1]) + " and " + said[-1] if said else "no one"


def _faction(world, variant) -> str:
    faction = world.entity(variant.get("target")) if variant.get("target") is not None else None
    return f"the {faction.name}" if faction is not None else "a sect"


def _crisis_story(world, variant, viewer) -> str:
    sect = _faction(world, variant)
    if variant.get("stage") == "settled":
        how = HOW_WORDS.get(variant.get("how"), "")
        return cap(f"{who(world, variant.get('actor'), viewer)} now leads {sect}{', ' + how if how else ''}.")
    return cap(f"{sect} is without a master: {names(world, variant.get('people') or [variant.get('actor')], viewer)} "
               f"each claim the seat.")


def _named_chief_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} was named chief disciple of {_faction(world, variant)}.")


def _transmitted_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)}, dying, poured their inner strength into "
               f"{who(world, variant.get('target'), viewer)}.")



SPECIAL_PHRASES.update({"crisis": _crisis_story, "named_chief": _named_chief_story,
                        "transmitted": _transmitted_story})


def claim_words(kind: str) -> str:
    return KIND_WORDS.get(kind, "a claimant")
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4g_task3.py`:
```python
"""Phase 4g, Task 3: the contest, the settlement and the summary far away; the tales and the names they carry"""
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


edit('systems/succession_crisis.py', r'''import systems.claimants as C
import systems.sky as sky''', r'''import systems.claimants as C
import systems.lives as lives
import systems.sky as sky''')
edit('systems/succession_crisis.py', r'''from world.events import Event, effect, listen''', r'''from systems.world_clock import _promotion
from world.events import Event, Witness, commit, effect, listen''')
edit('systems/succession_crisis.py', r'''    seat = world.entity(faction).data["seat"]
    if not force and not near(world, faction):
        return None  # far from the player: 4a's handover, until Task 3 settles it in a line''', r'''    seat = world.entity(faction).data["seat"]
    summary = [Event("crisis_summarised", (), seat, {"faction": faction, "season": n, "cause": cause,
                                                      "leader": leader, "claimants": claimants})]
    if not force and not near(world, faction):
        return summary  # far from the player: settled in a line (spec 2.4)''')
edit('systems/succession_crisis.py', r'''    return sky.start_events(world, KIND, seat, starts, crisis) or None  # long over: 4a's handover after all''', r'''    return sky.start_events(world, KIND, seat, starts, crisis) or summary  # long over: settled in a line''')
edit('systems/succession_crisis.py', r'''                 force: bool = False) -> list[Event] | None:''', r'''                 force: bool = False) -> list[Event]:''')
edit('systems/succession_crisis.py', r'''        return [Event("crisis_phase", (), occurrence.data["place"], {"occurrence": occurrence.id, "phase": "canvass"})]
    return []''', r'''        return [Event("crisis_phase", (), occurrence.data["place"], {"occurrence": occurrence.id, "phase": "canvass"})]
    if stage == "aftermath":
        return [Event("crisis_phase", (), occurrence.data["place"], {"occurrence": occurrence.id, "phase": "contest"})]
    if stage == "over" and (crisis.get("trial") or {}).get("pending"):
        return forfeit_events(world, occurrence)  # the days passed and the player never came to the trial
    return []''')
append('systems/succession_crisis.py', r'''

# --- the contest (spec 4.6, 4.9) --------------------------------------------------------------

REFUSE_CHANCE = 0.5
PROUD = frozenset({"proud", "hot-tempered"})
TRIAL_BOUNDS = (0.1, 0.9)
FAR_PROOF, FAR_REALM = 0.5, 0.3


@listen("crisis_phase")
def _contest(world, event, event_id: int) -> None:
    if event.data["phase"] == "contest":
        commit(world, decide_events(world, world.entity(event.data["occurrence"])))


def champion(world, crisis: dict, person: int, camp: list[int]) -> int:
    """Who fights for a claimant: whom they named (the player, spec 6.2), the player if the claimant,
    else the strongest of the camp."""
    named = crisis.get("champions", {}).get(str(person))
    if named is not None and alive(world, named):
        return named
    if world.entity(person).data.get("is_player"):
        return person
    fighters = [p for p in camp if not world.entity(p).data.get("is_player") and alive(world, p)] or [person]
    return max(fighters, key=lambda p: (realm_of(world, p), p == person, -p))


def trial_chance(world, a: int, b: int) -> float:
    """The first fighter's chance: realm decides, with upsets (4e plan ruling 7)."""
    low, high = TRIAL_BOUNDS
    return max(low, min(high, 0.5 + 0.15 * (realm_of(world, a) - realm_of(world, b))))


def decide_events(world, occurrence) -> list[Event]:
    """The contest: a camp with more than half of all votes takes the seat; else the two largest fight."""
    crisis, place = crisis_of(occurrence), occurrence.data["place"]
    if crisis["phase"] != "contest":
        return []
    standing = standing_claimants(world, crisis)
    if len(standing) <= 1:
        return settle_events(world, occurrence, standing[0]["person"] if standing else None, "unopposed")
    backing, undecided = C.camps(world, crisis)
    tally = C.votes(world, crisis, {c["person"]: backing[c["person"]] for c in standing})
    total = sum(tally.values()) + len(undecided)
    ranked = sorted(tally, key=lambda p: (-tally[p], -realm_of(world, p), p))
    if tally[ranked[0]] * 2 > total:
        return settle_events(world, occurrence, ranked[0], "backing")
    a, b = ranked[:2]
    fighters = {str(a): champion(world, crisis, a, backing[a]), str(b): champion(world, crisis, b, backing[b])}
    trial = {"a": a, "b": b, "champions": fighters, "winner": None, "pending": False}
    player = world.get_meta("player_id")
    if player in fighters.values():
        return [Event("crisis_trial", (), place, {"occurrence": occurrence.id, "trial": {**trial, "pending": True}})]
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:trial")
    winner = a if rng.random() < trial_chance(world, fighters[str(a)], fighters[str(b)]) else b
    return trial_events(world, occurrence, trial, winner, rng)


def trial_events(world, occurrence, trial: dict, winner: int, rng) -> list[Event]:
    """The trial fought: the winner takes the seat, unless a proud loser refuses (then force of arms, Task 4)."""
    place = occurrence.data["place"]
    loser = trial["b"] if winner == trial["a"] else trial["a"]
    fighters = (trial["champions"][str(winner)], trial["champions"][str(loser)])
    events = [Event("crisis_trial", fighters, place,
                    {"occurrence": occurrence.id, "trial": {**trial, "winner": winner, "pending": False}})]
    if PROUD & set(world.entity(loser).data.get("traits", ())) and rng.random() < REFUSE_CHANCE:
        return events + [Event("crisis_refused", (loser, winner), place, {"occurrence": occurrence.id})]
    return events + settle_events(world, occurrence, winner, "trial")


def forfeit_events(world, occurrence) -> list[Event]:
    """The player's side never came to the trial: the other side wins it."""
    trial = crisis_of(occurrence)["trial"]
    player = world.get_meta("player_id")
    winner = trial["b"] if trial["champions"][str(trial["a"])] == player else trial["a"]
    return trial_events(world, occurrence, trial, winner, rng_for(world.world_seed, f"crisis:{occurrence.id}:forfeit"))


@effect("crisis_trial")
def _trial(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**crisis_of(occurrence), "trial": event.data["trial"]})


@effect("crisis_refused")
def _refused(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**crisis_of(occurrence), "phase": "strife",
                                           "strife": {"a": event.actors[1], "b": event.actors[0], "seasons": 0}})


def settle_events(world, occurrence, winner, how: str) -> list[Event]:
    """The seat is filled: the winner leads, each other claimant remembers who beat them (spec 4.9)."""
    crisis, place = crisis_of(occurrence), occurrence.data["place"]
    faction = crisis["faction"]
    if winner is None:  # every claimant fell: the elders put forward one of their own
        winner = C._best(world, C.staff(world, faction, ("elder",)) or C.staff(world, faction, ("keeper",)))
        how = "chosen"
    losers = [c["person"] for c in crisis["claimants"] if c["person"] != winner and alive(world, c["person"])]
    events = [Event("crisis_settled", (winner,) if winner is not None else (), place,
                    {"occurrence": occurrence.id, "faction": faction, "winner": winner, "how": how, "losers": losers})]
    if winner is None:
        return events
    events += [Event("crisis_lost", (winner, loser), place, {"faction": faction},
                     witnesses=(Witness(loser, "wronged", 0.6),)) for loser in losers]
    return events + [_promotion(world, winner, faction, "leader", 4, None)]


@effect("crisis_settled")
def _settled(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    crisis = crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "phase": "settled",
                                           "outcome": {"leader": d["winner"], "how": d["how"], "schism": None}})
    _record(world, d["faction"], crisis["claimants"], d["winner"], d["how"])
    world.update_data(d["faction"], crisis=None)


def _record(world, faction: int, claimants: list[dict], winner, how: str, schism=None) -> None:
    data = world.entity(faction).data
    line = {"season": lives.current_season(world), "claimants": [c["person"] for c in claimants],
            "winner": winner, "how": how, "schism": schism}
    world.update_data(faction, history=list(data.get("history", [])) + [line], fallen=None)


@listen("crisis_settled")
def _settled_news(world, event, event_id: int) -> None:
    d = event.data
    crisis = crisis_of(world.entity(d["occurrence"]))
    _told(world, event.place, event_id, d["winner"], d["faction"], [c["person"] for c in crisis["claimants"]], d["how"])


def _told(world, place: int, event_id: int, winner, faction: int, people: list[int], how: str) -> None:
    if winner is None:
        return
    variant = make_variant("crisis", winner, faction, place=place_name(world, place))
    variant.update(stage="settled", people=people, how=how)
    record_fact(world, winner, "crisis", faction, place=place, source_event=event_id, weight=2.5, variant=variant)


# --- far away (spec 2.4, 4.6) -----------------------------------------------------------------

@listen("crisis_summarised")
def _summarised(world, event, event_id: int) -> None:
    """Nobody near: the crisis is settled in a line, weighed by proofs and realms."""
    d = event.data
    faction, rng = d["faction"], rng_for(world.world_seed, f"crisis:{d['faction']}:{d['season']}:far")
    crisis = T.at_mourning(world, {"faction": faction, "leader": d["leader"], "claimants": d["claimants"]}, rng,
                           far=True)
    standing = standing_claimants(world, crisis)
    if not standing:
        return
    weakest = min(realm_of(world, c["person"]) for c in standing)
    weights = [1 + FAR_PROOF * len(C.proofs(world, crisis, c)) + FAR_REALM * (realm_of(world, c["person"]) - weakest)
               for c in standing]
    winner = rng.choices([c["person"] for c in standing], weights=weights)[0]
    losers = [c["person"] for c in standing if c["person"] != winner]
    commit(world, [Event("crisis_lost", (winner, loser), event.place, {"faction": faction},
                         witnesses=(Witness(loser, "wronged", 0.6),)) for loser in losers]
           + [_promotion(world, winner, faction, "leader", 4, None)])
    _record(world, faction, d["claimants"], winner, "far")
    _told(world, event.place, event_id, winner, faction, [c["person"] for c in d["claimants"]], "far")
''')
edit('narrate/outcomes.py', r'''import narrate.realm_text  # noqa: E402,F401
''', r'''import narrate.realm_text  # noqa: E402,F401
import narrate.crisis_text  # noqa: E402,F401
''')
edit('systems/beliefs.py', r'''        for someone in (belief.variant.get("actor"), belief.variant.get("target")):
            if someone is not None and someone != player_id and someone not in seen:
                seen.append(someone)''', r'''        for someone in (belief.variant.get("actor"), belief.variant.get("target"), *belief.variant.get("people", ())):
            if someone is not None and someone != player_id and someone not in seen:
                seen.append(someone)  # `people`: everyone a tale names, as a crisis's claimants (phase 4g)''')
print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4g_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crisis_contest.py tests/test_testament.py tests/test_succession_crisis.py`
Expected: `28 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the contest - backing, trial by combat, a proud refusal, the seat filled, crises far away settled in a line

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: Strife and schism

A refused trial is force of arms: each season on the faction clock the camps clash (the loser loses a backer), the weaker may yield, and after two seasons the losing camp walks out to found a breakaway sect (`Southern ...`, `True ...`), hostile to the old one, within the caps; past them the losers are exiled. Far away a close contest may do the same.

**Files:**
- Create: `systems/schism.py`
- Create: `tests/test_schism.py`
- Modify (by `.patches/4g_task4.py`): `systems/succession_crisis.py`, `systems/world_clock.py`, `engine/standing_page.py`, `debug/invariants.py`, `narrate/crisis_text.py`

**Interfaces:**
- Consumes: Task 3: `SC.settle_events`, `SC.crisis_of`, the `crisis_refused` phase `strife` with `strife = {a, b, seasons}`; `C.camps`.
- Produces:
  - `schism`: `STRIFE_SEASONS`, `YIELD`, `PREFIXES`, `MAX_BREAKAWAYS`, `MAX_MINORS`, `STANCE`, `FAR_STRIFE`, `FAR_GAP`, `FAR_SCHISM`, `strength`, `strife_camps`, `strife_events(world, n)` (a season hook), `season_of_strife`, `breakaways(world, f)`, `schism_events(world, f, place, loser, winner, camp, key, occurrence=None)`, `far_strife(...)`; events `strife_clash`, `schism`, `exiled`; faction data `parent`.
  - `known_factions` reads a variant's `factions`.

- [ ] **Step 1: Write the failing tests**

`tests/test_schism.py`:
```python
import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.schism as schism
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from debug.invariants import check_crises
from engine.game import Game
from engine.standing_page import known_factions
from narrate.gossip_text import rumour_text
from systems import factions as F
from systems import founding, halls
from systems.beliefs import believe
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_town, region_of


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
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)


def a_sect(game, near=True):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    home = world.entity(seat).data
    where = seat if near else ensure_town(world, home["x"] + 6, home["y"] + 6, 0)
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, where, "located_in")
    return sect, seat


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def kill(world, person, place, cause="age"):
    commit(world, [Event("died", (person, person), place, {"cause": cause, "world": True})])


def a_season(game):
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)


def one_season(game):
    """Exactly one season of the faction clock, whatever the time."""
    clock.run_season(game.world, clock.world_tick(game.world) + 1)


def backer(world, sect, seat, i):
    person = founding.make_person(world, f"test:backer:{i}", seat, occupation="wandering swordsman", age=30,
                                  realm="second-rate")
    world.relate(person, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 0, "status": "member",
                                                "secret": False})
    return person


def at_war(game, monkeypatch, near=True):
    """The chief disciple wins the trial; the proud elder refuses it: the camps go to war."""
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 1.0)
    monkeypatch.setattr(SC, "trial_chance", lambda world, a, b: 0.0)
    world = game.world
    sect, seat = a_sect(game, near)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["proud"])
    world.update_data(elders[1], traits=["kind"], realm="mortal")
    proud = elders[0]
    ours, theirs = [backer(world, sect, seat, i) for i in range(3)], [backer(world, sect, seat, i + 3) for i in range(3)]
    camps = {keeper: [keeper] + ours, proud: [proud] + theirs}
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {k: [p for p in v if not world.entity(p).data.get("dead")] for k, v in camps.items()}, [1, 2]))
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    a_season(game)
    occurrence = SC.live(world, sect)
    world.set_time(occurrence.data["ends"]["active"])
    sky.observe(world, seat)
    assert SC.crisis_of(world.entity(occurrence.id))["phase"] == "strife"
    return sect, seat, keeper, proud, theirs, occurrence


def test_a_camp_that_yields_ends_the_strife(game, monkeypatch):
    monkeypatch.setattr(schism, "YIELD", (1.0, 1.0))
    world = game.world
    sect, seat, keeper, proud, theirs, occurrence = at_war(game, monkeypatch)
    one_season(game)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["phase"] == "settled" and crisis["outcome"]["how"] == "strife"
    assert crisis["strife"]["seasons"] == 1
    [leader] = staff(world, sect, seat, "leader")
    assert leader in (keeper, proud)
    assert world.entity(sect).data["crisis"] is None and check_crises(world) == []


def test_a_clash_can_cost_the_losing_camp_a_backer(game, monkeypatch):
    monkeypatch.setattr(schism, "YIELD", (0.0, 0.0))
    monkeypatch.setattr(schism, "KILL_CHANCE", 1.0)
    world = game.world
    sect, seat, keeper, proud, theirs, occurrence = at_war(game, monkeypatch)
    one_season(game)
    [clash] = world.chronicle_of_kind("strife_clash")
    victim = clash.data["victim"]
    assert victim is not None and world.entity(victim).data.get("dead")


def test_two_seasons_of_strife_split_the_sect(game, monkeypatch):
    monkeypatch.setattr(schism, "YIELD", (0.0, 0.0))
    monkeypatch.setattr(schism, "KILL_CHANCE", 0.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, theirs, occurrence = at_war(game, monkeypatch)
    one_season(game)
    one_season(game)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    new = crisis["outcome"]["schism"]
    assert crisis["phase"] == "settled" and new is not None
    breakaway = world.entity(new)
    old = world.entity(sect)
    loser = proud if staff(world, sect, seat, "leader") == [keeper] else keeper
    assert breakaway.data["parent"] == sect and breakaway.data["tier"] == "minor"
    assert breakaway.name.endswith(old.name) and breakaway.name.split(" ")[0] in schism.PREFIXES
    assert F.membership(world, loser, new)[1]["role"] == "leader" and F.membership(world, loser, new)[0] == 4
    assert F.membership(world, loser, sect)[1]["status"] == "released"
    assert F.stance(world, sect, new) == schism.STANCE and F.stance(world, new, sect) == schism.STANCE
    assert new in region_of(world, breakaway.data["seat"]).data["minors"]
    assert old.data["history"][-1]["schism"] == new
    [fact] = world.facts(predicate="schism")
    believe(world, me, fact.id, fact.data["variant"], None, 0.9, 1, "gossip")
    assert breakaway.name in rumour_text(world, fact.data["variant"], me)
    assert new in known_factions(world, me, seat)  # a tale's new sect is one the player has heard of
    assert check_crises(world) == []


def test_past_the_caps_the_losers_are_exiled(game, monkeypatch):
    monkeypatch.setattr(schism, "YIELD", (0.0, 0.0))
    monkeypatch.setattr(schism, "KILL_CHANCE", 0.0)
    monkeypatch.setattr(schism, "MAX_BREAKAWAYS", 0)
    world = game.world
    sect, seat, keeper, proud, theirs, occurrence = at_war(game, monkeypatch)
    one_season(game)
    one_season(game)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["outcome"]["schism"] is None
    [exile] = world.chronicle_of_kind("exiled")
    loser = exile.actors[0]
    assert F.membership(world, loser, sect)[1]["status"] == "released"
    assert world.entity(loser).data["occupation"] == "wandering swordsman"


def test_a_close_contest_far_away_may_split_the_sect(game, monkeypatch):
    monkeypatch.setattr(schism, "FAR_STRIFE", 1.0)
    monkeypatch.setattr(schism, "FAR_GAP", 99.0)
    monkeypatch.setattr(schism, "FAR_SCHISM", 1.0)
    world = game.world
    sect, seat = a_sect(game, near=False)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["proud"])
    world.update_data(elders[1], traits=["kind"], realm="mortal")
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    one_season(game)
    [new] = schism.breakaways(world, sect)
    assert world.entity(sect).data["history"][-1]["schism"] == new
    assert check_crises(world) == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_schism.py`
Expected: `ModuleNotFoundError: No module named 'systems.schism'`.

- [ ] **Step 3: Write the new modules**

`systems/schism.py`:
```python
"""Force of arms and schism (phase 4g spec 4.7, 4.8): camps that will not yield fight season by season,
and a war that drags on splits the sect.

Strife runs on the faction clock (a season hook). A camp that loses a clash loses a backer: dead at 4a's
kill rate, or gone home (plan ruling 7). The weaker camp may yield; after two seasons the losers walk out
and found a breakaway sect, within the caps, or are exiled.
"""

import systems.claimants as C
import systems.succession_crisis as SC
import systems.world_clock as world_clock
import systems.world_events as W
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.tournaments import alive, realm_of
from systems.wars import KILL_CHANCE
from world.events import Event, Witness, commit, effect, listen  # commit: the far hook
from world.gen.materialize import region_of
from world.seed import rng_for

STRIFE_SEASONS = 2
YIELD = (0.3, 0.6)  # the weaker camp yields after the first clash, after the second
PREFIXES = ("Southern", "Northern", "Eastern", "Western", "True", "New")
MAX_BREAKAWAYS = 2  # from any one faction
MAX_MINORS = 4  # minor factions in one region: past it the losers are exiled (plan ruling 8)
STANCE = -0.8
FAR_STRIFE, FAR_GAP, FAR_SCHISM = 0.2, 0.5, 0.5


# --- strife, a season at a time (spec 4.7) ----------------------------------------------------

def strength(world, camp: list[int]) -> int:
    return sum(realm_of(world, p) + 1 for p in camp if alive(world, p))


def strife_camps(world, crisis: dict) -> dict[int, list[int]]:
    """The two camps at war: each claimant's backers as last settled, less those gone home."""
    backing, _ = C.camps(world, crisis)
    gone = set(crisis["strife"].get("gone", []))
    return {side: [p for p in backing.get(side, [side]) if p not in gone and alive(world, p)]
            for side in (crisis["strife"]["a"], crisis["strife"]["b"])}


def strife_events(world, n: int) -> list[Event]:
    """Each faction's crisis at war fights once a season (a faction clock hook)."""
    events = []
    for row in W.index(world):
        if row[W.TYPE] != SC.KIND:
            continue
        occurrence = world.entity(row[W.ID])
        crisis = SC.crisis_of(occurrence)
        if crisis["phase"] == "strife" and crisis["strife"].get("season") != n:
            events += season_of_strife(world, occurrence, n)
    return events


def season_of_strife(world, occurrence, n: int) -> list[Event]:
    crisis, place = SC.crisis_of(occurrence), occurrence.data["place"]
    strife = crisis["strife"]
    a, b = strife["a"], strife["b"]
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:strife:{n}")
    if not alive(world, a) or not alive(world, b):  # a claimant fell: the other takes the seat
        return SC.settle_events(world, occurrence, a if alive(world, a) else b if alive(world, b) else None, "strife")
    camps = strife_camps(world, crisis)
    sa, sb = strength(world, camps[a]), strength(world, camps[b])
    winner, loser = (a, b) if rng.random() < (sa / (sa + sb) if sa + sb else 0.5) else (b, a)
    fallen = [p for p in camps[loser] if p != loser]
    victim = max(fallen, key=lambda p: (realm_of(world, p), -p)) if fallen else None
    seasons = strife["seasons"] + 1
    events = [Event("strife_clash", (winner, loser), place,
                    {"occurrence": occurrence.id, "season": n, "victim": victim,
                     "dies": victim is not None and rng.random() < KILL_CHANCE})]
    if events[0].data["dies"]:
        killer = max(camps[winner], key=lambda p: (realm_of(world, p), -p))
        events.append(Event("died", (killer, victim), place, {"cause": "clash", "world": True}))
    left = [p for p in camps[loser] if p != victim]
    weaker = loser if strength(world, left) <= strength(world, camps[winner]) else winner
    other = a if weaker == b else b
    if len(left) <= 1 and weaker == loser or rng.random() < YIELD[min(seasons, STRIFE_SEASONS) - 1]:
        return events + SC.settle_events(world, occurrence, other, "strife")
    if seasons >= STRIFE_SEASONS:
        split = schism_events(world, crisis["faction"], place, weaker, other, camps[weaker], str(occurrence.id),
                              occurrence.id)
        return events + split + SC.settle_events(world, occurrence, other, "strife")
    return events


@effect("strife_clash")
def _clash(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    strife = dict(crisis["strife"])
    strife.update(seasons=strife["seasons"] + 1, season=event.data["season"])
    if event.data["victim"] is not None and not event.data["dies"]:
        strife["gone"] = list(strife.get("gone", [])) + [event.data["victim"]]  # beaten, they go home
    world.update_data(occurrence.id, data={**crisis, "strife": strife})


# --- schism (spec 4.8) ------------------------------------------------------------------------

def breakaways(world, faction: int) -> list[int]:
    return [f.id for f in world.entities("faction") if f.data.get("parent") == faction]


def _name(world, faction: int, rng) -> str | None:
    used = {f.name for f in world.entities("faction")}
    old = world.entity(faction).name
    for prefix in rng.sample(PREFIXES, len(PREFIXES)):
        name = f"{prefix} {old}"
        if name not in used:
            return name
    return None


def schism_events(world, faction: int, place: int, loser: int, winner: int, camp: list[int], key: str,
                  occurrence: int | None = None) -> list[Event]:
    """The losing camp walks out: a breakaway sect, or exile past the caps."""
    followers = sorted(p for p in camp if p != loser and alive(world, p))
    rng = rng_for(world.world_seed, f"crisis:{key}:schism")
    region = region_of(world, place)
    name = _name(world, faction, rng)
    full = len(breakaways(world, faction)) >= MAX_BREAKAWAYS or len(region.data.get("minors", [])) >= MAX_MINORS
    grudge = (Witness(loser, "hatred", 0.8, True), Witness(winner, "hatred", 0.8, True))
    if full or name is None:
        return [Event("exiled", (loser, winner), place, {"occurrence": occurrence, "faction": faction,
                                                        "followers": followers}, witnesses=grudge)]
    towns = [t for t in world.entity(faction).data.get("branches", [])
             if any(C.role_in(world, p, faction) == "keeper" and world.targets(p, "located_in") == [t]
                    for p in followers)]
    return [Event("schism", (loser, winner), place, {"occurrence": occurrence, "key": key, "faction": faction,
                                                     "name": name, "followers": followers, "halls": towns,
                                                     "region": region.id}, witnesses=grudge)]


@effect("schism")
def _schism(world, event) -> None:
    loser, _ = event.actors
    d = event.data
    old = world.entity(d["faction"])
    seat = d["halls"][0] if d["halls"] else world.targets(loser, "located_in")[0]
    seat_town = world.entity(seat)
    if seat_town.kind != "town":
        seat = old.data["seat"]
        seat_town = world.entity(seat)
    power = min(60, 25 + 5 * len(d["followers"]))
    data = {"type": old.data["type"], "tier": "minor", "home": [seat_town.data["x"], seat_town.data["y"]],
            "seat": seat, "path": old.data["path"], "ranks": list(old.data["ranks"]), "power": power,
            "base_power": power, "wealth": 20, "treasury": 100, "forms": list(old.data.get("forms", [])),
            "arts": list(old.data.get("arts", [])), "branches": [t for t in d["halls"] if t != seat],
            "parent": old.id}
    new = world.add_entity("faction", d["name"], data, f"schism:{d['key']}")
    for town in d["halls"]:
        town_data = world.entity(town).data
        world.update_data(town, halls=[f for f in town_data.get("halls", []) if f != old.id] + [new])
    here = world.entity(seat).data
    world.update_data(seat, halls=list(dict.fromkeys([*here.get("halls", []), new])),
                      seats=[*here.get("seats", []), new])
    world.update_data(old.id, branches=[t for t in old.data.get("branches", []) if t not in d["halls"]])
    for person, rank, role in [(loser, 4, "leader")] + [(p, *_post(world, p, old.id)) for p in d["followers"]]:
        if F.membership(world, person, old.id):
            set_membership(world, person, old.id, status="released")
        world.relate(person, new, "member_of", rank, {"role": role, "hall": None, "merit": 0, "status": "member",
                                                     "secret": False})
        if not world.entity(person).data.get("is_player"):
            world.update_data(person, occupation=F.title(world, new, rank) if role != "keeper" else "hall keeper")
    region = world.entity(d["region"])
    minors = list(region.data.get("minors", []))
    F._set_stances(world, [new], F.ensure_roster(world) + minors)
    world.relate(new, old.id, "stance", STANCE)
    world.relate(old.id, new, "stance", STANCE)
    world.update_data(region.id, minors=[*minors, new])
    if d["occurrence"] is not None:
        crisis = SC.crisis_of(world.entity(d["occurrence"]))
        world.update_data(d["occurrence"], data={**crisis, "breakaway": new})
    else:  # far away the history line is already written: it gains its schism
        history = list(old.data.get("history", []))
        if history:
            world.update_data(old.id, history=history[:-1] + [{**history[-1], "schism": new}])


def _post(world, person: int, faction: int) -> tuple[int, str]:
    found = F.membership(world, person, faction)
    rank, role = (found[0], found[1].get("role")) if found else (1, "disciple")
    if world.entity(person).data.get("is_player"):
        return rank, "member"  # the player walks out as what they were
    return (rank, role) if role in ("elder", "keeper", "disciple") else (1, "disciple")


@effect("exiled")
def _exiled(world, event) -> None:
    loser, _ = event.actors
    for person in [loser] + list(event.data["followers"]):
        if F.membership(world, person, event.data["faction"]):
            set_membership(world, person, event.data["faction"], status="released")
        world.update_data(person, occupation="wandering swordsman")


@listen("schism")
def _schism_news(world, event, event_id: int) -> None:
    loser, winner = event.actors
    new = world.entity_by_seed(f"schism:{event.data['key']}").id
    variant = make_variant("schism", loser, event.data["faction"], place=place_name(world, event.place))
    variant.update(people=[winner], factions=[new])
    record_fact(world, loser, "schism", event.data["faction"], place=event.place, source_event=event_id, weight=3.0,
                variant=variant, extra={"breakaway": new})


@listen("exiled")
def _exiled_news(world, event, event_id: int) -> None:
    loser, winner = event.actors
    variant = make_variant("exiled", loser, event.data["faction"], place=place_name(world, event.place))
    variant.update(people=[winner])
    record_fact(world, loser, "exiled", event.data["faction"], place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


@listen("crisis_settled")
def _schism_recorded(world, event, event_id: int) -> None:
    """The history line and the outcome say whether the sect split (spec 4.9)."""
    crisis = SC.crisis_of(world.entity(event.data["occurrence"]))
    new = crisis.get("breakaway")
    if new is None:
        return
    world.update_data(event.data["occurrence"], data={**crisis, "outcome": {**crisis["outcome"], "schism": new}})
    history = list(world.entity(crisis["faction"]).data.get("history", []))
    if history:
        world.update_data(crisis["faction"], history=history[:-1] + [{**history[-1], "schism": new}])


def far_strife(world, event, crisis: dict, standing: list[dict], weights: list[float], winner: int, rng) -> None:
    """Far away, a close contest may come to arms, and half of those split the sect (spec 4.6, plan ruling 9)."""
    ranked = sorted(zip(weights, [c["person"] for c in standing]), reverse=True)
    if len(ranked) < 2 or ranked[0][0] - ranked[1][0] > FAR_GAP or rng.random() >= FAR_STRIFE \
            or rng.random() >= FAR_SCHISM:
        return
    loser = next(p for _, p in ranked if p != winner)
    backing, _ = C.camps(world, crisis, full=False)
    d = event.data
    commit(world, schism_events(world, d["faction"], event.place, loser, winner, backing.get(loser, [loser]),
                                f"far:{d['faction']}:{d['season']}"))


world_clock.SEASON_HOOKS.append(strife_events)
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4g_task4.py`:
```python
"""Phase 4g, Task 4: strife on the clock, breakaways in the world, their tales, the breakaway cap"""
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


edit('systems/succession_crisis.py', r'''    _told(world, event.place, event_id, winner, faction, [c["person"] for c in d["claimants"]], "far")
''', r'''    _told(world, event.place, event_id, winner, faction, [c["person"] for c in d["claimants"]], "far")
    from systems.schism import far_strife  # a close contest far away may come to arms (Task 4)
    far_strife(world, event, crisis, standing, weights, winner, rng)
''')
edit('systems/world_clock.py', r'''import systems.rankings  # noqa: E402,F401  phase 4d: the Pavilion's informants and yearly lists''', r'''import systems.rankings  # noqa: E402,F401  phase 4d: the Pavilion's informants and yearly lists
import systems.schism  # noqa: E402,F401  phase 4g: strife between a crisis's camps, season by season''')
edit('engine/standing_page.py', r'''        for named in (belief.variant.get("actor"), belief.variant.get("target")):  # "the X beat the Y" names both''', r'''        for named in (belief.variant.get("actor"), belief.variant.get("target"), *belief.variant.get("factions", ())):''')
edit('debug/invariants.py', r'''    for token in world.entities("treasure"):
        if token.data.get("kind") == "sect_token":''', r'''    parents: dict = {}
    for faction in world.entities("faction"):
        if faction.data.get("parent") is not None:
            parents[faction.data["parent"]] = parents.get(faction.data["parent"], 0) + 1
    for parent, count in parents.items():
        if count > 2:
            out.append(f"the {world.entity(parent).name} has {count} breakaways")
    for token in world.entities("treasure"):
        if token.data.get("kind") == "sect_token":''')
edit('narrate/crisis_text.py', r'''SPECIAL_PHRASES.update({"crisis": _crisis_story, "named_chief": _named_chief_story,
                        "transmitted": _transmitted_story})''', r'''def _schism_story(world, variant, viewer) -> str:
    new = world.entity((variant.get("factions") or [None])[0]) if variant.get("factions") else None
    founded = f" and founded the {new.name}" if new is not None else ""
    return cap(f"{who(world, variant.get('actor'), viewer)} walked out of {_faction(world, variant)} with their "
               f"followers{founded}.")


def _exiled_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} lost the war for the seat of {_faction(world, variant)} "
               f"and was driven out.")


SPECIAL_PHRASES.update({"crisis": _crisis_story, "named_chief": _named_chief_story,
                        "transmitted": _transmitted_story, "schism": _schism_story, "exiled": _exiled_story})''')
print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4g_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_schism.py tests/test_crisis_contest.py`
Expected: `13 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: force of arms - camps at war season by season, a yield or a schism, breakaway sects and exiles

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: The player in a crisis

At the seat of a sect they belong to, while its crisis lives, the player may claim the seat (rank 2 or more, or the named heir), declare for a claimant (and change camps once), sway voters by word, gift, threat or favour (once a voter a stage), offer to be a camp's champion and fight its trial, search the late master's chambers and read out or burn the will, challenge a holder for the will; anywhere they may pick up, buy, win or hand over a leader's token. Winning makes them the sect's leader.

**Files:**
- Create: `engine/crisis.py`
- Create: `narrate/grammar/crisis.toml`
- Create: `systems/crisis_play.py`
- Create: `tests/test_crisis_play.py`
- Modify (by `.patches/4g_task5.py`): `narrate/crisis_text.py`, `engine/game.py`, `systems/ranks.py`, `tests/test_ranks.py`, `debug/invariants.py`

**Interfaces:**
- Consumes: Tasks 1-4: `SC` (`live`, `crisis_of`, `claimant`, `standing_claimants`, `trial_events`), `C` (`voters`, `camps`), `T` (`holder`, `put`, `search_chance`, `TOKEN_PRICE`), `duties.issue_events`.
- Produces:
  - `crisis_play` (P): `OPEN`, `SWAY`, `mine_here(world, player, town)`, `camp_of`, `declare_block/events`, `claim_block/events`, `sway_for`, `sway_block/events(world, occ, player, voter, way)`, `gift_price`, `speak_chance`, `champion_block/events`, `my_trial(world, occ, player) -> (side, opposing champion) | None`, `trial_result_events`, `search_block/events`, `will_events(world, occ, player, burn)`, `will_duel_result_events`, `token_price`, `buy_block`, `token_events(world, token, player, place, how, other=None)`, `tokens_lying_at`, `tokens_held_by`.
  - `engine/crisis.py`: `CrisisMixin` with `_crisis_here`, `_general_extras`, `_conversation_extras`, the `_do_*` handlers `claim_seat`, `declare_for`, `champion_for`, `sway`, `search_chambers`, `reveal_will`, `burn_will`, `fight_trial`, `duel_for_will`, `buy_sect_token`, `duel_for_token`, `take_token`, `hand_token`, and `_after_duel`.
  - `narrate/grammar/crisis.toml`; outcomes and journal lines for every deed.

- [ ] **Step 1: Write the failing tests**

`tests/test_crisis_play.py`:
```python
import pytest

import systems.claimants as C
import systems.crisis_play as P
import systems.duties as duties
import systems.encounters as encounters
import systems.lives as lives
import systems.ranks as ranks
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from debug.invariants import check_crises, check_factions
from engine.actions import Action
from engine.game import Game
from narrate.outcomes import SUMMARIES
from systems import factions as F
from systems import founding, halls
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
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def labels(turn):
    return [c.label for c in turn.all_choices]


def crisis_at_seat(game, rank=2):
    """The player, a member of the given rank, stands at the orthodox sect's seat as its crisis begins."""
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", rank, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                               "secret": False})
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    proud, other = staff(world, sect, seat, "elder")
    world.update_data(proud, traits=["proud"])
    world.update_data(other, traits=["kind"], realm="mortal")
    [leader] = staff(world, sect, seat, "leader")
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    clock.world_tick(world)
    world.set_time(world.time + lives.SEASON)
    clock.run_due(world)
    return sect, seat, keeper, proud, other, SC.live(world, sect)


def to_stage(world, occurrence, seat, stage):
    world.set_time(occurrence.data["ends"][stage])
    sky.observe(world, seat)


def test_a_core_disciple_may_claim_the_seat_in_the_mourning(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    turn = game.perform(Action("look"))
    name = world.entity(sect).name
    assert f"Claim the seat of the {name}" in labels(turn)
    game.perform(Action("claim_seat", occurrence.id))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert {"person": me, "kind": "player"} in crisis["claimants"] and crisis["declared"][str(me)] == me
    assert world.facts(predicate="claimed_seat", subject=me)
    assert f"Claim the seat of the {name}" not in labels(game.perform(Action("look")))


def test_an_outer_disciple_may_not_claim(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game, rank=1)
    assert P.claim_block(world, occurrence, me) == "Only a core disciple or better, or the named heir, may claim the seat."
    assert ranks.promotion_block(world, me, sect) is not None


def test_declaring_for_a_claimant_and_changing_camps_once(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    assert f"Declare for {world.entity(keeper).name}" in labels(game.perform(Action("look")))
    game.perform(Action("declare_for", keeper))
    assert SC.crisis_of(world.entity(occurrence.id))["declared"][str(me)] == keeper
    game.perform(Action("declare_for", proud))
    assert SC.crisis_of(world.entity(occurrence.id))["declared"][str(me)] == proud
    assert any(m.feeling == "wronged" for m in world.memories(keeper, about=me))  # the camp left behind remembers
    turn = game.perform(Action("declare_for", keeper))
    assert any("changed camps once" in t for t, _ in turn.lines)
    backing, _ = C.camps(world, SC.crisis_of(world.entity(occurrence.id)))
    assert me in backing[proud]  # the player's own vote, for a member of rank 2


def test_swaying_a_voter_by_word_gift_and_threat(game, monkeypatch):
    monkeypatch.setattr(P, "speak_chance", lambda world, voter, player: 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    turn = game.perform(Action("talk", other))
    assert f"Speak to them for {world.entity(keeper).name}" in labels(turn)
    game.perform(Action("sway", (other, "speak")))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["sways"][str(other)][str(keeper)] == P.SWAY["speak"]
    turn = game.perform(Action("sway", (other, "gift")))
    assert any("already worked on them" in t for t, _ in turn.lines)  # once a voter a stage
    world.update_data(me, silver=500)
    to_stage(world, occurrence, seat, "announced")  # the canvass: a new stage, a new chance
    game.perform(Action("talk", other))
    price = P.gift_price(world, SC.crisis_of(world.entity(occurrence.id)), other)
    game.perform(Action("sway", (other, "gift")))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["sways"][str(other)][str(keeper)] > P.SWAY["speak"]
    assert world.entity(me).data["silver"] == 500 - price


def test_a_threat_needs_the_upper_hand_and_leaves_a_grudge(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    assert P.sway_block(world, world.entity(occurrence.id), me, other, "threat") == "They do not fear you."
    monkeypatch.setattr(P, "realm_of", lambda world, person: 5 if person == me else 0)
    game.perform(Action("talk", other))
    game.perform(Action("sway", (other, "threat")))
    assert SC.crisis_of(world.entity(occurrence.id))["sways"][str(other)][str(keeper)] == P.SWAY["threat"]
    assert any(m.feeling == "wronged" for m in world.memories(other, about=me))


def test_a_favour_done_in_the_canvass_wins_the_voter(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    game.perform(Action("talk", other))
    game.perform(Action("sway", (other, "favour")))
    duty = duties.open_duty(world, me)
    assert duty is not None and duty.data["favour"]["voter"] == other
    commit(world, duties.done_events(world, me, seat))
    assert SC.crisis_of(world.entity(occurrence.id))["sways"][str(other)][str(keeper)] == P.SWAY["favour"]


def test_the_player_who_claims_and_wins_leads_the_sect(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    sways = {str(v): {str(me): 5.0} for v in C.voters(world, sect)}
    world.update_data(occurrence.id, data={**crisis, "sways": sways})
    to_stage(world, occurrence, seat, "active")
    assert F.membership(world, me, sect)[0] == 4 and F.membership(world, me, sect)[1]["role"] == "leader"
    assert check_factions(world) == [] and check_crises(world) == []


def test_a_champion_fights_the_trial_for_their_claimant(game, monkeypatch):
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 0.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    assert f"Offer to fight as {world.entity(keeper).name}'s champion" in labels(game.perform(Action("look")))
    game.perform(Action("champion_for", keeper))
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: ({keeper: [keeper, me], proud: [proud]}, [1, 2, 3]))
    to_stage(world, occurrence, seat, "active")
    side, foe = P.my_trial(world, world.entity(occurrence.id), me)
    assert side == keeper and foe == proud
    assert f"Fight the trial against {world.entity(proud).name}" in labels(game.perform(Action("look")))
    game.perform(Action("fight_trial", occurrence.id))
    assert game.combat is not None
    commit(world, P.trial_result_events(world, world.entity(occurrence.id), me, won=True))
    assert staff(world, sect, seat, "leader") == [keeper]


def test_searching_the_late_masters_chambers_can_turn_up_the_will(game, monkeypatch):
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 1.0, "other": 1.0})
    monkeypatch.setattr(T, "WILL_STATES", (("hidden", 1.0),))
    monkeypatch.setattr(T, "SEARCH_BASE", 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    to_stage(world, occurrence, seat, "announced")
    assert "Search the late master's chambers" in labels(game.perform(Action("look")))
    game.perform(Action("search_chambers", occurrence.id))
    will = SC.crisis_of(world.entity(occurrence.id))["will"]
    assert will["state"] == "held" and will["holder"] == me
    turn = game.perform(Action("look"))
    assert "Read out the late master's will" in labels(turn) and "Burn the late master's will" in labels(turn)
    assert "Search the late master's chambers" not in labels(turn)  # once a season
    game.perform(Action("reveal_will", occurrence.id))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["will"]["state"] == "read" and "will" in C.proofs(world, crisis, SC.claimant(crisis, keeper))


def test_the_leaders_token_changes_hands(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    token = SC.crisis_of(occurrence)["token"]
    T.put(world, token, place=seat)  # set down in the hall
    turn = game.perform(Action("look"))
    assert f"Pick up {world.entity(token).name}" in labels(turn)
    game.perform(Action("take_token", token))
    assert T.holder(world, token) == me
    assert f"Hand the leader's token to {world.entity(proud).name}" in labels(game.perform(Action("look")))
    game.perform(Action("hand_token", (token, proud)))
    assert T.holder(world, token) == proud
    assert any(m.feeling == "grateful" and m.indelible for m in world.memories(proud, about=me))
    assert "token" in C.proofs(world, SC.crisis_of(world.entity(occurrence.id)),
                               SC.claimant(SC.crisis_of(occurrence), proud))
    assert check_crises(world) == []


def test_a_token_can_be_bought_from_a_holder_who_is_no_claimant(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    token = SC.crisis_of(occurrence)["token"]
    T.put(world, token, owner=other)
    price = P.token_price(world, token)
    world.update_data(me, silver=price + 10)
    turn = game.perform(Action("talk", other))
    assert f"Buy {world.entity(token).name} ({price} silver)" in labels(turn)
    game.perform(Action("buy_sect_token", (other, token)))
    assert T.holder(world, token) == me and world.entity(me).data["silver"] == 10


def test_rank_three_is_as_high_as_anyone_rises_without_a_crisis(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    world.relate(me, sect, "member_of", 3, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    assert ranks.promotion_block(world, me, sect) == "Only a crisis opens the leader's seat."


def test_every_crisis_event_you_take_part_in_has_a_journal_line():
    for kind in ("crisis_declared", "crisis_claimed", "crisis_swayed", "crisis_champion", "chambers_searched",
                 "will_revealed", "will_burned", "will_taken", "sect_token_bought", "sect_token_taken",
                 "sect_token_won", "sect_token_handed", "crisis_trial", "crisis_settled", "crisis_refused",
                 "crisis_lost"):
        assert kind in SUMMARIES, kind


def test_a_claimant_who_dies_before_the_contest_leaves_it_to_the_others(game):
    """Review focus: the player claims, then dies; the contest goes on among the living."""
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    commit(world, [Event("died", (me, me), seat, {"cause": "age", "player": True})])
    to_stage(world, occurrence, seat, "active")
    [leader] = staff(world, sect, seat, "leader")
    assert leader in (keeper, proud) and check_crises(world) == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crisis_play.py`
Expected: `ModuleNotFoundError: No module named 'systems.crisis_play'`.

- [ ] **Step 3: Write the new modules**

`engine/crisis.py`:
```python
"""Succession crises in the engine (phase 4g spec 6, 7): claim, declare, sway, champion, search, trade the token."""

import systems.crisis_play as P
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action, Choice

SWAY_LABELS = {"speak": "Speak to them for {name}", "gift": "Offer them a gift for {name} ({silver} silver)",
               "threat": "Lean on them for {name}", "favour": "Ask what favour would win them for {name}"}


class CrisisMixin:
    def _crisis_here(self):
        return P.mine_here(self.world, self.player.id, self.place.id)

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me = self.world, self.player.id
        occurrence = self._crisis_here()
        if occurrence is not None:
            crisis = SC.crisis_of(occurrence)
            faction = world.entity(crisis["faction"]).name
            if P.claim_block(world, occurrence, me) is None:
                extras.append(Choice(f"Claim the seat of the {faction}", Action("claim_seat", occurrence.id)))
            for c in SC.standing_claimants(world, crisis):
                person = c["person"]
                if P.declare_block(world, occurrence, me, person) is None:
                    extras.append(Choice(f"Declare for {world.entity(person).name}", Action("declare_for", person)))
                if P.champion_block(world, occurrence, me, person) is None:
                    extras.append(Choice(f"Offer to fight as {world.entity(person).name}'s champion",
                                         Action("champion_for", person)))
            if P.search_block(world, occurrence, me) is None:
                extras.append(Choice("Search the late master's chambers", Action("search_chambers", occurrence.id)))
            will = crisis.get("will") or {}
            if will.get("holder") == me and will.get("state") == "held":
                extras.append(Choice("Read out the late master's will", Action("reveal_will", occurrence.id)))
                extras.append(Choice("Burn the late master's will", Action("burn_will", occurrence.id)))
            trial = P.my_trial(world, occurrence, me)
            if trial is not None:
                extras.append(Choice(f"Fight the trial against {world.entity(trial[1]).name}",
                                     Action("fight_trial", occurrence.id)))
            for token in P.tokens_held_by(world, me):
                if world.entity(token).data["faction"] == crisis["faction"]:
                    for c in SC.standing_claimants(world, crisis):
                        if c["person"] != me:
                            extras.append(Choice(f"Hand the leader's token to {world.entity(c['person']).name}",
                                                 Action("hand_token", (token, c["person"]))))
        for token in P.tokens_lying_at(world, self.place.id):
            extras.append(Choice(f"Pick up {world.entity(token).name}", Action("take_token", token)))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        world, me = self.world, self.player.id
        occurrence = self._crisis_here()
        if occurrence is not None:
            crisis = SC.crisis_of(occurrence)
            toward = P.sway_for(world, occurrence, me)
            for way, label in SWAY_LABELS.items():
                if toward is not None and P.sway_block(world, occurrence, me, npc.id, way) is None:
                    name = "yourself" if toward == me else world.entity(toward).name
                    silver = P.gift_price(world, crisis, npc.id) if way == "gift" else 0
                    extras.append(Choice(label.format(name=name, silver=silver), Action("sway", (npc.id, way))))
            will = crisis.get("will") or {}
            if will.get("holder") == npc.id and will.get("state") == "held":
                extras.append(Choice("Challenge them for the late master's will", Action("duel_for_will", npc.id)))
        for token in P.tokens_held_by(world, npc.id):
            if P.buy_block(world, token, me, npc.id) is None:
                extras.append(Choice(f"Buy {world.entity(token).name} ({P.token_price(world, token)} silver)",
                                     Action("buy_sect_token", (npc.id, token))))
            extras.append(Choice(f"Challenge them for {world.entity(token).name}", Action("duel_for_token", (npc.id, token))))
        return extras

    def _crisis_or_say(self):
        occurrence = self._crisis_here()
        return occurrence, (None if occurrence is not None else self._turn([("There is no crisis here.", "system")]))

    def _do_claim_seat(self, _target):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        if (why := P.claim_block(self.world, occurrence, self.player.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.claim_events(self.world, occurrence, self.player.id)))

    def _do_declare_for(self, claimant):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        if (why := P.declare_block(self.world, occurrence, self.player.id, claimant)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.declare_events(self.world, occurrence, self.player.id, claimant)))

    def _do_champion_for(self, claimant):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        if (why := P.champion_block(self.world, occurrence, self.player.id, claimant)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.champion_events(self.world, occurrence, self.player.id, claimant)))

    def _do_sway(self, target):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        voter, way = target if isinstance(target, tuple) else (self.focus, "speak")
        if self.focus != voter:
            return self._turn([("Speak with them first.", "system")])
        if (why := P.sway_block(self.world, occurrence, self.player.id, voter, way)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.sway_events(self.world, occurrence, self.player.id, voter, way)))

    def _do_search_chambers(self, _target):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        if (why := P.search_block(self.world, occurrence, self.player.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.search_events(self.world, occurrence, self.player.id)))

    def _do_reveal_will(self, _target):
        return self._will(False)

    def _do_burn_will(self, _target):
        return self._will(True)

    def _will(self, burn: bool):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        events = P.will_events(self.world, occurrence, self.player.id, burn)
        return self._turn(self._commit(events) if events else [("You hold no will.", "system")])

    def _do_fight_trial(self, _target):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        trial = P.my_trial(self.world, occurrence, self.player.id)
        if trial is None:
            return self._turn([("No trial waits for you.", "system")])
        return self._turn(self._start_duel(trial[1], "duel", purpose={"crisis_trial": occurrence.id}))

    def _do_duel_for_will(self, holder):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        will = SC.crisis_of(occurrence).get("will") or {}
        if will.get("holder") != holder or holder is None:
            return self._turn([("They do not hold it.", "system")])
        return self._turn(self._start_duel(holder, "duel", purpose={"crisis_will": occurrence.id}))

    def _do_buy_sect_token(self, target):
        holder, token = target if isinstance(target, tuple) else (None, None)
        if token is None or (why := P.buy_block(self.world, token, self.player.id, holder)) is not None:
            return self._turn([(why if token is not None else "Buy what?", "system")])
        return self._turn(self._commit(P.token_events(self.world, token, self.player.id, self.place.id, "bought", holder)))

    def _do_duel_for_token(self, target):
        holder, token = target if isinstance(target, tuple) else (None, None)
        if token is None or T.holder(self.world, token) != holder:
            return self._turn([("They do not hold it.", "system")])
        return self._turn(self._start_duel(holder, "duel", purpose={"sect_token": token}))

    def _do_take_token(self, token):
        if token not in P.tokens_lying_at(self.world, self.place.id):
            return self._turn([("It is not here.", "system")])
        return self._turn(self._commit(P.token_events(self.world, token, self.player.id, self.place.id, "taken")))

    def _do_hand_token(self, target):
        token, claimant = target if isinstance(target, tuple) else (None, None)
        occurrence = self._crisis_here()
        if token not in P.tokens_held_by(self.world, self.player.id) or occurrence is None \
                or SC.claimant(SC.crisis_of(occurrence), claimant) is None:
            return self._turn([("You cannot hand that over here.", "system")])
        return self._turn(self._commit(P.token_events(self.world, token, self.player.id, self.place.id, "handed",
                                                      claimant)))

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is None or len(entry.actors) < 2:
            return lines
        me, opponent = entry.actors[0], entry.actors[1]
        won = data.get("result") == "won"
        if "crisis_trial" in purpose:
            occurrence = self.world.entity(purpose["crisis_trial"])
            if P.my_trial(self.world, occurrence, me) is not None:
                lines += self._commit(P.trial_result_events(self.world, occurrence, me, won))
        elif "crisis_will" in purpose:
            events = P.will_duel_result_events(self.world, self.world.entity(purpose["crisis_will"]), me, won)
            lines += self._commit(events) if events else []
        elif "sect_token" in purpose and won and T.holder(self.world, purpose["sect_token"]) == opponent:
            lines += self._commit(P.token_events(self.world, purpose["sect_token"], me, self.place.id, "won", opponent))
        return lines
```

`narrate/grammar/crisis.toml`:
```toml
[symbols]
crisis_air = ["The hall smells of incense and old grudges.", "Somewhere a bell tolls for the late master.", "Disciples fall silent as you pass.", "White mourning banners stir in the draught.", "Every glance in the hall weighs you.", "Voices stop in the corridor, and start again behind you."]

[crisis_declared]
colour = "default"
lines = ["#crisis_air#"]

[crisis_claimed]
colour = "gold"
lines = ["#crisis_air# #crisis_air#"]

[crisis_swayed]
colour = "dim"
lines = ["#crisis_air#"]

[crisis_champion]
colour = "default"
lines = ["#crisis_air#"]

[chambers_searched]
colour = "dim"
lines = ["#crisis_air#"]

[will_revealed]
colour = "gold"
lines = ["#crisis_air#"]

[will_burned]
colour = "red"
lines = ["#crisis_air#"]

[will_taken]
colour = "default"
lines = ["#crisis_air#"]

[sect_token_bought]
colour = "default"
lines = ["#crisis_air#"]

[sect_token_taken]
colour = "default"
lines = ["#crisis_air#"]

[sect_token_won]
colour = "default"
lines = ["#crisis_air#"]

[sect_token_handed]
colour = "default"
lines = ["#crisis_air#"]

[crisis_trial]
colour = "default"
lines = ["#crisis_air#"]

[crisis_settled]
colour = "gold"
lines = ["#crisis_air#"]

[crisis_refused]
colour = "red"
lines = ["#crisis_air#"]

[crisis_lost]
colour = "dim"
lines = ["#crisis_air#"]

[succeeded]
colour = "gold"
lines = ["#crisis_air#"]
```

`systems/crisis_play.py`:
```python
"""The player in a crisis (phase 4g spec 6.2, 6.3): declaring, swaying, claiming, championing, searching,
and the leader's token and the will changing hands.

Each rule is a `*_block` (why not, or None) and each deed a `*_events` list, as in 3b and 4e.
"""

import systems.claimants as C
import systems.duties as duties
import systems.succession_crisis as SC
import systems.testament as T
from systems import factions as F
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from systems.tournaments import alive, realm_of
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

OPEN = ("mourning", "canvass")  # the phases in which camps are still being made
SWAY = {"speak": 0.15, "gift": 0.2, "threat": 0.25, "favour": 0.3}
SPEAK_BASE, SPEAK_PER_ATTITUDE, SPEAK_BOUNDS = 0.4, 0.5, (0.1, 0.9)
GIFT_PER_RANK = 20
CLAIM_RANK = 2


def mine_here(world, player: int, town: int):
    """The live crisis of a faction the player belongs to, whose seat is this town."""
    for fid, _, data in F.memberships(world, player):
        if data.get("status", "member") != "member":
            continue
        occurrence = SC.live(world, fid)
        if occurrence is not None and occurrence.data["place"] == town:
            return occurrence
    return None


def camp_of(crisis: dict, player: int) -> int | None:
    return crisis.get("declared", {}).get(str(player))


# --- declaring and claiming -------------------------------------------------------------------

def declare_block(world, occurrence, player: int, claimant: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "The camps are made; it is too late to choose one."
    if SC.claimant(crisis, claimant) is None or not alive(world, claimant) or claimant == player:
        return "They do not claim the seat."
    if SC.claimant(crisis, player) is not None:
        return "You claim the seat yourself."
    if camp_of(crisis, player) == claimant:
        return "You already stand with them."
    if camp_of(crisis, player) is not None and str(player) in crisis.get("switched", {}):
        return "You have changed camps once; a second time and no one would trust you."
    return None


def declare_events(world, occurrence, player: int, claimant: int) -> list[Event]:
    left = camp_of(SC.crisis_of(occurrence), player)
    witnesses = (Witness(left, "wronged", 0.4),) if left is not None else ()
    return [Event("crisis_declared", (player, claimant), occurrence.data["place"],
                  {"occurrence": occurrence.id, "claimant": claimant, "left": left}, witnesses=witnesses)]


@effect("crisis_declared")
def _declared(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    player = event.actors[0]
    switched = dict(crisis.get("switched", {}))
    if event.data["left"] is not None:
        switched[str(player)] = event.data["left"]
    world.update_data(occurrence.id, data={**crisis, "declared": {**crisis.get("declared", {}),
                                                                  str(player): event.data["claimant"]},
                                           "switched": switched})


def claim_block(world, occurrence, player: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] != "mourning":
        return "Claims are made in the days of mourning; that time has passed."
    if SC.claimant(crisis, player) is not None:
        return "You already claim the seat."
    rank, _ = F.membership(world, player, crisis["faction"])
    if rank < CLAIM_RANK and world.entity(crisis["faction"]).data.get("heir") != player:
        return "Only a core disciple or better, or the named heir, may claim the seat."
    return None


def claim_events(world, occurrence, player: int) -> list[Event]:
    return [Event("crisis_claimed", (player,), occurrence.data["place"],
                  {"occurrence": occurrence.id, "faction": SC.crisis_of(occurrence)["faction"]})]


@effect("crisis_claimed")
def _claimed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    player = event.actors[0]
    world.update_data(occurrence.id, data={**crisis, "claimants": crisis["claimants"] + [{"person": player,
                                                                                          "kind": "player"}],
                                           "declared": {**crisis.get("declared", {}), str(player): player}})


@listen("crisis_claimed")
def _claimed_news(world, event, event_id: int) -> None:
    variant = make_variant("claimed_seat", event.actors[0], event.data["faction"], place=place_name(world, event.place))
    record_fact(world, event.actors[0], "claimed_seat", event.data["faction"], place=event.place,
                source_event=event_id, weight=1.5, variant=variant)


# --- swaying a voter (spec 6.2) ---------------------------------------------------------------

def sway_for(world, occurrence, player: int) -> int | None:
    """Whom the player sways for: themself if claiming, else their declared camp."""
    crisis = SC.crisis_of(occurrence)
    return player if SC.claimant(crisis, player) is not None else camp_of(crisis, player)


def sway_block(world, occurrence, player: int, voter: int, way: str) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "The camps are made; words will not move anyone now."
    if sway_for(world, occurrence, player) is None:
        return "Declare for a claimant first."
    if voter not in C.voters(world, crisis["faction"]) or SC.claimant(crisis, voter) is not None or voter == player:
        return "Their voice is not one to win."
    if crisis.get("swayed", {}).get(str(voter)) == crisis["phase"]:
        return "You have already worked on them; give it time."
    if way == "gift" and silver_of(world, player) < gift_price(world, crisis, voter):
        return f"A gift worthy of them costs {gift_price(world, crisis, voter)} silver."
    if way == "threat" and realm_of(world, voter) >= realm_of(world, player):
        return "They do not fear you."
    if way == "favour" and duties.open_duty(world, player) is not None:
        return "Finish the duty you already carry first."
    return None


def gift_price(world, crisis: dict, voter: int) -> int:
    return GIFT_PER_RANK * max(1, F.membership(world, voter, crisis["faction"])[0])


def speak_chance(world, voter: int, player: int) -> float:
    low, high = SPEAK_BOUNDS
    warmth = attitude(world, voter, apparent_to(world, voter, player)).score
    return max(low, min(high, SPEAK_BASE + SPEAK_PER_ATTITUDE * warmth))


def sway_events(world, occurrence, player: int, voter: int, way: str) -> list[Event]:
    crisis, place = SC.crisis_of(occurrence), occurrence.data["place"]
    toward = sway_for(world, occurrence, player)
    faction = world.entity(crisis["faction"])
    data = {"occurrence": occurrence.id, "voter": voter, "claimant": toward, "way": way, "delta": 0.0, "silver": 0}
    witnesses = ()
    traits = set(world.entity(voter).data.get("traits", ()))
    if way == "speak":
        rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:speak:{voter}:{crisis['phase']}")
        data["delta"] = SWAY["speak"] if rng.random() < speak_chance(world, voter, player) else 0.0
    elif way == "gift":
        data["silver"] = gift_price(world, crisis, voter)
        if "loyal" in traits and faction.data.get("path") == "righteous":
            data["silver"], witnesses = 0, (Witness(voter, "annoyed", 0.25),)  # refused, and taken amiss
        else:
            data["delta"] = SWAY["gift"] * (2 if "greedy" in traits or faction.data.get("path") == "ruthless" else 1)
    elif way == "threat":
        data["delta"], witnesses = SWAY["threat"], (Witness(voter, "wronged", 0.5),)
    elif way == "favour":
        events = duties.issue_events(world, player, crisis["faction"], voter, place, kind="deliver")
        events[0].data["favour"] = {"occurrence": occurrence.id, "voter": voter, "claimant": toward}
        return events + [Event("crisis_swayed", (player, voter), place, {**data, "delta": 0.0})]
    return [Event("crisis_swayed", (player, voter), place, data, witnesses=witnesses)]


@effect("crisis_swayed")
def _swayed(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    crisis = SC.crisis_of(occurrence)
    sways = {k: dict(v) for k, v in crisis.get("sways", {}).items()}
    mine = sways.setdefault(str(d["voter"]), {})
    mine[str(d["claimant"])] = round(mine.get(str(d["claimant"]), 0.0) + d["delta"], 3)
    swayed = {**crisis.get("swayed", {}), str(d["voter"]): crisis["phase"]}
    world.update_data(occurrence.id, data={**crisis, "sways": sways, "swayed": swayed})
    if d["silver"]:
        player = event.actors[0]
        world.update_data(player, silver=silver_of(world, player) - d["silver"])
        world.update_data(d["voter"], silver=silver_of(world, d["voter"]) + d["silver"])


@listen("duty_done")
def _favour_done(world, event, event_id: int) -> None:
    """A favour done within the canvass wins the voter's lean (spec 6.2)."""
    favour = world.entity(event.data["duty"]).data.get("favour")
    if not favour:
        return
    occurrence = world.entity(favour["occurrence"])
    if occurrence is None or SC.crisis_of(occurrence)["phase"] not in OPEN:
        return
    commit(world, [Event("crisis_swayed", (event.actors[0], favour["voter"]), occurrence.data["place"],
                         {"occurrence": occurrence.id, "voter": favour["voter"], "claimant": favour["claimant"],
                          "way": "favour_done", "delta": SWAY["favour"], "silver": 0})])


# --- champions, the trial, the chambers -------------------------------------------------------

def champion_block(world, occurrence, player: int, claimant: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "The contest is already upon them."
    if camp_of(crisis, player) != claimant or claimant == player:
        return "Stand with them first."
    if crisis.get("champions", {}).get(str(claimant)) == player:
        return "You are already their champion."
    return None


def champion_events(world, occurrence, player: int, claimant: int) -> list[Event]:
    return [Event("crisis_champion", (player, claimant), occurrence.data["place"],
                  {"occurrence": occurrence.id, "claimant": claimant},
                  witnesses=(Witness(claimant, "respect", 0.4),))]


@effect("crisis_champion")
def _champion(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "champions": {**crisis.get("champions", {}),
                                                                  str(event.data["claimant"]): event.actors[0]}})


def my_trial(world, occurrence, player: int) -> tuple[int, int] | None:
    """(the player's side, the opposing champion) if a pending trial waits for the player."""
    trial = SC.crisis_of(occurrence).get("trial") or {}
    if not trial.get("pending"):
        return None
    for side, other in ((trial["a"], trial["b"]), (trial["b"], trial["a"])):
        if trial["champions"][str(side)] == player:
            return side, trial["champions"][str(other)]
    return None


def trial_result_events(world, occurrence, player: int, won: bool) -> list[Event]:
    side, _ = my_trial(world, occurrence, player)
    trial = SC.crisis_of(occurrence)["trial"]
    other = trial["b"] if side == trial["a"] else trial["a"]
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:trial:played")
    return SC.trial_events(world, occurrence, trial, side if won else other, rng)


def search_block(world, occurrence, player: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] != "canvass":
        return "The late master's rooms are sealed but in the canvass."
    if crisis.get("searched", {}).get(str(player)) == SC.lives.current_season(world):
        return "You searched them this season."
    return None


def search_events(world, occurrence, player: int) -> list[Event]:
    crisis = SC.crisis_of(occurrence)
    season = SC.lives.current_season(world)
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:chambers:{player}:{season}")
    found = (crisis.get("will") or {}).get("state") == "hidden" and rng.random() < T.search_chance(world, player)
    return [Event("chambers_searched", (player,), occurrence.data["place"],
                  {"occurrence": occurrence.id, "found": found, "season": season})]


@effect("chambers_searched")
def _searched(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    player = event.actors[0]
    will = crisis.get("will") or {}
    if event.data["found"]:
        will = {**will, "state": "held", "holder": player}  # the player keeps it until they choose
    world.update_data(occurrence.id, data={**crisis, "will": will,
                                           "searched": {**crisis.get("searched", {}),
                                                        str(player): event.data["season"]}})


def will_events(world, occurrence, player: int, burn: bool) -> list[Event]:
    will = SC.crisis_of(occurrence).get("will") or {}
    if will.get("holder") != player or will.get("state") != "held":
        return []
    return [Event("will_burned" if burn else "will_revealed", (player,), occurrence.data["place"],
                  {"occurrence": occurrence.id, "names": will.get("names")})]


@effect("will_revealed")
def _revealed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "will": {**crisis["will"], "state": "read", "holder": None}})


@effect("will_burned")
def _burned(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "will": {**crisis["will"], "state": "burned", "holder": None}})


@listen("will_burned")
def _burned_news(world, event, event_id: int) -> None:
    """Burned where others saw it, it is a tale (spec 4.4)."""
    if len(people_at(world, event.place, exclude=event.actors[0])) == 0:
        return
    faction = SC.crisis_of(world.entity(event.data["occurrence"]))["faction"]
    variant = make_variant("will_burned", event.actors[0], faction, place=place_name(world, event.place))
    record_fact(world, event.actors[0], "will_burned", faction, place=event.place, source_event=event_id,
                weight=2.0, variant=variant)


def will_duel_result_events(world, occurrence, player: int, won: bool) -> list[Event]:
    if not won:
        return []
    return [Event("will_taken", (player,), occurrence.data["place"], {"occurrence": occurrence.id})]


@effect("will_taken")
def _will_taken(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "will": {**crisis["will"], "state": "held",
                                                              "holder": event.actors[0]}})


# --- the leader's token, anywhere (spec 4.5, 6.3) ---------------------------------------------

def token_price(world, token: int) -> int:
    faction = world.entity(world.entity(token).data["faction"])
    return T.TOKEN_PRICE * int(faction.data.get("power", 50))


def claimant_in(world, person: int, faction: int) -> bool:
    occurrence = SC.live(world, faction)
    return occurrence is not None and SC.claimant(SC.crisis_of(occurrence), person) is not None


def buy_block(world, token: int, player: int, holder: int) -> str | None:
    if T.holder(world, token) != holder or holder == player:
        return "They do not hold it."
    if claimant_in(world, holder, world.entity(token).data["faction"]):
        return "A claimant will not part with it at any price."
    if silver_of(world, player) < token_price(world, token):
        return f"They want {token_price(world, token)} silver for it."
    return None


def token_events(world, token: int, player: int, place: int, how: str, other: int | None = None) -> list[Event]:
    """`how`: bought from `other`, taken where it lies, won from `other` in a duel, handed to claimant `other`."""
    price = token_price(world, token)
    kind = {"bought": "sect_token_bought", "taken": "sect_token_taken", "won": "sect_token_won",
            "handed": "sect_token_handed"}[how]
    actors = (player,) if other is None else (player, other)
    silver = price if how == "bought" else (price if how == "handed" and silver_of(world, other) >= price else 0)
    witnesses = (Witness(other, "grateful", 0.8, True),) if how == "handed" else ()
    return [Event(kind, actors, place, {"token": token, "silver": silver}, witnesses=witnesses)]


def _moved(world, event, to: int) -> None:
    T.put(world, event.data["token"], owner=to)


@effect("sect_token_bought")
def _bought(world, event) -> None:
    player, holder = event.actors
    _moved(world, event, player)
    world.update_data(player, silver=silver_of(world, player) - event.data["silver"])
    world.update_data(holder, silver=silver_of(world, holder) + event.data["silver"])


@effect("sect_token_taken")
def _taken(world, event) -> None:
    _moved(world, event, event.actors[0])


@effect("sect_token_won")
def _won(world, event) -> None:
    _moved(world, event, event.actors[0])


@effect("sect_token_handed")
def _handed(world, event) -> None:
    player, claimant = event.actors
    _moved(world, event, claimant)
    if event.data["silver"]:
        world.update_data(claimant, silver=silver_of(world, claimant) - event.data["silver"])
        world.update_data(player, silver=silver_of(world, player) + event.data["silver"])


def tokens_lying_at(world, town: int) -> list[int]:
    return [t for t in world.sources(town, "located_in") if world.entity(t).kind == "treasure"
            and world.entity(t).data.get("kind") == "sect_token"]


def tokens_held_by(world, person: int) -> list[int]:
    return [t for t in world.targets(person, "owns") if world.entity(t).kind == "treasure"
            and world.entity(t).data.get("kind") == "sect_token"]
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4g_task5.py`:
```python
"""Phase 4g, Task 5: the player's deeds narrated, the mixin in the game, the leader's seat past rank three"""
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


edit('narrate/crisis_text.py', r'''from narrate.outcomes import cap  # first''', r'''from narrate.outcomes import cap, outcome, summary  # first''')
append('narrate/crisis_text.py', r'''

def _name(world, person) -> str:
    entity = world.entity(person) if person is not None else None
    return entity.name if entity is not None else "someone"


def _sect_of(world, event) -> str:
    occurrence = world.entity(event.data["occurrence"])
    return world.entity(occurrence.data["data"]["faction"]).name


@outcome("crisis_declared", body_facts=False)
def _declared(world, event):
    return [f"You stand with {_name(world, event.data['claimant'])} before the {_sect_of(world, event)}."], {}


@summary("crisis_declared")
def _declared_line(world, entry, names, place, other):
    return f"Declared for {other} in the crisis at {place}."


@outcome("crisis_claimed", body_facts=False)
def _claimed(world, event):
    return [f"Before the mourning banners you name yourself for the seat of the {_sect_of(world, event)}."], {}


@summary("crisis_claimed")
def _claimed_line(world, entry, names, place, other):
    return f"Claimed the seat of a sect at {place}."


SWAY_WORDS = {"speak": ("{v} hears you out, and nods slowly.", "{v} hears you out, unmoved."),
              "gift": ("{v} accepts your gift and your cause with it.", "{v} will not touch your silver, and is offended."),
              "threat": ("{v} goes pale, and says they will think again.", "{v} goes pale."),
              "favour": ("{v} names a favour: a letter to carry.", "{v} names a favour: a letter to carry."),
              "favour_done": ("{v} remembers the favour, and leans your way.", "{v} remembers the favour.")}


@outcome("crisis_swayed", body_facts=False)
def _swayed(world, event):
    good, bad = SWAY_WORDS.get(event.data["way"], ("{v} listens.", "{v} listens."))
    return [(good if event.data["delta"] > 0 else bad).format(v=_name(world, event.data["voter"]))], {}


@summary("crisis_swayed")
def _swayed_line(world, entry, names, place, other):
    return f"Worked on {other} in the crisis at {place}."


@outcome("crisis_champion", body_facts=False)
def _champion(world, event):
    return [f"You will fight for {_name(world, event.data['claimant'])} if it comes to a trial."], {}


@summary("crisis_champion")
def _champion_line(world, entry, names, place, other):
    return f"Swore to fight as {other}'s champion at {place}."


@outcome("chambers_searched", body_facts=False)
def _searched(world, event):
    if event.data["found"]:
        return ["Behind a loose board in the late master's study: a sealed will. It is yours to read out or burn."], {}
    return ["You turn the late master's rooms over and find nothing."], {}


@summary("chambers_searched")
def _searched_line(world, entry, names, place, other):
    return "Found the late master's will." if entry.data["found"] else "Searched the late master's rooms in vain."


@outcome("will_revealed", body_facts=False)
def _revealed(world, event):
    return [f"You read the will aloud: it names {_name(world, event.data['names'])}."], {}


@summary("will_revealed")
def _revealed_line(world, entry, names, place, other):
    return f"Read out the late master's will at {place}."


@outcome("will_burned", body_facts=False)
def _burned(world, event):
    return ["The will curls and blackens in the brazier."], {}


@summary("will_burned")
def _burned_line(world, entry, names, place, other):
    return f"Burned the late master's will at {place}."


@outcome("will_taken", body_facts=False)
def _will_taken(world, event):
    return ["You take the late master's will from them."], {}


@summary("will_taken")
def _will_taken_line(world, entry, names, place, other):
    return f"Won the late master's will at {place}."


@outcome("sect_token_bought", body_facts=False)
def _token_bought(world, event):
    return [f"{_name(world, event.actors[1])} counts your {event.data['silver']} silver and hands over the token."], {}


@summary("sect_token_bought")
def _token_bought_line(world, entry, names, place, other):
    return f"Bought a sect's leader's token from {other}."


@outcome("sect_token_taken", body_facts=False)
def _token_taken(world, event):
    return [f"You pick up {world.entity(event.data['token']).name}."], {}


@summary("sect_token_taken")
def _token_taken_line(world, entry, names, place, other):
    return f"Picked up a sect's leader's token at {place}."


@outcome("sect_token_won", body_facts=False)
def _token_won(world, event):
    return [f"You take {world.entity(event.data['token']).name} from {_name(world, event.actors[1])}."], {}


@summary("sect_token_won")
def _token_won_line(world, entry, names, place, other):
    return f"Won a sect's leader's token from {other}."


@outcome("sect_token_handed", body_facts=False)
def _token_handed(world, event):
    paid = f", and {event.data['silver']} silver changes hands" if event.data["silver"] else ""
    return [f"You place the token in {_name(world, event.actors[1])}'s hands{paid}."], {}


@summary("sect_token_handed")
def _token_handed_line(world, entry, names, place, other):
    return f"Handed a sect's leader's token to {other}."


@outcome("crisis_trial", body_facts=False)
def _trial(world, event):
    trial = event.data["trial"]
    if trial.get("pending"):
        return ["The claimants' camps cannot agree: it will be settled by a trial of arms."], {}
    return [f"The trial is fought: {_name(world, trial['winner'])}'s side has won it."], {}


@summary("crisis_trial")
def _trial_line(world, entry, names, place, other):
    return f"A trial of arms for a sect's seat at {place}."


@outcome("crisis_settled", body_facts=False)
def _settled(world, event):
    return [f"{_name(world, event.data['winner'])} takes the seat of the {_sect_of(world, event)}."], {}


@summary("crisis_settled")
def _settled_line(world, entry, names, place, other):
    return f"{names[0] if names else 'Someone'} took a sect's seat at {place}."


@outcome("crisis_refused", body_facts=False)
def _refused(world, event):
    return [f"{_name(world, event.actors[0])} will not bow to the trial. It will be settled by arms."], {}


@summary("crisis_refused")
def _refused_line(world, entry, names, place, other):
    return f"{names[0]} refused the trial at {place}; the camps went to war."


@outcome("crisis_lost", body_facts=False)
def _lost(world, event):
    return [], {}


@summary("crisis_lost")
def _lost_line(world, entry, names, place, other):
    return f"{other} lost the seat to {names[0]}."
''')
edit('engine/game.py', r'''from engine.delve import ChamberMixin, DelveMixin, RivalMixin, SealedMixin''', r'''from engine.crisis import CrisisMixin
from engine.delve import ChamberMixin, DelveMixin, RivalMixin, SealedMixin''')
edit('engine/game.py', r'''class Game(SealedMixin, RivalMixin,''', r'''class Game(CrisisMixin, SealedMixin, RivalMixin,''')
edit('systems/ranks.py', r'''        return "You have risen as far as anyone can without leading them."''', r'''        return "Only a crisis opens the leader's seat."  # phase 4g: claim it when it falls empty''')
edit('tests/test_ranks.py', r'''    assert "as far as anyone can" in ranks.promotion_block(game.world, game.player.id, sect)''', r'''    assert "Only a crisis opens the leader's seat" in ranks.promotion_block(game.world, game.player.id, sect)''')
edit('debug/invariants.py', r'''            founder = world.entity(fid).data.get("type") == "player_sect" and data.get("role") == "leader"''', r'''            founder = data.get("role") == "leader"  # a sect founded (3c), or a seat won in a crisis (4g)''')
print("task 5 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4g_task5.py`
Expected: `task 5 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crisis_play.py tests/test_ranks.py`
Expected: `19 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the player in a crisis - claim, declare, sway, champion, the trial, the chambers, the will and the token

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: A sect the player leads, and regents

A regent claims for a child heir and hands over when they come of age (an ambitious one may fight for it). A sect the player leads can be lost: the heir must win a seat the elders doubt; a long absence brings a regent and, if ambitious, a usurper (a return may reclaim it); stepping down hands it on, cleanly or into a crisis. A founded sect that passes to someone not of the player's line becomes a school of the world.

**Files:**
- Create: `systems/regency.py`
- Create: `tests/test_regency.py`
- Modify (by `.patches/4g_task6.py`): `systems/succession_crisis.py`, `debug/invariants.py`, `systems/claimants.py`, `systems/succession.py`, `systems/world_clock.py`, `engine/crisis.py`, `narrate/crisis_text.py`, `narrate/grammar/crisis.toml`

**Interfaces:**
- Consumes: Tasks 1-5: `SC.begin_events(force=True)`, `SC.settle_events`, `C.declare`, `C.camps`, `C.votes`, `world_clock._promotion`, the 4b `succession` event, `CrisisMixin`.
- Produces:
  - `regency` (R): `ABSENCE`, `REFUSE_HANDOVER`, `SUCCESSORS`, `led_by(world, person)`, `world_type`, `release(world, sect)`, `heir_doubt`, `absence_events(world, n)` and `regency_events(world, n)` (season hooks), `return_events`, `reclaim_block/events`, `visit(world, player, town)`, `successors`, `step_down_events`; events `regency_declared`, `usurped`, `regency_ended`, `stepped_down`, `regency_over`.
  - `SC`: event `deposed`; the claimant kind `regent`; the 4b event's `led`.
  - `CrisisMixin`: `_commit_all`, `_before_scene` (the visit and the return), `_do_step_down`, `_do_reclaim_seat`, `_do_name_chief`.

- [ ] **Step 1: Write the failing tests**

`tests/test_regency.py`:
```python
import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.regency as R
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from debug.invariants import check_crises, check_factions, check_sect
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from systems.membership import set_membership
from tests.test_sect import found_sect
from world.events import Event, commit
from world.gen.materialize import ensure_town, region_of


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
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def labels(turn):
    return [c.label for c in turn.all_choices]


def the_sect(game, at_seat=True):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    home = world.entity(seat).data
    where = seat if at_seat else ensure_town(world, home["x"] + 6, home["y"] + 6, 0)
    world.unrelate(me, "located_in")
    world.relate(me, where, "located_in")
    return sect, seat


def player_leads(game, at_seat=True):
    """The player has won the orthodox sect's seat."""
    world, me = game.world, game.player.id
    sect, seat = the_sect(game, at_seat)
    [leader] = staff(world, sect, seat, "leader")
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    world.update_data(sect, fallen=None)
    world.relate(me, sect, "member_of", 4, {"role": "leader", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    return sect, seat


def settle_for(world, occurrence, seat, person):
    crisis = SC.crisis_of(world.entity(occurrence.id))
    world.update_data(occurrence.id, data={**crisis, "sways": {str(v): {str(person): 5.0}
                                                               for v in C.voters(world, crisis["faction"])}})
    world.set_time(world.entity(occurrence.id).data["ends"]["active"])
    sky.observe(world, seat)


def test_a_regent_claims_for_a_child_and_hands_over_when_they_come_of_age(game, monkeypatch):
    world = game.world
    sect, seat = the_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    world.update_data(keeper, age=12)
    for elder in staff(world, sect, seat, "elder"):
        world.update_data(elder, traits=["kind"])
    [leader] = staff(world, sect, seat, "leader")
    claims = C.declare(world, sect, leader)
    regent = next(c["person"] for c in claims if c["kind"] == "regent")
    assert {"person": keeper, "kind": "chief"} in claims
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    clock.world_tick(world)
    world.set_time(world.time + lives.SEASON)
    clock.run_due(world)
    occurrence = SC.live(world, sect)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {c["person"]: [c["person"]] + ([1, 2, 3] if c["person"] == regent else []) for c in crisis["claimants"]}, []))
    settle_for(world, occurrence, seat, regent)
    assert staff(world, sect, seat, "leader") == [regent]
    assert world.entity(sect).data["regency_for"] == keeper
    world.update_data(keeper, age=16)
    commit(world, R.regency_events(world, clock.world_tick(world) + 1))
    assert staff(world, sect, seat, "leader") == [keeper]
    assert C.role_in(world, regent, sect) == "elder" and world.entity(sect).data["regency_for"] is None


def test_an_ambitious_regent_may_refuse_to_hand_over(game, monkeypatch):
    monkeypatch.setattr(R, "REFUSE_HANDOVER", 1.0)
    world = game.world
    sect, seat = the_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    [leader] = staff(world, sect, seat, "leader")
    world.update_data(leader, traits=["proud"])
    world.update_data(sect, regency_for=keeper)
    commit(world, R.regency_events(world, clock.world_tick(world) + 1))
    crisis = SC.crisis_of(SC.live(world, sect))
    assert crisis["cause"] == "regency"
    assert {c["person"] for c in crisis["claimants"]} == {keeper, leader}
    assert check_crises(world) == []  # the regent holds the seat while contesting it


def test_a_long_absence_brings_a_regent_and_an_ambitious_regent_takes_the_seat(game):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game, at_seat=False)
    elders = staff(world, sect, seat, "elder")
    for elder in elders:
        world.update_data(elder, traits=["proud"])
    n = clock.world_tick(world)
    world.update_data(sect, visited=n)
    assert R.absence_events(world, n + R.ABSENCE - 1) == []
    commit(world, R.absence_events(world, n + R.ABSENCE))
    regent = world.entity(sect).data["regent"]["person"]
    assert regent in elders and world.facts(predicate="regency", subject=regent)
    commit(world, R.absence_events(world, n + 2 * R.ABSENCE))
    assert staff(world, sect, seat, "leader") == [regent]
    assert F.membership(world, me, sect)[0] == 3 and world.entity(sect).data["usurped_from"] == me
    assert world.facts(predicate="usurped", subject=regent)
    assert check_factions(world) == []


def test_coming_home_ends_a_loyal_regency_and_contests_an_ambitious_one(game):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game)
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["kind"])
    world.update_data(sect, regent={"person": elders[0], "since": 0})
    game.perform(Action("look"))
    assert world.entity(sect).data["regent"] is None and SC.live(world, sect) is None
    world.update_data(elders[1], traits=["proud"])
    world.update_data(sect, regent={"person": elders[1], "since": 0})
    game.perform(Action("look"))
    crisis = SC.crisis_of(SC.live(world, sect))
    assert {c["person"] for c in crisis["claimants"]} == {me, elders[1]} and crisis["cause"] == "regency"
    assert check_crises(world) == []


def test_a_usurped_master_may_reclaim_the_seat(game):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game)
    usurper = staff(world, sect, seat, "elder")[0]
    set_membership(world, me, sect, rank=3, role="member")
    set_membership(world, usurper, sect, rank=4, role="leader")
    world.update_data(sect, usurped_from=me)
    turn = game.perform(Action("look"))
    assert f"Reclaim the seat of the {world.entity(sect).name}" in labels(turn)
    game.perform(Action("reclaim_seat", sect))
    crisis = SC.crisis_of(SC.live(world, sect))
    assert {c["person"] for c in crisis["claimants"]} == {me, usurper} and crisis["cause"] == "usurped"


def test_stepping_down_in_favour_of_a_clear_successor(game):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game)
    strong, weak = staff(world, sect, seat, "elder")
    world.update_data(strong, traits=["kind"])
    world.update_data(weak, traits=["kind"], realm="mortal")
    assert f"Step down in favour of {world.entity(strong).name}" in labels(game.perform(Action("look")))
    game.perform(Action("step_down", (sect, strong)))
    assert staff(world, sect, seat, "leader") == [strong]
    assert F.membership(world, me, sect)[1]["role"] == "retired" and F.membership(world, me, sect)[0] == 3
    assert world.facts(predicate="stepped_down", subject=me)


def test_stepping_down_against_an_ambitious_elder_starts_a_crisis(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game)
    chosen, proud = staff(world, sect, seat, "elder")
    world.update_data(proud, traits=["proud"])
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {c["person"]: [c["person"]] for c in crisis["claimants"]}, [1, 2, 3]))
    game.perform(Action("step_down", (sect, chosen)))
    crisis = SC.crisis_of(SC.live(world, sect))
    assert {c["person"] for c in crisis["claimants"]} == {chosen, proud} and crisis["cause"] == "stepped_down"
    assert F.membership(world, me, sect)[1]["role"] == "retired"
    assert me in C.voters(world, sect)  # the old master may still back and sway


def test_a_founded_sect_handed_on_becomes_a_school_of_the_world(game):
    world, me = game.world, game.player.id
    sect, town = found_sect(game)
    elder = founding.make_person(world, "test:elder", town, occupation="wandering swordsman", age=40,
                                 realm="second-rate")
    founding.enrol(world, elder, sect, 70, role="elder", rank=3)
    game.perform(Action("step_down", (sect, elder)))
    data = world.entity(sect).data
    assert data["type"] == "school" and data["founder"] is None and data["tier"] == "minor"
    assert sect in region_of(world, town).data["minors"]
    assert founding.my_sect(world, me) is None
    assert F.membership(world, elder, sect)[1]["role"] == "leader"
    assert check_sect(world) == [] and check_factions(world) == []


def test_an_heir_the_elders_doubt_must_win_the_founded_sect(game):
    world, me = game.world, game.player.id
    sect, town = found_sect(game)
    elder = founding.make_person(world, "test:elder", town, occupation="wandering swordsman", age=40,
                                 realm="first-rate")
    founding.enrol(world, elder, sect, 70, role="elder", rank=3)
    heir = founding.make_person(world, "test:heir", town, occupation="wandering swordsman", age=20, realm="third-rate")
    commit(world, [Event("died", (me, me), town, {"cause": "age", "player": True})])
    commit(world, [Event("succession", (me, heir), town, {"kind": "named", "silver": 0, "arts": [], "home": town,
                                                          "led": [[sect, False]]})])
    crisis = SC.crisis_of(SC.live(world, sect))
    assert crisis["cause"] == "heir"
    assert {"person": heir, "kind": "player"} in crisis["claimants"] and SC.claimant(crisis, elder) is not None
    assert world.get_meta("player_id") == heir and check_crises(world) == []


def test_an_heir_no_one_doubts_holds_the_seat_their_forebear_won(game):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game)
    for elder in staff(world, sect, seat, "elder"):
        world.update_data(elder, realm="mortal")
    heir = founding.make_person(world, "test:heir", seat, occupation="wandering swordsman", age=25,
                                realm="first-rate")
    world.relate(heir, sect, "member_of", 2, {"role": "keeper", "hall": None, "merit": 0, "status": "member",
                                              "secret": False})
    commit(world, [Event("succession", (me, heir), seat, {"kind": "named", "silver": 0, "arts": [], "home": seat,
                                                          "led": [[sect, True]]})])
    assert C.role_in(world, heir, sect) == "leader" and SC.live(world, sect) is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_regency.py`
Expected: `ModuleNotFoundError: No module named 'systems.regency'`.

- [ ] **Step 3: Write the new modules**

`systems/regency.py`:
```python
"""A sect the player leads (phase 4g spec 6.4), and regents (6.5).

A sect the player leads is one they founded (3c) or an NPC seat they won. It can be lost three ways: on
their death (the heir must hold it), while they are gone (a regent, then a usurper), and when they step
down. A founded sect that passes to someone not of the player's line becomes a school of the world, run
by the faction clock (plan ruling 10).
"""

import systems.claimants as C
import systems.lives as lives
import systems.succession_crisis as SC
import systems.world_clock as world_clock
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.tournaments import alive, realm_of
from world.events import Event, commit, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

ABSENCE = 8  # seasons away from the seat before a regency, and again before a usurpation
REFUSE_HANDOVER = 0.5  # an ambitious regent's chance to refuse a child come of age
SUCCESSORS = 3  # how many members are offered when the player steps down


def led_by(world, person: int) -> list[int]:
    """The factions whose seat this person holds (and has not lost)."""
    return [fid for fid, _, d in F.memberships(world, person)
            if d.get("role") == "leader" and d.get("status", "member") == "member"
            and not world.entity(fid).data.get("dissolved")]


def world_type(world, sect: int) -> str:
    return "unorthodox_clan" if world.entity(sect).data.get("path") == "ruthless" else "school"


def release(world, sect: int) -> None:
    """A founded sect passes out of the player's line: a minor faction of the world from now on (plan ruling 10)."""
    data = world.entity(sect).data
    if data.get("type") != "player_sect":
        return
    kind = world_type(world, sect)
    world.update_data(sect, type=kind, ranks=list(F.LADDERS[kind]), founder=None, tier="minor",
                      base_power=data.get("power", 20))
    region = region_of(world, data["seat"])
    world.update_data(region.id, minors=[*region.data.get("minors", []), sect])
    for person, _, _ in world.relations_to(sect, "member_of"):
        if world.entity(person).data.get("sect") == sect:
            world.update_data(person, sect=None)


@listen("succeeded")
def _passes_on(world, event, event_id: int) -> None:
    d = event.data
    if d["role"] == "leader" and world.entity(d["faction"]).data.get("type") == "player_sect" \
            and not world.entity(event.actors[0]).data.get("is_player"):
        release(world, d["faction"])


# --- the player's death (spec 6.4.1) ----------------------------------------------------------

def heir_doubt(world, faction: int, heir: int, was_member: bool) -> str | None:
    if not was_member or C.age_of(world, heir) < C.ADULT:
        return "heir"
    rivals = [e for e in C.staff(world, faction, ("elder",)) if e != heir]
    if any(realm_of(world, e) >= realm_of(world, heir) - 1 for e in rivals):
        return "close"
    return None


@listen("succession")
def _heir_holds(world, event, event_id: int) -> None:
    """The heir keeps the seats their forebear held, unless the elders doubt them: then a crisis, played in full."""
    old, heir = event.actors
    n = lives.current_season(world)
    for fid, was_member in event.data.get("led", []):
        if world.entity(fid).data.get("dissolved"):
            continue
        cause = heir_doubt(world, fid, heir, was_member)
        if cause is None:
            if world.entity(fid).data.get("type") != "player_sect":  # 4b already made them the founder's heir
                commit(world, [world_clock._promotion(world, heir, fid, "leader", 4, None)])
            continue
        rivals = [{"person": e, "kind": "elder"} for e in C.staff(world, fid, ("elder",))
                  if e != heir and (C.ambitious(world, e) or realm_of(world, e) >= realm_of(world, heir) - 1)]
        claimants = [{"person": heir, "kind": "player"}] + rivals[:C.MAX_CLAIMANTS]
        if len(claimants) < 2:
            if world.entity(fid).data.get("type") != "player_sect":
                commit(world, [world_clock._promotion(world, heir, fid, "leader", 4, None)])
            continue
        commit(world, SC.begin_events(world, fid, n, cause, claimants, old, force=True))


# --- absence: a regency, then a usurpation (spec 6.4.2) ---------------------------------------

def absence_events(world, n: int) -> list[Event]:
    """Each season: a sect whose master has been gone too long gets a regent; an ambitious regent, in time, the seat."""
    player = world.get_meta("player_id")
    if not isinstance(player, int):
        return []
    events = []
    for fid in led_by(world, player):
        data = world.entity(fid).data
        if SC.live(world, fid) is not None:
            continue
        regent = data.get("regent")
        visited = data.get("visited", n)
        if regent is None and n - visited >= ABSENCE:
            elders = [e for e in C.staff(world, fid, ("elder",)) if e != player]
            senior = C._best(world, elders)
            if senior is not None:
                events.append(Event("regency_declared", (senior, player), data["seat"], {"faction": fid, "season": n}))
        elif regent is not None and alive(world, regent["person"]) and n - regent["since"] >= ABSENCE \
                and C.ambitious(world, regent["person"]):
            events.append(Event("usurped", (regent["person"], player), data["seat"], {"faction": fid, "season": n}))
    return events


@effect("regency_declared")
def _regency(world, event) -> None:
    world.update_data(event.data["faction"], regent={"person": event.actors[0], "since": event.data["season"]})


@effect("usurped")
def _usurped(world, event) -> None:
    usurper, player = event.actors
    faction = event.data["faction"]
    set_membership(world, player, faction, rank=3, role="member")
    set_membership(world, usurper, faction, rank=4, role="leader")
    world.update_data(usurper, occupation=F.title(world, faction, 4))
    world.update_data(faction, regent=None, usurped_from=player)
    release(world, faction)


def _news(world, event, event_id: int, predicate: str) -> None:
    actor, player = event.actors
    faction = event.data["faction"]
    variant = make_variant(predicate, actor, faction, place=place_name(world, event.place))
    variant.update(people=[player])
    record_fact(world, actor, predicate, faction, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


@listen("regency_declared")
def _regency_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, "regency")


@listen("usurped")
def _usurped_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, "usurped")


def return_events(world, player: int, faction: int) -> list[Event]:
    """Back at the seat during a regency: the regent hands it back, or (ambitious) contests it."""
    data = world.entity(faction).data
    regent = (data.get("regent") or {}).get("person")
    if regent is None:
        return []
    if alive(world, regent) and C.ambitious(world, regent) and SC.live(world, faction) is None:
        claimants = [{"person": player, "kind": "player"}, {"person": regent, "kind": "regent"}]
        return [Event("regency_ended", (regent, player), data["seat"], {"faction": faction, "contested": True})] \
            + SC.begin_events(world, faction, lives.current_season(world), "regency", claimants, None, force=True)
    return [Event("regency_ended", (regent, player), data["seat"], {"faction": faction, "contested": False})]


@effect("regency_ended")
def _regency_ended(world, event) -> None:
    world.update_data(event.data["faction"], regent=None)


def reclaim_block(world, player: int, faction: int) -> str | None:
    data = world.entity(faction).data
    if data.get("usurped_from") != player:
        return "The seat was never yours."
    if SC.live(world, faction) is not None:
        return "The seat is already contested."
    return None


def reclaim_events(world, player: int, faction: int) -> list[Event]:
    holder = C.staff(world, faction, ("leader",))
    claimants = [{"person": player, "kind": "player"}] + [{"person": h, "kind": "elder"} for h in holder]
    return SC.begin_events(world, faction, lives.current_season(world), "usurped", claimants, None, force=True)


def visit(world, player: int, town: int) -> list[int]:
    """The player stands at the seat of sects they lead: the season is noted (a write only once a season)."""
    n = lives.current_season(world)
    found = []
    for fid in led_by(world, player):
        data = world.entity(fid).data
        if data.get("seat") == town:
            if data.get("visited") != n:
                world.update_data(fid, visited=n)
            found.append(fid)
    return found


# --- stepping down (spec 6.4.3) ---------------------------------------------------------------

def successors(world, player: int, faction: int) -> list[int]:
    """Members of rank 2 or more who could take the seat, the strongest first."""
    able = [p for p, rank, d in world.relations_to(faction, "member_of")
            if d.get("status", "member") == "member" and int(rank) >= 2 and p != player and alive(world, p)
            and d.get("role") not in ("grand_elder", "retired")]
    return sorted(able, key=lambda p: (-realm_of(world, p), p))[:SUCCESSORS]


def step_down_events(world, player: int, faction: int, successor: int) -> list[Event]:
    seat = world.entity(faction).data["seat"]
    rivals = [{"person": e, "kind": "elder"} for e in C.staff(world, faction, ("elder",))
              if e != successor and (C.ambitious(world, e) or realm_of(world, e) >= realm_of(world, successor))]
    claimants = [{"person": successor, "kind": "chief"}] + rivals[:C.MAX_CLAIMANTS - 1]
    probe = {"faction": faction, "claimants": claimants, "declared": {str(player): successor}}
    backing, undecided = C.camps(world, probe)
    tally = C.votes(world, probe, backing)
    clean = len(claimants) == 1 or tally[successor] * 2 > sum(tally.values()) + len(undecided)
    events = [Event("stepped_down", (player, successor), seat, {"faction": faction, "clean": clean})]
    if clean:
        return events + [world_clock._promotion(world, successor, faction, "leader", 4, None)]
    return events + SC.begin_events(world, faction, lives.current_season(world), "stepped_down", claimants, player,
                                    force=True)


@effect("stepped_down")
def _stepped_down(world, event) -> None:
    player = event.actors[0]
    set_membership(world, player, event.data["faction"], rank=3, role="retired")


@listen("stepped_down")
def _stepped_down_news(world, event, event_id: int) -> None:
    player, successor = event.actors
    variant = make_variant("stepped_down", player, event.data["faction"], place=place_name(world, event.place))
    variant.update(people=[successor])
    record_fact(world, player, "stepped_down", event.data["faction"], place=event.place, source_event=event_id,
                weight=2.0, variant=variant)


# --- regents for a child heir (spec 6.5) ------------------------------------------------------

@listen("crisis_settled")
def _regent_rules(world, event, event_id: int) -> None:
    """A regent who won rules for the child they claimed for."""
    crisis = SC.crisis_of(world.entity(event.data["occurrence"]))
    winner = event.data["winner"]
    won = SC.claimant(crisis, winner) if winner is not None else None
    if won is None or won["kind"] != "regent":
        return
    child = next((c["person"] for c in crisis["claimants"] if c["kind"] in ("chief", "blood")), None)
    if child is not None:
        world.update_data(event.data["faction"], regency_for=child)
        world.update_data(winner, regent_of=event.data["faction"])


def regency_events(world, n: int) -> list[Event]:
    """Each season: a regent whose ward has come of age hands the seat over, or (ambitious) fights to keep it."""
    events = []
    for faction in world.entities("faction"):
        child = faction.data.get("regency_for")
        if child is None or faction.data.get("dissolved") or SC.live(world, faction.id) is not None:
            continue
        leaders = C.staff(world, faction.id, ("leader",))
        regent = leaders[0] if leaders else None
        if regent is None or not alive(world, child) or C.role_in(world, child, faction.id) is None:
            events.append(Event("regency_over", (), faction.data["seat"], {"faction": faction.id}))
            continue
        if C.age_of(world, child) < C.ADULT:
            continue
        rng = rng_for(world.world_seed, f"regency:{faction.id}:{n}")
        if C.ambitious(world, regent) and rng.random() < REFUSE_HANDOVER:
            claimants = [{"person": child, "kind": "chief"}, {"person": regent, "kind": "regent"}]
            events += [Event("regency_over", (), faction.data["seat"], {"faction": faction.id})]
            events += SC.begin_events(world, faction.id, n, "regency", claimants, None)
        else:
            events += [Event("regency_over", (), faction.data["seat"], {"faction": faction.id}),
                       Event("deposed", (regent, child), faction.data["seat"], {"faction": faction.id}),
                       world_clock._promotion(world, child, faction.id, "leader", 4, None)]
    return events


@effect("regency_over")
def _regency_over(world, event) -> None:
    world.update_data(event.data["faction"], regency_for=None)


world_clock.SEASON_HOOKS.extend([absence_events, regency_events])
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4g_task6.py`:
```python
"""Phase 4g, Task 6: a holder deposed, a regent's claim, the heir's seats, the engine's regency, its tales"""
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


edit('systems/succession_crisis.py', r'''    events += [Event("crisis_lost", (winner, loser), place, {"faction": faction},
                     witnesses=(Witness(loser, "wronged", 0.6),)) for loser in losers]
    return events + [_promotion(world, winner, faction, "leader", 4, None)]''', r'''    events += [Event("crisis_lost", (winner, loser), place, {"faction": faction},
                     witnesses=(Witness(loser, "wronged", 0.6),)) for loser in losers]
    events += [Event("deposed", (holder, winner), place, {"faction": faction})  # a holder who lost the seat
               for holder in C.staff(world, faction, ("leader",)) if holder != winner]
    return events + [_promotion(world, winner, faction, "leader", 4, None)]


@effect("deposed")
def _deposed(world, event) -> None:
    holder = event.actors[0]
    player = world.entity(holder).data.get("is_player")
    set_membership(world, holder, event.data["faction"], rank=3, role="member" if player else "elder",
                   regent_for=None)''')
edit('systems/succession_crisis.py', r'''from systems.world_clock import _promotion''', r'''from systems.membership import set_membership
from systems.world_clock import _promotion''')
edit('debug/invariants.py', r'''        if C.staff(world, faction, ("leader",)):
            out.append(f"the {world.entity(faction).name} has a leader during its crisis")''', r'''        claimants = {c["person"] for c in crisis["claimants"]}
        if any(p not in claimants for p in C.staff(world, faction, ("leader",))):
            out.append(f"the {world.entity(faction).name} has a leader during its crisis")  # a holder must be a claimant''')
edit('systems/claimants.py', r'''    elders = sorted(staff(world, faction, ("elder",)), key=lambda p: (-realm_of(world, p), p))''', r'''    elders = sorted(staff(world, faction, ("elder",)), key=lambda p: (-realm_of(world, p), p))
    if out and all(age_of(world, c["person"]) < ADULT for c in out) and elders:
        add(elders[0], "regent")  # only children claim by right: the senior elder claims to rule for them (spec 4.1)''')
edit('systems/succession.py', r'''    return [Event("succession", (player, heir), home, {"kind": kind, "silver": silver, "arts": arts, "home": home,
                                                       "goods": goods, "mule": mule})]''', r'''    led = [[fid, bool((F.membership(world, heir, fid) or (0, {}))[1].get("status", "member") == "member"
                      and F.membership(world, heir, fid))]
           for fid, _, d in F.memberships(world, player) if d.get("role") == "leader"]  # for 4g: was the heir one of them
    return [Event("succession", (player, heir), home, {"kind": kind, "silver": silver, "arts": arts, "home": home,
                                                       "goods": goods, "mule": mule, "led": led})]''')
edit('systems/world_clock.py', r'''    set_membership(world, person, d["faction"], rank=d["rank"], role=d["role"], hall=d["hall"])''', r'''    set_membership(world, person, d["faction"], rank=d["rank"], role=d["role"], hall=d["hall"], status="member")''')
edit('systems/world_clock.py', r'''import systems.schism  # noqa: E402,F401  phase 4g: strife between a crisis's camps, season by season''', r'''import systems.schism  # noqa: E402,F401  phase 4g: strife between a crisis's camps, season by season
import systems.regency  # noqa: E402,F401  phase 4g: regents, usurpers, and heirs who must hold the seat''')
edit('engine/crisis.py', r'''import systems.crisis_play as P
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action, Choice''', r'''import systems.crisis_play as P
import systems.regency as R
import systems.claimants as C
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action, Choice
from systems import factions as F
from world.events import Event, commit''')
edit('engine/crisis.py', r'''            extras.append(Choice(f"Pick up {world.entity(token).name}", Action("take_token", token)))
        return extras

''', r'''            extras.append(Choice(f"Pick up {world.entity(token).name}", Action("take_token", token)))
        for fid in R.led_by(world, me):
            if world.entity(fid).data["seat"] == self.place.id and SC.live(world, fid) is None:
                for successor in R.successors(world, me, fid):
                    extras.append(Choice(f"Step down in favour of {world.entity(successor).name}",
                                         Action("step_down", (fid, successor))))
        for fid, _, data in F.memberships(world, me):
            if world.entity(fid).data.get("seat") == self.place.id and R.reclaim_block(world, me, fid) is None:
                extras.append(Choice(f"Reclaim the seat of the {world.entity(fid).name}", Action("reclaim_seat", fid)))
        return extras

    def _before_scene(self) -> None:
        super()._before_scene()
        for fid in R.visit(self.world, self.player.id, self.place.id):
            events = R.return_events(self.world, self.player.id, fid)
            if events:
                self._pending += self._commit_all(events)

    def _do_step_down(self, target):
        fid, successor = target if isinstance(target, tuple) else (None, None)
        if fid not in R.led_by(self.world, self.player.id) or successor not in R.successors(self.world, self.player.id, fid):
            return self._turn([("You cannot hand the seat to them.", "system")])
        return self._turn(self._commit_all(R.step_down_events(self.world, self.player.id, fid, successor)))

    def _do_reclaim_seat(self, fid):
        if (why := R.reclaim_block(self.world, self.player.id, fid)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit_all(R.reclaim_events(self.world, self.player.id, fid)))

    def _do_name_chief(self, npc):
        fid = next((f for f in R.led_by(self.world, self.player.id)
                    if C.role_in(self.world, npc, f) in ("keeper", "disciple")), None)
        if fid is None or self.focus != npc:
            return self._turn([("You cannot name them.", "system")])
        seat = self.world.entity(fid).data["seat"]
        return self._turn(self._commit([Event("named_chief", (npc,), seat, {"faction": fid, "season": 0})]))

''')
edit('engine/crisis.py', r'''        for token in P.tokens_held_by(world, npc.id):
            if P.buy_block(world, token, me, npc.id) is None:''', r'''        for fid in R.led_by(world, me):
            if C.role_in(world, npc.id, fid) in ("keeper", "disciple") and world.entity(fid).data.get("heir") != npc.id:
                extras.append(Choice(f"Name them chief disciple of the {world.entity(fid).name}",
                                     Action("name_chief", npc.id)))
        for token in P.tokens_held_by(world, npc.id):
            if P.buy_block(world, token, me, npc.id) is None:''')
edit('engine/crisis.py', r'''    def _crisis_or_say(self):''', r'''    def _commit_all(self, events: list) -> list:
        """The player's deeds narrated; a crisis the world starts (no actors) committed quietly (4f's rule)."""
        lines = []
        for event in events:
            if event.actors:
                lines += self._commit([event])
            else:
                commit(self.world, [event])
        return lines

    def _crisis_or_say(self):''')
append('narrate/crisis_text.py', r'''

def _regency_story(world, variant, viewer) -> str:
    master = names(world, variant.get("people") or [], viewer)
    return cap(f"With {master} long gone, {who(world, variant.get('actor'), viewer)} rules {_faction(world, variant)} "
               f"as regent.")


def _usurped_story(world, variant, viewer) -> str:
    master = names(world, variant.get("people") or [], viewer)
    return cap(f"{who(world, variant.get('actor'), viewer)} has taken the seat of {_faction(world, variant)} "
               f"from {master}.")


def _stepped_down_story(world, variant, viewer) -> str:
    heir = names(world, variant.get("people") or [], viewer)
    return cap(f"{who(world, variant.get('actor'), viewer)} stepped down as master of {_faction(world, variant)} "
               f"in favour of {heir}.")


def _claimed_seat_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} has claimed the empty seat of {_faction(world, variant)}.")


SPECIAL_PHRASES.update({"regency": _regency_story, "usurped": _usurped_story, "stepped_down": _stepped_down_story,
                        "claimed_seat": _claimed_seat_story})


@outcome("stepped_down", body_facts=False)
def _stepped(world, event):
    how = "The elders bow to your choice." if event.data["clean"] else "The elders will not all bow: the seat is contested."
    return [f"You lay down the seat of the {world.entity(event.data['faction']).name}. {how}"], {}


@summary("stepped_down")
def _stepped_line(world, entry, names, place, other):
    return f"Stepped down in favour of {other}."


@outcome("regency_ended", body_facts=False)
def _regency_ended(world, event):
    if event.data["contested"]:
        return [f"{_name(world, event.actors[0])} will not give the seat back. It will be contested."], {}
    return [f"{_name(world, event.actors[0])} bows and gives the seat back to you."], {}


@summary("regency_ended")
def _regency_ended_line(world, entry, names, place, other):
    return f"Came home to {place} and the regency ended."


@outcome("named_chief", body_facts=False)
def _named_chief(world, event):
    return [f"{_name(world, event.actors[0])} is named chief disciple."], {}


@summary("named_chief")
def _named_chief_line(world, entry, names, place, other):
    return f"{names[0]} was named chief disciple."
''')
append('narrate/grammar/crisis.toml', r'''
[stepped_down]
colour = "gold"
lines = ["#crisis_air#"]

[regency_ended]
colour = "default"
lines = ["#crisis_air#"]

[named_chief]
colour = "default"
lines = ["#crisis_air#"]

[deposed]
colour = "red"
lines = ["#crisis_air#"]
''')
print("task 6 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4g_task6.py`
Expected: `task 6 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_regency.py tests/test_crisis_play.py tests/test_succession.py`
Expected: `31 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: a sect you lead - the heir's claim, regents and usurpers, stepping down, a founded sect passing to the world

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: The screens

The Succession block on the standing page (the stage, the claimants and their proofs, the camps as known, the will and the token), the sky page's crises heard of, the sheet's posts, help, typed commands, and the scene's mourning in the brief.

**Files:**
- Create: `engine/crisis_page.py`
- Create: `tests/test_crisis_screens.py`
- Modify (by `.patches/4g_task7.py`): `engine/standing_page.py`, `engine/sky.py`, `engine/sheet.py`, `engine/game.py`, `engine/commands.py`, `engine/crisis.py`, `narrate/brief.py`, `narrate/crisis_text.py`

**Interfaces:**
- Consumes: Tasks 1-6: `SC`, `C.camps`, `C.proofs`, `T.holder`, `claim_words`, `known_people`.
- Produces:
  - `engine/crisis_page.py`: `succession_lines(world, player)`, `sky_crisis_lines(world, player)`, `sheet_crisis_lines(world, player)`.
  - `narrate/crisis_text.crisis_facts(world, town, player)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_crisis_screens.py`:
```python
import pytest

import systems.encounters as encounters
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action, Choice
from engine.commands import parse
from engine.crisis_page import sheet_crisis_lines, succession_lines
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.brief import scene_brief
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.membership import set_membership
from tests.test_crisis_play import crisis_at_seat


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
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)


def texts(lines):
    return " | ".join(t for t, _ in lines)


def test_the_succession_block_shows_the_stage_the_claimants_and_your_camp(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    text = texts(succession_lines(world, me))
    assert f"Succession: the {world.entity(sect).name}" in text and "the mourning" in text and "days left" in text
    assert f"{world.entity(keeper).name}, the chief disciple (your camp)" in text
    assert f"{world.entity(proud).name}, an elder" in text
    assert "no will has been read" in text.lower() and "leader's token" in text
    assert "Succession:" in texts(game.perform(Action("standing")).lines)


def test_undecided_voters_are_shown_only_once_you_have_worked_on_them(game, monkeypatch):
    import systems.crisis_play as P
    monkeypatch.setattr(P, "speak_chance", lambda world, voter, player: 0.0)  # they stay undecided
    import systems.claimants as C
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: ({keeper: [keeper], proud: [proud]}, [other]))
    game.perform(Action("declare_for", keeper))
    assert world.entity(other).name not in texts(succession_lines(world, me))
    game.perform(Action("talk", other))
    game.perform(Action("sway", (other, "speak")))
    assert f"Undecided: {world.entity(other).name}" in texts(succession_lines(world, me))


def test_the_sky_page_lists_the_crises_you_have_heard_of(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    sky.observe(world, seat)
    [fact] = world.facts(predicate="crisis")
    believe(world, me, fact.id, fact.data["variant"], None, 0.9, 1, "gossip")
    text = texts(game.perform(Action("sky")).lines)
    assert "Succession crises heard of:" in text and "is without a master" in text


def test_the_sheet_names_the_posts_a_crisis_made(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    name = world.entity(sect).name
    world.update_data(sect, heir=me)
    assert f"Chief disciple of the {name}" in texts(sheet_crisis_lines(world, me))
    set_membership(world, me, sect, rank=4, role="leader")
    assert f"Leader of the {name}" in texts(sheet_lines(world, me))
    set_membership(world, me, sect, rank=3, role="retired")
    assert f"Retired master of the {name}" in texts(sheet_crisis_lines(world, me))


def test_help_and_typed_commands_reach_the_crisis(game):
    world = game.world
    assert any("claim | declare <name>" in t for t, _ in game.perform(Action("help")).lines)
    assert parse("claim", []) == Action("claim_seat")
    assert parse("search chambers", []) == Action("search_chambers")
    assert parse("step down", []) == Action("step_down")
    choices = [Choice("Declare for Baek Rin", Action("declare_for", 41))]
    assert parse("declare baek", choices) == Action("declare_for", 41)


def test_the_scene_at_a_seat_in_crisis_tells_of_the_mourning(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    brief = scene_brief(world, seat, me, "t")
    assert any(f"The {world.entity(sect).name} mourns its master" in fact for fact in brief.facts)


def test_a_save_reloaded_mid_crisis_keeps_its_camps(game):
    """Review focus: the crisis lives in the save: camps, choices and the Succession block come back."""
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    path = world.path
    game.close()
    again = Game.load(path)
    try:
        turn = again.look()
        assert Action("declare_for", proud) in [c.action for c in turn.all_choices]
        assert "(your camp)" in texts(succession_lines(again.world, me))
    finally:
        again.close()
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crisis_screens.py`
Expected: `ModuleNotFoundError: No module named 'engine.crisis_page'`.

- [ ] **Step 3: Write the new modules**

`engine/crisis_page.py`:
```python
"""The Succession block (standing page, phase 4g spec 7), the sky page's crises, and the sheet's posts.

Built from what the player knows (spec 5): a camp's backers the player has met or heard of, undecided
voters only if the player has worked on them this crisis, the will and the token as far as they are shown.
"""

import systems.claimants as C
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_events as W
from narrate.base import Line
from narrate.crisis_text import claim_words
from narrate.gossip_text import rumour_text
from systems import factions as F
from systems.beliefs import known_people

WATCHES_PER_DAY = 4
PHASE_WORDS = {"mourning": "the mourning: claims are made", "canvass": "the canvass: the camps are made",
               "contest": "the contest", "strife": "force of arms", "settled": "settled"}


def _days(world, occurrence) -> int:
    ends = occurrence.data["ends"]
    stage = W.stage_at(occurrence.data, world.time)
    end = ends.get(stage, occurrence.data["over_at"])
    return max(0, (end - world.time + WATCHES_PER_DAY - 1) // WATCHES_PER_DAY)


def _will_words(world, crisis: dict, player: int) -> str:
    will = crisis.get("will") or {}
    state = will.get("state")
    if state == "read":
        return f"the will names {world.entity(will['names']).name}"
    if state == "held" and will.get("holder") == player:
        return "you hold the late master's will"
    if state == "burned":
        return "the will is ash"
    return "no will has been read"


def _token_words(world, crisis: dict, player: int) -> str:
    token = crisis.get("token")
    holder = T.holder(world, token) if token is not None else None
    if holder == player:
        return "you hold the leader's token"
    if holder is not None and SC.claimant(crisis, holder) is not None:
        return f"{world.entity(holder).name} holds the leader's token"
    return "where the leader's token lies, you do not know"


def succession_lines(world, player: int) -> list[Line]:
    """For each faction of the player's in crisis: its stage, claimants, the camps as known, the will and the token."""
    lines: list[Line] = []
    heard = None
    for fid, _, data in F.memberships(world, player):
        occurrence = SC.live(world, fid) if data.get("status", "member") == "member" else None
        if occurrence is None:
            continue
        if heard is None:
            heard = set(known_people(world, player))
        crisis = SC.crisis_of(occurrence)
        lines += [("", "default"), (f"Succession: the {world.entity(fid).name}", "heading"),
                  (f"  {PHASE_WORDS.get(crisis['phase'], crisis['phase'])}, {_days(world, occurrence)} days left",
                   "dim")]
        backing, undecided = C.camps(world, crisis)
        mine = crisis.get("declared", {}).get(str(player))
        for c in SC.standing_claimants(world, crisis):
            person = c["person"]
            proofs = [p for p in C.proofs(world, crisis, c) if p != "token" or "holds" in _token_words(world, crisis, player)]
            known = [world.entity(b).name for b in backing.get(person, []) if b != person and (b in heard or b == player)]
            name = "you" if person == player else world.entity(person).name
            tag = " (your camp)" if mine == person and person != player else ""
            lines.append((f"  {name}, {claim_words(c['kind'])}{tag}"
                          + (f"; proofs: {', '.join(proofs)}" if proofs else "")
                          + (f"; backed by {', '.join(known)}" if known else ""), "dim"))
        worked = {int(v) for v in crisis.get("swayed", {})}
        wavering = [world.entity(v).name for v in undecided if v in worked]
        if wavering:
            lines.append((f"  Undecided: {', '.join(wavering)}", "dim"))
        spent = sum(1 for stage in crisis.get("swayed", {}).values() if stage == crisis["phase"])
        lines.append((f"  You have worked on {spent} this stage. {_will_words(world, crisis, player).capitalize()}; "
                      f"{_token_words(world, crisis, player)}.", "dim"))
        trial = crisis.get("trial") or {}
        if trial.get("pending"):
            a, b = trial["champions"][str(trial["a"])], trial["champions"][str(trial["b"])]
            lines.append((f"  A trial of arms waits: {world.entity(a).name} against {world.entity(b).name}.", "red"))
    return lines


def sky_crisis_lines(world, player: int) -> list[Line]:
    """The sky page's crises heard of, while they last: the heralds' cry, as the player heard it."""
    newest: dict = {}
    for belief, fact in world.known_facts(player):
        occurrence = fact.data.get("occurrence")
        if fact.predicate == "crisis" and occurrence is not None and world.entity(occurrence) is not None \
                and SC.crisis_of(world.entity(occurrence))["phase"] != "settled" \
                and (occurrence not in newest or fact.time >= newest[occurrence][1].time):
            newest[occurrence] = (belief, fact)
    if not newest:
        return []
    return [("Succession crises heard of:", "heading")] + [
        (f"  {rumour_text(world, belief.variant, player)}", "dim") for belief, fact in newest.values()]


def sheet_crisis_lines(world, player: int) -> list[Line]:
    """The sheet's posts a crisis made: chief disciple, leader of a seat won, retired master."""
    lines = []
    for fid, rank, data in F.memberships(world, player):
        if data.get("status", "member") != "member":
            continue
        faction = world.entity(fid)
        if faction.data.get("heir") == player:
            lines.append(f"Chief disciple of the {faction.name}")
        if data.get("role") == "leader" and faction.data.get("type") != "player_sect":
            lines.append(f"Leader of the {faction.name}")
        if data.get("role") == "retired":
            lines.append(f"Retired master of the {faction.name}")
    return [(text, "default") for text in lines]
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4g_task7.py`:
```python
"""Phase 4g, Task 7: the Succession block, the sky's crises, the sheet's posts, help, commands, the scene's mourning"""
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


edit('engine/standing_page.py', r'''    lines += [("", "default"), ("How factions see you:", "heading")]''', r'''    from engine.crisis_page import succession_lines  # phase 4g: the seats in contest
    lines += succession_lines(world, player)
    lines += [("", "default"), ("How factions see you:", "heading")]''')
edit('engine/sky.py', r'''                lines.append((f"  {rumour_text(world, belief.variant, me)} ({days} days left)", "dim"))
        return self._turn(lines)''', r'''                lines.append((f"  {rumour_text(world, belief.variant, me)} ({days} days left)", "dim"))
        from engine.crisis_page import sky_crisis_lines  # phase 4g
        return self._turn(lines + sky_crisis_lines(world, me))''')
edit('engine/sheet.py', r'''    from engine.realm_page import sheet_realm_lines  # phase 4f
    lines += sheet_realm_lines(world, player_id)
    return lines''', r'''    from engine.realm_page import sheet_realm_lines  # phase 4f
    lines += sheet_realm_lines(world, player_id)
    from engine.crisis_page import sheet_crisis_lines  # phase 4g
    lines += sheet_crisis_lines(world, player_id)
    return lines''')
edit('engine/game.py', r'''    ("  realms (F5) | enter | deeper | up | leave realm", "system"),''', r'''    ("  realms (F5) | enter | deeper | up | leave realm", "system"),
    ("  claim | declare <name> | search chambers | step down: a sect's succession (see standing, F6)", "system"),''')
edit('engine/commands.py', r'''    "on": Action("delve_on"), "up": Action("delve_back"), "leave realm": Action("leave_realm"),''', r'''    "on": Action("delve_on"), "up": Action("delve_back"), "leave realm": Action("leave_realm"),
    "claim": Action("claim_seat"), "claim seat": Action("claim_seat"), "claim the seat": Action("claim_seat"),
    "search chambers": Action("search_chambers"), "search": Action("search_chambers"), "step down": Action("step_down"),''')
edit('engine/commands.py', r'''    "open": "open_meridian", "use": "use",''', r'''    "open": "open_meridian", "use": "use", "declare": "declare_for",''')
edit('engine/crisis.py', r'''    def _do_step_down(self, target):
        fid, successor = target if isinstance(target, tuple) else (None, None)''', r'''    def _do_step_down(self, target):
        if target is None:  # typed: say who may take the seat
            options = [c.label for c in self._general_extras() if c.action.verb == "step_down"]
            return self._turn([("Step down in favour of whom?" if options else "You lead no sect here.", "system")])
        fid, successor = target if isinstance(target, tuple) else (None, None)''')
edit('narrate/brief.py', r'''    facts += realm_facts(world, place_id, player_id)
    ancestors''', r'''    facts += realm_facts(world, place_id, player_id)
    from narrate.crisis_text import crisis_facts  # a sect's seat in contest here (phase 4g)
    facts += crisis_facts(world, place_id, player_id)
    ancestors''')
append('narrate/crisis_text.py', r'''

STAGE_FACTS = {"mourning": "mourns its master, and its seat stands empty", "canvass": "is split into camps over its empty seat",
               "contest": "is settling who takes its seat", "strife": "is at war with itself over its seat"}


def crisis_facts(world, town: int, player: int) -> list[str]:
    """The scene's sect in crisis: mourning banners anyone at the seat can see (spec 5); the claimants only as known."""
    import systems.succession_crisis as SC
    from systems.beliefs import known_people
    facts = []
    for row in SC.W.index(world):
        if row[SC.W.TYPE] != SC.KIND or row[SC.W.PLACE] != town:
            continue
        crisis = SC.crisis_of(world.entity(row[SC.W.ID]))
        if crisis["phase"] == "settled":
            continue
        heard = set(known_people(world, player))
        named = [world.entity(c["person"]).name for c in crisis["claimants"] if c["person"] in heard]
        claim = f" {', '.join(named)} claim it." if named else ""
        facts.append(f"The {world.entity(crisis['faction']).name} {STAGE_FACTS.get(crisis['phase'], 'is in crisis')}.{claim}")
    return facts
''')
print("task 7 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4g_task7.py`
Expected: `task 7 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crisis_screens.py tests/test_standing_page.py tests/test_sheet.py tests/test_commands.py`
Expected: `24 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: crisis screens - the Succession block, the sky's crises, the sheet's posts, help, commands, the mourning in the scene

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 8: A crisis season end to end

The fork guide's section 8, the speed of a crisis on a turn and a page, a sect heir played at random through crisis after crisis, and 4e's raid hook told apart from a 3b duty's raid (plan ruling 11).

**Files:**
- Create: `tests/test_crisis_fuzz.py`
- Create: `tests/test_crisis_season.py`
- Modify (by `.patches/4g_task8.py`): `engine/tournament.py`, `docs/world-events.md`

**Interfaces:**
- Consumes: Everything above.
- Produces:
  - `docs/world-events.md` section 8.
  - `tests/test_crisis_fuzz.py`: `test_a_sect_heir`.

- [ ] **Step 1: Write the failing tests**

`tests/test_crisis_fuzz.py`:
```python
"""A sect heir, played at random through crisis after crisis (phase 4g): nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing


@pytest.mark.parametrize("seed", [4, 13])
def test_a_sect_heir(tmp_path, seed, monkeypatch):
    """A core disciple at their sect's seat as its leaders fall, again and again: claim, declare, sway, search,
    champion, trade the token, and whatever the camps decide."""
    import systems.claimants as C
    import systems.lives as lives
    import systems.succession_crisis as SC
    import systems.world_events as W
    from systems import factions as F
    from systems import halls
    from world.events import Event, commit
    monkeypatch.setitem(W.TYPES, "succession_crisis", {**W.TYPES["succession_crisis"],
                                                       "stages": {**W.TYPES["succession_crisis"]["stages"],
                                                                  "announced": 4, "active": 8, "aftermath": 3}})
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Heir{seed}", world_seed=seed)
    world = app.game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    me = world.get_meta("player_id")
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    app.submit("look")

    def a_leader_falls(world):
        """The seat falls empty, and a crisis begins where the heir stands."""
        if SC.live(world, sect) is not None:
            return
        for leader in C.staff(world, sect, ("leader",)):
            if world.entity(leader).data.get("is_player"):
                return
            commit(world, [Event("died", (leader, leader), seat, {"cause": "killed", "world": True})])
        claims = C.declare(world, sect, None)
        if len(claims) >= 2:
            commit(world, SC.begin_events(world, sect, lives.current_season(world), "violence", claims, None,
                                          force=True))
    happened = set()
    for step in range(300):
        game = app.game
        if game is None:
            break
        if step % 25 == 0 and game.world.get_meta("player_id") == me:
            a_leader_falls(game.world)
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.5 and app.choices:
            stay = [n for n, c in enumerate(app.choices, 1) if c.action.verb not in ("travel", "routes")]
            app.submit(str(rng.choice(stay or [1])))
        else:
            app.submit(rng.choice(["claim", "search chambers", "standing", "look", "rest", "meditate week",
                                   "journal", "sky", "step down", "declare " + rng.choice("abcdefghijklmnopqrstuvwxyz")]))
        if rng.random() < 0.05:
            app.handle_key("f6", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    assert {"sky_started", "crisis_settled"} <= happened, happened
    app.shutdown()
```

`tests/test_crisis_season.py`:
```python
import gc
import random
import time
from pathlib import Path

import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.crisis_page import succession_lines
from engine.game import Game
from systems.creation import CreationChoice
from tests.test_crisis_play import crisis_at_seat


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
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)


def average(fn, n=10) -> float:
    """CPU time per call, averaged: Windows' CPU clock ticks in 15.6 ms steps (4e ruling 19)."""
    fn()
    gc.collect()
    start = time.process_time()
    for _ in range(n):
        fn()
    return (time.process_time() - start) / n


def test_the_fork_guide_covers_succession_crises():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("succession_crisis", "doubt", "leaderless_events", "MAX_CLAIMANTS", "PROOF_LEAN", "WILL_STATES",
                 "sect_token", "TRANSMIT_CHANCE", "EMERGE_CHANCE", "MAX_BREAKAWAYS", "ABSENCE", "check_crises",
                 "regency_for", "secluded"):
        assert word in guide, word


def test_a_crisis_costs_little_on_a_turn_and_a_page(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert average(lambda: C.camps(world, crisis)) < 0.01  # the camps, settled at a stage or on the page
    assert average(lambda: succession_lines(world, me)) < 0.03  # the Succession block
    assert average(lambda: game.perform(Action("look"))) < 0.05  # a turn at the seat
    assert average(lambda: SC.leaderless_events(world, sect, 99)) < 0.005  # the clock's question, crisis live


def test_a_guard_dutys_raider_is_no_tournament_raid(game):
    """The realm heir's fuzz found 4e reading a 3b duty's raid as a tournament's (plan ruling 11)."""
    from systems import founding
    from world.events import Event, commit
    world, me, town = game.world, game.player.id, game.place.id
    raider = founding.make_person(world, "test:raider", town, occupation="bandit", age=30)
    [duel] = commit(world, [Event("raid", (me, raider), town, {"duty": town})])
    game._after_duel({"duel": duel, "mode": "duel", "result": "won", "verdict": None, "purpose": {"raid": town}})  # no KeyError: it is no occurrence
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crisis_fuzz.py tests/test_crisis_season.py`
Expected: 3 failed, 2 passed: the fork guide (`AssertionError: succession_crisis`), the raid (`KeyError: 'place'`), and seed 4's crash (the same raid); the speed test and seed 13 already pass.

- [ ] **Step 3: Write the new modules**

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/4g_task8.py`:
```python
"""Phase 4g, Task 8: the fork guide's section 8, and 4e's raid hook told apart from a 3b duty's raid"""
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


edit('engine/tournament.py', r'''        elif "raid" in purpose:''', r'''        elif "raid" in purpose and self.world.entity(purpose["raid"]).kind == "world_event":  # not a 3b duty's raid''')
append('docs/world-events.md', r'''
## 8. Succession crises (phase 4g)

A crisis is a `succession_crisis` occurrence: a trigger type, started by the faction clock (never on a calendar)
when a leader has died and the seat is in doubt. Its stages carry the framework's fixed names: `announced` is the
mourning (claims are made), `active` the canvass (camps are made), and the contest is decided as the `aftermath`
begins. Force of arms (`strife`) runs on after the stages, a season at a time, on the faction clock.

**Where the rules live:**
- `systems/succession_crisis.py`: `doubt` (why the seat is in doubt: `violence`, `token`, `heir`, `close`),
  `leaderless_events` (the clock's question), `begin_events`, the contest and the summary far from the player.
- `systems/claimants.py`: the chief disciple (`heir` on the faction, named once a year), who claims (`declare`,
  `MAX_CLAIMANTS`), who votes (`voters`), how they lean (`lean`, `PROOF_LEAN`, `AMBITIOUS`).
- `systems/testament.py`: the will (`WILL_CHANCE`, `WILL_STATES`), the leader's token (`sect_token`, one per faction),
  deathbed transmission (`TRANSMIT_CHANCE`), the Grand Elder (`EMERGE_CHANCE`, `secluded`).
- `systems/schism.py`: strife (`YIELD`, `STRIFE_SEASONS`) and breakaways (`PREFIXES`, `MAX_BREAKAWAYS`, `MAX_MINORS`).
- `systems/regency.py`: a sect the player leads (the heir's claim, `ABSENCE`, stepping down) and regents for a child.
- `systems/crisis_play.py` and `engine/crisis.py`: what the player can do (declare, claim, sway, champion, search,
  the token and the will).

**Saved state:**
- on a faction: `crisis` (its live occurrence), `heir` (the chief disciple), `fallen` (how its leader died),
  `transmitted`, `history` (one line per crisis), `parent` (a breakaway's), `regent`, `regency_for`, `visited`,
  `usurped_from`;
- the occurrence's `data["data"]`: claimants, declared camps, sways, champions, the will, the token, the trial,
  strife, the outcome and its phase;
- a Grand Elder is a person `secluded` in the seat's region: in no scene, at no tournament.

**The rules:** `check_crises` in `debug/invariants.py` holds one live crisis a faction, the faction pointing at it,
no one but a claimant in the leader's seat during it, a token in exactly one place, and at most two breakaways a sect.
''')
print("task 8 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/4g_task8.py`
Expected: `task 8 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_crisis_season.py tests/test_crisis_fuzz.py`
Expected: `5 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Run the 500-year soak**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: `1 passed` (the dry run: 126 s).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: a crisis season end to end - the fork guide, speed, the sect heir's fuzz, and a duty's raid told from a tournament's

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Self-review

- **Spec coverage:**
  - §3 trigger (Task 1), §3.3 transmission and §4.2 Grand Elder (Task 2), §4.1 claimants (Tasks 1, 2, 6), §4.3 leanings (Tasks 1-2);
  - §4.4 will and §4.5 token (Tasks 2, 5), §4.6 contest and far (Task 3), §4.7-4.8 strife and schism (Task 4), §4.9 aftermath (Task 3);
  - §5 knowledge (Tasks 3, 7), §6.1-6.3 the player (Tasks 5, 7), §6.4-6.5 own sect and regents (Task 6);
  - §7 screens (Task 7), §8 rules (Tasks 1, 2, 4, 5, 6), §9 testing (every task; the fuzz and speed in Task 8).
- **Dry run:**
  - every task was applied in order to a copy of master; its tests failed as each Step 2 says, then passed;
  - the whole suite passed after every task, and the 500-year soak passed at the end.
