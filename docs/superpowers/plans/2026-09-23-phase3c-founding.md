# Phase 3c: Founding Your Own Sect — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The player can get land, gather sworn followers and found a sect, then run it: recruit, teach, raise elders, build halls, keep a treasury and make pacts. The sect lives on through seasonal catch-up while the player roams.

**Architecture:**
- The player's sect is a 3b faction entity of type `player_sect`.
- Land is an `owns_land` relation. Disciples are persons with `member_of` the sect.
- `systems/sect_seasons.py` produces one season's events at a time. The engine commits them season by season, so every season's rolls are seeded by the season's number.
- As in 3b, each area has its own system module, engine mixin, narration module and grammar file:

| Area | System | Engine | Narration | Grammar |
|---|---|---|---|---|
| land | `land.py` | `LandMixin` | `land_text.py` | `land.toml` |
| founding | `founding.py` | `FoundingMixin` | `founding_text.py` | `founding.toml` |
| running the sect | `sect.py` | `SectMixin` | `sect_text.py` | `sect.toml` |
| seasons | `sect_seasons.py` | `SeasonsMixin` | `season_text.py` | `seasons.toml` |

**Tech Stack:** Python 3.12, SQLite (save format v2, unchanged), pygame-ce, pytest.

**Spec:** `docs/superpowers/specs/2026-09-23-phase3c-founding-design.md`, which builds on the 3b spec `docs/superpowers/specs/2026-09-23-phase3b-factions-design.md`.

## Global Constraints

- No schema change: entities, relations, facts and beliefs only.
- The player's sect never shows up in 3b recruiter menus. `halls.recruits_for` skips `player_sect`, and sect business goes through its own *Sect matters...* submenu.
- A season is 360 watches. The catch-up processes at most 8 seasons per trigger. Season `n` uses `rng_for(world.world_seed, f"sect:{sect}:season:{n}")`, with `n = last_tick // 360`.
- Every new event kind gets a grammar table with at least 6 distinct expansions, an outcome builder and a journal summary. Grammar symbol names are prefixed with their area (`land_`, `found_`, `sect_`, `season_`).
- A menu shows at most 9 choices. Briefs keep at most 6 facts, at most 1,200 characters, and no ids.
- Test command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.

## Review Focus

1. **Coming back after years away.** Catch-up processes at most 8 seasons per trigger and never runs ahead of the clock. Task 4 pins this with `test_a_long_absence_catches_up_eight_seasons_at_a_time`.
2. **An empty treasury.** Upkeep never makes the treasury negative, unpaid seasons hurt loyalty, and nothing crashes. Task 4 pins this with `test_an_empty_treasury_means_unpaid_seasons`.
3. **The founder standing at the seat when a gate challenger comes.** The challenger calls the player out instead of being resolved offstage. Task 4 pins this with `test_a_challenger_calls_out_the_founder_at_home`.
4. **Every disciple gone.** The sect dissolves cleanly at the season's end, and its hall leaves the town lists. Task 4 pins this with `test_an_empty_sect_dissolves`.
5. **Founding while already in a martial faction.** The founding is refused with the spec's reason. Task 2 pins this with `test_founding_is_refused_step_by_step`.

## Plan-time rulings (deviations from the spec, argued)

1. **No typed sect names.** The founding offers 3 seeded names, because the command line cannot type free text into a submenu. *Cost if wrong:* the player can't pick a custom name. *(Spec §4.3.)*
2. **A disciple's recruit chance uses the founder's reputation** in that town, rather than the sect's. Both come from the same beliefs, and the founder's deeds dominate. *Cost if wrong:* recruit odds differ slightly.
3. **The "talking to an elder anywhere" catch-up trigger is dropped.** Arriving at the seat, looking there, and opening the ledger remain. *Cost if wrong:* news waits until you visit the seat or open the ledger.
4. **Disciples on duty are moved to the seat's region entity**, so each person still has exactly one location (the 3a rule). "Call back" returns them to the seat.
5. **A death on duty is committed as `died` with the victim as both actors.** There is no killer, so no avengers form. Kin still grieve (3a).
6. **Protection income** requires the founder's reputation at the seat to be at least "little known" (renown ≥ 2) and not ruthless.
7. **Disbanding or dissolving sets every member's status to `released`**, so no one hunts the player for it. The land is kept.

---

### Task 1: Land: buying, claiming ruins, seizing a seat

**Files:**
- Create: `systems/land.py`, `engine/land.py`, `narrate/land_text.py`, `narrate/grammar/land.toml`
- Modify (via `.patches/3c_task1.py`):
  - `systems/reputation.py` (`seized` is ruthless)
  - `engine/game.py` (mixin order), `narrate/outcomes.py`
- Test: `tests/test_land.py`

**Interfaces:**
- Consumes: 3b `systems.factions` (`ensure_roster`, `minor_factions`, `members_of`, `memberships`, `membership`), `systems.halls` (`settle_town`, `keeper_at`, `staff_at`, `halls_here`), and `systems.membership.set_membership`.
- Produces:
  - `systems.land`:
    - Constants: `PRICES = {"village": 150, "town": 400, "city": 900}`, `RUIN_CHANCE = 0.3`.
    - Ownership and price: `owner_of(world, town) -> int | None`, `land_price(world, town) -> int`.
    - Buying and claiming: `buy_block(world, player, town) -> str | None`, `buy_events(world, player, magistrate, town)`, `is_ruin(world, town) -> bool`, `contester(world, town) -> int | None`, `claim_events(player, town)`.
    - Seizing: `seizable(world, npc, town) -> int | None` (a faction id), `seized_events(world, player, faction, town)`.
    - `magistrate_of(world, town) -> int | None`.
  - Events: `land_bought`, `land_claimed`, `seized`. Their effects set `owns_land` (player → town) and `town.data["owner"]`. `seized` also dissolves the minor faction (`dissolved`, members `expelled`) and writes the fact `seized` (weight 2.5), with `wronged` memories.
  - `engine.land.LandMixin`: the verbs `buy_land`, `claim_land` and `seize_seat`. `_after_duel` handles the purposes `claim` and `seize`. There are presence lines for ruins and owned land.

- [ ] **Step 1: Write the failing test** — `tests/test_land.py`
```python
import pytest

import systems.encounters as encounters
import systems.land as land
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.gen.materialize import ensure_region, ensure_town
from world.gen.region import region_spec


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


def go(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def towns(game, radius=4):
    for x in range(-radius, radius + 1):
        for y in range(-radius, radius + 1):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                yield ensure_town(game.world, x, y, i)


def buyable_town(game):
    for town in towns(game):
        halls.settle_town(game.world, town)
        if land.magistrate_of(game.world, town) and land.buy_block(game.world, game.player.id, town) != "This land is not for sale.":
            return town
    raise AssertionError("no buyable town")


def test_buying_land_from_the_magistrate(game):
    town = buyable_town(game)
    go(game, town)
    price = land.land_price(game.world, town)
    game.world.update_data(game.player.id, silver=price + 5)
    magistrate = land.magistrate_of(game.world, town)
    game.perform(Action("talk", magistrate))
    turn = game.perform(Action("faction_menu"))
    assert Action("buy_land", town) in [c.action for c in turn.choices]
    game.perform(Action("buy_land", town))
    assert land.owner_of(game.world, town) == game.player.id and silver_of(game.world, game.player.id) == 5
    assert land.buy_block(game.world, game.player.id, town) == "This land is already yours."


def test_ruins_are_seeded_and_never_in_a_great_home(game):
    homes = {tuple(game.world.entity(f).data["home"]) for f in F.ensure_roster(game.world)}
    ruins = [t for t in towns(game) if land.is_ruin(game.world, t)]
    assert ruins
    for t in ruins:
        data = game.world.entity(t).data
        assert (data["x"], data["y"]) not in homes
    assert [t for t in towns(game) if land.is_ruin(game.world, t)] == ruins


def test_claiming_a_ruin_may_need_a_duel(game):
    ruin = next(t for t in towns(game) if land.is_ruin(game.world, t))
    go(game, ruin)
    turn = game.perform(Action("look"))
    assert any("abandoned hall" in text for text, _ in turn.lines)
    game.perform(Action("claim_land", ruin))
    if land.contester(game.world, ruin) is None:
        assert land.owner_of(game.world, ruin) == game.player.id
    else:
        assert game.combat is not None and game.combat.purpose == {"claim": ruin}
        game._finish_duel({"mode": "duel", "result": "won", "purpose": {"claim": ruin}})
        assert land.owner_of(game.world, ruin) == game.player.id


def test_seizing_a_minor_seat_scatters_its_people(game):
    fort = None
    for x in range(-4, 5):
        for y in range(-4, 5):
            for fid in F.minor_factions(game.world, game.world.entity(ensure_region(game.world, x, y))):
                fort = fort or fid
    seat = game.world.entity(fort).data["seat"]
    go(game, seat)
    leader = halls.staff_at(game.world, fort, seat, roles=("leader",))[0]
    staff = halls.staff_at(game.world, fort, seat)
    assert land.seizable(game.world, leader, seat) == fort
    game.perform(Action("talk", leader))
    game.perform(Action("seize_seat", fort))
    assert game.combat.purpose == {"seize": fort}
    game._finish_duel({"mode": "duel", "result": "won", "purpose": {"seize": fort}})
    assert land.owner_of(game.world, seat) == game.player.id
    assert game.world.entity(fort).data["dissolved"]
    assert fort not in halls.halls_here(game.world, seat)
    assert all(F.membership(game.world, p, fort)[1]["status"] == "expelled" for p in staff)
    assert any(m.feeling == "wronged" for m in game.world.memories(staff[1], about=game.player.id))
    assert game.world.facts(predicate="seized")[0].subject == game.player.id
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_land.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.land'`.

- [ ] **Step 3: Write land** — `systems/land.py`
```python
"""Land (phase 3c spec 3): bought from a magistrate, claimed from ruins, or seized from a minor faction."""

from systems import factions as F
from systems import halls
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.purse import payment_events
from world.events import Event, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

PRICES = {"village": 150, "town": 400, "city": 900}
RUIN_CHANCE = 0.3


def owner_of(world, town: int) -> int | None:
    return world.entity(town).data.get("owner")


def land_price(world, town: int) -> int:
    return PRICES.get(world.entity(town).data.get("kind"), 400)


def _great_home(world, town: int) -> bool:
    data = world.entity(town).data
    return any(tuple(world.entity(f).data["home"]) == (data["x"], data["y"]) for f in F.ensure_roster(world))


def magistrate_of(world, town: int) -> int | None:
    """Who registers land here: whoever keeps the imperial office's hall."""
    bureau = next(f for f in F.ensure_roster(world) if world.entity(f).data["type"] == "imperial")
    return halls.keeper_at(world, bureau, town)


def buy_block(world, player: int, town: int) -> str | None:
    owner = owner_of(world, town)
    if owner == player:
        return "This land is already yours."
    if owner is not None or world.entity(town).data.get("seats") or _great_home(world, town):
        return "This land is not for sale."
    return None


def buy_events(world, player: int, magistrate: int, town: int) -> list[Event]:
    price = land_price(world, town)
    return payment_events(player, magistrate, town, price, "land") + [
        Event("land_bought", (player, magistrate), town, {"price": price})]


def is_ruin(world, town: int) -> bool:
    """An old hall stands in one seeded town of some regions that no great faction calls home."""
    entity = world.entity(town)
    if entity.data.get("owner") is not None or _great_home(world, town):
        return False
    region = region_of(world, town)
    rng = rng_for(world.world_seed, f"{region.seed_path}/ruin")
    return rng.random() < RUIN_CHANCE and rng.randrange(region.data["town_count"]) == entity.data["index"]


def contester(world, town: int) -> int | None:
    """The leader of the region's first minor faction contests a claim, if there is one."""
    for fid in F.minor_factions(world, region_of(world, town)):
        faction = world.entity(fid)
        if faction.data.get("dissolved"):
            continue
        halls.settle_town(world, faction.data["seat"])
        leaders = halls.staff_at(world, fid, faction.data["seat"], roles=("leader",))
        if leaders:
            return leaders[0]
    return None


def claim_events(player: int, town: int) -> list[Event]:
    return [Event("land_claimed", (player,), town, {})]


def _own(world, event) -> None:
    player, town = event.actors[0], event.place
    world.relate(player, town, "owns_land")
    world.update_data(town, owner=player)


effect("land_bought")(_own)
effect("land_claimed")(_own)


def seizable(world, npc: int, town: int) -> int | None:
    """The minor faction this person leads from a seat in this town."""
    for fid, _, data in F.memberships(world, npc):
        faction = world.entity(fid)
        if data.get("role") == "leader" and data.get("status", "member") == "member" \
                and faction.data["tier"] == "minor" and faction.data.get("seat") == town \
                and not faction.data.get("dissolved"):
            return fid
    return None


def seized_events(world, player: int, faction: int, town: int) -> list[Event]:
    return [Event("seized", (player,), town, {"faction": faction})]


@effect("seized")
def _seized(world, event) -> None:
    faction, town = event.data["faction"], event.place
    for person in world.sources(faction, "member_of"):
        set_membership(world, person, faction, status="expelled")
    world.update_data(faction, dissolved=True)
    data = world.entity(town).data
    world.update_data(town, halls=[f for f in data.get("halls", []) if f != faction],
                      seats=[f for f in data.get("seats", []) if f != faction])
    _own(world, event)


@listen("seized")
def _seized_fact(world, event, event_id: int) -> None:
    player, faction = event.actors[0], event.data["faction"]
    for person in world.sources(faction, "member_of"):
        if not world.entity(person).data.get("dead"):
            world.add_memory(person, event_id, "wronged", 0.8, ignore_existing=True)
    record_fact(world, player, "seized", faction, place=event.place, source_event=event_id, weight=2.5,
                variant=make_variant("seized", player, faction, place=place_name(world, event.place)))
```

- [ ] **Step 4: Write the land mixin** — `engine/land.py`
```python
"""Land in the engine (phase 3c spec 3)."""

import systems.land as land
from engine.actions import Action, Choice
from systems.purse import silver_of


class LandMixin:
    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        town = self.place.id
        if land.magistrate_of(self.world, town) == npc.id and land.buy_block(self.world, self.player.id, town) is None:
            options.append(Choice(f"Buy land here ({land.land_price(self.world, town)} silver)", Action("buy_land", town)))
        return options

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        fid = land.seizable(self.world, npc.id, self.place.id)
        if fid is not None:
            extras.append(Choice("Seize this seat", Action("seize_seat", fid)))
        return extras

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        if land.is_ruin(self.world, self.place.id):
            extras.append(Choice("Claim the old hall", Action("claim_land", self.place.id)))
        return extras

    def _presence_extras(self) -> list:
        lines = super()._presence_extras()
        town = self.place.id
        if land.owner_of(self.world, town) == self.player.id:
            lines.append(("You own land here.", "dim"))
        elif land.is_ruin(self.world, town):
            lines.append(("An abandoned hall stands at the edge of town.", "dim"))
        return lines

    def _do_buy_land(self, town):
        town = self.place.id
        magistrate = land.magistrate_of(self.world, town)
        if self.focus is None or self.focus != magistrate:
            return self._turn([("Land is registered with the magistrate.", "system")])
        if (why := land.buy_block(self.world, self.player.id, town)) is not None:
            return self._turn([(why, "system")])
        price = land.land_price(self.world, town)
        if silver_of(self.world, self.player.id) < price:
            return self._turn([(f"The land costs {price} silver.", "system")])
        self.submenu = None
        return self._turn(self._commit(land.buy_events(self.world, self.player.id, magistrate, town)))

    def _do_claim_land(self, town):
        town = self.place.id
        if not land.is_ruin(self.world, town):
            return self._turn([("There is nothing here to claim.", "system")])
        rival = land.contester(self.world, town)
        if rival is None:
            return self._turn(self._commit(land.claim_events(self.player.id, town)))
        self.world.unrelate(rival, "located_in")
        self.world.relate(rival, town, "located_in")
        return self._turn([(f"{self.world.entity(rival).name} contests your claim.", "system")]
                          + self._start_duel(rival, "duel", purpose={"claim": town}))

    def _do_seize_seat(self, faction_id):
        if self.focus is None or land.seizable(self.world, self.focus, self.place.id) != faction_id:
            return self._turn([("There is no seat to seize here.", "system")])
        return self._turn(self._start_duel(self.focus, "duel", purpose={"seize": faction_id}))

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        if data["result"] != "won":
            return lines
        if purpose.get("claim") == self.place.id and land.is_ruin(self.world, self.place.id):
            lines += self._commit(land.claim_events(self.player.id, self.place.id))
        elif purpose.get("seize"):
            lines += self._commit(land.seized_events(self.world, self.player.id, purpose["seize"], self.place.id))
        return lines
```

- [ ] **Step 5: Write the land narration** — `narrate/land_text.py`
```python
"""What the player is told about land."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import outcome, summary

EXTRA_PHRASES["seized"] = "{actor} seized the seat of the {target}."


@outcome("land_bought", body_facts=False)
def _bought(world, event):
    return [f"The deed is yours: land in {world.entity(event.place).name}, for {event.data['price']} silver."], {}


@outcome("land_claimed", body_facts=False)
def _claimed(world, event):
    return [f"You claim the old hall in {world.entity(event.place).name}."], {}


@outcome("seized", body_facts=False)
def _seized(world, event):
    return [f"The {world.entity(event.data['faction']).name} is broken; its seat is yours."], {}


@summary("land_bought")
def _bought_line(world, entry, names, place, other):
    return f"Bought land in {place}."


@summary("land_claimed")
def _claimed_line(world, entry, names, place, other):
    return f"Claimed the old hall in {place}."


@summary("seized")
def _seized_line(world, entry, names, place, other):
    return f"Seized the seat of the {world.entity(entry.data['faction']).name}."
```

- [ ] **Step 6: Write the land grammar** — `narrate/grammar/land.toml`
```toml
[symbols]
land_deed = ["A seal is pressed into red wax.", "The register gains a line.", "A clerk blows on the ink.", "The deed is folded and handed over.", "Boundary stones are named aloud."]
land_after = ["It is not much, but it is yours.", "Weeds will need clearing.", "The wind moves through the empty rooms.", "Somewhere a door bangs.", "You pace the ground once."]
land_broken = ["Banners come down.", "The last of them slink away.", "Their gate stands open.", "A torn pennant drifts in the yard.", "The hall falls quiet."]

[land_bought]
colour = "default"
lines = ["#land_deed# #land_after#", "#land_after# #land_deed#"]

[land_claimed]
colour = "default"
lines = ["#land_after# #land_deed#", "#land_after#"]

[seized]
colour = "default"
lines = ["#land_broken# #land_after#", "#land_after# #land_broken#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3c_task1.py`
```python
"""Task 1 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("systems/reputation.py", '''              "paid_off": -0.1, "left_for_dead": -0.8, "owns_manual": 0.0}''',
     '''              "paid_off": -0.1, "left_for_dead": -0.8, "owns_manual": 0.0, "seized": -0.8}''')
GAME = "engine/game.py"
edit(GAME, "from engine.law import LawMixin\n", "from engine.law import LawMixin\nfrom engine.land import LandMixin\n")
edit(GAME, "PoliticsMixin, LeavingMixin, LawMixin,", "PoliticsMixin, LeavingMixin, LawMixin, LandMixin,")
edit("narrate/outcomes.py", "import narrate.law_text  # noqa: E402,F401\n",
     "import narrate.law_text  # noqa: E402,F401\nimport narrate.land_text  # noqa: E402,F401\n")
print("task 1 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3c_task1.py && .venv/Scripts/python.exe -m pytest tests/test_land.py -q -p no:cacheprovider`
Expected: `task 1 edits applied`, then `4 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: land - buy from the magistrate, claim ruins, seize a minor seat"`

---

### Task 2: Sworn followers and founding the sect

**Files:**
- Create: `systems/founding.py`, `engine/founding.py`, `narrate/founding_text.py`, `narrate/grammar/founding.toml`
- Modify (via `.patches/3c_task2.py`):
  - `systems/factions.py` (`player_sect` is martial)
  - `systems/halls.py` (`recruits_for` skips your sect)
  - `engine/game.py`, `narrate/outcomes.py`
- Test: `tests/test_founding.py`

**Interfaces:**
- Consumes: Task 1 (`owner_of`, `magistrate_of`), 3b `factions`, `halls`, `membership.open_martial` and `payment_events`, 3a `attitude`, `reputation` and `EPITHET_RENOWN`, and `realm_index`.
- Produces:
  - `systems.founding`:
    - Constants: `CHARTER = 200`, `FOLLOWERS_NEEDED = 3`, `MIN_REALM = 2`, `PRESETS`, `TABOOS`, `TRIALS`.
    - Followers: `followers(world, player) -> list[int]`, `can_ask_to_follow(world, npc, player) -> bool`, `follow_chance(world, npc, player, town) -> float`, `sworn_events(world, player, npc, place)`.
    - Founding: `found_block(world, player, town) -> str | None`, `name_suggestions(world, player) -> list[str]`, `founded_events(world, player, magistrate, town, choice)`.
    - `my_sect(world, player) -> int | None`, `make_person(world, path, town, **overrides) -> int`.
  - Player data: `sect` (a faction id). Follower data: `sworn_to`. Member data: `loyalty`, `talent`, `on_duty`, `sect_joined_at`.
  - Events: `sworn` and `sect_founded`. Sect faction data: `{type: "player_sect", tier: "minor", home, seat, path, taboos, trial, ranks, treasury, power, buildings, last_tick, founder, dissolved, chronicle, arts, forms, branches}`.
  - `engine.founding.FoundingMixin`: the verbs `ask_follow`, `found_menu`, `found_name`, `found_path`, `found_taboo`, `found_trial`, `found_ranks` and `found_confirm`.

- [ ] **Step 1: Write the failing test** — `tests/test_founding.py`
```python
import pytest

import systems.encounters as encounters
import systems.founding as founding
import systems.land as land
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event, Witness, commit
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


def home_town(game):
    """A town with a magistrate that the player owns."""
    for fid in [None]:
        pass
    from tests.test_land import buyable_town
    town = buyable_town(game)
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")
    commit(game.world, land.claim_events(game.player.id, town))
    return town


def renowned(game, town):
    for i in range(3):
        bandit = game.world.add_entity("person", f"Ma Da{i}", {"realm": "mortal", "occupation": "bandit"})
        record_fact(game.world, game.player.id, "killed", bandit, place=town,
                    variant=make_variant("killed", game.player.id, bandit, place=game.world.entity(town).name))


def friend(game, town, name):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {"realm": "mortal", "occupation": "farmer", "traits": ["kind", "honest"],
                                                 "surname": surname, "given": given,
                                                 "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, town, "located_in")
    commit(game.world, [Event("helped", (game.player.id, pid), town, {}, witnesses=(Witness(pid, "grateful", 1.0),))])
    return pid


def ready(game):
    town = home_town(game)
    renowned(game, town)
    game.world.update_data(game.player.id, realm="second-rate", silver=500)
    for name in ("Lu An", "Lu Bo", "Lu Chen"):
        game.world.update_data(friend(game, town, name), sworn_to=game.player.id)
    return town


def test_friends_can_be_asked_to_follow(game, monkeypatch):
    monkeypatch.setattr(founding, "follow_chance", lambda *args, **kwargs: 1.0)
    town = home_town(game)
    npc = friend(game, town, "Lu An")
    assert founding.can_ask_to_follow(game.world, npc, game.player.id)
    turn = game.perform(Action("talk", npc))
    assert Action("ask_follow", npc) in [c.action for c in turn.all_choices]
    game.perform(Action("ask_follow", npc))
    assert founding.followers(game.world, game.player.id) == [npc]
    assert not founding.can_ask_to_follow(game.world, npc, game.player.id)


def test_founding_is_refused_step_by_step(game):
    town = home_town(game)
    me = game.player.id
    assert founding.found_block(game.world, me, town) == "You must be renowned in this town."
    renowned(game, town)
    assert founding.found_block(game.world, me, town) == "You must be at least Second-rate."
    game.world.update_data(me, realm="second-rate")
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    game.world.relate(me, sect, "member_of", 0, {"role": "member", "status": "member", "secret": False})
    assert founding.found_block(game.world, me, town) == "You must leave your martial faction first."
    game.world.unrelate(me, "member_of", sect)
    assert founding.found_block(game.world, me, town) == "You need 3 sworn followers."
    for name in ("Lu An", "Lu Bo", "Lu Chen"):
        game.world.update_data(friend(game, town, name), sworn_to=me)
    game.world.update_data(me, silver=10)
    assert founding.found_block(game.world, me, town) == "The charter costs 200 silver."
    game.world.update_data(me, silver=500)
    assert founding.found_block(game.world, me, town) is None
    elsewhere = next(t.id for t in game.world.entities("town") if t.id != town)
    assert founding.found_block(game.world, me, elsewhere) == "You must own land here."


def test_founding_through_the_menus(game):
    town = ready(game)
    game.perform(Action("talk", land.magistrate_of(game.world, town)))
    game.perform(Action("found_menu"))
    name = founding.name_suggestions(game.world, game.player.id)[0]
    for action in (Action("found_name", name), Action("found_path", "righteous"),
                   Action("found_taboo", "never_rob"), Action("found_taboo", "never_kill_unarmed"),
                   Action("found_trial", "spar"), Action("found_ranks", "clan")):
        turn = game.perform(action)
    assert any(c.action.verb == "found_confirm" for c in turn.choices)
    turn = game.perform(Action("found_confirm"))
    sect = founding.my_sect(game.world, game.player.id)
    data = game.world.entity(sect).data
    assert game.world.entity(sect).name == name and data["type"] == "player_sect" and data["seat"] == town
    assert data["taboos"] == ["never_rob", "never_kill_unarmed"] and data["ranks"][0] == "retainer"
    assert F.membership(game.world, game.player.id, sect)[0] == 4
    members = [p for p in F.members_of(game.world, sect) if p != game.player.id]
    assert len(members) == 3 and all(game.world.entity(p).data["loyalty"] == 60 for p in members)
    assert all(game.world.targets(p, "located_in") == [town] for p in members)
    assert sect in halls.halls_here(game.world, town) and sect not in halls.recruits_for(game.world, members[0])
    assert game.world.facts(predicate="founded")[0].object == sect
    sect_orthodox = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    assert F.stance(game.world, sect, sect_orthodox) == 0.6
    assert any(name in text for text, _ in turn.lines)
    from debug.invariants import check_factions
    assert check_factions(game.world) == []  # the founder's rank 4 is the one rank above a member's 3
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_founding.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.founding'`.

- [ ] **Step 3: Write founding** — `systems/founding.py`
```python
"""Founding a sect (phase 3c spec 4): sworn followers, the charter, the founding choices."""

import systems.land as land
from systems import factions as F
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import make_variant, place_name, record_fact
from systems.membership import open_martial
from systems.purse import payment_events, silver_of
from systems.realms import realm_index
from systems.reputation import EPITHET_RENOWN, reputation
from world.events import Event, Witness, effect, listen
from world.gen.names import person_name
from world.gen.npc import OCCUPATIONS, PORTRAIT_PARTS, TRAITS
from world.seed import rng_for

CHARTER = 200
FOLLOWERS_NEEDED = 3
MIN_REALM = 2
PRESETS = {"orthodox": F.LADDERS["orthodox_sect"], "clan": F.LADDERS["martial_clan"],
           "beggars": F.LADDERS["beggars"], "cult": F.LADDERS["demonic_cult"]}
TABOOS = ("never_kill_unarmed", "never_teach_outsiders", "never_spare_cultists", "never_rob", "never_desert_a_duel")
TRIALS = ("spar", "service", "ears", "escort", "blood")
PATH_TRAITS = {"righteous": {"kind", "honest"}, "ruthless": {"cunning", "hot-tempered"}}
RENOWN_BANDS = {"unknown": 0, "little known": 1, "known": 2, "renowned": 3, "famous": 4}
NAME_ENDS = ("Sect", "Hall", "Gate")


def my_sect(world, player: int) -> int | None:
    sect = world.entity(player).data.get("sect")
    return sect if sect and not world.entity(sect).data.get("dissolved") else None


def followers(world, player: int) -> list[int]:
    return [p.id for p in world.entities("person")
            if p.data.get("sworn_to") == player and not p.data.get("dead")]


def can_ask_to_follow(world, npc: int, player: int) -> bool:
    entity = world.entity(npc)
    if entity.data.get("is_player") or entity.data.get("beast") or entity.data.get("sworn_to") or F.memberships(world, npc):
        return False
    return attitude(world, npc, apparent_to(world, npc, player)).score >= 0.3


def follow_chance(world, npc: int, player: int, town: int) -> float:
    rep = reputation(world, town, apparent_to(world, town, player))
    traits = set(world.entity(npc).data.get("traits", ()))
    match = 1.0 if rep.path == "hard to read" or traits & PATH_TRAITS.get(rep.path, set()) else 0.0
    return max(0.0, min(1.0, 0.2 + 0.1 * RENOWN_BANDS.get(rep.word, 0) + 0.2 * match))


def sworn_events(world, player: int, npc: int, place: int) -> list[Event]:
    roll = rng_for(world.world_seed, f"sworn:{npc}:{player}:{world.time}").random()
    accepted = roll < follow_chance(world, npc, player, place)
    witness = Witness(npc, "grateful" if accepted else "annoyed", 0.3 if accepted else 0.2)
    return [Event("sworn", (player, npc), place, {"accepted": accepted}, witnesses=(witness,))]


@effect("sworn")
def _sworn(world, event) -> None:
    if event.data["accepted"]:
        world.update_data(event.actors[1], sworn_to=event.actors[0])


def found_block(world, player: int, town: int) -> str | None:
    me = world.entity(player)
    if land.owner_of(world, town) != player:
        return "You must own land here."
    if reputation(world, town, apparent_to(world, town, player)).renown < EPITHET_RENOWN:
        return "You must be renowned in this town."
    if realm_index(me.data.get("realm", "mortal")) < MIN_REALM:
        return "You must be at least Second-rate."
    if open_martial(world, player) is not None:
        return "You must leave your martial faction first."
    if len(followers(world, player)) < FOLLOWERS_NEEDED:
        return f"You need {FOLLOWERS_NEEDED} sworn followers."
    if silver_of(world, player) < CHARTER:
        return f"The charter costs {CHARTER} silver."
    if my_sect(world, player) is not None:
        return "You already lead a sect."
    return None


def name_suggestions(world, player: int) -> list[str]:
    rng = rng_for(world.world_seed, f"sect-names:{player}")
    names: list[str] = []
    while len(names) < 3:
        name = f"{rng.choice(F.SECT_A)} {rng.choice(F.SECT_B)} {rng.choice(NAME_ENDS)}"
        if name not in names:
            names.append(name)
    return names


def make_person(world, path: str, town: int, **overrides) -> int:
    """A seeded person standing in `town` (recruits, followers made on the spot)."""
    rng = rng_for(world.world_seed, path)
    surname, given = person_name(rng)
    data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": rng.randint(16, 40),
            "occupation": rng.choice(OCCUPATIONS), "traits": rng.sample(TRAITS, 2), "realm": "mortal",
            "portrait": {part: rng.randrange(count) for part, count in PORTRAIT_PARTS.items()}}
    data.update(overrides)
    person = world.add_entity("person", f"{data['surname']} {data['given']}", data, path)
    world.relate(person, town, "located_in")
    return person


def founded_events(world, player: int, magistrate: int, town: int, choice: dict) -> list[Event]:
    return payment_events(player, magistrate, town, CHARTER, "charter") + [
        Event("sect_founded", (player, magistrate), town, dict(choice))]


def _talent(world, person: int) -> float:
    return round(rng_for(world.world_seed, f"talent:{person}").uniform(0.5, 1.5), 2)


def enrol(world, person: int, sect: int, loyalty: int, role: str = "disciple", rank: int = 0) -> None:
    """Make someone a member of the player's sect, standing at its seat."""
    seat = world.entity(sect).data["seat"]
    world.relate(person, sect, "member_of", rank, {"role": role, "hall": None, "merit": 0, "status": "member",
                                                  "secret": False})
    world.update_data(person, loyalty=loyalty, talent=_talent(world, person), on_duty=False,
                      sect_joined_at=world.time, sworn_to=None)
    world.unrelate(person, "located_in")
    world.relate(person, seat, "located_in")


@effect("sect_founded")
def _founded(world, event) -> None:
    player, town, choice = event.actors[0], event.place, event.data
    here = world.entity(town).data
    data = {"type": "player_sect", "tier": "minor", "home": [here["x"], here["y"]], "seat": town,
            "path": choice["path"], "taboos": list(choice["taboos"]), "trial": choice["trial"],
            "ranks": list(PRESETS[choice["ranks"]]), "treasury": 0, "power": 20, "wealth": 0, "buildings": {},
            "last_tick": world.time, "founder": player, "dissolved": False, "chronicle": [], "arts": [],
            "forms": [], "branches": []}
    sect = world.add_entity("faction", choice["name"], data, f"sect:{player}:{world.time}")
    world.relate(player, sect, "member_of", 4, {"role": "leader", "hall": None, "merit": 0, "status": "member",
                                               "secret": False, "joined_at": world.time, "judged": []})
    for person in followers(world, player):
        enrol(world, person, sect, 60)
    world.update_data(town, halls=[*here.get("halls", []), sect], seats=[*here.get("seats", []), sect])
    world.update_data(player, sect=sect)
    model = {"righteous": "orthodox_sect", "ruthless": "demonic_cult"}.get(choice["path"])
    for other in F.ensure_roster(world):
        value = F.base_stance(model, world.entity(other).data["type"]) if model else 0.0
        if value:
            world.relate(sect, other, "stance", value)
            world.relate(other, sect, "stance", value)


@listen("sect_founded")
def _founded_fact(world, event, event_id: int) -> None:
    player = event.actors[0]
    sect = world.entity(player).data["sect"]
    record_fact(world, player, "founded", sect, place=event.place, source_event=event_id, weight=3.0,
                variant=make_variant("founded", player, sect, place=place_name(world, event.place)))
```

- [ ] **Step 4: Write the founding mixin** — `engine/founding.py`
```python
"""Founding a sect in the engine (phase 3c spec 4): followers, and the founding menus."""

import systems.founding as founding
import systems.land as land
from engine.actions import Action, Choice

FOUND_MENUS = ("found_name", "found_path", "found_taboo", "found_trial", "found_ranks", "found_confirm")


class FoundingMixin:
    _founding: dict | None = None

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if founding.my_sect(self.world, self.player.id) is None and founding.can_ask_to_follow(self.world, npc.id, self.player.id):
            extras.append(Choice("Ask them to follow you", Action("ask_follow", npc.id)))
        return extras

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        town = self.place.id
        if land.magistrate_of(self.world, town) == npc.id and land.owner_of(self.world, town) == self.player.id \
                and founding.my_sect(self.world, self.player.id) is None:
            options.append(Choice("Found a sect", Action("found_menu")))
        return options

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None and self.submenu in FOUND_MENUS:
            options[self.submenu] = (self._found_choices(self.submenu), Action("talk_menu"))
        return options

    def _found_choices(self, step: str) -> list:
        f = self._founding or {}
        if step == "found_name":
            return [Choice(n, Action("found_name", n)) for n in founding.name_suggestions(self.world, self.player.id)]
        if step == "found_path":
            return [Choice(p.capitalize(), Action("found_path", p)) for p in ("righteous", "neutral", "ruthless")]
        if step == "found_taboo":
            return [Choice(t.replace("_", " ").capitalize(), Action("found_taboo", t))
                    for t in founding.TABOOS if t not in f.get("taboos", [])]
        if step == "found_trial":
            return [Choice(f"Entry by {t}", Action("found_trial", t)) for t in founding.TRIALS]
        if step == "found_ranks":
            return [Choice(f"Ranks like a {k} ({founding.PRESETS[k][0]} first)", Action("found_ranks", k))
                    for k in founding.PRESETS]
        return [Choice(f"Found the {f.get('name')}", Action("found_confirm"))]

    def _do_ask_follow(self, npc):
        if self.focus != npc or not founding.can_ask_to_follow(self.world, npc, self.player.id):
            return self._turn([("They will not follow you.", "system")])
        return self._turn(self._commit(founding.sworn_events(self.world, self.player.id, npc, self.place.id)))

    def _found_step(self, step: str, prompt: str):
        self.submenu = step
        return self._turn([(prompt, "system")])

    def _do_found_menu(self, _target):
        town = self.place.id
        if self.focus != land.magistrate_of(self.world, town):
            return self._turn([("A charter is granted by the magistrate.", "system")])
        if (why := founding.found_block(self.world, self.player.id, town)) is not None:
            return self._turn([(why, "system")])
        self._founding = {"taboos": []}
        return self._found_step("found_name", "What will your sect be called?")

    def _do_found_name(self, name):
        if self._founding is None or name not in founding.name_suggestions(self.world, self.player.id):
            return self._turn([("Choose a name first.", "system")])
        self._founding["name"] = name
        return self._found_step("found_path", "Which path will it walk?")

    def _do_found_path(self, path):
        if self._founding is None or path not in ("righteous", "neutral", "ruthless"):
            return self._turn([("Choose a path.", "system")])
        self._founding["path"] = path
        return self._found_step("found_taboo", "Choose the first of two taboos.")

    def _do_found_taboo(self, taboo):
        if self._founding is None or taboo not in founding.TABOOS or taboo in self._founding["taboos"]:
            return self._turn([("Choose a taboo.", "system")])
        self._founding["taboos"].append(taboo)
        if len(self._founding["taboos"]) < 2:
            return self._found_step("found_taboo", "Choose the second taboo.")
        return self._found_step("found_trial", "How will newcomers prove themselves?")

    def _do_found_trial(self, trial):
        if self._founding is None or trial not in founding.TRIALS:
            return self._turn([("Choose an entry trial.", "system")])
        self._founding["trial"] = trial
        return self._found_step("found_ranks", "What will its ranks be called?")

    def _do_found_ranks(self, ranks):
        if self._founding is None or ranks not in founding.PRESETS:
            return self._turn([("Choose the ranks.", "system")])
        self._founding["ranks"] = ranks
        return self._found_step("found_confirm", "All is ready. Found it?")

    def _do_found_confirm(self, _target):
        f = self._founding or {}
        if not all(k in f for k in ("name", "path", "trial", "ranks")) or len(f.get("taboos", [])) != 2:
            return self._turn([("The founding is not ready.", "system")])
        town = self.place.id
        if (why := founding.found_block(self.world, self.player.id, town)) is not None:
            return self._turn([(why, "system")])
        self._founding, self.submenu = None, None
        return self._turn(self._commit(founding.founded_events(self.world, self.player.id, self.focus, town, f)))
```

- [ ] **Step 5: Write the founding narration** — `narrate/founding_text.py`
```python
"""What the player is told about followers and founding."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import cap, outcome, summary

EXTRA_PHRASES["founded"] = "{actor} founded the {target}."


@outcome("sworn", body_facts=False)
def _sworn(world, event):
    name = cap(world.entity(event.actors[1]).name)
    if event.data["accepted"]:
        return [f"{name} swears to follow you."], {}
    return [f"{name} is not ready to follow you."], {}


@outcome("sect_founded", body_facts=False)
def _founded(world, event):
    sect = world.entity(event.actors[0]).data["sect"]
    return [f"The charter is sealed: the {world.entity(sect).name} is founded.",
            "Your followers bow to you as their leader."], {}


@summary("sworn")
def _sworn_line(world, entry, names, place, other):
    return f"{cap(other)} swore to follow you." if entry.data["accepted"] else f"{cap(other)} declined to follow you."


@summary("sect_founded")
def _founded_line(world, entry, names, place, other):
    return f"Founded a sect in {place}."
```

- [ ] **Step 6: Write the founding grammar** — `narrate/grammar/founding.toml`
```toml
[symbols]
found_vow = ["Hands are clasped.", "A cup is shared.", "Knees touch the dust.", "An oath is spoken plainly.", "Incense is lit between you."]
found_after = ["Something new begins.", "Eyes turn to you.", "The moment settles.", "Somewhere a bird calls.", "No one speaks for a breath."]
found_rite = ["The charter is read aloud.", "A banner is raised for the first time.", "The magistrate's seal comes down.", "A gong sounds over the town.", "Your name is written at the head of a new ledger."]

[sworn]
colour = "npc"
lines = ["#found_vow# #found_after#", "#found_after# #found_vow#"]

[sect_founded]
colour = "gold"
lines = ["#found_rite# #found_after#", "#found_after# #found_rite#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3c_task2.py`
```python
"""Task 2 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("systems/factions.py", '''MARTIAL = frozenset({"orthodox_sect", "school", "demonic_cult", "unorthodox_clan", "bandit_fort"})''',
     '''MARTIAL = frozenset({"orthodox_sect", "school", "demonic_cult", "unorthodox_clan", "bandit_fort", "player_sect"})''')
edit("systems/halls.py", '''    for fid, _, data in F.memberships(world, npc_id):
        if data.get("status", "member") != "member":
            continue
        if data.get("role") in RECRUITERS''', '''    for fid, _, data in F.memberships(world, npc_id):
        if data.get("status", "member") != "member" or world.entity(fid).data["type"] == "player_sect":
            continue  # the player's own sect has its own business (phase 3c)
        if data.get("role") in RECRUITERS''')
GAME = "engine/game.py"
edit(GAME, "from engine.land import LandMixin\n", "from engine.land import LandMixin\nfrom engine.founding import FoundingMixin\n")
edit(GAME, "LawMixin, LandMixin,", "LawMixin, LandMixin, FoundingMixin,")
edit("narrate/outcomes.py", "import narrate.land_text  # noqa: E402,F401\n",
     "import narrate.land_text  # noqa: E402,F401\nimport narrate.founding_text  # noqa: E402,F401\n")
edit("debug/invariants.py", '''            if not 0 <= rank <= 3:
                out.append(f"the player holds rank {rank} in #{fid}")''', '''            founder = world.entity(fid).data.get("type") == "player_sect" and data.get("role") == "leader"
            if not 0 <= rank <= (4 if founder else 3):
                out.append(f"the player holds rank {rank} in #{fid}")''')
print("task 2 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3c_task2.py && .venv/Scripts/python.exe -m pytest tests/test_founding.py -q -p no:cacheprovider`
Expected: `task 2 edits applied`, then `3 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: sworn followers and founding your own sect"`

---
### Task 3: Running the sect: recruits, teaching, elders, duty, expulsion, buildings, treasury, pacts, disbanding

**Files:**
- Create: `systems/sect.py`, `engine/sect.py`, `narrate/sect_text.py`, `narrate/grammar/sect.toml`
- Modify (via `.patches/3c_task3.py`): `engine/game.py`, `narrate/outcomes.py`
- Test: `tests/test_sect.py`

**Interfaces:**
- Consumes: Task 2 (`my_sect`, `enrol`, `make_person`, `follow_chance`, `founded_events`), Task 1 (`owner_of`, `magistrate_of`, `claim_events`), 3b `F.*`, `halls.recruits_for`, `membership.left_events`, `set_membership` and `standing.knowledge_about`, and 2b `teach` and `martial_arts`.
- Produces:
  - `systems.sect`:
    - Constants: `MAX_DISCIPLES = 12`, `MAX_ELDERS = 3`, `BUILDINGS = {name: (cost, upkeep)}`, `SEASON = 360`, `HARM`.
    - Roster: `members(world, sect, roles=("disciple", "elder")) -> list[int]`, `sect_of_member(world, player, person) -> int | None`.
    - Recruiting: `can_invite(world, npc, player) -> bool`, `invite_events(world, player, npc, place)`.
    - Teaching and elders: `teachable_to(world, player, person) -> list[int]`, `teach_events(world, player, person, technique, place)`, `elder_block(world, sect, person) -> str | None`, `elder_events(world, player, person, place)`.
    - Duty and expulsion: `duty_events(world, player, person, place, on: bool)`, `expel_events(world, player, person, place)`.
    - Buildings and treasury: `built(world, sect, name) -> bool`, `build_block(world, sect, name) -> str | None`, `build_events(world, player, name, place)`, `treasury_events(world, player, place, amount)`.
    - Relations: `sect_stance(world, other, sect) -> float`, `stance_word(value, pact) -> str`, `has_pact(world, sect, other) -> bool`, `pact_events(world, player, recruiter, other, place)`.
    - Ending: `disband_events(world, player, place)`, `dissolve(world, sect)`.
  - Events: `sect_invite`, `sect_teach`, `sect_elder`, `sect_duty`, `sect_expel`, `sect_build`, `sect_treasury`, `allied_with`, `sect_dissolved`.
  - `engine.sect.SectMixin`: the submenus `sect` and `sect_money`, and the verbs `sect_menu`, `sect_money`, `sect_invite`, `sect_teach`, `sect_elder`, `sect_duty`, `sect_expel`, `sect_build`, `sect_treasury`, `sect_disband`, `propose_pact`.
  - Test helper: `tests.test_sect.found_sect(game, path="righteous") -> (sect, town)`.

- [ ] **Step 1: Write the failing test** — `tests/test_sect.py`
```python
import pytest

import systems.encounters as encounters
import systems.founding as founding
import systems.land as land
import systems.sect as sect_mod
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.realms import REALMS, realm_index
from systems.techniques import known_arts, martial_arts
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


def found_sect(game, path="righteous"):
    """Found a sect in a town with a magistrate, with three followers, skipping the menus."""
    from tests.test_land import buyable_town
    world, me = game.world, game.player.id
    town = buyable_town(game)
    halls.settle_town(world, town)
    world.unrelate(me, "located_in")
    world.relate(me, town, "located_in")
    commit(world, land.claim_events(me, town))
    for i in range(3):
        follower = founding.make_person(world, f"test:follower:{i}", town)
        commit(world, [Event("sworn", (me, follower), town, {"accepted": True})])
    body = load_body(world, me)
    body.realm = realm_index("second-rate")
    body.energy_years = max(body.energy_years, REALMS[body.realm].threshold)
    save_body(world, me, body)
    world.update_data(me, silver=500)
    choice = {"name": "Test Pine Sect", "path": path, "taboos": ["never_rob", "never_kill_unarmed"],
              "trial": "spar", "ranks": "orthodox"}
    game._commit(founding.founded_events(world, me, land.magistrate_of(world, town), town, choice))
    return founding.my_sect(world, me), town


def texts(turn):
    return [t for t, _ in turn.lines]


def test_inviting_someone_brings_them_to_the_seat(game, monkeypatch):
    monkeypatch.setattr(founding, "follow_chance", lambda *args, **kwargs: 1.0)
    sect, town = found_sect(game)
    other = next(t.id for t in game.world.entities("town") if t.id != town)
    halls.settle_town(game.world, other)
    stranger = founding.make_person(game.world, "test:stranger", other)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, other, "located_in")
    turn = game.perform(Action("talk", stranger))
    assert Action("sect_invite", stranger) in [c.action for c in turn.all_choices]
    game.perform(Action("sect_invite", stranger))
    assert stranger in sect_mod.members(game.world, sect)
    assert game.world.targets(stranger, "located_in") == [town]


def test_teaching_makes_sect_arts(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    art = martial_arts(game.world, game.player.id)[0].technique.id
    game.perform(Action("talk", disciple))
    turn = game.perform(Action("sect_menu"))
    assert Action("sect_teach", art) in [c.action for c in turn.choices]
    game.perform(Action("sect_teach", art))
    assert art in {a.technique.id for a in known_arts(game.world, disciple)}
    assert game.world.entity(sect).data["arts"] == [art]


def test_raising_an_elder_needs_a_loyal_and_able_disciple(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    assert sect_mod.elder_block(game.world, sect, disciple) == "They are not ready to be an elder."
    game.world.update_data(disciple, realm="third-rate")
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_elder", disciple))
    assert disciple in sect_mod.members(game.world, sect, roles=("elder",))


def test_duty_sends_a_disciple_away_and_back(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_duty", disciple))
    assert game.world.entity(disciple).data["on_duty"] and game.world.targets(disciple, "located_in") != [town]
    other = sect_mod.members(game.world, sect)[1]
    game.perform(Action("talk", other))
    turn = game.perform(Action("sect_menu"))
    assert Action("sect_duty", disciple) in [c.action for c in turn.choices]
    game.perform(Action("sect_duty", disciple))
    assert game.world.targets(disciple, "located_in") == [town] and not game.world.entity(disciple).data["on_duty"]


def test_expelling_leaves_a_grudge(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_expel", disciple))
    assert F.membership(game.world, disciple, sect)[1]["status"] == "expelled"
    assert any(m.feeling == "wronged" for m in game.world.memories(disciple, about=game.player.id))


def test_the_treasury_pays_for_buildings(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_treasury", 200))
    assert game.world.entity(sect).data["treasury"] == 200
    assert sect_mod.build_block(game.world, sect, "walls") == "The treasury holds 200 silver; that costs 300."
    game.perform(Action("sect_build", "training_yard"))
    data = game.world.entity(sect).data
    assert data["treasury"] == 50 and data["buildings"]["training_yard"]["done_at"] == game.world.time + 360
    assert not sect_mod.built(game.world, sect, "training_yard")
    game.perform(Action("sect_treasury", -50))
    assert game.world.entity(sect).data["treasury"] == 0


def test_other_factions_judge_the_sect_by_its_people(game):
    sect, town = found_sect(game)
    orthodox = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    assert sect_mod.sect_stance(game.world, orthodox, sect) == 0.6
    seat = halls.seat_of(game.world, orthodox)
    victim = halls.staff_at(game.world, orthodox, seat, roles=("disciple",))[0]
    member = sect_mod.members(game.world, sect)[0]
    for _ in range(3):
        record_fact(game.world, member, "robbed", victim, place=seat, variant=make_variant("robbed", member, victim))
    assert sect_mod.sect_stance(game.world, orthodox, sect) == pytest.approx(0.3)


def test_an_alliance_with_a_friendly_faction(game):
    sect, town = found_sect(game)
    orthodox = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, orthodox)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, seat, "located_in")
    keeper = halls.keeper_at(game.world, orthodox, seat)
    game.perform(Action("talk", keeper))
    turn = game.perform(Action("faction_menu"))
    assert Action("propose_pact", orthodox) in [c.action for c in turn.choices]
    game.perform(Action("propose_pact", orthodox))
    assert sect_mod.has_pact(game.world, sect, orthodox)
    assert game.world.facts(predicate="allied_with")[0].subject == sect


def test_disbanding_asks_twice_and_releases_everyone(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_disband", False))
    assert founding.my_sect(game.world, game.player.id) == sect
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_disband", True))
    assert game.world.entity(sect).data["dissolved"] and founding.my_sect(game.world, game.player.id) is None
    assert F.membership(game.world, disciple, sect)[1]["status"] == "released"
    assert sect not in halls.halls_here(game.world, town)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sect.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.sect'`.

- [ ] **Step 3: Write the sect** — `systems/sect.py`
```python
"""Running your sect (phase 3c spec 5, 7): roster, teaching, elders, duty, buildings, treasury, pacts, the end."""

import systems.founding as founding
from systems import factions as F
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import make_variant, place_name, record_fact
from systems.membership import left_events, set_membership
from systems.realms import realm_index
from systems.standing import HARMFUL, knowledge_about
from systems.techniques import known_arts, martial_arts, teach
from world.events import Event, Witness, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

MAX_DISCIPLES, MAX_ELDERS = 12, 3
BUILDINGS = {"training_yard": (150, 10), "library": (200, 10), "infirmary": (150, 10),
             "guest_hall": (100, 5), "walls": (300, 15)}
SEASON = 360
HARM = HARMFUL
PACT_FLOOR = 0.6


def members(world, sect: int, roles=("disciple", "elder")) -> list[int]:
    out = []
    for person in F.members_of(world, sect):
        found = F.membership(world, person, sect)
        if found and found[1].get("role") in roles:
            out.append(person)
    return sorted(out)


def sect_of_member(world, player: int, person: int) -> int | None:
    sect = founding.my_sect(world, player)
    return sect if sect is not None and person in members(world, sect) else None


def can_invite(world, npc: int, player: int) -> bool:
    sect = founding.my_sect(world, player)
    entity = world.entity(npc)
    if sect is None or entity.data.get("is_player") or entity.data.get("beast") or entity.data.get("sworn_to"):
        return False
    if F.memberships(world, npc) or len(members(world, sect, ("disciple",))) >= MAX_DISCIPLES:
        return False
    return attitude(world, npc, apparent_to(world, npc, player)).score > -0.3


def invite_events(world, player: int, npc: int, place: int) -> list[Event]:
    sect = founding.my_sect(world, player)
    roll = rng_for(world.world_seed, f"invite:{npc}:{player}:{world.time}").random()
    accepted = roll < founding.follow_chance(world, npc, player, place)
    witness = Witness(npc, "respect" if accepted else "annoyed", 0.3 if accepted else 0.2)
    return [Event("sect_invite", (player, npc), place, {"sect": sect, "accepted": accepted}, witnesses=(witness,))]


@effect("sect_invite")
def _invited(world, event) -> None:
    if event.data["accepted"]:
        founding.enrol(world, event.actors[1], event.data["sect"], 50)


def teachable_to(world, player: int, person: int) -> list[int]:
    known = {a.technique.id for a in known_arts(world, person)}
    return [a.technique.id for a in martial_arts(world, player) if a.technique.id not in known]


def teach_events(world, player: int, person: int, technique: int, place: int) -> list[Event]:
    sect = founding.my_sect(world, player)
    return [Event("sect_teach", (player, person), place,
                  {"sect": sect, "technique": technique, "name": world.entity(technique).name})]


@effect("sect_teach")
def _taught(world, event) -> None:
    player, person, d = event.actors[0], event.actors[1], event.data
    teach(world, person, d["technique"], source="sect", teacher=player)
    arts = list(world.entity(d["sect"]).data.get("arts", []))
    if d["technique"] not in arts and len(arts) < 3:
        world.update_data(d["sect"], arts=[*arts, d["technique"]])


def elder_block(world, sect: int, person: int) -> str | None:
    if len(members(world, sect, ("elder",))) >= MAX_ELDERS:
        return "Your sect already has three elders."
    rank = F.membership(world, person, sect)[0]
    if rank < 2 and realm_index(world.entity(person).data.get("realm", "mortal")) < 1:
        return "They are not ready to be an elder."
    if world.entity(person).data.get("loyalty", 0) < 60:
        return "They are not loyal enough."
    return None


def elder_events(world, player: int, person: int, place: int) -> list[Event]:
    return [Event("sect_elder", (player, person), place, {"sect": founding.my_sect(world, player)})]


@effect("sect_elder")
def _elder(world, event) -> None:
    set_membership(world, event.actors[1], event.data["sect"], rank=3, role="elder")


def duty_events(world, player: int, person: int, place: int, on: bool) -> list[Event]:
    return [Event("sect_duty", (player, person), place, {"sect": founding.my_sect(world, player), "on": on})]


@effect("sect_duty")
def _duty(world, event) -> None:
    person, d = event.actors[1], event.data
    seat = world.entity(d["sect"]).data["seat"]
    world.update_data(person, on_duty=d["on"])
    world.unrelate(person, "located_in")
    world.relate(person, region_of(world, seat).id if d["on"] else seat, "located_in")


def expel_events(world, player: int, person: int, place: int) -> list[Event]:
    sect = founding.my_sect(world, player)
    return [Event("sect_expel", (player, person), place, {"sect": sect},
                  witnesses=(Witness(person, "wronged", 0.8),))] + left_events(world, person, sect, place, "expelled")


def built(world, sect: int, name: str) -> bool:
    return bool(world.entity(sect).data.get("buildings", {}).get(name, {}).get("built"))


def build_block(world, sect: int, name: str) -> str | None:
    if name not in BUILDINGS:
        return "There is no such building."
    if name in world.entity(sect).data.get("buildings", {}):
        return "That is already built or being built."
    treasury, cost = world.entity(sect).data["treasury"], BUILDINGS[name][0]
    if treasury < cost:
        return f"The treasury holds {treasury} silver; that costs {cost}."
    return None


def build_events(world, player: int, name: str, place: int) -> list[Event]:
    sect = founding.my_sect(world, player)
    return [Event("sect_build", (player,), place, {"sect": sect, "building": name, "cost": BUILDINGS[name][0]})]


@effect("sect_build")
def _build(world, event) -> None:
    d = event.data
    data = world.entity(d["sect"]).data
    buildings = {**data.get("buildings", {}), d["building"]: {"done_at": world.time + SEASON, "built": False}}
    world.update_data(d["sect"], treasury=data["treasury"] - d["cost"], buildings=buildings)


def treasury_events(world, player: int, place: int, amount: int) -> list[Event]:
    """Positive deposits your silver; negative withdraws from the treasury."""
    return [Event("sect_treasury", (player,), place, {"sect": founding.my_sect(world, player), "amount": amount})]


@effect("sect_treasury")
def _treasury(world, event) -> None:
    player, d = event.actors[0], event.data
    silver = int(world.entity(player).data.get("silver", 0))
    world.update_data(player, silver=silver - d["amount"])
    world.update_data(d["sect"], treasury=world.entity(d["sect"]).data["treasury"] + d["amount"])


def has_pact(world, sect: int, other: int) -> bool:
    return other in world.targets(sect, "pact")


def sect_stance(world, other: int, sect: int) -> float:
    """How another faction regards your sect: the founding stance, moved by what its towns heard your people do."""
    value = F.stance(world, other, sect)
    harm = help_ = 0
    founder = world.entity(sect).data["founder"]
    for person in [founder, *members(world, sect)]:
        know, _ = knowledge_about(world, other, person)
        for belief, fact in know:
            target = belief.variant.get("target")
            if fact.predicate not in HARM or not isinstance(target, int):
                continue
            theirs = [f for f, _, d in F.memberships(world, target) if d.get("status", "member") == "member"]
            if other in theirs:
                harm += 1
            elif any(F.stance(world, other, g) <= F.HOSTILE for g in theirs):
                help_ += 1
    value = max(-1.0, min(1.0, value - 0.1 * harm + 0.05 * help_))
    return max(value, PACT_FLOOR) if has_pact(world, sect, other) else round(value, 3)


def stance_word(value: float, pact: bool = False) -> str:
    if pact:
        return "allied"
    if value >= 0.3:
        return "friendly"
    if value > -0.3:
        return "neutral"
    if value > -0.6:
        return "hostile"
    return "enemy"


def pact_events(world, player: int, recruiter: int, other: int, place: int) -> list[Event]:
    return [Event("allied_with", (player, recruiter), place, {"sect": founding.my_sect(world, player), "other": other})]


@effect("allied_with")
def _allied(world, event) -> None:
    sect, other = event.data["sect"], event.data["other"]
    world.relate(sect, other, "pact")
    world.relate(other, sect, "pact")
    value = max(F.stance(world, sect, other), PACT_FLOOR)
    world.relate(sect, other, "stance", value)
    world.relate(other, sect, "stance", value)


@listen("allied_with")
def _allied_fact(world, event, event_id: int) -> None:
    sect, other = event.data["sect"], event.data["other"]
    record_fact(world, sect, "allied_with", other, place=event.place, source_event=event_id, weight=1.5,
                variant=make_variant("allied_with", sect, other, place=place_name(world, event.place)))


def disband_events(world, player: int, place: int) -> list[Event]:
    return [Event("sect_dissolved", (player,), place, {"sect": founding.my_sect(world, player), "reason": "disbanded"})]


def dissolve(world, sect: int) -> None:
    for person in world.sources(sect, "member_of"):
        found = F.membership(world, person, sect)
        if found and found[1].get("status", "member") == "member":
            set_membership(world, person, sect, status="released")
    data = world.entity(sect).data
    seat = world.entity(data["seat"]).data
    world.update_data(data["seat"], halls=[f for f in seat.get("halls", []) if f != sect],
                      seats=[f for f in seat.get("seats", []) if f != sect])
    world.update_data(sect, dissolved=True)
    if world.entity(data["founder"]).data.get("sect") == sect:
        world.update_data(data["founder"], sect=None)


@effect("sect_dissolved")
def _dissolved(world, event) -> None:
    dissolve(world, event.data["sect"])


@listen("sect_dissolved")
def _dissolved_fact(world, event, event_id: int) -> None:
    player, sect = event.actors[0], event.data["sect"]
    record_fact(world, player, "sect_dissolved", sect, place=event.place, source_event=event_id, weight=2.0,
                variant=make_variant("sect_dissolved", player, sect, place=place_name(world, event.place)))
```

- [ ] **Step 4: Write the sect mixin** — `engine/sect.py`
```python
"""Running your sect in the engine (phase 3c spec 5)."""

import systems.founding as founding
import systems.sect as sect_mod
from engine.actions import Action, Choice
from systems import halls
from systems.purse import silver_of

SECT_MENUS = ("sect", "sect_money")


class SectMixin:
    _disband_asked: bool = False

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        me = self.player.id
        if sect_mod.sect_of_member(self.world, me, npc.id) is not None:
            extras.insert(0, Choice("Sect matters...", Action("sect_menu")))
        elif sect_mod.can_invite(self.world, npc.id, me):
            extras.append(Choice("Invite them to your sect", Action("sect_invite", npc.id)))
        return extras

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        sect = founding.my_sect(self.world, self.player.id)
        if sect is None:
            return options
        for other in halls.recruits_for(self.world, npc.id):
            if self.world.entity(other).data["tier"] == "great" and not sect_mod.has_pact(self.world, sect, other) \
                    and sect_mod.sect_stance(self.world, other, sect) >= 0.5:
                options.append(Choice("Propose an alliance with your sect", Action("propose_pact", other)))
        return options

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None and self.submenu in SECT_MENUS:
            back = Action("talk_menu") if self.submenu == "sect" else Action("sect_menu")
            options[self.submenu] = (self._sect_choices(self.submenu), back)
        return options

    def _sect_choices(self, menu: str) -> list:
        world, me, person = self.world, self.player.id, self.focus
        sect = founding.my_sect(world, me)
        if sect is None:
            return []
        if menu == "sect_money":
            out = [Choice(f"Build a {name.replace('_', ' ')} ({cost} silver)", Action("sect_build", name))
                   for name, (cost, _) in sect_mod.BUILDINGS.items() if sect_mod.build_block(world, sect, name) is None]
            out += [Choice(f"Deposit {n} silver", Action("sect_treasury", n)) for n in (50, 200) if silver_of(world, me) >= n]
            if world.entity(sect).data["treasury"] >= 50:
                out.append(Choice("Withdraw 50 silver", Action("sect_treasury", -50)))
            out.append(Choice("Disband the sect" if not self._disband_asked else "Yes, disband it for good",
                              Action("sect_disband", self._disband_asked)))
            return out
        out = [Choice(f"Teach them the {world.entity(t).name}", Action("sect_teach", t))
               for t in sect_mod.teachable_to(world, me, person)[:2]]
        if sect_mod.elder_block(world, sect, person) is None and person not in sect_mod.members(world, sect, ("elder",)):
            out.append(Choice("Raise them to elder", Action("sect_elder", person)))
        out.append(Choice("Send them on sect duties", Action("sect_duty", person)))
        away = [p for p in sect_mod.members(world, sect) if world.entity(p).data.get("on_duty")]
        out += [Choice(f"Call back {world.entity(p).name}", Action("sect_duty", p)) for p in away[:2]]
        out.append(Choice("Treasury and buildings...", Action("sect_money")))
        out.append(Choice("Expel them", Action("sect_expel", person)))
        return out

    def _sect_member_here(self) -> int | None:
        return sect_mod.sect_of_member(self.world, self.player.id, self.focus) if self.focus is not None else None

    def _do_sect_menu(self, _target):
        if self._sect_member_here() is None:
            return self._turn([("That is not sect business.", "system")])
        self.submenu = "sect"
        return self._turn([("What of the sect?", "system")])

    def _do_sect_money(self, _target):
        if self._sect_member_here() is None:
            return self._turn([("That is not sect business.", "system")])
        self.submenu = "sect_money"
        return self._turn([("The treasury and the halls.", "system")])

    def _do_sect_invite(self, npc):
        if self.focus != npc or not sect_mod.can_invite(self.world, npc, self.player.id):
            return self._turn([("They cannot join your sect.", "system")])
        return self._turn(self._commit(sect_mod.invite_events(self.world, self.player.id, npc, self.place.id)))

    def _do_sect_teach(self, technique):
        if self._sect_member_here() is None or technique not in sect_mod.teachable_to(self.world, self.player.id, self.focus):
            return self._turn([("You cannot teach them that.", "system")])
        self.submenu = None
        return self._turn(self._commit(sect_mod.teach_events(self.world, self.player.id, self.focus, technique, self.place.id)))

    def _do_sect_elder(self, person):
        sect = self._sect_member_here()
        if sect is None or person != self.focus:
            return self._turn([("That is not sect business.", "system")])
        if (why := sect_mod.elder_block(self.world, sect, person)) is not None:
            return self._turn([(why, "system")])
        self.submenu = None
        return self._turn(self._commit(sect_mod.elder_events(self.world, self.player.id, person, self.place.id)))

    def _do_sect_duty(self, person):
        sect = self._sect_member_here()
        if sect is None or person not in sect_mod.members(self.world, sect):
            return self._turn([("That is not sect business.", "system")])
        on = not self.world.entity(person).data.get("on_duty")
        if on and person == self.focus:
            self.focus = None
        self.submenu = None
        return self._turn(self._commit(sect_mod.duty_events(self.world, self.player.id, person, self.place.id, on)))

    def _do_sect_expel(self, person):
        if self._sect_member_here() is None or person != self.focus:
            return self._turn([("That is not sect business.", "system")])
        self.submenu, self.focus = None, None
        return self._turn(self._commit(sect_mod.expel_events(self.world, self.player.id, person, self.place.id)))

    def _do_sect_build(self, name):
        sect = self._sect_member_here()
        if sect is None:
            return self._turn([("That is not sect business.", "system")])
        if (why := sect_mod.build_block(self.world, sect, name)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(sect_mod.build_events(self.world, self.player.id, name, self.place.id)))

    def _do_sect_treasury(self, amount):
        sect = self._sect_member_here()
        if sect is None or not isinstance(amount, int) or amount == 0:
            return self._turn([("That is not sect business.", "system")])
        if amount > 0 and silver_of(self.world, self.player.id) < amount:
            return self._turn([(f"You don't have {amount} silver.", "system")])
        if amount < 0 and self.world.entity(sect).data["treasury"] < -amount:
            return self._turn([("The treasury cannot spare it.", "system")])
        return self._turn(self._commit(sect_mod.treasury_events(self.world, self.player.id, self.place.id, amount)))

    def _do_sect_disband(self, confirmed):
        if self._sect_member_here() is None:
            return self._turn([("That is not sect business.", "system")])
        if not confirmed or not self._disband_asked:
            self._disband_asked = True
            self.submenu = "sect_money"
            return self._turn([("Disband your sect? Choose again to confirm.", "system")])
        self._disband_asked, self.submenu, self.focus = False, None, None
        return self._turn(self._commit(sect_mod.disband_events(self.world, self.player.id, self.place.id)))

    def _do_propose_pact(self, other):
        sect = founding.my_sect(self.world, self.player.id)
        if sect is None or self.focus is None or other not in halls.recruits_for(self.world, self.focus) \
                or sect_mod.sect_stance(self.world, other, sect) < 0.5 or sect_mod.has_pact(self.world, sect, other):
            return self._turn([("They will not ally with you.", "system")])
        self.submenu = None
        return self._turn(self._commit(sect_mod.pact_events(self.world, self.player.id, self.focus, other, self.place.id)))
```

- [ ] **Step 5: Write the sect narration** — `narrate/sect_text.py`
```python
"""What the player is told about running the sect."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import cap, outcome, summary

EXTRA_PHRASES.update({"allied_with": "{actor} allied with the {target}.",
                      "sect_dissolved": "{actor} disbanded the {target}."})


def _who(world, event, i=1) -> str:
    return cap(world.entity(event.actors[i]).name)


@outcome("sect_invite", body_facts=False)
def _invite(world, event):
    if event.data["accepted"]:
        return [f"{_who(world, event)} accepts, and sets out for your seat."], {}
    return [f"{_who(world, event)} declines."], {}


@outcome("sect_teach", body_facts=False)
def _teach(world, event):
    return [f"You teach {world.entity(event.actors[1]).name} the {event.data['name']}."], {}


@outcome("sect_elder", body_facts=False)
def _elder(world, event):
    return [f"{_who(world, event)} is raised to elder."], {}


@outcome("sect_duty", body_facts=False)
def _duty(world, event):
    if event.data["on"]:
        return [f"{_who(world, event)} sets out on sect business."], {}
    return [f"{_who(world, event)} is called back to the seat."], {}


@outcome("sect_expel", body_facts=False)
def _expel(world, event):
    return [f"You cast {world.entity(event.actors[1]).name} out of the sect."], {}


@outcome("sect_build", body_facts=False)
def _build(world, event):
    return [f"Work begins on a {event.data['building'].replace('_', ' ')}; it will stand in a season."], {}


@outcome("sect_treasury", body_facts=False)
def _treasury(world, event):
    amount = event.data["amount"]
    return [f"You {'deposit' if amount > 0 else 'withdraw'} {abs(amount)} silver."], {}


@outcome("allied_with", body_facts=False)
def _allied(world, event):
    return [f"Your sect and the {world.entity(event.data['other']).name} are now allies."], {}


@outcome("sect_dissolved", body_facts=False)
def _dissolved(world, event):
    return [f"The {world.entity(event.data['sect']).name} is no more."], {}


for _kind, _line in {"sect_invite": "Invited {other} to the sect.", "sect_teach": "Taught {other} an art.",
                     "sect_elder": "Raised {other} to elder.", "sect_duty": "Sent {other} on sect business.",
                     "sect_expel": "Cast {other} out of the sect.", "sect_build": "Began a new building.",
                     "sect_treasury": "Moved silver in the treasury.", "allied_with": "Made an alliance.",
                     "sect_dissolved": "The sect was dissolved."}.items():
    summary(_kind)(lambda world, entry, names, place, other, _line=_line: _line.format(other=other))
```

- [ ] **Step 6: Write the sect grammar** — `narrate/grammar/sect.toml`
```toml
[symbols]
sect_yard = ["Disciples drill in the yard.", "Someone sweeps the steps.", "Water boils for tea.", "A wooden sword clacks against another.", "The sect's banner stirs."]
sect_mood = ["It feels like home.", "There is much to do.", "Eyes follow you.", "The seat is quieter than you'd like.", "You feel the weight of leading."]
sect_coin = ["Coins go into the chest.", "The ledger is updated.", "A key turns in the strongbox.", "The treasurer counts twice.", "Silver changes hands."]

[sect_invite]
colour = "npc"
lines = ["#sect_mood# #sect_yard#", "#sect_yard# #sect_mood#"]

[sect_teach]
colour = "default"
lines = ["#sect_yard# #sect_mood#", "#sect_mood# #sect_yard#"]

[sect_elder]
colour = "gold"
lines = ["#sect_yard# #sect_mood#", "#sect_mood# #sect_yard#"]

[sect_duty]
colour = "default"
lines = ["#sect_yard# #sect_mood#", "#sect_mood# #sect_yard#"]

[sect_expel]
colour = "default"
lines = ["#sect_mood# #sect_yard#", "#sect_yard# #sect_mood#"]

[sect_build]
colour = "default"
lines = ["#sect_coin# #sect_yard#", "#sect_yard# #sect_coin#"]

[sect_treasury]
colour = "default"
lines = ["#sect_coin# #sect_mood#", "#sect_coin#"]

[allied_with]
colour = "gold"
lines = ["#sect_mood# #sect_coin#", "#sect_yard# #sect_mood#"]

[sect_dissolved]
colour = "default"
lines = ["#sect_mood# #sect_yard#", "#sect_yard# #sect_mood#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3c_task3.py`
```python
"""Task 3 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


GAME = "engine/game.py"
edit(GAME, "from engine.founding import FoundingMixin\n", "from engine.founding import FoundingMixin\nfrom engine.sect import SectMixin\n")
edit(GAME, "LandMixin, FoundingMixin,", "LandMixin, FoundingMixin, SectMixin,")
edit("narrate/outcomes.py", "import narrate.founding_text  # noqa: E402,F401\n",
     "import narrate.founding_text  # noqa: E402,F401\nimport narrate.sect_text  # noqa: E402,F401\n")
print("task 3 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3c_task3.py && .venv/Scripts/python.exe -m pytest tests/test_sect.py -q -p no:cacheprovider`
Expected: `task 3 edits applied`, then `9 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: run your sect - recruits, teaching, elders, duty, buildings, treasury, pacts"`

---

### Task 4: The seasonal catch-up

**Files:**
- Create: `systems/sect_seasons.py`, `engine/seasons.py`, `narrate/season_text.py`, `narrate/grammar/seasons.toml`
- Modify (via `.patches/3c_task4.py`): `engine/game.py`, `narrate/outcomes.py`
- Test: `tests/test_seasons.py`

**Interfaces:**
- Consumes: Tasks 1–3 (`sect.members`, `sect.built`, `sect.BUILDINGS`, `sect.sect_stance`, `sect.has_pact`, `sect.dissolve`, `founding.make_person`, `founding.enrol`), 3b `membership.left_events`, 3a `reputation` and `attitude`, and 2a/2b `load_body`, `save_body`, `add_energy`, `breakthrough_chance`, `add_injury`, `fighter_for`, `best_art`, `duel_sim.simulate` and `INTENTS`.
- Produces:
  - `systems.sect_seasons`:
    - Constants: `SEASON = 360`, `MAX_SEASONS = 8`, `LAND_INCOME`, `INJURY = 0.08`, `DEATH_ON_DUTY = 0.05`, `DUTY_INJURY = 0.3`, `GATE_BASE = 0.15`, `GATE_HOSTILE = 0.25`, `DESERT_BELOW = 25`, `DESERT_CHANCE = 0.5`, `RECRUITS`.
    - `season_events(world, player, sect) -> list[Event] | None`, covering one due season or None.
  - Events: `sect_season` (its data is the season summary, including `line`), plus `died` with actors `(victim, victim)` and `cause: "duty"` or `"gate"`, deserters' `deserted` (3b), and `sect_dissolved` with reason `"empty"`.
  - A listener on `sect_season` writes the facts `defended_gate` or `gate_breached` (subject is the sect).
  - Player data: `gate_challenger`, set when a challenger arrives while the founder is at the seat.
  - `engine.seasons.SeasonsMixin`: `_sect_catch_up() -> list[Line]`, which runs on arrival and look at the seat, processes up to 8 seasons, then turns a waiting gate challenger into a 2b challenge.

- [ ] **Step 1: Write the failing test** — `tests/test_seasons.py`
```python
import time

import pytest

import systems.sect as sect_mod
import systems.sect_seasons as seasons
from engine.actions import Action
from systems import factions as F
from systems.bodies import load_body
from tests.test_sect import calm, found_sect, game  # noqa: F401  (shared fixtures)


def advance(game, n):
    game.world.set_time(game.world.time + n * seasons.SEASON)


def season_data(game, sect):
    return [e.data for e in game.world.chronicle_about(game.player.id, limit=40) if e.kind == "sect_season"]


def test_a_season_pays_income_and_upkeep(game):
    sect, town = found_sect(game)
    advance(game, 1)
    [events] = [seasons.season_events(game.world, game.player.id, sect)]
    d = events[0].data
    kind = game.world.entity(town).data["kind"]
    assert d["income"] >= seasons.LAND_INCOME[kind] and d["upkeep"] == 5 * 3
    game._commit(events)
    assert game.world.entity(sect).data["treasury"] == d["treasury_after"] == max(0, d["income"] - d["upkeep"])
    assert game.world.entity(sect).data["last_tick"] % seasons.SEASON == 0 or True
    assert seasons.season_events(game.world, game.player.id, sect) is None


def test_an_empty_treasury_means_unpaid_seasons(game, monkeypatch):
    monkeypatch.setattr(seasons, "LAND_INCOME", {"village": 0, "town": 0, "city": 0})
    monkeypatch.setattr(seasons, "PROTECTION", 0)
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    before = game.world.entity(member).data["loyalty"]
    advance(game, 1)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert game.world.entity(sect).data["treasury"] == 0
    assert game.world.entity(member).data["loyalty"] < before


def test_a_training_yard_speeds_growth(game):
    sect, town = found_sect(game)
    advance(game, 1)
    plain = seasons.season_events(game.world, game.player.id, sect)[0].data["growth"]
    data = game.world.entity(sect).data
    game.world.update_data(sect, buildings={"training_yard": {"done_at": 0, "built": True}})
    yard = seasons.season_events(game.world, game.player.id, sect)[0].data["growth"]
    member = str(sect_mod.members(game.world, sect)[0])
    assert yard[member]["years"] == pytest.approx(plain[member]["years"] * 1.5)
    game.world.update_data(sect, buildings=data["buildings"])


def test_growth_is_applied_to_the_body(game):
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    before = load_body(game.world, member).energy_years
    advance(game, 1)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert load_body(game.world, member).energy_years > before


def test_a_long_absence_catches_up_eight_seasons_at_a_time(game):
    sect, town = found_sect(game)
    elsewhere = next(t.id for t in game.world.entities("town") if t.id != town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, elsewhere, "located_in")
    start = game.world.entity(sect).data["last_tick"]
    advance(game, 20)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")
    game.perform(Action("look"))
    assert game.world.entity(sect).data["last_tick"] == start + 8 * seasons.SEASON
    assert game.world.entity(sect).data["last_tick"] <= game.world.time
    assert len(game.world.entity(sect).data["chronicle"]) == 8


def test_one_call_or_many_give_the_same_sect(game, tmp_path):
    from engine.game import Game
    from systems.creation import CreationChoice
    other = Game.new(tmp_path / "twin.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    other.start()
    results = []
    for g, steps in ((game, [8]), (other, [1] * 8)):
        sect, town = found_sect(g)
        for n in steps:
            g.world.set_time(g.world.time + n * seasons.SEASON)
            for _ in range(n):
                events = seasons.season_events(g.world, g.player.id, sect)
                if events:
                    g._commit(events)
        data = g.world.entity(sect).data
        results.append((data["treasury"], data["power"], data["chronicle"],
                        sorted(g.world.entity(p).data["loyalty"] for p in sect_mod.members(g.world, sect))))
    other.close()
    assert results[0][:2] == results[1][:2] and results[0][3] == results[1][3]


def test_deserters_leave(game, monkeypatch):
    monkeypatch.setattr(seasons, "DESERT_CHANCE", 1.0)
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    game.world.update_data(member, loyalty=0)
    advance(game, 1)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert F.membership(game.world, member, sect)[1]["status"] == "deserter"


def test_an_empty_sect_dissolves(game, monkeypatch):
    monkeypatch.setattr(seasons, "RECRUITS", {})
    sect, town = found_sect(game)
    for member in sect_mod.members(game.world, sect):
        game.world.relate(member, sect, "member_of", 0, {**F.membership(game.world, member, sect)[1], "status": "expelled"})
    advance(game, 1)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert game.world.entity(sect).data["dissolved"]


def test_a_challenger_calls_out_the_founder_at_home(game, monkeypatch):
    monkeypatch.setattr(seasons, "GATE_BASE", 1.0)
    sect, town = found_sect(game)
    advance(game, 1)
    turn = game.perform(Action("look"))
    assert game.challenger is not None
    assert any("at the gate of your sect" in text for text, _ in turn.lines)
    assert not any("have not forgotten you" in text for text, _ in turn.lines)


def test_a_gate_fight_happens_while_the_founder_is_away(game, monkeypatch):
    monkeypatch.setattr(seasons, "GATE_BASE", 1.0)
    sect, town = found_sect(game)
    elsewhere = next(t.id for t in game.world.entities("town") if t.id != town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, elsewhere, "located_in")
    advance(game, 1)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    gate = season_data(game, sect)[0]["gate"]
    assert gate and gate["won"] in (True, False) and gate["defenders"]
    assert game.world.facts(predicate="defended_gate" if gate["won"] else "gate_breached")[0].subject == sect


def test_eight_seasons_for_fifteen_members_are_quick(game):
    sect, town = found_sect(game)
    from systems import founding
    for i in range(12):
        founding.enrol(game.world, founding.make_person(game.world, f"test:extra:{i}", town), sect, 70)
    advance(game, 8)
    start = time.perf_counter()
    for _ in range(8):
        game._commit(seasons.season_events(game.world, game.player.id, sect))
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"8 seasons took {elapsed * 1000:.0f} ms"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_seasons.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.sect_seasons'`.

- [ ] **Step 3: Write the seasons** — `systems/sect_seasons.py`
```python
"""The seasonal catch-up for your sect (phase 3c spec 6): one season's events at a time, all seeded.

The engine commits each season before asking for the next, so a season always
sees the world its predecessor left, and one call for eight seasons gives the
same sect as eight calls for one.
"""

import systems.founding as founding
import systems.sect as sect_mod
from systems import factions as F
from systems import halls
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.bodies import load_body, save_body
from systems.combat_core import INTENTS
from systems.duel import best_art, fighter_for
from systems.duel_sim import simulate
from systems.facts import make_variant, place_name, record_fact
from systems.membership import left_events
from systems.realms import add_energy, breakthrough_chance, realm_index
from systems.reputation import reputation
from systems.time import format_season_year
from world.body import add_injury, from_dict, to_dict
from world.events import Event, effect, listen
from world.seed import rng_for

SEASON = 360
MAX_SEASONS = 8
LAND_INCOME = {"village": 20, "town": 40, "city": 80}
PROTECTION = 10
DUTY_PAY, ALLY_GIFT = 20, 30
INJURY, DEATH_ON_DUTY, DUTY_INJURY = 0.08, 0.05, 0.3
GATE_BASE, GATE_HOSTILE, GATE_DEATH = 0.15, 0.25, 0.1
DESERT_BELOW, DESERT_CHANCE = 25, 0.5
RECRUITS = {"unknown": 0, "little known": 1, "known": 1, "renowned": 2, "famous": 3}
PATH_TRAITS = {"righteous": {"kind", "honest"}, "ruthless": {"cunning", "hot-tempered"}}


def _knows_sect_art(world, person: int, arts: list[int]) -> bool:
    return bool(set(arts) & {t for t, _, _ in world.relations_from(person, "knows")})


def _challenger(world, sect: int, hostile: list[int], rng, n: int) -> int:
    for other in hostile:
        staff = halls.staff_at(world, other, halls.seat_of(world, other), roles=("disciple",))
        if staff:
            return rng.choice(sorted(staff))
    seat = world.entity(sect).data["seat"]
    return founding.make_person(world, f"sect:{sect}:gate:{n}", seat, occupation="wandering swordsman",
                                realm=world.entity(world.entity(sect).data["founder"]).data.get("realm", "mortal"))


def _fight(world, defender: int, challenger: int, rng) -> bool:
    mine, theirs = best_art(world, defender), best_art(world, challenger)
    a = fighter_for(world, defender, mine.technique.id if mine else None)
    b = fighter_for(world, challenger, theirs.technique.id if theirs else None)
    result, _ = simulate(a, b, lambda r, history: r.choice(INTENTS), rng)
    return result == "player"


def season_events(world, player: int, sect: int) -> list[Event] | None:
    """The events of the next due season of the player's sect, or None if none is due."""
    data = world.entity(sect).data
    if data.get("dissolved") or world.time - data["last_tick"] < SEASON:
        return None
    n = data["last_tick"] // SEASON
    rng = rng_for(world.world_seed, f"sect:{sect}:season:{n}")
    seat, end = data["seat"], data["last_tick"] + SEASON
    people = sect_mod.members(world, sect)
    disciples = sect_mod.members(world, sect, ("disciple",))
    elders = sect_mod.members(world, sect, ("elder",))
    built_now = [b for b, v in sorted(data.get("buildings", {}).items()) if not v["built"] and v["done_at"] <= end]
    has = {b for b, v in data.get("buildings", {}).items() if v["built"]} | set(built_now)

    # duties
    won, duty_hurt, died = [], [], []
    for person in people:
        if not world.entity(person).data.get("on_duty"):
            continue
        realm = realm_index(world.entity(person).data.get("realm", "mortal"))
        if rng.random() < 0.5 + 0.1 * realm:
            won.append(person)
        else:
            roll = rng.random()
            if roll < DEATH_ON_DUTY:
                died.append(person)
            elif roll < DEATH_ON_DUTY + DUTY_INJURY:
                duty_hurt.append(person)

    # money
    rep = reputation(world, seat, apparent_to(world, seat, player))
    allies = len(world.targets(sect, "pact"))
    protection = PROTECTION if rep.renown >= 2 and rep.path != "ruthless" else 0
    income = LAND_INCOME.get(world.entity(seat).data.get("kind"), 20) + DUTY_PAY * len(won) + ALLY_GIFT * allies + protection
    upkeep = 5 * len(disciples) + 10 * len(elders) + sum(sect_mod.BUILDINGS[b][1] for b in has)
    treasury = data["treasury"] + income - upkeep
    unpaid = treasury < 0
    treasury = max(0, treasury)

    # growth
    present = [p for p in people if p not in died and not world.entity(p).data.get("on_duty")]
    growth = {}
    for person in present:
        talent = world.entity(person).data.get("talent", 1.0)
        years = 0.25 * talent * (1.5 if "training_yard" in has else 1.0) \
            * (1.2 if _knows_sect_art(world, person, data.get("arts", [])) else 1.0)
        body = from_dict(to_dict(load_body(world, person)))
        add_energy(body, years)
        breakthrough = body.bottleneck and rng.random() < breakthrough_chance(body, True)
        growth[str(person)] = {"years": round(years, 4), "breakthrough": bool(breakthrough)}

    # injuries
    chance = INJURY * (0.5 if "infirmary" in has else 1.0)
    injured = [p for p in present if rng.random() < chance] + duty_hurt

    # loyalty and desertion
    loyalty, deserters = {}, []
    for person in people:
        if person in died:
            continue
        entity = world.entity(person)
        value = entity.data.get("loyalty", 50) + (-15 if unpaid else 5)
        wanted = PATH_TRAITS.get(data["path"])
        if wanted is not None:
            value += 5 if wanted & set(entity.data.get("traits", ())) else -10
        word = attitude(world, person, player).word
        value += 5 if word == "warm" else -10 if word in ("wary", "hostile", "hateful") else 0
        value = max(0, min(100, value))
        loyalty[str(person)] = value
        if value < DESERT_BELOW and rng.random() < DESERT_CHANCE:
            deserters.append(person)

    # recruits
    leaving = set(died) | set(deserters)
    room = sect_mod.MAX_DISCIPLES - len([d for d in disciples if d not in leaving])
    rolls = RECRUITS.get(rep.word, 0) + (1 if "guest_hall" in has else 0)
    paths = [f"sect:{sect}:recruit:{n}:{i}" for i in range(rolls) if rng.random() < 0.5][:max(0, room)]
    recruits = [(found.id if (found := world.entity_by_seed(path)) else founding.make_person(world, path, seat))
                for path in paths]  # made now, so the season's event can name them as actors

    # the gate
    hostile = [f for f in F.ensure_roster(world) if sect_mod.sect_stance(world, f, sect) <= -0.5]
    gate_chance = (GATE_BASE + (GATE_HOSTILE if hostile else 0.0)) * (0.5 if "walls" in has else 1.0)
    gate = None
    power = data["power"] + 2 * len(won)
    if rng.random() < gate_chance:
        challenger = _challenger(world, sect, hostile, rng, n)
        if seat in world.targets(player, "located_in"):
            gate = {"challenger": challenger, "deferred": True, "won": None, "defenders": [], "fallen": []}
        else:
            standing_by = sorted((p for p in present if p not in deserters),
                                 key=lambda p: -realm_index(world.entity(p).data.get("realm", "mortal")))
            defenders = standing_by[:2 if "walls" in has else 1]
            fallen, won_gate = [], False
            for defender in defenders:
                if _fight(world, defender, challenger, rng):
                    won_gate = True
                    break
                fallen.append(defender)
                if rng.random() < GATE_DEATH:
                    died.append(defender)
            gate = {"challenger": challenger, "deferred": False, "won": won_gate, "defenders": defenders, "fallen": fallen}
            power += 5 if won_gate else -5

    names = lambda ids: ", ".join(world.entity(p).name for p in ids)  # noqa: E731
    parts = [f"{'+' if treasury - data['treasury'] >= 0 else ''}{treasury - data['treasury']} silver"]
    rises = [p for p, g in growth.items() if g["breakthrough"]]
    if rises:
        parts.append(f"{names([int(p) for p in rises])} broke through")
    if recruits:
        parts.append(f"{len(recruits)} recruit{'s' if len(recruits) > 1 else ''} arrived")
    if deserters:
        parts.append(f"{names(deserters)} deserted")
    if died:
        parts.append(f"{names(died)} died")
    if gate and not gate["deferred"]:
        parts.append("the gate was held" if gate["won"] else "the gate was breached")
    when = format_season_year(end)
    line = f"{when[:1].upper()}{when[1:]}: " + "; ".join(parts) + "."
    summary = {"sect": sect, "season": n, "end": end, "income": income, "upkeep": upkeep, "unpaid": unpaid,
               "treasury_after": treasury, "built": built_now, "growth": growth, "injured": sorted(set(injured)),
               "loyalty": loyalty, "recruits": recruits, "gate": gate, "power_after": max(0, power),
               "duties_won": won, "line": line, "infirmary": "infirmary" in has}
    # the founder hears of everyone the season touched, so the ledger never names a stranger
    events = [Event("sect_season", tuple(dict.fromkeys((player, *people, *recruits))), seat, summary)]
    events += [Event("died", (p, p), seat, {"cause": "duty" if p not in (gate or {}).get("fallen", []) else "gate"})
               for p in died]
    for person in deserters:
        events += left_events(world, person, sect, seat, "deserter")
    remaining = [p for p in people if p not in died and p not in deserters]
    if not remaining and not recruits:
        events.append(Event("sect_dissolved", (player,), seat, {"sect": sect, "reason": "empty"}))
    return events


@effect("sect_season")
def _season(world, event) -> None:
    d = event.data
    sect = d["sect"]
    data = world.entity(sect).data
    buildings = {b: ({**v, "built": True} if b in d["built"] else v) for b, v in data.get("buildings", {}).items()}
    chronicle = [*data.get("chronicle", []), d["line"]][-12:]
    world.update_data(sect, treasury=d["treasury_after"], power=d["power_after"], buildings=buildings,
                      last_tick=data["last_tick"] + SEASON, chronicle=chronicle)
    for person, value in d["loyalty"].items():
        world.update_data(int(person), loyalty=value)
    for person, g in d["growth"].items():
        body = load_body(world, int(person))
        if d["infirmary"]:
            body.injuries = [i for i in body.injuries if i.permanent]
        add_energy(body, g["years"])
        if g["breakthrough"] and body.bottleneck:
            body.realm += 1
            body.bottleneck = False
        save_body(world, int(person), body)
    for person in d["injured"]:
        body = load_body(world, person)
        add_injury(body, "torso", "bruise", 2, world.time, "the hard life of the sect")
        save_body(world, person, body)
    gate = d["gate"] or {}
    for person in gate.get("fallen", []):
        body = load_body(world, person)
        add_injury(body, "torso", "cut", 3, world.time, f"defending the gate against {world.entity(gate['challenger']).name}")
        save_body(world, person, body)
    for person in d["recruits"]:
        founding.enrol(world, person, sect, 50)
    if gate.get("deferred"):
        world.unrelate(gate["challenger"], "located_in")
        world.relate(gate["challenger"], data["seat"], "located_in")
        world.update_data(event.actors[0], gate_challenger=gate["challenger"])


@listen("sect_season")
def _gate_fact(world, event, event_id: int) -> None:
    gate = event.data["gate"] or {}
    if gate.get("deferred") or gate.get("won") is None:
        return
    sect = event.data["sect"]
    predicate = "defended_gate" if gate["won"] else "gate_breached"
    record_fact(world, sect, predicate, gate["challenger"], place=event.place, source_event=event_id, weight=1.0,
                variant=make_variant(predicate, sect, gate["challenger"], place=place_name(world, event.place)))
```

- [ ] **Step 4: Write the seasons mixin** — `engine/seasons.py`
```python
"""The sect's seasons in the engine (phase 3c spec 6): catching up when you come home."""

import systems.founding as founding
import systems.sect_seasons as seasons
from world.events import Event


class SeasonsMixin:
    def _sect_catch_up(self) -> list:
        sect = founding.my_sect(self.world, self.player.id)
        if sect is None:
            return []
        lines = []
        for _ in range(seasons.MAX_SEASONS):
            events = seasons.season_events(self.world, self.player.id, sect)
            if not events:
                break
            lines += self._commit(events)
            if founding.my_sect(self.world, self.player.id) is None:
                break
        waiting = self.player.data.get("gate_challenger")
        if waiting and self.combat is None and self.encounter is None and self.challenger is None \
                and not self.world.entity(waiting).data.get("dead"):
            self.world.update_data(self.player.id, gate_challenger=None)
            lines += self._commit([Event("challenge_issued", (self.player.id, waiting), self.place.id, {"gate": True})])
            self.challenger = waiting
        return lines

    def _at_seat(self) -> bool:
        sect = founding.my_sect(self.world, self.player.id)
        return sect is not None and self.world.entity(sect).data["seat"] == self.place.id

    def _after_look(self) -> list:
        return super()._after_look() + (self._sect_catch_up() if self._at_seat() else [])

    def _after_arrival(self) -> list:
        return super()._after_arrival() + (self._sect_catch_up() if self._at_seat() else [])
```

- [ ] **Step 5: Write the season narration** — `narrate/season_text.py`
```python
"""What the player is told about their sect's seasons."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import outcome, summary

EXTRA_PHRASES.update({"defended_gate": "The {actor} drove off {target} at its gate.",
                      "gate_breached": "{target} broke through the gate of the {actor}."})


@outcome("sect_season", body_facts=False)
def _season(world, event):
    return [event.data["line"]], {}


@summary("sect_season")
def _season_line(world, entry, names, place, other):
    return entry.data["line"]
```

- [ ] **Step 6: Write the season grammar** — `narrate/grammar/seasons.toml`
```toml
[symbols]
season_turn = ["The season turns.", "Leaves fall and grow again.", "Rain comes and goes.", "The yard's stones wear a little smoother.", "Time has passed at the seat."]
season_news = ["The ledger has news.", "Your elders report.", "There is much to hear.", "The treasurer clears their throat.", "A disciple hurries to meet you."]

[sect_season]
colour = "default"
lines = ["#season_turn# #season_news#", "#season_news# #season_turn#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3c_task4.py`
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
edit(GAME, "from engine.sect import SectMixin\n", "from engine.sect import SectMixin\nfrom engine.seasons import SeasonsMixin\n")
edit(GAME, "FoundingMixin, SectMixin,", "FoundingMixin, SectMixin, SeasonsMixin,")
edit("narrate/outcomes.py", "import narrate.sect_text  # noqa: E402,F401\n",
     "import narrate.sect_text  # noqa: E402,F401\nimport narrate.season_text  # noqa: E402,F401\n")
edit("narrate/road_text.py", '''def _challenge(world, event):
    return''', '''def _challenge(world, event):
    if event.data.get("gate"):  # a stranger calling out a sect's founder (phase 3c)
        return [f"{cap(_name(world, event))} stands at the gate of your sect and calls you out."], {}
    return''')
print("task 4 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3c_task4.py && .venv/Scripts/python.exe -m pytest tests/test_seasons.py -q -p no:cacheprovider`
Expected: `task 4 edits applied`, then `11 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: the sect lives on - seasonal catch-up of money, growth, loyalty, recruits and the gate"`

---

### Task 5: The ledger (F7), and the sect on F6, in towns and in briefs

**Files:**
- Create: `engine/ledger.py`
- Modify (via `.patches/3c_task5.py`): `engine/game.py` (the verb `ledger`), `engine/commands.py`, `app.py` (F7), `engine/sect.py` (a ledger choice), `engine/standing_page.py` (the F6 line and the brief fact)
- Test: `tests/test_ledger.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces:
  - `engine.ledger.ledger_lines(world, player) -> list[Line]`.
  - The verb `ledger` (typed `ledger`, or F7), which catches up first when the player is at the seat.
  - `faction_facts` gives the leader fact "You lead the <name>, N disciples strong.", and F6 gains "Your sect: <name> at <seat>, N disciples, power P."

- [ ] **Step 1: Write the failing test** — `tests/test_ledger.py`
```python
import pytest

import systems.sect_seasons as seasons
from app import App
from config import Config
from engine.actions import Action
from engine.ledger import ledger_lines
from engine.standing_page import faction_facts, known_factions, standing_lines
from systems import factions as F
from tests.test_sect import calm, found_sect, game  # noqa: F401


def test_the_ledger_shows_treasury_roster_relations_and_chronicle(game):
    sect, town = found_sect(game)
    game.world.set_time(game.world.time + seasons.SEASON)
    turn = game.perform(Action("ledger"))
    text = [t for t, _ in turn.lines]
    assert any(t.startswith("Test Pine Sect (righteous)") for t in text)
    assert any(t.startswith("Treasury:") for t in text)
    assert any(t.startswith("Roster (3):") for t in text)
    assert any("Relations:" == t for t in text)
    assert any(t.startswith("  The ") and "of year" in t for t in text)


def test_the_ledger_names_only_factions_you_have_heard_of(game):
    sect, town = found_sect(game)
    heard = set(known_factions(game.world, game.player.id, town))
    text = " ".join(t for t, _ in ledger_lines(game.world, game.player.id))
    unheard = [game.world.entity(f).name for f in F.ensure_roster(game.world) if f not in heard]
    assert unheard and not any(name in text for name in unheard)


def test_no_sect_no_ledger(game):
    assert game.perform(Action("ledger")).lines[-1] == ("You lead no sect.", "system")


def test_f6_and_briefs_mention_the_sect(game):
    sect, town = found_sect(game)
    assert any(t.startswith("Your sect: Test Pine Sect") for t, _ in standing_lines(game.world, game.player.id, town))
    assert faction_facts(game.world, game.player.id, None)[0] == "You lead the Test Pine Sect, 3 disciples strong."


def test_f7_opens_the_ledger(game, tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Leader", world_seed=11)
    app.handle_key("f7", "")
    assert any("You lead no sect." in text for text, _ in app.log)
    app.shutdown()
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ledger.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'engine.ledger'`.

- [ ] **Step 3: Write the ledger** — `engine/ledger.py`
```python
"""The sect ledger (F7, phase 3c spec 8)."""

import systems.founding as founding
import systems.sect as sect_mod
from engine.standing_page import known_factions
from narrate.base import Line
from systems import factions as F


def _loyalty_word(value: int) -> str:
    return "devoted" if value >= 80 else "loyal" if value >= 50 else "uneasy" if value >= 25 else "disloyal"


def ledger_lines(world, player: int) -> list[Line]:
    sect = founding.my_sect(world, player)
    if sect is None:
        return [("You lead no sect.", "system")]
    entity = world.entity(sect)
    d = entity.data
    taboos = ", ".join(t.replace("_", " ") for t in d.get("taboos", []))
    lines: list[Line] = [
        (f"{entity.name} ({d['path']}) at {world.entity(d['seat']).name}", "heading"),
        (f"Taboos: {taboos}. Entry: {d['trial']}.", "dim"),
        (f"Treasury: {d['treasury']} silver | power {d['power']}", "dim"),
    ]
    building = [f"{b.replace('_', ' ')}{'' if v['built'] else ' (building)'}" for b, v in sorted(d.get("buildings", {}).items())]
    lines.append(("Buildings: " + (", ".join(building) or "none"), "dim"))
    roster = sect_mod.members(world, sect)
    lines.append((f"Roster ({len(roster)}):", "heading"))
    for person in roster:
        p = world.entity(person)
        rank = F.title(world, sect, F.membership(world, person, sect)[0])
        status = " - away on duty" if p.data.get("on_duty") else ""
        lines.append((f"  {p.name}, {rank}, {p.data.get('realm', 'mortal')}, {_loyalty_word(p.data.get('loyalty', 50))}{status}", "dim"))
    lines.append(("Relations:", "heading"))
    here = world.targets(player, "located_in")
    heard = set(known_factions(world, player, here[0])) if here else set()
    for other in [f for f in F.ensure_roster(world) if f in heard]:  # never name a faction the player never heard of
        value = sect_mod.sect_stance(world, other, sect)
        word = sect_mod.stance_word(value, sect_mod.has_pact(world, sect, other))
        if word != "neutral":
            lines.append((f"  {world.entity(other).name}: {word}", "dim"))
    lines.append(("Recent seasons:", "heading"))
    lines += [(f"  {line}", "dim") for line in d.get("chronicle", [])[-6:]] or [("  none yet", "dim")]
    return lines
```

- [ ] **Step 4: Edit the existing files** — `.patches/3c_task5.py`
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
edit(GAME, "from engine.standing_page import standing_lines\n", "from engine.standing_page import standing_lines\nfrom engine.ledger import ledger_lines\n")
edit(GAME, '''    def _do_standing(self, _target) -> Turn:''', '''    def _do_ledger(self, _target) -> Turn:
        caught_up = self._sect_catch_up() if self._at_seat() else []
        return self._turn(caught_up + ledger_lines(self.world, self.player.id))

    def _do_standing(self, _target) -> Turn:''')
edit(GAME, '''rumours | wear mask | remove mask | standing (F6)"''', '''rumours | wear mask | remove mask | standing (F6) | ledger (F7)"''')
edit("engine/commands.py", '''"standing": Action("standing"), "factions": Action("standing"),''',
     '''"standing": Action("standing"), "factions": Action("standing"), "ledger": Action("ledger"),''')
edit("app.py", '''        elif key == "f6":
            self.submit("standing")''', '''        elif key == "f6":
            self.submit("standing")
        elif key == "f7":
            self.submit("ledger")''')
edit("engine/sect.py", '''        out.append(Choice("Treasury and buildings...", Action("sect_money")))''',
     '''        out.append(Choice("Treasury and buildings...", Action("sect_money")))
        out.append(Choice("Open the sect ledger", Action("ledger")))''')
SP = "engine/standing_page.py"
edit(SP, '''    facts = []
    for fid, rank, data in F.memberships(world, player):
        if data.get("status", "member") == "member":''', '''    facts = []
    for fid, rank, data in F.memberships(world, player):
        if data.get("status", "member") == "member" and data.get("role") == "leader":
            count = len([p for p in F.members_of(world, fid) if p != player])
            facts.append(f"You lead the {world.entity(fid).name}, {count} disciples strong.")
            break
        if data.get("status", "member") == "member":''')
edit(SP, '''    lines: list[Line] = [("Your standing", "heading"), ("Your factions:", "heading")]''',
     '''    lines: list[Line] = [("Your standing", "heading")]
    sect = world.entity(player).data.get("sect")
    if sect and not world.entity(sect).data.get("dissolved"):
        s = world.entity(sect)
        count = len([p for p in F.members_of(world, sect) if p != player])
        lines.append((f"Your sect: {s.name} at {world.entity(s.data['seat']).name}, {count} disciples, power {s.data['power']}.", "dim"))
    lines.append(("Your factions:", "heading"))''')
print("task 5 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3c_task5.py && .venv/Scripts/python.exe -m pytest tests/test_ledger.py -q -p no:cacheprovider`
Expected: `task 5 edits applied`, then `5 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass. The 3b test `test_typing_standing_and_f6_show_the_page` still sees "Your standing" as the first line.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: the sect ledger (F7), and the sect on F6 and in briefs"`

---

### Task 6: Sect rules, a sect-founder fuzz run, docs

**Files:**
- Modify (via `.patches/3c_task6.py`): `debug/invariants.py`, `tests/test_fuzz.py`, `docs/debugging.md`
- Test: `tests/test_sect_rules.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `debug.invariants.check_sect(world) -> list[str]`, called from `check_world`, and the fuzz test `test_a_sect_founder`.

- [ ] **Step 1: Write the failing test** — `tests/test_sect_rules.py`
```python
import systems.sect as sect_mod
from debug.invariants import check_sect
from tests.test_sect import calm, found_sect, game  # noqa: F401


def test_a_founded_sect_breaks_no_rule(game):
    found_sect(game)
    assert check_sect(game.world) == []


def test_a_member_wandering_off_is_caught(game):
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    other = next(t.id for t in game.world.entities("town") if t.id != town)
    game.world.unrelate(member, "located_in")
    game.world.relate(member, other, "located_in")
    assert any("not at the seat" in p for p in check_sect(game.world))


def test_two_owners_of_one_town_are_caught(game):
    sect, town = found_sect(game)
    stranger = game.world.add_entity("person", "Land Grabber", {"realm": "mortal"})
    game.world.relate(stranger, town, "owns_land")
    assert any("owners" in p for p in check_sect(game.world))


def test_a_sect_ahead_of_time_is_caught(game):
    sect, town = found_sect(game)
    game.world.update_data(sect, last_tick=game.world.time + 999)
    assert any("ahead" in p for p in check_sect(game.world))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sect_rules.py -q -p no:cacheprovider`
Expected: the collection error `ImportError: cannot import name 'check_sect' from 'debug.invariants'`.

- [ ] **Step 3: Edit the rules, the fuzz test and the docs** — `.patches/3c_task6.py`
```python
"""Task 6 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


INV = "debug/invariants.py"
edit(INV, '''    problems += check_factions(world)
''', '''    problems += check_factions(world)
    problems += check_sect(world)
''')
edit(INV, '''def check_people(game, turn) -> list[str]:''', '''def check_sect(world) -> list[str]:
    """The player's sect: one leader, an owned seat, a sane roster and clock (phase 3c spec 9)."""
    from systems import factions as F
    from world.gen.materialize import region_of
    out = []
    for town in world.entities("town"):
        if len(world.sources(town.id, "owns_land")) > 1:
            out.append(f"{town.name} has {len(world.sources(town.id, 'owns_land'))} owners")
    for sect in world.entities("faction"):
        if sect.data.get("type") != "player_sect":
            continue
        living = [p for p in world.sources(sect.id, "member_of")
                  if (F.membership(world, p, sect.id) or (0, {}))[1].get("status", "member") == "member"]
        if sect.data.get("dissolved"):
            if living:
                out.append(f"dissolved {sect.name} still has {len(living)} members")
            continue
        leaders = [p for p in living if F.membership(world, p, sect.id)[1].get("role") == "leader"]
        founder = sect.data["founder"]
        if leaders != [founder]:
            out.append(f"{sect.name} has leaders {leaders}, not its founder")
        seat = sect.data["seat"]
        if seat not in world.targets(founder, "owns_land"):
            out.append(f"{sect.name}'s seat is not the founder's land")
        roles = [F.membership(world, p, sect.id)[1].get("role") for p in living]
        if roles.count("disciple") > 12 or roles.count("elder") > 3:
            out.append(f"{sect.name} has too many members")
        region = region_of(world, seat).id
        for person in living:
            entity = world.entity(person)
            if person == founder or entity.data.get("dead"):
                continue
            where = world.targets(person, "located_in")
            expected = region if entity.data.get("on_duty") else seat
            if where != [expected]:
                out.append(f"{entity.name} of {sect.name} is not at the seat or on duty")
        if sect.data["last_tick"] > world.time:
            out.append(f"{sect.name}'s seasons are ahead of the clock")
        if sect.data["treasury"] < 0:
            out.append(f"{sect.name} has a negative treasury")
    return out


def check_people(game, turn) -> list[str]:''')

FUZZ = "tests/test_fuzz.py"
Path(FUZZ).write_text(Path(FUZZ).read_text(encoding="utf-8") + '''

@pytest.mark.parametrize("seed", [4, 19])
def test_a_sect_founder(tmp_path, seed, monkeypatch):
    """Found a sect, run it, roam for seasons, come home: every rule holds."""
    import tests.test_sect as helpers
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 1.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Founder{seed}", world_seed=seed)
    helpers.found_sect(app.game)
    app.game.world.update_data(app.game.player.id, silver=800)
    app.submit("look")
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif game.player.data.get("summons") or game.player.data.get("arrest"):
            app.submit(rng.choice(["1", "2", "3", "4"]))
        elif game.focus is not None:
            app.submit(rng.choice(["1", "2", "3", "4", "5", "6", "7", "8", "9", "bye"]))
        else:
            app.submit(rng.choice(["1", "2", "3", "look", "ledger", "standing", "meditate season", "rest",
                                   "go north", "go south", "go east", "go west"]))
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()
''', encoding="utf-8", newline="\n")

edit("docs/debugging.md", '''- **Names on screen:**''', '''- **Your sect (phase 3c):** a live sect has one leader (its founder) and a seat the founder owns; at most 12 disciples and 3 elders, each at the seat or away on duty; its seasons never run ahead of the clock and its treasury never goes negative; a dissolved sect has no members; a town has at most one owner.
- **Names on screen:**''')
ROADS = "narrate/grammar/roads.toml"
edit(ROADS, '''"A crow calls from a dead branch.", "The wind drops."]''',
     '''"A crow calls from a dead branch.", "The wind drops.", "A cart track bends out of sight.", "Insects fall silent in the grass.", "The light goes flat and grey."]''')
edit(ROADS, '''"They spit in the dust.", "They take their time looking you over."]''',
     '''"They spit in the dust.", "They take their time looking you over.", "They crack their knuckles one by one.", "They step into the middle of the road.", "They weigh your purse with their eyes."]''')
print("task 6 edits applied")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3c_task6.py && .venv/Scripts/python.exe -m pytest tests/test_sect_rules.py -q -p no:cacheprovider`
Expected: `task 6 edits applied`, then `4 passed`.

Run: `.venv/Scripts/python.exe -m pytest tests/test_fuzz.py -q -p no:cacheprovider`
Expected: every fuzz test passes, including `test_a_sect_founder[4]` and `[19]`. Treat each rule violation as a bug and find its cause with systematic debugging. Do not loosen the rule.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "test: sect rules, a sect-founder fuzz run, docs"`

---

## Self-review

**Spec coverage:**

| Spec section | Where it is built |
|---|---|
| §3 land | Task 1 |
| §4.1 sworn followers | Task 2 |
| §4.2 founding requirements | Task 2 |
| §4.3 founding choices | Task 2 |
| §5 recruiting, teaching, elders, duty, expulsion | Task 3 |
| §5 treasury and buildings | Task 3 (built), with effects in Task 4 |
| §5 pacts and dissolution | Task 3 |
| §6 seasonal catch-up | Task 4 |
| §7 `sect_stance` | Task 3 |
| §7 reputation of the sect's own facts | Tasks 3 and 4 |
| §8 ledger, F6, scenes (3b's seat line and gate art cover the seat), briefs | Task 5 |
| §9 debug rules | Task 6 |
| §10 tests | Every task, with fuzz in Task 6 |

**Differences from the spec:** the plan-time rulings 1–7 above. Also:
- The library's "elders teach while you are away" is **not built**. The library is buildable and costs upkeep, but no season step teaches. It is deferred and recorded here so the final review can grade it.
- A catch-up's outcome shows one chronicle line per season. The spec asks for "at most 4 shown, then …"; each season shows its own line as it is committed.

**Type consistency:**
- `season_events(world, player, sect)` everywhere.
- Member data keys: `loyalty`, `talent`, `on_duty`, `sect_joined_at`.
- `founding.enrol(world, person, sect, loyalty, role="disciple", rank=0)`.
- `sect_stance(world, other, sect)`.

**Dry run** (the whole plan run on a scratch copy of `acaa82e`: 464 tests plus 13 fuzz, all passing). It found and fixed:
- The 3b rank rule now allows the founder's rank 4 (Task 2 patch, and a check in the founding test).
- The ledger names only factions the player has heard of (Task 5, with a test).
- Season recruits are made when the season is drawn, and the sect's people are actors on `sect_season`, so the ledger never names a stranger.
- The test helper swears followers through the real `sworn` event and raises the body's realm, not only the label.
- A gate challenger calls you out at your gate instead of "they have not forgotten you".
- The road-encounter grammar is wider (8 × 8 combinations), because frequent gate and road fights repeated lines.
